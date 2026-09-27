import { Icon, type IconName } from "../Icon";
import { useTranslate } from "../../i18n/useTranslate";
import type { NavigationDestination } from "../../types/navigation";
import "./AppSidebar.css";

interface AppSidebarProps {
  active: NavigationDestination;
  collapsed: boolean;
  onNavigate: (destination: NavigationDestination) => void;
  onToggle: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

const navigation: Array<{ id: Exclude<NavigationDestination, "settings">; labelId: string; label: string; icon: IconName }> = [
  { id: "library", labelId: "nav.library", label: "资源库", icon: "archive" },
  { id: "recent", labelId: "nav.recent", label: "最近访问", icon: "clock" },
  { id: "trash", labelId: "nav.trash", label: "回收站", icon: "trash" },
  { id: "tasks", labelId: "nav.tasks", label: "任务队列", icon: "pulse" },
];

export function AppSidebar({ active, collapsed, onNavigate, onToggle, mobileOpen, onMobileClose }: AppSidebarProps) {
  const t = useTranslate();

  return (
    <>
      {mobileOpen && <div className="sidebar-backdrop" onClick={onMobileClose} />}
      <aside className={`sidebar ${collapsed ? "is-collapsed" : ""} ${mobileOpen ? "is-mobile-open" : ""}`}>
        <div className="sidebar-header">
          <div className="brand" aria-label="FileSeek">
            <button className="brand-mark" type="button" aria-label={collapsed ? t("nav.expand", "展开侧边栏") : t("nav.collapse", "折叠侧边栏")} title={collapsed ? t("nav.expand", "展开侧边栏") : t("nav.collapse", "折叠侧边栏")} onClick={onToggle}><Icon name="search" size={27} /></button>
            <span>FileSeek</span>
          </div>
          {mobileOpen && onMobileClose && (
            <button className="sidebar-mobile-close" type="button" aria-label={t("dialog.close", "关闭")} onClick={onMobileClose}>
              <Icon name="close" size={21} />
            </button>
          )}
        </div>

        <nav className="primary-nav" aria-label={t("nav.label", "主导航")}>
          {navigation.map((item) => (
            <button className={`nav-item ${active === item.id ? "is-active" : ""}`} key={item.id} type="button" aria-label={t(item.labelId, item.label)} title={collapsed ? t(item.labelId, item.label) : undefined} onClick={() => { onNavigate(item.id); onMobileClose?.(); }}>
              <Icon name={item.icon} size={28} />
              <span>{t(item.labelId, item.label)}</span>
            </button>
          ))}
        </nav>

        <button className={`nav-item settings-link ${active === "settings" ? "is-active" : ""}`} type="button" aria-label={t("nav.settings", "系统设置")} title={collapsed ? t("nav.settings", "系统设置") : undefined} onClick={() => { onNavigate("settings"); onMobileClose?.(); }}>
          <Icon name="settings" size={28} />
          <span>{t("nav.settings", "系统设置")}</span>
        </button>
      </aside>
    </>
  );
}
