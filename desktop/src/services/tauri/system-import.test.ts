import { beforeEach, describe, expect, it, vi } from "vitest";

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { isTauriRuntime } from "./api";
import {
  listenSystemImportRequest,
  parseSystemImportRequest,
  systemImportEventName,
} from "./system-import";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(),
}));

vi.mock("./api", () => ({
  isTauriRuntime: vi.fn(),
}));

const invokeMock = vi.mocked(invoke);
const listenMock = vi.mocked(listen);
const runtimeMock = vi.mocked(isTauriRuntime);

describe("system import Tauri service", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    listenMock.mockReset();
    runtimeMock.mockReturnValue(true);
    invokeMock.mockResolvedValue(null);
    listenMock.mockResolvedValue(() => undefined);
  });

  it("validates the typed event payload", () => {
    expect(parseSystemImportRequest({ paths: ["/tmp/a.pdf"], errors: [] })).toEqual({
      paths: ["/tmp/a.pdf"],
      errors: [],
    });
    expect(parseSystemImportRequest(null)).toBeNull();
    expect(parseSystemImportRequest({ paths: "not-an-array", errors: [] })).toBeNull();
    expect(parseSystemImportRequest({ paths: ["/tmp/a.pdf"], errors: [null] })).toBeNull();
    expect(parseSystemImportRequest({ paths: [], errors: [] })).toBeNull();
  });

  it("registers the typed listener and consumes a first-launch request", async () => {
    const onRequest = vi.fn();
    invokeMock.mockResolvedValue({ paths: ["/tmp/first.pdf"], errors: [] });

    await listenSystemImportRequest(onRequest);

    expect(listenMock).toHaveBeenCalledWith(systemImportEventName, expect.any(Function));
    expect(invokeMock).toHaveBeenCalledWith("take_pending_system_import");
    expect(onRequest).toHaveBeenCalledWith({ paths: ["/tmp/first.pdf"], errors: [] });
  });

  it("ignores malformed runtime events and empty pending requests", async () => {
    const onRequest = vi.fn();
    invokeMock.mockResolvedValue({ paths: ["/tmp/pending.pdf"], errors: [] });
    listenMock.mockImplementation(async () => {
      const callback = vi.mocked(listen).mock.calls[0]?.[1] as (event: {
        payload: unknown;
      }) => void;
      callback({ payload: { paths: ["/tmp/valid.pdf"], errors: [] } });
      callback({ payload: { paths: ["/tmp/invalid.pdf", 42], errors: [] } });
      callback({ payload: null });
      return () => undefined;
    });

    await listenSystemImportRequest(onRequest);

    expect(onRequest).toHaveBeenCalledTimes(2);
    expect(JSON.stringify([...listenMock.mock.calls, ...invokeMock.mock.calls])).not.toContain(
      "token",
    );
  });

  it("does not subscribe outside Tauri", async () => {
    runtimeMock.mockReturnValue(false);
    const unlisten = await listenSystemImportRequest(vi.fn());

    unlisten();
    expect(listenMock).not.toHaveBeenCalled();
    expect(invokeMock).not.toHaveBeenCalled();
  });
});
