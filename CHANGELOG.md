# Changelog

## v1.3

**ClipTap Helper**
- Added YouTube playlist download mode in the helper queue using yt-dlp playlist handling.
- Added per-job Cancel controls, working persistent History, real Clear Completed behavior, and updated the helper sidebar version to 1.3.
- Removed misleading Stop controls because safe pause/resume support is not available for the current yt-dlp/FFmpeg subprocess workflow.
- Fixed section downloads getting stuck at the metadata step by forcing YouTube metadata reads to target the current video instead of playlist context.

**ClipTap**
- Enlarged the player toolbar ClipTap glyph to better match adjacent YouTube controls and forced existing SPA-mounted buttons to refresh to the latest icon markup.
- Reduced and re-centered the player toolbar ClipTap icon, and refined its corner-frame silhouette so it fits the native YouTube toolbar more naturally.
- Reworked the player toolbar ClipTap icon into a native-style filled glyph that reflects the ClipTap corner-frame logo instead of a plain download arrow.
- Rebuilt the YouTube playlist download and player toolbar icons as native-style filled SVG glyphs based on YouTube icon source patterns.
- Refined the YouTube playlist download icon so it matches native YouTube playlist toolbar glyph proportions more closely.
- Fixed logo/icon visibility by using the approved SVG path with explicit white stroke styling and restoring the website brand mark image.
- Refined the YouTube playlist download icon to use a cleaner white native-style SVG glyph with balanced stroke geometry.
- Fixed YouTube playlist download button mounting so the native-style white icon is inserted even when YouTube action button DOM changes.
- Rebuilt YouTube playlist download buttons by cloning nearby native controls and using a centered white filled 24px Material-style icon.
- Rebuilt the YouTube playlist download buttons as white, centered, filled native-style controls that visually match adjacent YouTube icons.
- Replaced playlist download image assets with inline YouTube-style SVG buttons so the controls blend with adjacent native icons.
- Added playlist download buttons on YouTube playlist pages and watch pages with playlist panels.
- Clarified current and planned service support messaging and added expandable YouTube capability details.
- Aligned the Supported Sites top header markup and background treatment with the main homepage header.
- Fixed README image references so the documentation only uses available project image assets.
- Matched the Supported Sites top header styling to the main homepage header for consistent navigation across the site.
- Kept the hero trust labels on a single line on desktop layouts.
- Updated the main View on GitHub buttons to use the supplied GitHub image asset and a wider button width.
- Updated the main Download for Windows buttons to load their icons from image assets.
- Restyled the main Download for Windows buttons with wider padding, a deeper left-to-right gradient, and hover motion to better match the landing page mockup.
- Refined the Supported Sites native service card layout so descriptions use the full row beneath the title and status badge in dense three-column listings.
- Rebuilt the GitHub Pages promotional website to match the provided dark desktop mockup.
- Added a separate Supported Sites page for native ClipTap service support and planned integrations.
- Matched the Supported Sites navigation to the main site.
- Replaced CSS-only promo visuals with supplied product and CTA image assets.

## v1.2.1

**ClipTap Helper**
- Shortened queue status labels such as `Downloading...` and `Trimming...` to prevent wrapped status text in the manager table.
- Slightly widened the Status column and applied no-wrap ellipsis styling for compact queue rows.
- Changed selected section trimming to accurate FFmpeg transcoding so exported clips match the start/end positions selected in YouTube.
- Moved section download working files from the visible download folder to the OS temporary directory.
- Added cleanup for leftover `.part`, `.ytdl`, `.temp`, and legacy `.cliptap-temp` files after jobs finish when no other downloads are active.
- Reworked selected section downloads to avoid the yt-dlp `--download-sections` stall path by downloading source media to a temporary file and trimming it locally with FFmpeg.
- Added staged section progress: source media download first, then FFmpeg section cutting.
- Added automatic cleanup for temporary section download files.
- Added FFmpeg `-progress pipe:1` output for section downloads so the manager can receive real selected-range progress updates instead of staying at 1%.
- Added parsing for FFmpeg `out_time`, `out_time_ms`, and `out_time_us` progress records.
- Improved section progress calculation for both output-relative and source-timestamp-relative FFmpeg time values.
- Changed section jobs to enter a selected-section download status before media processing starts.
- Fixed section downloads appearing stuck at 0% by reading yt-dlp/FFmpeg progress output split by both newlines and carriage returns.
- Added FFmpeg time-based progress parsing for selected section downloads.
- Prefer the external `python -m yt_dlp` launcher before the embedded helper wrapper when running from source.
- Hardened the bundled yt-dlp CLI wrapper so it no longer depends on importing `main` from `yt_dlp.__main__`.
- Added forced overwrite handling to avoid download jobs waiting on existing output file prompts.

**ClipTap**
- No extension UI changes in this patch.

## v1.2

**ClipTap Helper**
- Fixed Download History page spacing so the empty state card no longer looks broken.
- Fixed the Save folder field so the manager writes the output path into the input value instead of leaving it as Loading.
- Fixed the bundled yt-dlp launcher by importing yt-dlp from the package entry point instead of `yt_dlp.__main__`.
- Improved queue table column spacing between Platform, Format, Progress, and Status.
- Changed the queue Format column to show media format labels such as `mp4 (1080p)` or `audio (mp3)` instead of download mode labels like full/section.
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
- Added a GitHub Pages-ready promotional website under `docs/` with a dark landing page, product sections, installation steps, screenshot slots, and deployment notes.
- Updated package script defaults to `v1.2-8`.
- Updated package script defaults to `v1.2-7`.
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
