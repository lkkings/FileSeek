import { useState } from "react";

import "video.js/dist/video-js.css";

import { useTranslate } from "../../../i18n/useTranslate";
import { buildOriginalFileUrl, buildPreviewUrl } from "../preview";
import type { FilePreviewItem, PreviewUrlOptions } from "../types";
import { VideoJsPlayer } from "./VideoJsPlayer";
import "./MediaDrawerPreview.css";

export interface VideoDrawerPreviewProps {
  item: FilePreviewItem;
  urlOptions?: PreviewUrlOptions | undefined;
}

export function VideoDrawerPreview({ item, urlOptions }: VideoDrawerPreviewProps) {
  const [isPlayerActive, setIsPlayerActive] = useState(false);
  const [hasThumbnailError, setHasThumbnailError] = useState(false);
  const sourceUrl = buildOriginalFileUrl(item, urlOptions);
  const thumbnailUrl = buildPreviewUrl(item, "detail", urlOptions);
  const t = useTranslate();

  if (!isPlayerActive) {
    return (
      <div className="media-drawer-preview media-drawer-video">
        {hasThumbnailError ? (
          <span className="media-drawer-preview-fallback" role="alert">
            {t("preview.error", "预览加载失败")}
          </span>
        ) : (
          <img
            src={thumbnailUrl}
            alt={item.fileName}
            loading="lazy"
            decoding="async"
            onError={() => setHasThumbnailError(true)}
          />
        )}
        <button type="button" onClick={() => setIsPlayerActive(true)}>
          {t("preview.playVideo", "播放视频")}
        </button>
      </div>
    );
  }

  return (
    <VideoJsPlayer
      autoPlay
      className="media-drawer-preview media-drawer-video is-playing"
      sourceUrl={sourceUrl}
      startTime={item.startTime}
      testId="drawer-video-player"
    />
  );
}
