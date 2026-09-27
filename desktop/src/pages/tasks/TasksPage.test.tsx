import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../test/test-utils";
import { TasksPage } from "./TasksPage";

const mocks = vi.hoisted(() => ({
  reload: vi.fn(),
  retryTask: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
}));

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
  progress: 45,
  stage: null,
  error_message: "OCR failed",
  created_at: "2026-09-28T08:00:00Z",
} as const;

vi.mock("../../features/tasks/hooks/useTasks", () => ({
  useTasks: () => ({
    data: {
      tasks: [task],
      counts: { queued: 1, processing: 2, completed: 3, failed: 4 },
      page: 1,
      page_size: 50,
      total: 10,
    },
    loading: false,
    error: null,
    page: 1,
    setPage: vi.fn(),
    pageSize: 50,
    reload: mocks.reload,
    retryTask: mocks.retryTask,
  }),
}));

describe("TasksPage", () => {
  it("uses the four backend statuses and retries a failed task", async () => {
    renderWithI18n(<TasksPage />);

    expect(screen.getByText("Task.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /等待中/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /处理中/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /已完成/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /失败/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /pending/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /重试/ }));

    await waitFor(() => expect(mocks.retryTask.mutateAsync).toHaveBeenCalledWith("task-1"));
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/任务重试已提交/)).toBeInTheDocument();
  });
});
