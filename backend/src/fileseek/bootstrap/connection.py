"""连接文件的发布与清理。

服务启动时把 `{port, token}` 写到配置目录，客户端读它才知道该连哪个端口、
带什么 token。桌面端（Rust 侧 `sidecar.rs`）靠两件事判断后端就绪：连接文件的
mtime 变新，以及文件能被解析出一个非空 token。

所以写入必须是原子的：先写临时文件再 rename。直接往目标文件里写，轮询的一方
会读到半个 JSON，把它当成"还没好"反复重试（运气不好则解析失败直接报错）。

token 每次启动重新生成，上一次运行泄露出去的 token 不会一直有效。
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import stat
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_token() -> str:
    """生成本次运行的鉴权 token。"""
    return secrets.token_urlsafe(32)


def publish(connection_file: Path, port: int, token: str) -> None:
    """把 `{port, token}` 原子地写入连接文件。

    Args:
        connection_file: 目标路径，通常取自 `AppPaths.resolve().connection_file`
        port: 服务实际监听的端口
        token: 本次运行的鉴权 token
    """
    connection_file.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps({"port": port, "token": token})

    # 同目录下的临时文件：rename 要求同一文件系统才具备原子性。
    temp_file = connection_file.with_name(f"{connection_file.name}.{os.getpid()}.tmp")
    try:
        temp_file.write_text(payload, encoding="utf-8")
        # token 是凭据，只给文件属主读写。rename 会保留这里设的权限位，
        # 所以要在换到正式位置之前设好。
        temp_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        temp_file.replace(connection_file)
    except OSError:
        temp_file.unlink(missing_ok=True)
        raise
    logger.info("连接文件已发布: %s (port=%d)", connection_file, port)
    logger.info("认证 token: %s", token)


def revoke(connection_file: Path) -> None:
    """删除连接文件。

    关闭时调用：留下一个指向已经没人监听的端口的文件，客户端会一直连不上却
    以为后端在跑。删不掉不算致命错误——只记一条日志，不要因此让关闭流程失败。
    """
    try:
        connection_file.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("连接文件清理失败 %s: %s", connection_file, exc)
    else:
        logger.info("连接文件已清理: %s", connection_file)
