import { afterEach, describe, expect, it, vi } from "vitest";

import {
  browserEnhancedSearchEventTransport,
  createEnhancedSearchSseParser,
  defaultEnhancedSearchEventTransport,
  openEnhancedSearchEventStream,
  type EnhancedSearchEventStreamTransport,
} from "./enhanced-search-events";
import { isTauriRuntime } from "../tauri/api";
import { tauriSearchProgressEventTransport } from "../tauri/search-progress-events";

vi.mock("../tauri/api", () => ({
  isTauriRuntime: vi.fn(() => false),
}));

vi.mock("../tauri/search-progress-events", () => ({
  tauriSearchProgressEventTransport: vi.fn(),
}));

const resultEvent =
  'event: progress\ndata: {"type":"result","result":{"items":[],"total":0,"page_number":1,"page_size":20,"has_more":false,"counter":{}}}\n\n';

describe("enhanced search event stream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.mocked(isTauriRuntime).mockReset();
    vi.mocked(tauriSearchProgressEventTransport).mockReset();
  });

  it("selects the browser transport outside packaged Tauri runtime", () => {
    vi.mocked(isTauriRuntime).mockReturnValue(false);
    vi.stubEnv("DEV", false);

    expect(defaultEnhancedSearchEventTransport()).toBeDefined();
    expect(tauriSearchProgressEventTransport).not.toHaveBeenCalled();
  });

  it("selects the Tauri transport in packaged runtime", () => {
    vi.mocked(isTauriRuntime).mockReturnValue(true);
    vi.stubEnv("DEV", false);
    const transport = browserEnhancedSearchEventTransport();
    vi.mocked(tauriSearchProgressEventTransport).mockReturnValue(transport);

    expect(defaultEnhancedSearchEventTransport()).toBe(transport);
    expect(tauriSearchProgressEventTransport).toHaveBeenCalledOnce();
  });

  it("parses progress events across split chunks", () => {
    const parser = createEnhancedSearchSseParser();
    const first = parser.push('event: progress\ndata: {"type":"tool_call","round');
    const second = parser.push(
      '_number":1,"tool_name":"search_files","query":"猫照片"}\n\n: ping\n\n' + resultEvent,
    );

    expect(first).toEqual([]);
    expect(second).toEqual([
      {
        type: "tool_call",
        round_number: 1,
        tool_name: "search_files",
        query: "猫照片",
      },
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
  });

  it("ignores malformed or non-progress blocks", () => {
    const parser = createEnhancedSearchSseParser();
    const events = parser.push(
      "event: progress\ndata: {broken}\n\n" +
        'event: other\ndata: {"type":"status"}\n\n' +
        'event: progress\ndata: {"type":"status","phase":"starting"}\n\n',
    );

    expect(events).toEqual([{ type: "status", phase: "starting" }]);
  });

  it("completes on terminal events and closes the transport signal", async () => {
    let receivedSignal: AbortSignal | undefined;
    const transport: EnhancedSearchEventStreamTransport = {
      async open(path, request, onChunk, signal) {
        expect(path).toBe("/api/v1/search/enhanced/stream");
        expect(request.query).toBe("猫照片");
        receivedSignal = signal;
        onChunk('event: progress\ndata: {"type":"status"}\n\n');
        onChunk(resultEvent);
      },
    };
    const onEvent = vi.fn();
    const onComplete = vi.fn();

    await openEnhancedSearchEventStream(
      { query: "猫照片", sort_by: "relevance", sort_order: "desc" },
      { onEvent, onComplete },
      { transport },
    ).done;

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onComplete).toHaveBeenCalledOnce();
    expect(receivedSignal?.aborted).toBe(true);
  });

  it("browser transport posts the request and reads the response body", async () => {
    const fetchMock = vi.fn(async () => new Response(resultEvent));
    vi.stubGlobal("fetch", fetchMock);

    await browserEnhancedSearchEventTransport().open(
      "/api/v1/search/enhanced/stream",
      { query: "猫照片", sort_by: "relevance", sort_order: "desc" },
      () => undefined,
      new AbortController().signal,
    );

    expect(fetchMock).toHaveBeenCalledOnce();
    const [path, init] = fetchMock.mock.calls[0]!;
    expect(path).toBe("/api/v1/search/enhanced/stream");
    expect(init.method).toBe("POST");
    expect(init.headers.Accept).toBe("text/event-stream");
    expect(JSON.parse(init.body)).toEqual({
      query: "猫照片",
      sort_by: "relevance",
      sort_order: "desc",
    });
  });

  it("browser transport does not send when the signal is already aborted", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    controller.abort();

    await expect(
      browserEnhancedSearchEventTransport().open(
        "/api/v1/search/enhanced/stream",
        { query: "猫照片", sort_by: "relevance", sort_order: "desc" },
        () => undefined,
        controller.signal,
      ),
    ).rejects.toThrow();

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
