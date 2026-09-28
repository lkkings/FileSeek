import { useTranslate } from "../../../i18n/useTranslate";
import { getDocumentFormat, getFileExtension } from "../preview";
import "./DocumentFormatIcon.css";

export type DocumentIconVariant =
  | "pdf"
  | "word"
  | "sheet"
  | "slides"
  | "text"
  | "code"
  | "data"
  | "markup"
  | "legacy";

const variantByExtension: Record<string, DocumentIconVariant> = {
  pdf: "pdf",
  doc: "legacy",
  docx: "word",
  xls: "legacy",
  xlsx: "sheet",
  ppt: "legacy",
  pptx: "slides",
  rtf: "legacy",
  odt: "legacy",
  ods: "legacy",
  odp: "legacy",
  csv: "data",
  md: "text",
  markdown: "text",
  txt: "text",
  log: "text",
  html: "markup",
  htm: "markup",
  xml: "markup",
  json: "data",
  yaml: "data",
  yml: "data",
  toml: "data",
  ini: "data",
  js: "code",
  jsx: "code",
  ts: "code",
  tsx: "code",
  css: "code",
  py: "code",
  rs: "code",
  java: "code",
  c: "code",
  h: "code",
  cpp: "code",
  cs: "code",
  go: "code",
  rb: "code",
  php: "code",
  sh: "code",
  sql: "code",
};

export interface DocumentFormatIconProps {
  fileName: string;
  isUnsupported?: boolean;
}

export function DocumentFormatIcon({ fileName, isUnsupported = false }: DocumentFormatIconProps) {
  const format = getDocumentFormat(fileName);
  const extension = getFileExtension(fileName);
  const variant = variantByExtension[extension] ?? "text";
  const t = useTranslate();
  const label = t("preview.documentFormat", "{format} 文档", { format });
  const unsupportedLabel = t("preview.documentUnsupported", "{format} 文档（不支持预览）", { format });

  return (
    <span
      className={`document-format-icon document-format-${variant}${isUnsupported ? " is-unsupported" : ""}`}
      role="img"
      aria-label={isUnsupported ? unsupportedLabel : label}
    >
      <span className="document-format-label">{format}</span>
    </span>
  );
}
