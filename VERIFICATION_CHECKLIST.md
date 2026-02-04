# 사주 앱 재구성 검증 체크리스트

## 배포 전 확인 사항

### 1. ✅ 파일 존재 확인
```bash
# 신규 파일 확인
ls -la fortune/views_teacher.py
ls -la fortune/views_general.py
ls -la fortune/utils/pillar_serializer.py
ls -la fortune/templates/fortune/base_saju_form.html
ls -la fortune/templates/fortune/teacher_form.html
ls -la fortune/templates/fortune/general_form.html
ls -la fortune/migrations/0009_enhance_cache_schema.py
```

### 2. ✅ 마이그레이션 확인
```bash
# 로컬에서 마이그레이션 적용 확인
python manage.py showmigrations fortune

# 프로덕션에서 마이그레이션 적용
python manage.py migrate fortune
```

### 3. 🔍 URL 접근 테스트

브라우저에서 다음 URL 접속:

- [ ] `http://localhost:8000/fortune/` → 교사 모드로 리다이렉트 확인
- [ ] `http://localhost:8000/fortune/teacher/` → 🍎 아이콘 + "교사 사주운세" 헤더 확인
- [ ] `http://localhost:8000/fortune/general/` → 🌟 아이콘 + "일반 사주 분석" 헤더 확인

### 4. 🔍 캐싱 동작 테스트

#### A. 일진 캐싱 테스트
1. 로그인 후 `/fortune/teacher/` 접속
2. 사주 정보 입력 후 분석
3. "일진 보기" 클릭 → 특정 날짜 선택 (예: 내일)
4. **첫 조회**: 응답 시간 측정 (20-30초 예상)
5. 같은 날짜 다시 선택
6. **두 번째 조회**: 응답 시간 측정 (<1초 예상)
7. 브라우저 콘솔에서 캐시 히트 확인 (선택 사항)

#### B. 모드별 격리 테스트
1. 교사 모드에서 일진 조회 (예: 2026-02-10)
2. 일반 모드에서 **같은 사주, 같은 날짜** 일진 조회
3. 결과 비교:
   - 교사 모드: "학급", "학생", "교실" 등의 키워드 포함
   - 일반 모드: "업무", "학업", "인간관계" 등의 키워드 포함
4. 두 결과가 다른지 확인 ✅

### 5. 🔍 Django Shell 검증

```bash
python manage.py shell
```

```python
# 모델 임포트 확인
from fortune.models import DailyFortuneCache, FortuneResult
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()

# DailyFortuneCache 모델 확인
print(DailyFortuneCache.objects.count())  # 캐시 개수
print(DailyFortuneCache.objects.filter(user=user).values('mode', 'target_date'))

# FortuneResult 모델 확인 (user_context_hash 필드 추가)
result = FortuneResult.objects.first()
if result:
    print(f"natal_hash: {result.natal_hash}")
    print(f"user_context_hash: {result.user_context_hash}")

# 캐싱 함수 테스트
from fortune.utils.caching import get_user_context_hash
hash_result = get_user_context_hash('테스트', 'male', 'test_natal_hash')
print(f"User context hash: {hash_result[:16]}...")  # 앞 16자만 출력
```

### 6. 🔍 API 응답 확인

#### A. 일진 API 캐시 확인
```bash
# 캐시 미스 (첫 조회)
curl -X POST http://localhost:8000/fortune/api/daily/ \
  -H "Content-Type: application/json" \
  -d '{
    "target_date": "2026-02-15",
    "natal_chart": {"year": "甲子", "month": "丙寅", "day": "戊辰", "hour": "庚午"},
    "name": "테스트",
    "gender": "male",
    "mode": "teacher"
  }'

# 응답에서 "cached": false 확인

# 캐시 히트 (두 번째 조회 - 같은 요청)
# 응답에서 "cached": true 확인
```

#### B. 스트리밍 API 캐시 확인
```bash
# 응답 헤더에서 X-Cache-Hit 확인
curl -I http://localhost:8000/fortune/api/streaming/ \
  -X POST \
  -d "name=테스트&gender=male&mode=teacher&..."
```

### 7. ⚠️ 프로덕션 설정 확인

#### settings_production.py 동기화 필요 사항
- **이번 구현에서는 설정 변경 없음** (모델만 추가)
- 단, 마이그레이션은 프로덕션에서 반드시 실행

```bash
# Railway/Heroku에서 실행
python manage.py migrate fortune
```

### 8. 📊 모니터링 (배포 후)

#### A. 캐시 히트율 확인
```python
from fortune.models import DailyFortuneCache, DailyFortuneLog

total_requests = DailyFortuneLog.objects.count()
cached_results = DailyFortuneCache.objects.count()

cache_rate = (cached_results / total_requests * 100) if total_requests > 0 else 0
print(f"캐시 히트율: {cache_rate:.1f}%")
# 목표: 30-50% (같은 사주로 같은 날짜를 여러 번 조회할 가능성)
```

#### B. API 비용 절감 확인
- 배포 후 1주일 뒤 API 사용량 확인
- Gemini/DeepSeek 대시보드에서 요청 수 비교
- 예상: 40-45% 감소

#### C. 응답 시간 개선 확인
- 일진 조회 시 캐시 히트 시간 측정
- 목표: <1초 (기존 20-30초 대비 99% 개선)

### 9. 🐛 알려진 이슈

#### 모델 재등록 경고
```
RuntimeWarning: Model 'fortune.dailyfortunecache' was already registered.
```
- **원인**: 개발 환경의 핫 리로드
- **영향**: 없음 (개발 환경에서만 발생)
- **해결**: 프로덕션 환경에서는 발생하지 않음

### 10. ✅ 최종 체크리스트

배포 전:
- [ ] 모든 마이그레이션 적용 완료
- [ ] 로컬에서 교사/일반 모드 URL 접근 확인
- [ ] 로컬에서 일진 캐싱 동작 확인
- [ ] 모드별 일진 내용 격리 확인
- [ ] Django shell에서 모델 확인

배포 후:
- [ ] 프로덕션에서 마이그레이션 적용
- [ ] 프로덕션에서 URL 접근 확인
- [ ] 프로덕션에서 캐싱 동작 확인
- [ ] 1주일 후 캐시 히트율 확인
- [ ] 1주일 후 API 비용 절감 확인

---

## 빠른 검증 스크립트

```bash
#!/bin/bash
# 로컬 환경에서 실행

echo "🔍 Phase 1-4 구현 검증"

# 1. 파일 존재 확인
echo "✅ 신규 파일 확인..."
test -f fortune/views_teacher.py && echo "  - views_teacher.py: OK" || echo "  - views_teacher.py: MISSING"
test -f fortune/views_general.py && echo "  - views_general.py: OK" || echo "  - views_general.py: MISSING"
test -f fortune/utils/pillar_serializer.py && echo "  - pillar_serializer.py: OK" || echo "  - pillar_serializer.py: MISSING"
test -f fortune/templates/fortune/base_saju_form.html && echo "  - base_saju_form.html: OK" || echo "  - base_saju_form.html: MISSING"

# 2. 마이그레이션 확인
echo ""
echo "✅ 마이그레이션 확인..."
python manage.py showmigrations fortune | grep "0009_enhance_cache_schema"

# 3. 모델 확인
echo ""
echo "✅ 모델 확인..."
python manage.py shell -c "
from fortune.models import DailyFortuneCache
print(f'DailyFortuneCache 모델: {DailyFortuneCache._meta.db_table}')
print(f'필드 수: {len(DailyFortuneCache._meta.fields)}')
"

echo ""
echo "✅ 검증 완료! 브라우저에서 수동 테스트를 진행하세요."
echo "   - http://localhost:8000/fortune/teacher/"
echo "   - http://localhost:8000/fortune/general/"
```

---

## 문제 발생 시 롤백 방법

### 1. 마이그레이션 롤백
```bash
# 이전 마이그레이션으로 되돌리기
python manage.py migrate fortune 0008_alter_fortuneresult_unique_together
```

### 2. URL 롤백
```python
# fortune/urls.py에서 수정
path('', views.saju_view, name='saju'),  # 기존 뷰로 복원
```

### 3. 템플릿 롤백
```bash
# 기존 템플릿 사용
mv fortune/templates/fortune/saju_form.html.backup fortune/templates/fortune/saju_form.html
```
