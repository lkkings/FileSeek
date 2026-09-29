import { useEffect, useRef } from "react";

import { listenSystemImportRequest } from "../../../services/tauri/system-import";

export function useSystemImportRequest(
  onRequest: (request: { paths: string[]; errors: string[] }) => void,
) {
  const requestRef = useRef(onRequest);

  useEffect(() => {
    requestRef.current = onRequest;
  }, [onRequest]);

  useEffect(() => {
    let active = true;
    let unlisten: (() => void) | undefined;

    void listenSystemImportRequest((request) => {
      if (active) {
        requestRef.current(request);
      }
    })
      .then((removeListener) => {
        if (active) {
          unlisten = removeListener;
        } else {
          removeListener();
        }
      })
      .catch(() => undefined);

    return () => {
      active = false;
      unlisten?.();
    };
  }, []);
}
