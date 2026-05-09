## 1.2.2
- Updated the helper build to use the bundled ClipTapHelper icon asset for the app window and the built executable.
- Removed inline [SCREENSHOT] placeholder notes from the README.

# Changelog

## v1.2.1

- Refreshed the helper app UI with a darker blue interface.
- Added stronger blue and orange accent colors for dependency actions and live recording state.
- Improved download request cards with darker panels, clearer thumbnail placeholders, and better contrast.
- Reduced the bright white helper window feel.

## v1.2.0

- Added standalone Windows GUI helper app.
- Replaced terminal-first helper workflow with `ClipTapHelper.pyw` and a Windows `.exe` build script.
- Added dependency status UI for yt-dlp and FFmpeg.
- Added install/update button for yt-dlp.
- Added FFmpeg install button through winget.
- Added download request cards with thumbnail, title, status, progress, speed, ETA, and cancel button.
- Added live-stream full-download display mode using an active recording indicator instead of percentage progress.
- Updated README for the GUI helper workflow.

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
