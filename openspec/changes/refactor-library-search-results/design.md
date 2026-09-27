## Context

The current `SearchResultsView` renders search results inside a static grid layout without supporting interactive, deep metadata preview sidebars. See `proposal.md` for details and motivation.

## Goals / Non-Goals

**Goals:**
- Provide clear, fluid, and robust multi-resolution styling for list items and the sidebar details viewer.
- Maintain existing row previews and metadata on collapsed/expanded states, avoiding any content overlap or illegibility.
- Support smooth side-by-side split layout on desktop and responsive slide-in drawer on tablet/mobile views.

**Non-Goals:**
- Modifying backend APIs or the `useFileSearch` custom React hook logic.

## Decisions

### 1. Fluid Flexbox Split Workspace
We will split the workspace into a flex container wrapping both the file list and the details sidebar.
- **Option A (Fixed Widths)**: Keep fixed grid column dimensions. (Rejected because it causes truncation on low-resolution displays).
- **Option B (Fluid Flex Layout - Selected)**: Use flex-grow and `grid-template-columns` with percentage/fraction metrics. This ensures both components adjust dynamically when space shifts.

### 2. Rotated Icon Sort Toggle Indicator
To support ascending and descending sort, we will introduce a CSS-rotated `chevron` icon in a dedicated button adjacent to the sorting dropdown.
- **Option A (Separate Up/Down Arrows)**: Add separate ascending and descending SVGs. (Rejected because it increases DOM size unnecessarily).
- **Option B (CSS-transformed chevron - Selected)**: Rely on CSS transition properties to spin a single existing `chevron` icon. It is lightweight, fluid, and standard.

### 3. Responsive Sliding Drawer on Small Screen
On devices with narrow widths (<= 1024px), displaying a side-by-side layout makes the interface crowded.
- **Selected Approach**: The details panel transitions into a fixed overlay drawer sliding out from the right (`right: 0`), taking up `360px` (or `100%` on mobile). This leaves the original file search list functional underneath.

## Risks / Trade-offs

- **[Risk]** Too many tags or long descriptions on the sidebar details panel causing overflow.
  - **Mitigation**: Add `overflow-y: auto` to the sidebar details container and restrict its height to fit the screen.
- **[Risk]** Large images/videos causing lag or visual distortion in the sidebar preview.
  - **Mitigation**: Constrain the sidebar's preview thumb height to `180px` and use standard CSS `object-fit: cover` to preserve ratios cleanly.
