-- After citeproc: turns the log book's Markdown into Typst (the PDF) or HTML (the view).
-- Python prepares the input (lablogbook/render.py): each entry is a Div .lb-entry, each wiki page
-- a Div .lb-wiki, each figure a Div .lb-fig with a key; [[links]] are links to logbook:...
-- Data from Python, in the JSON file named by $LB_DATA (not pandoc metadata, which would be read
-- as Markdown): doi (citation key -> DOI url), fig (key -> figure fields), wiki_in (pages present).

local typst = FORMAT:match("typst") ~= nil
local meta_doi, meta_fig, wiki_in = {}, {}, {}

local CALLOUT = {decision = true, finding = true, issue = true, todo = true, context = true, incident = true}
local TYPST_FN = {decision = "decision", finding = "finding", issue = "issue", todo = "todo",
                  context = "context-box", incident = "incident"}
local HTML_LABEL = {decision = "Decision", finding = "Finding", issue = "Issue → cause → fix",
                    todo = "Open item", context = "Background", incident = "Incident"}

local function str(v) return v and pandoc.utils.stringify(v) or nil end

-- An entry's or wiki page's own headings, renumbered to consecutive levels from `top` down
-- (`##` then `####` become top, top + 1): PDF/UA-1 does not allow a skipped level.
local function shift_headers(blocks, top)
  local used = {}
  pandoc.Blocks(blocks):walk({Header = function(h) used[h.level] = true end})
  local map, next_level = {}, top
  for level = 1, 6 do
    if used[level] then map[level] = math.min(next_level, 6); next_level = next_level + 1 end
  end
  return pandoc.Blocks(blocks):walk({Header = function(h) h.level = map[h.level]; return h end})
end

local function esc(s)
  return (s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;"))
end

local function tstr(s)   -- a Typst string literal
  return '"' .. s:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function figure(key)
  local f = meta_fig[key]
  if not f then
    return pandoc.Para({pandoc.Str("[missing figure " .. key .. "]")})
  end
  if typst then
    local cap = f.caption_typst or tstr(f.caption)
    return pandoc.RawBlock("typst", string.format(
      "#figure(strip-image(%s, strip: %sin, alt: %s, width: %s), caption: [#%s])%s",
      tstr(f.typst_path), f.strip_in, tstr(f.alt), f.width or "62%", cap,
      f.label and (" <" .. f.label .. ">") or ""))
  end
  -- the figure (its SVG), with the labfig strip cropped; a click opens it on its own
  return pandoc.RawBlock("html", string.format(
    '<figure class="lb-fig"%s><a class="lb-crop" href="@@FIGVEC:%s@@" target="_blank" rel="noopener" ' ..
    'title="Open the vector original" style="aspect-ratio: %s / %s">' ..
    '<img src="@@FIG:%s@@" data-png="@@FIGPNG:%s@@" alt="%s" loading="lazy"></a>' ..
    '<figcaption>%s</figcaption></figure>',
    f.label and (' id="' .. f.label .. '"') or "", esc(key), f.w, f.h_visible, esc(key), esc(key), esc(f.alt), esc(f.caption)))
end

local PRIORITY_LABEL = {low = "low", high = "high", asap = "ASAP"}   -- medium, the default, is not shown
local inner   -- callouts and figures inside an entry (defined below)

local function Div(el)
  if el.classes:includes("lb-entry") or el.classes:includes("lb-wiki") then
    local id = el.attributes["data-id"]
    local kind = el.classes:includes("lb-entry") and "ENTRY" or "WIKI"
    local top = kind == "ENTRY" and 3 or 2   -- under a day (1) and its note (2); under "Projects" (1)
    -- pandoc does not run this filter again on what a handler returns, so convert the
    -- blocks inside the entry here (bottom-up, so nested blocks are handled first)
    local content = shift_headers(el.content, top):walk({Div = inner})
    local marker = typst and pandoc.RawBlock("typst", "// @@" .. kind .. " " .. id)
                          or pandoc.RawBlock("html", "<!--@@" .. kind .. " " .. id .. "-->")
    local out = pandoc.Blocks({marker})
    out:extend(content)
    return out
  end
  return inner(el)
end

inner = function(el)
  if el.classes:includes("lb-fig") then
    return figure(el.attributes["key"])
  end
  for name, _ in pairs(CALLOUT) do
    if el.classes:includes(name) then
      if typst then
        local out = pandoc.Blocks({pandoc.RawBlock("typst", "#" .. TYPST_FN[name] .. "[")})
        -- an open item's priority as written (the view shows the current one)
        local pr = PRIORITY_LABEL[(el.attributes["priority"] or ""):lower()]
        if pr then out:insert(pandoc.Plain({pandoc.Emph({pandoc.Str("Priority: " .. pr)})})) end
        out:extend(el.content)
        local close = "]"
        if el.identifier ~= "" then close = close .. " <e-" .. el.identifier .. ">" end
        out:insert(pandoc.RawBlock("typst", close))
        return out
      end
      local id = el.identifier ~= "" and (' id="e-' .. el.identifier .. '"') or ""
      local out = pandoc.Blocks({pandoc.RawBlock("html", '<div class="callout ' .. name .. '"' .. id ..
        '><div class="callout-label">' .. HTML_LABEL[name] .. '</div>')})
      out:extend(el.content)
      out:insert(pandoc.RawBlock("html", "</div>"))
      return out
    end
  end
end

local function Link(el)
  local t = el.target
  if t:sub(1, 8) == "logbook:" then
    local rest = t:sub(9)
    local what, target = rest:match("^(%a+)/(.+)$")
    if what == "entry" then
      local id, anchor = target:match("^([^#]+)#?(.*)$")
      local lab = "e-" .. id .. (anchor ~= "" and ("--" .. anchor) or "")
      if typst then
        local out = pandoc.Inlines({pandoc.RawInline("typst", "#link(<" .. lab .. ">)[")})
        out:extend(el.content)
        out:insert(pandoc.RawInline("typst", "]"))
        return out
      end
      el.target = "#/e/" .. id .. (anchor ~= "" and ("/" .. anchor) or "")
      el.classes:insert("lb-link")
      return el
    elseif what == "wiki" then
      if typst then
        if wiki_in[target] then
          local out = pandoc.Inlines({pandoc.RawInline("typst", "#link(<w-" .. target:gsub("/", "-") .. ">)[")})
          out:extend(el.content)
          out:insert(pandoc.RawInline("typst", "]"))
          return out
        end
        return pandoc.Emph(el.content)
      end
      el.target = "#/wiki/" .. target
      el.classes:insert("lb-link")
      return el
    end
  end
end

local function Cite(el)
  local key = el.citations[1] and el.citations[1].id
  local url = key and meta_doi[key]
  if not url then return nil end
  return pandoc.Link(el.content, url, "", pandoc.Attr("", {"lb-cite"}))
end

do
  local path = os.getenv("LB_DATA")
  if path then
    local fh = io.open(path, "r")
    if fh then
      local data = pandoc.json.decode(fh:read("a"), false)
      fh:close()
      meta_doi = data.doi or {}
      meta_fig = data.fig or {}
      for _, w in ipairs(data.wiki_in or {}) do wiki_in[w] = true end
    end
  end
end

-- PDF/UA-1 needs alt text on every equation: pandoc's Typst math, wrapped in an equation whose
-- alt text is the TeX source.
local function Math(el)
  if not typst then return nil end
  local out = pandoc.write(pandoc.Pandoc({pandoc.Plain({el})}), "typst"):gsub("%s+$", "")
  return pandoc.RawInline("typst", "#{ let e = " .. out .. "; math.equation(block: " ..
    tostring(el.mathtype == "DisplayMath") .. ", alt: " .. tstr(el.text) .. ", e.body) }")
end

-- Task lists (`- [ ]`, `- [x]`): pandoc writes the boxes as the characters U+2610 and U+2612,
-- which none of the template's embedded fonts has (PDF/UA refuses the fallback font), so the
-- boxes are drawn.
local BOX = "box(width: 0.75em, height: 0.75em, baseline: 0.1em, stroke: 0.6pt + luma(90)"
local function Str(el)
  if not typst then return nil end
  if el.text == "\u{2610}" then return pandoc.RawInline("typst", "#" .. BOX .. ")") end
  if el.text == "\u{2612}" then
    return pandoc.RawInline("typst", "#" .. BOX .. ", inset: 0.12em, box(width: 100%, height: 100%, fill: luma(90)))")
  end
end

return {
  {Math = Math, Str = Str},
  {Div = Div, Link = Link, Cite = Cite, traverse = "topdown"},
}
