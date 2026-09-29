import { useEffect, useRef } from "react";
import videojs from "video.js";

type VideoPlayer = ReturnType<typeof videojs>;

interface VideoJsPlayerProps {
  autoPlay?: boolean | undefined;
  className: string;
  sourceUrl: string;
  startTime?: number | undefined;
  posterUrl?: string | undefined;
  testId: string;
}

export function VideoJsPlayer({
  autoPlay = false,
  className,
  sourceUrl,
  startTime,
  posterUrl,
  testId,
}: VideoJsPlayerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<VideoPlayer | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const videoElement = document.createElement("video");
    videoElement.className = "video-js";
    videoElement.setAttribute("data-testid", testId);
    videoElement.controls = true;
    videoElement.playsInline = true;
    videoElement.preload = "auto";
    videoElement.src = sourceUrl;
    container.appendChild(videoElement);

    const player = videojs(videoElement, {
      autoplay: autoPlay ? "any" : false,
      controls: true,
      fill: true,
      preload: "auto",
      responsive: true,
      poster: posterUrl,
    });
    playerRef.current = player;

    if (startTime !== undefined) {
      player.ready(() => {
        player.currentTime(startTime);
      });
    }

    if (autoPlay) {
      void videoElement.play()?.catch(() => undefined);
    }

    return () => {
      playerRef.current?.dispose();
      playerRef.current = null;
      videoElement.remove();
    };
  }, [autoPlay, posterUrl, sourceUrl, startTime, testId]);

  return <div className={className} ref={containerRef} />;
}
