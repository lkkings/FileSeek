"""系统全局配置。

统一管理所有环境变量和配置项，业务代码不得直接使用 os.getenv()。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """系统配置类。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 文件库根路径
    lib_root: Path = Path.home() / "FileSeekLibrary"

    # 数据库配置
    db_path: Path | None = None  # 默认为 lib_root / "metadata.db"

    # NAS 配置
    nas_protocol: str | None = None  # "smb" | "nfs" | "webdav"
    nas_host: str | None = None
    nas_share_path: str | None = None
    nas_username: str | None = None
    nas_password: str | None = None

    # 服务配置
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_prefix: str = "/api/v1"

    # 媒体流配置
    media_chunk_size: int = 1024 * 1024  # 1MB

    # 任务队列配置
    task_poll_interval: float = 2.0  # 秒
    # 已不再生效：导入计算固定在一个模型子进程里串行执行（每多一个进程就多一份模型）。
    # 保留字段是为了不让旧 .env 里的这一项报错。
    task_max_workers: int = 1
    task_max_retries: int = 3
    task_document_batch_size: int = Field(default=32, ge=1)
    task_video_batch_size: int = Field(default=2, ge=1)

    # 关闭时等待在飞任务落地的时限（秒），超时仍在跑的任务放回 queued。
    task_drain_timeout: float = 10.0

    # 模型子进程空闲多少秒后自行退出，把模型内存完整还给系统；0 表示常驻不退出。
    # 进程内卸载模型只能收回约一半内存，且反复卸载会越积越多，所以只能靠进程退出。
    task_worker_idle_timeout: float = Field(default=300.0, ge=0)
    query_worker_idle_timeout: float = Field(default=900.0, ge=0)

    # 向量模型配置 (jina-clip-v2 via ONNX Runtime)
    embedding_provider: Literal["jina-clip-v2"] = "jina-clip-v2"
    embedding_model_name: str = "jinaai/jina-clip-v2"
    embedding_dim: int = 1024  # 模型原生输出维度，未做 Matryoshka 截断
    embedding_model_cache_dir: Path | None = None
    intra_op_num_threads: int | None = None
    inter_op_num_threads: int | None = None

    # 向量索引配置
    vector_store_provider: Literal["chroma"] = "chroma"
    vector_distance_metric: Literal["l2","cosine","ip"] = "cosine"
    vector_db_path: Path | None = None  # 默认为 lib_root / "vectors"

    # 视频处理配置
    video_sample_every_n_frames: int = 30
    video_perceptual_hash_threshold: int = 10  # hamming distance

    # 文档处理配置
    document_chunk_size: int = 4096
    document_overlap: int = 256

    # OCR配置
    ocr_provider: Literal["rapidocr"] = "rapidocr"

    # File classifier label vocabularies
    classifier_document_labels: list[str] = Field(default_factory=lambda: ["document"])
    classifier_video_labels: list[str] = Field(default_factory=lambda: ["video"])
    classifier_image_labels: list[str] = Field(default_factory=lambda: ["photo", "image"])
    classifier_provider: Literal["jina-clip-v2"] = "jina-clip-v2"
    classifier_text_similarity_threshold: float = 0.3
    classifier_image_similarity_threshold: float = 0.3
    classifier_video_similarity_threshold: float = 0.3
    classifier_max_labels: int = 5

    # 回收站文件夹
    recycle_dir: Path | None = None

    temp_dir: Path | None = None

    def __init__(self, **data: Any) -> None:
        """初始化配置。"""
        super().__init__(**data)
        # 设置默认派生路径
        if self.db_path is None:
            db_dir = self.lib_root / ".db"
            db_dir.mkdir(parents=True,exist_ok=True)
            self.db_path = db_dir / "app.db"
        if self.vector_db_path is None:
            self.vector_db_path = self.lib_root / ".vectors"
        if self.embedding_model_cache_dir is None:
            self.embedding_model_cache_dir = self.lib_root / ".models"
        if self.recycle_dir is None:
            self.recycle_dir = self.lib_root / ".recycle"

        if self.temp_dir is None:
            self.temp_dir = self.lib_root / ".temp"


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()
