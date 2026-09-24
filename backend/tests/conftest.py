"""全局测试配置。

`KMP_DUPLICATE_LIB_OK` 要在任何东西 import torch 之前设好：torch 和 faiss-cpu 各自
带一份 libomp，同一进程里两份都在，第一次 faiss 检索会以 OMP: Error #15 abort——不是
在 import 时，所以看起来像测试卡住而不是报错。这个开关是官方标注 unsafe 的绕法，
测试里可以接受，服务进程不能靠它。
"""

from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
