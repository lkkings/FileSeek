## 1. 生成对照基准（删依赖之前，用旧实现）

- [x] 1.1 写一次性脚本 `backend/scripts/make_parity_fixtures.py`：按固定种子生成覆盖不同尺寸、长宽比（含奇数边和极端长宽比）和模式（RGB/L/RGBA/P）的测试图，用当前 `AutoImageProcessor` 产出 `pixel_values`。验证：`tests/fixtures/parity/image_preprocess.npz` 生成，且小于 2 MB（必要时缩小 size 参数之外的样本数）
- [x] 1.2 同一脚本用当前 `AutoTokenizer`（`truncation=True, max_length=8194`）对中英文、空白、特殊字符和超过 77 及超过 8194 token 的文本分词。验证：`tests/fixtures/parity/token_ids.json` 生成，至少一条记录长度大于 77
- [x] 1.3 同一脚本用 `imagehash.phash` 计算一组合成帧（纯色、渐变、噪声、平移后的同图）的哈希。验证：`tests/fixtures/parity/phash.json` 生成
- [x] 1.4 模型已缓存时，再用旧实现为几张测试图生成图片向量。验证：`tests/fixtures/parity/image_embeddings.npz` 生成（只在本地有模型时生成，`slow` 测试使用）

## 2. 图片预处理

- [x] 2.1 新建 `infrastructure/embedding/clip_preprocess.py`，按 design 第 1 节实现读取配置、缩放、中心裁剪、归一化、转 CHW，不支持的配置抛 `ModelLoadError`。验证：新增单测对比 1.1 的基准，最大绝对误差 < 0.05；不支持的 `resize_mode` 用例抛错
- [x] 2.2 `jina_clip_v2.py` 改用该预处理器，删除 `_as_numpy` 和 `AutoImageProcessor`。验证：`tests/infrastructure/test_jina_clip_v2_embedding.py` 通过，`text_only` 模式下预处理器仍为 None

## 3. 分词

- [x] 3.1 新建 tokenizer 包装（基于 `tokenizers.Tokenizer.from_file`），在加载时关闭 padding，并把截断覆盖为 `model_max_length`，从 `tokenizer_config.json` 读取 `pad_token`。验证：新增单测对比 1.2 的基准，token id 全部完全相等；有用例断言超过 77 个 token 的文本没被截断
- [x] 3.2 `jina_clip_v2.py` 改用该包装，删除 `AutoTokenizer`、`trust_remote_code` 和 transformers 类型注解。验证：`grep -n transformers src/` 无结果；`test_jina_clip_v2_embedding.py`、`test_text_model.py` 通过

## 4. 感知哈希

- [x] 4.1 新建 `file_processor/perceptual_hash.py`，按 design 第 3 节实现，支持用 `-` 计算汉明距离。验证：新增单测对比 1.3 的基准，每对汉明距离 ≤ 2；相同帧的距离为 0
- [x] 4.2 `video_sampler.py` 改用它，删除 `import imagehash`。验证：video sampler 相关测试通过

## 5. 依赖与发布清单

- [x] 5.1 修改 `backend/pyproject.toml`：删除 torch、torchvision、timm、transformers、sentence-transformers、faiss-cpu、imagehash、zeroconf、keyring、smbprotocol、webdavclient3 及 torchvision/timm 的注释，新增 `tokenizers==0.23.2`，然后 `uv lock && uv sync`。验证：`uv tree --frozen` 的非 dev 闭包里没有 spec 列出的任何包
- [x] 5.2 更新 `model_cache.py` 中 `_MODEL_FILES` 的注释（去掉 torchvision 前提）。验证：代码审阅
- [x] 5.3 去掉 `tests/conftest.py` 的 `KMP_DUPLICATE_LIB_OK` 及其说明。验证：完整测试套件不出现 OMP 报错；如果复现，就保留开关并改写注释说明真实原因
- [x] 5.4 运行 `release/build_sources.py`，重新生成 `desktop/src-tauri/runtime-sources/*.json`。验证：`--check` 通过，清单里没有 spec 列出的包
- [x] 5.5 1.1 的生成脚本依赖旧实现，删除它，或在文件头注明只能在旧依赖下运行；fixture 保留。验证：`ruff` 和 `mypy` 不再扫到失效的 import

## 6. 整体验证

- [ ] 6.1 在 backend 运行 `ruff check`、`mypy`、`pytest`（含 coverage combine）。验证：全部通过，coverage 不低于 80%
- [x] 6.2 本地有模型时运行 `pytest -m slow`：真实图片向量与 1.4 基准的余弦相似度 ≥ 0.999，离线场景下图片向量化成功。验证：slow 用例通过
- [x] 6.3 对比瘦身前后的 `.venv/lib/python3.12/site-packages` 体积。验证：记录在 PR 描述中，预计减少约 830 MB
- [ ] 6.4 起 `tauri dev`，导入一个含图片、视频、文档的目录，然后跑一次文本搜索和一次以图搜图。验证：任务全部成功，搜索结果合理
- [x] 6.5 把 `MEMORY.md` 里的 OpenMP 冲突那条（torch 对 faiss）改成已失效，或直接删除。验证：memory 文件已更新
