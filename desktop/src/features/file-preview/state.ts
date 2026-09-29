import { getDocumentPreviewSupport, getImagePreviewSupport } from "./preview";
import type { FilePreviewItem, PreviewStatus } from "./types";

export function getInitialPreviewStatus(item: FilePreviewItem): PreviewStatus {
  const documentSupport = getDocumentPreviewSupport(item);
  const imageSupport = getImagePreviewSupport(item);
  return documentSupport === "unsupported" || imageSupport === "unsupported"
    ? "unsupported"
    : "loading";
}

export function getPreviewLoadSuccessStatus(): PreviewStatus {
  return "loaded";
}

export function getPreviewLoadErrorStatus(): PreviewStatus {
  return "error";
}
