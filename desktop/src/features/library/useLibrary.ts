/**
 * 文件库的后端状态。
 *
 * 组件只管渲染和收集输入，读写后端集中在这里。三件事值得先说明：
 *
 * - **文件夹既有 id 又有名字。** 后端的写操作按 id（`PUT/DELETE /library/folders/{id}`），
 *   而列文件按**名字**（`GET /library/files?folder=`，用例内部再查 id）。父级 `App` 也是
 *   按名字记住"当前文件夹"。所以两者都得留着，不能只存一个。
 * - **文件的 `parentFolder` 是 id。** 渲染和筛选用的是名字，所以载入后要拿文件夹列表把
 *   id 翻成名字。
 * - **写操作失败要说话。** 这些操作改的是用户的真实文件，静默失败等于骗人，所以每个
 *   动作都回一个 `string | null` 的错误给组件去显示。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  batchDeleteFiles,
  clearRecycleBin,
  createFolder as createFolderRequest,
  deleteFolder as deleteFolderRequest,
  deleteRecycleItem,
  formatModified,
  formatSize,
  importFile,
  listFiles,
  listFolders,
  listRecycleItems,
  restoreRecycleItem,
  toCategory,
  updateFolder as updateFolderRequest,
  type ApiFile,
  type ApiFolder,
  type ApiRecycleItem,
} from "../../api/library";
import { defaultClient, errorText, type ApiClient } from "../../api/client";

export type FolderIconType = "default" | "travel" | "work" | "photos" | "videos";

/** 文件夹的展示模型。`id` 用于写操作，`name` 用于列文件和面包屑。 */
export interface FolderItem {
  id: string;
  name: string;
  iconType: FolderIconType;
  description: string;
  modified: string;
  fileCount: number;
}

/** 文件的展示模型。`size`/`modified` 已格式化成可直接渲染的串。 */
export interface FileItem {
  id: string;
  name: string;
  category: "document" | "image" | "video" | "other";
  size: string;
  /** 原始字节数，排序和体积筛选要用——格式化后的串没法比大小。 */
  sizeBytes: number;
  modified: string;
  /** 所属文件夹的**名字**（已由 id 翻译过来），根目录下为 null。 */
  parentFolder: string | null;
  path: string;
}

export interface RecycleItem {
  id: string;
  name: string;
  category: "document" | "image" | "video" | "other";
  size: string;
  deletedAt: string;
  originalPath: string;
}

/** 后端图标取值是自由字符串，这里收敛到 UI 认识的那几个。 */
function toIconType(value: string | null | undefined): FolderIconType {
  switch (value) {
    case "travel":
    case "work":
    case "photos":
    case "videos":
      return value;
    default:
      return "default";
  }
}

function toFolderItem(folder: ApiFolder): FolderItem {
  return {
    id: folder.id,
    name: folder.name,
    iconType: toIconType(folder.iconType),
    description: folder.description ?? "",
    modified: formatModified(folder.modified),
    fileCount: folder.file_count ?? 0,
  };
}

function toFileItem(file: ApiFile, folderNameById: Map<string, string>): FileItem {
  return {
    id: file.id,
    name: file.name,
    category: toCategory(file.FileType),
    size: formatSize(file.size),
    sizeBytes: Number(file.size) || 0,
    modified: formatModified(file.modified),
    parentFolder: file.parentFolder ? folderNameById.get(file.parentFolder) ?? null : null,
    path: file.path,
  };
}

function toRecycleItem(item: ApiRecycleItem): RecycleItem {
  return {
    id: item.id,
    name: item.original_name,
    category: toCategory(item.file_type),
    size: formatSize(item.size),
    deletedAt: formatModified(item.deleted_at),
    originalPath: item.original_path,
  };
}

export interface UseLibraryOptions {
  /** 当前进入的文件夹名字，null 表示在根目录。决定要不要去取文件列表。 */
  currentFolder: string | null;
  /** "recycle" 视图只需要回收站数据，不必去拉文件夹和文件。 */
  viewType: "all" | "recycle";
  /** 覆盖用的客户端，只给测试用；不传就走默认那个（经 Tauri 桥）。 */
  client?: ApiClient | undefined;
}

export function useLibrary({ currentFolder, viewType, client }: UseLibraryOptions) {
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [recycle, setRecycle] = useState<RecycleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadVersion = useRef(0);

  const api = client ?? defaultClient;

  const folderNameById = useMemo(
    () => new Map(folders.map((folder) => [folder.id, folder.name])),
    [folders],
  );

  const folderIdByName = useMemo(
    () => new Map(folders.map((folder) => [folder.name, folder.id])),
    [folders],
  );

  const loadRecycle = useCallback(async (version: number) => {
    const response = await listRecycleItems(api);
    if (version !== loadVersion.current) return;
    if (response.status !== "success" || !response.data) {
      setError(errorText(response.error) || "无法读取回收站");
      return;
    }
    setRecycle(response.data.map(toRecycleItem));
  }, [api]);

  /**
   * 拉一遍当前视图需要的数据。
   *
   * 文件夹列表总要取：文件的 `parentFolder` 是 id，没有它翻不成名字。
   */
  const reload = useCallback(async () => {
    const version = ++loadVersion.current;
    setLoading(true);
    setError(null);

    try {
      if (viewType === "recycle") {
        await loadRecycle(version);
        if (version === loadVersion.current) {
          setFolders([]);
          setFiles([]);
        }
        return;
      }

      const folderResponse = await listFolders(api);
      if (folderResponse.status !== "success" || !folderResponse.data) {
        if (version === loadVersion.current) setError(errorText(folderResponse.error) || "无法读取文件夹列表");
        return;
      }

      const loadedFolders = folderResponse.data.map(toFolderItem);
      if (version !== loadVersion.current) return;
      setFolders(loadedFolders);
      setRecycle([]);

      // 根目录只渲染文件夹卡片，不列文件，所以那一趟请求可以省掉。
      if (!currentFolder) {
        setFiles([]);
        return;
      }

      const fileResponse = await listFiles({ folder: currentFolder }, api);
      if (fileResponse.status !== "success" || !fileResponse.data) {
        if (version === loadVersion.current) setError(errorText(fileResponse.error) || "无法读取文件列表");
        return;
      }

      if (version !== loadVersion.current) return;
      const nameById = new Map(loadedFolders.map((folder) => [folder.id, folder.name]));
      setFiles(fileResponse.data.map((file) => toFileItem(file, nameById)));
    } catch (cause) {
      if (version === loadVersion.current) {
        const message = cause instanceof Error ? cause.message : "无法连接到文件库服务";
        setError(message);
      }
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, [api, currentFolder, viewType, loadRecycle]);

  useEffect(() => {
    // 推到微任务里再跑：`reload` 一进去就 `setLoading(true)`，在 effect 里同步改 state
    // 会触发级联渲染（`react-hooks/immutability` 会报），而且这一帧的 loading 也没人看。
    void Promise.resolve().then(reload);
    return () => {
      loadVersion.current += 1;
    };
  }, [reload]);

  // -------------------------------------------------------------------------
  // 写操作。成功回 null，失败回可以直接显示给用户的文案。
  // -------------------------------------------------------------------------

  const createFolder = useCallback(
    async (input: { name: string; iconType: FolderIconType; description: string }) => {
      const response = await createFolderRequest(input, api);
      if (response.status !== "success") {
        return errorText(response.error) || "创建文件夹失败";
      }
      await reload();
      return null;
    },
    [api, reload],
  );

  const updateFolder = useCallback(
    async (
      folderId: string,
      input: { name: string; iconType: FolderIconType; description: string },
    ) => {
      const response = await updateFolderRequest(folderId, input, api);
      if (response.status !== "success") {
        return errorText(response.error) || "保存文件夹失败";
      }
      await reload();
      return null;
    },
    [api, reload],
  );

  /** 删除文件夹。后端对非空文件夹会拒绝，错误文案直接透给用户。 */
  const deleteFolder = useCallback(
    async (folderId: string) => {
      const response = await deleteFolderRequest(folderId, api);
      if (response.status !== "success") {
        return errorText(response.error) || "删除文件夹失败";
      }
      await reload();
      return null;
    },
    [api, reload],
  );

  /**
   * 把一个路径下的文件入库到当前文件夹。
   *
   * 文件名由路径尾段推出来：后端的 `filename` 只用于报错文案，真正落盘用的是 `path`。
   */
  const addFile = useCallback(
    async (path: string) => {
      const trimmed = path.trim();
      if (!trimmed) return "请填写要导入的文件路径";

      const folderId = currentFolder ? folderIdByName.get(currentFolder) ?? null : null;
      const filename = trimmed.split(/[/\\]/).filter(Boolean).pop() ?? trimmed;

      const response = await importFile({ folderId, filename, path: trimmed }, api);
      if (response.status !== "success") {
        return errorText(response.error) || "导入失败";
      }
      await reload();
      return null;
    },
    [api, currentFolder, folderIdByName, reload],
  );

  const deleteFiles = useCallback(
    async (fileIds: string[]) => {
      if (fileIds.length === 0) return null;
      const response = await batchDeleteFiles(fileIds, api);
      if (response.status !== "success") {
        return errorText(response.error) || "删除文件失败";
      }
      await reload();
      return null;
    },
    [api, reload],
  );

  const restoreItem = useCallback(
    async (itemId: string) => {
      const response = await restoreRecycleItem(itemId, api);
      if (response.status !== "success") {
        return errorText(response.error) || "还原失败";
      }
      await reload();
      return null;
    },
    [api, reload],
  );

  const deleteItemPermanently = useCallback(
    async (itemId: string) => {
      const response = await deleteRecycleItem(itemId, api);
      if (response.status !== "success") {
        return errorText(response.error) || "彻底删除失败";
      }
      await reload();
      return null;
    },
    [api, reload],
  );

  const emptyRecycleBin = useCallback(async () => {
    const response = await clearRecycleBin(api);
    if (response.status !== "success") {
      return errorText(response.error) || "清空回收站失败";
    }
    await reload();
    return null;
  }, [api, reload]);

  return {
    folders,
    files,
    recycle,
    loading,
    error,
    setError,
    folderNameById,
    folderIdByName,
    reload,
    createFolder,
    updateFolder,
    deleteFolder,
    addFile,
    deleteFiles,
    restoreItem,
    deleteItemPermanently,
    emptyRecycleBin,
  };
}
