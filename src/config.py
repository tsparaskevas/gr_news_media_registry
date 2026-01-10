from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Paths:
    root: Path
    data: Path
    sources: Path
    bronze: Path
    silver: Path
    gold: Path
    overrides: Path
    published: Path

def get_paths(project_root: Path) -> Paths:
    data = project_root / "data"
    return Paths(
        root=project_root,
        data=data,
        sources=data / "sources",
        bronze=data / "bronze",
        silver=data / "silver",
        gold=data / "gold",
        overrides=data / "overrides",
        published=data / "published",
    )

