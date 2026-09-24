import { useState } from "react";
import type { PreviewFile } from "./types";

export function PresentationPreview({ file }: { file: PreviewFile }) {
  const [slide, setSlide] = useState(1);
  return <div className="preview-presentation"><aside className="preview-slides">{[1, 2, 3].map((number) => <button key={number} type="button" className={slide === number ? "is-active" : ""} onClick={() => setSlide(number)}>幻灯片 {number}</button>)}</aside><div className="preview-slide-stage"><article className="preview-slide"><h1>{slide === 1 ? file.name.replace(/\.pptx?$/i, "") : slide === 2 ? "技术选型及基础架构" : "多模态模型评估"}</h1><p>{slide === 1 ? "项目汇报与产品分发白皮书" : "FileSeek 基于 Tauri、React 与 TypeScript 构建桌面语义检索体验。"}</p></article></div></div>;
}
