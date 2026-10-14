## Context

动机见 proposal.md。和实现相关的现状：

- `JinaClipV2Embedding._load_resources` 用 `AutoTokenizer` 和 `AutoImageProcessor`（都开了 `trust_remote_code`）加载 `tokenizer/` 目录。图片处理器通过 `preprocessor_config.json` 的 `auto_map` 指向 `jinaai/jina-clip-implementation`，这份远程代码顶层 import 了 torchvision，返回 torch 张量，再由 `_as_numpy` 转回 numpy。
- 当前预处理配置：`size=512`、`resize_mode=shortest`、`interpolation=bicubic`、CLIP 的 mean/std、`fill_color=0`。推理分支（`is_train=False`）的流程是 `Resize(512, BICUBIC)`，然后 `CenterCrop(512)`、`_convert_to_rgb`、`ToTensor`（/255，转 CHW），最后 `Normalize`。
- 分词调用的是 `tokenizer(texts, padding=False, truncation=True, max_length=8194)`，`max_length` 取自 `tokenizer_config.json` 的 `model_max_length`。`pad_token_id` 是 1。
- `tokenizer.json` 自带 `truncation.max_length=77` 和 `padding.strategy=Fixed(77)`。transformers 在调用时会覆盖这两项，直接用 `tokenizers` 时不会。
- `video_sampler` 只用了 `imagehash.phash`：转灰度，LANCZOS 缩放到 32x32，二维 DCT-II，取左上 8x8，与中位数比较得到 64 位，帧之间用汉明距离和阈值 10 比较。
- 依赖闭包里：sympy、networkx 只被 torch 依赖；scipy 只被 imagehash、scikit-learn、sentence-transformers 依赖；`tokenizers` 已经被 chromadb 间接依赖，提升为直接依赖不会增加下载量。`huggingface-hub` 仍是直接依赖（dev 模式下 `model_cache.py` 用它下载模型），保留。

## Goals / Non-Goals

**Goals:**
- `jina_clip_v2.py` 和 `video_sampler.py` 在运行时只依赖 numpy、Pillow、onnxruntime、tokenizers。
- 和旧实现的数值差异控制在 spec 给出的阈值内。

**Non-Goals:**
- 不改 ONNX 推理、文本分批、注意力预算等逻辑。
- 不改模型文件清单、下载流程和文本塔子图的现场抽取。
- 不重建已有索引，也不提供迁移脚本。
- 不实现 `resize_mode=longest/squash` 等当前模型用不到的分支。

## Decisions

### 1. 图片预处理：内置一个只覆盖推理路径的小模块

新建 `infrastructure/embedding/clip_preprocess.py`，从 `preprocessor_config.json` 读取 `size`、`mean`、`std`、`resize_mode`、`interpolation`，按下面的步骤处理：

1. 转 RGB（`_load_image` 已经做了。上游是先缩放再转 RGB，对 RGB 输入两种顺序结果一样；对带透明通道的图先转 RGB 更稳妥，差异在可接受范围内）。
2. 最短边缩放到 `size`，长边按 torchvision 的规则计算：`int(size * long / short)`。用 `Image.resize(..., Image.BICUBIC)`，torchvision 对 PIL 输入调用的就是它。
3. 中心裁剪：`top = int(round((h - size) / 2))`，`left` 同理，和 torchvision 的 `CenterCrop` 取整方式一致。
4. 转成 `float32` 并除以 255，按通道减 mean、除 std，转成 CHW，在 batch 维堆叠成 `(N, 3, size, size)`。

遇到配置中不支持的值（`resize_mode` 不是 `shortest`，或 `interpolation` 不是 `bicubic`/`bilinear`），加载阶段直接抛 `ModelLoadError`，不默默退化。

`_as_numpy` 随之删除。`_image_processor` 改为持有这个预处理器实例，`text_only` 模式下仍为 None。

替代方案：
- 换用 transformers 内置的 `CLIPImageProcessor`：仍然依赖 transformers，而且它的 resize 和裁剪规则与 torchvision 不完全相同，差异更大。
- 把预处理烘焙进 ONNX 图：要改模型文件和发布流程，收益不抵成本。

### 2. 分词：`tokenizers.Tokenizer.from_file` 加一层薄包装

新建一个小包装，对外提供 `encode_batch(texts) -> list[list[int]]`、`pad_token_id` 和 `max_length`：

- 加载后先调用 `no_padding()`，再调用 `enable_truncation(max_length=model_max_length)`，覆盖 `tokenizer.json` 自带的 77。漏掉这一步，文本会被静默截到 77 个 token，这是本次改动最容易出错的地方。
- `model_max_length` 和 `pad_token` 从 `tokenizer_config.json` 读，`pad_token_id` 用 `token_to_id(pad_token)` 换算。`_get_max_sequence_length` 现有的兜底（缺失或大于 1e6 时取 8192）保留。
- `add_special_tokens=True`，由 `post_processor`（TemplateProcessing，`<s> A </s>`）负责加首尾 token，和 transformers 行为一致。
- `embed_text` 只把 `tokenizer(...)["input_ids"]` 这一处换成 `encode_batch`，分批和 padding 逻辑不动。

类型注解里的 `PreTrainedTokenizerBase`、`AutoImageProcessor` 换成新包装类和预处理器类，`TYPE_CHECKING` 下也不再 import transformers。

替代方案：保留 transformers、只去掉 torch。transformers 本身约 59 MB，而这里只用了 tokenizer，不划算。

### 3. phash：用 numpy 矩阵乘法实现 DCT

在 `video_sampler.py` 旁边新建 `perceptual_hash.py`：

- `image.convert("L").resize((32, 32), Image.LANCZOS)`，转成 float64 数组。
- 预先算好 32x32 的 DCT-II 基矩阵 `C`（不归一化，和 `scipy.fftpack.dct` 默认 `norm=None` 一致），`dct = C @ pixels @ C.T`。
- 取 `dct[:8, :8]`，与中位数比较得到布尔数组。之后只做相对比较，所以系数上的整体缩放不影响结果。
- 返回一个包含 64 位布尔数组的小对象，实现 `__sub__` 计算汉明距离，这样 `video_sampler` 里 `current_hash - previous_hash` 的写法不用改。

替代方案：用 `numpy.fft` 拼出 DCT。可行，但 32x32 的矩阵乘法更短，也更直观。

### 4. 依赖清单

- 从 `dependencies` 删除：torch、torchvision、timm、transformers、sentence-transformers、faiss-cpu、imagehash、zeroconf、keyring、smbprotocol、webdavclient3。
- 新增直接依赖 `tokenizers==0.23.2`（与当前锁定版本一致）。
- 保留：onnx、onnxruntime、huggingface-hub、pillow、chromadb、rapidocr-onnxruntime 等。
- 一并删掉 pyproject 里那段解释 torchvision 和 timm 的注释，并把 `model_cache.py` 中 `_MODEL_FILES` 的注释改成新的前提：`preprocessor_config.json` 仍然需要，由预处理器读取。
- 运行 `uv lock` 后，用 `release/build_sources.py` 重新生成 `desktop/src-tauri/runtime-sources/*.json`，并用 `--check` 确认结果一致。

### 5. 验证方式：一次性对照，不留下运行时依赖

在删除依赖之前，先在当前环境里用旧实现跑一遍，生成对照基准：一组覆盖不同尺寸、长宽比和模式（RGB、L、RGBA、P）的图片，各自的 `pixel_values` 和图片向量；一组中英文和超长文本的 token id；一组视频帧的 phash。结果存成 `tests/fixtures/` 下的小 `.npz` 或 `.json`。

新实现的测试只读这些基准文件，不需要 torch 或 transformers：

- 预处理 `pixel_values` 的最大绝对误差 < 0.05（归一化之后的数值）。
- 依赖真实模型的向量对比放在 `@pytest.mark.slow` 下，阈值见 spec。
- token id 必须完全相等。
- phash 的汉明距离 ≤ 2。

基准用的图片在测试里按固定种子生成或画出来，不往仓库提交大文件。

## Risks / Trade-offs

- [`tokenizer.json` 自带的截断和填充没被关掉，导致长文本被截到 77] → 包装类在加载时强制覆盖；对照测试必须包含超过 77 个 token 的文本。
- [PIL 和 torchvision 的 bicubic 在边缘处或长边取整上有细微差异] → 对照测试覆盖奇数尺寸和极端长宽比；超出阈值时先查长边取整规则。按用户的决定，极小差异可以接受。
- [远程预处理代码以后升级、行为变了，我们跟不上] → 我们锁定了模型 revision，远程代码也不再执行，反而更稳定。换模型时需要重新核对预处理。
- [chromadb 以后不再依赖 tokenizers] → 已经列为直接依赖，不受影响。
- [删掉 `KMP_DUPLICATE_LIB_OK` 后，onnxruntime 和 opencv 之间出现新的 OpenMP 冲突] → 去掉这个变量后跑完整测试套件；如果复现，就换个注释保留这个开关，并在 memory 里记下来。
- [有人用旧版 transformers 的 tokenizer 缓存] → 不涉及：模型目录里本来就是 `tokenizer.json`，新旧实现读的是同一份文件。

## Migration Plan

1. 先生成对照基准（第 5 节），并提交。
2. 实现预处理、分词包装和 phash，测试通过。
3. 删依赖，`uv lock`、`uv sync`，跑完整测试和 `mypy --strict`。
4. 重新生成 runtime-sources，用 `--check` 确认。
5. 回滚：恢复 `pyproject.toml`、`uv.lock` 和这三个模块即可。数据和模型文件没有任何变化。

## Open Questions

无。
