"""jina-clip-v2 加载路径上的两处类型/文件契约。

图片检索要跑起来，这条链上有四个坎，前两个是环境依赖（torchvision、timm，见 pyproject.toml
里的注释），后两个在代码里，就是这里测的：

1. `ensure_model_cached` 必须把 `preprocessor_config.json` 一起落到 tokenizer 目录。
   `AutoImageProcessor.from_pretrained(tokenizer_dir)` 去那个目录找它，缺了就没有
   size/mean/std 可读。这和缺 torchvision 是两个独立的失败，装了包也不会自动好。
2. 图片处理器的输出必须收口成 numpy。`return_tensors="np"` 对这个模型不起作用——
   jina-clip-v2 的处理器是远程代码，直接返回 torch 张量，而 ONNX Runtime 只吃 numpy。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest

from fileseek.features.tasks.infrastructure.embedding.jina_clip_v2 import (
    JinaClipV2Embedding,
    _as_numpy,
)

if TYPE_CHECKING:
    from types import ModuleType


def _load_model_cache() -> ModuleType:
    """按文件加载 model_cache。

    它只依赖 logging/pathlib/huggingface_hub，没有项目内 import，所以不必经过
    `fileseek.shared` 的包初始化。
    """
    path = Path(__file__).resolve().parents[4] / "src/fileseek/shared/utils/model_cache.py"
    spec = importlib.util.spec_from_file_location("_model_cache_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheCachedFileSet:
    """`ensure_model_cached` 下哪些文件。"""

    def test_the_image_processor_config_is_fetched(self, tmp_path: Path) -> None:
        cache = _load_model_cache()
        requested: list[str] = []

        def fake_download(model_name: str, filename: str, cache_dir: str) -> str:
            requested.append(filename)
            source = tmp_path / "hub" / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("{}", encoding="utf-8")
            return str(source)

        cache.hf_hub_download = fake_download  # type: ignore[attr-defined]
        # `ensure_model_cached` 在函数体里 `from huggingface_hub import hf_hub_download`，
        # 所以要替掉源头而不是模块属性。
        import huggingface_hub

        original = huggingface_hub.hf_hub_download
        huggingface_hub.hf_hub_download = fake_download  # type: ignore[assignment]
        try:
            onnx_path, tokenizer_dir = cache.ensure_model_cached(
                "jinaai/jina-clip-v2", tmp_path / "models"
            )
        finally:
            huggingface_hub.hf_hub_download = original  # type: ignore[assignment]

        # 少了它，装上 torchvision 也照样加载失败。
        assert "preprocessor_config.json" in requested
        assert (tokenizer_dir / "preprocessor_config.json").exists()
        assert onnx_path.exists()

    def test_the_tokenizer_files_are_still_fetched(self, tmp_path: Path) -> None:
        """加 preprocessor_config 不能挤掉原来的三件套。"""
        cache = _load_model_cache()

        assert set(cache._MODEL_FILES) >= {
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "preprocessor_config.json",
        }


class TestPixelValuesReachOnnxAsNumpy:
    """`_as_numpy`：处理器给什么都要变成 numpy。"""

    def test_a_torch_tensor_becomes_an_array(self) -> None:
        torch = pytest.importorskip("torch")
        tensor = torch.zeros((1, 3, 512, 512), dtype=torch.float32)

        result = _as_numpy(tensor)

        # 这就是报错现场：`'Tensor' object has no attribute 'astype'`。
        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 3, 512, 512)
        # 下游 `_build_image_inputs` 就是这么喂给 ONNX 的。
        assert result.astype(np.float32, copy=False).dtype == np.float32

    def test_an_array_passes_through_untouched(self) -> None:
        array = np.zeros((2, 3, 512, 512), dtype=np.float32)

        # 处理器哪天真的遵守 `return_tensors="np"` 也不能坏。
        assert _as_numpy(array) is array

    def test_a_tensor_that_requires_grad_still_converts(self) -> None:
        """带梯度的张量不能直接 `.numpy()`，得先 detach。"""
        torch = pytest.importorskip("torch")
        tensor = torch.zeros((1, 3, 8, 8), dtype=torch.float32, requires_grad=True)

        assert isinstance(_as_numpy(tensor), np.ndarray)


class _FakeInput:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeSession:
    """只提供 `get_inputs()` 的假 session，够 `_build_*_inputs` 用。"""

    def __init__(self, *names: str) -> None:
        self._names = names

    def get_inputs(self) -> list[_FakeInput]:
        return [_FakeInput(name) for name in self._names]


class TestBuildingOnnxInputs:
    """构造 ONNX 输入时 numpy 必须在运行期可用。

    `numpy` 曾经只写在 `if TYPE_CHECKING:` 里，而这两个方法在运行期就要 `np.float32` /
    `np.zeros`，于是 `NameError: name 'np' is not defined`。这个错之前被挡住了：同一行的
    `pixel_values.astype` 先抛 AttributeError（处理器给的是 torch 张量），修好类型之后它才露出来。

    这两条不下载模型，纯跑输入构造。
    """

    def test_image_inputs_are_built_without_a_nameerror(self) -> None:
        pixel_values = np.zeros((1, 3, 512, 512), dtype=np.float32)

        inputs = JinaClipV2Embedding._build_image_inputs(
            session=_FakeSession("pixel_values", "input_ids"),
            pixel_values=pixel_values,
        )

        assert inputs["pixel_values"].dtype == np.float32
        # 模型同时要 input_ids，图片推理时喂 dummy。
        assert inputs["input_ids"].shape[0] == 1

    def test_a_model_without_pixel_values_is_refused(self) -> None:
        from fileseek.features.tasks.domain.exceptions import InferenceError

        with pytest.raises(InferenceError, match="pixel_values"):
            JinaClipV2Embedding._build_image_inputs(
                session=_FakeSession("input_ids"),
                pixel_values=np.zeros((1, 3, 8, 8), dtype=np.float32),
            )
