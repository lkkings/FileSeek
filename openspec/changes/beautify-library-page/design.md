## Context

The current user interface on the library page of the FileSeek desktop application suffers from subtle visual spacing and component proportion issues. The "Create Folder" button uses the default high-saturation gradient background styling from `library.css` and enforces a touch-target size height of 46px on all screen sizes, leading to a clunky aesthetic on desktop viewports. See proposal.md for motivation and background.

## Goals / Non-Goals

**Goals:**
- Recalibrate the height and layout of `.create-button` to fit seamlessly into desktop screens at 36px height with refined sizing and padding.
- Add an elegant glassmorphic border button style that is semi-transparent in its default idle state, and transitions dynamically to the active vibrant blue gradient on hover.
- Introduce an elegant gradient separator underneath the section header.
- Maintain full compatibility with touch devices (>= 44px height targets) on mobile viewports (`<= 780px`).

**Non-Goals:**
- Modifying the folder grid structure, card styles, list mechanics, dialog modals, or state workflows.
- Refactoring folder actions such as editing, deleting, or loading state management.

## Decisions

### 1. Refined Layout & Icon Sizing in `FolderSection`
- **Choice**: Scale down header elements:
  - Header icon name `"folder"` scaled from `38` to `32`.
  - Header action icon name `"plus"` in `.create-button` scaled from `18` to `14`.
- **Rationale**: Keeps icon sizes visually proportional with desktop typography and the compact 36px button height.
- **Alternatives Considered**: Keeping original icon sizes. This made the compact button appear crowded and unbalanced.

### 2. Micro-Interactive Styling with CSS Transition
- **Choice**: Transition the button states using custom CSS:
  - **Idle**: `background: rgba(39, 175, 255, 0.05); border: 1px solid rgba(39, 175, 255, 0.28); color: #c2e2ff;`
  - **Hover**: `background: linear-gradient(135deg, #27afff, #0967ec); border-color: transparent; color: #fff;`
  - Apply custom bezier curve: `transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.1s ease;`
- **Rationale**: Semi-transparent idle style aligns with the "dark tech" aesthetic of the desktop app and highlights the heading title rather than competing with it. Hover transition adds satisfying feedback.
- **Alternatives Considered**: Full solid background colors or outline-only states. None of these provided the high-tech, micro-interactive glassmorphism feeling.

### 3. Responsive Target Media Queries
- **Choice**: Reset `.create-button` height to `36px` and `min-height: unset` by default, but restore the touch target sizes in `@media (max-width: 780px)` viewport configuration to `height: 44px`.
- **Rationale**: Fulfills both desktop visual refinement and mobile accessibility guidelines without introducing runtime JS viewport checks.

### 4. Gradient Micro-separator Line
- **Choice**: Implement a linear-gradient line via a simple semantic `div` positioned in `FolderSection` right under the heading wrapper:
  ```css
  .section-heading-divider {
    height: 1px;
    width: 100%;
    background: linear-gradient(90deg, 
      rgba(39, 175, 255, 0) 0%, 
      rgba(39, 175, 255, 0.2) 15%, 
      rgba(39, 175, 255, 0.2) 85%, 
      rgba(39, 175, 255, 0) 100%
    );
    margin-top: 4px;
    margin-bottom: 24px;
  }
  ```
- **Rationale**: An elegant fading line acts as a visual break that structure-delimits header actions and the grid content while retaining screen space.

## Risks / Trade-offs

- **[Risk]**: Compact buttons may be harder to hover or click for users with motor impairments on larger touch-capable monitors.
  - **Mitigation**: Maintain interactive outline/focus rings on keyboard tab navigation (`:focus-visible`) and keep transitions snappy but clean.
- **[Risk]**: Gradient divider line may clip content if the container padding is narrow.
  - **Mitigation**: Pair layout paddings with established `.main-content` margins and set explicit top/bottom spacing.
