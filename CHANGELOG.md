# Changelog

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

- YouTube 페이지 접속 시 멈춤을 유발할 수 있던 전역 MutationObserver 렌더 루프를 제거했습니다.
- 렌더링을 스로틀링하고 YouTube 내비게이션 이벤트 중심으로 재탐색하도록 변경했습니다.


## v1.1.0

- Move ClipTap from a fixed page panel into YouTube's player controls.
- Add draggable start/end handles directly on the YouTube progress bar.
- Seek the video while dragging a start/end handle.

## v1.0.0

- Add popup controls for section downloading with yt-dlp.
- Add local Python helper server.
- Add simple in-page control panel.
