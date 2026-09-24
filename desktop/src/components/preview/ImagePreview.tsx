import { useState } from "react";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
import { mediaUrl } from "../../utils/media";
import type { PreviewFile } from "./types";

export function ImagePreview({ file }: { file: PreviewFile }) {
  const [rotation, setRotation] = useState(0);
  return (
    <div className="preview-image">
      <TransformWrapper initialScale={1} minScale={0.2} maxScale={8}>
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            <div className="preview-floating-toolbar preview-floating-toolbar--top">
              <button type="button" onClick={() => zoomIn()} aria-label="放大图片">＋</button>
              <button type="button" onClick={() => zoomOut()} aria-label="缩小图片">－</button>
              <button type="button" onClick={() => resetTransform()}>重置</button>
            </div>
            <TransformComponent wrapperClass="preview-image__transform" contentClass="preview-image__transform-content">
              <img className="preview-image__asset" src={mediaUrl(file.id)} alt={file.name} style={{ transform: `rotate(${rotation}deg)` }} />
            </TransformComponent>
          </>
        )}
      </TransformWrapper>
      <div className="preview-floating-toolbar preview-floating-toolbar--bottom">
        <button type="button" onClick={() => setRotation((value) => (value + 90) % 360)}>旋转 90°</button>
      </div>
    </div>
  );
}
