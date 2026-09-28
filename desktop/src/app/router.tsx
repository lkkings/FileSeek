import { LibraryPage } from "../pages/library/LibraryPage";
import { RecentPage } from "../pages/recent/RecentPage";
import { RecyclePage } from "../pages/recycle/RecyclePage";
import { SettingsPage } from "../pages/settings/SettingsPage";
import { TasksPage } from "../pages/tasks/TasksPage";
import type { NavigationDestination } from "../types/navigation";

interface RouterProps {
  currentPath?: NavigationDestination;
}

export function Router({ currentPath = "library" }: RouterProps) {
  switch (currentPath) {
    case "library":
      return <LibraryPage />;
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
