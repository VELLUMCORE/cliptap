# ClipTap

ClipTap is a browser extension for downloading either a selected section or the full version of a YouTube video using `yt-dlp`.

It adds controls directly inside the YouTube player and uses a local Web UI manager for dependency checks, download progress, cancellation, and live-stream recording status.

![ClipTap button integrated into the YouTube player controls](docs/images/cliptap-player-button.png)

## Features

- Mark a start point and end point from the current playback position
- Drag blue/orange timeline handles directly on the YouTube progress bar
- Type exact timestamps, including decimal seconds
- Loop the selected range while checking the clip
- Download only the selected range
- Download the full video
- Manage downloads from a dark local Web UI dashboard
- Check and install FFmpeg from the manager
- Use bundled `yt-dlp` when the helper is built as a standalone executable
- View incoming download requests with title, thumbnail, status, progress, and cancel controls
- Show live-stream downloads as an active recording instead of a fixed percentage

![ClipTap panel inside the YouTube player](docs/images/cliptap-panel.png)

## Recommended setup

For normal use, use these two pieces together:

1. `ClipTapHelper.exe`  
   Starts the local manager and opens the Web UI automatically.

2. Browser extension  
   Installs ClipTap into Firefox, Chrome, or Edge.

The helper executable is intentionally separate from the browser extension. Browser extensions cannot directly run local programs such as `yt-dlp` or FFmpeg, so ClipTap needs a local helper running on your computer.

```text
YouTube player
→ ClipTap extension
→ ClipTap Manager at http://127.0.0.1:17723
→ yt-dlp / FFmpeg
→ downloaded file
```

## ClipTap Manager

Run:

```text
ClipTapHelper.exe
```

The manager opens in your default browser:

```text
http://127.0.0.1:17723
```

Keep the manager running while using ClipTap. Use **Stop manager** in the Web UI when you want to shut it down.

![ClipTap Manager dependency status](docs/images/cliptap-manager-status.png)

## Dependencies

### yt-dlp

When `ClipTapHelper.exe` is built with the included build script, `yt-dlp` is bundled into the helper. Users do not need to install `yt-dlp` separately for the normal standalone build.

If you run ClipTap from source, install `yt-dlp` manually:

```powershell
py -m pip install -U yt-dlp
```

### FFmpeg

FFmpeg is still required for merging video/audio and cutting sections.

If FFmpeg is missing, open ClipTap Manager and click:

```text
Install FFmpeg with winget
```

You can also install it manually:

```powershell
winget install -e --id Gyan.FFmpeg
```

If FFmpeg is not available globally, place `ffmpeg.exe` next to `ClipTapHelper.exe` or in a `bin` folder beside it:

```text
bin/ffmpeg.exe
```

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

The blue start handle appears on the YouTube progress bar.

### Set the end point

Move the playback position to the place where the clip should end, then click:

```text
Set End
```

The orange end handle appears on the YouTube progress bar.

![Start and end handles on the YouTube timeline](docs/images/cliptap-timeline-handles.png)

### Fine-tune the range

The start and end handles can be dragged directly on the YouTube progress bar.

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

This is useful when checking whether the clip starts and ends at the right moment.

![Loop enabled in ClipTap](docs/images/cliptap-loop-enabled.png)

### Download the selected range

Click:

```text
Download Section
```

ClipTap sends the selected start and end timestamps to the manager. The request appears in the Web UI with progress and a cancel button.

![ClipTap Manager showing a download request](docs/images/cliptap-manager-job.png)

### Download the full video

Click:

```text
Download Full Video
```

This downloads the full video without applying the selected start and end range.

For live streams, full download mode records until the stream ends or until the request is cancelled. The manager shows this as an active recording instead of a normal percentage progress bar.

## Build the standalone helper

The helper source is a single file:

```text
helper/ClipTapHelper.py
```

To build the one-file Windows helper executable:

```powershell
cd helper
.\build-standalone.ps1
```

The output is:

```text
dist/ClipTapHelper.exe
```

The repository also includes a GitHub Actions workflow:

```text
.github/workflows/build-helper.yml
```

Run the workflow from GitHub to build `ClipTapHelper.exe` on `windows-latest` and download it as an artifact.

## Run from source

For development, run:

```text
helper/start-helper.bat
```

This starts the same manager using Python and opens:

```text
http://127.0.0.1:17723
```

## Troubleshooting

### “Helper is off or an error occurred”

Open the manager:

```text
http://127.0.0.1:17723
```

If the page does not open, run `ClipTapHelper.exe` again.

### The manager says FFmpeg is missing

Use the manager install button, or run:

```powershell
winget install -e --id Gyan.FFmpeg
```

If FFmpeg is not available globally, place `ffmpeg.exe` here beside the helper executable:

```text
bin/ffmpeg.exe
```

### Download requests appear but fail

Check the failed request in ClipTap Manager. Common causes are:

1. FFmpeg is missing
2. `yt-dlp` is outdated
3. The video requires browser cookies
4. The video URL is unavailable
5. YouTube changed its response format and `yt-dlp` needs an update

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
    ClipTapHelper.py
    build-standalone.ps1
    start-helper.bat
    start-helper.ps1
    assets/
      ClipTapHelper.png
      ClipTapHelper.ico
    bin/
      .gitkeep

  .github/
    workflows/
      build-helper.yml

  scripts/
    package.sh

  README.md
  CHANGELOG.md
  LICENSE
```

## Notes

ClipTap uses `yt-dlp` for downloading and FFmpeg for media processing. Use ClipTap only with videos that you have the right to download or archive.

## License

This project is licensed under the terms included in `LICENSE`.
