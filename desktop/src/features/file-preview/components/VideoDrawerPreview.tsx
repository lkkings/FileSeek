import { useEffect, useRef, useState } from "react";
import videojs from "video.js";

import "video.js/dist/video-js.css";

import { useTranslate } from "../../../i18n/useTranslate";
import { buildOriginalFileUrl, buildPreviewUrl } from "../preview";
import type { FilePreviewItem, PreviewUrlOptions } from "../types";
import "./MediaDrawerPreview.css";

type VideoPlayer = ReturnType<typeof videojs>;

export interface VideoDrawerPreviewProps {
  item: FilePreviewItem;
  urlOptions?: PreviewUrlOptions | undefined;
}

export function VideoDrawerPreview({ item, urlOptions }: VideoDrawerPreviewProps) {
  const [isPlayerActive, setIsPlayerActive] = useState(false);
  const [hasThumbnailError, setHasThumbnailError] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<VideoPlayer | null>(null);
  const sourceUrl = buildOriginalFileUrl(item, urlOptions);
  const thumbnailUrl = buildPreviewUrl(item, "detail", urlOptions);
  const t = useTranslate();

  useEffect(() => {
    if (!isPlayerActive) return;
    const videoElement = containerRef.current?.querySelector("video");
    if (!videoElement) return;

    const player = videojs(videoElement, { controls: true, preload: "auto", responsive: true });
    playerRef.current = player;

    return () => {
      playerRef.current?.dispose();
      playerRef.current = null;
    };
  }, [isPlayerActive, sourceUrl]);

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
    <div className="media-drawer-preview media-drawer-video is-playing" ref={containerRef}>
      <video src={sourceUrl} controls playsInline data-testid="drawer-video-player" />
    </div>
  );
}
