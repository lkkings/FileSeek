import { LibraryPage } from "../pages/library/LibraryPage";
import { RecentPage } from "../pages/recent/RecentPage";
import { RecyclePage } from "../pages/recycle/RecyclePage";
import { SettingsPage } from "../pages/settings/SettingsPage";
import { TasksPage } from "../pages/tasks/TasksPage";
import type { NavigationDestination } from "../types/navigation";

interface RouterProps {
  currentPath?: NavigationDestination;
  onNavigate?: (destination: NavigationDestination) => void;
}

export function Router({ currentPath = "library", onNavigate }: RouterProps) {
  switch (currentPath) {
    case "library":
      return <LibraryPage onNavigateSettings={() => onNavigate?.("settings")} />;
    case "recent":
      return <RecentPage />;
    case "trash":
      return <RecyclePage />;
    case "tasks":
      return <TasksPage />;
    case "settings":
      return <SettingsPage />;
    default:
      return <LibraryPage />;
  }
}
