## Purpose

约束 backend 运行时需要安装的依赖集合，让 release 版首次下载只包含推理真正用到的包，同时保证图片、文本向量化和视频关键帧去重的行为不变。

## ADDED Requirements

### Requirement: 运行时依赖不含深度学习训练框架

backend 的运行时依赖集合 SHALL NOT 包含 PyTorch 及其生态包（torch、torchvision、timm）、transformers、sentence-transformers、faiss，以及代码中没有使用的包。所有向量化推理 SHALL 只通过 ONNX 推理引擎完成。

#### Scenario: 锁文件中不出现被移除的包
- **WHEN** 解析 `backend/uv.lock` 中 fileseek 的非 dev 依赖闭包
- **THEN** 闭包中 SHALL NOT 出现 torch、torchvision、timm、transformers、sentence-transformers、faiss-cpu、scikit-learn、scipy、imagehash、zeroconf、keyring、smbprotocol、webdavclient3

#### Scenario: release 运行时清单同步缩减
- **WHEN** 根据锁文件重新生成各平台的运行时 wheel 清单
- **THEN** 清单中 SHALL NOT 包含上述任何包的 wheel

### Requirement: 图片向量化不依赖远程预处理代码

图片向量化 SHALL 只根据本地模型目录中的预处理配置（尺寸、缩放方式、插值、均值、标准差）完成预处理，SHALL NOT 加载或执行模型仓库中的远程 Python 代码。

#### Scenario: 离线环境中图片向量化成功
- **WHEN** 模型文件已在本地缓存、网络不可用，对一张 JPEG 图片执行图片向量化
- **THEN** 系统 SHALL 返回一条 1024 维、L2 归一化的向量

#### Scenario: 与旧实现的向量近似一致
- **WHEN** 对同一组测试图片分别用旧实现和新实现生成向量
- **THEN** 每对向量的余弦相似度 SHALL 不低于 0.999

#### Scenario: 非 RGB 图片
- **WHEN** 输入灰度、带透明通道或调色板模式的图片
- **THEN** 系统 SHALL 先转换为 RGB 再预处理，并返回 1024 维向量

### Requirement: 文本向量化结果保持不变

文本向量化 SHALL 使用模型自带的 tokenizer 定义完成分词，截断长度和填充规则与原实现一致。

#### Scenario: token 序列与旧实现一致
- **WHEN** 对同一组中英文文本（包括超过最大长度的长文本）分别用旧实现和新实现分词
- **THEN** 两者产生的 token id 序列 SHALL 完全相同

#### Scenario: 查询指令前缀
- **WHEN** 以查询模式向量化一段文本
- **THEN** 系统 SHALL 在分词前加上查询指令前缀，行为与原实现一致

### Requirement: 视频关键帧去重行为保持不变

视频抽帧后的相似帧去重 SHALL 继续使用感知哈希（DCT phash，64 位）和现有的汉明距离阈值。

#### Scenario: 相同帧被去重
- **WHEN** 连续两帧画面完全相同
- **THEN** 两帧哈希的汉明距离 SHALL 为 0，第二帧 SHALL 被丢弃

#### Scenario: 与旧实现近似一致
- **WHEN** 对同一组测试帧分别用旧实现和新实现计算哈希
- **THEN** 每对哈希的汉明距离 SHALL 不超过 2
