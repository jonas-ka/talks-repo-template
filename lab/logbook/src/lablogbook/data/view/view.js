/* The log-book view: everything runs in the browser over the data embedded in the page. */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("lb-data").textContent);
  const E = D.entries.slice().sort((a, b) => (a.date + (a.time || "") + a.id).localeCompare(b.date + (b.time || "") + b.id));
  const byId = Object.fromEntries(E.map((e) => [e.id, e]));
  const wikiBy = Object.fromEntries(D.wiki.map((w) => [w.page, w]));
  const refBy = Object.fromEntries(D.references.map((r) => [r.key, r]));
  const $ = (s, el = document) => el.querySelector(s);
  const main = $("#main"), side = $("#side"), app = $(".app");

  // ------------------------------------------------------------------ helpers -------------
  // The "New entry" form with fields filled in (GitHub reads them from the link by field id).
  const newEntry = (fields) => D.site ? D.site.new_entry + Object.entries(fields).filter(([, v]) => v)
    .map(([k, v]) => `&${k}=${encodeURIComponent(v)}`).join("") : null;
  const resolveLink = (e, anchor, text) => D.site ? ` <a class="link" href="${newEntry({ title: "Resolved: " + (text || e.title).slice(0, 70),
    resolves: e.id + "#" + anchor, project: e.project, subproject: e.subproject })}" title="Write an entry that resolves this item">Resolve</a>` : "";
  const nEntries = (n) => `${n} ${n === 1 ? "entry" : "entries"}`;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[−–]/g, "-").toLowerCase();
  const enc = encodeURIComponent;
  const name = (h) => (D.people[h] && D.people[h].name) || h;
  const ymd = (iso) => { const [y, m, d] = String(iso).split("-").map(Number); return new Date(y, (m || 1) - 1, d || 1); };
  const fmtDay = (iso) => ymd(iso).toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const fmtDate = (iso) => ymd(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  const fmtShort = (iso) => ymd(iso).toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" });
  const daysSince = (iso) => Math.round((ymd(D.today) - ymd(iso)) / 864e5);
  const fmtLogged = (s) => { if (!s) return "not yet logged"; const d = new Date(s); return isNaN(d) ? s : "logged " + d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); };
  const withText = (w) => (w ? (w === "claude" ? "Claude Code" : w) : "");
  const projectsOf = (e) => [e.project].concat(e.also || []);
  const COLORS = ["blue", "teal", "green"];   // lab colours for names; red and yellow stay for issues, corrections and open items
  const hue = (s) => { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return COLORS[h % COLORS.length]; };
  const KIND = { note: "gray", run: "blue", calibration: "green", maintenance: "maroon", incident: "red", meeting: "yellow", correction: "red", redaction: "gray" };
  const tag = (text, color, href) => href ? `<a class="tag ${color}" href="${href}">${esc(text)}</a>` : `<span class="tag ${color}">${esc(text)}</span>`;
  const kindTag = (k, link = true) => tag(k, KIND[k] || "gray", link ? `#/?kind=${enc(k)}` : null);
  const projTag = (p, sub, link = true) => tag(p + (sub ? " · " + sub : ""), hue(p), link ? `#/project/${enc(p)}` : null);
  const initials = (h) => { const n = name(h).replace(/[^\p{L}\s.-]/gu, "").split(/[\s.]+/).filter(Boolean); return ((n[0] || h)[0] + (n.length > 1 ? n[n.length - 1][0] : "")).toUpperCase(); };
  const avatar = (h, big) => `<span class="av hue-${hue(h)}${big ? " big" : ""}" aria-hidden="true">${esc(initials(h))}</span>`;
  const personLink = (h) => `<a class="person" href="#/person/${enc(h)}">${avatar(h)}<span>${esc(name(h))}</span></a>`;
  const entryLink = (id, anchor, text) => {
    const e = byId[id];
    const t = text || (e ? e.title : id) + (anchor ? " (#" + anchor + ")" : "");
    return e ? `<a class="link" href="#/e/${enc(id)}${anchor ? "/" + enc(anchor) : ""}">${esc(t)}</a>` : `<span title="${esc(id)}">${esc(t)}</span>`;
  };
  const I = {   // a few line icons (hidden where SVG paths cannot be drawn; labels stay)
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>', plus: '<path d="M12 5v14M5 12h14"/>',
    chev: '<path d="M9 6l6 6-6 6"/>', down: '<path d="M6 9l6 6 6-6"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    export: '<path d="M12 15V3M7 8l5-5 5 5M5 21h14"/>', link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    git: '<circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="9" r="2"/><path d="M6 8v8M18 11c0 4-6 3-10 6"/>',
    chat: '<path d="M4 5h16v11H9l-5 4z"/>', pen: '<path d="M4 20l4-1L19 8l-3-3L5 16z"/>',
  };
  const icon = (n) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${I[n] || ""}</svg>`;
  const store = { get(k) { try { return localStorage.getItem(k); } catch (err) { return null; } },
                  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (err) { /* private window */ } } };

  const FIG = /<a class="lb-crop"[^>]*?style="aspect-ratio: ([\d.]+) \/ ([\d.]+)"[^>]*><img src="([^"]*)" data-png="([^"]*)"/;
  for (const e of E) {
    e._title = norm(e.title);
    e._hay = norm([e.id, e.title, e.text, e.kind, e.project, e.subproject, (e.also || []).join(" "), (e.apparatus || []).join(" "),
      (e.tags || []).join(" "), e.authors.map(name).join(" "), e.authors.join(" "), (e.runs || []).join(" "),
      (e.parameters || []).map((p) => `${p.name} ${p.value} ${p.unit || ""}`).join(" "),
      (e.epics || []).map((s) => s.group + " " + s.pvs.map((p) => `${p.name} ${p.value} ${p.unit || ""}`).join(" ")).join(" "),
      (e.attendees || []).map(name).join(" ")].join(" "));
    const m = FIG.exec(e.html || "");
    e._thumb = m ? { w: m[1], h: m[2], src: m[3], png: m[4] } : null;     // the entry's first figure
  }

  // ------------------------------------------------------------------ figures: SVG, else PNG -
  // Some browsers cannot paint SVG paths on screen: the Claude app's built-in browser fills them as
  // solid boxes, although it draws them correctly into a canvas. It names itself in the user agent
  // ("Claude/…"), so it is recognised by that; any other browser is tested with a small triangle
  // drawn into a canvas. Either way every figure switches to the PNG saved next to its SVG, and
  // the line icons are hidden.
  const CLAUDE_APP = /\bClaude\/\d/.test(navigator.userAgent);
  let usePng = false;
  const svgTest = new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      try {
        const c = document.createElement("canvas"); c.width = 20; c.height = 20;
        const x = c.getContext("2d"); x.drawImage(img, 0, 0, 20, 20);
        resolve(x.getImageData(17, 2, 1, 1).data[3] === 0);       // top right lies outside the triangle
      } catch (err) { resolve(true); }                            // cannot tell: keep the SVG
    };
    img.onerror = () => resolve(true);
    img.src = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20"><path d="M0 0 L0 20 L20 20 Z" fill="#000"/></svg>');
  });
  function figures(root) {
    if (!usePng) return;
    document.documentElement.classList.add("no-svg-paths");
    root.querySelectorAll("img[data-png]").forEach((im) => { if (im.dataset.png && !im.dataset.swapped) { im.src = im.dataset.png; im.dataset.swapped = "1"; } });
  }

  // ------------------------------------------------------------------ filters -------------
  const F = { q: "", project: new Set(), sub: new Set(), who: new Set(), app: new Set(), kind: new Set(), tag: new Set(),
              from: "", to: "", open: false, figs: false, release: false, sort: "new", full: false };
  const SETS = ["project", "sub", "who", "app", "kind", "tag"];
  const FIELDS = new Set(["kind", "project", "by", "tag", "on"]);   // kind:run project:fast by:aa tag:x on:source
  function parseQuery(q) {
    const terms = [], fields = {};
    const re = /(\w+):("[^"]*"|\S+)|"([^"]*)"|(\S+)/g;
    let m;
    while ((m = re.exec(q))) {
      if (m[1] && FIELDS.has(m[1].toLowerCase())) fields[m[1].toLowerCase()] = norm(m[2].replace(/"/g, ""));
      else terms.push(norm(m[1] ? m[0].replace(/"/g, "") : m[3] != null ? m[3] : m[4]));   // e.g. a PV name SRC:Extract
    }
    return { terms: terms.filter(Boolean), fields };
  }
  const openCount = (e) => Object.values(e.resolved || {}).filter((r) => !r.length).length;
  function match(e, Q) {
    if (F.project.size && !projectsOf(e).some((p) => F.project.has(p))) return false;
    if (F.sub.size && !F.sub.has(e.project + "/" + (e.subproject || ""))) return false;
    if (F.who.size && !e.authors.some((a) => F.who.has(a))) return false;
    if (F.app.size && !(e.apparatus || []).some((a) => F.app.has(a))) return false;
    if (F.kind.size && !F.kind.has(e.kind)) return false;
    if (F.tag.size && !(e.tags || []).some((t) => F.tag.has(t))) return false;
    if (F.from && e.date < F.from) return false;
    if (F.to && e.date > F.to) return false;
    if (F.open && !openCount(e)) return false;
    if (F.figs && !e.figures) return false;
    if (F.release && e.release !== "candidate") return false;
    const f = Q.fields;
    if (f.kind && norm(e.kind) !== f.kind) return false;
    if (f.project && !projectsOf(e).some((p) => norm(p).includes(f.project))) return false;
    if (f.by && !e.authors.some((a) => norm(a) === f.by || norm(name(a)).includes(f.by))) return false;
    if (f.tag && !(e.tags || []).some((t) => norm(t) === f.tag)) return false;
    if (f.on && !(e.apparatus || []).some((a) => norm(a) === f.on)) return false;
    return Q.terms.every((t) => e._hay.includes(t));
  }
  const score = (e, Q) => Q.terms.reduce((s, t) => s + (e._title.includes(t) ? 3 : 1), 0);
  function filtered() {
    const Q = parseQuery(F.q);
    let list = E.filter((e) => match(e, Q));
    if (Q.terms.length && F.sort === "relevance") list.sort((a, b) => score(b, Q) - score(a, Q));
    else if (F.sort !== "old") list = list.slice().reverse();
    return { list, Q };
  }
  const anyFilter = () => F.q || SETS.some((k) => F[k].size) || F.from || F.to || F.open || F.figs || F.release;
  function toHash() {
    const p = new URLSearchParams();
    if (F.q) p.set("q", F.q);
    for (const k of SETS) if (F[k].size) p.set(k, [...F[k]].join("|"));
    for (const k of ["from", "to"]) if (F[k]) p.set(k, F[k]);
    for (const k of ["open", "figs", "release", "full"]) if (F[k]) p.set(k, "1");
    if (F.sort !== "new") p.set("sort", F.sort);
    const s = p.toString();
    return s ? "?" + s : "";
  }
  function fromHash(qs) {
    const p = new URLSearchParams(qs || "");
    F.q = p.get("q") || "";
    for (const k of SETS) F[k] = new Set((p.get(k) || "").split("|").filter(Boolean));
    F.from = p.get("from") || ""; F.to = p.get("to") || "";
    F.open = p.has("open"); F.figs = p.has("figs"); F.release = p.has("release"); F.full = p.has("full");
    F.sort = p.get("sort") || "new";
  }
  function count(fn, list = E) { const c = {}; for (const e of list) for (const k of fn(e)) c[k] = (c[k] || 0) + 1; return c; }
  let listBase = "#/";
  function go() { const h = listBase + toHash(); if (location.hash !== h) location.hash = h; else render(); }

  // filter menus ("pills"): each opens a small menu of checkboxes with counts
  const FILTERS = [
    { key: "project", label: "Project", opts: () => {
        const pc = count(projectsOf), sc = count((e) => (e.subproject ? [e.project + "/" + e.subproject] : []));
        const out = [];
        for (const p of D.projects) {
          if (!pc[p.name]) continue;
          out.push({ set: "project", v: p.name, l: p.name, n: pc[p.name] });
          for (const s of p.subprojects) if (sc[p.name + "/" + s]) out.push({ set: "sub", v: p.name + "/" + s, l: s, n: sc[p.name + "/" + s], sub: true });
        }
        return out; } },
    { key: "who", label: "Person", opts: () => { const c = count((e) => e.authors); return Object.keys(c).sort((a, b) => name(a).localeCompare(name(b))).map((h) => ({ set: "who", v: h, l: name(h), n: c[h] })); } },
    { key: "app", label: "Apparatus", opts: () => { const c = count((e) => e.apparatus || []); return D.apparatus.filter((a) => c[a.id]).map((a) => ({ set: "app", v: a.id, l: a.name, n: c[a.id] })); } },
    { key: "kind", label: "Kind", opts: () => { const c = count((e) => [e.kind]); return Object.keys(c).sort().map((k) => ({ set: "kind", v: k, l: k, n: c[k] })); } },
    { key: "tag", label: "Tag", opts: () => { const c = count((e) => e.tags || []); return Object.keys(c).sort((a, b) => c[b] - c[a] || a.localeCompare(b)).map((t) => ({ set: "tag", v: t, l: t, n: c[t] })); } },
    { key: "date", label: "Date" },
    { key: "more", label: "More" },
  ];
  function pillLabel(f) {
    if (f.key === "project") { const n = F.project.size + F.sub.size; return n ? `Project: ${[...F.project, ...[...F.sub].map((s) => s.split("/")[1])].join(", ")}` : null; }
    if (f.key === "date") return F.from || F.to ? `Date: ${F.from ? fmtDate(F.from) : "…"} – ${F.to ? fmtDate(F.to) : "…"}` : null;
    if (f.key === "more") { const on = [F.open && "open items", F.figs && "with figures", F.release && "release candidates"].filter(Boolean); return on.length ? on.join(", ") : null; }
    const s = F[f.key];
    if (!s.size) return null;
    const lbl = [...s].map((v) => (f.key === "who" ? name(v) : f.key === "app" ? ((D.apparatus.find((a) => a.id === v) || {}).name || v) : v));
    return `${f.label}: ${lbl.join(", ")}`;
  }
  function clearFilter(key) {
    if (key === "project") { F.project.clear(); F.sub.clear(); }
    else if (key === "date") { F.from = ""; F.to = ""; }
    else if (key === "more") { F.open = F.figs = F.release = false; }
    else F[key].clear();
  }
  let popKey = null;
  function closePop() { $("#pop-host").innerHTML = ""; popKey = null; }
  function openPop(key, btn) {
    if (popKey === key) { closePop(); return; }
    popKey = key;
    const f = FILTERS.find((x) => x.key === key);
    let h = "";
    if (key === "date") {
      h = `<div class="dates"><label for="pf">From</label><input id="pf" type="date" data-date="from" value="${esc(F.from)}">` +
        `<label for="pt">To</label><input id="pt" type="date" data-date="to" value="${esc(F.to)}"></div>` +
        `<div class="row"><button class="btn ghost" data-preset="7">Last 7 days</button><button class="btn ghost" data-preset="30">Last 30 days</button>` +
        `<button class="btn ghost" data-preset="year">This year</button></div>`;
    } else if (key === "more") {
      h = [["open", "With open items"], ["figs", "With figures"], ["release", "Release candidates"]].map(([k, l]) =>
        `<label class="opt"><input type="checkbox" data-flag="${k}" ${F[k] ? "checked" : ""}><span>${l}</span></label>`).join("");
    } else {
      const opts = f.opts();
      h = opts.length ? opts.map((o) => `<label class="opt${o.sub ? " sub" : ""}"><input type="checkbox" data-set="${o.set}" value="${esc(o.v)}" ${F[o.set].has(o.v) ? "checked" : ""}>` +
        `<span>${esc(o.l)}</span><span class="n">${o.n}</span></label>`).join("") : `<div class="hint">Nothing to filter by yet.</div>`;
    }
    const host = $("#pop-host");
    host.innerHTML = `<div class="pop" role="dialog" aria-label="${esc(f.label)}">${h}</div>`;
    const pop = host.firstChild, r = btn.getBoundingClientRect();
    pop.style.left = Math.max(8, Math.min(r.left, innerWidth - pop.offsetWidth - 8)) + "px";
    pop.style.top = r.bottom + 6 + "px";
    const first = pop.querySelector("input,button"); if (first) first.focus();
  }
  $("#pop-host").addEventListener("change", (ev) => {
    const t = ev.target;
    if (t.dataset.set) { t.checked ? F[t.dataset.set].add(t.value) : F[t.dataset.set].delete(t.value); }
    else if (t.dataset.date) F[t.dataset.date] = t.value;
    else if (t.dataset.flag) F[t.dataset.flag] = t.checked;
    const k = popKey; go(); popKey = null; reopen(k);
  });
  $("#pop-host").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-preset]");
    if (!b) return;
    if (b.dataset.preset === "year") { F.from = D.today.slice(0, 4) + "-01-01"; F.to = ""; }
    else { const d = ymd(D.today); d.setDate(d.getDate() - +b.dataset.preset); F.from = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; F.to = ""; }
    closePop(); go();
  });
  function reopen(key) { const btn = main.querySelector(`[data-pill="${key}"]`); if (btn) openPop(key, btn); }
  document.addEventListener("mousedown", (ev) => { if (popKey && !ev.target.closest(".pop") && !ev.target.closest("[data-pill]")) closePop(); });

  // ------------------------------------------------------------------ pieces --------------
  function highlight(text, terms) {
    let s = esc(text);
    for (const t of terms) {
      if (t.length < 2) continue;
      s = s.replace(new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"), "<mark>$1</mark>");
    }
    return s;
  }
  function snippet(e, terms) {
    const text = e.text || "";
    let at = 0;
    if (terms.length) { const i = norm(text).indexOf(terms[0]); if (i > 60) at = i - 60; }
    return highlight((at ? "… " : "") + text.slice(at, at + 280), terms);
  }
  function markStates(e, root) {   // "open" / "resolved in …" on each issue and todo with an id
    for (const [a, by] of Object.entries(e.resolved || {})) {
      const el = root.querySelector(`[id="e-${CSS.escape(e.id)}--${CSS.escape(a)}"]`);
      if (!el || el.querySelector(".state")) continue;
      const s = document.createElement("span");
      s.className = "state status " + (by.length ? "done" : "open");
      const pr = (e.priority || {})[a] || { level: "medium", by: null };
      s.innerHTML = by.length ? "Resolved in " + by.map((x) => entryLink(x)).join(", ")
        : "Open " + prioTag({ priority: pr.level, by: pr.by, overdue: isOverdue(pr, e) }) +
          resolveLink(e, a, el.textContent.trim());
      el.appendChild(s);
    }
  }
  function cardMeta(e) {
    const oc = openCount(e);
    return `<div class="meta">${e.time ? `<span class="time">${esc(e.time)}</span>` : ""}${kindTag(e.kind, false)}${projTag(e.project, e.subproject, false)}` +
      `${(e.also || []).map((p) => projTag(p, null, false)).join("")}` +
      `${oc ? `<span class="status open">${oc} open</span>` : ""}${e.correctedBy.length ? tag("corrected", "red") : ""}</div>`;
  }
  function card(e, terms) {
    const th = e._thumb;
    const who = `<div class="who"><span class="avs">${e.authors.map((a) => avatar(a)).join("")}</span><span>${esc(e.authors.map(name).join(", "))}${e.with ? ` <span class="muted">with ${esc(withText(e.with))}</span>` : ""}</span>` +
      `${(e.tags || []).map((t) => tag(t, hue(t))).join("")}</div>`;
    if (F.full) {
      return `<article class="card full" data-id="${esc(e.id)}"><a class="card-head" href="#/e/${enc(e.id)}">${cardMeta(e)}<h2>${highlight(e.title, terms)}</h2></a>${who}` +
        `${(e.parameters || []).length ? paramTable(e) : ""}<div class="prose small">${e.html}</div></article>`;
    }
    return `<a class="card" href="#/e/${enc(e.id)}"><div class="card-main">${cardMeta(e)}<h2>${highlight(e.title, terms)}</h2>${who}` +
      `<p class="snip">${snippet(e, terms)}</p></div>` +
      (th ? `<span class="thumb" style="aspect-ratio: ${th.w} / ${th.h}"><img src="${th.src}" data-png="${th.png}" alt="" loading="lazy"></span>` : "") + `</a>`;
  }
  function cards(list, terms, limit) {
    if (!list.length) return `<p class="empty">No entries match.</p>`;
    let h = "", day = null;
    const n = F.full ? Math.min(limit, 30) : limit;
    for (const e of list.slice(0, n)) {
      if (e.date !== day) { day = e.date; h += `<div class="group">${esc(fmtDay(day))}</div>`; }
      h += card(e, terms);
    }
    if (list.length > n) h += `<button class="btn more-btn" data-more="${n + (F.full ? 30 : 100)}">Show ${Math.min(F.full ? 30 : 100, list.length - n)} more</button>`;
    return h;
  }
  const PRIO = ["low", "medium", "high", "asap"];
  // ASAP for longer than D.asapDays days, counted from the entry that made it ASAP
  const isOverdue = (pr, e) => pr.level === "asap" && daysSince(pr.since || e.date) > (D.asapDays || 2);
  const PRIO_LABEL = { low: "Low", medium: "Medium", high: "High", asap: "ASAP" };
  const PRIO_HUE = { low: "gray", medium: "blue", high: "yellow", asap: "red" };
  function prioTag(x) {
    const by = x.by ? ` title="Priority set in ${esc((byId[x.by] || { title: x.by }).title)}"` : "";
    return `<span class="tag ${PRIO_HUE[x.priority]}"${by}>${PRIO_LABEL[x.priority]}</span>` +
      (x.overdue ? ` <span class="tag red overdue" title="ASAP for longer than ${D.asapDays || 2} days">overdue</span>` : "");
  }
  // open items, most urgent first: an ASAP item open longer than D.asapDays days, then by
  // priority, then the oldest first; `order` "old" / "new" sorts by date only
  function openItems(list, order = "urgent") {
    const out = [];
    for (const e of list) for (const [anchor, by] of Object.entries(e.resolved || {})) if (!by.length) {
      const b = (e.blocks || {})[anchor] || { name: "todo", text: "" };
      const pr = (e.priority || {})[anchor] || { level: "medium", by: null };
      out.push({ e, anchor, name: b.name, text: b.text, priority: pr.level, by: pr.by, age: daysSince(e.date),
                 overdue: isOverdue(pr, e) });
    }
    const byDate = (a, b) => a.e.date.localeCompare(b.e.date) || a.e.id.localeCompare(b.e.id);
    if (order === "old") return out.sort(byDate);
    if (order === "new") return out.sort((a, b) => byDate(b, a));
    return out.sort((a, b) => (b.overdue - a.overdue) || (PRIO.indexOf(b.priority) - PRIO.indexOf(a.priority)) || byDate(a, b));
  }
  function table(head, trs, cls = "t") {
    return `<div class="tbl-wrap"><table class="${cls}"><thead><tr>${head.map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>` +
      trs.map((r) => `<tr${r.cls ? ` class="${r.cls}"` : ""}>${r.cells.map((c) => {
        const c2 = typeof c === "number" ? "num" : c && c.cls ? c.cls : "";
        return `<td${c2 ? ` class="${c2}"` : ""}>${c && c.html != null ? c.html : esc(c)}</td>`; }).join("")}</tr>`).join("") +
      `</tbody></table></div>`;
  }
  const paramTable = (e) => table(["Parameter", "Value", "Unit", "Note"], e.parameters.map((p) => ({ cells: [{ html: `<code class="c">${esc(p.name)}</code>` }, typeof p.value === "number" ? p.value : String(p.value), p.unit || "", p.note || ""] })));
  const pageHead = (title, desc) => `<h1 class="title">${esc(title)}</h1>${desc ? `<p class="desc">${desc}</p>` : ""}`;
  function crumbs(parts) {
    $("#crumbs").innerHTML = parts.map((p, i) => (i ? `<span class="sep">/</span>` : "") +
      (p.href ? `<a href="${p.href}">${esc(p.t)}</a>` : `<span class="c">${esc(p.t)}</span>`)).join("");
  }
  function toolbar(n, total, opts = {}) {
    const pills = FILTERS.map((f) => {
      const lbl = pillLabel(f);
      return lbl ? `<button class="pill on" data-pill="${f.key}">${esc(lbl)}<span class="x" data-clear="${f.key}" title="Remove">×</span></button>`
                 : `<button class="pill" data-pill="${f.key}">${f.label}${icon("down")}</button>`;
    }).join("");
    return `<div class="toolbar"><label class="search">${icon("search")}<span class="sr">Search</span>` +
      `<input id="q" type="search" placeholder="Search text, settings, PVs, people…" value="${esc(F.q)}" autocomplete="off" spellcheck="false"><kbd>/</kbd></label></div>` +
      `<div class="bar2">${pills}${anyFilter() ? `<button class="btn ghost" data-act="clear">Clear</button>` : ""}` +
      `<span class="count">${n} of ${total}</span>` +
      (opts.full ? `<label class="switch"><input type="checkbox" data-act="full" ${F.full ? "checked" : ""}><span>Full entries</span></label>` : "") +
      (opts.sort ? `<select class="select-plain" id="sort" aria-label="Order"><option value="new">Newest first</option><option value="old">Oldest first</option><option value="relevance">Best match</option></select>` : "") +
      (opts.export ? `<button class="btn ghost" data-act="export">${icon("export")}Export</button>` : "") + `</div>`;
  }
  const toggle = (title, body, n, open = true) =>
    `<details class="toggle"${open ? " open" : ""}><summary><span class="tri" aria-hidden="true">▸</span>${esc(title)}${n != null ? ` <span class="n">${n}</span>` : ""}</summary><div>${body}</div></details>`;
  function linkList(ids, here) {
    return `<ul class="links">${ids.map((x) => { const e = byId[x]; return e ? `<li class="${x === here ? "here" : ""}">` +
      (x === here ? esc(e.title) : entryLink(x)) + `<span class="d">${esc(fmtDate(e.date))}</span></li>` : ""; }).join("")}</ul>`;
  }

  // ------------------------------------------------------------------ views ---------------
  let limit = 100;
  const OP = { prio: "", sort: "urgent" };   // the open-items page's own priority filter and order
  function viewEntries() {
    listBase = "#/";
    const { list, Q } = filtered();
    crumbs([{ t: "Entries" }]);
    main.innerHTML = pageHead("Entries") + toolbar(list.length, E.length, { sort: true, export: true, full: true }) + cards(list, Q.terms, limit);
    $("#sort").value = F.sort;
    if (F.full) list.slice(0, 30).forEach((e) => markStates(e, main));
  }
  function viewOpen() {
    listBase = "#/open";
    const { list, Q } = filtered();
    const items = openItems(list, OP.sort).filter((x) => (!OP.prio || x.priority === OP.prio) &&
      (!Q.terms.length || Q.terms.every((t) => norm(x.text + " " + x.e.title).includes(t))));
    crumbs([{ t: "Open items" }]);
    main.className = "wide";
    main.innerHTML = pageHead("Open items", `Issues and todos that no later entry has resolved yet, most urgent first: items ASAP for longer than ${D.asapDays || 2} days, then by priority, then the oldest. A new entry resolves one by listing it under <code class="c">resolves:</code>, and changes a priority with <code class="c">priority: {&lt;entry-id&gt;#&lt;item&gt;: low}</code>.`) +
      toolbar(items.length, openItems(E).length) +
      `<div class="bar2"><select class="select-plain" id="op-prio" aria-label="Priority"><option value="">Every priority</option>` +
      PRIO.slice().reverse().map((k) => `<option value="${k}"${OP.prio === k ? " selected" : ""}>${PRIO_LABEL[k]}</option>`).join("") + `</select>` +
      `<select class="select-plain" id="op-sort" aria-label="Order">` +
      [["urgent", "Most urgent first"], ["old", "Oldest first"], ["new", "Newest first"]].map(([k, l]) => `<option value="${k}"${OP.sort === k ? " selected" : ""}>${l}</option>`).join("") + `</select></div>` +
      (items.length ? table(["Item", "Priority", "Entry", "Project", "Open since", "By"], items.map((x) => ({ cls: x.overdue ? "overdue" : "", cells: [
        { html: `<span class="status open" title="${esc(x.name)}"></span> ${highlight(x.text, Q.terms)}${resolveLink(x.e, x.anchor, x.text)}`, cls: "item" },
        { html: prioTag(x), cls: "nowrap" },
        { html: entryLink(x.e.id, x.anchor, x.e.title), cls: "entry" },
        { html: projTag(x.e.project, x.e.subproject) },
        { html: `${esc(fmtDate(x.e.date))} <span class="tag gray">${x.age} d</span>`, cls: "nowrap" },
        { html: `<span class="avs">${x.e.authors.map((a) => avatar(a)).join("")}</span>` }] })), "t full") : `<p class="empty">Nothing open.</p>`);
  }
  // ------------------------------------------------------------------ purchases -----------
  // Every item of every order (entries of kind order) and whether it arrived; filtered in place.
  const PU = { q: "", open: false };
  const money = (v) => typeof v === "number"
    ? esc((v < 0 ? "−" : "") + (D.currency || "$") + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: v % 1 ? 2 : 0, maximumFractionDigits: 2 }))
    : esc(v == null ? "" : v);
  const isoDate = (s) => /^\d{4}-\d{2}-\d{2}/.test(s || "");
  function viewPurchases() {
    const all = D.orders || [];
    crumbs([{ t: "Purchases" }]);
    main.className = "wide";
    main.innerHTML = pageHead("Purchases", `Every item of every order (entries of kind <code class="c">order</code>) and whether it has arrived. ` +
      `An item stays open until an entry says it arrived: "Resolve" on the item, or "All arrived" for everything still open in an order.`) +
      `<div class="bar2"><label class="search">${icon("search")}<span class="sr">Filter</span><input id="pu-q" type="search" placeholder="Filter items, vendors, orders, quotes…" value="${esc(PU.q)}" autocomplete="off" spellcheck="false"></label>` +
      `<label class="switch"><input type="checkbox" id="pu-open"${PU.open ? " checked" : ""}><span>Open only (${all.filter((x) => x.status === "open").length})</span></label>` +
      `<span class="count" id="pu-n"></span><button class="btn ghost" data-act="pu-csv" title="The items shown, as a table for Excel or Google Sheets">${icon("export")}Download CSV</button></div><div id="pu-t"></div>`;
    purchasesTable();
  }
  function purchasesShown() {
    const terms = norm(PU.q).split(/\s+/).filter(Boolean);
    return (D.orders || []).filter((x) => (!PU.open || x.status === "open") &&
      terms.every((t) => norm([x.order, x.item, x.vendor, x.info, x.ordered].join(" ")).includes(t)));
  }
  function purchasesCsv() {   // the rows shown, one line per item; numbers stay numbers
    const head = ["Order", "#", "Item", "Vendor", "Qty", "Unit cost", "Total", "Ordered", "Status", "Arrived on", "Arrived in entry", "Quote / info", "Order entry"];
    const q = (v) => v == null ? "" : typeof v === "number" ? String(v) : `"${String(v).replace(/"/g, '""')}"`;
    const lines = [head.map(q).join(",")].concat(purchasesShown().map((x) => [x.order, x.n, x.item, x.vendor, x.qty, x.unit_cost, x.total, x.ordered,
      x.status, x.arrived_on, x.arrived_in, x.info, x.entry].map(q).join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\ufeff" + lines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" }));
    a.download = `purchases-${D.today}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  function purchasesTable() {
    const all = D.orders || [], rows = purchasesShown();
    const openBy = {};   // what is still open per order: one link resolves all of it
    for (const x of all) if (x.status === "open") (openBy[x.entry] = openBy[x.entry] || []).push(x.key);
    let last = null;
    $("#pu-n").textContent = `${rows.length} of ${all.length}`;
    $("#pu-t").innerHTML = rows.length ? table(["Order", "#", "Item", "Vendor", "Qty", "Unit cost", "Total", "Ordered", "Status", "Quote / info"], rows.map((x) => {
      const e = byId[x.entry] || { id: x.entry, title: x.entry, project: "" };
      const first = x.entry !== last; last = x.entry;
      const rest = openBy[x.entry] || [];
      const allArrived = first && rest.length > 1 && D.site ? ` <a class="link" href="${newEntry({ title: "Arrived: order " + x.order,
        resolves: rest.join(", "), project: e.project, tags: "purchase" })}" title="Write an entry that says everything still open in this order arrived">All arrived</a>` : "";
      const info = /^https?:\/\//.test(x.info || "")
        ? `<a class="link" href="${esc(x.info)}" rel="noopener" title="${esc(x.info)}">${esc(x.info.replace(/^https?:\/\/(www\.)?/, "").slice(0, 32))}…</a>` : esc(x.info || "");
      const st = x.status === "open" ? `<span class="status open"></span> Open${resolveLink(e, "item-" + x.n, x.item)}`
        : `<span class="status done"></span> Arrived${isoDate(x.arrived_on) ? " " + esc(fmtDate(x.arrived_on)) : ""}${x.arrived_in ? " · " + entryLink(x.arrived_in) : ""}`;
      return { cells: [{ html: first ? entryLink(x.entry, null, "Order " + x.order) + allArrived : "", cls: "nowrap" }, x.n,
        { html: esc(x.item), cls: "item" }, { html: x.vendor ? esc(x.vendor) : `<span class="muted">–</span>`, cls: "nowrap" },
        typeof x.qty === "number" ? x.qty : String(x.qty == null ? "" : x.qty),
        { html: money(x.unit_cost), cls: "num" }, { html: money(x.total), cls: "num" },
        { html: isoDate(x.ordered) ? esc(fmtDate(x.ordered)) : esc(x.ordered || ""), cls: "nowrap" }, { html: st, cls: "nowrap" },
        { html: info, cls: "wrap" }] };
    }), "t full") : `<p class="empty">No items.</p>`;
  }
  function snapshotTable(s, other) {
    const ov = other ? Object.fromEntries(other.pvs.map((p) => [p.name, p])) : {};
    return table(["PV", "Value", "Unit", "Severity"].concat(other ? ["Δ to the other"] : []), s.pvs.map((p) => {
      const o = ov[p.name];
      const changed = other && (!o || String(o.value) !== String(p.value));
      const cells = [{ html: `<code class="c">${esc(p.name)}</code>` }, typeof p.value === "number" ? p.value : String(p.value), p.unit || "", p.severity || ""];
      if (other) cells.push(o ? (typeof p.value === "number" && typeof o.value === "number" ? +(p.value - o.value).toPrecision(6) : String(o.value)) : "–");
      return { cells, cls: changed ? "changed" : "" };
    }));
  }
  function thread(e) {
    const seen = new Set([e.id]), todo = [e.id];
    while (todo.length) {
      const x = byId[todo.pop()];
      if (!x) continue;
      for (const y of [].concat(x.related, x.corrects ? [x.corrects] : [], x.correctedBy)) if (y && !seen.has(y) && byId[y]) { seen.add(y); todo.push(y); }
    }
    return [...seen].map((i) => byId[i]).sort((a, b) => (a.date + a.id).localeCompare(b.date + b.id));
  }
  function viewEntry(id, anchor) {
    const e = byId[id];
    if (!e) { crumbs([{ t: "Entries", href: "#/" }]); main.innerHTML = `<p class="empty">No entry ${esc(id)} in this view.</p>`; return; }
    const i = E.indexOf(e), prev = E[i - 1], next = E[i + 1], S = D.site;
    crumbs([{ t: "Entries", href: "#/" + toHash() }, { t: e.project, href: `#/project/${enc(e.project)}` }, { t: e.title }]);
    let acts = "";
    if (S) {
      acts += `<a class="btn ghost sm" href="${e.pr ? `${S.repo}/pull/${e.pr}` : `${S.repo}/pulls?q=${enc(e.id)}`}" title="The pull request that added this entry">${icon("chat")}Discuss</a>`;
      acts += `<a class="btn ghost sm" href="${newEntry({ title: "Correction: " + e.title, kind: "correction", corrects: e.id, project: e.project, subproject: e.subproject })}" title="Write a correction entry">${icon("pen")}Correct</a>`;
      acts += `<a class="btn ghost sm" href="${S.repo}/blob/${S.branch}/${e.path.split("/").map(enc).join("/")}" title="The Markdown file">${icon("git")}Source</a>`;
    }
    acts += `<button class="btn ghost sm" data-act="cite-id" data-id="${esc(e.id)}" title="Copy [[id]] to link this entry from another one">${icon("link")}<span>Copy link</span></button>`;
    $("#top-actions").innerHTML = acts + (prev ? `<a class="iconbtn glyph" href="#/e/${enc(prev.id)}" title="Earlier: ${esc(prev.title)}" aria-label="Earlier entry">‹</a>` : "") +
      (next ? `<a class="iconbtn glyph" href="#/e/${enc(next.id)}" title="Later: ${esc(next.title)}" aria-label="Later entry">›</a>` : "");
    const apps = (e.apparatus || []).map((a) => tag((D.apparatus.find((x) => x.id === a) || {}).name || a, hue(a), `#/apparatus/${enc(a)}`)).join("");
    const extra = [esc(fmtLogged(e.logged)), e.backfilled && `backfilled ${esc(e.backfilled)}`,
      (e.runs || []).length && `runs ${e.runs.map((r) => `<code class="c">${esc(r)}</code>`).join(", ")}`,
      (e.attendees || []).length && `attendees ${e.attendees.map((a) => esc(name(a))).join(", ")}`,
      e.valid_until && `valid until ${esc(fmtDate(e.valid_until))}${e.valid_until < D.today ? ` <span class="tag red">expired</span>` : ""}`,
      e.release === "candidate" && "release candidate", e.migrated_from && `migrated from <code class="c">${esc(e.migrated_from)}</code>`].filter(Boolean);
    let h = `<header class="entry-head"><h1 class="title">${esc(e.title)}</h1>` +
      `<div class="meta"><span class="date">${esc(fmtShort(e.date))}${e.time ? " · " + esc(e.time) : ""}</span>` +
      `${e.authors.map(personLink).join("")}${e.with ? `<span class="muted">with ${esc(withText(e.with))}</span>` : ""}` +
      `${kindTag(e.kind)}${projectsOf(e).map((p, k) => projTag(p, k ? null : e.subproject)).join("")}${apps}` +
      `${(e.tags || []).map((t) => tag(t, hue(t), `#/?tag=${enc(t)}`)).join("")}</div>` +
      `<div class="meta2">${extra.join(" · ")}</div></header>`;
    for (const c of e.correctedBy) {
      const ce = byId[c];
      h += `<div class="banner correct"><b>Corrected</b> by ${entryLink(c)}${ce ? `<span class="q">${esc((ce.text || "").slice(0, 280))}${ce.text.length > 280 ? " …" : ""}</span>` : ""}</div>`;
    }
    for (const r of e.redactedBy) h += `<div class="banner redact"><b>Redacted:</b> see ${entryLink(r)}.</div>`;
    if (e.corrects) h += `<div class="banner correct"><b>Corrects</b> ${entryLink(e.corrects)}</div>`;
    if (e.redacts) h += `<div class="banner redact"><b>Redacts</b> ${entryLink(e.redacts)}</div>`;
    for (const r of e.resolves) {
      const [tid, a] = r.split("#"), t = byId[tid], b = t && (t.blocks || {})[a];
      h += `<div class="banner resolve"><b>Resolves</b> ${entryLink(tid, a)}${b ? `<span class="q">${esc(b.text)}</span>` : ""}</div>`;
    }
    for (const [r, level] of Object.entries(e.reprioritises || {})) {
      const [tid, a] = r.split("#"), t = byId[tid], b = t && (t.blocks || {})[a];
      h += `<div class="banner resolve"><b>Priority ${esc(PRIO_LABEL[level] || level)}</b> ${entryLink(tid, a)}${b ? `<span class="q">${esc(b.text)}</span>` : ""}</div>`;
    }
    if ((e.parameters || []).length) h += paramTable(e);
    h += `<div class="prose" id="body">${e.html}</div>`;
    e.epics.forEach((s, k) => {
      const others = E.filter((x) => x !== e).flatMap((x) => x.epics.filter((y) => y.group === s.group).map((y) => ({ x, y })));
      e["_others" + k] = others;
      h += toggle(`EPICS snapshot · ${s.group}${s.label ? " · " + s.label : ""}`,
        (others.length ? `<label class="compare">Compare with <select data-snap="${k}"><option value="">—</option>${others.map((o, j) =>
          `<option value="${j}">${esc(fmtDate(o.x.date))} · ${esc(o.x.title)}${o.y.label ? " · " + esc(o.y.label) : ""}</option>`).join("")}</select></label>` : "") +
        `<div id="snap-${k}">${snapshotTable(s)}</div>`, s.pvs.length);
    });
    const files = e.data.map((d) => ({ cells: [{ html: `<a class="link" href="${esc(d.url)}">${esc(d.file)}</a>` }, "data", d.source || ""] }))
      .concat(e.attachments.map((a) => ({ cells: [{ html: `<a class="link" href="${esc(a.url)}">${esc(a.file)}</a>` }, "attachment", a.description || ""] })));
    if (files.length) h += toggle("Files", table(["File", "", "Source / note"], files), files.length);
    // what surrounds the entry: in its own box, so it is not read as part of the entry
    let rel = "";
    const th = thread(e);
    if (th.length > 1) rel += toggle("Thread", linkList(th.map((x) => x.id), e.id), th.length);
    if (e.backlinks.length) rel += toggle("Linked from", linkList(e.backlinks), e.backlinks.length);
    if (e.cites.length) rel += toggle("Cited", `<ul class="links">${e.cites.map((k) => { const r = refBy[k]; return `<li>${r ? (r.doi ? `<a href="${esc(r.doi)}">${esc(r.cite)}</a>` : esc(r.cite)) : esc(k)}</li>`; }).join("")}</ul>`, e.cites.length);
    if (Object.keys(e.refs || {}).length) rel += toggle("In the repository", `<dl class="kv">${Object.entries(e.refs).map(([k, v]) => `<dt>${esc(k)}</dt><dd><code class="c">${esc(v)}</code></dd>`).join("")}</dl>`, Object.keys(e.refs).length);
    if (rel) h += `<aside class="related" aria-label="Related"><div class="related-h">Around this entry</div>${rel}</aside>`;
    main.innerHTML = h;
    markStates(e, main);
    main.querySelectorAll("select[data-snap]").forEach((sel) => sel.addEventListener("change", () => {
      const k = +sel.dataset.snap, o = e["_others" + k][sel.value];
      $("#snap-" + k).innerHTML = snapshotTable(e.epics[k], o ? o.y : null);
    }));
    if (anchor) { const el = document.getElementById("e-" + e.id + "--" + anchor); if (el) { el.scrollIntoView({ block: "center" }); el.classList.add("flash"); } }
    else window.scrollTo(0, 0);
  }
  function wikiHtml(page) {
    const w = wikiBy[page];
    if (!w) return "";
    const S = D.site;
    const html = w.html.replace(/^\s*<h[1-6][^>]*>[\s\S]*?<\/h[1-6]>/, "");   // the page's title is shown above it
    return `<div class="prose">${html}</div>` + (S ? `<p><a class="btn ghost sm" href="${S.repo}/edit/${S.branch}/${S.wiki}/${page.split("/").map(enc).join("/")}.md">${icon("pen")}Edit this page</a></p>` : "");
  }
  function viewProjects() {
    crumbs([{ t: "Projects" }]);
    const pc = count(projectsOf), open = openItems(E);
    main.innerHTML = pageHead("Projects") + `<div class="gallery">` + D.projects.map((p) =>
      `<a class="tile" href="#/project/${enc(p.name)}"><b>${esc(p.name)}</b><span>${pc[p.name] || 0} entries · ${open.filter((x) => projectsOf(x.e).includes(p.name)).length} open</span></a>`).join("") + `</div>`;
  }
  function openList(open) {
    return open.length ? `<ul class="links">${open.map((x) => `<li><span class="status open"></span>${esc(x.text)} ${prioTag(x)}<span class="d">${entryLink(x.e.id, x.anchor, fmtDate(x.e.date))}</span></li>`).join("")}</ul>`
                       : `<p class="desc">Nothing open.</p>`;
  }
  function viewProject(n) {
    const p = D.projects.find((x) => x.name === n) || { name: n, subprojects: [] };
    const list = E.filter((e) => projectsOf(e).includes(n)).reverse();
    const open = openItems(list);
    crumbs([{ t: "Projects", href: "#/projects" }, { t: n }]);
    main.innerHTML = `<header class="entry-head"><h1 class="title">${esc(n)}</h1><div class="meta"><span>${nEntries(list.length)}</span>` +
      `<a class="link" href="#/?project=${enc(n)}">filter the list</a>${D.site ? `<a class="link" href="${newEntry({ project: n })}">New entry here</a>` : ""}${p.subprojects.map((s) => tag(s, hue(s), `#/?project=${enc(n)}&sub=${enc(n + "/" + s)}`)).join("")}` +
      `<span class="status open">${open.length} open</span></div></header>` +
      (p.wiki ? wikiHtml(p.wiki) : `<p class="desc">No project page in the wiki yet.</p>`) +
      toggle("Open items", openList(open), open.length) + toggle("Latest entries", cards(list, [], 12), list.length);
  }
  function viewApparatusList() {
    crumbs([{ t: "Apparatus" }]);
    const ac = count((e) => e.apparatus || []);
    main.innerHTML = pageHead("Apparatus", "What each part of the setup has been through: calibrations, maintenance, incidents, settings.") +
      (D.apparatus.length ? `<div class="gallery">` + D.apparatus.map((a) => `<a class="tile" href="#/apparatus/${enc(a.id)}"><b>${esc(a.name)}</b><span>${nEntries(ac[a.id] || 0)}</span></a>`).join("") + `</div>` : `<p class="empty">No apparatus registered.</p>`);
  }
  function viewApparatus(id) {
    const a = D.apparatus.find((x) => x.id === id) || { id, name: id };
    const list = E.filter((e) => (e.apparatus || []).includes(id)).reverse();
    const current = list.filter((e) => ["calibration", "maintenance"].includes(e.kind) && (!e.valid_until || e.valid_until >= D.today));
    const incidents = list.filter((e) => e.kind === "incident"), snaps = list.filter((e) => e.epics.length);
    crumbs([{ t: "Apparatus", href: "#/apparatus" }, { t: a.name }]);
    const li = (xs) => (xs.length ? linkList(xs.map((e) => e.id)) : `<p class="desc">None.</p>`);
    main.innerHTML = `<header class="entry-head"><h1 class="title">${esc(a.name)}</h1><div class="meta"><span>${nEntries(list.length)}</span><a class="link" href="#/?app=${enc(id)}">filter the list</a>${D.site ? `<a class="link" href="${newEntry({ apparatus: `${a.name} (${id})` })}">New entry here</a>` : ""}</div></header>` +
      (a.wiki ? wikiHtml(a.wiki) : "") +
      toggle("Current calibrations and maintenance", li(current), current.length) + toggle("Incidents", li(incidents), incidents.length) +
      toggle("EPICS snapshots", li(snaps), snaps.length) + toggle("All entries", cards(list, [], 12), list.length, false);
  }
  function viewPeople() {
    crumbs([{ t: "People" }]);
    const wc = count((e) => e.authors);
    main.innerHTML = pageHead("People") + `<div class="gallery">` + Object.keys(wc).sort((a, b) => name(a).localeCompare(name(b))).map((w) =>
      `<a class="tile person-tile" href="#/person/${enc(w)}">${avatar(w)}<span class="pt"><b>${esc(name(w))}</b><span>${nEntries(wc[w])}</span></span></a>`).join("") + `</div>`;
  }
  function viewPerson(h) {
    const list = E.filter((e) => e.authors.includes(h)).reverse();
    crumbs([{ t: "People", href: "#/people" }, { t: name(h) }]);
    main.innerHTML = `<header class="entry-head person-head">${avatar(h, true)}<div><h1 class="title">${esc(name(h))}</h1>` +
      `<div class="meta"><span>${nEntries(list.length)}</span><a class="link" href="#/?who=${enc(h)}">filter the list</a></div></div></header>` + cards(list, [], limit);
  }
  function viewWikiList() {
    crumbs([{ t: "Wiki" }]);
    const groups = {};
    for (const w of D.wiki) { const g = w.page.includes("/") ? w.page.split("/")[0] : "pages"; (groups[g] = groups[g] || []).push(w); }
    main.innerHTML = pageHead("Wiki", "How things are now: projects, apparatus, procedures. Living pages, changed through pull requests.") +
      (D.wiki.length ? Object.keys(groups).sort().map((g) => toggle(g[0].toUpperCase() + g.slice(1), `<ul class="links">${groups[g].map((w) =>
        `<li><a href="#/wiki/${w.page.split("/").map(enc).join("/")}">${esc(w.title)}</a></li>`).join("")}</ul>`, groups[g].length)).join("") : `<p class="empty">The wiki is empty.</p>`);
  }
  function viewWiki(page) {
    const w = wikiBy[page];
    crumbs([{ t: "Wiki", href: "#/wiki" }, { t: w ? w.title : page }]);
    if (!w) { main.innerHTML = `<p class="empty">No wiki page ${esc(page)}.</p>`; return; }
    main.innerHTML = pageHead(w.title) + wikiHtml(page) +
      (w.backlinks.length ? `<aside class="related"><div class="related-h">Around this page</div>${toggle("Linked from", linkList(w.backlinks), w.backlinks.length)}</aside>` : "");
    window.scrollTo(0, 0);
  }
  function viewRefs() {
    listBase = "#/refs";
    crumbs([{ t: "References" }]);
    const Q = parseQuery(F.q);
    const refs = D.references.filter((r) => Q.terms.every((t) => norm(r.cite + " " + r.key + " " + (r.html || "")).includes(t)));
    main.innerHTML = pageHead("References", `The lab's reference list. Cite one in an entry as <code class="c">[@Key]</code>.`) +
      `<div class="toolbar"><label class="search">${icon("search")}<span class="sr">Search</span><input id="q" type="search" placeholder="Search references…" value="${esc(F.q)}" autocomplete="off"><kbd>/</kbd></label></div>` +
      refs.map((r) => `<div class="ref"><div>${r.doi ? `<a class="short" href="${esc(r.doi)}">${esc(r.cite)}</a>` : `<span class="short">${esc(r.cite)}</span>`} ${tag("@" + r.key, "gray")}</div>` +
        `<div class="full">${r.html || ""}</div>` + (r.citedBy.length ? `<div class="cited">Cited in ${r.citedBy.map((b) => entryLink(b)).join(" · ")}</div>` : "") + `</div>`).join("");
  }

  // ------------------------------------------------------------------ export dialog --------
  function exportDialog() {
    const { list } = filtered();
    const args = [];
    for (const p of F.project) args.push(`--project "${p}"`);
    for (const w of F.who) args.push(`--person ${w}`);
    for (const a of F.app) args.push(`--apparatus ${a}`);
    for (const k of F.kind) args.push(`--kind ${k}`);
    for (const t of F.tag) args.push(`--tag "${t}"`);
    if (F.from) args.push(`--from ${F.from}`);
    if (F.to) args.push(`--to ${F.to}`);
    if (F.q) args.push(`--query "${F.q.replace(/"/g, "'")}"`);
    const S = D.site;
    $("#dialog-body").innerHTML = `<h2>Export ${list.length} entries as a PDF</h2>` +
      `<p>An export for someone outside the lab is rendered with the lab notebook template and needs the PI's approval. Every export is logged.</p>` +
      (S ? `<p><a class="btn primary" href="${S.export}">Request the export on GitHub</a></p><p>with these settings:</p>` : `<p>From a clone of the log book:</p>`) +
      `<pre>logbook export ${esc(args.join(" "))}</pre>`;
    $("#dialog").showModal();
  }

  // ------------------------------------------------------------------ sidebar --------------
  function renderSide() {
    const curPath = (location.hash || "#/").split("?")[0];
    const nav = (href, emo, label, n, cls = "") => `<a class="nav ${cls}" href="${href}" ${curPath === href ? 'aria-current="page"' : ""}>` +
      `<span class="emo" aria-hidden="true">${emo}</span><span class="lbl">${esc(label)}</span>${n != null ? `<span class="n">${n}</span>` : ""}</a>`;
    const S = D.site, pc = count(projectsOf);
    const logo = D.logo ? `<img class="logo-img" src="${D.logo}" alt="">` : `<span class="logo" aria-hidden="true">${esc((D.title.match(/\p{L}/u) || ["L"])[0].toUpperCase())}</span>`;
    let h = `<div class="ws${D.logo && D.logo_wide ? " wide" : ""}">${logo}` +
      `<div class="ws-t"><b>${esc(D.title)}</b><span>${nEntries(E.length)}</span></div>` +
      `<button class="iconbtn glyph" data-act="collapse" title="Hide the sidebar" aria-label="Hide the sidebar">«</button></div>` +
      `<button class="nav" data-act="search"><span class="emo" aria-hidden="true">🔍</span><span class="lbl">Search</span><kbd>/</kbd></button>` +
      (S ? `<a class="nav" href="${S.new_entry}"><span class="emo" aria-hidden="true">➕</span><span class="lbl">New entry</span></a>` : "") +
      `<div style="height:8px"></div>` +
      nav("#/", "🗂️", "Entries", E.length) + nav("#/open", "📌", "Open items", openItems(E).length) +
      nav("#/people", "👥", "People") + nav("#/refs", "📚", "References", D.references.length || null) +
      ((D.orders || []).length ? nav("#/purchases", "🧾", "Purchases", D.orders.filter((x) => x.status === "open").length || null) : "");
    h += `<h4>Projects</h4>`;
    for (const p of D.projects) if (pc[p.name] || p.wiki) h += nav(`#/project/${enc(p.name)}`, "📁", p.name, pc[p.name] || 0);
    if (D.apparatus.length) { h += `<h4>Apparatus</h4>`; for (const a of D.apparatus) h += nav(`#/apparatus/${enc(a.id)}`, "🔧", a.name); }
    if (D.wiki.length) {
      h += `<h4>Wiki</h4>`;
      for (const w of D.wiki.filter((w) => !/^(projects|apparatus)\//.test(w.page))) h += nav(`#/wiki/${w.page.split("/").map(enc).join("/")}`, "📄", w.title);
      h += nav("#/wiki", "📖", "All pages", D.wiki.length, "muted");
    }
    h += `<div class="grow"></div><button class="nav muted" data-act="theme"><span class="emo" aria-hidden="true">${document.documentElement.dataset.theme === "dark" ? "🌙" : document.documentElement.dataset.theme === "light" ? "☀️" : "🌗"}</span><span class="lbl">${themeLabel()}</span></button>` +
      `<div class="foot">Built ${esc(D.generated.replace("T", " "))} · logbook ${esc(D.version)}</div>`;
    side.innerHTML = h;
  }
  const themeLabel = () => ({ dark: "Dark", light: "Light" }[document.documentElement.dataset.theme] || "Theme as the system");
  function theme(t) {
    if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
    store.set("lb-theme", t || null);
  }
  { const t = store.get("lb-theme"); if (t) document.documentElement.dataset.theme = t; }
  // the sidebar: folded in and out with the button at its top (or the ☰ in the top bar); remembered
  const narrow = () => matchMedia("(max-width: 900px)").matches;
  function setCollapsed(c) { app.classList.toggle("collapsed", c); store.set("lb-side", c ? "hidden" : null); }
  if (store.get("lb-side") === "hidden") app.classList.add("collapsed");

  // ------------------------------------------------------------------ routing --------------
  function route() {
    const raw = location.hash.slice(1) || "/";
    const at = raw.indexOf("?");
    const path = at < 0 ? raw : raw.slice(0, at), qs = at < 0 ? "" : raw.slice(at + 1);
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    const map = { e: "entry", open: "open", projects: "projects", project: "project", apparatus: parts[1] ? "app" : "apps",
                  people: "people", person: "person", wiki: parts[1] ? "wikipage" : "wiki", refs: "refs", purchases: "purchases" };
    return { name: parts.length ? map[parts[0]] || "entries" : "entries", parts, qs };
  }
  function render() {
    const r = route();
    closePop();
    if (["entries", "open", "refs"].includes(r.name)) fromHash(r.qs);
    main.className = "";
    $("#top-actions").innerHTML = "";
    side.classList.remove("open"); $("#scrim").classList.remove("open");
    ({ entries: viewEntries, open: viewOpen, entry: () => viewEntry(r.parts[1], r.parts[2]), projects: viewProjects,
       project: () => viewProject(r.parts.slice(1).join("/")), apps: viewApparatusList, app: () => viewApparatus(r.parts[1]),
       people: viewPeople, person: () => viewPerson(r.parts[1]), wiki: viewWikiList, wikipage: () => viewWiki(r.parts.slice(1).join("/")),
       refs: viewRefs, purchases: viewPurchases })[r.name]();
    renderSide();
    figures(main);
    const here = $("#crumbs .c");
    document.title = (here ? here.textContent + " · " : "") + D.title;
  }

  // ------------------------------------------------------------------ wiring ---------------
  let timer;
  main.addEventListener("input", (ev) => {
    if (ev.target.id === "pu-q") { PU.q = ev.target.value; purchasesTable(); return; }
    if (ev.target.id !== "q") return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      F.q = ev.target.value.trim(); limit = 100;
      const pos = ev.target.selectionStart;
      go();
      const q = $("#q"); if (q) { q.focus(); try { q.setSelectionRange(pos, pos); } catch (err) { /* not supported */ } }
    }, 180);
  });
  function focusSearch() {
    const r = route().name;
    if (!["entries", "open", "refs"].includes(r)) { location.hash = "#/"; setTimeout(() => $("#q") && $("#q").focus(), 30); }
    else if ($("#q")) $("#q").focus();
  }
  document.addEventListener("keydown", (ev) => {
    const t = document.activeElement.tagName;
    if (ev.key === "/" && t !== "INPUT" && t !== "SELECT" && t !== "TEXTAREA") { ev.preventDefault(); focusSearch(); }
    if (ev.key === "Escape") {
      if (popKey) closePop();
      else if (document.activeElement.id === "q" && F.q) { F.q = ""; go(); }
    }
  });
  main.addEventListener("click", (ev) => {
    const clr = ev.target.closest("[data-clear]");
    if (clr) { ev.stopPropagation(); ev.preventDefault(); clearFilter(clr.dataset.clear); closePop(); go(); return; }
    const pill = ev.target.closest("[data-pill]");
    if (pill) { openPop(pill.dataset.pill, pill); return; }
    const t = ev.target.closest("[data-act],[data-more]");
    if (!t) return;
    if (t.dataset.more) { limit = +t.dataset.more; render(); }
    else if (t.dataset.act === "export") exportDialog();
    else if (t.dataset.act === "pu-csv") purchasesCsv();
    else if (t.dataset.act === "clear") { fromHash(""); go(); }
  });
  main.addEventListener("change", (ev) => {
    if (ev.target.id === "sort") { F.sort = ev.target.value; go(); }
    if (ev.target.id === "op-prio") { OP.prio = ev.target.value; go(); }
    if (ev.target.id === "op-sort") { OP.sort = ev.target.value; go(); }
    if (ev.target.id === "pu-open") { PU.open = ev.target.checked; purchasesTable(); }
    if (ev.target.dataset.act === "full") { F.full = ev.target.checked; limit = 100; go(); }
  });
  $("#top-actions").addEventListener("click", (ev) => {
    const t = ev.target.closest("[data-act='cite-id']");
    if (!t) return;
    const text = "[[" + t.dataset.id + "]]", label = t.querySelector("span");
    try { navigator.clipboard.writeText(text); label.textContent = "Copied"; } catch (err) { label.textContent = text; }
  });
  side.addEventListener("click", (ev) => {
    const t = ev.target.closest("[data-act]");
    if (!t) return;
    if (t.dataset.act === "search") focusSearch();
    if (t.dataset.act === "collapse") { if (narrow()) { side.classList.remove("open"); $("#scrim").classList.remove("open"); } else setCollapsed(true); }
    if (t.dataset.act === "theme") { const c = document.documentElement.dataset.theme; theme(c === undefined ? "dark" : c === "dark" ? "light" : undefined); renderSide(); }
  });
  $("#menu").textContent = "☰";   // a text glyph: drawn by every browser
  $("#menu").setAttribute("title", "Show or hide the sidebar");
  $("#menu").addEventListener("click", () => {
    if (narrow()) { side.classList.add("open"); $("#scrim").classList.add("open"); }
    else setCollapsed(!app.classList.contains("collapsed"));
  });
  $("#scrim").addEventListener("click", () => { side.classList.remove("open"); $("#scrim").classList.remove("open"); });
  window.addEventListener("hashchange", render);
  render();
  if (CLAUDE_APP) { usePng = true; figures(main); }
  svgTest.then((ok) => { usePng = usePng || !ok; figures(main); });
})();
