import { useTranslate } from "../../../i18n/useTranslate";
import { revealPathInFolder } from "../../../services/tauri/opener";
import type { FileItem } from "../../../services/api/search";

export function useFileActions() {
  const t = useTranslate();

  const revealFile = async (file: FileItem) => {
    try {
      const revealed = await revealPathInFolder(file.path);
      return revealed ? null : t("search.desktopOnly", "此操作需要在桌面应用中执行");
    } catch {
      return t("search.locateFailed", "定位文件失败");
    }
  };

  return { revealFile };
}
