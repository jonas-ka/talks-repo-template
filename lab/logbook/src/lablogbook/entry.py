"""One log-book entry: a Markdown file `entries/YYYY/<id>.md` with a YAML header.

The id is the file name without `.md`: `YYYY-MM-DD-HHMM-<handle>-<slug>`, e.g.
`2026-10-13-1735-aa-first-scan`. Dates stay strings (`YYYY-MM-DD`), never `date` objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ID_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<hhmm>\d{4})-(?P<handle>[a-z0-9]+)-(?P<slug>[a-z0-9][a-z0-9-]*)$")
CALLOUTS = ("decision", "finding", "issue", "todo", "context", "incident")
OPENABLE = ("issue", "todo")  # blocks that stay open until a later entry `resolves` them
PRIORITIES = ("low", "medium", "high", "asap")   # of an open item; none written means medium
DEFAULT_PRIORITY = "medium"

# ::: finding            ::: issue {#issue-drift}            ::: {.todo #todo-1}
_DIV_OPEN = re.compile(r"^(?P<fence>:{3,})\s*(?:(?P<name>[A-Za-z][\w-]*)\s*)?(?:\{(?P<attrs>[^}]*)\})?\s*$")
_DIV_CLOSE = re.compile(r"^:{3,}\s*$")
_WIKILINK = re.compile(r"\[\[([^\]|\n]+)(?:\|[^\]\n]*)?\]\]")
_CODE_BLOCK = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
_CODE_SPAN = re.compile(r"`[^`\n]*`")
_BRACKET = re.compile(r"\[([^\[\]\n]*@[^\[\]\n]*)\]")
_CITE_IN_BRACKET = re.compile(r"(?<![\w.@])-?@([A-Za-z0-9_][\w:.#$%&+?<>~/-]*)")
_NARRATIVE_CITE = re.compile(r"(?<![\w.@\[])@([A-Z][A-Za-z'-]+\d{4}[a-z]?)\b")


class _StringDates(yaml.SafeLoader):
    """A YAML loader that leaves dates and times as the strings they were written as."""


_StringDates.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.copy().items()
}



def slugify(text: str, limit: int = 48) -> str:
    """Lower case, hyphens, at most `limit` characters, cut after a whole word where possible."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) > limit:
        cut = s[:limit + 1].rfind("-")
        s = s[:cut] if cut >= limit // 3 else s[:limit]
    return s.rstrip("-") or "entry"

def load_yaml(text: str):
    return yaml.load(text, Loader=_StringDates)


class EntryError(ValueError):
    """The file is not an entry at all (no header, unreadable YAML)."""


@dataclass
class Block:
    name: str           # decision, finding, issue, todo, context, incident, or something unknown
    anchor: str | None  # the {#id}, if any
    line: int           # 1-based line of the opening fence
    priority: str | None = None   # the block's own `priority=…` ({#todo-x priority=high}), as written


@dataclass
class Entry:
    path: Path                       # the .md file
    id: str
    header: dict
    body: str
    body_line: int                   # 1-based line where the body starts
    text: str                        # the whole file
    blocks: list[Block] = field(default_factory=list)

    # ---- convenience -----------------------------------------------------------------------
    @property
    def folder(self) -> Path:
        return self.path.parent

    @property
    def date(self) -> str:
        return str(self.header.get("date", ""))

    @property
    def authors(self) -> list[str]:
        return list(self.header.get("authors") or [])

    @property
    def projects(self) -> list[str]:
        p = [self.header.get("project")] + list(self.header.get("also") or [])
        return [x for x in p if x]

    def anchors(self) -> dict[str, Block]:
        return {b.anchor: b for b in self.blocks if b.anchor}

    def files(self) -> list[tuple[str, str, dict]]:
        """(section, relative path, item) for every file the header refers to."""
        out = []
        for section in ("figures", "data", "attachments", "epics"):
            for item in self.header.get(section) or []:
                if isinstance(item, dict) and item.get("file"):
                    out.append((section, item["file"], item))
        return out

    def links(self) -> list[tuple[str, int]]:
        """[[target]] links in the body with their line numbers (code removed)."""
        out = []
        for i, line in enumerate(_strip_code(self.body).splitlines(), start=self.body_line):
            out += [(m.group(1).strip(), i) for m in _WIKILINK.finditer(line)]
        return out

    def citations(self) -> list[tuple[str, int]]:
        """Citation keys ([@key], [see @a; @b], narrative @Lastname2019) with line numbers."""
        out = []
        for i, line in enumerate(_strip_code(self.body).splitlines(), start=self.body_line):
            for b in _BRACKET.finditer(line):
                out += [(k.rstrip(".:;,"), i) for k in _CITE_IN_BRACKET.findall(b.group(1))]
            out += [(k, i) for k in _NARRATIVE_CITE.findall(_BRACKET.sub("", line))]
        return out


def _strip_code(text: str) -> str:
    """Code blocks and spans replaced by blank text of the same line count."""
    text = _CODE_BLOCK.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _CODE_SPAN.sub("``", text)


def block_problems(body: str, first_line: int) -> list[tuple[int, str]]:
    """(line, message) for block lines that cannot be read (`::: todo {#todo-1` without its `}`)
    and for blocks that are never closed."""
    out, open_lines, in_code = [], [], False
    for i, line in enumerate(body.splitlines(), start=first_line):
        if line.startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code or not line.startswith(":::"):
            continue
        if _DIV_CLOSE.match(line):
            if open_lines:
                open_lines.pop()
            continue
        m = _DIV_OPEN.match(line)
        if m and (m.group("name") or m.group("attrs") is not None):
            open_lines.append(i)
        else:
            out.append((i, "a block line that cannot be read (a block starts with a line like "
                           "'::: todo {#todo-1}', braces closed, and ends with a line ':::')"))
    out += [(i, "this block is never closed: end it with a line ':::'") for i in open_lines]
    return out


def parse_blocks(body: str, first_line: int) -> list[Block]:
    blocks, depth = [], 0
    in_code = False
    for i, line in enumerate(body.splitlines(), start=first_line):
        if line.startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = _DIV_OPEN.match(line)
        if m and (m.group("name") or m.group("attrs")) and not _DIV_CLOSE.match(line):
            name, attrs = m.group("name"), m.group("attrs") or ""
            classes = re.findall(r"\.([A-Za-z][\w-]*)", attrs)
            ids = re.findall(r"#([A-Za-z][\w-]*)", attrs)
            pr = re.search(r"""\bpriority\s*=\s*["']?([A-Za-z]+)""", attrs)
            blocks.append(Block(name or (classes[0] if classes else ""), ids[0] if ids else None, i,
                                pr.group(1).lower() if pr else None))
            depth += 1
        elif _DIV_CLOSE.match(line) and depth:
            depth -= 1
    return blocks


def parse(path: str | Path, text: str | None = None) -> Entry:
    path = Path(path)
    if text is None:
        text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise EntryError("an entry starts with a YAML header between two '---' lines")
    end = text.find("\n---\n", 4)
    if end < 0:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            raise EntryError("the YAML header is not closed by a '---' line")
    try:
        header = load_yaml(text[4:end + 1]) or {}
    except yaml.YAMLError as e:
        raise EntryError(f"the YAML header does not parse: {e}".splitlines()[0]) from None
    if not isinstance(header, dict):
        raise EntryError("the YAML header must be a mapping (key: value lines)")
    body_start = end + len("\n---\n")
    body = text[body_start:]
    body_line = text[:body_start].count("\n") + 1
    e = Entry(path=path, id=path.stem, header=header, body=body, body_line=body_line, text=text)
    e.blocks = parse_blocks(body, body_line)
    return e


def new_id(date: str, hhmm: str, handle: str, title: str) -> str:
    """The id for a new entry; the slug is made from the title."""
    slug = slugify(title)
    return f"{date}-{hhmm}-{handle}-{slug}"
