## Why

backend 的 `.venv` 约 1527 MB，其中 torch 一条链（torch、torchvision、timm、sympy、networkx）约 630 MB，但代码里没有任何 `import torch`：推理全走 ONNX Runtime，torch 只是 jina-clip-v2 远程图片预处理代码的连带依赖。release 版在首次启动时按 `uv.lock` 逐个下载 wheel，这些用不上的包直接拉长了用户的首次下载和安装时间。

## What Changes

- 删除代码中没有使用的依赖：`faiss-cpu`、`sentence-transformers`（连带 scikit-learn）、`zeroconf`、`keyring`、`smbprotocol`、`webdavclient3`。`keyring` 本应在 `commercial-licensing-and-updates` 的 5.8 中删除，这里补上。
- 用 PIL + numpy 自行实现 jina-clip-v2 推理时的图片预处理，不再加载远程 `JinaCLIPImageProcessor`；删除 `torch`、`torchvision`、`timm`。
- 用 `tokenizers` 直接加载 `tokenizer.json`，替代 `transformers.AutoTokenizer`；删除 `transformers`，也不再需要 `trust_remote_code`。
- 用 numpy 实现视频关键帧去重所需的 phash；删除 `imagehash`（连带 scipy、pywavelets）。
- 去掉 `tests/conftest.py` 里为 torch 和 faiss 的 libomp 冲突设置的 `KMP_DUPLICATE_LIB_OK`。
- 预处理和 phash 改写后，向量和哈希值可能与旧实现有极小差异。这些差异视为可接受，不要求重建现有索引。

不在本次范围：chromadb（裁剪传递依赖或替换存储层）、rapidocr/OpenCV。`onnx` 保留：文本塔子图（约 563 MB）继续在首次加载时从联合模型现场抽取，比随模型分发更省下载量。

## Capabilities

### New Capabilities
- `backend-dependencies`：约束 backend 运行时依赖集合。运行时不得依赖 PyTorch 系列和 transformers，图片和文本向量化只用 ONNX Runtime 及轻量预处理。

### Modified Capabilities
（无）

## Impact

- `backend/pyproject.toml`、`backend/uv.lock`：移除上述依赖，新增 `tokenizers` 直接依赖。
- `backend/src/fileseek/infrastructure/embedding/jina_clip_v2.py`：替换 tokenizer 和图片处理器的加载与调用。
- `backend/src/fileseek/shared/utils/model_cache.py`：更新随行文件注释（不再有 torchvision 前提）；文本塔子图逻辑不变。
- `backend/src/fileseek/features/tasks/infrastructure/file_processor/video_sampler.py`：换用自实现的 phash。
- `desktop/src-tauri/runtime-sources/*.json`：wheel 列表随 `uv.lock` 用 `release/build_sources.py` 重新生成；模型文件清单不变。
- `backend/tests/conftest.py` 及 embedding、video sampler 相关测试。
- 预计 `.venv` 体积减少约 830 MB，release 首次下载量相应减少。
