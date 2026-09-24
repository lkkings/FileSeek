/**
 * 库接口的形状转换。
 *
 * 后端的响应字段是既定契约（`FileType` 大驼峰、`size` 是纯数字字符串、回收站用
 * `original_*`），前端组件按自己一套命名写成，所以两边的翻译集中放在这里，
 * 而不是散在每个组件里各写一遍。
 */

import { defaultClient, type ApiClient, type ApiResponse } from "./client";

/** `GET /library/files` 的列表项，也是 `GET /library/files/{id}` 的响应。 */
export interface ApiFile {
  id: string;
  name: string;
  /** 后端这个键是大驼峰 `FileType`，不是 `file_type` 也不是 `mediaType`。 */
  FileType: string;
  /** 纯数字字符串（后端是 `str(int)`），不带单位，要自己格式化。 */
  size: string;
  modified: string;
  /** 所属文件夹的 **id**，不是名字。 */
  parentFolder: string | null;
  path: string;
}

export interface ApiFolder {
  id: string;
  name: string;
  /** 字面驼峰，后端 schema 里就是这么定义的。 */
  iconType: string;
  description: string;
  modified: string;
  file_count: number;
}

export interface ApiRecycleItem {
  id: string;
  original_file_id: string;
  original_name: string;
  original_path: string;
  deleted_at: string;
  file_type: string;
  size: string;
}

export interface ApiRecentAccess {
  file_id: string;
  accessed_at: string;
}

/** 组件里用的媒体分类。后端只认前三种，`other` 是前端对无法归类内容的兜底。 */
export type MediaCategory = "document" | "image" | "video" | "other";

export function toCategory(fileType: string | null | undefined): MediaCategory {
  if (fileType === "document" || fileType === "image" || fileType === "video") {
    return fileType;
  }
  return "other";
}

/**
 * 字节数转可读体积。
 *
 * 后端给的是纯数字字符串：JS 的 Number 放不下超大文件的字节数而不丢精度，所以它在
 * 那一侧就转成了字符串。
 */
export function formatSize(bytes: string | number | null | undefined): string {
  const value = typeof bytes === "string" ? Number(bytes) : bytes;
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  if (value < 1024) return `${value} B`;

  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(1)} ${units[unit]}`;
}

/** ISO 时间串转 `YYYY-MM-DD HH:mm`，无法解析时原样返回。 */
export function formatModified(iso: string | null | undefined): string {
  if (!iso) return "--";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso ?? "--";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    ` ${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/**
 * 读最近访问列表，并把每条记录补成可渲染的条目。
 *
 * `GET /library/recent` 只返回 `{file_id, accessed_at}`，渲染要的名字/体积/路径得靠
 * `GET /library/files/{id}` 逐条取。两点值得说明：
 *
 * - **先按 file_id 去重**：recent 表不去重，同一个文件访问十次就有十行。去重后请求数
 *   通常远小于 limit。
 * - **取不到详情的跳过**：文件可能已被永久删除但访问记录还在，那一条没有可渲染的内容。
 */
export async function fetchRecentFiles(
  client: ApiClient = defaultClient,
  limit = 20,
): Promise<Array<{ file: ApiFile; accessedAt: string }>> {
  const listed = await client.get<ApiRecentAccess[]>(`/library/recent?limit=${limit}`);
  if (listed.status !== "success" || !listed.data) return [];

  const seen = new Set<string>();
  const unique = listed.data.filter((record) => {
    if (seen.has(record.file_id)) return false;
    seen.add(record.file_id);
    return true;
  });

  const details = await Promise.all(
    unique.map(async (record) => {
      const detail = await client.get<ApiFile>(`/library/files/${record.file_id}`);
      if (detail.status !== "success" || !detail.data) return null;
      return { file: detail.data, accessedAt: record.accessed_at };
    }),
  );

  return details.filter((item): item is { file: ApiFile; accessedAt: string } => item !== null);
}

/** 记录一次访问。失败不打断用户正在做的事——这是派生数据。 */
export async function recordAccess(
  fileId: string,
  client: ApiClient = defaultClient,
): Promise<void> {
  try {
    await client.post(`/library/files/${fileId}/access`);
  } catch {
    // 打开文件本身已经成功了，记不上这一笔不值得报错给用户。
  }
}

// ---------------------------------------------------------------------------
// 写操作
//
// 都返回 `ApiResponse`，由调用方决定失败怎么呈现：库里的这些操作会改用户的数据，
// 静默失败等于骗人。
// ---------------------------------------------------------------------------

export async function listFolders(
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ApiFolder[]>> {
  return client.get<ApiFolder[]>("/library/folders");
}

export async function createFolder(
  input: { name: string; iconType: string; description: string },
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ApiFolder>> {
  return client.post<ApiFolder>("/library/folders", input);
}

export async function updateFolder(
  folderId: string,
  input: { name: string; iconType: string; description: string },
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ApiFolder>> {
  return client.put<ApiFolder>(`/library/folders/${folderId}`, input);
}

export async function deleteFolder(
  folderId: string,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<null>> {
  return client.delete<null>(`/library/folders/${folderId}`);
}

/**
 * 列一个文件夹下的文件。
 *
 * `folder` 传的是文件夹**名字**而不是 id——后端 `ListFilesUseCase` 先按名字查文件夹
 * 再转成 id。传 null 表示不限定文件夹。
 *
 * 后端一页最多 100 条（`page_size` 有 `le=100`），要多的得自己翻页。
 */
export async function listFiles(
  options: { folder?: string | null; fileType?: string | null; page?: number; pageSize?: number },
  client: ApiClient = defaultClient,
): Promise<ApiResponse<ApiFile[]>> {
  const params = new URLSearchParams();
  if (options.folder) params.set("folder", options.folder);
  if (options.fileType) params.set("file_type", options.fileType);
  params.set("page", String(options.page ?? 1));
  params.set("page_size", String(options.pageSize ?? 100));
  return client.get<ApiFile[]>(`/library/files?${params.toString()}`);
}

/**
 * 入库一个文件。
 *
 * 注意后端会把源文件**移动**到库目录（`AddFileUseCase` 调的是 `move_to`），不是复制。
 * 成功后它还会自动建一个向量化任务，所以前端不需要再调 `/tasks`。
 */
export async function importFile(
  input: { folderId: string | null; filename: string; path: string },
  client: ApiClient = defaultClient,
): Promise<ApiResponse<{ file_id: string }>> {
  return client.post<{ file_id: string }>("/library/files", {
    folder_id: input.folderId,
    filename: input.filename,
    path: input.path,
  });
}

/** 批量删除（移入回收站）。 */
export async function batchDeleteFiles(
  fileIds: string[],
  client: ApiClient = defaultClient,
): Promise<ApiResponse<null>> {
  return client.post<null>("/library/files/batch-delete", { file_ids: fileIds });
}

export async function listRecycleItems(
  client: ApiClient = defaultClient,
  pageSize = 100,
): Promise<ApiResponse<ApiRecycleItem[]>> {
  return client.get<ApiRecycleItem[]>(`/library/recycle?page=1&page_size=${pageSize}`);
}

export async function restoreRecycleItem(
  itemId: string,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<null>> {
  return client.post<null>(`/library/recycle/${itemId}/restore`);
}

export async function deleteRecycleItem(
  itemId: string,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<null>> {
  return client.delete<null>(`/library/recycle/${itemId}`);
}

export async function clearRecycleBin(
  client: ApiClient = defaultClient,
): Promise<ApiResponse<null>> {
  return client.delete<null>("/library/recycle");
}
