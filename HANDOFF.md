# 작업 인계 문서

> 생성일: 2025-01-24
> 세션: AutoArticle 기능 완성 (원본 비교 및 누락 기능 구현)

---

## 완료된 작업

### 1. AutoArticle 원본 비교 및 기능 구현 (오늘)
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

- **배포 도메인**: `https://web-production-f2869.up.railway.app/`
- **테스트**: Django check 통과, import 테스트 통과
- **서버 실행**: 수동 테스트 필요

---

## 이전 세션 작업

- 2025-01-24: **Cloudinary 이미지 저장소 연동 완료**
- 2025-01-24: AutoArticle 기능 완성 (Word, 삭제, 수정, Rate Limiter)
- 2025-01-24: Padlet Bot 앱 생성, 소셜 로그인 수정
- 2025-01-23: DutyTicker 디자인 통합, AutoArticle 오류 수정

---

## 다음 세션 시작 방법

```
HANDOFF.md 읽고 이어서 작업해줘
```

또는:
```
Cloudinary 이미지 저장소 연동해줘
```
