import { type ReactNode, useState, isValidElement, cloneElement } from "react";
import { Notice } from "../components/Notice";
import { AppSidebar } from "../components/navigation/AppSidebar";
import { useTranslate } from "../i18n/useTranslate";
import type { NavigationDestination } from "../types/navigation";
import "./app-shell.css";

export function AppShell({ children }: { children: ReactNode }) {
  const t = useTranslate();
  const [activeNavigation, setActiveNavigation] = useState<NavigationDestination>("library");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notice, setNotice] = useState("");

  function handleNavigation(destination: NavigationDestination) {
    setActiveNavigation(destination);
    const labels: Record<NavigationDestination, string> = {
      library: t("nav.library", "资源库"),
      recent: t("nav.recent", "最近访问"),
      trash: t("nav.trash", "回收站"),
      tasks: t("nav.tasks", "任务队列"),
      settings: t("nav.settings", "系统设置"),
    };
    setNotice(`${t("nav.switched", "已切换到")}${labels[destination]}`);
  }

  const enhancedChildren = isValidElement(children)
    ? cloneElement(children as React.ReactElement<{ currentPath?: NavigationDestination }>, {
      currentPath: activeNavigation,
    })
    : children;

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <header className="app-mobile-header">
        <button className="mobile-menu-trigger" type="button" aria-label={t("nav.expand", "展开菜单")} onClick={() => setMobileMenuOpen(true)}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
        <span className="mobile-brand-title">FileSeek</span>
        <div className="mobile-header-spacer" />
      </header>

      <AppSidebar 
        active={activeNavigation} 
        collapsed={sidebarCollapsed} 
        onNavigate={handleNavigation} 
        onToggle={() => setSidebarCollapsed((current) => !current)} 
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />
      {enhancedChildren}
      {notice && <Notice message={notice} onClose={() => setNotice("")} />}
    </div>
  );
}
