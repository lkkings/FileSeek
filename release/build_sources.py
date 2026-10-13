"""Lists, per platform, every file the app downloads on first run: the Python interpreter,
the backend's dependency wheels, and the model. Written to
`desktop/src-tauri/runtime-sources/<target>.json`, which `build.rs` compiles into the app.

    uv run --no-project --python 3.12 --with packaging release/build_sources.py [--check]

Nothing is repackaged or rehosted. Each file is fetched from its official source or a
mirror of it (`runtime.json` → `mirrors`), and checked against the sha256 pinned here:

- Python: python-build-standalone, `install_only_stripped`, pinned in `runtime.json`
- wheels: exactly the files `backend/uv.lock` pins, picked for each platform by its
  markers and wheel tags
- model: the Hugging Face files pinned in `runtime.json` → `model`

Run it after changing `uv.lock` or `runtime.json`. `--check` exits non-zero when the
committed files are out of date (and needs no network once `pbs_size` is filled in).
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
import urllib.request
from pathlib import Path

from packaging.markers import Marker
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

from runtime_id import REPO_ROOT, RUNTIME_CONFIG, current_runtime_id, load_config

LOCK = REPO_ROOT / "backend" / "uv.lock"
OUT_DIR = REPO_ROOT / "desktop" / "src-tauri" / "runtime-sources"
PBS_FILE = "cpython-{version}+{release}-{target}-install_only_stripped.tar.gz"
# The official PyPI file host: lock URLs are under it, mirrors keep the same paths.
PYPI_FILES = "https://files.pythonhosted.org/packages/"
# Unpacked size, as a multiple of what is downloaded: measured on the macOS runtime
# (303 MB packed → 1.41 GB installed), rounded up. Only for the free-space check.
UNPACK_FACTOR = 5

# Decision 16: the four platforms every dependency publishes wheels for.
TARGETS = {
    "aarch64-apple-darwin": {
        "env": {"sys_platform": "darwin", "platform_system": "Darwin", "platform_machine": "arm64",
                "os_name": "posix"},
        "platforms": [f"macosx_{major}_0_arm64" for major in range(14, 10, -1)]
        + [f"macosx_{major}_0_universal2" for major in range(14, 10, -1)]
        + [f"macosx_10_{minor}_universal2" for minor in range(16, 8, -1)],
        "python": "python/bin/python3",
    },
    "x86_64-pc-windows-msvc": {
        "env": {"sys_platform": "win32", "platform_system": "Windows", "platform_machine": "AMD64",
                "os_name": "nt"},
        "platforms": ["win_amd64"],
        "python": "python/python.exe",
    },
    "x86_64-unknown-linux-gnu": {
        "env": {"sys_platform": "linux", "platform_system": "Linux", "platform_machine": "x86_64",
                "os_name": "posix"},
        "platforms": [f"manylinux_2_{minor}_x86_64" for minor in range(28, 16, -1)]
        + ["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"],
        "python": "python/bin/python3",
    },
    "aarch64-unknown-linux-gnu": {
        "env": {"sys_platform": "linux", "platform_system": "Linux", "platform_machine": "aarch64",
                "os_name": "posix"},
        "platforms": [f"manylinux_2_{minor}_aarch64" for minor in range(28, 16, -1)]
        + ["manylinux2014_aarch64"],
        "python": "python/bin/python3",
    },
}


def environment(target: str, python_version: str) -> dict[str, str]:
    major, minor, *_ = python_version.split(".")
    return {
        **TARGETS[target]["env"],
        "python_version": f"{major}.{minor}",
        "python_full_version": python_version,
        "implementation_name": "cpython",
        "platform_python_implementation": "CPython",
        "extra": "",
    }


def applies(marker: str | None, env: dict[str, str], extra: str = "") -> bool:
    return marker is None or Marker(marker).evaluate({**env, "extra": extra})


def resolve(lock: dict, env: dict[str, str]) -> list[dict]:
    """The packages installed for `env`: the editable root's dependencies, transitively,
    with markers and extras applied. Dev dependencies are not installed."""
    packages = {canonicalize_name(p["name"]): p for p in lock["package"]}
    root = next(p for p in lock["package"] if p.get("source", {}).get("editable"))
    wanted: dict[str, set[str]] = {}
    queue: list[tuple[str, set[str]]] = []

    def follow(deps: list[dict], parent_extra: str = "") -> None:
        for dep in deps:
            if applies(dep.get("marker"), env, parent_extra):
                queue.append((canonicalize_name(dep["name"]), set(dep.get("extra", []))))

    follow(root.get("dependencies", []))
    while queue:
        name, extras = queue.pop()
        seen = wanted.get(name)
        if seen is not None and extras <= seen:
            continue
        new_extras = extras - (seen or set())
        wanted[name] = (seen or set()) | extras
        package = packages[name]
        if seen is None:
            follow(package.get("dependencies", []))
        for extra in new_extras:
            follow(package.get("optional-dependencies", {}).get(extra, []), extra)
    return [packages[name] for name in sorted(wanted)]


def pick_wheel(package: dict, tags: list) -> dict:
    """The most specific wheel of `package` for these tags, as pip would choose."""
    rank = {tag: index for index, tag in enumerate(tags)}
    best: tuple[int, dict] | None = None
    for wheel in package.get("wheels", []):
        filename = wheel["url"].rsplit("/", 1)[1]
        _, _, _, wheel_tags = parse_wheel_filename(filename)
        score = min((rank[tag] for tag in wheel_tags if tag in rank), default=None)
        if score is not None and (best is None or score < best[0]):
            best = (score, wheel)
    if best is None:
        raise SystemExit(
            f"{package['name']} {package['version']} has no wheel for this platform "
            "(only an sdist, or none at all): it cannot be installed without building"
        )
    return best[1]


def pypi_path(url: str) -> str:
    if not url.startswith(PYPI_FILES):
        raise SystemExit(f"{url} is not on the PyPI file host; mirrors would not have it")
    return url.removeprefix(PYPI_FILES)


def pbs_size(config: dict, target: str, file: str) -> int:
    """The interpreter archive's size: from `runtime.json`, else asked of GitHub once."""
    cached = config.get("pbs_size", {}).get(target)
    if cached:
        return cached
    url = config["mirrors"]["python"][-1].format(release=config["pbs_release"], file=file)
    request = urllib.request.Request(url, method="HEAD")  # noqa: S310 -- fixed https URL
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        size = int(response.headers["Content-Length"])
    config.setdefault("pbs_size", {})[target] = size
    return size


def sources_for(target: str, config: dict, lock: dict, runtime_id: str) -> dict:
    spec = TARGETS[target]
    env = environment(target, config["python_version"])
    # What pip on that platform accepts, most specific first: cp312 and abi3 builds, then
    # `py3-none-<platform>` (pypdfium2 ships those), then pure Python.
    tags = list(cpython_tags((3, 12), abis=["cp312", "abi3", "none"], platforms=spec["platforms"]))
    tags += list(compatible_tags((3, 12), "cp312", platforms=spec["platforms"]))
    mirrors = config["mirrors"]

    wheels = []
    for package in resolve(lock, env):
        if package.get("source", {}).get("editable"):
            continue
        wheel = pick_wheel(package, tags)
        path = pypi_path(wheel["url"])
        wheels.append(
            {
                "file": path.rsplit("/", 1)[1],
                "size": wheel["size"],
                "sha256": wheel["hash"].removeprefix("sha256:"),
                "urls": [m.format(path=path) for m in mirrors["pypi"]],
            }
        )

    file = PBS_FILE.format(version=config["python_version"], release=config["pbs_release"], target=target)
    python_size = pbs_size(config, target, file)
    model = config["model"]
    return {
        "v": 2,
        "runtime_id": runtime_id,
        "target": target,
        "python": {
            "file": file,
            "size": python_size,
            "sha256": config["pbs_sha256"][target],
            "urls": [m.format(release=config["pbs_release"], file=file) for m in mirrors["python"]],
            "interpreter": spec["python"],
        },
        "wheels": wheels,
        "unpacked_size": UNPACK_FACTOR * (python_size + sum(w["size"] for w in wheels)),
        "model": {
            "id": model["id"],
            "files": [
                {
                    "path": f["path"],
                    "size": f["size"],
                    "sha256": f["sha256"],
                    "urls": [
                        m.format(repo=model["repo"], revision=model["revision"], file=f["file"])
                        for m in mirrors["model"]
                    ],
                }
                for f in model["files"]
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if the committed files are stale")
    args = parser.parse_args()

    config = load_config()
    lock = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    runtime_id = current_runtime_id()
    stale = []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for target in TARGETS:
        sources = sources_for(target, config, lock, runtime_id)
        text = json.dumps(sources, indent=1) + "\n"
        path = OUT_DIR / f"{target}.json"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path.name)
            continue
        path.write_text(text, encoding="utf-8")
        total = sources["python"]["size"] + sum(w["size"] for w in sources["wheels"])
        print(f"{target}: {len(sources['wheels'])} wheels, {total / 1e6:.0f} MB to download")
    if args.check:
        if stale:
            sys.exit(f"stale, run release/build_sources.py: {', '.join(stale)}")
        print("runtime sources are up to date")
    else:
        # Keep the sizes looked up, so `--check` and the next run need no network.
        RUNTIME_CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
