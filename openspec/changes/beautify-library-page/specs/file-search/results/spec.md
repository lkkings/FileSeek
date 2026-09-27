## ADDED Requirements

### Requirement: Refined and Highly Interactive Folder Heading Layout
The default Library page header section SHALL display a refined layout containing a title, an aligned header icon, a stylized linear gradient separator, and a compact "Create Folder" action button.

#### Scenario: Verify Folder heading layout elements
- **WHEN** the user is on the default Library list page view
- **THEN** the heading section displays a title with a folder icon scaled to exactly 32px
- **AND** a "Create Folder" button is displayed on the opposite side
- **AND** a linear gradient separator is displayed directly below the heading line, stretching 100% width and fading out at both horizontal ends

### Requirement: Micro-interactive Action Button
The "Create Folder" action button SHALL support two distinct visual states depending on user interaction: a calm semi-transparent state, and a glowing gradient interactive state.
- Default state: a semi-transparent background with a subtle border and high-contrast, low-weight branding, with a height of exactly 36px on desktop devices.
- Interactive hover/focus state: transitioned via a smooth CSS cubic-bezier transition into a filled glowing blue gradient with an active shadow glow.
- Responsive scaling: on mobile and small-viewport devices (<= 780px), the button height SHALL scale to 44px for standard touch target compatibility.

#### Scenario: Verify Create Folder button styling states on desktop
- **WHEN** the user views the "Create Folder" button on desktop in its idle state
- **THEN** the button is styled with a subtle border, a semi-transparent background, a height of 36px, and a plus icon sized to 14px
- **WHEN** the user hovers over the button
- **THEN** it transitions smoothly via spring-feel cubic-bezier easing to a blue gradient background with a 3D lift translate-y action and an active glowing shadow

#### Scenario: Verify Create Folder button responsive scaling
- **WHEN** the user views the Library page on a viewport width of 780px or less
- **THEN** the "Create Folder" button height is scaled up to exactly 44px to satisfy standard mobile touch targets
