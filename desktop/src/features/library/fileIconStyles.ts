import type { CSSProperties } from "react";

export function thumbnailStyle(fileName: string, category?: string | undefined): CSSProperties {
  if (category === "image") return { background: fileName.includes("猫") ? "linear-gradient(135deg,#ff9a9e,#fecfef)" : "linear-gradient(135deg,#f6d365,#fda085)" };
  if (category === "video") return { background: "linear-gradient(135deg,#30cfd0,#33086f)" };
  const extension = fileName.split(".").pop()?.toLowerCase();
  if (extension === "pdf") return { background: "linear-gradient(135deg,#fee2e2,#fca5a5)" };
  if (["doc", "docx"].includes(extension ?? "")) return { background: "linear-gradient(135deg,#dbeafe,#93c5fd)" };
  return { background: "linear-gradient(135deg,#f3f4f6,#d1d5db)" };
}
