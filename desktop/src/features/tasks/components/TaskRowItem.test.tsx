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
  return {
    id: `task-${status}`,
    file,
    status,
    progress: status === "completed" ? 100 : status === "failed" ? 45 : status === "processing" ? 60 : 0,
    stage: status === "processing" || status === "failed" ? "classify" : null,
    error_message: status === "failed" ? "OCR failed" : null,
    created_at: "2026-09-28T08:00:00Z",
  };
}

describe("TaskRowItem", () => {
  it.each(["queued", "processing", "completed", "failed"] as TaskStatus[])(
    "renders status, progress, stages, and retry behavior for %s",
    (status) => {
      const onRetry = vi.fn();
      const onRemove = vi.fn();
      const onOpenDetails = vi.fn();
      const { unmount } = renderWithI18n(
        <TaskRowItem
          task={createTask(status)}
          onRetry={onRetry}
          onRemove={onRemove}
          onOpenDetails={onOpenDetails}
        />,
      );

      expect(screen.getByText("Task.pdf")).toBeInTheDocument();
      expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(status === "completed" ? 100 : status === "failed" ? 45 : status === "processing" ? 60 : 0));
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

      if (status === "failed") {
        expect(screen.getByRole("button", { name: "Task.pdf 重试" })).toBeInTheDocument();
      } else {
        expect(screen.queryByRole("button", { name: "Task.pdf 重试" })).not.toBeInTheDocument();
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
