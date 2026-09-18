# FileSeek 后端服务

承载全部业务逻辑：文件搬运、任务队列、特征抽取、向量索引、检索 API。仅监听 `127.0.0.1`，通过令牌鉴权。

```bash
uv sync --extra dev      # 安装依赖
uv run pytest            # 运行测试
uv run ruff check .      # lint
uv run mypy src          # 类型检查
```

模型推理运行在独立子进程中，以隔离显存占用并让模型档位切换不需要重启整个服务。
