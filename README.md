# ClipTap v1.0

유튜브를 보다가 현재 재생 시간을 시작/끝으로 찍고, 로컬에 설치된 `yt-dlp`로 해당 구간만 다운로드하는 Chromium 계열 브라우저용 확장 + 로컬 헬퍼입니다.

> 개인적으로 보관 권한이 있는 영상, 본인 영상, 저작권자 허락을 받은 영상에 사용하세요. YouTube 및 각 사이트 약관은 별도로 확인해야 합니다.

## 구성

- `extension/` : Chrome, Edge, Brave 등에 "압축해제된 확장 프로그램"으로 로드하는 폴더
- `helper/` : 확장에서 보낸 요청을 받아 `yt-dlp` 명령을 실행하는 로컬 Python 서버

## 준비물

Windows 기준:

- Python 3
- yt-dlp
- ffmpeg

이미 `yt-dlp`, `ffmpeg`를 쓰고 있다면 대부분 준비 끝입니다.

확인:

```powershell
yt-dlp --version
ffmpeg -version
python --version
```

## 설치 / 실행

### 1. 로컬 헬퍼 실행

`helper/start-helper.bat`을 더블클릭하세요.

검은 창이 열리고 다음 비슷한 문구가 보이면 정상입니다.

```text
ClipTap helper running at http://127.0.0.1:17723
```

창을 닫으면 다운로드 기능도 멈춥니다.

### 2. 확장 로드

Chrome 또는 Edge에서:

1. 주소창에 `chrome://extensions` 입력  
   Edge는 `edge://extensions`
2. 개발자 모드 켜기
3. `압축해제된 확장 프로그램 로드` 클릭
4. 이 프로젝트의 `extension/` 폴더 선택

### 3. 사용법

1. YouTube 영상 페이지 열기
2. 오른쪽 아래 `ClipTap` 작은 패널에서
   - `시작 찍기`
   - 원하는 지점으로 이동
   - `끝 찍기`
   - `받기`
3. 파일은 기본적으로 `다운로드/ClipTap` 폴더에 저장됩니다.

확장 아이콘을 눌러 팝업에서도 같은 기능을 쓸 수 있습니다.

## 옵션

팝업에서 다음을 고를 수 있습니다.

- 화질: 최고 / 1080p 이하 / 720p 이하 / 오디오 MP3
- 브라우저 쿠키: 없음 / Edge / Chrome / Firefox
- 정확 컷: 켜면 `--force-keyframes-at-cuts`를 사용합니다. 더 정확하지만 느립니다.

## 문제 해결

### 헬퍼 연결 실패

`helper/start-helper.bat`이 켜져 있는지 확인하세요.

### yt-dlp를 찾을 수 없음

PowerShell에서 `yt-dlp --version`이 안 되면 yt-dlp가 PATH에 안 잡힌 겁니다. 먼저 yt-dlp를 설치하거나 PATH에 추가하세요.

### ffmpeg 오류

구간 다운로드와 병합에는 ffmpeg가 필요합니다. `ffmpeg -version`이 되는지 확인하세요.

### YouTube 로그인/멤버십/비공개 영상

팝업에서 `브라우저 쿠키`를 Edge/Chrome/Firefox 중 실제 로그인된 브라우저로 골라보세요.

## Git commit name

```bash
git commit -m "Add ClipTap section downloader extension"
```
