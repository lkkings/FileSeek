## Context

The `SearchBar` currently spans 100% width with a fixed height of `64px` in `search.css`. We will reduce this height to `48px` to make it sleeker and more professional.
To keep the search bar hidden in the folder view until clicked:
- Introduce a state `folderSearchVisible` in `LibraryPage.tsx` when a folder is active.
- If `currentFolder` is set and `folderSearchVisible` is false, show a search action trigger button (or show search icon button).
- Ensure a margin-bottom of `24px` is set on the search bar or filter area to give breathing room.

## Goals / Non-Goals

**Goals:**
- Make SearchBar smaller (height `48px`, icon size smaller).
- Toggle SearchBar visibility in FolderDetails mode via a search icon.
- Ensure correct layout distance/spacing between search bar area and lower content.

**Non-Goals:**
- Do not affect global search bar visibility when *outside* of a folder.
