import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";
import { renderWithI18n } from "../test/test-utils";

describe("AppShell", () => {
  it("toggles the sidebar-collapsed layout class", () => {
    const { container } = renderWithI18n(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );

    expect(container.querySelector(".app-shell")).not.toHaveClass("sidebar-collapsed");
    fireEvent.click(screen.getByRole("button", { name: "折叠侧边栏" }));
    expect(container.querySelector(".app-shell")).toHaveClass("sidebar-collapsed");
    fireEvent.click(screen.getByRole("button", { name: "展开侧边栏" }));
    expect(container.querySelector(".app-shell")).not.toHaveClass("sidebar-collapsed");
  });
});
