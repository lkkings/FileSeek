"""组装根：把配置、基础设施、feature 路由装成一个可运行的服务。

这是唯一知道"整个系统长什么样"的地方。各 feature 只认自己的端口和依赖，互相
不打照面，由这里统一接起来。

对外的两个工厂：

- `create_app()` —— 完整装配，测试和内嵌运行都用它。
- `create_service_app()` —— 给 `uvicorn --factory` 的薄封装，额外发布连接文件。
"""

from fileseek.bootstrap.app import PORT_ENV_VAR, create_app, create_service_app
from fileseek.bootstrap.container import Container
from fileseek.bootstrap.logging_config import configure_logging

__all__ = [
    "PORT_ENV_VAR",
    "Container",
    "configure_logging",
    "create_app",
    "create_service_app",
]
