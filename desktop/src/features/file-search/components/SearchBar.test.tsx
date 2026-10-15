import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../../test/test-utils";
import { WARMUP_THROTTLE_MS, resetWarmupThrottleForTests } from "../warmup";
import { SearchBar } from "./SearchBar";

function renderBar(onWarmup: () => Promise<unknown>) {
  return renderWithI18n(
    <SearchBar
      query=""
      mode="advanced"
      onModeChange={() => undefined}
      onQueryChange={() => undefined}
      onOpenAdvanced={() => undefined}
      advancedOpen={false}
      onSubmit={() => undefined}
      onWarmup={onWarmup}
    />,
  );
}

describe("SearchBar warmup", () => {
  beforeEach(() => {
    resetWarmupThrottleForTests();
    vi.useRealTimers();
  });

  it("warms the query model when the input gains focus", () => {
    const onWarmup = vi.fn(async () => undefined);
    renderBar(onWarmup);

    fireEvent.focus(screen.getByRole("textbox"));

    expect(onWarmup).toHaveBeenCalledTimes(1);
  });

  it("does not warm again within the throttle window", () => {
    vi.useFakeTimers();
    const onWarmup = vi.fn(async () => undefined);
    renderBar(onWarmup);
    const input = screen.getByRole("textbox");

    fireEvent.focus(input);
    fireEvent.blur(input);
    vi.advanceTimersByTime(WARMUP_THROTTLE_MS - 1);
    fireEvent.focus(input);
    expect(onWarmup).toHaveBeenCalledTimes(1);

    fireEvent.blur(input);
    vi.advanceTimersByTime(1);
    fireEvent.focus(input);
    expect(onWarmup).toHaveBeenCalledTimes(2);
  });

  it("swallows warmup failures without showing an error", async () => {
    const onWarmup = vi.fn(async () => {
      throw new Error("backend unavailable");
    });
    renderBar(onWarmup);
    const input = screen.getByRole("textbox");

    fireEvent.focus(input);
    await Promise.resolve();
    fireEvent.change(input, { target: { value: "cat" } });

    expect(onWarmup).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/backend unavailable/)).toBeNull();
  });

  it("toggles retrieval augmentation and hides the advanced-filter entry", () => {
    const onModeChange = vi.fn();
    const onOpenAdvanced = vi.fn();
    const { unmount } = renderWithI18n(
      <SearchBar
        query=""
        mode="advanced"
        onModeChange={onModeChange}
        onQueryChange={() => undefined}
        onOpenAdvanced={onOpenAdvanced}
        advancedOpen={false}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: "高级筛选", expanded: false })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "启动检索增强" }));
    expect(onModeChange).toHaveBeenCalledWith("enhanced");

    unmount();
    renderWithI18n(
      <SearchBar
        query=""
        mode="enhanced"
        onModeChange={onModeChange}
        onQueryChange={() => undefined}
        onOpenAdvanced={onOpenAdvanced}
        advancedOpen={false}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.queryByRole("button", { name: "高级筛选", expanded: false })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "启动检索增强" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("disables controls and ignores submissions while loading", () => {
    const onModeChange = vi.fn();
    const onSubmit = vi.fn();
    renderWithI18n(
      <SearchBar
        query="cat"
        mode="advanced"
        onModeChange={onModeChange}
        onQueryChange={() => undefined}
        onOpenAdvanced={() => undefined}
        advancedOpen={false}
        onSubmit={onSubmit}
        loading
      />,
    );

    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(screen.getByRole("button", { name: "启动检索增强" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "高级筛选", expanded: false })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "启动检索增强" }));
    fireEvent.submit(screen.getByRole("textbox").closest("form"));

    expect(onModeChange).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
