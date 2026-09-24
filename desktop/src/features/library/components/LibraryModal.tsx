import type { ReactNode } from "react";

interface LibraryModalProps { title: string; onClose: () => void; children: ReactNode; footer: ReactNode }

export function LibraryModal({ title, onClose, children, footer }: LibraryModalProps) {
  return <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}><div className="modal-content" onClick={(event) => event.stopPropagation()}><div className="modal-header"><h2>{title}</h2><button type="button" className="modal-close" onClick={onClose} aria-label="关闭">×</button></div>{children}<div className="modal-footer">{footer}</div></div></div>;
}

export function IconPicker({ value, onChange }: { value: "default" | "travel" | "work" | "photos" | "videos"; onChange: (value: "default" | "travel" | "work" | "photos" | "videos") => void }) {
  const options = [{ type: "default" as const, label: "📁" }, { type: "travel" as const, label: "🌴" }, { type: "work" as const, label: "💼" }, { type: "photos" as const, label: "📷" }, { type: "videos" as const, label: "🎬" }];
  return <div className="icon-picker-row">{options.map((option) => <button key={option.type} type="button" className={`icon-picker-btn ${value === option.type ? "icon-picker-btn--active" : ""}`} onClick={() => onChange(option.type)} aria-label={`选择${option.type}图标`}>{option.label}</button>)}</div>;
}

export function ImportSourcePicker({ value, onChange }: { value: "local" | "nas" | "cloud"; onChange: (value: "local" | "nas" | "cloud") => void }) {
  const options = [{ key: "local" as const, label: "本地" }, { key: "nas" as const, label: "NAS" }, { key: "cloud" as const, label: "云盘" }];
  return <div className="import-source-picker">{options.map((option) => <button key={option.key} type="button" className={`icon-picker-btn ${value === option.key ? "icon-picker-btn--active" : ""}`} onClick={() => onChange(option.key)}>{option.label}</button>)}</div>;
}
