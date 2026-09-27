import { useEffect } from "react";
import { Icon, type IconName } from "./Icon";
import "./notice.css";

interface NoticeProps {
  message: string;
  onClose: () => void;
  duration?: number;
}

function getIconForMessage(msg: string): IconName {
  const text = msg.toLowerCase();
  if (text.includes("删") || text.includes("delete") || text.includes("trash")) return "trash";
  if (text.includes("建") || text.includes("create") || text.includes("plus")) return "plus";
  if (text.includes("修") || text.includes("改") || text.includes("更") || text.includes("update") || text.includes("edit")) return "edit";
  if (text.includes("搜") || text.includes("找") || text.includes("search") || text.includes("found")) return "search";
  if (text.includes("重置") || text.includes("reset") || text.includes("refresh")) return "refresh";
  if (text.includes("切") || text.includes("switch") || text.includes("settings") || text.includes("设置")) return "settings";
  return "pulse";
}

export function Notice({ message, onClose, duration = 4000 }: NoticeProps) {
  // Auto close notice after duration
  useEffect(() => {
    if (!duration) return;
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [message, duration, onClose]);

  const statusIcon = getIconForMessage(message);

  return (
    <div className="notice-toast" role="status" aria-live="polite">
      <div className="notice-icon-wrap" aria-hidden="true">
        <Icon name={statusIcon} size={16} />
      </div>
      <span className="notice-message">{message}</span>
      <button 
        className="notice-close-btn" 
        type="button" 
        onClick={onClose} 
        aria-label="关闭提示"
        title="关闭提示"
      >
        <Icon name="close" size={14} />
      </button>
    </div>
  );
}
