import type { FolderIconType } from "./useLibrary";

export function FolderIcon({ type }: { type?: FolderIconType | undefined }) {
  const common = { className: "folder-card__icon", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.5 };
  if (type === "work") return <svg {...common}><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>;
  if (type === "photos") return <svg {...common}><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>;
  if (type === "videos") return <svg {...common}><rect x="2" y="2" width="20" height="20" rx="2"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/></svg>;
  if (type === "travel") return <svg {...common}><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/></svg>;
  return <svg {...common}><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>;
}

export function FileIcon({ fileName, category }: { fileName: string; category?: string | undefined }) {
  const extension = fileName.split(".").pop()?.toLowerCase();
  const color = category === "image" ? "#10b981" : category === "video" ? "#f59e0b" : extension === "pdf" ? "#ef4444" : ["doc", "docx"].includes(extension ?? "") ? "#3b82f6" : "#9ca3af";
  if (category === "image") return <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>;
  if (category === "video") return <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>;
  return <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/></svg>;
}
