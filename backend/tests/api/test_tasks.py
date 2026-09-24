"""任务队列 API 用例。

重试走的是 `Task` 的状态机：只有 FAILED 能回到 QUEUED。其他状态的重试请求要被
拒绝，否则一个正在处理的任务会被重置，处理器写回结果时就撞上不合法的状态转换。

任务是入库时自动建的（`AddFileUseCase` 末尾调 `task_manager.create`），没有单独的
"提交向量化"接口。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from tests.api.conftest import API

TASKS = f"{API}/tasks"


def test_adding_a_file_creates_its_vectorization_task(
    client: TestClient, tmp_path: Path
) -> None:
    """入库即建任务：`AddFileUseCase` 末尾会调 `task_manager.create`。

    所以没有单独的"提交向量化"接口——`POST /library/files` 一步到位。
    """
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4\n1 0 obj\n")

    response = client.post(
        f"{API}/library/files",
        json={"folder_id": None, "filename": "report.pdf", "path": str(source)},
    )

    assert response.status_code == 200
    file_id = response.json()["data"]["file_id"]

    tasks = client.get(TASKS).json()["data"]["tasks"]
    assert [task["id"] for task in tasks] == [file_id]
    assert tasks[0]["status"] == "queued"


def test_adding_an_unsupported_file_is_refused(
    client: TestClient, tmp_path: Path
) -> None:
    """认不出类型的文件不入库，也就不会产生任务。"""
    source = tmp_path / "data.raw"
    source.write_bytes(b"\x00\x01\x02")

    response = client.post(
        f"{API}/library/files",
        json={"folder_id": None, "filename": "data.raw", "path": str(source)},
    )

    assert response.json()["status"] == "error"
    assert client.get(TASKS).json()["data"]["tasks"] == []


def test_adding_a_file_rejects_missing_fields(client: TestClient) -> None:
    response = client.post(f"{API}/library/files", json={})

    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_list_tasks_empty(client: TestClient) -> None:
    body = client.get(TASKS).json()

    assert body["status"] == "success"
    assert body["data"]["tasks"] == []
    # 计数四个状态都在，前端不用自己补零。
    assert body["data"]["counts"] == {
        "queued": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
    }


def test_list_tasks_shape(client: TestClient, seed: Any) -> None:
    seed.task(
        task_id="t_1",
        source_path="/seeded/a.pdf",
        status="failed",
        progress=50,
        stage="extracted",
        completed_stages='["moved", "extracted"]',
        error_message="boom",
    )

    task = client.get(TASKS).json()["data"]["tasks"][0]

    assert task["id"] == "t_1"
    assert task["source_path"] == "/seeded/a.pdf"
    assert task["status"] == "failed"
    assert task["progress"] == 50
    assert task["stage"] == "extracted"
    # `TaskResponse` 只有 7 个字段：completed_stages / priority 不在响应里。
    assert "completed_stages" not in task
    assert "priority" not in task
    assert task["error_message"] == "boom"


def test_list_tasks_counts_by_status(client: TestClient, seed: Any) -> None:
    seed.task(task_id="t_1", status="queued")
    seed.task(task_id="t_2", status="queued")
    seed.task(task_id="t_3", status="completed")
    seed.task(task_id="t_4", status="failed")

    counts = client.get(TASKS).json()["data"]["counts"]

    assert counts == {"queued": 2, "processing": 0, "completed": 1, "failed": 1}


def test_list_tasks_filters_by_status(client: TestClient, seed: Any) -> None:
    seed.task(task_id="t_1", status="queued")
    seed.task(task_id="t_2", status="failed")

    body = client.get(TASKS, params={"status": "failed"}).json()

    assert [t["id"] for t in body["data"]["tasks"]] == ["t_2"]
    # 过滤只影响列表，counts 始终是全局的。
    assert body["data"]["counts"]["queued"] == 1


def test_list_tasks_pagination(client: TestClient, seed: Any) -> None:
    for index in range(5):
        seed.task(task_id=f"t_{index}", source_path=f"/seeded/{index}.pdf")

    body = client.get(TASKS, params={"page": 1, "page_size": 2}).json()

    assert len(body["data"]["tasks"]) == 2
    assert body["data"]["pagination"] == {"page": 1, "page_size": 2, "total": 5}


def test_list_tasks_rejects_bad_pagination(client: TestClient) -> None:
    assert client.get(TASKS, params={"page": 0}).status_code == 422
    assert client.get(TASKS, params={"page_size": 101}).status_code == 422


def test_retry_failed_task_requeues_it(client: TestClient, seed: Any) -> None:
    seed.task(task_id="t_1", status="failed", error_message="boom", progress=40)

    response = client.post(f"{TASKS}/t_1/retry")

    assert response.status_code == 200
    task = response.json()["data"]
    assert task["status"] == "queued"
    # 重试要清掉上次的错误，否则界面上一个排队中的任务还挂着旧报错。
    assert task["error_message"] is None


def test_retry_persists_new_status(client: TestClient, seed: Any) -> None:
    seed.task(task_id="t_1", status="failed", error_message="boom")

    client.post(f"{TASKS}/t_1/retry")

    listed = client.get(TASKS).json()["data"]["tasks"][0]
    assert listed["status"] == "queued"


def test_retry_queued_task_is_refused(client: TestClient, seed: Any) -> None:
    """只有 FAILED 能重试，见模块 docstring。"""
    seed.task(task_id="t_1", status="queued")

    body = client.post(f"{TASKS}/t_1/retry").json()

    assert body["status"] == "error"
    assert body["error"]


def test_retry_completed_task_is_refused(client: TestClient, seed: Any) -> None:
    seed.task(task_id="t_1", status="completed", progress=100)

    body = client.post(f"{TASKS}/t_1/retry").json()

    assert body["status"] == "error"


def test_retry_missing_task_returns_error_envelope(client: TestClient) -> None:
    body = client.post(f"{TASKS}/nope/retry").json()

    assert body["status"] == "error"
    assert "nope" in body["error"]
