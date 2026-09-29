import type { StorageLocation } from "../../settings/types";
import type { ImportFileSelection } from "../types";

export interface SystemImportMapping {
  selections: ImportFileSelection[];
  invalidPaths: string[];
  unmappedPaths: string[];
  storageRequired: boolean;
}

const emptyMapping: SystemImportMapping = {
  selections: [],
  invalidPaths: [],
  unmappedPaths: [],
  storageRequired: false,
};

export function mapSystemImportPaths(
  paths: string[],
  storageLocations: StorageLocation[],
): SystemImportMapping {
  const activeLocations = storageLocations.filter((location) => location.status === "active");
  const mapping: SystemImportMapping = {
    ...emptyMapping,
    selections: [],
    invalidPaths: [],
    unmappedPaths: [],
  };

  for (const path of paths) {
    if (path.trim() === "") {
      mapping.invalidPaths.push(path);
      continue;
    }

    const match = matchStorageLocation(path, activeLocations);
    if (!match) {
      mapping.unmappedPaths.push(path);
      continue;
    }

    mapping.selections.push({
      storageId: match.location.id,
      path: match.sourcePath,
    });
  }

  mapping.storageRequired = mapping.unmappedPaths.length > 0 && activeLocations.length === 0;
  return mapping;
}

function matchStorageLocation(
  path: string,
  locations: StorageLocation[],
): { location: StorageLocation; sourcePath: string } | null {
  const matches = locations
    .map((location) => ({
      location,
      root: storageRoot(location),
      sourcePath: sourcePathForLocation(path, location),
    }))
    .filter((match) => match.root !== null && match.sourcePath !== null)
    .map((match) => ({ ...match, sourcePath: match.sourcePath as string, root: match.root as string }))
    .sort((first, second) => second.root.length - first.root.length);

  return matches[0] ?? null;
}

function storageRoot(location: StorageLocation): string | null {
  if (location.protocol === "file" && location.type === "local") {
    return normalizePath(location.root_path || "/");
  }
  if (location.protocol === "mounted") {
    return normalizePath(location.root_path || location.endpoint);
  }
  return null;
}

function sourcePathForLocation(path: string, location: StorageLocation): string | null {
  const root = storageRoot(location);
  if (!root) {
    return null;
  }

  const normalizedPath = normalizePath(path);
  const relative = relativeToRoot(normalizedPath, root);
  if (relative === null) {
    return null;
  }

  if (location.type === "local") {
    return normalizedPath;
  }
  return relative.replace(/^\/+/, "");
}

function normalizePath(path: string): string {
  const normalized = path.replace(/\\/g, "/").replace(/\/+/g, "/");
  return normalized.endsWith("/") && normalized !== "/" ? normalized.slice(0, -1) : normalized;
}

function relativeToRoot(path: string, root: string): string | null {
  if (root === "" || root === "/") {
    return path;
  }
  if (samePath(path, root)) {
    return "";
  }
  const separator = root.endsWith("/") ? "" : "/";
  if (!pathStartsWith(path, root + separator)) {
    return null;
  }
  return path.slice(root.length + separator.length);
}

function samePath(first: string, second: string): boolean {
  return comparePath(first, second) === 0;
}

function pathStartsWith(path: string, prefix: string): boolean {
  return comparePath(path.slice(0, prefix.length), prefix) === 0;
}

function comparePath(first: string, second: string): number {
  const isWindowsPath = /^[a-z]:\//i.test(first) || /^[a-z]:\//i.test(second);
  return (isWindowsPath ? first.toLowerCase() : first).localeCompare(
    isWindowsPath ? second.toLowerCase() : second,
  );
}
