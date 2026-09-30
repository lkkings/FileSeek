"""jina-clip-v2 模型文件缓存管理。

负责将 ONNX 模型和 tokenizer 文件下载到本地缓存目录，
后续加载均从本地文件读取，不依赖网络。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 量化后的 ONNX 模型（约 874MB），相比 fp32 版本（约 3.5GB）显著减小下载体积。
_ONNX_FILENAME = "onnx/model_quantized.onnx"

# 落到同一个目录里的随行文件。
#
# `AutoTokenizer` 和 `AutoImageProcessor` 都是 `from_pretrained(tokenizer_dir)`，各自去这个
# 目录里找自己那份配置。少了 preprocessor_config.json，图片处理器就没有 size/mean/std 可读，
# 报的是"找不到 preprocessor config"，和缺 torchvision 是两回事——两个都得满足。
_MODEL_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "preprocessor_config.json",
)


def ensure_model_cached(model_name: str, cache_dir: Path) -> tuple[Path, Path]:
    """确保模型文件已缓存到本地，返回 (onnx_model_path, tokenizer_dir)。

    首次调用时从 Hugging Face 下载并缓存；后续调用直接复用缓存，不产生网络请求。

    Args:
        model_name: Hugging Face 模型名称（如 "jinaai/jina-clip-v2"）
        cache_dir: 本地缓存根目录

    Returns:
        (onnx 模型文件路径, tokenizer 文件所在目录)
    """
    from huggingface_hub import hf_hub_download

    cache_dir.mkdir(parents=True, exist_ok=True)
    tokenizer_dir = cache_dir / "tokenizer"
    tokenizer_dir.mkdir(parents=True, exist_ok=True)

    onnx_path = cache_dir / "model_quantized.onnx"
    if not onnx_path.exists():
        logger.info("下载 %s 的 ONNX 模型（约 874MB），首次加载可能耗时较长", model_name)
        downloaded = hf_hub_download(
            model_name, _ONNX_FILENAME, cache_dir=str(cache_dir / "hf_cache")
        )
        onnx_path.write_bytes(Path(downloaded).read_bytes())

    for filename in _MODEL_FILES:
        target = tokenizer_dir / filename
        if target.exists():
            continue
        downloaded = hf_hub_download(model_name, filename, cache_dir=str(cache_dir / "hf_cache"))
        target.write_bytes(Path(downloaded).read_bytes())

    return onnx_path, tokenizer_dir


# 文本塔子图的输入和输出。官方只发布了文本、图片两座塔打包在一张图里的联合模型；
# 查询只用得到文本塔，把它单独抽出来能少加载一半权重（实测 874MB -> 537MB），
# 而两座塔在图内互不依赖，抽出来的子图输出与联合模型逐位一致。
_TEXT_GRAPH_INPUTS = ["input_ids"]
_TEXT_GRAPH_OUTPUTS = ["l2norm_text_embeddings"]


def text_model_path(onnx_path: Path) -> Path:
    """文本塔子图的位置：和联合模型放在一起。

    `model_quantized.onnx` -> `model_quantized.text.onnx`。
    """
    return onnx_path.with_suffix(".text.onnx")


def ensure_text_model(onnx_path: Path) -> Path | None:
    """确保文本塔子图已生成，返回其路径；生成失败返回 None，调用方回退到联合模型。

    首次调用时从联合模型抽取，约 1~2 秒。先写临时文件再 rename：抽取途中进程被杀掉，
    也不会留下一个半截的子图让下次加载失败。
    """
    target = text_model_path(onnx_path)
    if target.exists():
        return target
    tmp = target.with_suffix(".onnx.tmp")
    try:
        import onnx
        from onnx.utils import Extractor

        model = onnx.load(str(onnx_path))
        sub = Extractor(model).extract_model(_TEXT_GRAPH_INPUTS, _TEXT_GRAPH_OUTPUTS)
        onnx.save(sub, str(tmp))
        tmp.replace(target)
    except Exception:
        logger.warning("文本塔子图生成失败，将使用联合模型: %s", onnx_path, exc_info=True)
        tmp.unlink(missing_ok=True)
        return None
    logger.info("已生成文本塔子图: %s", target)
    return target
