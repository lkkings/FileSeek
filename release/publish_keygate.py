"""把各平台的应用更新包发布到自部署的 Keygate。

    KEYGATE_API_KEY=kg_live_... uv run --no-project --python 3.12 release/publish_keygate.py \\
        --version 0.2.0 --notes "修复导入大文件时崩溃" \\
        --artifact darwin-arm64=.../FileSeek.app.tar.gz \\
        --artifact windows-x64=.../FileSeek_0.2.0_x64-setup.exe \\
        --artifact linux-x64=.../FileSeek_0.2.0_amd64.AppImage \\
        [--publish] [--dry-run]

流程（Keygate admin API，`Authorization: Bearer <key>`，只需 `releases:write`）：

    POST /admin/releases                          建草稿（同版本已有草稿就复用）
    POST /admin/releases/:id/artifacts            每个平台拿一个短时预签名上传地址
    PUT  <upload_url>                             直传到对象存储，不经过 Keygate
    POST /admin/releases/:id/artifacts/:aid/finalize  带本地 sha256，Keygate 读回存储复核
    POST /admin/releases/:id/actions/publish      Keygate 签名每个文件，进入 feed

不加 `--publish` 只上传到草稿，可以在 Keygate 后台检查后再手动发布。已发布或已撤回的
同名版本不会被改动。复用草稿时，同平台的旧文件先删掉再传。

更新包由 Keygate 在发布时签名，`tauri build` 生成的 `.sig` 不需要上传。地址和产品取自
`desktop/src-tauri/keygate.json`。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYGATE_CONFIG = REPO_ROOT / "desktop" / "src-tauri" / "keygate.json"
# 决策 16：只发布依赖齐全的 4 个平台。
PLATFORMS = ("darwin-arm64", "windows-x64", "linux-x64", "linux-arm64")
TIMEOUT = 60
UPLOAD_TIMEOUT = 1800


class KeygateError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"HTTP {status} {code}: {message}")
        self.status = status
        self.code = code


@dataclass
class Keygate:
    base_url: str
    api_key: str

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(  # noqa: S310 -- 构建时配置的 https 地址
            f"{self.base_url}/api/v1/admin{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "FileSeek-release",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
                text = response.read()
        except urllib.error.HTTPError as error:
            text = error.read()
            try:
                err = json.loads(text)["error"]
                raise KeygateError(
                    error.code, err.get("code", ""), err.get("message", "")
                ) from None
            except (ValueError, KeyError, TypeError):
                raise KeygateError(error.code, "", text[:200].decode(errors="replace")) from None
        return json.loads(text)["data"] if text else {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def content_type(path: Path) -> str:
    name = path.name.lower()
    if name.endswith((".tar.gz", ".tgz")):
        return "application/gzip"
    if name.endswith(".zip"):
        return "application/zip"
    return "application/octet-stream"


def put_file(url: str, path: Path, mime: str) -> None:
    with path.open("rb") as body:
        request = urllib.request.Request(  # noqa: S310 -- Keygate 给的预签名地址
            url,
            data=body,
            method="PUT",
            headers={"Content-Type": mime, "Content-Length": str(path.stat().st_size)},
        )
        try:
            with urllib.request.urlopen(request, timeout=UPLOAD_TIMEOUT):  # noqa: S310
                pass
        except urllib.error.HTTPError as error:
            raise KeygateError(
                error.code, "UPLOAD_FAILED", error.read()[:200].decode(errors="replace")
            ) from None


def find_release(kg: Keygate, product_id: str, version: str, channel: str) -> dict | None:
    offset = 0
    while True:
        page = kg.call(
            "GET", f"/releases?product_id={product_id}&channel={channel}&limit=200&offset={offset}"
        )
        releases = page.get("releases", [])
        for release in releases:
            if release["version"] == version:
                return release
        if len(releases) < page.get("limit", 200):
            return None
        offset += len(releases)


def publish(
    kg: Keygate,
    *,
    product_id: str,
    version: str,
    channel: str,
    notes: str,
    artifacts: dict[str, Path],
    do_publish: bool,
    log=print,
) -> dict:
    release = find_release(kg, product_id, version, channel)
    if release is None:
        release = kg.call(
            "POST",
            "/releases",
            {
                "product_id": product_id,
                "version": version,
                "channel": channel,
                "name": "FileSeek",
                "release_notes": notes,
            },
        )
        log(f"已创建草稿 {version}（{release['id']}）")
    elif release["status"] != "draft":
        raise SystemExit(
            f"{version} 在 Keygate 上已是 {release['status']}，不会改动它。请换一个版本号"
        )
    else:
        log(f"复用草稿 {version}（{release['id']}）")
        kg.call("PATCH", f"/releases/{release['id']}", {"release_notes": notes})

    existing = kg.call("GET", f"/releases/{release['id']}").get("artifacts") or []
    for platform, path in artifacts.items():
        for old in (a for a in existing if a["platform"] == platform):
            kg.call("DELETE", f"/releases/{release['id']}/artifacts/{old['id']}")
            log(f"  {platform}: 删除草稿里的旧文件")
        size, mime, digest = path.stat().st_size, content_type(path), sha256_file(path)
        added = kg.call(
            "POST",
            f"/releases/{release['id']}/artifacts",
            {
                "platform": platform,
                "filename": path.name,
                "content_type": mime,
                "expected_size": size,
            },
        )
        log(f"  {platform}: 上传 {path.name}（{size / 1e6:.1f} MB）")
        put_file(added["upload_url"], path, mime)
        kg.call(
            "POST",
            f"/releases/{release['id']}/artifacts/{added['artifact']['id']}/finalize",
            {"expected_sha256": digest},
        )
        log(f"  {platform}: 已校验 sha256 {digest[:12]}…")

    if do_publish:
        release = kg.call("POST", f"/releases/{release['id']}/actions/publish")
        log(f"已发布 {version}")
    else:
        log("未发布：在 Keygate 后台检查后发布，或加 --publish")
    return release


def parse_artifact(spec: str) -> tuple[str, Path]:
    platform, _, path = spec.partition("=")
    if platform not in PLATFORMS:
        raise SystemExit(f"不支持的平台 {platform!r}，应为 {', '.join(PLATFORMS)}")
    file = Path(path)
    if not file.is_file():
        raise SystemExit(f"找不到 {file}")
    if file.name.endswith(".sig"):
        raise SystemExit(f"{file.name} 是签名文件；上传更新包本身，Keygate 发布时会签名")
    return platform, file


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--channel", default="stable", choices=["stable", "beta", "alpha", "dev"])
    parser.add_argument("--artifact", action="append", default=[], metavar="PLATFORM=PATH")
    parser.add_argument("--publish", action="store_true", help="上传后立即发布")
    parser.add_argument("--dry-run", action="store_true", help="只检查参数和 Keygate 上的状态")
    args = parser.parse_args(argv)

    artifacts = dict(parse_artifact(spec) for spec in args.artifact)
    if not artifacts:
        raise SystemExit("至少需要一个 --artifact")
    config = json.loads(KEYGATE_CONFIG.read_text(encoding="utf-8"))
    api_key = os.environ.get("KEYGATE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("需要环境变量 KEYGATE_API_KEY（releases:write）")
    kg = Keygate(config["base_url"].rstrip("/"), api_key)

    if args.dry_run:
        found = find_release(kg, config["product_id"], args.version, args.channel)
        state = found["status"] if found else "不存在，将创建"
        print(f"Keygate 上 {args.version}（{args.channel}）：{state}")
        for platform, path in artifacts.items():
            print(f"  {platform}: {path.name} {path.stat().st_size / 1e6:.1f} MB")
        return

    try:
        publish(
            kg,
            product_id=config["product_id"],
            version=args.version,
            channel=args.channel,
            notes=args.notes,
            artifacts=artifacts,
            do_publish=args.publish,
        )
    except KeygateError as error:
        sys.exit(f"Keygate 拒绝了请求：{error}")


if __name__ == "__main__":
    main()
