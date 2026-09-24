/**
 * The FileSeek Desktop Application Shell.
 *
 * It provides a split-screen dashboard with a Left Sidebar navigation
 * and a right main content panel. In accordance with design layouts:
 * - Search is integrated as a beautiful persistent Top Search Bar in the workspace.
 * - Unified Category Tabs "全部", "文档", "图片", "视频" are persistent on all views.
 * - File Search supports Advanced Filters: searching by file name, min/max size range,
 *   and start/end date time ranges, integrated dynamically inside a collapsible drawer.
 * - Top Sidebar contains exactly: All Files, Recent Access, Recycle Bin, Tasks Queue.
 * - Bottom Sidebar strictly displays the Folders list.
 * - System Settings is displayed at the very bottom footer of the Left Sidebar.
 * - The Search Bar, Tabs, and Filters are completely hidden when browsing settings page.
 * - Import Files is launched as a beautiful modal overlay from the Library header.
 */

import { useState, useEffect, useCallback } from "react";
import { useSearch } from "./features/search/useSearch";
import { SearchBar } from "./features/search/SearchBar";
import { SearchResultsView } from "./features/search/SearchResults";
import { describeStatus } from "./app/status";
import { ApiClient, defaultClient } from "./api/client";
import { I18nProvider } from "./i18n/i18nContext.tsx";
import { useTranslation } from "./i18n/useTranslation";

import { FileLibrary } from "./features/library/FileLibrary";
import { IngestPanel } from "./features/ingest/IngestPanel";
import { TaskQueueView } from "./features/tasks/TaskQueueView";
import { SettingsPanel } from "./features/settings/SettingsPanel";
import { RecentAccess } from "./features/library/RecentAccess";

import "./App.css";

export interface AppProps {
  /** The backend client, injectable so the page is testable without a Tauri runtime. */
  client?: ApiClient | undefined;
}

/**
 * What the live region says about the search in effect.
 */

type NavigationPage =
  | "library"
  | "recent"
  | "recycle"
  | "tasks"
  | "settings";

type CategoryFilter = "all" | "document" | "image" | "video";

export function AppInner({ client }: AppProps) {
  const { t } = useTranslation();
  const { state, search } = useSearch(client);
  const activeClient = client || defaultClient;

  // Active navigation tab
  const [activeTab, setActiveTab] = useState<NavigationPage>("library");
  
  // Unified category tab state: persistently shared by all pages and search!
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("all");

  // Advanced Search Filters Drawer Toggle
  // The library opens with its filtering workspace visible, matching the desktop
  // product's primary workflow and making the available controls discoverable.
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Advanced Search Filter States
  const [filterName, setFilterName] = useState("");
  const [filterFileType, setFilterFileType] = useState<CategoryFilter>("all");
  const [filterMinSize, setFilterMinSize] = useState("");
  const [filterMaxSize, setFilterMaxSize] = useState("");
  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");

  // Modal State for Import Files
  const [importOpen, setImportOpen] = useState(false);

  // Selected folder state to filter files if clicked from sidebar
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);

  // Realtime Active tasks count for Sidebar notification badge
  const [activeTasksCount, setActiveTasksCount] = useState(0);

  const fetchActiveTasksCount = useCallback(async () => {
    try {
      const response = await activeClient.get<{ counts?: { processing?: number } }>("/tasks");
      if (response && response.status === "success" && response.data && response.data.counts) {
        setActiveTasksCount(response.data.counts.processing || 0);
      }
    } catch (err) {
      console.warn("Failed to update sidebar tasks badge:", err);
    }
  }, [activeClient]);

  useEffect(() => {
    // Only query task queue progress in actual native / browser runtimes.
    // Skip in tests (where client is injected) to prevent polluting mock transport expectations.
    if (client) return;

    // Defer state update using microtask to prevent synchronous cascading render warning
    Promise.resolve().then(() => {
      fetchActiveTasksCount();
    });
    
    // Updates tasks count dynamically on mock updates or polling
    const handleMockUpdate = () => {
      Promise.resolve().then(() => {
        fetchActiveTasksCount();
      });
    };

    window.addEventListener("mock-tasks-updated", handleMockUpdate);
    const interval = setInterval(fetchActiveTasksCount, 5000);

    return () => {
      window.removeEventListener("mock-tasks-updated", handleMockUpdate);
      clearInterval(interval);
    };
  }, [client, fetchActiveTasksCount]);

  // Unified Advanced options mapping
  const getAdvancedOptions = useCallback(() => {
    return {
      name_query: filterName || undefined,
      min_size_m: filterMinSize ? Number(filterMinSize) : null,
      max_size_m: filterMaxSize ? Number(filterMaxSize) : null,
      start_date: filterStartDate || undefined,
      end_date: filterEndDate || undefined,
    };
  }, [filterName, filterMinSize, filterMaxSize, filterStartDate, filterEndDate]);

  const toMediaTypes = (category: CategoryFilter) =>
    category === "all" ? ["document", "image", "video"] : [category];

  // Advanced filter's file type takes precedence over the global category tab when set,
  // since it narrows the search results specifically rather than the page's visible list.
  const effectiveSearchCategory = filterFileType !== "all" ? filterFileType : activeCategory;

  // Unified Search Handler taking the global category tab and advanced options into account.
  // A search only ever fires from here — pressing Enter/submitting with a non-empty query —
  // never as a side effect of editing an advanced filter field. Filters just ride along with
  // whatever the next Enter-triggered search sends.
  const handleSearch = (query: string) => {
    if (!query.trim()) return;
    search(query, toMediaTypes(effectiveSearchCategory), getAdvancedOptions());
  };

  // Clear advanced filter fields. Only re-runs the search if one is already active, so this
  // never fires a search on its own with an empty query.
  const handleResetFilters = () => {
    setFilterName("");
    setFilterFileType("all");
    setFilterMinSize("");
    setFilterMaxSize("");
    setFilterStartDate("");
    setFilterEndDate("");

    if (state.query) {
      search(state.query, toMediaTypes(activeCategory), {});
    }
  };

  // Unified Category Tab Click handler
  const handleCategoryClick = (category: CategoryFilter) => {
    setActiveCategory(category);
    // Only re-run if a search is already active — this never initiates a search on its own.
    if (state.query) {
      const effectiveCategory = filterFileType !== "all" ? filterFileType : category;
      search(state.query, toMediaTypes(effectiveCategory), getAdvancedOptions());
    }
  };

  // Header visibility per page: search bar + advanced filters only make sense on the
  // resource library root; category tabs stay out of the task queue, which has its own
  // status tabs instead.
  const showSearchBar = activeTab === "library" && !selectedFolder;
  const showCategoryTabs =
    (activeTab === "library" && selectedFolder !== null) ||
    activeTab === "recent" ||
    activeTab === "recycle";

  return (
    <div className="app-container">
      <a className="skip-link" href="#results">
        {t("search.skipLink")}
      </a>

      {/* 1. Left Navigation Sidebar */}
      <aside className="app-sidebar" aria-label="Primary Navigation">
        <div className="app-sidebar__brand">
          <div className="app-sidebar__logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="m21 21-4.3-4.3" />
              <circle cx="11" cy="11" r="8" />
              <path d="M11 8v6M8 11h6" />
            </svg>
          </div>
          <span className="app-sidebar__title">FileSeek</span>
        </div>

        {/* Top Sidebar Group */}
        <nav className="app-sidebar__nav">
          <div
            className={`nav-item ${activeTab === "library" && !selectedFolder ? "nav-item--active" : ""}`}
            onClick={() => {
              setSelectedFolder(null);
              setActiveTab("library");
            }}
          >
            <svg className="nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <line x1="9" y1="3" x2="9" y2="21" />
            </svg>
            <span className="nav-item__label">{t("nav.allFiles")}</span>
          </div>

          <div
            className={`nav-item ${activeTab === "recent" ? "nav-item--active" : ""}`}
            onClick={() => {
              setSelectedFolder(null);
              setActiveTab("recent");
            }}
          >
            <svg className="nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="12 8 12 12 14 14" />
              <circle cx="12" cy="12" r="10" />
            </svg>
            <span className="nav-item__label">{t("nav.recentFiles")}</span>
          </div>

          <div
            className={`nav-item ${activeTab === "recycle" ? "nav-item--active" : ""}`}
            onClick={() => {
              setSelectedFolder(null);
              setActiveTab("recycle");
            }}
          >
            <svg className="nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            <span className="nav-item__label">{t("nav.recycleBin")}</span>
          </div>

          <div
            className={`nav-item ${activeTab === "tasks" ? "nav-item--active" : ""}`}
            onClick={() => {
              setSelectedFolder(null);
              setActiveTab("tasks");
            }}
          >
            <div className="nav-item__icon-container">
              <svg className="nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              {activeTasksCount > 0 && (
                <span className="sidebar-tasks-badge" aria-label={`${activeTasksCount} processing tasks`}>
                  {activeTasksCount}
                </span>
              )}
            </div>
            <span className="nav-item__label">{t("nav.tasksQueue")}</span>
          </div>
        </nav>

        {/* System Settings at the very bottom of the Left Sidebar */}
        <div className="app-sidebar__footer">
          <div
            className={`nav-item ${activeTab === "settings" ? "nav-item--active" : ""}`}
            onClick={() => {
              setSelectedFolder(null);
              // Clear search query to exit search mode when entering settings
              if (state.query) {
                search("");
              }
              setActiveTab("settings");
            }}
          >
            <svg className="nav-item__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            <span className="nav-item__label">{t("nav.settings")}</span>
          </div>
        </div>
      </aside>

      {/* 2. Main Work Panel Area */}
      <div className="app-main-panel">
        
        {/* Persistent Top Header (Completely hidden when browsing settings page) */}
        {activeTab !== "settings" && (showSearchBar || showCategoryTabs) && (
          <header className="app__header" role="banner">
            <h1 className="app__title" style={{ display: "none" }}>FileSeek</h1>

            {/* Search bar + advanced filters: resource library root only */}
            {showSearchBar && (
              <div className="app__header-search-row" style={{ width: "100%" }}>
                <SearchBar
                  onSearch={handleSearch}
                  busy={state.busy}
                  filtersOpen={filtersOpen}
                  setFiltersOpen={setFiltersOpen}
                  filterName={filterName}
                  setFilterName={setFilterName}
                  filterFileType={filterFileType}
                  setFilterFileType={setFilterFileType}
                  filterMinSize={filterMinSize}
                  setFilterMinSize={setFilterMinSize}
                  filterMaxSize={filterMaxSize}
                  setFilterMaxSize={setFilterMaxSize}
                  filterStartDate={filterStartDate}
                  setFilterStartDate={setFilterStartDate}
                  filterEndDate={filterEndDate}
                  setFilterEndDate={setFilterEndDate}
                  onResetFilters={handleResetFilters}
                />
              </div>
            )}

            {/* Unified Category Tabs: "全部", "文档", "图片", "视频" — folder detail / recent / recycle only */}
            {showCategoryTabs && (
              <div className="app__header-tabs-row" style={{ display: "flex", alignItems: "center", width: "100%" }}>
                <div className="category-tabs" role="tablist" aria-label="筛选媒体类型" style={{ flex: 1 }}>
                  <button
                    type="button"
                    className={`category-tab ${activeCategory === "all" ? "category-tab--active" : ""}`}
                    onClick={() => handleCategoryClick("all")}
                    disabled={state.busy}
                  >
                    {t("search.filterAll")}
                  </button>
                  <button
                    type="button"
                    className={`category-tab ${activeCategory === "document" ? "category-tab--active" : ""}`}
                    onClick={() => handleCategoryClick("document")}
                    disabled={state.busy}
                  >
                    {t("search.filterDocument")}
                  </button>
                  <button
                    type="button"
                    className={`category-tab ${activeCategory === "image" ? "category-tab--active" : ""}`}
                    onClick={() => handleCategoryClick("image")}
                    disabled={state.busy}
                  >
                    {t("search.filterImage")}
                  </button>
                  <button
                    type="button"
                    className={`category-tab ${activeCategory === "video" ? "category-tab--active" : ""}`}
                    onClick={() => handleCategoryClick("video")}
                    disabled={state.busy}
                  >
                    {t("search.filterVideo")}
                  </button>
                </div>
              </div>
            )}

            {/* Status text (Status Landmark) — only meaningful while the search bar is present */}
            {showSearchBar && (
              <p className="app__status" role="status" aria-live="polite" style={{ marginTop: "8px" }}>
                {describeStatus(state)}
              </p>
            )}
          </header>
        )}

        {/* A search only ever runs with a non-empty query (see handleSearch), so state.query
            alone is sufficient to know whether the results overlay should show. */}
        {(state.query && activeTab !== "settings" && !(activeTab === "library" && selectedFolder !== null)) ? (
          <main className="app__results" id="results" tabIndex={-1}>
            {state.error !== null && (
              <p className="app__error" role="alert">
                {state.error}
              </p>
            )}

            <SearchResultsView
              results={state.results}
              query={state.error === null ? state.query : null}
            />
          </main>
        ) : (
          /* Else, show regular page workspace (Main Landmark fallback) */
          <main className="app-content-body" id="results" tabIndex={-1}>
            {activeTab === "library" && (
              <div className="file-library-wrapper">
                <FileLibrary
                  viewType="all"
                  selectedFolder={selectedFolder}
                  onSelectFolder={setSelectedFolder}
                  onOpenImport={() => setImportOpen(true)}
                  activeCategory={activeCategory}
                  searchQuery={state.query}
                  filterName={filterName}
                  filterMinSize={filterMinSize}
                  filterMaxSize={filterMaxSize}
                  filterStartDate={filterStartDate}
                  filterEndDate={filterEndDate}
                />
              </div>
            )}
            {activeTab === "recent" && <RecentAccess activeCategory={activeCategory} />}
            {activeTab === "tasks" && <TaskQueueView />}
            {activeTab === "recycle" && (
              <FileLibrary
                viewType="recycle"
                activeCategory={activeCategory}
              />
            )}
            {activeTab === "settings" && <SettingsPanel />}
          </main>
        )}
      </div>

      {/* Import Files Modal Overlay (formerly IngestPanel tab) */}
      {importOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={() => setImportOpen(false)}>
          <div className="modal-content modal-content--large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{t("nav.importFiles")}</h2>
              <button type="button" className="modal-close" onClick={() => setImportOpen(false)}>
                &times;
              </button>
            </div>
            <div className="modal-body" style={{ maxHeight: "75vh", overflowY: "auto" }}>
              <IngestPanel />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function App({ client }: AppProps = {}) {
  // Wrap inner elements in the type-safe I18nProvider context
  return (
    <I18nProvider>
      <AppInner client={client} />
    </I18nProvider>
  );
}

export default App;
