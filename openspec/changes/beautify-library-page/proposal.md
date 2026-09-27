## Why

The current library page's folder list view needs design improvements for desktop users. The "Create Folder" button is visually oversized and lacks sophisticated interaction styling. Additionally, the vertical transition between the section heading and the folder grid is abrupt, missing a subtle, modern separator to establish structured visual hierarchy and depth.

## What Changes

- **Refined Folder Action Button**: Re-style the "Create Folder" button to be more compact and visually delicate on desktop, stripping the desktop-forced 46px min-height to a clean 36px height, while maintaining the touch-friendly size target for mobile viewports (`<= 780px`).
- **Semi-transparent Tech-glass Aesthetics**: Redesign the "Create Folder" button to start as a subtle, semi-transparent border button with high-contrast, low-weight branding, transitioning dynamically via smooth spring easing into a vibrant, glowing gradient on hover.
- **Section Heading Divider**: Introduce a modern, linear gradient divider below the folder heading, featuring a soft middle-glow fading out towards both horizontal ends, bringing polished spacing and tech-aesthetic structure to the page.
- **Icon Scale Calibration**: Scale down the folder header icon and button icons slightly for precise pixel proportions that balance with the refined typography.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `file-search/results`: Modifies the default Library folder list view visual presentation and header layout.

## Impact

- `desktop/src/features/library/components/FolderSection.tsx`: Header icon size calibration, addition of `<div className="section-heading-divider" />`, and action icon sizing.
- `desktop/src/features/library/components/library.css`: Styling overrides for `.create-button`, touch-target responsive adjustments, and style definitions for `.section-heading-divider`.
