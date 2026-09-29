import { useState } from "react";
import { AdaptiveDocViewer } from "./AdaptiveDocViewer";

import { useTranslate } from "../../../i18n/useTranslate";
import { DocumentFormatIcon } from "./DocumentFormatIcon";
import { buildPreviewUrl, buildThumbnailUrl, getFileExtension, getDocumentPreviewSupport } from "../preview";
import type { FilePreviewItem, PreviewUrlOptions } from "../types";
import "./DocumentDrawerPreview.css";

export interface DocumentDrawerPreviewProps {
  item: FilePreviewItem;
  urlOptions?: PreviewUrlOptions | undefined;
}

export function DocumentDrawerPreview({ item, urlOptions }: DocumentDrawerPreviewProps) {
  const [hasError, setHasError] = useState(false);
  const t = useTranslate();
  const documentSupport = getDocumentPreviewSupport(item);
  const isPdf = getFileExtension(item.fileName) === "pdf";

  if (documentSupport !== "supported" || hasError) {
    return (
      <div className="document-drawer-preview document-drawer-preview-fallback">
        <DocumentFormatIcon
          fileName={item.fileName}
          isUnsupported={documentSupport === "unsupported" || hasError}
        />
        <p role={hasError ? "alert" : undefined}>
          {hasError
            ? t("preview.documentError", "文档预览加载失败")
            : t("preview.unsupported", "该格式暂不支持预览")}
        </p>
      </div>
    );
  }

  return (
    <div className="document-drawer-preview">
      {isPdf ? (
        <img
          src={buildThumbnailUrl(item, "detail", urlOptions)}
          alt={item.fileName}
          loading="lazy"
          decoding="async"
          onError={() => setHasError(true)}
        />
      ) : (
        <AdaptiveDocViewer
          source={{
            kind: "url",
            url: buildPreviewUrl(item, "list", urlOptions),
            filename: item.fileName,
          }}
          page={0}
          showToolbar={false}
          showSidebar={false}
          onError={() => setHasError(true)}
        />
      )}
    </div>
  );
}
