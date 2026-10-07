// Spoken mathematics: alt text for equations, the way a reader would say them.
//
// PDF/UA-1 refuses an equation without alt text, and a lecture has hundreds of them. Two
// ways to supply it, both from this file:
//
//   1. `eq(alt: auto)[$...$]` (slide and notes themes): the alt text is `speak(body)`, the
//      spoken form of the parsed math ("x sub 0 plus one half a t squared"). Give `alt: "..."`
//      where the automatic form is wrong or too long.
//   2. Plain `$...$` in lecture notes: `talks alts <file.typ>` collects every equation of a
//      file into `<stem>.alts.yaml` (source -> spoken draft from `speak`, status `draft`
//      until reviewed), and the notes theme applies the reviewed text with `apply-alts`,
//      one `show math.equation.where(body: ...)` rule per equation (300 rules cost < 0.3 s).
//
// `speak` is deliberately simple: it reads structure (fractions, powers, roots, vectors,
// sums, integrals) and a word list for symbols. Anything it does not know is read as its
// text. The result is a draft for a human to check, and the fallback when nobody did.

#let sequence = ([a] + [b]).func()
#let space = [ ].func()

#let symbol-words = (
  // Greek
  "α": "alpha", "β": "beta", "γ": "gamma", "Γ": "capital gamma", "δ": "delta", "Δ": "capital delta",
  "ε": "epsilon", "ϵ": "epsilon", "ζ": "zeta", "η": "eta", "θ": "theta", "Θ": "capital theta", "ϑ": "theta",
  "κ": "kappa", "λ": "lambda", "Λ": "capital lambda", "μ": "mu", "ν": "nu", "ξ": "xi", "Ξ": "capital xi",
  "π": "pi", "Π": "capital pi", "ρ": "rho", "σ": "sigma", "Σ": "capital sigma", "τ": "tau", "υ": "upsilon",
  "φ": "phi", "ϕ": "phi", "Φ": "capital phi", "χ": "chi", "ψ": "psi", "Ψ": "capital psi", "ω": "omega", "Ω": "capital omega",
  // relations and operators
  "=": "equals", "≠": "is not equal to", "≈": "is approximately", "≃": "is approximately", "≡": "is identical to",
  "∝": "is proportional to", "<": "is less than", ">": "is greater than", "≤": "is less than or equal to",
  "≥": "is greater than or equal to", "≪": "is much less than", "≫": "is much greater than",
  "∼": "goes like", "~": "goes like", "⟂": "is perpendicular to", "⊥": "is perpendicular to", "∥": "is parallel to",
  "+": "plus", "−": "minus", "-": "minus", "±": "plus or minus", "∓": "minus or plus", "×": "times", "·": "times",
  "⋅": "times", "∗": "star", "/": "over", "÷": "divided by", "∘": "composed with",
  "→": "which gives", "↦": "maps to", "⇒": "implies", "⇔": "if and only if", "←": "comes from",
  "∞": "infinity", "∂": "partial", "∇": "del", "∑": "the sum of", "∏": "the product of", "∫": "the integral of",
  "∮": "the closed integral of", "√": "the square root of", "ℏ": "h bar", "ħ": "h bar", "ℓ": "ell",
  "°": "degrees", "′": "prime", "″": "double prime", "…": "and so on", "⋯": "and so on", "!": "factorial",
  "∈": "in", "∉": "not in", "∀": "for all", "∃": "there exists", "∅": "the empty set", "∪": "union", "∩": "intersection",
  "⟨": "the expectation value of", "⟩": "", "|": "", "‖": "", "∣": "given", "†": "dagger",
  "(": "open parenthesis", ")": "close parenthesis", "[": "open bracket", "]": "close bracket", "{": "open brace", "}": "close brace",
  ",": ",", ";": ";", ":": ",", "'": "prime", "%": "percent", "&": "", "\\": "",
  // named functions and constants that appear as identifiers
  "sin": "sine", "cos": "cosine", "tan": "tangent", "arcsin": "arc sine", "arccos": "arc cosine", "arctan": "arc tangent",
  "sinh": "hyperbolic sine", "cosh": "hyperbolic cosine", "tanh": "hyperbolic tangent",
  "cot": "cotangent", "sec": "secant", "csc": "cosecant",
  "ln": "the natural log of", "log": "log", "exp": "exponential of", "lim": "the limit", "max": "the maximum of", "min": "the minimum of",
  "det": "the determinant of", "tr": "the trace of", "dim": "the dimension of", "mod": "modulo",
  "d": "d", "e": "e", "i": "i",
)

#let small-numbers = ("1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten")

#let _ordinal(n) = (
  "2": "half", "3": "third", "4": "quarter", "5": "fifth", "6": "sixth", "7": "seventh", "8": "eighth", "9": "ninth", "10": "tenth",
).at(n, default: none)

#let _join(parts) = parts.filter(s => s != "").join(" ")

// Units written as quoted text in math (`"m/s"^2`, `"kg"`) are read as words.
#let unit-words = (
  "m": "meters", "cm": "centimeters", "mm": "millimeters", "km": "kilometers", "s": "seconds", "ms": "milliseconds",
  "kg": "kilograms", "g": "grams", "N": "newtons", "J": "joules", "W": "watts", "Hz": "hertz", "rad": "radians",
  "h": "hours", "min": "minutes", "ft": "feet", "mph": "miles per hour", "lb": "pounds", "lbs": "pounds",
  "kN": "kilonewtons", "kJ": "kilojoules", "MJ": "megajoules", "kW": "kilowatts", "MW": "megawatts", "GW": "gigawatts",
  "hp": "horsepower", "slug": "slugs", "eV": "electron volts",
  "m/s": "meters per second", "km/h": "kilometers per hour", "ft/s": "feet per second", "N/m": "newtons per meter",
  "kN/m": "kilonewtons per meter", "rad/s": "radians per second", "kg m/s": "kilogram meters per second",
  "m^2/s^2": "meters squared per second squared", "ft/s^2": "feet per second squared",
)

// Quoted labels on W and friends: `W^"grav"` reads "W done by gravity"
// Quoted subscripts: `r_"cm"` is the centre of mass, not centimeters
#let sub-words = ("cm": "center of mass", "CM": "center of mass", "EXT": "external", "ext": "external", "tot": "total", "max": "max", "min": "min", "grav": "gravity", "fric": "friction")

#let label-words = (
  "grav": "done by gravity", "gravity": "done by gravity", "fric": "done by friction", "friction": "done by friction",
  "spring": "done by the spring", "man": "done by the man", "total": "done by the total force", "cons": "done by the conservative forces",
  "nc": "done by the non-conservative forces", "N": "done by the normal force", "K.E.": "kinetic energy", "P.E.": "potential energy",
)

// "1 metres" -> "1 metre": the first word of a unit phrase in the singular after the number 1
#let _singular(w) = {
  let parts = w.split(" ")
  let f = parts.first()
  f = if f == "feet" { "foot" } else if f == "hertz" { f } else if f.ends-with("s") { f.slice(0, f.len() - 1) } else { f }
  (f, ..parts.slice(1)).join(" ")
}

#let _plain(s) = {
  // a run of characters: split off trailing/leading punctuation we have words for
  if s.len() >= 2 and s in unit-words { return unit-words.at(s) }
  if s in symbol-words { return symbol-words.at(s) }
  if s.len() > 1 and s.clusters().all(c => c in symbol-words) and s.clusters().all(c => not c.match(regex("[A-Za-z0-9]")) != none) {
    return _join(s.clusters().map(c => symbol-words.at(c)))
  }
  s
}

/// Spoken form of math content, as a string.
#let speak(c) = {
  if type(c) == str { return _plain(c) }
  if c == none or c == [] { return "" }
  let f = c.func()
  if f == text {
    if c.text in unit-words { unit-words.at(c.text) } else if c.text in ("K.E.", "P.E.") { label-words.at(c.text) } else { _plain(c.text) }
  } else if f == sequence {
    let kids = c.children.filter(k => k.func() != space and k.func() != h)
    // a number followed by a quoted unit ("9.8 m/s", `4 thin "s"`): the text is a unit (bare
    // letters are symbols: `2 g H`); "1 kg" is singular; `|...|` written as bare bars is a
    // magnitude; "theta -> 0" approaches; "kg · m" drops the times between units
    if kids.len() >= 2 {
      let words = ()
      let i = 0
      let merged = false
      let last-unit = false
      let txt(k) = if k.has("text") and type(k.text) == str { k.text } else { "" }
      let quoted(k) = k.func() == text or (k.func() == math.attach and k.base.func() == text)
      let unit-of(k) = if k.func() == text { k.text } else if k.func() == math.attach and k.base.func() == text { k.base.text } else { "" }
      while i < kids.len() {
        let k = kids.at(i)
        let is-num = txt(k).match(regex("^[0-9.]+$")) != none
        // `1\/2 g t^2`: a slash between two small numbers is a spoken fraction, "one half"
        if txt(k) in small-numbers and i + 2 < kids.len() and txt(kids.at(i + 1)) == "/" and _ordinal(txt(kids.at(i + 2))) != none {
          let n = txt(k)
          let o = _ordinal(txt(kids.at(i + 2)))
          words.push(small-numbers.at(n) + " " + (if n != "1" { if o == "half" { "halves" } else { o + "s" } } else { o }))
          i += 3
          merged = true
          continue
        }
        if is-num and i + 1 < kids.len() {
          let nx = kids.at(i + 1)
          let u = unit-of(nx)
          if u in unit-words and quoted(nx) {
            let w = unit-words.at(u)
            if nx.func() == math.attach and nx.has("t") {
              let t = speak(nx.t)
              w += if t == "2" { " squared" } else if t == "3" { " cubed" } else { " to the " + t }
            }
            if k.text == "1" { w = _singular(w) }
            words.push(k.text + " " + w)
            i += 2
            merged = true
            last-unit = true
            continue
          }
        }
        if txt(k) in ("·", "⋅") and last-unit and i + 1 < kids.len() and unit-of(kids.at(i + 1)) in unit-words and quoted(kids.at(i + 1)) {
          let nx = kids.at(i + 1)
          let w = unit-words.at(unit-of(nx))
          if nx.func() == math.attach and nx.has("t") {
            let t = speak(nx.t)
            w += if t == "2" { " squared" } else if t == "3" { " cubed" } else { " to the " + t }
          }
          words.push(_singular(w))
          i += 2
          merged = true
          continue
        }
        last-unit = false
        let is-vec(k) = k.func() == math.accent or (k.func() == math.attach and k.base.func() == math.accent)
        if txt(k) in ("⋅", "·", "×") and i > 0 and i + 1 < kids.len() {
          let nx = kids.at(i + 1)
          let unit-ijk(k) = k.func() == math.accent and k.base.has("text") and type(k.base.text) == str and k.base.text in ("i", "j", "k")
          // a bracket holding a vector, `(B arrow(i) + y arrow(j)) × (-m g arrow(j))`, counts as a vector
          let has-vec(x) = is-vec(x) or unit-ijk(x) or (x.func() == math.lr and has-vec(x.body)) or (x.func() == sequence and x.children.any(has-vec))
          let prev-vec = is-vec(kids.at(i - 1)) or has-vec(kids.at(i - 1)) or unit-ijk(kids.at(i - 1))
          let next-vec = is-vec(nx) or unit-ijk(nx) or (nx.func() == math.lr and has-vec(nx)) or (txt(nx) == "d" and i + 2 < kids.len() and is-vec(kids.at(i + 2))) or (txt(nx) == "m" and i + 2 < kids.len() and is-vec(kids.at(i + 2)))
          if prev-vec or next-vec {
            words.push(if txt(k) == "×" { "cross" } else { "dot" })
            i += 1
            merged = true
            continue
          }
        }
        if k.func() == math.lr and i > 0 and kids.at(i - 1).func() == math.attach {
          let ik = if k.body.func() == sequence { k.body.children.filter(x => x.func() != space) } else { (k.body,) }
          if ik.len() == 3 and txt(ik.first()) == "(" and txt(ik.last()) == ")" and txt(ik.at(1)).match(regex("^[0-9]$")) != none {
            // v_x(0), v_x(2), v^2(0): read literally, "v sub x of 0", "v of 0 squared" (J. Karthein's review,
            // 2026-10-05: the equation says only "of 0"; time or point is the reader's knowledge)
            let a = kids.at(i - 1)
            let core = if a.has("b") { speak(math.attach(a.base, b: a.b)) } else { speak(a.base) }
            let sup = if a.has("t") {
              let t = speak(a.t)
              if t == "2" { " squared" } else if t == "3" { " cubed" } else { " to the " + t }
            } else { "" }
            let _ = words.pop()
            words.push(core + " of " + txt(ik.at(1)) + sup)
            i += 1
            merged = true
            continue
          }
        }
        if txt(k) == "|" {
          // the closing bar may carry a subscript: `|arrow(F)|_"spring"`
          let is-bar(k) = txt(k) == "|" or (k.func() == math.attach and txt(k.base) == "|")
          let j = i + 1
          while j < kids.len() and not is-bar(kids.at(j)) { j += 1 }
          if j < kids.len() {
            // spoken as one expression, so `|arrow(A) × arrow(B)|` keeps its "cross"
            let inner = speak(kids.slice(i + 1, j).join())
            let close = kids.at(j)
            let sub = if close.func() == math.attach and close.has("b") { " sub " + speak(close.b) } else { "" }
            let sup = if close.func() == math.attach and close.has("t") {
              let t = speak(close.t)
              if t == "2" { " squared" } else if t == "3" { " cubed" } else { " to the " + t }
            } else { "" }
            words.push(if inner.starts-with("vector ") and not inner.slice(7).contains(" ") { "the magnitude of " + inner.slice(7) + sub + ", end magnitude," + sup }
              else if inner.starts-with("vector ") or inner.starts-with("unit vector ") { "the magnitude of " + inner + sub + ", end magnitude," + sup } else { "the absolute value of " + inner + sub + ", end absolute value," + sup })
            i = j + 1
            merged = true
            continue
          }
        }
        let single(k) = txt(k).match(regex("^[\\p{L}\\p{N}.°]+$")) != none or k.func() == math.accent or k.func() == math.attach
        let limit-like = kids.len() == 3 and i == 1 and single(kids.at(0)) and single(kids.at(2))
        let limit-neg = kids.len() == 4 and i == 1 and single(kids.at(0)) and txt(kids.at(2)) in ("−", "-") and single(kids.at(3))
        let limit-deg = kids.len() == 4 and i == 1 and single(kids.at(0)) and single(kids.at(2)) and txt(kids.at(3)) == "°"
        // "a → …" with a single symbol before the arrow and no "=" after it is a limit
        let limit-any = i == 1 and single(kids.at(0)) and kids.slice(2).all(x => txt(x) != "=")
        if txt(k) == "→" and i + 1 < kids.len() and (txt(kids.at(i + 1)) in ("0", "∞") or limit-like or limit-neg or limit-deg or limit-any) {
          words.push("approaches")
          i += 1
          merged = true
          continue
        }
        words.push(speak(k))
        i += 1
      }
      if merged { return _join(words) }
    }
    // "f(x)", "x(t)", "v(0)", "v_x(2)": a one- or two-letter name, possibly with a subscript,
    // followed by a bracketed single symbol
    let head = if kids.len() == 2 { kids.first() } else { none }
    let head-text = if head == none { "" } else if head.has("text") and type(head.text) == str { head.text }
      else if head.func() == math.attach and head.has("b") and not head.has("t") and head.base.has("text") and type(head.base.text) == str { head.base.text } else { "" }
    let name = if head-text.len() <= 2 and head-text.match(regex("^[A-Za-z]+$")) != none { speak(head) } else { "" }
    if name != "" and kids.last().func() == math.lr {
      let inner = kids.last().body
      let ik = if inner.func() == sequence { inner.children } else { (inner,) }
      if ik.len() == 3 and ik.first().has("text") and ik.first().text == "(" and ik.last().has("text") and ik.last().text == ")" {
        let arg = speak(ik.at(1))
        if arg.len() <= 12 { return name + " of " + arg }
      }
    }
    _join(c.children.map(speak))
  } else if f == space or f == h or f == linebreak {
    ""
  } else if f == math.equation {
    speak(c.body)
  } else if f == math.attach {
    let base = speak(c.base)
    // big operators read their limits as a range: "the sum from i equals 1 to N of"
    let big = ("the sum of": "the sum", "the product of": "the product", "the integral of": "the integral",
               "the closed integral of": "the closed integral", "the limit": "the limit", "the maximum of": "the maximum", "the minimum of": "the minimum")
    if base in big {
      let out = big.at(base)
      // "the sum over i of" when the subscript names only the index (no start value, no upper limit)
      if c.has("b") {
        let b = speak(c.b)
        out += (if base == "the limit" { " as " } else if not c.has("t") and not b.contains("equals") { " over " } else { " from " }) + b
      }
      if c.has("t") { out += " to " + speak(c.t) }
      return out + " of"
    }
    let out = base
    if base == "" and c.has("t") and not c.has("b") { return "superscript " + speak(c.t) }
    // the work W^"grav"_(1 2): "W done by gravity from 1 to 2"
    if base == "W" {
      if c.has("t") {
        let t = c.t
        // unquoted single letters (`W^N`) are not `text` elements but carry `.text`
        let tt = if t.has("text") and type(t.text) == str { t.text } else { "" }
        out += if tt in label-words { " " + label-words.at(tt) }
          else if t.func() == text { " " + t.text }
          else if t.func() == math.accent or (t.func() == math.attach and t.base.func() == math.accent) { " done by " + speak(t) }
          else { " to the " + speak(t) }
      }
      if c.has("b") {
        let bk = if c.b.func() == sequence { c.b.children.filter(x => x.func() != space) } else { (c.b,) }
        let arrow-at = bk.position(x => x.has("text") and type(x.text) == str and x.text == "→")
        let btxt = if bk.len() == 1 and bk.first().has("text") and type(bk.first().text) == str { bk.first().text } else { "" }
        out += if arrow-at != none { " from " + _join(bk.slice(0, arrow-at).map(speak)) + " to " + _join(bk.slice(arrow-at + 1).map(speak)) }
          else if bk.len() == 2 { " from " + speak(bk.first()) + " to " + speak(bk.last()) }
          else if btxt.match(regex("^[0-9]{2}$")) != none { " from " + btxt.first() + " to " + btxt.last() }
          else { " sub " + speak(c.b) }
      }
      return out
    }
    if c.has("bl") { out = _join((speak(c.bl), out)) }
    if c.has("tl") { out = _join((speak(c.tl), out)) }
    if c.has("b") {
      // `H_min`: Typst makes `min` an operator; read its name, not "minutes"
      let btxt = if c.b.has("text") and type(c.b.text) == str { c.b.text }
        else if c.b.func() == math.op and c.b.text.has("text") { c.b.text.text } else { "" }
      let b = if btxt in sub-words { sub-words.at(btxt) } else if c.b.func() == text { btxt } else { speak(c.b) }
      if b == "the maximum of" { b = "max" } else if b == "the minimum of" { b = "min" }   // v_max: `max` is an operator
      if b.match(regex("^[0-9]{2,}$")) != none { b = b.clusters().join(" ") }   // F_12: "F sub 1 2"
      out += if b == "0" and base.len() <= 2 { " zero" } else { " sub " + b }
    }
    if c.has("t") and c.t.func() == text and c.t.text.match(regex("^[A-Za-z.]+$")) != none {
      out += " " + c.t.text + ","          // a quoted label: F^"man" reads "F man,"
    } else if c.has("t") {
      let t = speak(c.t)
      out += if t == "2" { " squared" } else if t == "3" { " cubed" } else if t == "prime" or t == "dagger" or t == "star" { " " + t }
        else if t == "minus 1" and base != "" { " inverse" }
        else if t.contains(" ") { " to the power of " + t + ", end exponent," } else { " to the " + t }
    }
    if c.has("br") { out = _join((out, speak(c.br))) }
    if c.has("tr") { out = _join((out, speak(c.tr))) }
    out
  } else if f == math.frac {
    let n = speak(c.num)
    let d = speak(c.denom)
    let o = if n in small-numbers { _ordinal(d) } else { none }
    if o != none { small-numbers.at(n) + " " + (if n != "1" { (if o == "half" { "halves" } else { o + "s" }) } else { o }) }
    else if n.len() <= 5 and (d.len() <= 5 or (d.len() <= 9 and not d.contains("over") and not d.contains("plus") and not d.contains("minus"))) { n + " over " + d }
    else if n.len() <= 3 { n + " over, " + d + ", end fraction," }
    else { "the fraction " + n + " over " + d + ", end fraction," }
  } else if f == math.binom {
    "the binomial coefficient " + speak(c.upper) + " choose " + _join(c.lower.map(speak))
  } else if f == math.root {
    let r = speak(c.radicand)
    let close = if r.contains(" ") { ", end root," } else { "" }
    if c.has("index") { "the " + speak(c.index) + "th root of " + r + close } else { "the square root of " + r + close }
  } else if f == math.vec {
    "the vector with components " + c.children.map(speak).join(", ")
  } else if f == math.mat {
    "the " + str(c.rows.len()) + " by " + str(c.rows.first().len()) + " matrix with rows " + c.rows.map(r => r.map(speak).join(", ")).join("; ")
  } else if f == math.cases {
    "the cases: " + c.children.map(speak).join("; ")
  } else if f == math.accent {
    // the accent is the combining character: U+20D7 arrow, U+0307 dot, U+0308 double dot, U+0302 hat, U+0303 tilde, U+0304 macron
    let a = str(c.accent)
    let word = (
      "\u{20d7}": "vector ", "\u{307}": "the time derivative of ", "\u{308}": "the second time derivative of ",
      "\u{302}": "unit vector ", "\u{303}": "tilde ", "\u{304}": "bar ", "\u{30a}": "ring ", "\u{306}": "breve ", "\u{30c}": "check ",
    ).at(a, default: "")
    let base-txt = if c.base.has("text") and type(c.base.text) == str { c.base.text } else { "" }
    if word == "vector " and base-txt in ("i", "j", "k") { "unit vector " + base-txt } else { word + speak(c.base) }
  } else if f == math.op {
    speak(c.text)
  } else if f == math.lr {
    // delimiters: |x| absolute value, ‖v‖ norm, otherwise read the brackets out
    let kids = if c.body.func() == sequence { c.body.children } else { (c.body,) }
    // delimiters are `symbol` elements with a `text` field (not `text` elements)
    let first = if kids.len() > 0 and kids.first().has("text") and type(kids.first().text) == str { kids.first().text } else { "" }
    let inner = _join(kids.slice(1, kids.len() - 1).map(speak))
    if first == "|" { (if inner.starts-with("vector ") { "the magnitude of " + inner.slice(7) } else { "the absolute value of " + inner }) + ", end magnitude," }
    else if first == "‖" { "the norm of " + inner + ", end norm," }
    else if first == "⟨" { "the expectation value of " + inner }
    else { speak(c.body) }
  } else if c.has("child") {           // styled content (e.g. the upright d of `dif`)
    speak(c.child)
  } else if f == math.limits or f == math.scripts {
    speak(c.body)
  } else if f == math.class {
    speak(c.body)
  } else if f == math.overbrace or f == math.underbrace or f == math.overline or f == math.underline {
    speak(c.body)
  } else if f == math.stretch {
    speak(c.body)
  } else if f == math.primes {
    if c.count == 1 { "prime" } else if c.count == 2 { "double prime" } else { str(c.count) + " primes" }
  } else if f == math.upright or f == math.italic or f == math.bold or f == math.sans or f == math.cal or f == math.bb or f == math.frak or f == math.mono or f == math.serif {
    speak(c.body)
  } else if f == strong or f == emph or f == box or f == block or f == smartquote {
    if c.has("body") { speak(c.body) } else { "" }
  } else if c.has("body") {
    speak(c.body)
  } else if c.has("text") {
    speak(c.text)
  } else if c.has("children") {
    _join(c.children.map(speak))
  } else {
    ""
  }
}

/// Tidy a spoken string: no dangling punctuation, single spaces, a lone "the integral of" is the sign.
#let tidy(t) = {
  let u = t.replace(regex("\\s+"), " ").trim()
  u = u.replace(regex(",\\s*,"), ",").replace(regex(",\\s*\\."), ".").replace(regex("\\s+([,.;])"), m => m.captures.at(0))
  u = u.replace(regex("[,;]\\s*$"), "").replace(regex("\\.\\s*$"), "")
  if u == "the integral of" { u = "the integral sign" }
  u
}

/// The math content of a source string, for `where(body: ...)` selectors.
#let math-body(src) = {
  // the parser drops the spaces around `$ F = m a $`; eval keeps them
  let e = eval(src.trim(), mode: "math")
  if e.func() == math.equation { e.body } else { e }
}

/// Apply reviewed alt texts from `<stem>.alts.yaml` (a list of `(src:, alt:)`) to every
/// equation of `body` whose math equals `src`. Entries without an alt are skipped.
#let apply-alts(alts, body) = alts.filter(p => p.at("alt", default: "") != "").fold(body, (acc, p) => {
  show math.equation.where(body: math-body(p.src)): set math.equation(alt: p.alt)
  acc
})

/// An equation whose alt text is mandatory: a string, or `auto` for `speak(body)`.
#let spoken-eq(alt: auto, block: true, numbering: none, body) = {
  assert(alt != none, message: "every equation needs alt text (a string, or auto for the spoken form)")
  let a = if alt == auto { tidy(speak(body)) } else { alt }
  math.equation(block: block, numbering: numbering, alt: a, body)
}
