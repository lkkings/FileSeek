import { useCallback, useEffect, useRef, useState } from "react";

import { useTranslate } from "../../../i18n/useTranslate";
import {
  startBatchImport,
  type BatchImportItem,
} from "../../../services/api/library";
import { errorText } from "../../../services/api/client";
import {
  openImportEventStream,
  type ImportEvent,
} from "../../../services/api/import-events";
import type {
  BatchImportState,
  ImportFileSelection,
  ImportProgressItem,
} from "../types";

const IDLE_STATE: BatchImportState = {
  importId: null,
  status: "idle",
  total: 0,
  succeeded: 0,
  failed: 0,
  items: [],
  error: null,
};

export function useBatchImport(
  folderId: string,
  onNotice: (message: string) => void = () => undefined,
) {
  const t = useTranslate();
  const [state, setState] = useState<BatchImportState>(IDLE_STATE);
  const streamRef = useRef<{ close: () => void; done: Promise<void> } | null>(null);
  const batchFailedMessage = t("import.batchFailed", "导入任务失败");

  useEffect(() => () => streamRef.current?.close(), []);

  const start = useCallback(
    async (selections: ImportFileSelection[], targetFolderId = folderId) => {
      if (selections.length === 0) return false;
      const items: BatchImportItem[] = selections.map((selection) => ({
        path: selection.path,
        storageId: selection.storageId,
      }));
      setState({ ...IDLE_STATE, status: "starting", items: toProgressItems(selections) });

      const response = await startBatchImport({ folderId: targetFolderId, items });
      if (response.status !== "success" || !response.data) {
        const message =
          errorText(response.error) || t("import.startFailed", "导入任务创建失败");
        setState({ ...IDLE_STATE, items: toProgressItems(selections), error: message });
        onNotice(message);
        return false;
      }

      const importId = response.data.import_id;
      setState((current) => ({
        ...current,
        importId,
        total: response.data?.total ?? current.items.length,
        status: "running",
      }));
      streamRef.current?.close();
      streamRef.current = openImportEventStream(
        `/api/v1/library/files/import/${encodeURIComponent(importId)}/events`,
        {
          onEvent: (event) =>
            setState((current) => applyEvent(current, event, batchFailedMessage)),
          onError: () => {
            setState((current) => ({
              ...current,
              status: current.status === "completed" ? current.status : "failed",
              error: t("import.streamFailed", "导入进度连接失败"),
            }));
          },
        },
      );
      onNotice(t("import.started", "导入任务已开始"));
      return true;
    },
    [batchFailedMessage, folderId, onNotice, t],
  );

  return { state, start };
}

function toProgressItems(selections: ImportFileSelection[]): ImportProgressItem[] {
  return selections.map((selection) => ({
    storageId: selection.storageId,
    path: selection.path,
    state: "queued",
    fileId: null,
    taskId: null,
    error: null,
  }));
}

function applyEvent(
  current: BatchImportState,
  event: ImportEvent,
  batchFailedMessage: string,
): BatchImportState {
  const index = Number(event.payload.index ?? -1);
  const patch = event.payload as {
    file_id?: string;
    task_id?: string;
    error?: string;
    total?: number;
    succeeded?: number;
    failed?: number;
  };
  const items = index >= 0 && index < current.items.length
    ? current.items.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              fileId: patch.file_id ?? item.fileId,
              taskId: patch.task_id ?? item.taskId,
              error: patch.error ?? item.error,
              state: nextItemState(event.type),
            }
          : item,
      )
    : current.items;

  switch (event.type) {
    case "batch_started":
      return { ...current, status: "running", total: patch.total ?? current.total };
    case "item_completed":
      return { ...current, items, succeeded: current.succeeded + 1 };
    case "item_failed":
      return { ...current, items, failed: current.failed + 1 };
    case "batch_completed":
      return {
        ...current,
        items,
        status: "completed",
        succeeded: patch.succeeded ?? current.succeeded,
        failed: patch.failed ?? current.failed,
      };
    case "batch_failed":
      return {
        ...current,
        items,
        status: "failed",
        error: patch.error ?? batchFailedMessage,
      };
    default:
      return { ...current, items };
  }
}

function nextItemState(eventType: ImportEvent["type"]): ImportProgressItem["state"] {
  if (eventType === "item_registered") return "registered";
  if (eventType === "item_completed") return "completed";
  if (eventType === "item_failed") return "failed";
  return "processing";
}
