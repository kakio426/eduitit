# Eduitit Teacher Launcher (Electron)

## Purpose
`eduitit-launcher://` 프로토콜을 받아서 수업 화면을 자동으로 좌/우 분할합니다.

- Left window: YouTube playback (non-embeddable videos supported)
- Right window: Eduitit artclass dashboard (`display=dashboard`)

## Run (development)
```bash
cd desktop/teacher-launcher
npm install
npm start
```

브라우저에서 `런처로 수업 시작` 버튼을 누르면 런처가 payload를 받아 분할 창을 엽니다.

## Build (Windows installer)
```bash
cd desktop/teacher-launcher
npm install
npm run dist:win
```

빌드 산출물은 `desktop/teacher-launcher/dist`에 생성됩니다.

## Protocol payload contract
런처는 URL query `payload`를 base64url JSON으로 받습니다.

```json
{
  "version": 1,
  "classId": 123,
  "title": "수업 제목",
  "youtubeUrl": "https://www.youtube.com/watch?...",
  "dashboardUrl": "https://.../artclass/classroom/123/?display=dashboard&runtime=launcher",
  "issuedAt": 1700000000,
  "expiresAt": 1700000120
}
```

## Notes
- 웹 브라우저 팝업 제약을 우회하기 위해 창 배치는 런처가 담당합니다.
- 런처 미설치 상태에서는 브라우저에서 프로토콜 실행이 실패하므로 설치가 필요합니다.
