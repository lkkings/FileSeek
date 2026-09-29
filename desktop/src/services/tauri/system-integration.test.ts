import { beforeEach, describe, expect, it, vi } from "vitest";

import { invoke } from "@tauri-apps/api/core";
import { isTauriRuntime } from "./api";
import {
  defaultSystemIntegrationStatus,
  getSystemIntegrationStatus,
  setFileManagerIntegration,
  setSilentStartup,
} from "./system-integration";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

vi.mock("./api", () => ({
  isTauriRuntime: vi.fn(),
}));

const invokeMock = vi.mocked(invoke);
const runtimeMock = vi.mocked(isTauriRuntime);

describe("system integration service", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    runtimeMock.mockReturnValue(true);
  });

  it("returns the default status outside Tauri", async () => {
    runtimeMock.mockReturnValue(false);

    await expect(getSystemIntegrationStatus()).resolves.toEqual(defaultSystemIntegrationStatus);
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("reads the integration status through Tauri", async () => {
    invokeMock.mockResolvedValue(defaultSystemIntegrationStatus);

    await getSystemIntegrationStatus();

    expect(invokeMock).toHaveBeenCalledWith("get_system_integration_status");
  });

 it("sends boolean payloads through Tauri", async () => {
    invokeMock.mockResolvedValue(defaultSystemIntegrationStatus);

    await setSilentStartup(true);
    await setFileManagerIntegration(false);

    expect(invokeMock).toHaveBeenCalledWith("set_silent_startup", { enabled: true });
    expect(invokeMock).toHaveBeenCalledWith("set_file_manager_integration", { enabled: false });
  });
});
