# FileSeek 桌面客户端

Tauri v2 + React + TypeScript。负责检索界面、结果呈现、片段跳转播放、任务视图与设置。

后端作为 Tauri sidecar 进程被管理：客户端启动时拉起后端，退出时停止它。关闭主窗口只收进托盘，后端继续处理排队任务。
