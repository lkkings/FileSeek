import { describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
const listenMock = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: (...args: unknown[]) => listenMock(...args),
}));

import { openEnhancedSearchEventStream } from "../api/enhanced-search-events";
import { tauriSearchProgressEventTransport } from "./search-progress-events";

type ChunkHandler = (event: { payload: TauriSearchProgressChunk }) => void;
interface TauriSearchProgressChunk {
  stream_id: string;
  chunk: string;
}

function setupTauriMocks() {
  invokeMock.mockReset();
  listenMock.mockReset();
  let chunkHandler: ChunkHandler | undefined;
  listenMock.mockImplementation(async (_event: string, handler: ChunkHandler) => {
    chunkHandler = handler;
    return () => undefined;
  });
  invokeMock.mockImplementation(async (command: string, args?: unknown) => {
    if (command !== "open_search_progress_stream") return null;
    const request = (args as { request: { streamId: string } }).request;
    chunkHandler?.({
      payload: {
        stream_id: "other-stream",
        chunk: 'event: progress\ndata: {"type":"status","phase":"ignored"}\n\n',
      },
    });
    chunkHandler?.({
      payload: {
        stream_id: request.streamId,
        chunk:
          'event: progress\ndata: {"type":"tool_call","tool_name":"search_files","query":"猫照片"}\n\n' +
          'event: progress\ndata: {"type":"result","result":{"items":[],"total":0,"page_number":1,"page_size":20,"has_more":false,"counter":{}}}\n\n',
      },
    });
    return null;
  });
}

describe("tauri search progress transport", () => {
  it("forwards matching chunks through the shared SSE parser", async () => {
    setupTauriMocks();
    const events: unknown[] = [];

    await openEnhancedSearchEventStream(
      { query: "猫照片", sort_by: "relevance", sort_order: "desc" },
      { onEvent: (event) => events.push(event) },
      { transport: tauriSearchProgressEventTransport() },
    ).done;

    expect(events).toEqual([
      { type: "tool_call", tool_name: "search_files", query: "猫照片" },
      {
        type: "result",
        result: {
          items: [],
          total: 0,
          page_number: 1,
          page_size: 20,
          has_more: false,
          counter: {},
        },
      },
    ]);
    expect(listenMock).toHaveBeenCalledWith(
      "search-progress-chunk",
      expect.any(Function),
    );
  });

  it("posts the scoped request and cancels when the signal aborts", async () => {
    setupTauriMocks();
    const controller = new AbortController();
    invokeMock.mockImplementation(async (command: string) => {
      if (command === "open_search_progress_stream") {
        controller.abort();
        return null;
      }
      return null;
    });

    await tauriSearchProgressEventTransport().open(
      "/api/v1/search/enhanced/stream",
      { query: "猫照片", sort_by: "relevance", sort_order: "desc" },
      () => undefined,
      controller.signal,
    );
    await Promise.resolve();

    expect(controller.signal.aborted).toBe(true);
    expect(invokeMock).toHaveBeenCalledWith("open_search_progress_stream", {
      request: {
        path: "/api/v1/search/enhanced/stream",
        body: JSON.stringify({
          query: "猫照片",
          sort_by: "relevance",
          sort_order: "desc",
        }),
        streamId: expect.stringMatching(/^search-progress-/),
      },
    });
    expect(invokeMock).toHaveBeenCalledWith("cancel_search_progress_stream", {
      streamId: expect.stringMatching(/^search-progress-/),
    });
  });
});
