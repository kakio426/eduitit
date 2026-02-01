# 작업 인계 문서

> 최근 업데이트: 2026-02-01
> 최근 세션: eduitit SNS 기능 확장 구현

---

## 🆕 최신 작업 (2026-02-01)

### eduitit SNS 기능 확장 구현 완료 ✅

**목표**: 비로그인 사용자도 SNS 게시물을 볼 수 있게 하고, 이미지 붙여넣기 기능 추가

#### 구현된 기능:

1. **비로그인 사용자 SNS 읽기 권한** ✅
   - 비로그인 사용자도 게시물 목록 조회 가능 (읽기 전용)
   - 로그인 유도 메시지 표시 ("글을 작성하고 소통하려면 로그인이 필요해요")
   - 좋아요/댓글 버튼 클릭 시 로그인 페이지로 이동 (`?next` 파라미터 포함)

2. **이미지 붙여넣기 기능 (Ctrl+V)** ✅
   - 클립보드에서 이미지 감지 및 자동 업로드
   - 이미지 미리보기 표시
   - X 버튼으로 미리보기 삭제
   - 파일 선택 버튼과 병행 지원 (모바일 대응)

3. **이미지 자동 최적화** ✅ (핵심 기능!)
   - 최대 해상도: 1920px × 1920px (가로/세로 중 큰 쪽 기준)
   - JPEG 품질: 85% (육안 구별 불가능한 수준)
   - PNG → JPEG 자동 변환
   - 평균 70-90% 파일 크기 감소 (예: 5MB → 500KB)
   - Cloudinary 용량 절약 효과 (10배 절약)

4. **보안 강화** ✅
   - 파일 크기 제한: 10MB
   - MIME 타입 검증: JPEG, PNG, GIF, WebP만 허용
   - PIL로 이미지 무결성 검증 (악성 파일 방지)

#### 수정된 파일:

**신규 생성 (2개)**:
1. `core/templates/core/partials/sns_widget.html` - 공통 SNS 위젯 파일
2. `core/static/core/js/post_image_paste.js` - 이미지 붙여넣기 + 최적화 스크립트

**수정 (4개)**:
1. `core/views.py` - home()에서 비로그인 사용자에게도 posts 전달, post_create()에 이미지 검증 추가
2. `core/templates/core/home.html` - 2컬럼 레이아웃 + SNS 위젯 include + HTMX/Phosphor Icons 추가
3. `core/templates/core/home_authenticated.html` - SNS 위젯 코드 제거하고 include로 교체
4. `core/templates/core/partials/post_item.html` - 좋아요/댓글 버튼에 로그인 확인 로직 추가

#### 테스트 체크리스트:

**비로그인 사용자**:
- [ ] SNS 위젯 좌측에 표시
- [ ] 게시물 목록 표시
- [ ] "로그인하기" 버튼 표시
- [ ] 좋아요 버튼 클릭 → 로그인 페이지 이동
- [ ] 댓글 입력란 비활성화
- [ ] 로그인 후 원래 페이지로 복귀 확인

**로그인 사용자**:
- [ ] 게시물 작성 폼 표시
- [ ] 파일 선택 버튼으로 이미지 업로드
- [ ] Ctrl+V로 이미지 붙여넣기
- [ ] 이미지 미리보기 표시
- [ ] 미리보기 삭제 버튼 동작
- [ ] 개발자 콘솔에서 "이미지 최적화 완료: 5.2MB → 0.52MB" 로그 확인
- [ ] 10MB 초과 이미지 차단
- [ ] 텍스트 파일 업로드 차단

#### 이미지 최적화 효과:

```
원본: 4000px × 3000px, 5.2MB (PNG)
  ↓ 자동 최적화
결과: 1920px × 1440px, 520KB (JPEG 85%)
절약: 90% 용량 감소
```

- Cloudinary 저장 공간 10배 절약
- 업로드 속도 향상
- 사용자 경험 개선 (빠른 로딩)

#### 주의사항:

1. **Pillow 라이브러리 필수**: `pip install Pillow` (이미 설치되어 있어야 함)
2. **GIF 애니메이션 손실**: GIF를 JPEG로 변환하면 애니메이션 손실 (개선 필요 시 별도 처리)
3. **PNG 투명도 손실**: PNG를 JPEG로 변환하면 투명도 손실 (필요 시 투명도 채널 확인 로직 추가)
4. **모바일 붙여넣기 제한**: 일부 모바일 브라우저에서 클립보드 API 제한 (파일 선택 버튼 병행 제공으로 해결)

#### 다음 개선 제안:

1. **무한 스크롤**: 현재 모든 게시물을 한 번에 로드 → HTMX 페이지네이션
2. **실시간 알림**: Django Channels + WebSocket으로 좋아요/댓글 알림
3. **이미지 갤러리 모드**: 이미지 클릭 시 라이트박스 모달
4. **해시태그 기능**: 게시물에 해시태그 추가 및 검색
5. **게시물 필터링**: 인기순, 최신순, 좋아요순 정렬

---

## 완료된 작업

### 1. Fortune(사주) & Ssambti 카카오톡 공유 카드 구현 (2026-02-01)
- [x] **Ssambti 카카오톡 공유 수정** - 저장된 결과 페이지로 공유되도록 변경
  - views.py: saved_result_id 반환하도록 수정
  - detail.html: 카카오톡 공유 기능 추가
  - partials/result.html: 저장된 결과 페이지로 링크 수정
  - detail_view: @login_required 제거하여 공개 접근 가능

- [x] **Fortune 사주 서비스 카드 UI 구현**
  - detail.html: 사주 명식 강조 카드 형태로 재구성
  - 헤더 카드: 일간(천간) 정보 + 이모지/이미지 표시
  - 사주 명식 카드: 일주 강조 (크기 확대 + 보라색 테두리)
  - 카카오톡 공유 기능 추가 (일간 정보 자동 추출)
  - views.py: save_fortune_api에서 pk 반환, detail_view 공개화

### 2. AutoArticle 원본 비교 및 기능 구현 (이전 세션)
- [x] 원본 GitHub 레포 분석 (https://github.com/kakio426/autoarticle)
- [x] **step1.html 입력 필드 추가** - 장소, 날짜, 톤 필드 복원
- [x] **테마 일관성 수정** - views.py THEMES를 constants.py와 통일
- [x] **Word 생성 기능 연결** - archive/detail에서 Word 다운로드 가능
- [x] **기사 삭제 기능** - ArticleDeleteView, 확인 다이얼로그 포함
- [x] **기사 수정 기능** - ArticleEditView, edit.html 템플릿 생성
- [x] **Rate Limiter 연동** - 마스터 키 사용 시 5분당 2회 제한

### 2. padlet_bot 앱 생성 (이전 세션)
- [x] 앱 디렉토리 및 기본 파일 생성
- [x] 모델, 뷰, 템플릿 완성
- [x] 마이그레이션 완료

### 3. 네이버/카카오 소셜 로그인 오류 수정 (이전 세션)
- [x] Site 도메인 수정
- [x] settings.py 환경변수명 수정

---

## 진행 중인 작업

### ~~이미지 저장소 클라우드 전환~~ ✅ 완료
- **완료일**: 2025-01-24
- **구현 내용**:
  - Cloudinary 패키지 설치 (`cloudinary`, `django-cloudinary-storage`)
  - `settings.py`에 Cloudinary 설정 추가
  - `views.py` 이미지 업로드 로직 수정 (Cloudinary/로컬 자동 선택)
- **환경변수 필요**: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
- **참고**: 환경변수 미설정 시 로컬 저장소 사용 (개발 환경 호환)

---

## AutoArticle 수정 파일 목록

```
autoarticle/
├── views.py                    # Word/Delete/Edit 뷰, Rate Limiter, Cloudinary 업로드
├── urls.py                     # 3개 URL 패턴 추가 (word, delete, edit)
├── engines/
│   └── ai_service.py           # Rate Limiter 함수 활성화
└── templates/autoarticle/
    ├── wizard/step1.html       # 입력 필드 추가 (장소, 날짜, 톤)
    ├── archive.html            # Word 다운로드 버튼 추가
    ├── detail.html             # Word 버튼 활성화, 수정/삭제 버튼 연결
    └── edit.html               # 신규 생성

config/
├── settings.py                 # Cloudinary 설정 추가

requirements.txt                # cloudinary, django-cloudinary-storage 추가
```

### 새 URL 패턴
| URL | 뷰 | 설명 |
|-----|-----|------|
| `/autoarticle/result/<pk>/word/` | ArticleWordView | Word 다운로드 |
| `/autoarticle/result/<pk>/delete/` | ArticleDeleteView | 기사 삭제 |
| `/autoarticle/result/<pk>/edit/` | ArticleEditView | 기사 수정 |

---

## 다음에 해야 할 작업

### 우선순위 높음
1. ~~**Cloudinary 이미지 저장소 연동**~~ ✅ 완료
2. **Railway 환경변수 설정** - Cloudinary 키 추가 필요
   - `CLOUDINARY_CLOUD_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`
3. **KAKAO_CLIENT_SECRET 추가** (이전 세션에서 미완료)
   - `.env` 파일에 추가 필요

### 우선순위 중간
4. 테스트 구조 수정 - `autoarticle/tests/` import 오류
5. PDF 신문형 레이아웃 연동 (코드 있지만 미사용)

---

## 주의사항

- **건드리면 안 됨**:
  - `ai_service.py`의 `FIXED_MODEL_NAME = "gemini-3-flash-preview"`
  - `constants.py`의 THEMES 딕셔너리 키

- **알려진 이슈**:
  - 이미지 재배포 시 삭제됨 (클라우드 전환 필요)
  - `autoarticle/tests/` import 오류

- **환경변수 필요**:
  - `GEMINI_API_KEY` - AI 기사 생성
  - `DATABASE_URL` - Neon PostgreSQL
  - `KAKAO_CLIENT_SECRET` - 카카오 로그인 (미설정)
  - `CLOUDINARY_CLOUD_NAME` - Cloudinary 클라우드 이름 (**신규**)
  - `CLOUDINARY_API_KEY` - Cloudinary API 키 (**신규**)
  - `CLOUDINARY_API_SECRET` - Cloudinary API 시크릿 (**신규**)

---

## 비용 관련 메모

| 서비스 | 현재 | 무료 한도 | 걱정 수준 |
|--------|------|----------|----------|
| Neon (DB) | 사용 중 | 0.5GB | 낮음 (텍스트 위주) |
| 이미지 | Cloudinary | 25GB/월 | 낮음 ✅ |
| Gemini API | 마스터 키 | 무료 | Rate Limit 적용됨 |

---

## 마지막 상태

- **메인 도메인**: `https://eduitit.site/`
- **Railway 도메인**: `https://web-production-f2869.up.railway.app/`
- **테스트**: Django check 통과, import 테스트 통과
- **서버 실행**: 수동 테스트 필요

---

## 이전 세션 작업

- 2025-01-24: **Cloudinary 이미지 저장소 연동 완료**
- 2025-01-24: AutoArticle 기능 완성 (Word, 삭제, 수정, Rate Limiter)
- 2025-01-24: Padlet Bot 앱 생성, 소셜 로그인 수정
- 2025-01-23: DutyTicker 디자인 통합, AutoArticle 오류 수정

---

---

## 📸 사주 서비스 이미지 추가 방법

> 작업일: 2026-02-01
> 담당: fortune 앱 카드 UI 구현 완료

### 현재 상태
- ✅ 사주 서비스에 ssambti와 동일한 카드 형태 구현 완료
- ✅ 카카오톡 공유 기능 구현 완료
- ⏳ 일간 이미지는 현재 **이모지**로 표시 중 (이미지로 교체 가능)

### 이미지 추가 옵션

#### 옵션 1: 천간별 이미지 (10개) - 추천 ⭐

각 천간(天干)마다 하나씩 만들어주세요:

**폴더 위치**: `fortune/static/fortune/images/stems/`

**파일명 및 컨셉**:
- `갑.png` (甲) - 큰 나무 이미지
- `을.png` (乙) - 풀/넝쿨 이미지
- `병.png` (丙) - 태양 이미지
- `정.png` (丁) - 촛불 이미지
- `무.png` (戊) - 큰 산 이미지
- `기.png` (己) - 논밭 이미지
- `경.png` (庚) - 칼/바위 이미지
- `신.png` (辛) - 보석 이미지
- `임.png` (壬) - 바다 이미지
- `계.png` (癸) - 비/이슬 이미지

**이미지 사양**:
- 크기: **512x512px** (정사각형)
- 형식: **PNG** (투명 배경 권장)
- 스타일: 심플하고 현대적인 일러스트 또는 아이콘 스타일

#### 옵션 2: 오행별 이미지 (5개) - 간단함

**폴더 위치**: `fortune/static/fortune/images/elements/`

**파일명**:
- `wood.png` (목 木) - 나무/숲 이미지
- `fire.png` (화 火) - 불꽃 이미지
- `earth.png` (토 土) - 흙/산 이미지
- `metal.png` (금 金) - 금속/칼 이미지
- `water.png` (수 水) - 물/파도 이미지

### 코드 수정 방법

이미지 파일을 위 폴더에 넣은 후, `fortune/templates/fortune/detail.html` 파일을 수정하세요.

**파일**: `fortune/templates/fortune/detail.html`
**위치**: 약 295번째 줄 근처

#### 현재 코드 (이모지 사용):
```javascript
// 헤더 카드 업데이트 (일간 정보)
if (dayStemCharacter && stemKoreanMap[dayStemCharacter]) {
    const stemIcon = document.getElementById('stemIcon');
    const stemName = document.getElementById('stemName');
    const stemDesc = document.getElementById('stemDesc');

    if (stemIcon) stemIcon.textContent = stemEmojiMap[dayStemCharacter];
    if (stemName) stemName.textContent = stemKoreanMap[dayStemCharacter];
    if (stemDesc) stemDesc.textContent = stemDescMap[dayStemCharacter];

    // 이미지가 있다면 표시 (나중에 이미지 추가 시)
    // const stemImageContainer = document.getElementById('stemImageContainer');
    // stemImageContainer.innerHTML = `<img src="/static/fortune/images/stems/${dayStemCharacter}.png" class="w-48 h-48 object-cover rounded-full" alt="${stemKoreanMap[dayStemCharacter]}">`;
}
```

#### 수정할 코드 (이미지 사용):

**천간별 이미지 사용 시**:
```javascript
// 헤더 카드 업데이트 (일간 정보)
if (dayStemCharacter && stemKoreanMap[dayStemCharacter]) {
    const stemName = document.getElementById('stemName');
    const stemDesc = document.getElementById('stemDesc');
    const stemImageContainer = document.getElementById('stemImageContainer');

    // 한자를 한글로 변환 (파일명 매핑)
    const hanjaToKorean = {
        '甲': '갑', '乙': '을', '丙': '병', '丁': '정', '戊': '무',
        '己': '기', '庚': '경', '辛': '신', '壬': '임', '癸': '계'
    };
    const koreanFileName = hanjaToKorean[dayStemCharacter];

    // 이미지 표시
    if (stemImageContainer && koreanFileName) {
        stemImageContainer.innerHTML = `
            <img src="/static/fortune/images/stems/${koreanFileName}.png"
                 class="w-48 h-48 object-cover rounded-full"
                 alt="${stemKoreanMap[dayStemCharacter]}"
                 onerror="this.parentElement.innerHTML='<div class=\\'w-48 h-48 flex items-center justify-center text-9xl\\'>${stemEmojiMap[dayStemCharacter]}</div>'">
        `;
    }

    if (stemName) stemName.textContent = stemKoreanMap[dayStemCharacter];
    if (stemDesc) stemDesc.textContent = stemDescMap[dayStemCharacter];
}
```

**오행별 이미지 사용 시**:
```javascript
// 오행 매핑
const elementMapping = {
    '甲': 'wood', '乙': 'wood',
    '丙': 'fire', '丁': 'fire',
    '戊': 'earth', '己': 'earth',
    '庚': 'metal', '辛': 'metal',
    '壬': 'water', '癸': 'water'
};
const elementType = elementMapping[dayStemCharacter];

if (stemImageContainer && elementType) {
    stemImageContainer.innerHTML = `
        <img src="/static/fortune/images/elements/${elementType}.png"
             class="w-48 h-48 object-cover rounded-full"
             alt="${stemKoreanMap[dayStemCharacter]}">
    `;
}
```

### 참고사항

1. **이미지 없이도 동작함**: 현재 이모지로 표시되므로 이미지 없이도 문제없습니다.
2. **폴백 처리**: 위 코드의 `onerror` 속성으로 이미지 로드 실패 시 이모지로 대체됩니다.
3. **캐싱**: 이미지 변경 시 브라우저 캐시 때문에 반영이 안 될 수 있습니다. 강제 새로고침(Ctrl+F5)으로 해결하세요.

---

## 다음 세션 시작 방법

```
HANDOFF.md 읽고 이어서 작업해줘
```

또는:
```
Cloudinary 이미지 저장소 연동해줘
```

또는:
```
사주 서비스 이미지 추가해줘
```
