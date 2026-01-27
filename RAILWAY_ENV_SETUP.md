# Railway 환경 변수 설정 가이드

## 🚨 필수 설정 (Railway Dashboard에서 설정)

Railway 프로젝트 → Variables 탭에서 아래 환경 변수를 **반드시** 설정해야 합니다.

### 1. Django 설정
```bash
DJANGO_SETTINGS_MODULE=config.settings_production
DJANGO_SECRET_KEY=<강력한 랜덤 키 생성 필요>
DJANGO_DEBUG=False
ALLOWED_HOSTS=.railway.app,eduitit.site,www.eduitit.site
```

**SECRET_KEY 생성 방법:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2. 데이터베이스 (PostgreSQL)
Railway에서 PostgreSQL 플러그인 추가 시 자동으로 `DATABASE_URL` 생성됨
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

> ⚠️ **중요**: DATABASE_URL이 없으면 SQLite를 사용하게 됩니다!
> SQLite는 프로덕션 환경에 적합하지 않습니다 (동시 접속 처리 불가).

### 3. Cloudinary (이미지 저장소)
```bash
CLOUDINARY_CLOUD_NAME=dl5pq1o6o
CLOUDINARY_API_KEY=719636959788391
CLOUDINARY_API_SECRET=-aZFKug8SeFJnWNiI-5ajPLOf64
CLOUDINARY_URL=cloudinary://719636959788391:-aZFKug8SeFJnWNiI-5ajPLOf64@dl5pq1o6o
```

### 4. 소셜 로그인 (Kakao, Naver)
```bash
KAKAO_CLIENT_ID=08173c0ab91102b7cbf348564b4cd0ea
KAKAO_CLIENT_SECRET=<시크릿 키>
NAVER_CLIENT_ID=FK4ZWrVuv1I80fjRhrQb
NAVER_CLIENT_SECRET=prX2VqR53R
```

### 5. AI API 키
```bash
GEMINI_API_KEY=AIzaSyCo29bqCrZfA2hBYNwIOarDj1ZgnVjg70c
MASTER_DEEPSEEK_API_KEY=sk-d2cb78f7225c4be08a2cbf2068a8206c
```

### 6. 기타 설정
```bash
SSO_JWT_SECRET=ghksrudtjfwjddkTkfkql88!@!
SCHOOLIT_URL=https://schoolit.shop
PADLET_API_KEY=pdltp_3bcdceb2e74b30093f68af8c5d14b78266577641f9e97ea011d135aa67e18df10372b7
```

---

## 🔍 설정 확인 방법

### Railway 배포 후 로그 확인
```bash
railway logs
```

로그에서 다음 메시지를 확인:
- ✅ `[DATABASE] Using PostgreSQL with conn_max_age=600`
- ✅ `DEBUG: Cloudinary initialized: dl5pq1o6o`
- ❌ `[DATABASE] Using SQLite (development)` ← 이 메시지가 나오면 DATABASE_URL 설정 누락!

### 체크리스트
- [ ] DJANGO_SETTINGS_MODULE=config.settings_production
- [ ] DJANGO_DEBUG=False
- [ ] DATABASE_URL 설정 (PostgreSQL)
- [ ] DJANGO_SECRET_KEY 변경 (기본값 사용 금지)
- [ ] ALLOWED_HOSTS에 실제 도메인 포함
- [ ] Cloudinary 설정 (CLOUDINARY_URL)
- [ ] 소셜 로그인 키 설정 (KAKAO_CLIENT_ID, NAVER_CLIENT_ID)

---

## 📊 현재 설정 vs 권장 설정

| 항목 | 이전 설정 | 수정 후 설정 |
|------|-----------|-------------|
| Settings Module | `config.settings` (개발용) | `config.settings_production` |
| Database | SQLite (단일 연결) | PostgreSQL (CONN_MAX_AGE=600) |
| DEBUG | True ⚠️ | False ✅ |
| 정적 파일 | Django 기본 | WhiteNoise (압축, 캐싱) |
| 보안 설정 | 없음 ⚠️ | HTTPS, HSTS, CSP ✅ |
| DB 연결 풀링 | 없음 | 600초 (10분) ✅ |

---

## 🚀 배포 순서

1. **Railway에서 PostgreSQL 플러그인 추가**
   - New → Database → PostgreSQL
   - 자동으로 DATABASE_URL 환경 변수 생성됨

2. **환경 변수 설정**
   - Variables 탭에서 위의 필수 환경 변수 모두 입력

3. **재배포**
   ```bash
   git add .
   git commit -m "fix: 프로덕션 설정으로 전환 및 PostgreSQL 지원 추가"
   git push
   ```

4. **마이그레이션 확인**
   - Railway 로그에서 `python manage.py migrate` 성공 확인

5. **Site 도메인 설정 (Django Admin)**
   - Railway URL로 접속
   - `/admin` → Sites → 도메인을 실제 Railway URL로 변경
   - 예: `web-production-f2869.up.railway.app`

---

## ⚠️ 주의사항

### .env 파일은 로컬 개발용
- `.env` 파일은 로컬 개발 환경에서만 사용
- Railway에서는 **환경 변수 탭**에서 직접 설정
- `.env` 파일은 `.gitignore`에 포함되어 Git에 커밋되지 않음

### 민감한 정보 관리
- ❌ `.env` 파일을 Git에 커밋하지 마세요
- ✅ `.env.example` 파일로 템플릿만 공유
- ✅ Railway 환경 변수에만 실제 값 저장

### DEBUG=True 절대 금지 (프로덕션)
- 내부 에러 정보 노출
- 민감한 경로 정보 노출
- 성능 저하

---

## 🔧 수정된 파일 목록

1. `config/wsgi.py` - settings_production 기본 사용
2. `config/settings.py` - DATABASE_URL 지원 추가 (폴백)
3. `config/settings_production.py` - django_htmx 추가
4. `requirements.txt` - django-htmx 추가
5. `.env` - DJANGO_SETTINGS_MODULE 명시

---

## 📚 참고 자료

- [Django 배포 체크리스트](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/)
- [Railway PostgreSQL 가이드](https://docs.railway.app/databases/postgresql)
- [dj-database-url 문서](https://github.com/jazzband/dj-database-url)
