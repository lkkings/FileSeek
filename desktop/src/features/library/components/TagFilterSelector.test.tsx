import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../../test/test-utils";
import { TagFilterSelector } from "./TagFilterSelector";

const mocks = vi.hoisted(() => ({
  useLibraryTags: vi.fn(),
  refetch: vi.fn(),
}));

vi.mock("../hooks/useLibraryTags", () => ({
  useLibraryTags: mocks.useLibraryTags,
}));

describe("TagFilterSelector", () => {
  it("selects a backend tag", () => {
    mocks.useLibraryTags.mockReturnValue({
      tags: ["旅游", "文档"],
      loading: false,
      error: null,
      refetch: mocks.refetch,
    });

    const onTagChange = vi.fn();
    renderWithI18n(<TagFilterSelector selectedTag="全部" onTagChange={onTagChange} />);

    fireEvent.click(screen.getByRole("button", { name: "旅游" }));

    expect(onTagChange).toHaveBeenCalledWith("旅游");
    expect(screen.queryByRole("button", { name: "添加标签" })).not.toBeInTheDocument();
  });

  it("retries after a tag-list error", () => {
    mocks.useLibraryTags.mockReturnValue({
      tags: ["文档", "图片", "视频"],
      loading: false,
      error: "无法读取标签列表",
      refetch: mocks.refetch,
    });

    renderWithI18n(<TagFilterSelector selectedTag="全部" onTagChange={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));

    expect(mocks.refetch).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "文档" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "图片" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "视频" })).toBeInTheDocument();
  });

  it("selects a default tag while the tag list is unavailable", () => {
    mocks.useLibraryTags.mockReturnValue({
      tags: ["文档", "图片", "视频"],
      loading: false,
      error: "无法读取标签列表",
      refetch: mocks.refetch,
    });

    const onTagChange = vi.fn();
    renderWithI18n(<TagFilterSelector selectedTag="全部" onTagChange={onTagChange} />);

    fireEvent.click(screen.getByRole("button", { name: "文档" }));

    expect(onTagChange).toHaveBeenCalledWith("文档");
  });
});
