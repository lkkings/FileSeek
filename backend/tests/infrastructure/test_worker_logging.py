from __future__ import annotations

import logging
from pathlib import Path

from tests.infrastructure.worker_targets import log_worker

from fileseek.bootstrap.logging_config import configure_logging
from fileseek.config.settings import Settings
from fileseek.features.tasks.infrastructure.worker import build_task_worker_config
from fileseek.shared.infrastructure.worker import WorkerHandle


def test_worker_logs_go_to_service_log_file_with_process_name(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    configure_logging(log_file=log_file)
    try:
        worker = WorkerHandle(
            "fileseek-task-worker",
            log_worker,
            build_task_worker_config(Settings(lib_root=tmp_path)),
        )
        worker.ensure_started()
        assert worker.conn.poll(30)
        assert worker.conn.recv() == "done"
        worker.terminate()

        text = log_file.read_text(encoding="utf-8")
        assert "[fileseek-task-worker] fileseek.worker.test: hello-from-worker" in text
    finally:
        configure_logging()
        logging.getLogger().handlers.clear()
