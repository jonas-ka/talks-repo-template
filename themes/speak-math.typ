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
  "+": "plus", "−": "minus", "-": "minus", "±": "plus or minus", "∓": "minus or plus", "×": "times", "·": "times",
  "⋅": "times", "∗": "star", "/": "over", "÷": "divided by", "∘": "composed with",
  "→": "goes to", "↦": "maps to", "⇒": "implies", "⇔": "if and only if", "←": "comes from",
  "∞": "infinity", "∂": "partial", "∇": "del", "∑": "the sum of", "∏": "the product of", "∫": "the integral of",
  "∮": "the closed integral of", "√": "the square root of", "ℏ": "h bar", "ħ": "h bar", "ℓ": "ell",
  "°": "degrees", "′": "prime", "″": "double prime", "…": "and so on", "⋯": "and so on", "!": "factorial",
  "∈": "in", "∉": "not in", "∀": "for all", "∃": "there exists", "∅": "the empty set", "∪": "union", "∩": "intersection",
  "⟨": "the expectation value of", "⟩": "", "|": "", "‖": "", "∣": "given", "†": "dagger",
  "(": "open parenthesis", ")": "close parenthesis", "[": "open bracket", "]": "close bracket", "{": "open brace", "}": "close brace",
  ",": ",", ";": ";", ":": "such that", "'": "prime", "%": "percent", "&": "", "\\": "",
  // named functions and constants that appear as identifiers
  "sin": "sine", "cos": "cosine", "tan": "tangent", "arcsin": "arc sine", "arccos": "arc cosine", "arctan": "arc tangent",
  "sinh": "hyperbolic sine", "cosh": "hyperbolic cosine", "tanh": "hyperbolic tangent",
  "ln": "the natural log of", "log": "log", "exp": "exponential of", "lim": "the limit", "max": "the maximum of", "min": "the minimum of",
  "det": "the determinant of", "tr": "the trace of", "dim": "the dimension of", "mod": "modulo",
  "d": "d", "e": "e", "i": "i",
)

#let small-numbers = ("1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten")

#let _ordinal(n) = (
  "2": "half", "3": "third", "4": "quarter", "5": "fifth", "6": "sixth", "7": "seventh", "8": "eighth", "9": "ninth", "10": "tenth",
).at(n, default: none)

#let _join(parts) = parts.filter(s => s != "").join(" ")

#let _plain(s) = {
  // a run of characters: split off trailing/leading punctuation we have words for
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
    _plain(c.text)
  } else if f == sequence {
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
      if c.has("b") { out += (if base == "the limit" { " as " } else { " from " }) + speak(c.b) }
      if c.has("t") { out += " to " + speak(c.t) }
      return out + " of"
    }
    let out = base
    if base == "" and c.has("t") and not c.has("b") { return "superscript " + speak(c.t) }
    if c.has("bl") { out = _join((speak(c.bl), out)) }
    if c.has("tl") { out = _join((speak(c.tl), out)) }
    if c.has("b") {
      let b = speak(c.b)
      out += if b == "0" and base.len() <= 2 { " nought" } else { " sub " + b }
    }
    if c.has("t") {
      let t = speak(c.t)
      out += if t == "2" { " squared" } else if t == "3" { " cubed" } else if t == "prime" or t == "dagger" or t == "star" { " " + t }
        else if t == "minus 1" and base != "" { " inverse" } else { " to the " + t }
    }
    if c.has("br") { out = _join((out, speak(c.br))) }
    if c.has("tr") { out = _join((out, speak(c.tr))) }
    out
  } else if f == math.frac {
    let n = speak(c.num)
    let d = speak(c.denom)
    let o = if n in small-numbers { _ordinal(d) } else { none }
    if o != none { small-numbers.at(n) + " " + o + (if n != "1" { "s" } else { "" }) }
    else if n.len() <= 3 and d.len() <= 3 { n + " over " + d }
    else { "the fraction " + n + " over " + d + ", end fraction," }
  } else if f == math.binom {
    "the binomial coefficient " + speak(c.upper) + " choose " + _join(c.lower.map(speak))
  } else if f == math.root {
    if c.has("index") { "the " + speak(c.index) + "th root of " + speak(c.radicand) } else { "the square root of " + speak(c.radicand) }
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
    word + speak(c.base)
  } else if f == math.op {
    speak(c.text)
  } else if f == math.lr {
    // delimiters: |x| absolute value, ‖v‖ norm, otherwise read the brackets out
    let kids = if c.body.func() == sequence { c.body.children } else { (c.body,) }
    // delimiters are `symbol` elements with a `text` field (not `text` elements)
    let first = if kids.len() > 0 and kids.first().has("text") and type(kids.first().text) == str { kids.first().text } else { "" }
    let inner = _join(kids.slice(1, kids.len() - 1).map(speak))
    if first == "|" { "the absolute value of " + inner + ", end absolute value," }
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
  let a = if alt == auto { speak(body) } else { alt }
  math.equation(block: block, numbering: numbering, alt: a, body)
}
