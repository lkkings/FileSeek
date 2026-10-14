"""Lists, per platform, every file the app downloads on first run: the model files.
Written to `desktop/src-tauri/runtime-sources/<target>.json`, which `build.rs` compiles
into the app. The backend is compiled (`backend/build_nuitka.py`) and ships inside the app.

    uv run --no-project --python 3.12 release/build_sources.py [--check]

Nothing is repackaged or rehosted. Each file is fetched from its official source or a
mirror of it (`runtime.json` → `mirrors.model`), and checked against the sha256 pinned in
`runtime.json` → `model`.

Run it after changing `runtime.json`. `--check` exits non-zero when the committed files
are out of date.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RELEASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = RELEASE_DIR.parent
RUNTIME_CONFIG = RELEASE_DIR / "runtime.json"
OUT_DIR = REPO_ROOT / "desktop" / "src-tauri" / "runtime-sources"
# The source list format `runtime/manifest.rs` reads.
VERSION = 3

# The platforms the app can be built for. The model is the same on each; the list is per
# target only because the app compiles in the one for its own.
TARGETS = (
    "aarch64-apple-darwin",
    "x86_64-pc-windows-msvc",
    "x86_64-unknown-linux-gnu",
    "aarch64-unknown-linux-gnu",
)


def load_config(path: Path = RUNTIME_CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sources_for(target: str, config: dict) -> dict:
    model = config["model"]
    mirrors = config["mirrors"]["model"]
    return {
        "v": VERSION,
        "target": target,
        "model": {
            "id": model["id"],
            "files": [
                {
                    "path": f["path"],
                    "size": f["size"],
                    "sha256": f["sha256"],
                    "urls": [
                        m.format(repo=model["repo"], revision=model["revision"], file=f["file"])
                        for m in mirrors
                    ],
                }
                for f in model["files"]
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check", action="store_true", help="fail if the committed files are stale"
    )
    args = parser.parse_args()

    config = load_config()
    stale = []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for target in TARGETS:
        sources = sources_for(target, config)
        text = json.dumps(sources, indent=1) + "\n"
        path = OUT_DIR / f"{target}.json"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path.name)
            continue
        path.write_text(text, encoding="utf-8")
        files = sources["model"]["files"]
        total = sum(f["size"] for f in files)
        print(f"{target}: {len(files)} model files, {total / 1e6:.0f} MB to download")
    if args.check:
        if stale:
            sys.exit(f"stale, run release/build_sources.py: {', '.join(stale)}")
        print("runtime sources are up to date")


if __name__ == "__main__":
    main()
