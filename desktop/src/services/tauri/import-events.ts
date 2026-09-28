import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import type { ImportEventStreamTransport } from "../api/import-events";

interface TauriImportEventChunk {
  stream_id: string;
  chunk: string;
}

export function tauriImportEventTransport(): ImportEventStreamTransport {
  return {
    async open(path, lastEventId, onChunk, signal) {
      const streamId = `import-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      let removeListener: (() => void) | undefined;
      try {
        removeListener = await listen<TauriImportEventChunk>(
          "import-event-chunk",
          (event) => {
            if (event.payload.stream_id === streamId) {
              onChunk(event.payload.chunk);
            }
          },
        );
        if (signal.aborted) {
          throw new DOMException("Aborted", "AbortError");
        }
        await invoke("open_import_event_stream", {
          request: {
            path,
            lastEventId,
            streamId,
          },
        });
      } finally {
        removeListener?.();
      }
    },
  };
}
