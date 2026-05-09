# Changelog

## v1.1.7

- Translate the extension UI, helper messages, manifest description, README, and changelog to English.
- Keep existing ClipTap behavior unchanged.

## v1.1.6

- Add a repeat toggle button to the ClipTap player panel.
- Automatically loop playback inside the selected start/end range while repeat is enabled.
- Seek to the selected start point when repeat is turned on.

## v1.1.5

- Fix helper detection when yt-dlp is installed as a Python module but not added to PATH.
- Add clearer FFmpeg error guidance and support `helper/bin/ffmpeg.exe` as a local fallback path.

## v1.1.4

- Change start/end timeline handles to round playhead-like markers.
- Use blue for the start handle and orange for the end handle.
- Increase handle hit targets so they are easier to drag.
- Move the ClipTap player panel slightly downward.
- Allow decimal timestamp entry in the player panel.

## v1.1.2

- Move the ClipTap player panel upward so it no longer blocks the progress bar.
- Add a full video download button to the player panel and popup.
- Add helper support for section and full download modes.
- Use `extension/icons/cliptap.png` for the player control icon so users can replace the logo.

## v1.1.1

- Remove the global MutationObserver render loop that could freeze YouTube pages.
- Throttle rendering and rely more on YouTube navigation events for rediscovery.

## v1.1.0

- Move ClipTap from a fixed page panel into YouTube's player controls.
- Add draggable start/end handles directly on the YouTube progress bar.
- Seek the video while dragging a start/end handle.

## v1.0.0

- Add popup controls for section downloading with yt-dlp.
- Add local Python helper server.
- Add simple in-page control panel.
