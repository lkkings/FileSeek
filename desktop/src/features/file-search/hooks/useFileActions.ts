import { useTranslate } from "../../../i18n/useTranslate";
import { openPathInSystem, revealPathInFolder } from "../../../services/tauri/opener";
import type { FileItem } from "../../../services/api/search";

export function useFileActions() {
  const t = useTranslate();

  const openFile = async (file: FileItem) => {
    try {
      const opened = await openPathInSystem(file.path);
      return opened ? null : t("search.desktopOnly", "此操作需要在桌面应用中执行");
    } catch {
      return t("search.openFailed", "打开文件失败");
    }
  };

  const revealFile = async (file: FileItem) => {
    try {
      const revealed = await revealPathInFolder(file.path);
      return revealed ? null : t("search.desktopOnly", "此操作需要在桌面应用中执行");
    } catch {
      return t("search.locateFailed", "定位文件失败");
    }
  };

  return { openFile, revealFile };
}
