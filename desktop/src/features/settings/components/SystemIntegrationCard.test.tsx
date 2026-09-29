import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { activateLocale, defaultLocale } from "../../../i18n/i18n";
import { renderWithProviders } from "../../../test/test-utils";
import {
  defaultSystemIntegrationStatus,
  getSystemIntegrationStatus,
  setFileManagerIntegration,
  setSilentStartup,
  type SystemIntegrationStatus,
} from "../../../services/tauri/system-integration";
import { SystemIntegrationCard } from "./SystemIntegrationCard";

vi.mock("../../../services/tauri/system-integration", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../services/tauri/system-integration")>();
  return {
    ...original,
    getSystemIntegrationStatus: vi.fn(),
    setSilentStartup: vi.fn(),
    setFileManagerIntegration: vi.fn(),
  };
});

const getStatus = vi.mocked(getSystemIntegrationStatus);
const setSilent = vi.mocked(setSilentStartup);
const setFileManager = vi.mocked(setFileManagerIntegration);

function status(overrides: Partial<SystemIntegrationStatus> = {}): SystemIntegrationStatus {
  return { ...defaultSystemIntegrationStatus, ...overrides };
}

describe("SystemIntegrationCard", () => {
  beforeEach(() => {
    let currentStatus = status();
    getStatus.mockImplementation(async () => currentStatus);
    setSilent.mockImplementation(async (enabled: boolean) => {
      currentStatus = status({ silentStartupEnabled: enabled });
      return currentStatus;
    });
    setFileManager.mockImplementation(async (enabled: boolean) => {
      currentStatus = status({ fileManagerIntegrationEnabled: enabled });
      return currentStatus;
    });
  });

  afterEach(() => {
    activateLocale(defaultLocale);
  });

  it("renders both integrations off by default", async () => {
    renderWithProviders(<SystemIntegrationCard />);

    expect(await screen.findByRole("heading", { name: "系统集成" })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "开机静默启动" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByRole("switch", { name: "文件管理器右键菜单" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("enables and disables silent startup", async () => {
    renderWithProviders(<SystemIntegrationCard />);
    const control = await screen.findByRole("switch", { name: "开机静默启动" });
    await waitFor(() => expect(control).toBeEnabled());

    fireEvent.click(control);
    await waitFor(() => expect(setSilent.mock.calls.at(-1)?.[0]).toBe(true));
    await waitFor(() => expect(control).toHaveAttribute("aria-checked", "true"));

    fireEvent.click(control);
    await waitFor(() => expect(setSilent.mock.calls.at(-1)?.[0]).toBe(false));
    await waitFor(() => expect(control).toHaveAttribute("aria-checked", "false"));
  });

  it("enables file manager integration", async () => {
    renderWithProviders(<SystemIntegrationCard />);
    const control = await screen.findByRole("switch", { name: "文件管理器右键菜单" });
    await waitFor(() => expect(control).toBeEnabled());

    fireEvent.click(control);

    await waitFor(() => expect(setFileManager.mock.calls.at(-1)?.[0]).toBe(true));
    await waitFor(() => expect(control).toHaveAttribute("aria-checked", "true"));
  });

  it("disables file manager integration", async () => {
    setFileManager.mockClear();
    getStatus.mockImplementationOnce(async () =>
      status({ fileManagerIntegrationEnabled: true }),
    );
    renderWithProviders(<SystemIntegrationCard />);
    const control = await screen.findByRole("switch", { name: "文件管理器右键菜单" });
    await waitFor(() => expect(control).toHaveAttribute("aria-checked", "true"));

    fireEvent.click(control);

    await waitFor(() => expect(setFileManager.mock.calls.at(-1)?.[0]).toBe(false));
    await waitFor(() => expect(control).toHaveAttribute("aria-checked", "false"));
  });

  it("renders English accessibility labels", async () => {
    activateLocale("en-US");

    renderWithProviders(<SystemIntegrationCard />);

    expect(await screen.findByRole("switch", { name: "Silent startup" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByRole("switch", { name: "File manager context menu" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("shows a save failure", async () => {
    setSilent.mockRejectedValueOnce(new Error("无法写入启动项"));
    renderWithProviders(<SystemIntegrationCard />);
    const control = await screen.findByRole("switch", { name: "开机静默启动" });
    await waitFor(() => expect(control).toBeEnabled());

    fireEvent.click(control);

    expect(await screen.findByText("无法写入启动项")).toBeInTheDocument();
  });

  it("shows a file-manager registration failure", async () => {
    setFileManager.mockRejectedValueOnce(new Error("无法注册右键菜单"));
    renderWithProviders(<SystemIntegrationCard />);
    const control = await screen.findByRole("switch", { name: "文件管理器右键菜单" });
    await waitFor(() => expect(control).toBeEnabled());

    fireEvent.click(control);

    await waitFor(() => expect(setFileManager).toHaveBeenCalled());
    expect(
      await screen.findByText("无法注册右键菜单", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it("guides users to approve the macOS Finder extension", async () => {
    getStatus.mockImplementationOnce(async () =>
      status({ finderExtensionApprovalRequired: true }),
    );

    renderWithProviders(<SystemIntegrationCard />);

    expect(
      await screen.findByText(/登录项与扩展/),
    ).toBeInTheDocument();
  });
});
