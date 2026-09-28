import { describe, expect, it, vi } from "vitest";

import {
  createSseParser,
  openImportEventStream,
  type ImportEventStreamTransport,
} from "./import-events";

function createTransport(chunks: string[][], expectedLastEventIds: number[]) {
  const calls: number[] = [];
  const transport: ImportEventStreamTransport = {
    async open(path, lastEventId, onChunk) {
      expect(path).toBe("/api/v1/library/files/import/import-1/events");
      calls.push(lastEventId);
      expectedLastEventIds.push(lastEventId);
      for (const chunk of chunks[calls.length - 1] ?? []) {
        onChunk(chunk);
      }
    },
  };
  return { transport, calls };
}

describe("import event stream", () => {
  it("parses events across split chunks", () => {
    const parser = createSseParser();
    const first = parser.push('id: 1\nevent: item_started\ndata: {"ind');
    const second = parser.push('ex":0}\n\nid: 2\nevent: batch_completed\ndata: {"total":1}\n\n');

    expect(first).toEqual([]);
    expect(second).toEqual([
      {
        id: 1,
        type: "item_started",
        payload: { index: 0 },
      },
      {
        id: 2,
        type: "batch_completed",
        payload: { total: 1 },
      },
    ]);
  });

  it("reconnects with the last event id and completes on terminal events", async () => {
    const expectedLastEventIds: number[] = [];
    const { transport } = createTransport(
      [
        ['id: 1\nevent: item_started\ndata: {"index":0}\n\n'],
        ['id: 2\nevent: batch_completed\ndata: {"total":1}\n\n'],
      ],
      expectedLastEventIds,
    );
    const events: unknown[] = [];
    const onComplete = vi.fn();

    await openImportEventStream(
      "/api/v1/library/files/import/import-1/events",
      {
        onEvent: (event) => events.push(event),
        onComplete,
      },
      { transport, reconnectDelayMs: 0 },
    ).done;

    expect(events).toHaveLength(2);
    expect(expectedLastEventIds).toEqual([0, 1]);
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("reports an error after reconnect attempts are exhausted", async () => {
    const expectedLastEventIds: number[] = [];
    const { transport } = createTransport([], expectedLastEventIds);
    const onError = vi.fn();
    const originalOpen = transport.open;
    transport.open = async () => {
      await originalOpen("", 0, () => {}, new AbortController().signal);
      throw new Error("network");
    };

    await openImportEventStream(
      "/api/v1/library/files/import/import-1/events",
      { onEvent: () => undefined, onError },
      { transport, reconnectDelayMs: 0, maxReconnectAttempts: 1 },
    ).done;

    expect(onError).toHaveBeenCalledOnce();
    expect(expectedLastEventIds).toEqual([]);
  });
});
