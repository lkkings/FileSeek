import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../test/test-utils";
import type { UpdateStatus } from "../../services/tauri/update";
import { UpdateBanner, UpdateCard } from ".";

const service = vi.hoisted(() => {
  let listener: ((s: UpdateStatus) => void) | undefined;
  return {
    emit(s: UpdateStatus) {
      listener?.(s);
    },
    getUpdateStatus: vi.fn(),
    onUpdateStatusChange: vi.fn(async (fn: (s: UpdateStatus) => void) => {
      listener = fn;
      return () => {};
    }),
    checkForUpdates: vi.fn(),
    downloadUpdate: vi.fn(async () => {}),
    cancelUpdateDownload: vi.fn(async () => {}),
    installUpdate: vi.fn(async () => {}),
  };
});

vi.mock("../../services/tauri/update", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../services/tauri/update")>();
  return { ...actual, ...service };
});

function status(partial: Partial<UpdateStatus>): UpdateStatus {
  return { currentVersion: "0.1.0", phase: "idle", update: null, done: 0, total: null, error: null, ...partial };
}

const available = (required = false, requiredMessage: string | null = null) =>
  status({
    phase: "available",
    update: { version: "0.2.0", notes: "修复导入崩溃", required, requiredMessage },
  });

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.removeItem("fileseek.updateDismissed.v1");
});

describe("UpdateBanner", () => {
  it("shows a required update with Keygate's message, and it cannot be dismissed", async () => {
    service.getUpdateStatus.mockResolvedValue(available(true, "此版本存在安全问题，请更新"));
    renderWithI18n(<UpdateBanner />);

    expect(await screen.findByRole("alert")).toHaveTextContent("此版本存在安全问题，请更新");
    expect(screen.queryByRole("button", { name: "稍后" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下载更新" }));
    expect(service.downloadUpdate).toHaveBeenCalled();
  });

  it("words a required update itself when Keygate gives no message", async () => {
    service.getUpdateStatus.mockResolvedValue(available(true));
    renderWithI18n(<UpdateBanner />);

    expect(await screen.findByRole("alert")).toHaveTextContent("当前版本已不再受支持，请更新到 0.2.0");
  });

  it("offers a normal update once per version", async () => {
    service.getUpdateStatus.mockResolvedValue(available());
    const { unmount } = renderWithI18n(<UpdateBanner />);

    fireEvent.click(await screen.findByRole("button", { name: "稍后" }));
    expect(screen.queryByText(/新版本 0.2.0/)).not.toBeInTheDocument();
    unmount();

    renderWithI18n(<UpdateBanner />);
    await waitFor(() => expect(service.getUpdateStatus).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(/新版本 0.2.0/)).not.toBeInTheDocument();
  });

  it("follows the download through to a restart", async () => {
    service.getUpdateStatus.mockResolvedValue(available());
    renderWithI18n(<UpdateBanner />);
    await screen.findByText(/新版本 0.2.0/);
    const info = available().update;

    act(() => service.emit(status({ phase: "downloading", update: info, done: 50, total: 100 })));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(service.cancelUpdateDownload).toHaveBeenCalled();

    act(() => service.emit(status({ phase: "ready", update: info })));
    fireEvent.click(screen.getByRole("button", { name: "重启并更新" }));
    expect(service.installUpdate).toHaveBeenCalled();
  });
});

describe("UpdateCard", () => {
  it("checks on demand and shows the notes", async () => {
    service.getUpdateStatus.mockResolvedValue(status({ phase: "up_to_date" }));
    service.checkForUpdates.mockResolvedValue(available());
    renderWithI18n(<UpdateCard />);

    expect(await screen.findByText("已是最新版本。")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "检查更新" }));

    expect(await screen.findByText("有新版本 0.2.0 可用。")).toBeInTheDocument();
    expect(screen.getByText("修复导入崩溃")).toBeInTheDocument();
  });

  it("says so when updates are off in this build", async () => {
    service.getUpdateStatus.mockResolvedValue(status({ phase: "disabled" }));
    renderWithI18n(<UpdateCard />);
    expect(await screen.findByText("此版本不检查更新。")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
