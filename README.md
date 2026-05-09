# ClipTap

A lightweight browser extension for clipping and downloading selected sections of YouTube videos with `yt-dlp`.

ClipTap adds a small button directly inside the YouTube player controls. From there, you can mark a start point, mark an end point, drag timeline handles, loop the selected range, and download either the selected section or the full video through a local helper.

> Use ClipTap only for videos you own, videos you have permission to download, or videos you are otherwise legally allowed to keep. YouTube and other services may have their own terms of service.

## Screenshots

> The repository does not include screenshots by default. Add your own images using the paths below.

![ClipTap button in the YouTube player](docs/images/cliptap-player-button.png)

[SCREENSHOT: ClipTap button placed naturally next to the YouTube player control buttons, such as Settings, Fullscreen, and SponsorBlock.]

![ClipTap panel opened inside the player](docs/images/cliptap-panel.png)

[SCREENSHOT: ClipTap panel opened above the YouTube player utility controls. Show the Start, End, Section Download, Full Download, and Loop controls.]

![Start and end handles on the timeline](docs/images/cliptap-timeline-handles.png)

[SCREENSHOT: YouTube progress bar with a blue circular start handle and an orange circular end handle, shaped like the native YouTube playhead.]

![Loop mode enabled](docs/images/cliptap-loop-enabled.png)

[SCREENSHOT: Loop toggle enabled while the selected start-to-end range is repeating.]

![ClipTap helper terminal](docs/images/cliptap-helper-terminal.png)

[SCREENSHOT: ClipTap helper terminal running successfully, showing that yt-dlp and ffmpeg were detected.]

Recommended screenshot file list:

```text
docs/images/cliptap-player-button.png
docs/images/cliptap-panel.png
docs/images/cliptap-timeline-handles.png
docs/images/cliptap-loop-enabled.png
docs/images/cliptap-helper-terminal.png
docs/images/firefox-temporary-addon.png
docs/images/chrome-load-unpacked.png
```

## Features

- Adds a ClipTap button inside the YouTube player controls
- Selects a video section using Start and End buttons
- Shows draggable start and end handles directly on the YouTube progress bar
- Uses a blue handle for the start point and an orange handle for the end point
- Moves the video playhead while dragging a handle so you can preview the exact position
- Supports precise time input with decimals, such as `01:23.45` or `83.45`
- Repeats the selected range with the loop toggle
- Downloads the selected section using `yt-dlp --download-sections`
- Downloads the full video with the Full Download button
- Keeps the downloader logic local on your computer

## How it works

Browser extensions cannot directly run local programs such as `yt-dlp.exe`, `python.exe`, or `ffmpeg.exe`. ClipTap therefore uses a small local helper server.

```text
YouTube page
  -> ClipTap browser extension
  -> http://127.0.0.1:17723
  -> ClipTap local helper
  -> yt-dlp / ffmpeg
  -> downloaded video file
```

The helper must stay open while using the download feature. If the helper window is closed, the extension can still appear in YouTube, but downloads will fail.

## Project structure

```text
cliptap/
  extension/
    manifest.json
    popup.html
    popup.css
    popup.js
    content.js
    icons/
      cliptap.png
  helper/
    server.py
    start-helper.bat
    start-helper.ps1
    bin/
      .gitkeep
  scripts/
    package.sh
  docs/
    images/
      cliptap-player-button.png
      cliptap-panel.png
      cliptap-timeline-handles.png
      cliptap-loop-enabled.png
      cliptap-helper-terminal.png
      firefox-temporary-addon.png
      chrome-load-unpacked.png
  README.md
  CHANGELOG.md
  LICENSE
```

## Requirements

ClipTap currently targets Windows first.

You need:

- Python 3
- `yt-dlp`
- FFmpeg
- A Chromium-based browser or Firefox

### Install yt-dlp

Install or update `yt-dlp` with Python:

```powershell
py -m pip install -U yt-dlp
```

Check that it works:

```powershell
py -m yt_dlp --version
```

If the `yt-dlp` command is available globally, this should also work:

```powershell
yt-dlp --version
```

ClipTap can fall back to `py -m yt_dlp` when the global `yt-dlp` command is not found.

### Install FFmpeg

Recommended Windows installation:

```powershell
winget install -e --id Gyan.FFmpeg
```

After installation, open a new terminal and check:

```powershell
ffmpeg -version
```

Alternatively, place `ffmpeg.exe` here:

```text
cliptap/helper/bin/ffmpeg.exe
```

Do not rely on this command for FFmpeg:

```powershell
pip install ffmpeg
```

That installs a Python package. It does not install the real `ffmpeg.exe` program required by `yt-dlp`.

## Installation

### 1. Start the local helper

Open the project folder and run:

```text
cliptap/helper/start-helper.bat
```

Or use PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\helper\start-helper.ps1
```

A terminal window should appear. Keep it open while using ClipTap.

You should see something similar to this:

```text
ClipTap helper starting...
Checking commands:
  yt-dlp: FOUND
  ffmpeg: FOUND
ClipTap helper running at http://127.0.0.1:17723
```

If it says `yt-dlp: NOT FOUND` or `ffmpeg: NOT FOUND`, check the troubleshooting section below.

### 2. Install the browser extension

#### Chrome / Edge / Brave

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click Load unpacked.
4. Select the extension folder:

```text
cliptap/extension
```

![Chrome Load unpacked screen](docs/images/chrome-load-unpacked.png)

[SCREENSHOT: Chrome or Edge extensions page with Developer mode enabled and the Load unpacked button visible.]

#### Firefox temporary installation

1. Open `about:debugging#/runtime/this-firefox`.
2. Click Load Temporary Add-on.
3. Select the packaged `.xpi` file, or select a file from the extension folder such as `manifest.json`.

![Firefox temporary add-on screen](docs/images/firefox-temporary-addon.png)

[SCREENSHOT: Firefox about:debugging page showing the Load Temporary Add-on button and ClipTap loaded.]

Unsigned Firefox add-ons loaded this way are temporary. They may disappear after restarting Firefox.

## Usage

### Open ClipTap in YouTube

1. Start the ClipTap helper.
2. Open a YouTube video.
3. Look at the bottom-right controls inside the YouTube player.
4. Click the ClipTap icon.

The ClipTap panel opens above the player utility controls.

### Select a section

1. Move the YouTube playhead to the desired start point.
2. Click Start.
3. Move the YouTube playhead to the desired end point.
4. Click End.

The selected range appears on the YouTube progress bar.

The start point is shown as a blue circular handle.  
The end point is shown as an orange circular handle.

### Adjust the section with timeline handles

You can drag the blue or orange handle directly on the YouTube progress bar.

While dragging a handle, ClipTap also moves the YouTube playhead to that position. This makes it easier to preview the exact frame or moment you are selecting.

The clickable area around each handle is intentionally larger than the visible circle, so the handles are easier to grab.

### Enter precise times manually

The Start and End input fields support multiple formats.

Examples:

```text
83
83.5
1:23
1:23.45
00:01:23
00:01:23.45
```

When you edit a time field, ClipTap updates the selected range and moves the video playhead to that point.

### Loop the selected range

Click the loop toggle in the ClipTap panel.

When loop mode is enabled:

- playback jumps to the selected start point
- the video plays until the selected end point
- the playhead automatically jumps back to the start point
- the selected section repeats until loop mode is turned off

Loop mode is useful for checking whether the selected range is correct before downloading.

### Download the selected section

After setting Start and End, click Section Download.

ClipTap sends the video URL and selected time range to the local helper. The helper then runs `yt-dlp` with a section download command.

### Download the full video

Click Full Download to download the entire video without using the selected start and end points.

### Output folder

By default, downloads are saved to the output folder configured by the helper. In the current Windows helper, this is typically:

```text
C:\Users\<YourName>\Downloads\ClipTap
```

Check the helper terminal when it starts. It prints the active output path.

## Troubleshooting

### The extension says the helper is off, but the helper window is open

Check the helper terminal. If you see this:

```text
yt-dlp: NOT FOUND
ffmpeg: NOT FOUND
```

then the helper is running, but the required download tools are missing or not detected.

Install or fix `yt-dlp` and FFmpeg, then restart the helper.

### `yt-dlp: NOT FOUND`

Try:

```powershell
py -m pip install -U yt-dlp
py -m yt_dlp --version
```

If `py -m yt_dlp --version` works, ClipTap should be able to use the Python module fallback.

If you want the global `yt-dlp` command to work too, make sure Python's Scripts folder is in your Windows PATH.

### `ffmpeg: NOT FOUND`

Install FFmpeg:

```powershell
winget install -e --id Gyan.FFmpeg
```

Then open a new terminal and check:

```powershell
ffmpeg -version
```

Or place `ffmpeg.exe` here:

```text
cliptap/helper/bin/ffmpeg.exe
```

### `pip install ffmpeg` did not fix FFmpeg

That is expected. `pip install ffmpeg` is not the real FFmpeg executable.

You need `ffmpeg.exe`, either from a Windows FFmpeg build or from a package manager such as winget.

### Downloads return HTTP 500 in the helper terminal

A `500` response means the helper received the request but failed while processing it.

Common causes:

- `yt-dlp` is missing
- FFmpeg is missing
- the selected range is invalid
- the video URL is not available to `yt-dlp`
- YouTube requires cookies or login for that video
- the output folder is not writable

Check the full error text printed in the helper terminal.

### The ClipTap button does not appear in YouTube

Try:

1. Refresh the YouTube page.
2. Open another video and come back.
3. Disable and re-enable the extension.
4. Check that the extension is allowed to run on `youtube.com`.

YouTube changes its page structure often, so the button may need a page refresh after navigation.

### The selected handles feel hard to grab

The visible handles are small so they match the YouTube player style, but the actual drag area is larger. Try clicking slightly around the handle, not only on the exact colored circle.

## Development

### Load the extension during development

Use the unpacked extension folder:

```text
cliptap/extension
```

After changing extension files, reload the extension from your browser's extension management page.

### Run the helper during development

```powershell
cd cliptap
.\helper\start-helper.bat
```

The helper runs locally at:

```text
http://127.0.0.1:17723
```

### Health check

Open this URL while the helper is running:

```text
http://127.0.0.1:17723/health
```

You should receive a basic success response.

### Packaging

If you use the included packaging script, run it from the project root:

```bash
bash scripts/package.sh
```

Generated package names may vary depending on the version.

## Replacing the icon

Replace this file with your own PNG:

```text
cliptap/extension/icons/cliptap.png
```

For the Chrome install zip after extraction, replace:

```text
cliptap/icons/cliptap.png
```

Reload the extension after replacing the icon.

## Notes

- ClipTap does not bypass DRM.
- ClipTap does not remove YouTube restrictions.
- Some videos may require cookies or login to be downloadable by `yt-dlp`.
- Section downloads may not be frame-perfect unless re-encoding is used.
- Keeping the helper terminal open is required for downloads in the current helper-server version.

## License

See `LICENSE`.
