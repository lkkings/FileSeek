import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../test/test-utils";
import type { Readiness } from "../../services/tauri/readiness";
import { ReadinessGate } from "./ReadinessGate";
import { etaSeconds, formatBytes, percent } from "./format";

const service = vi.hoisted(() => {
  let listener: ((r: Readiness) => void) | undefined;
  return {
    initial: null as Readiness | null,
    emit(r: Readiness) {
      listener?.(r);
    },
    getReadiness: vi.fn(),
    onReadinessChange: vi.fn(async (fn: (r: Readiness) => void) => {
      listener = fn;
      return () => {
        listener = undefined;
      };
    }),
    retryReadiness: vi.fn(async () => {}),
    repairRuntime: vi.fn(async () => {}),
    hideToTray: vi.fn(async () => {}),
  };
});

vi.mock("../../services/tauri/readiness", () => service);

const systemIntegration = vi.hoisted(() => ({
  status: {
    silentStartupEnabled: false,
    fileManagerIntegrationEnabled: false,
    fileManagerIntegrationSupported: true,
    finderExtensionApprovalRequired: false,
  },
  setSilentStartup: vi.fn(),
  setFileManagerIntegration: vi.fn(),
}));

vi.mock("../../services/tauri/system-integration", () => ({
  defaultSystemIntegrationStatus: systemIntegration.status,
  getSystemIntegrationStatus: vi.fn(async () => systemIntegration.status),
  setSilentStartup: systemIntegration.setSilentStartup,
  setFileManagerIntegration: systemIntegration.setFileManagerIntegration,
}));

function snapshot(partial: Partial<Readiness>): Readiness {
  return {
    state: "checking",
    done: 0,
    total: 0,
    bytesPerSecond: 0,
    failedStep: null,
    errorKind: null,
    error: null,
    space: null,
    unwritablePath: null,
    logPath: null,
    ...partial,
  };
}

function renderGate() {
  return renderWithProviders(
    <ReadinessGate>
      <div>Library</div>
    </ReadinessGate>,
  );
}

describe("ReadinessGate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    service.getReadiness.mockResolvedValue(snapshot({ state: "checking" }));
    window.localStorage.setItem("fileseek.setupPromptShown.v1", "1");
  });

  it("holds the app back until the backend is ready", async () => {
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());
    expect(screen.queryByText("Library")).not.toBeInTheDocument();
    expect(screen.getByText("正在启动 FileSeek")).toBeInTheDocument();

    act(() => service.emit(snapshot({ state: "ready" })));

    expect(screen.getByText("Library")).toBeInTheDocument();
  });

  it("shows only the activation screen without a license, even after being ready", async () => {
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());

    act(() => service.emit(snapshot({ state: "activation" })));
    expect(screen.getByRole("heading", { name: "激活 FileSeek" })).toBeInTheDocument();
    expect(screen.queryByText("Library")).not.toBeInTheDocument();

    act(() => service.emit(snapshot({ state: "ready" })));
    expect(screen.getByText("Library")).toBeInTheDocument();

    // The license is lost while running: the app is taken away.
    act(() => service.emit(snapshot({ state: "activation" })));
    expect(screen.queryByText("Library")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "激活 FileSeek" })).toBeInTheDocument();
  });

  it("shows the install steps and download progress on a first run", async () => {
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());

    act(() =>
      service.emit(snapshot({ state: "downloading", done: 256_000_000, total: 2_400_000_000, bytesPerSecond: 2_500_000 })),
    );

    expect(screen.getByText("正在准备 FileSeek")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "10");
    expect(screen.getByText(/256 MB \/ 2.4 GB · 2.5 MB\/s · 约 15 分钟/)).toBeInTheDocument();
    const current = screen.getByText("下载运行时和模型").closest("li");
    expect(current).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("检查磁盘空间").closest("li")).toHaveClass("is-done");

    fireEvent.click(screen.getByRole("button", { name: "最小化到托盘，完成后通知我" }));
    expect(service.hideToTray).toHaveBeenCalled();
  });

  it("explains a failure and retries from where it stopped", async () => {
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());

    act(() =>
      service.emit(
        snapshot({
          state: "failed",
          failedStep: "downloading",
          errorKind: "network",
          error: "network error: connection reset",
          logPath: "/logs/backend.log",
        }),
      ),
    );

    expect(screen.getByRole("alert")).toHaveTextContent("网络连接失败");
    expect(screen.getByText("/logs/backend.log")).toBeInTheDocument();
    expect(screen.getByText("下载运行时和模型").closest("li")).toHaveClass("is-failed");
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(service.retryReadiness).toHaveBeenCalled();
  });

  it("names the space needed when the disk is full", async () => {
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());

    act(() =>
      service.emit(
        snapshot({
          state: "failed",
          failedStep: "space_check",
          errorKind: "disk_space",
          space: { path: "/data", required: 2_640_000_000, available: 2_400_000_000 },
        }),
      ),
    );

    expect(screen.getByRole("alert")).toHaveTextContent("需要 2.6 GB，/data 所在磁盘只有 2.4 GB 可用");
  });

  it("asks before repairing a runtime that keeps crashing", async () => {
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());
    act(() => service.emit(snapshot({ state: "repair_needed", errorKind: "backend", error: "Segmentation fault" })));

    fireEvent.click(screen.getByRole("button", { name: "修复运行时" }));
    expect(service.repairRuntime).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "确定修复" }));

    await waitFor(() => expect(service.repairRuntime).toHaveBeenCalled());
  });

  it("keeps the app on screen when the backend restarts later", async () => {
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());
    act(() => service.emit(snapshot({ state: "ready" })));

    act(() => service.emit(snapshot({ state: "starting" })));

    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("后端服务正在重新启动…")).toBeInTheDocument();
  });

  it("does not let an older initial read overwrite a newer event", async () => {
    let resolveInitial: (r: Readiness) => void = () => {};
    service.getReadiness.mockReturnValue(new Promise((resolve) => (resolveInitial = resolve)));
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());

    act(() => service.emit(snapshot({ state: "ready" })));
    await act(async () => resolveInitial(snapshot({ state: "checking" })));

    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.queryByText("后端服务正在重新启动…")).not.toBeInTheDocument();
  });

  it("offers the suggested settings once, all unchecked", async () => {
    window.localStorage.removeItem("fileseek.setupPromptShown.v1");
    systemIntegration.setSilentStartup.mockResolvedValue(systemIntegration.status);
    renderGate();
    await waitFor(() => expect(service.onReadinessChange).toHaveBeenCalled());
    act(() => service.emit(snapshot({ state: "ready" })));

    const dialog = await screen.findByRole("dialog", { name: "建议设置" });
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.every((box) => !(box as HTMLInputElement).checked)).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "开机静默启动" }));
    fireEvent.click(screen.getByRole("button", { name: "完成" }));

    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(systemIntegration.setSilentStartup).toHaveBeenCalledWith(true, expect.anything());
    expect(systemIntegration.setFileManagerIntegration).not.toHaveBeenCalled();
    expect(window.localStorage.getItem("fileseek.setupPromptShown.v1")).toBe("1");
  });
});

describe("readiness formatting", () => {
  it("formats sizes in decimal units", () => {
    expect(formatBytes(999)).toBe("999 B");
    expect(formatBytes(256_000_000)).toBe("256 MB");
    expect(formatBytes(1_412_957_223)).toBe("1.4 GB");
  });

  it("estimates time left only with a known speed", () => {
    expect(etaSeconds(0, 100, 0)).toBeNull();
    expect(etaSeconds(50, 100, 10)).toBe(5);
    expect(percent(1, 3)).toBe(33);
    expect(percent(5, 0)).toBe(0);
  });
});
