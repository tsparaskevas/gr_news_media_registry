from __future__ import annotations

from pathlib import Path

DEMO_ALLOWED = {
    "07_Final_Registry.py",
    "08_Map_Prefectures.py",
}


def apply_demo_page_visibility(project_root: Path, demo: bool = True) -> None:
    pages_dir = project_root / "app" / "pages"
    hidden_dir = project_root / "app" / "pages_hidden"
    hidden_dir.mkdir(parents=True, exist_ok=True)

    if not pages_dir.exists():
        return

    if demo:
        # Move non-demo pages into pages_hidden/
        for p in pages_dir.glob("*.py"):
            if p.name in DEMO_ALLOWED:
                continue
            target = hidden_dir / p.name
            if target.exists():
                # avoid overwriting
                continue
            p.rename(target)
    else:
        # Restore all hidden pages back into pages/
        for p in hidden_dir.glob("*.py"):
            target = pages_dir / p.name
            if target.exists():
                continue
            p.rename(target)

