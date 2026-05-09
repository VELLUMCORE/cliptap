# ClipTap

ClipTap is a browser extension for downloading either a selected section or the full version of a YouTube video using `yt-dlp`.

It adds a small control directly inside the YouTube player, so the start point, end point, loop toggle, and download actions stay close to the video.

![ClipTap button integrated into the YouTube player controls](docs/images/cliptap-player-button.png)


## Features

- Mark a start point and end point from the current playback position
- Drag blue/orange timeline handles directly on the YouTube progress bar
- Type exact timestamps, including decimal seconds
- Loop the selected range while checking the clip
- Download only the selected range
- Download the full video
- Use a standalone Windows helper app instead of a terminal window
- Check and install `yt-dlp` / FFmpeg from the helper app
- View incoming download requests with title, thumbnail, status, progress, and cancel controls
- Show live-stream downloads as an active recording instead of a fixed percentage

![ClipTap panel inside the YouTube player](docs/images/cliptap-panel.png)


## How it works

ClipTap has two parts:

1. **Browser extension**  
   Adds ClipTap controls to YouTube and sends download requests.

2. **ClipTap Helper**  
   A local Windows app that receives requests from the extension and runs `yt-dlp` / FFmpeg.

The browser extension cannot directly run local programs, so the helper app must be open while downloading.

```text
YouTube player
→ ClipTap extension
→ ClipTap Helper at http://127.0.0.1:17723
→ yt-dlp / FFmpeg
→ downloaded file
```

## Requirements

- Windows
- Firefox, Chrome, Edge, or another Chromium-based browser
- Python, only if you are running from source or building the helper app yourself
- `yt-dlp`
- FFmpeg

The helper app can check whether `yt-dlp` and FFmpeg are available. If they are missing, it shows install buttons.

![ClipTap Helper dependency status](docs/images/cliptap-helper-dependencies.png)


## Install ClipTap Helper

Download and run:

```text
ClipTapHelper.exe
```

Keep the helper app open while using ClipTap. The browser extension sends download requests to the helper at:

```text
http://127.0.0.1:17723
```

If `yt-dlp` is missing, click:

```text
Install / Update yt-dlp
```

If FFmpeg is missing, click:

```text
Install FFmpeg with winget
```

After installing FFmpeg, restart ClipTap Helper if it still appears as missing.

![ClipTap Helper download request](docs/images/cliptap-helper-download.png)


## Install the browser extension

### Firefox

Open:

```text
about:debugging#/runtime/this-firefox
```

Choose:

```text
Load Temporary Add-on
```

Then select the `.xpi` file.

![Firefox temporary add-on installation page](docs/images/firefox-temporary-addon.png)


### Chrome / Edge

Open:

```text
chrome://extensions
```

or:

```text
edge://extensions
```

Then:

1. Enable **Developer mode**
2. Click **Load unpacked**
3. Select the `cliptap` extension folder

![Chrome load unpacked extension screen](docs/images/chrome-load-unpacked.png)


## Using ClipTap

### Open ClipTap

Open a YouTube video and click the ClipTap icon inside the player controls.

### Set the start point

Move the YouTube playback position to the place where the clip should begin, then click:

```text
Set Start
```

### Set the end point

Move the playback position to the place where the clip should end, then click:

```text
Set End
```

![Start and end handles on the YouTube timeline](docs/images/cliptap-timeline-handles.png)


### Fine-tune the range

Drag the start and end handles directly on the YouTube progress bar.

When a handle is moved, the video playback position also moves to that timestamp, so the selected point can be checked immediately.

You can also type timestamps manually.

Supported timestamp examples:

```text
83
83.5
01:23
01:23.5
00:01:23.5
```

### Loop the selected range

Turn on the loop button to repeatedly play the selected start-to-end range.

![Loop enabled in ClipTap](docs/images/cliptap-loop-enabled.png)


### Download the selected range

Click:

```text
Download Section
```

The helper app will show the request, video title, thumbnail, and progress.

### Download the full video

Click:

```text
Download Full
```

For normal videos, the helper shows a percentage progress bar.

For live streams, the helper shows an active recording state because there is no fixed final size while the stream is still running.

![ClipTap live recording state](docs/images/cliptap-helper-live-recording.png)


## Build ClipTapHelper.exe from source

From PowerShell:

```powershell
cd cliptap\helper
.\build-helper-exe.ps1
```

The build script creates:

```text
cliptap/dist/ClipTapHelper.exe
```

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
    ClipTapHelper.pyw
    build-helper-exe.ps1
    requirements.txt
    bin/
      ffmpeg.exe

  scripts/
    package.sh

  README.md
  CHANGELOG.md
  LICENSE
```

## Troubleshooting

### The extension says the helper is off or an error occurred

Open ClipTap Helper and check that the server status says:

```text
Server: running at http://127.0.0.1:17723
```

You can also open this URL in your browser:

```text
http://127.0.0.1:17723/health
```

### yt-dlp is missing

Click **Install / Update yt-dlp** in ClipTap Helper.

Or install it manually:

```powershell
py -m pip install -U yt-dlp
```

### FFmpeg is missing

Click **Install FFmpeg** in ClipTap Helper.

Or install it manually:

```powershell
winget install -e --id Gyan.FFmpeg
```

If FFmpeg still is not detected, place `ffmpeg.exe` here:

```text
cliptap/helper/bin/ffmpeg.exe
```

### A download is wrong or no progress appears

Some streams do not report progress in a normal percentage format. Live streams are shown as active recordings and can be cancelled from the helper window.

## Notes

ClipTap uses `yt-dlp` for downloading and FFmpeg for media processing. Use ClipTap only with videos that you have the right to download or archive.

## License

This project is licensed under the terms included in `LICENSE`.
