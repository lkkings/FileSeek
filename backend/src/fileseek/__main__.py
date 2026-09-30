import multiprocessing

from fileseek.main import main

if __name__ == "__main__":
    # 模型子进程用 spawn 启动。冻结打包（PyInstaller 等）下子进程会重新执行入口，
    # 没有这一行就会再起一个 uvicorn；非冻结环境下它什么也不做。
    multiprocessing.freeze_support()
    raise SystemExit(main())
