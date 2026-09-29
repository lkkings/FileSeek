## Purpose

Provides consistent, trustworthy previews and in-app viewing for indexed documents, images, and videos across file lists, detail surfaces, and full-screen viewing.

## ADDED Requirements

### Requirement: File list preview rendering
The system SHALL render a preview cell for every visible file according to its category and format.

#### Scenario: Document list preview
- **WHEN** a document file is visible in a list or grid
- **THEN** the system SHALL show an icon or compact visual that identifies its specific document format rather than a generic simulated media scene

#### Scenario: Image list preview
- **WHEN** a supported image file is visible in a list or grid
- **THEN** the system SHALL request and display an image thumbnail for that file

#### Scenario: Unsupported image list preview
- **WHEN** a HEIF, HEIC, or SVG file is visible in a list or grid
- **THEN** the system SHALL show an unsupported-preview state without requesting a thumbnail

#### Scenario: Video list preview
- **WHEN** a video file is visible in a list or grid
- **THEN** the system SHALL request and display a video-frame thumbnail with a visible playback affordance

#### Scenario: Thumbnail failure
- **WHEN** an image or video thumbnail cannot be loaded
- **THEN** the system SHALL show the category-specific fallback visual without replacing or removing the file row

### Requirement: File detail drawer preview
The file detail drawer SHALL render a preview appropriate to the selected file's category and format.

#### Scenario: Supported document detail preview
- **WHEN** the drawer is opened for a supported document format
- **THEN** the system SHALL render the first page or first logical document view without leaving the drawer

#### Scenario: Image detail preview
- **WHEN** the drawer is opened for a supported image
- **THEN** the system SHALL display the image preview within the drawer

#### Scenario: Unsupported image detail preview
- **WHEN** the drawer is opened for a HEIF, HEIC, or SVG file
- **THEN** the system SHALL show an unsupported-preview state without displaying the image

#### Scenario: Video detail preview
- **WHEN** the drawer is opened for a video
- **THEN** the system SHALL display the video thumbnail and a playback control
- **WHEN** the playback control is activated
- **THEN** the system SHALL replace the thumbnail with an inline video player for that file

#### Scenario: Unsupported document detail preview
- **WHEN** the drawer is opened for a document format that cannot be rendered in-app
- **THEN** the system SHALL show a format-specific fallback and an explanatory message

### Requirement: In-app file opening
The system SHALL open files in an application-internal full-screen or page viewer rather than invoking the operating system's default file handler.

#### Scenario: Open document
- **WHEN** the open action is activated for a supported document
- **THEN** the system SHALL open the document in the in-app document viewer with navigation and document controls

#### Scenario: Open image
- **WHEN** the open action is activated for a supported image
- **THEN** the system SHALL open the image in the in-app image viewer

#### Scenario: Open unsupported image
- **WHEN** the open action is activated for a HEIF, HEIC, or SVG file
- **THEN** the system SHALL remain in the application and show an unsupported-format state

#### Scenario: Open video
- **WHEN** the open action is activated for a video
- **THEN** the system SHALL open the video in the in-app video player

#### Scenario: Open unsupported document
- **WHEN** the open action is activated for an unsupported document
- **THEN** the system SHALL remain in the application and show an unsupported-format state

### Requirement: Thumbnail retrieval
The system SHALL provide an authenticated thumbnail resource for indexed image and video files.

#### Scenario: Request list-size thumbnail
- **WHEN** a list-size thumbnail is requested for an existing image or video
- **THEN** the system SHALL return a generated thumbnail image and metadata that allows safe browser caching

#### Scenario: Request detail-size thumbnail
- **WHEN** a detail-size thumbnail is requested for an existing image or video
- **THEN** the system SHALL return a larger generated thumbnail suitable for the detail drawer

#### Scenario: Unknown file
- **WHEN** a thumbnail is requested for a file that does not exist or is inaccessible
- **THEN** the system SHALL return an appropriate error response without exposing the file path

#### Scenario: Repeated thumbnail requests
- **WHEN** the same valid thumbnail is requested again and the source file has not changed
- **THEN** the system SHALL reuse the cached thumbnail instead of regenerating it

### Requirement: Secure binary preview transport
The system SHALL provide binary preview access in browser development and packaged desktop builds without exposing backend credentials to the WebView.

#### Scenario: Browser development preview
- **WHEN** the desktop UI runs through the development server
- **THEN** document, image, and video previews SHALL load through the local development proxy

#### Scenario: Packaged desktop preview
- **WHEN** the desktop UI runs as a packaged Tauri application
- **THEN** document, image, and video preview requests SHALL pass through a WebView-accessible binary transport that adds backend authentication outside the WebView

#### Scenario: Video seeking
- **WHEN** a user seeks within a video
- **THEN** the preview transport SHALL preserve range requests and support player seeking

### Requirement: Preview accessibility and state handling
The system SHALL communicate preview loading, unsupported, and failed states accessibly.

#### Scenario: Loading preview
- **WHEN** a preview resource is loading
- **THEN** the system SHALL expose a loading state that does not block interaction with the containing file item

#### Scenario: Preview error
- **WHEN** a preview resource fails to load
- **THEN** the system SHALL expose an error or fallback state and retain the open action where the underlying file is still available
