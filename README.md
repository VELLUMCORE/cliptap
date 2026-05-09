# ClipTap v1.1.4

YouTube 플레이어 안에서 시작/끝 지점을 찍고, 로컬에 설치된 `yt-dlp`로 해당 구간 또는 전체 영상을 다운로드하는 브라우저 확장 + 로컬 헬퍼입니다.

> 개인적으로 보관 권한이 있는 영상, 본인 영상, 저작권자 허락을 받은 영상에 사용하세요. YouTube 및 각 사이트 약관은 별도로 확인해야 합니다.

## v1.1.4 변경점

- 시작/끝 지점을 YouTube 재생 헤드처럼 동그란 핸들로 변경
- 시작 지점은 파란색, 끝 지점은 주황색으로 표시
- 핸들의 실제 클릭/드래그 판정을 시각 크기보다 크게 확장
- ClipTap 플레이어 패널을 컨트롤 유틸리티 영역 바로 위쪽으로 조금 내림
- 플레이어 패널의 시작/끝 입력칸에서 `00:14:09.35`처럼 소수점 시간 입력 지원

## 로고 바꾸기

직접 만든 PNG 로고를 아래 경로에 같은 파일명으로 넣으면 됩니다.

```text
cliptap/extension/icons/cliptap.png
```

Chrome 설치용 zip을 풀어서 쓰는 경우에는 압축을 푼 폴더 기준으로 아래 파일을 교체하세요.

```text
cliptap/icons/cliptap.png
```

교체 후에는 확장 프로그램을 새로고침하거나 다시 로드해야 반영됩니다.

## 구성

- `extension/` : Chrome, Edge, Brave, Firefox 등에 로드하는 확장 폴더
- `helper/` : 확장에서 보낸 요청을 받아 `yt-dlp` 명령을 실행하는 로컬 Python 서버
- `scripts/` : 패키징용 스크립트

## 준비물

Windows 기준:

- Python 3
- yt-dlp
- ffmpeg

확인:

```powershell
yt-dlp --version
ffmpeg -version
python --version
```

## 설치 / 실행

### 1. 로컬 헬퍼 실행

`helper/start-helper.bat`을 더블클릭하세요.

다음 비슷한 문구가 보이면 정상입니다.

```text
ClipTap helper running at http://127.0.0.1:17723
```

창을 닫으면 다운로드 기능도 멈춥니다.

### 2. Chrome / Edge 설치

1. `cliptap-v1.1.4-chrome.zip` 압축 풀기
2. 주소창에 `chrome://extensions` 입력  
   Edge는 `edge://extensions`
3. 개발자 모드 켜기
4. `압축해제된 확장 프로그램 로드` 클릭
5. 압축을 푼 `cliptap/` 폴더 선택

소스코드 압축본을 쓰는 경우에는 `extension/` 폴더를 선택하세요.

### 3. Firefox 설치

Firefox 일반판에서 unsigned XPI 설치가 막히면:

1. `about:debugging` 접속
2. `이 Firefox` 클릭
3. `임시 부가 기능 로드` 클릭
4. `cliptap-v1.1.4.xpi` 선택

## 사용법

### 구간 다운로드

1. YouTube 영상 페이지 열기
2. 플레이어 오른쪽 아래 컨트롤 영역의 ClipTap 버튼 클릭
3. `시작 찍기`
4. 원하는 지점으로 이동
5. `끝 찍기`
6. 필요하면 진행바 위의 파란 시작점/주황 끝점 핸들을 드래그하거나 시간 입력칸에 소수점 단위로 직접 입력
7. `구간 받기`

### 전체 다운로드

1. YouTube 영상 페이지 열기
2. 플레이어 오른쪽 아래 컨트롤 영역의 ClipTap 버튼 클릭
3. `전체 다운로드` 클릭

파일은 기본적으로 `다운로드/ClipTap` 폴더에 저장됩니다.

확장 아이콘 팝업에서는 화질, 쿠키, 정확 컷 옵션을 바꿀 수 있습니다.

## 옵션

팝업에서 다음을 고를 수 있습니다.

- 화질: 최고 / 1080p 이하 / 720p 이하 / 오디오 MP3
- 브라우저 쿠키: 없음 / Edge / Chrome / Firefox
- 정확 컷: 켜면 구간 다운로드 때 `--force-keyframes-at-cuts`를 사용합니다. 더 정확하지만 느립니다.

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

```txt
fix: refine player handles and time inputs
```
