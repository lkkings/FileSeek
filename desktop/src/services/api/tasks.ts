import { defaultClient, type ApiClient, type ApiResponse } from "./client";

export type TaskStatus = "queued" | "processing" | "completed" | "failed";
export type TaskStage = "extracted" | "encoded" | "classify" | "indexed";

export interface TaskFile {
  id: string;
  name: string;
  path: string;
  size: number;
  file_type: string;
  modified: string;
}

export interface TaskItem {
  id: string;
  file: TaskFile;
  status: TaskStatus;
  progress: number;
  stage: TaskStage | null;
  error_message: string | null;
  created_at: string;
}

export interface TaskListResponse {
  tasks: TaskItem[];
  counts: Record<TaskStatus, number>;
  page: number;
  page_size: number;
  total: number;
}

export function listTasks(
  status: TaskStatus | null = null,
  page: number = 1,
  pageSize: number = 50,
  client: ApiClient = defaultClient,
): Promise<ApiResponse<TaskListResponse>> {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (status) parameters.set("status", status);
  return client.get<TaskListResponse>(`/tasks?${parameters.toString()}`);
}

export function retryTask(taskId: string, client: ApiClient = defaultClient): Promise<ApiResponse<TaskItem>> {
  return client.post<TaskItem>(`/tasks/${encodeURIComponent(taskId)}/retry`);
}
