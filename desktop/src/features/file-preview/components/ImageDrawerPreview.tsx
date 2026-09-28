import { useState } from "react";

import { useTranslate } from "../../../i18n/useTranslate";
import { buildPreviewUrl } from "../preview";
import type { FilePreviewItem, PreviewUrlOptions } from "../types";
import "./MediaDrawerPreview.css";

export interface ImageDrawerPreviewProps {
  item: FilePreviewItem;
  urlOptions?: PreviewUrlOptions | undefined;
}

export function ImageDrawerPreview({ item, urlOptions }: ImageDrawerPreviewProps) {
  const [hasError, setHasError] = useState(false);
  const t = useTranslate();

  if (hasError) {
    return (
      <div className="media-drawer-preview media-drawer-preview-fallback" role="alert">
        {t("preview.error", "预览加载失败")}
      </div>
    );
  }

  return (
    <div className="media-drawer-preview">
      <img
        src={buildPreviewUrl(item, "detail", urlOptions)}
        alt={item.fileName}
        loading="lazy"
        decoding="async"
        onError={() => setHasError(true)}
      />
    </div>
  );
}
