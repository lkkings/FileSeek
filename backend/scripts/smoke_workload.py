"""Exercise the protected backend with a real import and text search.

    uv run --extra dev python scripts/smoke_workload.py

The script starts the protected package using the current Python runtime, creates a
temporary library, imports a generated image, waits for the import to finish, and runs a
text search. It verifies that the API returns a result and that only the main backend
process listens on the API port.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "dist" / "fileseek-backend-protected"
STARTUP_TIMEOUT = 120.0
WORKLOAD_TIMEOUT = 180.0


def connection_file(home: Path) -> Path:
    if sys.platform == "win32":
        return home / "AppData" / "Roaming" / "FileSeek" / "connection.json"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "FileSeek" / "connection.json"
    return home / ".config" / "fileseek" / "connection.json"


def model_cache_dir() -> Path | None:
    configured = os.environ.get("EMBEDDING_MODEL_CACHE_DIR")
    if configured:
        return Path(configured)
    default = (
        Path.home()
        / "Library"
        / "Application Support"
        / "FileSeek"
        / "models"
        / "jina-clip-v2-q"
    )
    return default if default.is_dir() else None


def listener_count(port: int) -> int:
    lsof = shutil.which("lsof")
    if lsof is None:
        return 1
    result = subprocess.run(  # noqa: S603
        [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    return len(
        [line for line in result.stdout.splitlines() if line and not line.startswith("COMMAND")]
    )


def wait_for_connection(process: subprocess.Popen[bytes], connection: Path) -> dict[str, object]:
    started = time.monotonic()
    while not connection.is_file():
        if process.poll() is not None:
            raise RuntimeError("backend exited before publishing its connection file")
        if time.monotonic() - started > STARTUP_TIMEOUT:
            raise RuntimeError("backend did not publish its connection file in time")
        time.sleep(0.1)
    return json.loads(connection.read_text(encoding="utf-8"))


def stream_until_complete(client: httpx.Client, import_id: str) -> str:
    with client.stream(
        "GET",
        f"/api/v1/library/files/import/{import_id}/events",
    ) as response:
        response.raise_for_status()
        event_type = None
        task_id = None
        for line in response.iter_lines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ").strip()
            elif line.startswith("data: ") and event_type == "item_failed":
                payload = json.loads(line.removeprefix("data: "))
                raise RuntimeError(f"image import failed: {payload}")
            elif line.startswith("data: ") and event_type in {"item_registered", "item_completed"}:
                payload = json.loads(line.removeprefix("data: "))
                task_id = str(payload.get("task_id"))
            elif line.startswith("data: ") and event_type == "batch_completed":
                payload = json.loads(line.removeprefix("data: "))
                if payload.get("failed", 0):
                    raise RuntimeError(f"import completed with failures: {payload}")
                if task_id is None:
                    raise RuntimeError("import completed without a task id")
                return task_id
        raise RuntimeError("import event stream ended before batch_completed")


def wait_for_task(client: httpx.Client, task_id: str) -> None:
    deadline = time.monotonic() + WORKLOAD_TIMEOUT
    while time.monotonic() < deadline:
        response = client.get("/api/v1/tasks", params={"page": 1, "page_size": 100})
        response.raise_for_status()
        tasks = response.json()["data"]["tasks"]
        task = next((item for item in tasks if item["id"] == task_id), None)
        if task is None:
            raise RuntimeError(f"import task disappeared: {task_id}")
        status = task["status"]
        if status == "completed":
            return
        if status in {"failed", "cancelled"}:
            raise RuntimeError(f"import task ended as {status}: {task}")
        time.sleep(0.5)
    raise RuntimeError(f"import task did not finish in {WORKLOAD_TIMEOUT}s: {task_id}")


def main() -> int:
    if not (PACKAGE / "fileseek" / "__main__.py").is_file():
        print(f"protected backend not found: {PACKAGE}", file=sys.stderr)
        return 1

    model_cache = model_cache_dir()
    with tempfile.TemporaryDirectory(prefix="fileseek-workload-") as tmp:
        home = Path(tmp)
        image_path = home / "red.png"
        Image.new("RGB", (64, 64), "#ff0000").save(image_path, format="PNG")

        dropped = {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PYTHONSTARTUP", "XDG_CONFIG_HOME"}
        env = {key: value for key, value in os.environ.items() if key not in dropped}
        env.update(
            HOME=str(home),
            USERPROFILE=str(home),
            APPDATA=str(home / "AppData" / "Roaming"),
            LIB_ROOT=str(home / "FileSeekLibrary"),
            PYTHONUTF8="1",
            PYTHONPATH=str(PACKAGE),
        )
        if model_cache is not None:
            env["EMBEDDING_MODEL_CACHE_DIR"] = str(model_cache)

        log_path = home / "backend.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(  # noqa: S603
                [sys.executable, "-m", "fileseek"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                info = wait_for_connection(process, connection_file(home))
                port = int(info["port"])  # type: ignore[arg-type]
                token = str(info["token"])
                headers = {"X-FileSeek-Token": token}

                with httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    headers=headers,
                    timeout=WORKLOAD_TIMEOUT,
                ) as client:
                    health = client.get("/health")
                    health.raise_for_status()

                    folder = client.post(
                        "/api/v1/library/folders",
                        json={"name": "smoke", "icon_type": "default"},
                    )
                    folder.raise_for_status()
                    folder_id = folder.json()["data"]["id"]

                    started_import = client.post(
                        "/api/v1/library/files/import",
                        json={
                            "folder_id": folder_id,
                            "items": [{"path": str(image_path)}],
                        },
                    )
                    started_import.raise_for_status()
                    import_id = started_import.json()["data"]["import_id"]
                    task_id = stream_until_complete(client, import_id)
                    wait_for_task(client, task_id)

                    search = client.post(
                        "/api/v1/search",
                        json={
                            "query": "red",
                            "categories": ["image"],
                            "page_number": 1,
                            "page_size": 10,
                        },
                    )
                    search.raise_for_status()
                    items = search.json()["data"]["items"]
                    if not items:
                        raise RuntimeError("text search returned no results after image import")

                listeners = listener_count(port)
                if listeners != 1:
                    raise RuntimeError(f"expected one API listener, found {listeners}")

                print(
                    "ok: imported image, search returned "
                    f"{len(items)} result(s), one API listener"
                )
                return 0
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                if process.returncode not in (0, None):
                    sys.stderr.write(log_path.read_text(encoding="utf-8", errors="replace")[-4000:])


if __name__ == "__main__":
    raise SystemExit(main())
