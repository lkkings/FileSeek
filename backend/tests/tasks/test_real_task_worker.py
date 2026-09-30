"""真实导入子进程入口：`run_task_worker` 在子进程里自己装配 parser / embedding / classifier。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from fileseek.config.settings import Settings
from fileseek.features.tasks.application.compute import TaskResult, TaskSpec
from fileseek.features.tasks.domain.ports import ClassifierLabelSnapshot
from fileseek.features.tasks.infrastructure.worker import (
    TaskWorkerClient,
    build_task_worker_config,
    run_task_worker,
)
from fileseek.shared.domain.file_types import FileType
from fileseek.shared.infrastructure.worker import WorkerHandle

MODEL_CACHE = Path.home() / ".cache" / "fileseek" / "models"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not (MODEL_CACHE / "model_quantized.onnx").exists(),
        reason="需要本地已缓存的 jina-clip-v2 模型",
    ),
]


def test_real_worker_computes_txt_document(tmp_path: Path) -> None:
    temp = tmp_path / "note.txt"
    temp.write_text(
        "FileSeek 是一个本地文件语义检索工具。\n它支持文档、图片和视频。\n",
        encoding="utf-8",
    )
    settings = Settings(lib_root=tmp_path, embedding_model_cache_dir=MODEL_CACHE)
    client = TaskWorkerClient(
        WorkerHandle("test-real-task-worker", run_task_worker, build_task_worker_config(settings))
    )
    snapshot = ClassifierLabelSnapshot(
        document_labels=("文档",), image_labels=(), video_labels=(), version="v1"
    )
    spec = TaskSpec(
        task_id="t1",
        file_id="f1",
        file_type=FileType.TXT,
        file_path=str(temp),
        metadata={"temp_path": str(temp), **snapshot.as_metadata()},
    )
    try:
        client.submit(spec)
        deadline = time.monotonic() + 300
        result: object = None
        while time.monotonic() < deadline:
            event = client.poll()
            if isinstance(event, (TaskResult, BaseException)):
                result = event
                break
            time.sleep(0.05)
    finally:
        client.shutdown()

    assert isinstance(result, TaskResult), result
    assert len(result.chunks) >= 1
    assert result.vectors.shape == (len(result.chunks), 1024)
    assert not temp.exists()
