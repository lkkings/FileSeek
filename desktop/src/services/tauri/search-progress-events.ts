import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import type { EnhancedSearchEventStreamTransport } from "../api/enhanced-search-events";

interface TauriSearchProgressChunk {
  stream_id: string;
  chunk: string;
}

export function tauriSearchProgressEventTransport(): EnhancedSearchEventStreamTransport {
    return {
        async open(path, request, onChunk, signal) {
          const streamId = `search-progress-${Date.now()}-${Math.random().toString(16).slice(2)}`;
          let removeListener: (() => void) | undefined;
          const abortHandler = () => {
            void invoke("cancel_search_progress_stream", { streamId });
          };

          try {
              removeListener = await listen<TauriSearchProgressChunk>(
                "search-progress-chunk",
                (event) => {
                    if (event.payload.stream_id === streamId) {
                        onChunk(event.payload.chunk);
                    }
                },
              );
              signal.addEventListener("abort", abortHandler, { once: true });
              if (signal.aborted) {
                  throw new DOMException("Aborted", "AbortError");
              }
              await invoke("open_search_progress_stream", {
                request: {
                  path,
                  body: JSON.stringify(request),
                  streamId,
                },
              });
          } finally {
              signal.removeEventListener("abort", abortHandler);
              removeListener?.();
          }
        },
    };
}
