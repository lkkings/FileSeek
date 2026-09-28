import { useState } from "react";

import { useTranslate } from "../../../i18n/useTranslate";
import { DocumentFormatIcon } from "./DocumentFormatIcon";
import { buildPreviewUrl, getDocumentPreviewSupport } from "../preview";
import { getInitialPreviewStatus } from "../state";
import type { FilePreviewItem, PreviewSize, PreviewStatus, PreviewUrlOptions } from "../types";
import "./FilePreviewCell.css";

export interface FilePreviewCellProps {
  item: FilePreviewItem;
  size?: PreviewSize;
  urlOptions?: PreviewUrlOptions | undefined;
}

export function FilePreviewCell({ item, size = "list", urlOptions }: FilePreviewCellProps) {
  const [status, setStatus] = useState<PreviewStatus>(() => getInitialPreviewStatus(item));
  const t = useTranslate();
  const isImage = item.fileType === "image";
  const isVideo = item.fileType === "video";
  const isDocument = item.fileType === "document";
  const documentSupport = getDocumentPreviewSupport(item);
  const thumbnailUrl =
    isImage || isVideo
      ? buildPreviewUrl(item, size, urlOptions)
      : undefined;

  return (
    <div
      className={`file-preview-cell file-preview-${item.fileType}`}
      data-state={isDocument && documentSupport === "supported" ? "loaded" : status}
      aria-busy={status === "loading"}
    >
      {isDocument && (
        <DocumentFormatIcon fileName={item.fileName} isUnsupported={documentSupport === "unsupported"} />
      )}

      {(isImage || isVideo) && thumbnailUrl && status !== "error" && (
        <img
          key={thumbnailUrl}
          src={thumbnailUrl}
          alt={item.fileName}
          loading="lazy"
          decoding="async"
          onLoad={() => setStatus("loaded")}
          onError={() => setStatus("error")}
        />
      )}

      {isVideo && status !== "error" && (
        <span className="file-preview-play-affordance" aria-hidden="true">
          <span className="file-preview-play-icon" />
        </span>
      )}

      {status === "loading" && (
        <span className="file-preview-state" role="status">
          {t("preview.loading", "预览加载中")}
        </span>
      )}

      {status === "error" && (
        <span className="file-preview-state file-preview-error" role="alert">
          {t("preview.error", "预览加载失败")}
        </span>
      )}

      {status === "unsupported" && (
        <span className="file-preview-state" role="status">
          {t("preview.unsupported", "该格式暂不支持预览")}
        </span>
      )}
    </div>
  );
}
