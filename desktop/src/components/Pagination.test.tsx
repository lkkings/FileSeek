import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Pagination } from "./Pagination";
import { renderWithI18n } from "../test/test-utils";

function renderPagination(props: Partial<Parameters<typeof Pagination>[0]> = {}) {
  const onPageChange = vi.fn();
  renderWithI18n(
    <Pagination
      currentPage={1}
      totalPages={1}
      totalItems={10}
      onPageChange={onPageChange}
      {...props}
    />,
  );
  return { onPageChange };
}

function renderedPageNumbers(): string[] {
  return screen
    .getAllByRole("button")
    .map((button) => button.textContent ?? "")
    .filter((label) => /^\d+$/.test(label));
}

describe("Pagination", () => {
  it("renders every page when the page count is small", () => {
    // Arrange / Act
    renderPagination({ currentPage: 2, totalPages: 5 });

    // Assert
    expect(renderedPageNumbers()).toEqual(["1", "2", "3", "4", "5"]);
    expect(screen.queryByText("…")).toBeNull();
  });

  it("collapses to a seven item window when there are many pages", () => {
    // Arrange / Act
    renderPagination({ currentPage: 10, totalPages: 50 });

    // Assert
    expect(screen.getAllByRole("button")).toHaveLength(9); // 2 arrows + 7 slots
    expect(renderedPageNumbers()).toEqual(["1", "8", "9", "10", "11", "12", "50"]);
    expect(screen.getAllByText("…")).toHaveLength(2);
  });

  it("hides the leading ellipsis while the window covers the first pages", () => {
    // Arrange / Act
    renderPagination({ currentPage: 1, totalPages: 20 });

    // Assert
    expect(renderedPageNumbers()).toEqual(["1", "2", "3", "4", "5", "6", "20"]);
    expect(screen.getAllByText("…")).toHaveLength(1);
  });

  it("hides the trailing ellipsis while the window covers the last pages", () => {
    // Arrange / Act
    renderPagination({ currentPage: 20, totalPages: 20 });

    // Assert
    expect(renderedPageNumbers()).toEqual(["1", "15", "16", "17", "18", "19", "20"]);
    expect(screen.getAllByText("…")).toHaveLength(1);
  });

  it("marks only the current page and jumps to the clicked page", () => {
    // Arrange
    const { onPageChange } = renderPagination({ currentPage: 4, totalPages: 12 });

    // Act
    fireEvent.click(screen.getByRole("button", { name: "5" }));

    // Assert
    expect(onPageChange).toHaveBeenCalledWith(5);
    expect(
      screen.getAllByRole("button").filter((button) => button.getAttribute("aria-current") === "page"),
    ).toHaveLength(1);
  });

  it("renders the same window for the details variant", () => {
    // Arrange / Act
    renderPagination({ currentPage: 30, totalPages: 60, variant: "details" });

    // Assert
    expect(renderedPageNumbers()).toEqual(["1", "28", "29", "30", "31", "32", "60"]);
  });
});
