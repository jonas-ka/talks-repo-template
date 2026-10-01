"""talks-repo: reproducible research-talk slides from a brief plus an asset library."""

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TALKS_YAML = REPO_ROOT / "talks.yaml"
FILES_YAML = REPO_ROOT / "files.yaml"
FOLDERS_YAML = REPO_ROOT / "folders.yaml"
REVIEW_DIR = REPO_ROOT / "review"
WORK_DIR = REPO_ROOT / "work"


@dataclass(frozen=True)
class InputRoot:
    """A read-only input folder. Lower priority number = more important."""

    name: str
    path: Path
    era: str
    priority: int


# Never write inside these. Order = priority (UNI first, CERN-era last).
INPUT_ROOTS: tuple[InputRoot, ...] = (
    InputRoot(
        "tamu",
        Path("<input-folder-1>"),
        "UNI",
        1,
    ),
    InputRoot("mit", Path("<input-folder-2>"), "MIT", 2),
    InputRoot(
        "phd",
        Path("<input-folder-3>"),
        "PhD",
        3,
    ),
)
ROOT_BY_NAME = {r.name: r for r in INPUT_ROOTS}


def resolve_ref(ref: str) -> Path:
    """Turn a 'root:relative/path' reference from the manifests into an absolute path."""
    root_name, _, rel = ref.partition(":")
    return ROOT_BY_NAME[root_name].path / rel
