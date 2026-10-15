import { describe, expect, it, vi } from "vitest";

import { ApiClient, type RawResponse } from "../../../services/api/client";
import type { TaskBulkOperationResponse, TaskItem, TaskListResponse } from "../../../services/api/tasks";
import { useTasks } from "./useTasks";
import { renderHookWithProviders } from "../../../test/test-utils";

const task: TaskItem = {
  id: "task-1",
  file: {
    id: "file-1",
    name: "Task.pdf",
    path: "/documents/Task.pdf",
    size: 1024,
    file_type: "pdf",
    modified: "2026-09-28T08:00:00Z",
  },
  status: "failed",
  progress: "4/9",
  completed_count: 4,
  total_count: 9,
  stage: null,
  error_message: "OCR failed",
  created_at: "2026-09-28T08:00:00Z",
};

const taskList: TaskListResponse = {
  tasks: [task],
  counts: { queued: 0, processing: 0, completed: 0, failed: 1, cancelled: 0 },
  page: 1,
  page_size: 50,
  total: 1,
};

describe("useTasks", () => {
  it("requests the unfiltered page and polls every two seconds", async () => {
    vi.useFakeTimers();
    const transport = vi.fn(async (): Promise<RawResponse> => ({
      status: 200,
      body: JSON.stringify({ status: "success", data: taskList, error: null }),
    }));
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useTasks(client));

    await vi.advanceTimersByTimeAsync(0);
    expect(result.current.data?.tasks[0]?.id).toBe("task-1");
    expect(transport).toHaveBeenNthCalledWith(1, "GET", "/api/v1/tasks?page=1&page_size=50", undefined);

    await vi.advanceTimersByTimeAsync(2000);
    expect(transport).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("retries a task and invalidates the list", async () => {
    vi.useFakeTimers();
    const transport = vi.fn(async (method: string, path: string): Promise<RawResponse> => {
      const data = method === "POST" && path === "/api/v1/tasks/task-1/retry" ? task : taskList;
      return { status: 200, body: JSON.stringify({ status: "success", data, error: null }) };
    });
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useTasks(client));

    await vi.advanceTimersByTimeAsync(0);
    const response = await result.current.retryTask.mutateAsync("task-1");
    await vi.advanceTimersByTimeAsync(0);

    expect(response.status).toBe("success");
    expect(transport).toHaveBeenCalledWith("POST", "/api/v1/tasks/task-1/retry", undefined);
    expect(transport).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });

  it("cancels a running task and invalidates the list", async () => {
    vi.useFakeTimers();
    const transport = vi.fn(async (method: string, path: string): Promise<RawResponse> => {
      const data = method === "POST" && path === "/api/v1/tasks/task-1/cancel" ? task : taskList;
      return { status: 200, body: JSON.stringify({ status: "success", data, error: null }) };
    });
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useTasks(client));

    await vi.advanceTimersByTimeAsync(0);
    const response = await result.current.cancelTask.mutateAsync("task-1");
    await vi.advanceTimersByTimeAsync(0);

    expect(response.status).toBe("success");
    expect(transport).toHaveBeenCalledWith("POST", "/api/v1/tasks/task-1/cancel", undefined);
    expect(transport).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });

  it("removes a task and invalidates the list", async () => {
    vi.useFakeTimers();
    const transport = vi.fn(async (method: string, path: string): Promise<RawResponse> => {
      const data = method === "DELETE" && path === "/api/v1/tasks/task-1" ? null : taskList;
      return { status: 200, body: JSON.stringify({ status: "success", data, error: null }) };
    });
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useTasks(client));

    await vi.advanceTimersByTimeAsync(0);
    const response = await result.current.removeTask.mutateAsync("task-1");
    await vi.advanceTimersByTimeAsync(0);

    expect(response.status).toBe("success");
    expect(transport).toHaveBeenCalledWith("DELETE", "/api/v1/tasks/task-1", undefined);
    expect(transport).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });

  it("cancels incomplete tasks and invalidates the list", async () => {
    vi.useFakeTimers();
    const data: TaskBulkOperationResponse = { count: 3 };
    const transport = vi.fn(async (method: string, path: string): Promise<RawResponse> => {
      const response = method === "POST" && path === "/api/v1/tasks/cancel-incomplete" ? data : taskList;
      return { status: 200, body: JSON.stringify({ status: "success", data: response, error: null }) };
    });
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useTasks(client));

    await vi.advanceTimersByTimeAsync(0);
    const response = await result.current.cancelIncompleteTasks.mutateAsync();
    await vi.advanceTimersByTimeAsync(0);

    expect(response.status).toBe("success");
    expect(response.data?.count).toBe(3);
    expect(transport).toHaveBeenCalledWith("POST", "/api/v1/tasks/cancel-incomplete", undefined);
    expect(transport).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });

  it("continues cancelled tasks and invalidates the list", async () => {
    vi.useFakeTimers();
    const data: TaskBulkOperationResponse = { count: 2 };
    const transport = vi.fn(async (method: string, path: string): Promise<RawResponse> => {
      const response = method === "POST" && path === "/api/v1/tasks/continue-cancelled" ? data : taskList;
      return { status: 200, body: JSON.stringify({ status: "success", data: response, error: null }) };
    });
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useTasks(client));

    await vi.advanceTimersByTimeAsync(0);
    const response = await result.current.continueCancelledTasks.mutateAsync();
    await vi.advanceTimersByTimeAsync(0);

    expect(response.status).toBe("success");
    expect(response.data?.count).toBe(2);
    expect(transport).toHaveBeenCalledWith("POST", "/api/v1/tasks/continue-cancelled", undefined);
    expect(transport).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });

  it("deletes completed tasks and invalidates the list", async () => {
    vi.useFakeTimers();
    const data: TaskBulkOperationResponse = { count: 4 };
    const transport = vi.fn(async (method: string, path: string): Promise<RawResponse> => {
      const response = method === "POST" && path === "/api/v1/tasks/delete-completed" ? data : taskList;
      return { status: 200, body: JSON.stringify({ status: "success", data: response, error: null }) };
    });
    const client = new ApiClient(transport);
    const { result } = renderHookWithProviders(() => useTasks(client));

    await vi.advanceTimersByTimeAsync(0);
    const response = await result.current.deleteCompletedTasks.mutateAsync();
    await vi.advanceTimersByTimeAsync(0);

    expect(response.status).toBe("success");
    expect(response.data?.count).toBe(4);
    expect(transport).toHaveBeenCalledWith("POST", "/api/v1/tasks/delete-completed", undefined);
    expect(transport).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });
});
