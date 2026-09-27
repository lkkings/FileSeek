import { type ReactNode } from "react";

export type IconName =
  | "archive"
  | "calendar"
  | "chevron"
  | "clock"
  | "close"
  | "cornerDownLeft"
  | "document"
  | "edit"
  | "eye"
  | "filter"
  | "folder"
  | "image"
  | "more"
  | "plus"
  | "pulse"
  | "refresh"
  | "search"
  | "settings"
  | "sort"
  | "sort-asc"
  | "sort-desc"
  | "trash"
  | "video";

const iconPaths: Record<IconName, ReactNode> = {
  archive: <><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M8 9h8M8 13h3M13 13h3" /></>,
  calendar: <><rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M7 3v4M17 3v4M4 9h16" /></>,
  chevron: <path d="m7 9 5 5 5-5" />,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></>,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  cornerDownLeft: <><path d="M9 10 4 15l5 5" /><path d="M20 4v7a4 4 0 0 1-4 4H4" /></>,
  document: <><path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" /><path d="M14 3.5V8h4M9 12h6M9 16h6" /></>,
  edit: <><path d="m14 5 5 5" /><path d="M5 19h4l10-10a2.1 2.1 0 0 0-3-3L6 16v3Z" /></>,
  eye: <><path d="M2.8 12s3.3-5.2 9.2-5.2S21.2 12 21.2 12 17.9 17.2 12 17.2 2.8 12 2.8 12Z" /><circle cx="12" cy="12" r="2.5" /></>,
  filter: <path d="M4 5h16l-6.2 7.2v5.4l-3.6 1.9v-7.3L4 5Z" />,
  folder: <path d="M3.5 6.7A2.2 2.2 0 0 1 5.7 4.5h4l2 2h6.6a2.2 2.2 0 0 1 2.2 2.2v8.6a2.2 2.2 0 0 1-2.2 2.2H5.7a2.2 2.2 0 0 1-2.2-2.2V6.7Z" />,
  image: <><rect x="3.5" y="4.5" width="17" height="15" rx="2" /><circle cx="8.5" cy="9" r="1.2" /><path d="m4.5 17 4.6-4.7 3.3 3 2.1-2.1 2.1-2.1 4.9 4.8" /></>,
  more: <><circle cx="5" cy="12" r=".8" fill="currentColor" /><circle cx="12" cy="12" r=".8" fill="currentColor" /><circle cx="19" cy="12" r=".8" fill="currentColor" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  pulse: <path d="M3 12h4l2-7 4 14 2-7h6" />,
  refresh: <><path d="M20 11a8 8 0 0 0-14.8-3L4 10" /><path d="M4 5v5h5M4 13a8 8 0 0 0 14.8 3L20 14" /><path d="M20 19v-5h-5" /></>,
  search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.5 4.5" /></>,
  settings: <><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.09a2 2 0 0 1 1 1.74v.5a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z" /><circle cx="12" cy="12" r="3" /></>,
  sort: <><path d="M4 6h11M4 12h8M4 18h5" /><path d="m17 7 3 3 3-3M20 10V4" /></>,
  "sort-asc": <><path d="M4 6h11M4 12h8M4 18h5" /><path d="m17 7 3-3 3 3M20 4v6" /></>,
  "sort-desc": <><path d="M4 6h11M4 12h8M4 18h5" /><path d="m17 7 3 3 3-3M20 10V4" /></>,
  trash: <><path d="M4.5 7h15M9 4h6M7 7l.7 13h8.6L17 7M10 10.5v6M14 10.5v6" /></>,
  video: <><rect x="3.5" y="5" width="12.5" height="14" rx="2" /><path d="m16 10 4.5-2.5v9L16 14" /><path d="m9 9 3.5 3L9 15V9Z" /></>,
};

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {iconPaths[name]}
    </svg>
  );
}
