# Railway에서 쌤BTI 문제 해결 가이드

## 방법 1: Railway Dashboard에서 Shell 실행

1. Railway 대시보드 접속
2. 해당 프로젝트 선택
3. 오른쪽 상단 "..." → "Shell" 또는 "SSH" 클릭
4. 다음 명령어 실행:

```bash
python manage.py ensure_ssambti
```

출력 예시:
```
======================================================================
[Ssambti Product Setup]
======================================================================
[!] Found existing Ssambti product (ID: ...)
[X] external_url is not empty!
[OK] Updated Ssambti product with correct settings
...
[INFO] Total products in database: 13
```

## 방법 2: 강제 재배포

1. Railway 대시보드에서 "Deployments" 탭
2. 최신 배포 옆 "..." → "Redeploy"
3. 이번에는 Deploy Logs를 **처음부터 끝까지** 확인

## 방법 3: Railway CLI 사용 (로컬에서)

```bash
# Railway CLI 설치
npm install -g @railway/cli

# 로그인
railway login

# 프로젝트 연결
railway link

# 명령어 실행
railway run python manage.py ensure_ssambti
```

## 방법 4: 환경 변수로 강제 실행 트리거

Railway에 환경 변수 추가:
```
FORCE_SETUP=1
```

그리고 Procfile 수정하여 조건부 실행:
```bash
web: python3 manage.py collectstatic --noinput && python3 manage.py migrate --noinput && python3 manage.py ensure_ssambti --verbosity=2 && gunicorn config.wsgi --log-file - --timeout 120
```

## 현재 상황 확인

Django Admin에서 확인:
1. https://[your-url]/secret-admin-kakio/products/product/
2. "쌤BTI" 제품이 있는지 확인
3. 있다면:
   - external_url 필드가 **비어있어야 함**
   - service_type이 **"game"이어야 함**
4. 없다면: 위 방법 1-3 중 하나로 직접 실행

## 최종 확인

메인 페이지에서:
- Ctrl + Shift + R (강제 새로고침)
- 쌤BTI 카드가 보이는지 확인
- 카드 클릭 시 /ssambti/로 이동하는지 확인
