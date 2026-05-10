# Changelog

## v1.2

**ClipTap Helper**
- Reworked the helper into a single-file Web UI manager source (`helper/ClipTapHelper.py`).
- Added a one-file Windows helper build script (`helper/build-standalone.ps1`).
- Added a GitHub Actions workflow for building `ClipTapHelper.exe` on Windows.
- Embedded the manager HTML, CSS, and JavaScript into the helper source so the standalone executable does not need separate web asset files.
- Replaced the standalone GUI helper app with a local Web UI manager.
- Removed the PyInstaller executable build path and old helper app assets.
- Added manager endpoints for dependency checks, install actions, download progress, cancellation, and shutdown.
- Redesigned the helper Web Manager into a dark dashboard layout based on the provided mockup.
- Moved the ClipTap Helper brand block from the sidebar into a full-width top header.
- Removed divider styling from the top header and left navigation so both blend into the main background.
- Increased the left navigation item text size for better readability.
- Replaced text-based navigation and section icons with inline SVG icons.
- Reduced the left toolbar item height and tightened spacing between toolbar elements.
- Added dependency status UI for yt-dlp and FFmpeg.
- Added install/update button for yt-dlp.
- Added FFmpeg install button through winget.
- Added download request cards with thumbnail, title, status, progress, speed, ETA, and cancel controls.
- Added live-stream full-download display mode using an active recording indicator instead of percentage progress.
- Updated README for the Web UI manager workflow.

- Tightened the Helper dashboard layout to better match the target mockup.
- Reduced card padding, table row height, form control height, button sizing, and grid gaps for a denser dashboard.
- Refined the dark blue/purple theme, card contrast, borders, sidebar spacing, queue table, defaults form, and logs panel styling.

- Fixed the Helper AppShell layout so the main dashboard fills the remaining viewport width.
- Constrained page scrolling to the main content area while keeping the sidebar fixed at full viewport height.
- Removed the dashboard width cap and adjusted wide-screen grid columns so cards use available space naturally.
- Fixed clipped sidebar brand text by tightening the brand block and allowing the subtitle to wrap.
- Changed sidebar navigation from in-page anchor scrolling to page-style dashboard view switching.

**ClipTap**
- Updated package script defaults to `v1.2-6`.
- Updated package script defaults to `v1.2-5`.
- Restored package output names to use version and specific build IDs.
- Updated package script defaults to `v1.2-4`.

## v1.1.7

- Translated extension UI, helper messages, README, and changelog to English.

## v1.1.6

- Added selected range loop playback.

## v1.1.5

- Improved yt-dlp detection.
- Added fallback for Python module based yt-dlp execution.
- Improved FFmpeg handling.

## v1.1.4

- Refined player timeline handles.
- Added decimal timestamp input support.

## v1.1.3

- Updated ClipTap icon.

## v1.1.2

- Moved the player panel to avoid blocking the timeline.
- Added full video download.

## v1.1.1

- Fixed YouTube page freeze caused by heavy DOM observation.

## v1.1.0

- Moved ClipTap controls into the YouTube player.
- Added timeline handles for start/end selection.

## v1.0.0

- Initial local helper server version.
