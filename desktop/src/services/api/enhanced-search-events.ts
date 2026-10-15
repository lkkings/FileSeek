import type {
  EnhancedSearchProgressEvent,
  EnhancedSearchProgressEventType,
  EnhancedSearchRequest,
  FileItem,
  SearchResponseData,
} from "./search";
import { isTauriRuntime } from "../tauri/api";
import { tauriSearchProgressEventTransport } from "../tauri/search-progress-events";

const ENHANCED_SEARCH_STREAM_PATH = "/api/v1/search/enhanced/stream";
const PROGRESS_EVENT_TYPES = new Set<string>([
  "status",
  "reasoning",
  "tool_call",
  "tool_result",
  "result",
  "error",
]);

export interface EnhancedSearchEventStreamTransport {
  open(
    path: string,
    request: EnhancedSearchRequest,
    onChunk: (chunk: string) => void,
    signal: AbortSignal,
  ): Promise<void>;
}

export interface EnhancedSearchEventStreamCallbacks {
  onEvent: (event: EnhancedSearchProgressEvent) => void;
  onError?: (error: unknown) => void;
  onComplete?: () => void;
}

export interface EnhancedSearchEventStreamHandle {
  close: () => void;
  done: Promise<void>;
}

export function createEnhancedSearchSseParser() {
  let buffer = "";

  return {
    push(chunk: string): EnhancedSearchProgressEvent[] {
      buffer += chunk;
      const blocks = buffer.split(/\n\n|\r\n\r\n/);
      buffer = blocks.pop() ?? "";
      return blocks
        .map(parseProgressBlock)
        .filter((event): event is EnhancedSearchProgressEvent => event !== null);
    },
  };
}

export function browserEnhancedSearchEventTransport(): EnhancedSearchEventStreamTransport {
  return {
    async open(path, request, onChunk, signal) {
      if (signal.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      const response = await fetch(path, {
        method: "POST",
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`Enhanced search stream failed: ${response.status}`);
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

export function defaultEnhancedSearchEventTransport(): EnhancedSearchEventStreamTransport {
  return isTauriRuntime() && !import.meta.env.DEV
    ? tauriSearchProgressEventTransport()
    : browserEnhancedSearchEventTransport();
}

export function openEnhancedSearchEventStream(
  request: EnhancedSearchRequest,
  callbacks: EnhancedSearchEventStreamCallbacks,
  options: { transport?: EnhancedSearchEventStreamTransport } = {},
): EnhancedSearchEventStreamHandle {
  const transport = options.transport ?? defaultEnhancedSearchEventTransport();
  const controller = new AbortController();
  let terminal = false;

  const done = (async () => {
    const parser = createEnhancedSearchSseParser();
    try {
      await transport.open(
        ENHANCED_SEARCH_STREAM_PATH,
        request,
        (chunk) => {
          for (const event of parser.push(chunk)) {
            callbacks.onEvent(event);
            if (event.type === "result" || event.type === "error") {
              terminal = true;
              controller.abort();
              callbacks.onComplete?.();
            }
          }
        },
        controller.signal,
      );
    } catch (error) {
      if (!terminal && !controller.signal.aborted) {
        callbacks.onError?.(error);
      }
    }
  })();

  return {
    close: () => controller.abort(),
    done,
  };
}

function parseProgressBlock(block: string): EnhancedSearchProgressEvent | null {
  const dataLines: string[] = [];
  let eventName: string | null = null;

  for (const line of block.split(/\n|\r\n/)) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (eventName !== "progress" || dataLines.length === 0) return null;
  try {
    return parseProgressPayload(JSON.parse(dataLines.join("\n")));
  } catch {
    return null;
  }
}

function parseProgressPayload(value: unknown): EnhancedSearchProgressEvent | null {
  if (!isRecord(value)) return null;
  const type = value.type;
  if (!isProgressEventType(type)) {
    return null;
  }

  const event: EnhancedSearchProgressEvent = { type };
  assignOptionalString(event, "phase", value.phase);
  assignOptionalString(event, "message", value.message);
  assignOptionalString(event, "content", value.content);
  assignOptionalString(event, "tool_name", value.tool_name);
  assignOptionalString(event, "query", value.query);
  assignOptionalString(event, "name_query", value.name_query);
  assignOptionalString(event, "error", value.error);
  assignOptionalNumber(event, "round_number", value.round_number);
  assignOptionalNumber(event, "candidate_count", value.candidate_count);
  assignOptionalNumber(event, "total", value.total);

  if (value.categories !== undefined && value.categories !== null) {
    if (!Array.isArray(value.categories) || value.categories.some((item) => typeof item !== "string")) {
      return null;
    }
    event.categories = value.categories;
  }
  if (value.result !== undefined && value.result !== null) {
    const result = parseSearchResponse(value.result);
    if (result === null) return null;
    event.result = result;
  }
  return event;
}

function parseSearchResponse(value: unknown): SearchResponseData | null {
  if (!isRecord(value)) return null;
  const total = requiredNumber(value.total);
  const pageNumber = requiredNumber(value.page_number);
  const pageSize = requiredNumber(value.page_size);
  if (
    !Array.isArray(value.items) ||
    !isRecord(value.counter) ||
    total === null ||
    pageNumber === null ||
    pageSize === null ||
    typeof value.has_more !== "boolean"
  ) {
    return null;
  }
  const counter: Record<string, number> = {};
  for (const [category, count] of Object.entries(value.counter)) {
    if (!isNumber(count)) return null;
    counter[category] = count;
  }
  if (
    !Array.isArray(value.items) ||
    Object.keys(value.counter).length !== Object.keys(counter).length
  ) {
    return null;
  }
  const items: FileItem[] = [];
  for (const rawItem of value.items) {
    const item = parseFileItem(rawItem);
    if (item === null) return null;
    items.push(item);
  }
  return {
    items,
    total,
    page_number: pageNumber,
    page_size: pageSize,
    has_more: value.has_more,
    counter,
  };
}

function parseFileItem(value: unknown): FileItem | null {
  if (!isRecord(value)) return null;
  const fileId = requiredString(value.file_id);
  const fileName = requiredString(value.file_name);
  const fileType = requiredString(value.file_type);
  const category = requiredString(value.category);
  const path = requiredString(value.path);
  const score = requiredNumber(value.score);
  const size = optionalNumber(value.size);
  const modified = optionalString(value.modified);
  if (
    fileId === null ||
    fileName === null ||
    fileType === null ||
    category === null ||
    path === null ||
    score === null ||
    size === undefined ||
    modified === undefined
  ) {
    return null;
  }
  if (!Array.isArray(value.tags) || value.tags.some((tag) => typeof tag !== "string")) return null;

  return {
    file_id: fileId,
    file_name: fileName,
    file_type: fileType,
    category,
    path,
    size,
    modified,
    tags: value.tags,
    score,
    metadata: isRecord(value.metadata) ? value.metadata : null,
    chunks: Array.isArray(value.chunks) ? value.chunks : null,
  };
}

function assignOptionalString(
  event: EnhancedSearchProgressEvent,
  key: "phase" | "message" | "content" | "tool_name" | "query" | "name_query" | "error",
  value: unknown,
) {
  if (typeof value === "string") event[key] = value;
}

function assignOptionalNumber(
  event: EnhancedSearchProgressEvent,
  key: "round_number" | "candidate_count" | "total",
  value: unknown,
) {
  if (isNumber(value)) event[key] = value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isProgressEventType(value: unknown): value is EnhancedSearchProgressEventType {
  return typeof value === "string" && PROGRESS_EVENT_TYPES.has(value);
}

function requiredString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function optionalString(value: unknown): string | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return typeof value === "string" ? value : undefined;
}

function requiredNumber(value: unknown): number | null {
  return isNumber(value) ? value : null;
}

function optionalNumber(value: unknown): number | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return isNumber(value) ? value : undefined;
}
