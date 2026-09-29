import { isTauriRuntime } from "../tauri/api";
import { tauriImportEventTransport } from "../tauri/import-events";

export type ImportEventType =
  | "batch_started"
  | "item_started"
  | "item_registered"
  | "item_completed"
  | "item_failed"
  | "batch_completed"
  | "batch_failed";

export interface ImportEvent {
  id: number;
  type: ImportEventType;
  payload: Record<string, unknown>;
}

export interface ImportEventStreamCallbacks {
  onEvent: (event: ImportEvent) => void;
  onReconnecting?: () => void;
  onError?: (error: unknown) => void;
  onComplete?: () => void;
}

export interface ImportEventStreamTransport {
  open(
    path: string,
    lastEventId: number,
    onChunk: (chunk: string) => void,
    signal: AbortSignal,
  ): Promise<void>;
}

export interface ImportEventStreamHandle {
  close: () => void;
  done: Promise<void>;
}

interface ImportEventStreamOptions {
  transport?: ImportEventStreamTransport;
  reconnectDelayMs?: number;
  maxReconnectAttempts?: number;
}

const TERMINAL_EVENT_TYPES = new Set<ImportEventType>([
  "batch_completed",
  "batch_failed",
]);

export function createSseParser() {
  let buffer = "";

  return {
    push(chunk: string): ImportEvent[] {
      buffer += chunk;
      const blocks = buffer.split(/\n\n|\r\n\r\n/);
      buffer = blocks.pop() ?? "";
      return blocks
        .map(parseSseBlock)
        .filter((event): event is ImportEvent => event !== null);
    },
  };
}

function parseSseBlock(block: string): ImportEvent | null {
  let id = 0;
  let type: ImportEventType | null = null;
  const dataLines: string[] = [];

  for (const line of block.split(/\n|\r\n/)) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("id:")) {
      const parsed = Number.parseInt(line.slice(3).trim(), 10);
      if (Number.isFinite(parsed)) id = parsed;
    } else if (line.startsWith("event:")) {
      const candidate = line.slice(6).trim() as ImportEventType;
      type = candidate;
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (type === null || dataLines.length === 0) return null;
  try {
    const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
    return { id, type, payload };
  } catch {
    return null;
  }
}

export function browserImportEventTransport(): ImportEventStreamTransport {
  return {
    async open(path, lastEventId, onChunk, signal) {
      const response = await fetch(path, {
        method: "GET",
        headers: {
          Accept: "text/event-stream",
          ...(lastEventId > 0 ? { "Last-Event-ID": String(lastEventId) } : {}),
        },
        signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`Import event stream failed: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        onChunk(decoder.decode(value, { stream: true }));
      }
    },
  };
}

export function defaultImportEventTransport(): ImportEventStreamTransport {
  return isTauriRuntime() && !import.meta.env.DEV
    ? tauriImportEventTransport()
    : browserImportEventTransport();
}

export function openImportEventStream(
  path: string,
  callbacks: ImportEventStreamCallbacks,
  options: ImportEventStreamOptions = {},
): ImportEventStreamHandle {
  const transport = options.transport ?? defaultImportEventTransport();
  const reconnectDelayMs = options.reconnectDelayMs ?? 1000;
  const maxReconnectAttempts = options.maxReconnectAttempts ?? Number.POSITIVE_INFINITY;
  const controller = new AbortController();
  let lastEventId = 0;
  let terminal = false;

  const done = (async () => {
    let reconnectAttempts = 0;
    while (!terminal && !controller.signal.aborted) {
      const parser = createSseParser();
      try {
        await transport.open(
          path,
          lastEventId,
          (chunk) => {
            for (const event of parser.push(chunk)) {
              lastEventId = Math.max(lastEventId, event.id);
              callbacks.onEvent(event);
              if (TERMINAL_EVENT_TYPES.has(event.type)) {
                terminal = true;
                controller.abort();
                callbacks.onComplete?.();
              }
            }
          },
          controller.signal,
        );
        if (terminal || controller.signal.aborted) break;
      } catch (error) {
        if (terminal || controller.signal.aborted) break;
        if (reconnectAttempts >= maxReconnectAttempts) {
          callbacks.onError?.(error);
          return;
        }
      }

      if (terminal || controller.signal.aborted) break;
      reconnectAttempts += 1;
      callbacks.onReconnecting?.();
      await delay(reconnectDelayMs, controller.signal);
    }
  })();

  return {
    close: () => controller.abort(),
    done,
  };
}

function delay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    function onAbort() {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
