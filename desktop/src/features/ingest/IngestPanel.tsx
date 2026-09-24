import React, { useState } from "react";
import { useTranslation } from "../../i18n/useTranslation";
import { defaultClient } from "../../api/client";

interface PendingImportFile {
  id: string;
  name: string;
  path: string;
  size: string;
  status: "pending" | "uploading" | "success" | "failed";
}

export function IngestPanel() {
  const { t } = useTranslation();
  
  const [dragActive, setDragActive] = useState(false);
  const [pendingQueue, setPendingQueue] = useState<PendingImportFile[]>([]);
  const [importResult, setImportResult] = useState<{ accepted: number; skipped: number } | null>(null);
  const [busy, setBusy] = useState(false);

  // Simulated drag handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const addFilesToQueue = (fileList: Array<{ name: string; path: string; size: string }>) => {
    const nextFiles: PendingImportFile[] = fileList.map((f, idx) => ({
      id: `pending-${Date.now()}-${idx}`,
      name: f.name,
      path: f.path,
      size: f.size,
      status: "pending",
    }));

    setPendingQueue([...nextFiles, ...pendingQueue]);
    setImportResult(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const items: Array<{ name: string; path: string; size: string }> = [];
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        const file = e.dataTransfer.files[i];
        if (!file) continue;
        // Use standard placeholder paths since web drops don't expose full local paths for security,
        // but fully compatible with Tauri drops.
        items.push({
          name: file.name,
          path: `/Users/lkkings/Desktop/${file.name}`,
          size: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
        });
      }
      addFilesToQueue(items);
    }
  };

  const handleManualBrowse = () => {
    // Simulates choosing standard local files
    const sampleFiles = [
      { name: "2026年Q3发展大纲.pdf", path: "/Users/lkkings/Documents/2026年Q3发展大纲.pdf", size: "1.2 MB" },
      { name: "海边日出.jpg", path: "/Users/lkkings/Pictures/海边日出.jpg", size: "4.2 MB" },
      { name: "猫咪奔跑.mp4", path: "/Users/lkkings/Videos/猫咪奔跑.mp4", size: "124.3 MB" },
      { name: "未知数据格式.raw", path: "/Users/lkkings/Data/未知数据格式.raw", size: "890 KB" }, // Will be skipped as unsupported
    ];
    addFilesToQueue(sampleFiles);
  };

  const handleRemove = (id: string) => {
    setPendingQueue(pendingQueue.filter((f) => f.id !== id));
  };

  const handleStartImport = async () => {
    if (pendingQueue.length === 0 || busy) return;
    setBusy(true);

    const paths = pendingQueue.map((f) => f.path);
    
    try {
      const response = await defaultClient.post<{ accepted: number; skipped: number; task_ids: string[] }>("/ingest", {
        paths,
        interactive: true,
      });

      if (response.status === "success" && response.data) {
        setImportResult({
          accepted: response.data.accepted,
          skipped: response.data.skipped,
        });
        setPendingQueue([]);
        
        // Dispatches a global event so the sidebar task counts reload
        window.dispatchEvent(new CustomEvent("mock-tasks-updated"));
      } else {
        alert(response.error || "导入失败");
      }
    } catch (err) {
      const error = err as { message?: string };
      alert("无法提交入库任务：" + (error.message || "Unknown error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ingest-panel">
      <h1 className="ingest-panel__title">{t("ingest.title")}</h1>

      {/* Drag & Drop Upload Container */}
      <div
        className={`ingest-panel__drop-zone ${dragActive ? "ingest-panel__drop-zone--active" : ""}`}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" width="80" height="80">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <p className="drop-zone-text">
          {t("ingest.dragArea")}{" "}
          <button type="button" className="browse-link" onClick={handleManualBrowse}>
            {t("ingest.browse")}
          </button>
        </p>
        <span className="supported-formats-hint">
          {t("settings.search")} (PDF, DOCX, TXT, MD, PNG, JPG, MP4, MOV)
        </span>
      </div>

      {/* Import Source Options */}
      <div className="ingest-panel__sources">
        <button type="button" className="source-card" onClick={handleManualBrowse}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
            <line x1="8" y1="21" x2="16" y2="21" />
            <line x1="12" y1="17" x2="12" y2="21" />
          </svg>
          <span>{t("ingest.local")}</span>
        </button>
        <button type="button" className="source-card" onClick={() => alert(t("ingest.camera"))}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
          <span>{t("ingest.camera")}</span>
        </button>
        <button type="button" className="source-card" onClick={() => alert(t("ingest.cloud"))}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
          <span>{t("ingest.cloud")}</span>
        </button>
      </div>

      {/* Result feedback */}
      {importResult && (
        <div className="ingest-feedback" role="alert">
          <div className="ingest-feedback__success">
            {t("ingest.accepted", { count: importResult.accepted })}
          </div>
          {importResult.skipped > 0 && (
            <div className="ingest-feedback__skipped">
              {t("ingest.skipped", { count: importResult.skipped })}
            </div>
          )}
        </div>
      )}

      {/* Pending Files Queue */}
      {pendingQueue.length > 0 && (
        <div className="ingest-panel__queue-section">
          <div className="ingest-panel__queue-header">
            <h2>{t("ingest.queue")} ({pendingQueue.length})</h2>
            <button
              type="button"
              className="theme-btn"
              onClick={handleStartImport}
              disabled={busy}
            >
              {busy ? t("settings.nasTesting") : t("ingest.start")}
            </button>
          </div>
          <div className="ingest-queue-list">
            {pendingQueue.map((file) => (
              <div key={file.id} className="ingest-queue-item">
                <div className="ingest-queue-item__meta">
                  <div className="ingest-queue-item__name">{file.name}</div>
                  <div className="ingest-queue-item__path">{file.path}</div>
                </div>
                <div className="ingest-queue-item__size">{file.size}</div>
                <button
                  type="button"
                  className="ingest-queue-item__remove-btn"
                  onClick={() => handleRemove(file.id)}
                  disabled={busy}
                >
                  {t("ingest.remove")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
export default IngestPanel;
