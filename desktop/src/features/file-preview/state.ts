import { getDocumentPreviewSupport } from "./preview";
import type { FilePreviewItem, PreviewStatus } from "./types";

export function getInitialPreviewStatus(item: FilePreviewItem): PreviewStatus {
  const documentSupport = getDocumentPreviewSupport(item);
  return documentSupport === "unsupported" ? "unsupported" : "loading";
}

export function getPreviewLoadSuccessStatus(): PreviewStatus {
  return "loaded";
}

export function getPreviewLoadErrorStatus(): PreviewStatus {
  return "error";
}
