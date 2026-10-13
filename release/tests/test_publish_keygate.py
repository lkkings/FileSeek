"""`publish_keygate.py` 对着一个按 Keygate admin API 行为写的假服务器跑。"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from publish_keygate import Keygate, KeygateError, parse_artifact, publish  # noqa: E402

PRODUCT = "prod-1"


class FakeKeygate:
    """内存里的 releases / artifacts，加一个代替对象存储的 PUT 端点。"""

    def __init__(self) -> None:
        self.releases: dict[str, dict] = {}
        self.uploads: dict[str, bytes] = {}
        self.calls: list[tuple[str, str, dict | None, dict]] = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.base = f"http://127.0.0.1:{server.server_address[1]}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.server = server

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _reply(self, status, data=None, error=None):
                body = {"success": error is None}
                if error:
                    body["error"] = {"code": error, "message": error.lower()}
                else:
                    body["data"] = data
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _route(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                path = self.path.split("?")[0]
                if path.startswith("/upload/"):
                    fake.uploads[path.removeprefix("/upload/")] = raw
                    self.send_response(200)
                    self.end_headers()
                    return None
                if self.headers.get("Authorization") != "Bearer kg_test":
                    return self._reply(401, error="UNAUTHORIZED")
                body = json.loads(raw) if raw else None
                fake.calls.append((method, path, body, dict(self.headers)))
                return fake.handle(self, method, path, body)

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PATCH(self):
                self._route("PATCH")

            def do_DELETE(self):
                self._route("DELETE")

            def do_PUT(self):
                self._route("PUT")

        return Handler

    def handle(self, h, method, path, body):  # noqa: C901, PLR0911 -- 路由表
        parts = path.removeprefix("/api/v1/admin/").split("/")
        if parts == ["releases"] and method == "GET":
            return h._reply(
                200, {"limit": 200, "offset": 0, "releases": list(self.releases.values())}
            )
        if parts == ["releases"] and method == "POST":
            rid = str(uuid.uuid4())
            self.releases[rid] = {**body, "id": rid, "status": "draft", "artifacts": []}
            return h._reply(201, self.releases[rid])
        release = self.releases.get(parts[1]) if len(parts) > 1 else None
        if release is None:
            return h._reply(404, error="RELEASE_NOT_FOUND")
        if len(parts) == 2 and method == "GET":
            return h._reply(200, release)
        if len(parts) == 2 and method == "PATCH":
            release.update(body)
            return h._reply(200, release)
        if parts[2] == "artifacts" and len(parts) == 3:
            if any(a["platform"] == body["platform"] for a in release["artifacts"]):
                return h._reply(409, error="ARTIFACT_EXISTS")
            aid = str(uuid.uuid4())
            artifact = {
                "id": aid,
                "platform": body["platform"],
                "filename": body["filename"],
                "sha256": "",
            }
            release["artifacts"].append(artifact)
            return h._reply(201, {"artifact": artifact, "upload_url": f"{self.base}/upload/{aid}"})
        if parts[2] == "artifacts" and method == "DELETE":
            release["artifacts"] = [a for a in release["artifacts"] if a["id"] != parts[3]]
            return h._reply(200, {"status": "deleted"})
        if parts[2] == "artifacts" and parts[4] == "finalize":
            artifact = next(a for a in release["artifacts"] if a["id"] == parts[3])
            actual = hashlib.sha256(self.uploads.get(parts[3], b"")).hexdigest()
            if body.get("expected_sha256") and body["expected_sha256"] != actual:
                return h._reply(400, error="SHA256_MISMATCH")
            artifact["sha256"] = actual
            return h._reply(200, artifact)
        if parts[2:] == ["actions", "publish"]:
            if not release["artifacts"]:
                return h._reply(400, error="NO_ARTIFACTS")
            release["status"] = "published"
            return h._reply(200, release)
        return h._reply(404, error="NO_ROUTE")


@pytest.fixture
def fake():
    server = FakeKeygate()
    yield server
    server.server.shutdown()


def bundle(tmp_path: Path, name: str, content: bytes = b"app") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def run(fake: FakeKeygate, artifacts: dict, do_publish=True, version="0.2.0"):
    return publish(
        Keygate(fake.base, "kg_test"),
        product_id=PRODUCT,
        version=version,
        channel="stable",
        notes="notes",
        artifacts=artifacts,
        do_publish=do_publish,
        log=lambda *_: None,
    )


def test_creates_uploads_finalizes_and_publishes(fake, tmp_path):
    mac = bundle(tmp_path, "FileSeek.app.tar.gz", b"mac")
    win = bundle(tmp_path, "FileSeek_0.2.0_x64-setup.exe", b"win")

    release = run(fake, {"darwin-arm64": mac, "windows-x64": win})

    assert release["status"] == "published"
    stored = fake.releases[release["id"]]
    assert stored["product_id"] == PRODUCT and stored["version"] == "0.2.0"
    assert {a["platform"]: a["sha256"] for a in stored["artifacts"]} == {
        "darwin-arm64": hashlib.sha256(b"mac").hexdigest(),
        "windows-x64": hashlib.sha256(b"win").hexdigest(),
    }
    added = [body for method, path, body, _ in fake.calls if path.endswith("/artifacts")]
    assert added[0]["expected_size"] == 3
    assert added[0]["content_type"] == "application/gzip"


def test_without_publish_it_stays_a_draft(fake, tmp_path):
    release = run(fake, {"linux-x64": bundle(tmp_path, "FileSeek.AppImage")}, do_publish=False)

    assert fake.releases[release["id"]]["status"] == "draft"


def test_a_second_run_reuses_the_draft_and_replaces_the_platform_file(fake, tmp_path):
    first = run(fake, {"linux-x64": bundle(tmp_path, "a.AppImage", b"old")}, do_publish=False)

    second = run(fake, {"linux-x64": bundle(tmp_path, "b.AppImage", b"new")}, do_publish=False)

    assert second["id"] == first["id"]
    assert len(fake.releases) == 1
    (artifact,) = fake.releases[first["id"]]["artifacts"]
    assert artifact["sha256"] == hashlib.sha256(b"new").hexdigest()


def test_a_published_version_is_left_alone(fake, tmp_path):
    run(fake, {"linux-x64": bundle(tmp_path, "a.AppImage")})

    with pytest.raises(SystemExit, match="published"):
        run(fake, {"linux-x64": bundle(tmp_path, "b.AppImage")})


def test_a_corrupted_upload_is_caught_at_finalize(fake, tmp_path, monkeypatch):
    import publish_keygate

    original = publish_keygate.sha256_file
    monkeypatch.setattr(
        publish_keygate, "sha256_file", lambda p: "0" * 64 if p.name else original(p)
    )

    with pytest.raises(KeygateError) as error:
        run(fake, {"linux-x64": bundle(tmp_path, "a.AppImage")})
    assert error.value.code == "SHA256_MISMATCH"


def test_a_bad_key_is_reported(fake, tmp_path):
    with pytest.raises(KeygateError) as error:
        publish(
            Keygate(fake.base, "wrong"),
            product_id=PRODUCT,
            version="0.2.0",
            channel="stable",
            notes="",
            artifacts={"linux-x64": bundle(tmp_path, "a.AppImage")},
            do_publish=False,
            log=lambda *_: None,
        )
    assert error.value.status == 401


def test_artifact_arguments_are_checked(tmp_path):
    assert parse_artifact(f"linux-arm64={bundle(tmp_path, 'x.AppImage')}")[0] == "linux-arm64"
    with pytest.raises(SystemExit, match="不支持的平台"):
        parse_artifact(f"darwin-x64={bundle(tmp_path, 'y.app.tar.gz')}")
    with pytest.raises(SystemExit, match="签名文件"):
        parse_artifact(f"linux-x64={bundle(tmp_path, 'z.AppImage.sig')}")
    with pytest.raises(SystemExit, match="找不到"):
        parse_artifact(f"linux-x64={tmp_path / 'missing'}")
