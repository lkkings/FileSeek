import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../test/test-utils";
import { TasksPage } from "./TasksPage";
import type { FilePreviewItem } from "../../features/file-preview";

const mocks = vi.hoisted(() => ({
  reload: vi.fn(),
  retryTask: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
  cancelTask: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
  cancelIncompleteTasks: { mutateAsync: vi.fn(async () => ({ status: "success", data: { count: 3 }, error: null })) },
  continueCancelledTasks: { mutateAsync: vi.fn(async () => ({ status: "success", data: { count: 2 }, error: null })) },
  deleteCompletedTasks: { mutateAsync: vi.fn(async () => ({ status: "success", data: { count: 3 }, error: null })) },
}));

vi.mock("../../features/file-preview", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/file-preview")>();

  function MockFileViewerOverlay({
    isOpen,
    item,
    onClose,
  }: {
    isOpen: boolean;
    item: FilePreviewItem | null;
    onClose: () => void;
  }) {
    if (!isOpen || !item) return null;
    return (
      <div role="dialog" aria-label="文件预览">
        <p>{item.fileName}</p>
        <button type="button" onClick={onClose}>关闭</button>
      </div>
    );
  }

  return {
    ...actual,
    FileViewerOverlay: MockFileViewerOverlay,
  };
});

const task = {
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
} as const;

vi.mock("../../features/tasks/hooks/useTasks", () => ({
  useTasks: () => ({
    data: {
      tasks: [task],
      counts: { queued: 1, processing: 2, completed: 3, failed: 4, cancelled: 2 },
      page: 1,
      page_size: 50,
      total: 12,
    },
    loading: false,
    error: null,
    page: 1,
    setPage: vi.fn(),
    pageSize: 50,
    reload: mocks.reload,
    retryTask: mocks.retryTask,
    cancelTask: mocks.cancelTask,
    cancelIncompleteTasks: mocks.cancelIncompleteTasks,
    continueCancelledTasks: mocks.continueCancelledTasks,
    deleteCompletedTasks: mocks.deleteCompletedTasks,
  }),
}));

describe("TasksPage", () => {
  it("uses the backend statuses and retries a failed task", async () => {
    renderWithI18n(<TasksPage />);

    expect(screen.getByRole("heading", { name: "任务队列" })).toBeInTheDocument();
    const summary = screen.getByLabelText("任务状态摘要");
    expect(within(summary).getByText("总数")).toBeInTheDocument();
    expect(within(summary).getByText("12")).toBeInTheDocument();
    expect(within(summary).getByText("处理中")).toBeInTheDocument();
    expect(within(summary).getByText("4")).toBeInTheDocument();
    expect(within(summary).getByText("失败")).toBeInTheDocument();
    expect(within(summary).getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Task.pdf")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "任务批量操作" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "任务状态筛选" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /一键终止 3/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /一键继续 2/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /删除已完成 3/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Task.pdf 重试" }));

    await waitFor(() => expect(mocks.retryTask.mutateAsync).toHaveBeenCalledWith("task-1"));
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/任务重试已提交/)).toBeInTheDocument();
  });

  it("opens the file detail drawer and retries all failed tasks", async () => {
    renderWithI18n(<TasksPage />);

    fireEvent.click(screen.getByRole("button", { name: "Task.pdf 文件详情" }));
    const drawer = screen.getByText("文件详情").closest("aside");
    expect(drawer).toBeInTheDocument();
    expect(within(drawer!).getByText("Task.pdf")).toBeInTheDocument();

    fireEvent.click(within(drawer!).getByRole("button", { name: "打开" }));
    const viewer = screen.getByRole("dialog", { name: "文件预览" });
    expect(within(viewer).getByText("Task.pdf")).toBeInTheDocument();

    fireEvent.click(within(viewer).getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("dialog", { name: "文件预览" })).not.toBeInTheDocument();

    fireEvent.click(within(screen.getByRole("complementary")).getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /一键重试/ }));

    await waitFor(() => expect(mocks.retryTask.mutateAsync).toHaveBeenCalledWith("task-1"));
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/已提交 1 个重试/)).toBeInTheDocument();
  });

  it("runs bulk terminate, continue, and delete completed actions", async () => {
    renderWithI18n(<TasksPage />);

    fireEvent.click(screen.getByRole("button", { name: /一键终止 3/ }));
    await waitFor(() => expect(mocks.cancelIncompleteTasks.mutateAsync).toHaveBeenCalledTimes(1));
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/已终止 3 个任务/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /一键继续 2/ }));
    await waitFor(() => expect(mocks.continueCancelledTasks.mutateAsync).toHaveBeenCalledTimes(1));
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/已继续 2 个任务/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /删除已完成 3/ }));
    await waitFor(() => expect(mocks.deleteCompletedTasks.mutateAsync).toHaveBeenCalledTimes(1));
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/已删除 3 个已完成任务/)).toBeInTheDocument();
  });
});
