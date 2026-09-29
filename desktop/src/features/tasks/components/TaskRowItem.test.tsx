import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TaskRowItem } from "./TaskRowItem";
import { renderWithI18n } from "../../../test/test-utils";
import type { TaskFile, TaskItem, TaskStatus } from "../../../services/api/tasks";

const file: TaskFile = {
  id: "file-1",
  name: "Task.pdf",
  path: "/documents/Task.pdf",
  size: 1024,
  file_type: "pdf",
  modified: "2026-09-28T08:00:00Z",
};

function createTask(status: TaskStatus): TaskItem {
  const completedCount =
    status === "completed" ? 9 : status === "failed" ? 4 : status === "processing" ? 5 : 0;

  return {
    id: `task-${status}`,
    file,
    status,
    progress: `${completedCount}/9`,
    completed_count: completedCount,
    total_count: 9,
    stage: status === "processing" || status === "failed" ? "classify" : null,
    error_message: status === "failed" ? "OCR failed" : null,
    created_at: "2026-09-28T08:00:00Z",
  };
}

describe("TaskRowItem", () => {
  it.each(["queued", "processing", "completed", "failed", "cancelled"] as TaskStatus[])(
    "renders status, progress, stages, and retry behavior for %s",
    (status) => {
      const onRetry = vi.fn();
      const onCancel = vi.fn();
      const onRemove = vi.fn();
      const onOpenDetails = vi.fn();
      const { unmount } = renderWithI18n(
        <TaskRowItem
          task={createTask(status)}
          onRetry={onRetry}
          onCancel={onCancel}
          onRemove={onRemove}
          onOpenDetails={onOpenDetails}
        />,
      );

      expect(screen.getByText("Task.pdf")).toBeInTheDocument();
      expect(screen.getByRole("progressbar")).toHaveAttribute(
        "aria-valuenow",
        String(status === "completed" ? 9 : status === "failed" ? 4 : status === "processing" ? 5 : 0),
      );
      expect(screen.getByRole("progressbar")).toHaveAttribute(
        "aria-valuetext",
        `${status === "completed" ? 9 : status === "failed" ? 4 : status === "processing" ? 5 : 0}/9`,
      );
      expect(screen.getByText("提取")).toBeInTheDocument();
      expect(screen.getByText("编码")).toBeInTheDocument();
      expect(screen.getByText("分类")).toBeInTheDocument();
      expect(screen.getByText("构建索引")).toBeInTheDocument();
      const stageFlow = screen.getByRole("list", { name: "Task.pdf 阶段流程" });
      const currentStage = within(stageFlow).getByText("分类").closest("li");

      if (status === "processing") {
        expect(currentStage).toHaveAttribute("aria-current", "step");
        expect(currentStage).toHaveClass("is-current");
      } else if (status === "failed") {
        expect(currentStage).toHaveClass("is-failed");
      } else if (status === "completed") {
        expect(within(stageFlow).getAllByRole("listitem").every((item) => item.className.includes("is-complete"))).toBe(true);
      }

      if (status === "failed" || status === "cancelled") {
        expect(screen.getByRole("button", { name: "Task.pdf 重试" })).toBeInTheDocument();
      } else {
        expect(screen.queryByRole("button", { name: "Task.pdf 重试" })).not.toBeInTheDocument();
      }

      if (status === "processing") {
        const cancelButton = screen.getByRole("button", { name: "Task.pdf 终止" });
        fireEvent.click(cancelButton);
        expect(onCancel).toHaveBeenCalledWith(`task-${status}`);
      } else {
        expect(screen.queryByRole("button", { name: "Task.pdf 终止" })).not.toBeInTheDocument();
      }

      const removeButton = screen.getByRole("button", { name: "Task.pdf 移除" });
      if (status === "processing") {
        expect(removeButton).toBeDisabled();
      } else {
        fireEvent.click(removeButton);
        expect(onRemove).toHaveBeenCalledWith(`task-${status}`);
      }

      fireEvent.click(screen.getByRole("button", { name: "Task.pdf 文件详情" }));
      expect(onOpenDetails).toHaveBeenCalledWith(createTask(status));
      unmount();
    },
  );
});

it("renders a processing fallback when count data is unavailable", () => {
  const task: TaskItem = {
    ...createTask("processing"),
    progress: "processing",
    completed_count: null,
    total_count: null,
  };

  renderWithI18n(
    <TaskRowItem
      task={task}
      onRetry={vi.fn()}
      onCancel={vi.fn()}
      onRemove={vi.fn()}
      onOpenDetails={vi.fn()}
    />,
  );

  expect(screen.getAllByText("处理中")).toHaveLength(2);
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.getByText("Task.pdf")).toBeInTheDocument();
});
