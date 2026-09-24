import { useEffect, useRef } from "react";
import videojs from "video.js";
import "video.js/dist/video-js.css";
import { mediaUrl } from "../../utils/media";
import type { PreviewFile } from "./types";

export function VideoPreview({ file, initialTime }: { file: PreviewFile; initialTime: number }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    if (!videoRef.current) return;
    const player = videojs(videoRef.current, { controls: true, responsive: true, fluid: true, playbackRates: [0.5, 1, 1.25, 1.5, 2] });
    player.ready(() => { if (initialTime > 0) player.currentTime(initialTime); });
    return () => player.dispose();
  }, [initialTime]);
  return <div className="preview-video"><div data-vjs-player className="preview-video__player"><video ref={videoRef} className="video-js vjs-big-play-centered"><source src={mediaUrl(file.id)} /></video></div></div>;
}
