# ClipTap v1.1

YouTube 플레이어 안에서 시작/끝 지점을 찍고, 로컬에 설치된 `yt-dlp`로 해당 구간만 다운로드하는 브라우저 확장 + 로컬 헬퍼입니다.

> 개인적으로 보관 권한이 있는 영상, 본인 영상, 저작권자 허락을 받은 영상에 사용하세요. YouTube 및 각 사이트 약관은 별도로 확인해야 합니다.

## v1.1 변경점

- 페이지 오른쪽 아래 고정 패널 제거
- YouTube 플레이어 오른쪽 아래 컨트롤 영역에 ClipTap 버튼 추가
- 시작/끝 지점을 YouTube 진행바 위에 직접 표시
- 진행바의 시작/끝 손잡이를 드래그해서 구간 수정 가능
- 손잡이를 옮기면 재생 헤드도 같이 이동해서 해당 위치를 바로 확인 가능

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

1. `cliptap-v1.1-chrome.zip` 압축 풀기
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
4. `cliptap-v1.1.xpi` 선택

## 사용법

1. YouTube 영상 페이지 열기
2. 플레이어 오른쪽 아래 컨트롤 영역의 ClipTap 버튼 클릭
3. `시작 찍기`
4. 원하는 지점으로 이동
5. `끝 찍기`
6. 필요하면 진행바 위의 시작/끝 손잡이를 드래그해서 미세 조정
7. `받기`

파일은 기본적으로 `다운로드/ClipTap` 폴더에 저장됩니다.

확장 아이콘 팝업에서는 화질, 쿠키, 정확 컷 옵션을 바꿀 수 있습니다.

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
git commit -m "Move ClipTap controls into YouTube player"
```
