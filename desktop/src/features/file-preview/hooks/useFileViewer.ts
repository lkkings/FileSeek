import { useCallback, useState } from "react";

import type { FilePreviewItem } from "../types";

export function useFileViewer() {
  const [item, setItem] = useState<FilePreviewItem | null>(null);

  const openFile = useCallback((nextItem: FilePreviewItem) => {
    setItem(nextItem);
  }, []);

  const onClose = useCallback(() => {
    setItem(null);
  }, []);

  return {
    isOpen: item !== null,
    item,
    onClose,
    openFile,
  };
}
