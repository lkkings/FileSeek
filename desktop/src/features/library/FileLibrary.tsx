import { useState } from "react";
import { useTranslation } from "../../i18n/useTranslation";
import { FilePreviewModal } from "../../components/ui/FilePreviewModal";
import { recordAccess } from "../../api/library";
import { defaultClient, type ApiClient } from "../../api/client";
import {
  useLibrary,
  type FileItem,
  type FolderIconType,
  type FolderItem,
} from "./useLibrary";
import { filterFiles, sortFiles } from "./model";
import { RecycleBinView } from "./components/RecycleBinView";
import { FileListView } from "./components/FileListView";
import { FolderGrid } from "./components/FolderGrid";

interface FileLibraryProps {
  viewType: "all" | "recycle";
  selectedFolder?: string | null;
  onSelectFolder?: (folder: string | null) => void;
  onOpenImport?: () => void;
  activeCategory?: "all" | "document" | "image" | "video";
  searchQuery?: string | null;
  filterName?: string;
  filterMinSize?: string;
  filterMaxSize?: string;
  filterStartDate?: string;
  filterEndDate?: string;
  /** 覆盖用的客户端，只给测试用。 */
  client?: ApiClient;
}


/**
 * 各来源的路径示例。
 *
 * 来源不是一个独立的参数：后端 `FileSystemFactory` 只看路径前缀——`cloud://` 走云盘，
 * `smb://`/`webdav://`/`nfs://` 走 NAS，其余按本地路径处理。所以这个选择器只是给用户
 * 提示该填什么格式。
 */
const IMPORT_PATH_HINTS = {
  local: "例如: /Users/you/Documents/财务审计.xlsx",
  nas: "例如: smb://192.168.1.100/share/报告.pdf",
  cloud: "例如: cloud://aliyun/Documents/报告.pdf",
} as const;

export function FileLibrary({
  viewType,
  selectedFolder: initialSelectedFolder = null,
  onSelectFolder,
  activeCategory = "all",
  searchQuery = null,
  filterName = "",
  filterMinSize = "",
  filterMaxSize = "",
  filterStartDate = "",
  filterEndDate = "",
  client,
}: FileLibraryProps) {
  const { t } = useTranslation();

  // Selected folder tracking inside FileLibrary (allows entering folder natively)
  const [prevSelectedFolder, setPrevSelectedFolder] = useState<string | null>(initialSelectedFolder);
  const [currentFolder, setCurrentFolder] = useState<string | null>(initialSelectedFolder);

  if (initialSelectedFolder !== prevSelectedFolder) {
    setPrevSelectedFolder(initialSelectedFolder);
    setCurrentFolder(initialSelectedFolder);
  }
  
  // 后端状态。文件夹/文件/回收站都由这个 hook 负责读写（见 useLibrary.ts）。
  const library = useLibrary({ currentFolder, viewType, client });
  const { folders, files, recycle } = library;

  // Folder Pagination State
  const [folderPage, setFolderPage] = useState(1);
  const folderPageSize = 3;

  // File sorting and layout state
  const [sortBy, setSortBy] = useState<"name" | "size" | "time">("name");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [layoutMode, setLayoutMode] = useState<"list" | "grid">("list");

  // Selection states for files (Point select & batch operations)
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);

  // Add Folder Modal State (advanced form)
  const [createFolderOpen, setCreateFolderOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [newFolderIcon, setNewFolderIcon] = useState<FolderIconType>("default");
  const [newFolderDesc, setNewFolderDesc] = useState("");

  // Edit Folder Properties Modal State
  const [editFolderOpen, setEditFolderOpen] = useState(false);
  const [editingFolderId, setEditingFolderId] = useState("");
  const [editName, setEditName] = useState("");
  const [editIcon, setEditIcon] = useState<FolderIconType>("default");
  const [editDesc, setEditDesc] = useState("");

  // Add Files Modal State
  const [addFilesOpen, setAddFilesOpen] = useState(false);
  const [importSource, setImportSource] = useState<"local" | "nas" | "cloud">("local");
  const [importPathInput, setImportPathInput] = useState("");

  // File Previewer Modal State
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);

  /** 写操作的失败文案。成功时清空，失败时显示在顶部横幅里。 */
  const actionError = library.error;

  // Synchronize currentFolder choice back to parent
  const handleSelectFolder = (folderName: string | null) => {
    setCurrentFolder(folderName);
    setSelectedFileIds([]); // Clear selection upon changing folders
    if (onSelectFolder) {
      onSelectFolder(folderName);
    }
  };

  /** 打开预览，同时记一次访问——"最近访问"列表靠它才有内容。 */
  const handleOpenPreview = (file: FileItem) => {
    setPreviewFile(file);
    void recordAccess(file.id, client ?? defaultClient);
  };

  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;

    const failure = await library.createFolder({
      name: newFolderName.trim(),
      iconType: newFolderIcon,
      description: newFolderDesc,
    });
    if (failure) {
      library.setError(failure);
      return;
    }

    setNewFolderName("");
    setNewFolderIcon("default");
    setNewFolderDesc("");
    setCreateFolderOpen(false);
  };

  const handleCleanRecycle = async () => {
    if (!window.confirm(t("lib.cleanRecycleConfirm"))) return;
    const failure = await library.emptyRecycleBin();
    if (failure) library.setError(failure);
  };

  const handleRestore = async (id: string) => {
    const failure = await library.restoreItem(id);
    if (failure) library.setError(failure);
  };

  const handlePermanentDelete = async (id: string) => {
    const failure = await library.deleteItemPermanently(id);
    if (failure) library.setError(failure);
  };

  // Launch edit drawer dialog
  const handleOpenEditFolder = (folder: FolderItem) => {
    setEditingFolderId(folder.id);
    setEditName(folder.name);
    setEditIcon(folder.iconType);
    setEditDesc(folder.description);
    setEditFolderOpen(true);
  };

  const handleSaveFolderEdits = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editName.trim()) return;

    const renamedFrom = folders.find((folder) => folder.id === editingFolderId)?.name;

    const failure = await library.updateFolder(editingFolderId, {
      name: editName.trim(),
      iconType: editIcon,
      description: editDesc,
    });
    if (failure) {
      library.setError(failure);
      return;
    }

    // 当前视图是按名字定位文件夹的（父级 App 也是），改了名要跟着换，
    // 否则会停在一个已经不存在的名字上，文件列表变空。
    if (renamedFrom && renamedFrom === currentFolder && renamedFrom !== editName.trim()) {
      handleSelectFolder(editName.trim());
    }

    setEditFolderOpen(false);
  };

  // Interactive deletion of a folder (empty check mandated)
  const handleDeleteFolder = async (folderId: string, folderName: string) => {
    if (!window.confirm(`确定要删除文件夹 "${folderName}" 吗？`)) return;

    // 非空文件夹由后端拒绝（`Folder.ensure_can_delete`），文案直接透给用户——
    // 前端不重复判断，那样会因为分页只加载了一部分文件而判错。
    const failure = await library.deleteFolder(folderId);
    if (failure) {
      library.setError(failure);
      return;
    }

    const remaining = folders.length - 1;
    const nextMaxPages = Math.ceil(remaining / folderPageSize) || 1;
    if (folderPage > nextMaxPages) {
      setFolderPage(nextMaxPages);
    }
  };

  /**
   * 导入一个文件到当前文件夹。
   *
   * 后端一次只收一个文件（`POST /library/files` 的 `FileImportRequest`），而且是把源文件
   * **移动**进库目录。批量导入需要后端能枚举目录，`FileSystemPort` 目前没有这个能力，
   * 所以这里按单个文件处理。
   */
  const handleAddFilesSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const failure = await library.addFile(importPathInput);
    if (failure) {
      library.setError(failure);
      return;
    }

    setImportPathInput("");
    setAddFilesOpen(false);
  };

  /** 删单个文件。走的还是批量删除接口——后端只有这一个入口。 */
  const handleDeleteOneFile = async (file: FileItem) => {
    if (!window.confirm(`确定要删除文件 "${file.name}" 吗？`)) return;

    const failure = await library.deleteFiles([file.id]);
    if (failure) {
      library.setError(failure);
      return;
    }
    setSelectedFileIds(selectedFileIds.filter((id) => id !== file.id));
  };

  // Toggle selection checkbox for single file
  const handleToggleSelectFile = (fileId: string) => {
    if (selectedFileIds.includes(fileId)) {
      setSelectedFileIds(selectedFileIds.filter((id) => id !== fileId));
    } else {
      setSelectedFileIds([...selectedFileIds, fileId]);
    }
  };

  // Batch delete selected files
  const handleBatchDeleteFiles = async () => {
    if (selectedFileIds.length === 0) return;
    if (!window.confirm(t("lib.deleteFileConfirm", { count: selectedFileIds.length.toString() }))) {
      return;
    }

    const failure = await library.deleteFiles(selectedFileIds);
    if (failure) {
      library.setError(failure);
      return;
    }
    setSelectedFileIds([]);
  };

  /*
    switch (iconType) {
      case "travel":
        return (
          <svg className="folder-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
            <path d="M2 12h20" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
        );
      case "work":
        return (
          <svg className="folder-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
            <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
          </svg>
        );
      case "photos":
        return (
          <svg className="folder-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
        );
      case "videos":
        return (
          <svg className="folder-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
            <line x1="7" y1="2" x2="7" y2="22" />
            <line x1="17" y1="2" x2="17" y2="22" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <line x1="2" y1="7" x2="7" y2="7" />
            <line x1="2" y1="17" x2="7" y2="17" />
            <line x1="17" y1="17" x2="22" y2="17" />
            <line x1="17" y1="7" x2="22" y2="7" />
          </svg>
        );
      default:
        return (
          <svg className="folder-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        );
    }
  */

  // Maps individual file types to SVGs (coloured by category)
  /*
    const ext = fileName.split(".").pop()?.toLowerCase();
    
    if (mediaType === "image") {
      return (
        <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#10b981" }}>
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
      );
    }
    if (mediaType === "video") {
      return (
        <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#f59e0b" }}>
          <polygon points="23 7 16 12 23 17 23 7" />
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
        </svg>
      );
    }

    switch (ext) {
      case "pdf":
        return (
          <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#ef4444" }}>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
            <path d="M9 15h3a1.5 1.5 0 0 0 0-3H9v6" />
          </svg>
        );
      case "doc":
      case "docx":
        return (
          <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#3b82f6" }}>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="8" y1="13" x2="16" y2="13" />
            <line x1="8" y1="17" x2="14" y2="17" />
          </svg>
        );
      case "xls":
      case "xlsx":
      case "csv":
        return (
          <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#10b981" }}>
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="9" y1="3" x2="9" y2="21" />
            <line x1="3" y1="9" x2="21" y2="9" />
            <line x1="3" y1="15" x2="21" y2="15" />
          </svg>
        );
      case "ppt":
      case "pptx":
        return (
          <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#f97316" }}>
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
        );
      case "md":
        return (
          <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#06b6d4" }}>
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <path d="M7 15V9l3.5 3 3.5-3v6" />
            <path d="M18 11.5l-1.5-1.5m0 0L15 11.5m1.5-1.5V15" />
          </svg>
        );
      case "txt":
        return (
          <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#6b7280" }}>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="8" y1="13" x2="16" y2="13" />
            <line x1="8" y1="17" x2="12" y2="17" />
          </svg>
        );
      case "js":
      case "ts":
      case "tsx":
      case "py":
      case "json":
      case "html":
      case "css":
      case "rs":
      case "sh":
        return (
          <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#a855f7" }}>
            <polyline points="16 18 22 12 16 6" />
            <polyline points="8 6 2 12 8 18" />
          </svg>
        );
      default:
        return (
          <svg className="file-library__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#9ca3af" }}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        );
    }
    */
  // Simulated visual glassmorphic thumbnails based on selection
  /*
    if (mediaType === "image") {
      if (fileName.includes("猫")) {
        return { background: "linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%)" };
      }
      if (fileName.includes("毕业")) {
        return { background: "linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)" };
      }
      if (fileName.includes("大理")) {
        return { background: "linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)" };
      }
      return { background: "linear-gradient(135deg, #f6d365 0%, #fda085 100%)" };
    }
    if (mediaType === "video") {
      if (fileName.includes("骑行")) {
        return { background: "linear-gradient(135deg, #30cfd0 0%, #33086f 100%)" };
      }
      if (fileName.includes("猫咪")) {
        return { background: "linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)" };
      }
      return { background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" };
    }
    
    const ext = fileName.split(".").pop()?.toLowerCase();
    switch (ext) {
      case "pdf": return { background: "linear-gradient(135deg, #fee2e2 0%, #fca5a5 100%)" };
      case "doc":
      case "docx": return { background: "linear-gradient(135deg, #dbeafe 0%, #93c5fd 100%)" };
      case "xls":
      case "xlsx": return { background: "linear-gradient(135deg, #d1fae5 0%, #86efac 100%)" };
      case "ppt":
      case "pptx": return { background: "linear-gradient(135deg, #ffedd5 0%, #fdba74 100%)" };
      case "md": return { background: "linear-gradient(135deg, #ecfeff 0%, #67e8f9 100%)" };
      case "txt": return { background: "linear-gradient(135deg, #f3f4f6 0%, #d1d5db 100%)" };
      case "js":
      case "ts":
      case "tsx":
      case "py":
      case "json":
      case "html":
      case "css":
      case "rs":
      case "sh": return { background: "linear-gradient(135deg, #faf5ff 0%, #d8b4fe 100%)" };
      default: return { background: "linear-gradient(135deg, #f9fafb 0%, #e5e7eb 100%)" };
    }
  */
  if (viewType === "recycle") {
    // Filter Recycle Bin items based on globally passed activeCategory
    const displayedRecycle = activeCategory === "all"
      ? recycle
      : recycle.filter((i) => i.category === activeCategory);

    return <RecycleBinView items={displayedRecycle} error={actionError} onEmpty={handleCleanRecycle} onRestore={handleRestore} onDelete={handlePermanentDelete} />;
  }

  // Active folder detail matching
  const activeFolderItem = currentFolder
    ? folders.find((folder) => folder.name === currentFolder)
    : null;

  // 文件列表已经由后端按当前文件夹取好了（`GET /library/files?folder=`），这里只做
  // 分类和搜索/高级筛选——那几项是纯前端的即时筛选，没有对应的后端参数。
  const displayedFiles = filterFiles(files, {
    activeCategory,
    searchQuery,
    filterName,
    filterMinSize,
    filterMaxSize,
    filterStartDate,
    filterEndDate,
  });
  /*
  const displayedFilesLegacy = files.filter((item) => {
    if (activeCategory !== "all" && item.category !== activeCategory) return false;

    // Filter by search query (case-insensitive substring check)
    if (searchQuery) {
      const queryLower = searchQuery.toLowerCase();
      if (!item.name.toLowerCase().includes(queryLower)) return false;
    }

    // Filter by advanced filter: filename
    if (filterName) {
      const nameLower = filterName.toLowerCase();
      if (!item.name.toLowerCase().includes(nameLower)) return false;
    }

    // Filter by advanced filter: size range (converted to MB equivalents)
    if (filterMinSize) {
      const minVal = parseFloat(filterMinSize);
      if (item.sizeBytes / (1024 * 1024) < minVal) return false;
    }
    if (filterMaxSize) {
      const maxVal = parseFloat(filterMaxSize);
      if (item.sizeBytes / (1024 * 1024) > maxVal) return false;
    }

    // Filter by advanced filter: date range
    if (filterStartDate) {
      const itemDateStr = item.modified.substring(0, 10);
      if (itemDateStr < filterStartDate) return false;
    }
    if (filterEndDate) {
      const itemDateStr = item.modified.substring(0, 10);
      if (itemDateStr > filterEndDate) return false;
    }

    return true;
  }); */

  // Apply Sorting algorithms sequentially
  const sortedFiles = sortFiles(displayedFiles, sortBy, sortOrder);
  /*
  const sortedFilesLegacy = [...displayedFiles].sort((a, b) => {
    let comparison = 0;
    if (sortBy === "name") {
      comparison = a.name.localeCompare(b.name, "zh-CN");
    } else if (sortBy === "size") {
      comparison = a.sizeBytes - b.sizeBytes;
    } else if (sortBy === "time") {
      comparison = new Date(a.modified).getTime() - new Date(b.modified).getTime();
    }
    return sortOrder === "asc" ? comparison : -comparison;
  }); */

  // Folders list pagination calculations
  const totalFolderPages = Math.ceil(folders.length / folderPageSize) || 1;
  const clampedFolderPage = Math.min(folderPage, totalFolderPages);

  const paginatedFolders = folders.slice(
    (clampedFolderPage - 1) * folderPageSize,
    clampedFolderPage * folderPageSize
  );

  return (
    <div className="file-library" style={{ width: "100%" }}>
      {/* Dynamic Header based on root vs sub-folder detail level */}
      <div className="file-library__header" style={{ flexDirection: "column", alignItems: "flex-start", gap: "8px" }}>
        
        {/* Navigation Breadcrumb back path */}
        {currentFolder && (
          <button type="button" className="action-link-btn" onClick={() => handleSelectFolder(null)} style={{ fontSize: "13px", display: "flex", alignItems: "center", gap: "4px" }}>
            &larr; {t("lib.backToLib")}
          </button>
        )}

        <div className="file-library__header-row" style={{ display: "flex", width: "100%", justifyContent: currentFolder ? "space-between" : "flex-end", alignItems: "center", marginTop: "4px" }}>
          {currentFolder && (
            <h1 className="file-library__title" style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              {currentFolder}
              {activeFolderItem && (
                <button
                  type="button"
                  className="results-btn"
                  onClick={() => handleOpenEditFolder(activeFolderItem)}
                  title={t("lib.editFolder")}
                  style={{ borderRadius: "var(--radius-full)", width: "28px", height: "28px" }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="13" height="14">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
              )}
            </h1>
          )}

          <div className="file-library__header-actions" style={{ display: "flex", gap: "10px" }}>
            {/* Folder creation strictly rendered at Root level. Import Files button removed as requested. */}
            {!currentFolder ? (
              <button type="button" className="theme-btn" onClick={() => setCreateFolderOpen(true)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14" style={{ marginRight: "6px" }}>
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                {t("lib.createFolder")}
              </button>
            ) : (
              // Add Files Button inside sub-folders
              <button type="button" className="theme-btn" onClick={() => setAddFilesOpen(true)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14" style={{ marginRight: "6px" }}>
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                {t("lib.addFiles")}
              </button>
            )}
          </div>
        </div>

        {/* Render Folder description if viewing sub-folder */}
        {currentFolder && activeFolderItem && activeFolderItem.description && (
          <p className="folder-description-text" style={{ color: "var(--text-secondary)", fontSize: "13.5px", marginTop: "4px", lineHeight: "1.5" }}>
            {activeFolderItem.description}
          </p>
        )}
      </div>

      {actionError && <div className="library-error-banner" role="alert">{actionError}</div>}

      {/* VIEW LEVEL 1: Root Page (No active folder selected): Render ONLY Folders grid, absolutely no files list! */}
      {!currentFolder ? (
        <div className="file-library__section" style={{ marginTop: "16px" }}>
          <div className="file-library__section-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            <span className="file-library__section-header-label">全部文件</span>
            <span className="file-library__section-header-count">{folders.length}</span>
          </div>
          {!library.loading && folders.length === 0 && (
            <div className="file-library__empty">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <p>还没有文件夹，先建一个吧</p>
            </div>
          )}
          <FolderGrid folders={paginatedFolders} onOpen={handleSelectFolder} onEdit={handleOpenEditFolder} onDelete={handleDeleteFolder} />
          {/* Legacy folder markup removed; FolderGrid owns this rendering. */}
          {/*
            <div key="legacy-folder-markup" />
                <div className="folder-card__header-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", width: "100%" }}>
                  <div style={{ display: "flex", gap: "6px" }}>
                    <button
                      type="button"
                      className="results-btn"
                      onClick={(e) => { e.stopPropagation(); handleOpenEditFolder(folder); }}
                      title={t("lib.editFolder")}
                      style={{ width: "38px", height: "38px", opacity: 0.82, background: "rgba(24,57,111,.55)", border: "1px solid #245496", borderRadius: "9px" }}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                    </button>
                    Folder Deletion icon trigger
                    <button
                      type="button"
                      className="results-btn action-link-btn--danger"
                      onClick={(e) => { e.stopPropagation(); handleDeleteFolder(folder.id, folder.name); }}
                      title={t("lib.deleteFolder")}
                      aria-label="🗑"
                      style={{ width: "38px", height: "38px", padding: 0, opacity: 0.82, background: "rgba(24,57,111,.55)", border: "1px solid #245496", borderRadius: "9px", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                        <path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 15H6L5 6" /><path d="M10 11v6M14 11v6" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      className="results-btn folder-card__more"
                      onClick={(e) => e.stopPropagation()}
                      aria-label="更多操作"
                      style={{ width: "38px", height: "38px", opacity: 0.82, background: "rgba(24,57,111,.55)", border: "1px solid #245496", borderRadius: "9px" }}
                    >
                      <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><circle cx="12" cy="5" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="12" cy="19" r="1.6" /></svg>
                    </button>
                  </div>
                </div>
                <div className="folder-card__title" title={folder.name} style={{ marginTop: "12px" }}>{folder.name}</div>
                {folder.description && (
                  <p className="folder-card__desc" title={folder.description} style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: "1.4" }}>
                    {folder.description}
                  </p>
                )}
                <div className="folder-card__meta" style={{ marginTop: "auto", paddingTop: "8px" }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
                  {folder.modified}
                </div>
              </div>
          */}

          {/* Folder Pagination Controls */}
          {totalFolderPages > 1 && (
            <div className="folders-pagination-row">
              <button
                type="button"
                className="pagination-btn"
                onClick={() => setFolderPage(clampedFolderPage - 1)}
                disabled={clampedFolderPage === 1}
              >
                &larr; {t("lib.prevPage")}
              </button>
              <span className="pagination-indicator">
                {t("lib.pageIndicator", { current: clampedFolderPage.toString(), total: totalFolderPages.toString() })}
              </span>
              <button
                type="button"
                className="pagination-btn"
                onClick={() => setFolderPage(clampedFolderPage + 1)}
                disabled={clampedFolderPage === totalFolderPages}
              >
                {t("lib.nextPage")} &rarr;
              </button>
            </div>
          )}
        </div>
      ) : (
        /* VIEW LEVEL 2: Sub-folder Detail View (Active folder selected): Render Files view, with Inline Toolbar! */
        <div className="file-library__section" style={{ marginTop: "16px" }}>
          
          {/* Inline Toolbar for Sorting, Layout Options and Batch Deletion */}
          <div className="library-toolbar">
            <div className="library-toolbar__left">
              {/* Sorting Select and Direction arrow */}
              <div className="sort-selector-container">
                <span>{t("lib.sortBy")}:</span>
                <select
                  className="theme-select"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as "name" | "size" | "time")}
                >
                  <option value="name">{t("lib.sortByName")}</option>
                  <option value="size">{t("lib.sortBySize")}</option>
                  <option value="time">{t("lib.sortByTime")}</option>
                </select>
                <button
                  type="button"
                  className="sort-direction-btn"
                  onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
                  title={sortOrder === "asc" ? "升序" : "降序"}
                >
                  {sortOrder === "asc" ? "↑" : "↓"}
                </button>
              </div>

              {/* Batch Deletion Trigger button displayed only when files are checked */}
              {selectedFileIds.length > 0 && (
                <button
                  type="button"
                  className="theme-btn theme-btn--danger"
                  onClick={handleBatchDeleteFiles}
                  style={{ display: "flex", alignItems: "center", padding: "4px 12px", fontSize: "12.5px" }}
                >
                  🗑 {t("lib.batchDelete")} ({selectedFileIds.length})
                </button>
              )}
            </div>

            <div className="library-toolbar__right">
              {/* Layout Toggle Button Group */}
              <div className="layout-toggle-group">
                <button
                  type="button"
                  className={`layout-toggle-btn ${layoutMode === "list" ? "layout-toggle-btn--active" : ""}`}
                  onClick={() => setLayoutMode("list")}
                  title={t("lib.layoutList")}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                    <line x1="8" y1="6" x2="21" y2="6" />
                    <line x1="8" y1="12" x2="21" y2="12" />
                    <line x1="8" y1="18" x2="21" y2="18" />
                    <line x1="3" y1="6" x2="3.01" y2="6" />
                    <line x1="3" y1="12" x2="3.01" y2="12" />
                    <line x1="3" y1="18" x2="3.01" y2="18" />
                  </svg>
                </button>
                <button
                  type="button"
                  className={`layout-toggle-btn ${layoutMode === "grid" ? "layout-toggle-btn--active" : ""}`}
                  onClick={() => setLayoutMode("grid")}
                  title={t("lib.layoutGrid")}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                    <rect x="3" y="3" width="7" height="7" />
                    <rect x="14" y="3" width="7" height="7" />
                    <rect x="14" y="14" width="7" height="7" />
                    <rect x="3" y="14" width="7" height="7" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          {sortedFiles.length === 0 ? (
            <div className="file-library__empty" style={{ padding: "60px var(--space-md)" }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <p>{t("lib.emptyFolder")}</p>
            </div>
          ) : (
            <FileListView
              files={sortedFiles}
              layout={layoutMode}
              selectedIds={selectedFileIds}
              allSelected={sortedFiles.length > 0 && sortedFiles.every((file) => selectedFileIds.includes(file.id))}
              onSelectAll={(checked) => setSelectedFileIds(checked ? sortedFiles.map((file) => file.id) : [])}
              onToggle={handleToggleSelectFile}
              onPreview={handleOpenPreview}
              onDelete={(file) => { void handleDeleteOneFile(file); }}
            />
          )}
        </div>
      )}

      {/* Modal 1: Advanced Create Folder Modal (Supports Icon Selector and Description textarea) */}
      {createFolderOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={() => setCreateFolderOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{t("lib.createFolderTitle")}</h2>
              <button type="button" className="modal-close" onClick={() => setCreateFolderOpen(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleCreateFolder}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div className="form-group">
                  <label htmlFor="folderName">{t("lib.folderName")}</label>
                  <input
                    type="text"
                    id="folderName"
                    className="theme-input"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    placeholder={t("lib.folderName")}
                    autoFocus
                    required
                  />
                </div>

                <div className="form-group">
                  <label>{t("lib.folderIcon")}</label>
                  <div className="icon-picker-row" style={{ display: "flex", gap: "10px", marginTop: "6px" }}>
                    {[
                      { type: "default" as const, label: "📁" },
                      { type: "travel" as const, label: "🌴" },
                      { type: "work" as const, label: "💼" },
                      { type: "photos" as const, label: "📷" },
                      { type: "videos" as const, label: "🎬" },
                    ].map((iconObj) => (
                      <button
                        key={iconObj.type}
                        type="button"
                        className={`icon-picker-btn ${newFolderIcon === iconObj.type ? "icon-picker-btn--active" : ""}`}
                        onClick={() => setNewFolderIcon(iconObj.type)}
                        style={{
                          width: "36px",
                          height: "36px",
                          borderRadius: "var(--radius-md)",
                          fontSize: "18px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          border: newFolderIcon === iconObj.type ? "2px solid var(--accent-primary)" : "1px solid var(--border-color)",
                          backgroundColor: newFolderIcon === iconObj.type ? "var(--accent-light)" : "transparent",
                          cursor: "pointer",
                        }}
                      >
                        {iconObj.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="folderDesc">{t("lib.folderDesc")}</label>
                  <textarea
                    id="folderDesc"
                    className="theme-input"
                    value={newFolderDesc}
                    onChange={(e) => setNewFolderDesc(e.target.value)}
                    placeholder="添加该文件夹的简要描述和用途说明（可选）..."
                    rows={4}
                    style={{ resize: "none", fontFamily: "inherit" }}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="theme-btn theme-btn--outline" onClick={() => setCreateFolderOpen(false)}>
                  {t("lib.cancel")}
                </button>
                <button type="submit" className="theme-btn">
                  {t("lib.confirm")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Edit Folder Details Modal (Name, Icon, Description) */}
      {editFolderOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={() => setEditFolderOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{t("lib.editFolder")}</h2>
              <button type="button" className="modal-close" onClick={() => setEditFolderOpen(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleSaveFolderEdits}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div className="form-group">
                  <label htmlFor="editFolderName">{t("lib.folderName")}</label>
                  <input
                    type="text"
                    id="editFolderName"
                    className="theme-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    required
                    autoFocus
                  />
                </div>

                <div className="form-group">
                  <label>{t("lib.folderIcon")}</label>
                  <div className="icon-picker-row" style={{ display: "flex", gap: "10px", marginTop: "6px" }}>
                    {[
                      { type: "default" as const, label: "📁" },
                      { type: "travel" as const, label: "🌴" },
                      { type: "work" as const, label: "💼" },
                      { type: "photos" as const, label: "📷" },
                      { type: "videos" as const, label: "🎬" },
                    ].map((iconObj) => (
                      <button
                        key={iconObj.type}
                        type="button"
                        className={`icon-picker-btn ${editIcon === iconObj.type ? "icon-picker-btn--active" : ""}`}
                        onClick={() => setEditIcon(iconObj.type)}
                        style={{
                          width: "36px",
                          height: "36px",
                          borderRadius: "var(--radius-md)",
                          fontSize: "18px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          border: editIcon === iconObj.type ? "2px solid var(--accent-primary)" : "1px solid var(--border-color)",
                          backgroundColor: editIcon === iconObj.type ? "var(--accent-light)" : "transparent",
                          cursor: "pointer",
                        }}
                      >
                        {iconObj.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="editFolderDesc">{t("lib.folderDesc")}</label>
                  <textarea
                    id="editFolderDesc"
                    className="theme-input"
                    value={editDesc}
                    onChange={(e) => setEditDesc(e.target.value)}
                    placeholder="添加该文件夹的简要描述和用途说明..."
                    rows={4}
                    style={{ resize: "none", fontFamily: "inherit" }}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="theme-btn theme-btn--outline" onClick={() => setEditFolderOpen(false)}>
                  {t("lib.cancel")}
                </button>
                <button type="submit" className="theme-btn">
                  {t("lib.confirm")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 3: Advanced Add Files Modal (Supports Local, NAS, Cloud, and batch import checkbox) */}
      {addFilesOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={() => setAddFilesOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>添加文件到 "{currentFolder}"</h2>
              <button type="button" className="modal-close" onClick={() => setAddFilesOpen(false)}>
                &times;
              </button>
            </div>
            <form onSubmit={handleAddFilesSubmit}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {/* File Source selection radio group */}
                <div className="form-group">
                  <label>{t("lib.importSource")}</label>
                  <div style={{ display: "flex", gap: "10px", marginTop: "6px" }}>
                    {[
                      { key: "local" as const, label: t("lib.importLocal") },
                      { key: "nas" as const, label: t("lib.importNas") },
                      { key: "cloud" as const, label: t("lib.importCloud") },
                    ].map((src) => (
                      <button
                        key={src.key}
                        type="button"
                        className={`icon-picker-btn ${importSource === src.key ? "icon-picker-btn--active" : ""}`}
                        onClick={() => setImportSource(src.key)}
                        style={{
                          flex: 1,
                          padding: "8px 12px",
                          borderRadius: "var(--radius-md)",
                          fontSize: "13px",
                          fontWeight: "500",
                          border: importSource === src.key ? "2px solid var(--accent-primary)" : "1px solid var(--border-color)",
                          backgroundColor: importSource === src.key ? "var(--accent-light)" : "transparent",
                          cursor: "pointer",
                          textAlign: "center"
                        }}
                      >
                        {src.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Import Path input */}
                <div className="form-group">
                  <label htmlFor="importPath">文件路径</label>
                  <input
                    type="text"
                    id="importPath"
                    className="theme-input"
                    value={importPathInput}
                    onChange={(e) => setImportPathInput(e.target.value)}
                    placeholder={IMPORT_PATH_HINTS[importSource]}
                    autoFocus
                    required
                  />
                  <p style={{ fontSize: "11.5px", color: "var(--text-muted)", marginTop: "6px", lineHeight: "1.5" }}>
                    填写完整路径。后端按路径前缀判断走本地、NAS 还是云盘，导入会把源文件
                    <strong>移动</strong>到库目录，并自动建立索引任务。
                  </p>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="theme-btn theme-btn--outline" onClick={() => setAddFilesOpen(false)}>
                  {t("lib.cancel")}
                </button>
                <button type="submit" className="theme-btn">
                  {t("lib.confirm")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* File Previewer Modal Overlay */}
      {previewFile && (
        <FilePreviewModal
          file={{
            id: previewFile.id,
            name: previewFile.name,
            path: previewFile.path || "",
            category: previewFile.category,
            size: previewFile.size,
            modified: previewFile.modified
          }}
          onClose={() => setPreviewFile(null)}
        />
      )}
    </div>
  );
}
export default FileLibrary;
