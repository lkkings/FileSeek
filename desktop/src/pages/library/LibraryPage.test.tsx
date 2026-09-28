import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsPreferencesProvider } from "../../features/settings";
import { activateLocale, defaultLocale } from "../../i18n/i18n";
import { renderWithProviders } from "../../test/test-utils";
import { LibraryPage } from "./LibraryPage";

const folder = {
  id: "folder-1",
  name: "工作资料",
  icon_type: "work",
  description: "工作文件",
  modified: "2026-01-01T00:00:00Z",
  file_count: 0,
};

const storageLocations = [
  {
    id: "local",
    type: "local",
    name: "本地存储",
    protocol: "file",
    endpoint: "file://localhost",
    root_path: "/",
    account: null,
    status: "active",
    is_system: true,
  },
];

function successResponse<T>(data: T) {
  return new Response(JSON.stringify({ status: "success", data, error: null }), { status: 200 });
}

function renderLibraryPage() {
  return renderWithProviders(
    <SettingsPreferencesProvider>
      <LibraryPage />
    </SettingsPreferencesProvider>,
  );
}

describe("LibraryPage import dialog", () => {
  beforeEach(() => {
    window.localStorage.clear();
    activateLocale(defaultLocale);
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/v1/library/folders") return successResponse([folder]);
      if (path === "/api/v1/settings/classifier-labels") {
        return successResponse({ document_labels: [], image_labels: [], video_labels: [], version: "v1" });
      }
      if (path === "/api/v1/settings/storage-locations") return successResponse(storageLocations);
      if (path.startsWith("/api/v1/recent?")) {
        return successResponse({ items: [], page_number: 1, page_size: 20, total: 0, has_more: false });
      }
      if (path.startsWith("/api/v1/settings/storage-locations/local/directory")) {
        return successResponse({
          current_path: "/",
          entries: [
            { name: "report.pdf", kind: "file", source_path: "/report.pdf", size: 100, modified: "2026-01-01T00:00:00Z" },
          ],
        });
      }
      return successResponse(null);
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
    activateLocale(defaultLocale);
  });

  it("opens and closes the import-file dialog without an import-folder action", async () => {
    renderLibraryPage();

    expect(await screen.findByText("工作资料")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "导入文件" }));

    expect(await screen.findByRole("dialog", { name: "导入文件到 工作资料" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "导入文件夹" })).not.toBeInTheDocument();
    expect(await screen.findByText("report.pdf")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
