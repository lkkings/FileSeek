from __future__ import annotations

import logging
import threading
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, cast
import numpy as np

from fileseek.shared.domain.exceptions import (
    InferenceError,
    ModelLoadError,
)
from fileseek.shared.utils.model_cache import (
    ensure_model_cached,
)
from fileseek.infrastructure.embedding.base import EmbeddingPort

if TYPE_CHECKING:
    import onnxruntime as ort
    from PIL import Image
    from transformers import (
        AutoImageProcessor,
        PreTrainedTokenizerBase,
    )


logger = logging.getLogger(__name__)


def _as_numpy(pixel_values: object) -> np.ndarray:
    """把图片处理器的输出统一成 numpy 数组。

    `return_tensors="np"` 对这个模型不起作用：jina-clip-v2 用 auto_map 指向
    `jinaai/jina-clip-implementation` 的 `JinaCLIPImageProcessor`，那份远程代码里的
    transform 直接返回 torch 张量，不看这个参数。而下游 `_build_image_inputs` 要调
    `.astype()`、ONNX Runtime 也只吃 numpy，于是报 `'Tensor' object has no attribute
    'astype'`。类型在这里收口，推理侧就不必知道处理器到底给的是什么。
    """
    # 不在模块顶层 import torch：这个文件其余部分是纯 ONNX 路径，torch 只是远程预处理代码
    # 的连带依赖，没必要为了一个 isinstance 把它拉进导入链。
    detach = getattr(pixel_values, "detach", None)
    if detach is not None:
        return cast("np.ndarray", detach().cpu().numpy())

    return cast("np.ndarray", pixel_values)


class JinaClipV2Embedding(EmbeddingPort):
    """Jina CLIP V2 ONNX 向量化实现。

    该类属于 Infrastructure 层，不应该被 Domain 层直接依赖。

    职责：

    1. 管理 Jina CLIP V2 模型的懒加载。
    2. 管理 tokenizer。
    3. 管理 image processor。
    4. 使用 ONNX Runtime 执行推理。
    5. 将模型异常转换为领域定义的异常。
    6. 提供文本和图片统一的 embedding 能力。

    不负责：

    - 文件解析
    - 文本切 chunk
    - OCR
    - 视频抽帧
    - 向量数据库存储
    - ChromaDB 操作
    - 业务任务调度
    """

    DEFAULT_MODEL_NAME = "jinaai/jina-clip-v2"

    DEFAULT_CACHE_DIR = (
        Path.home() / ".cache" / "fileseek" / "models"
    )

    DEFAULT_DIMENSION = 1024

    QUERY_INSTRUCTION = (
        "Represent the query for retrieving evidence documents: "
    )

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        cache_dir: Path | None = None,
        *,
        intra_op_num_threads: int | None = None,
        inter_op_num_threads: int | None = None,
    ) -> None:
        """初始化 Jina CLIP V2 embedding adapter。

        Args:
            model_name:
                Hugging Face 模型名称。

            cache_dir:
                模型缓存目录。

            intra_op_num_threads:
                ONNX Runtime 单个算子内部使用的线程数。
                None 表示使用 ONNX Runtime 默认值。

            inter_op_num_threads:
                ONNX Runtime 算子之间使用的线程数。
                None 表示使用 ONNX Runtime 默认值。
        """
        self._model_name = model_name
        self._cache_dir = cache_dir or self.DEFAULT_CACHE_DIR

        self._intra_op_num_threads = intra_op_num_threads
        self._inter_op_num_threads = inter_op_num_threads

        self._session: ort.InferenceSession | None = None
        self._tokenizer: PreTrainedTokenizerBase | None = None
        self._image_processor: AutoImageProcessor | None = None

        self._load_lock = threading.Lock()

        self._dimension = self.DEFAULT_DIMENSION

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dimension(self) -> int:
        """返回 embedding 维度。"""
        return self._dimension

    def embed_text(
        self,
        texts: str | list[str],
        *,
        query: bool = False,
    ) -> list[list[float]]:
        """批量生成文本 embedding。

        Args:
            texts:
                文本列表。

            query:
                是否作为检索 Query 处理。
                True 时使用 Jina retrieval.query instruction。

        Returns:
            与 texts 一一对应的 1024 维向量。
        """
        texts = [texts] if isinstance(texts,str) else texts
        self._validate_texts(texts)

        session, tokenizer, _ = self._ensure_loaded()

        prepared_texts = self._prepare_texts(
            texts,
            query=query,
        )

        try:
            encoded = tokenizer(
                prepared_texts,
                padding=True,
                truncation=True,
                max_length=self._get_max_sequence_length(tokenizer),
                return_tensors="np",
            )

            input_ids = encoded["input_ids"]

            outputs = self._run_text_inference(
                session=session,
                input_ids=input_ids,
            )

            return self._to_embedding_list(outputs)

        except Exception as exc:
            logger.exception(
                "Jina CLIP V2 文本向量化失败，batch_size=%d",
                len(texts),
            )

            raise InferenceError(
                f"文本向量化推理失败: {exc}"
            ) from exc

    def embed_image(
        self,
        images: bytes | list[bytes],
    ) -> list[list[float]]:
        """批量生成图片 embedding。

        Args:
            images:
                图片二进制数据列表。

        Returns:
            与 images 一一对应的 1024 维向量。
        """
        images = [images] if isinstance(images,bytes) else images
        self._validate_images(images)

        session, _, image_processor = self._ensure_loaded()

        try:
            pil_images = [
                self._load_image(image)
                for image in images
            ]

            pixel_values = _as_numpy(
                image_processor(
                    pil_images,
                    return_tensors="np",
                )["pixel_values"]
            )

            outputs = self._run_image_inference(
                session=session,
                pixel_values=pixel_values,
            )

            return self._to_embedding_list(outputs)

        except InferenceError:
            raise

        except Exception as exc:
            logger.exception(
                "Jina CLIP V2 图片向量化失败，batch_size=%d",
                len(images),
            )

            raise InferenceError(
                f"图片向量化推理失败: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _ensure_loaded(
        self,
    ) -> tuple[
        ort.InferenceSession,
        PreTrainedTokenizerBase,
        AutoImageProcessor,
    ]:
        """确保模型资源已经加载。

        使用 double-check locking：
        正常情况下无需获取锁；
        首次加载时保证只有一个线程执行模型初始化。
        """
        session = self._session
        tokenizer = self._tokenizer
        image_processor = self._image_processor

        if (
            session is not None
            and tokenizer is not None
            and image_processor is not None
        ):
            return session, tokenizer, image_processor

        with self._load_lock:
            session = self._session
            tokenizer = self._tokenizer
            image_processor = self._image_processor

            if (
                session is not None
                and tokenizer is not None
                and image_processor is not None
            ):
                return session, tokenizer, image_processor

            try:
                session, tokenizer, image_processor = (
                    self._load_resources()
                )

                # 所有资源成功以后再一次性提交状态。
                self._session = session
                self._tokenizer = tokenizer
                self._image_processor = image_processor

                return session, tokenizer, image_processor

            except ModelLoadError:
                raise

            except Exception as exc:
                logger.exception(
                    "加载 Jina CLIP V2 模型失败: %s",
                    self._model_name,
                )

                raise ModelLoadError(
                    f"加载模型 {self._model_name} 失败: {exc}"
                ) from exc

    def _load_resources(
        self,
    ) -> tuple[
        ort.InferenceSession,
        PreTrainedTokenizerBase,
        AutoImageProcessor,
    ]:
        """加载 ONNX Session、Tokenizer 和 ImageProcessor。

        注意：

        这里使用局部变量加载所有资源，
        全部成功以后才由 _ensure_loaded() 提交到实例状态。
        """
        import onnxruntime as ort
        from transformers import (
            AutoImageProcessor,
            AutoTokenizer,
        )

        onnx_path, tokenizer_dir = ensure_model_cached(
            self._model_name,
            self._cache_dir,
        )

        session_options = self._build_session_options()

        session = ort.InferenceSession(
            str(onnx_path),
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )

        tokenizer = AutoTokenizer.from_pretrained(
            str(tokenizer_dir),
            trust_remote_code=True,
        )

        image_processor = AutoImageProcessor.from_pretrained(
            str(tokenizer_dir),
            trust_remote_code=True,
        )

        self._validate_model_outputs(session)

        return (
            session,
            tokenizer,
            image_processor,
        )

    def _build_session_options(self) -> ort.SessionOptions:
        """创建 ONNX Runtime SessionOptions。"""
        import onnxruntime as ort

        options = ort.SessionOptions()

        if self._intra_op_num_threads is not None:
            if self._intra_op_num_threads <= 0:
                raise ValueError(
                    "intra_op_num_threads 必须大于 0"
                )

            options.intra_op_num_threads = (
                self._intra_op_num_threads
            )

        if self._inter_op_num_threads is not None:
            if self._inter_op_num_threads <= 0:
                raise ValueError(
                    "inter_op_num_threads 必须大于 0"
                )

            options.inter_op_num_threads = (
                self._inter_op_num_threads
            )

        return options

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _run_text_inference(
        self,
        *,
        session: ort.InferenceSession,
        input_ids: np.ndarray,
    ) -> np.ndarray:
        """执行文本 ONNX 推理。"""
        inputs = self._build_text_inputs(
            session=session,
            input_ids=input_ids,
        )

        outputs = session.run(
            None,
            inputs,
        )

        return self._extract_text_embedding(
            session=session,
            outputs=outputs,
        )

    def _run_image_inference(
        self,
        *,
        session: ort.InferenceSession,
        pixel_values: np.ndarray,
    ) -> np.ndarray:
        """执行图片 ONNX 推理。"""
        inputs = self._build_image_inputs(
            session=session,
            pixel_values=pixel_values,
        )

        outputs = session.run(
            None,
            inputs,
        )

        return self._extract_image_embedding(
            session=session,
            outputs=outputs,
        )

    # ------------------------------------------------------------------
    # ONNX input/output
    # ------------------------------------------------------------------

    @staticmethod
    def _build_text_inputs(
        *,
        session: ort.InferenceSession,
        input_ids: np.ndarray,
    ) -> dict[str, np.ndarray]:
        """构建文本推理输入。

        Jina CLIP V2 当前 ONNX 模型需要 input_ids 和 pixel_values。
        对文本推理时，为 pixel_values 提供 dummy tensor。

        这里不直接硬编码 input name，
        而是根据 ONNX graph 的输入名称进行检查。
        """
        input_names = {
            item.name
            for item in session.get_inputs()
        }

        if "input_ids" not in input_names:
            raise InferenceError(
                "ONNX 模型缺少 input_ids 输入"
            )

        inputs: dict[str, np.ndarray] = {
            "input_ids": input_ids.astype(
                np.int64,
                copy=False,
            ),
        }

        if "pixel_values" in input_names:
            batch_size = input_ids.shape[0]

            inputs["pixel_values"] = np.zeros(
                (
                    batch_size,
                    3,
                    512,
                    512,
                ),
                dtype=np.float32,
            )

        return inputs

    @staticmethod
    def _build_image_inputs(
        *,
        session: ort.InferenceSession,
        pixel_values: np.ndarray,
    ) -> dict[str, np.ndarray]:
        """构建图片推理输入。"""
        input_names = {
            item.name
            for item in session.get_inputs()
        }

        if "pixel_values" not in input_names:
            raise InferenceError(
                "ONNX 模型缺少 pixel_values 输入"
            )

        inputs: dict[str, np.ndarray] = {
            "pixel_values": pixel_values.astype(
                np.float32,
                copy=False,
            ),
        }

        if "input_ids" in input_names:
            batch_size = pixel_values.shape[0]

            inputs["input_ids"] = np.zeros(
                (
                    batch_size,
                    1,
                ),
                dtype=np.int64,
            )

        return inputs

    @staticmethod
    def _extract_text_embedding(
        *,
        session: ort.InferenceSession,
        outputs: list[np.ndarray],
    ) -> np.ndarray:
        """从 ONNX 输出中提取文本 embedding。"""
        output_names = [
            output.name
            for output in session.get_outputs()
        ]

        # 优先寻找明确命名的归一化 embedding。
        preferred_names = (
            "l2norm_text_embeddings",
            "text_embeddings",
        )

        for name in preferred_names:
            if name in output_names:
                index = output_names.index(name)
                return cast(
                    "np.ndarray",
                    outputs[index],
                )

        # Jina 官方 ONNX 示例当前输出顺序：
        #
        # 0: text embeddings
        # 1: image embeddings
        # 2: normalized text embeddings
        # 3: normalized image embeddings
        #
        # 因此优先使用第三个输出。
        if len(outputs) >= 3:
            return cast(
                "np.ndarray",
                outputs[2],
            )

        raise InferenceError(
            "无法从 ONNX 输出中找到文本 embedding"
        )

    @staticmethod
    def _extract_image_embedding(
        *,
        session: ort.InferenceSession,
        outputs: list[np.ndarray],
    ) -> np.ndarray:
        """从 ONNX 输出中提取图片 embedding。"""
        output_names = [
            output.name
            for output in session.get_outputs()
        ]

        preferred_names = (
            "l2norm_image_embeddings",
            "image_embeddings",
        )

        for name in preferred_names:
            if name in output_names:
                index = output_names.index(name)
                return cast(
                    "np.ndarray",
                    outputs[index],
                )

        # Jina 官方 ONNX 示例当前输出顺序：
        #
        # 0: text embeddings
        # 1: image embeddings
        # 2: normalized text embeddings
        # 3: normalized image embeddings
        if len(outputs) >= 4:
            return cast(
                "np.ndarray",
                outputs[3],
            )

        raise InferenceError(
            "无法从 ONNX 输出中找到图片 embedding"
        )

    @staticmethod
    def _to_embedding_list(
        embeddings: np.ndarray,
    ) -> list[list[float]]:
        """将 NumPy embedding 转换成纯 Python 数据。"""
        if embeddings.ndim != 2:
            raise InferenceError(
                f"embedding 输出维度异常: {embeddings.shape}"
            )

        if embeddings.shape[1] <= 0:
            raise InferenceError(
                f"embedding 维度异常: {embeddings.shape}"
            )

        return embeddings.astype(
            "float32",
            copy=False,
        ).tolist()

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------

    @classmethod
    def _prepare_texts(
        cls,
        texts: list[str],
        *,
        query: bool,
    ) -> list[str]:
        """准备文本输入。"""
        if not query:
            return texts

        return [
            cls.QUERY_INSTRUCTION + text
            for text in texts
        ]

    @staticmethod
    def _get_max_sequence_length(
        tokenizer: PreTrainedTokenizerBase,
    ) -> int:
        """从 tokenizer 获取最大序列长度。"""
        max_length = tokenizer.model_max_length

        # 某些 tokenizer 在没有真实限制时会返回极大值。
        # 这种情况下不主动设置一个虚假的固定长度。
        if max_length is None:
            return 8192

        if max_length > 1_000_000:
            return 8192

        return int(max_length)

    @staticmethod
    def _validate_texts(
        texts: list[str],
    ) -> None:
        """校验文本输入。"""
        if not isinstance(texts, list):
            raise TypeError(
                "texts 必须是 list[str]"
            )

        if not texts:
            raise ValueError(
                "texts 不能为空"
            )

        for index, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(
                    f"texts[{index}] 必须是 str"
                )

            if not text.strip():
                raise ValueError(
                    f"texts[{index}] 不能为空字符串"
                )

    # ------------------------------------------------------------------
    # Image
    # ------------------------------------------------------------------

    @staticmethod
    def _load_image(
        data: bytes,
    ) -> Image.Image:
        """从 bytes 加载图片。"""
        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(BytesIO(data)) as image:
                return image.convert("RGB")

        except (
            OSError,
            ValueError,
            UnidentifiedImageError,
        ) as exc:
            raise InferenceError(
                f"无法解析图片: {exc}"
            ) from exc

    @staticmethod
    def _validate_images(
        images: list[bytes],
    ) -> None:
        """校验图片输入。"""
        if not isinstance(images, list):
            raise TypeError(
                "images 必须是 list[bytes]"
            )

        if not images:
            raise ValueError(
                "images 不能为空"
            )

        for index, image in enumerate(images):
            if not isinstance(image, bytes):
                raise TypeError(
                    f"images[{index}] 必须是 bytes"
                )

            if not image:
                raise ValueError(
                    f"images[{index}] 不能为空"
                )

    # ------------------------------------------------------------------
    # Model validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_model_outputs(
        session: ort.InferenceSession,
    ) -> None:
        """校验 ONNX 模型是否符合当前 Adapter 预期。"""
        input_names = {
            item.name
            for item in session.get_inputs()
        }

        if "input_ids" not in input_names:
            raise ModelLoadError(
                "Jina CLIP ONNX 模型缺少 input_ids 输入"
            )

        if "pixel_values" not in input_names:
            raise ModelLoadError(
                "Jina CLIP ONNX 模型缺少 pixel_values 输入"
            )

        if len(session.get_outputs()) < 3:
            raise ModelLoadError(
                "Jina CLIP ONNX 模型输出数量异常"
            )
