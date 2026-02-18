# PLAN: UX Rollout Continuation (2026-02-18)

## 1) 紐⑹쟻
- ?꾩옱 吏꾪뻾 以묒씤 UX 媛쒖꽑(UX-04 ~ UX-07)???덉쟾?섍쾶 ?댁뼱媛湲??꾪븳 ?ㅽ뻾 怨꾪쉷??怨좎젙?쒕떎.
- ?μ븷 諛쒖깮 ??鍮좊Ⅴ寃??섎룎由????덈룄濡??뚮옒洹?寃利?濡ㅻ갚 ?덉감瑜?臾몄꽌?뷀븳??

## 2) ?꾩옱 ?뺤젙 ?곹깭 (Snapshot)
- 완료:
  - UX-01: iPad/태블릿 차단 정책 개선
  - UX-02: 모바일 미지원 페이지 대체 경로 추가
  - UX-03: 댓글/액션 터치 접근성 개선
  - UX-04: V2 플래그 의존성 정리 (기본값 True + 롤백 규칙 문서화)
  - UX-05: route 필드화 (모델/마이그레이션/백필 + title fallback 제거)
  - UX-06: 768~1024 레이아웃 재설계 (SNS 분기점 `xl` 전환)
- 진행 중:
  - UX-07: IA 단순화 (섹션 preview cap 적용 완료, 추가 구조 단순화 잔여)

## 3) ?대? 諛섏쁺???댁쁺 ?ъ씤??- ?붾컮?댁뒪/濡ㅻ갚 ?뚮옒洹?
  - `config/settings.py:432` `ALLOW_TABLET_ACCESS`
  - `config/settings_production.py:548` `ALLOW_TABLET_ACCESS`
- 寃???뚮옒洹?遺꾨━:
  - `config/settings.py:433` `GLOBAL_SEARCH_ENABLED`
  - `config/settings_production.py:549` `GLOBAL_SEARCH_ENABLED`
  - `core/context_processors.py:75` (`HOME_V2_ENABLED` ?섏〈 ?쒓굅)
- ??붾㈃ ?쒕퉬??吏꾩엯 ?뺤콉:
  - `products/views.py:10` `_is_phone_user_agent`
  - `products/views.py:31` `_is_force_desktop`
  - `products/views.py:36` `_should_block_for_large_screen_service`
  - `products/views.py:88`, `products/views.py:102` (`continue_url`)
- 李⑤떒 ?섏씠吏 ?泥?寃쎈줈:
  - `products/templates/products/mobile_not_supported.html:34`
- ?곗튂 ?묎렐??
  - `core/templates/core/partials/comment_item.html:22`

## 4) ?ㅼ쓬 ?ㅽ뻾 ?쒖꽌
1. UX-04 留덈Т由?(?댁쁺 湲곗? ?뺤젙)
- `HOME_V2_ENABLED` 湲곕낯媛??댁쁺/?ㅽ뀒?댁쭠) ?뺤젙
- ?뚮옒洹?濡ㅻ갚 ?곕턿 ?뺤젙:
  - `HOME_V2_ENABLED`
  - `GLOBAL_SEARCH_ENABLED`
  - `ALLOW_TABLET_ACCESS`
- 諛고룷 臾몄꽌 諛섏쁺

2. UX-05 route ?꾨뱶??- 紐⑺몴: `title` 臾몄옄??遺꾧린 ?쒓굅
- 諛⑹떇: `Product`??紐낆떆??launch route ?꾨뱶 ?꾩엯 + ?먯쭊 ?꾪솚
- ?섏쐞?명솚: 湲곗〈 遺꾧린 ?좎? 湲곌컙 ?ㅼ젙 ???쒓굅

3. UX-06 ?쒕툝由??덉씠?꾩썐 媛쒖꽑
- 踰붿쐞: `768~1024` 援ш컙
- 紐⑺몴: 醫뚯륫 SNS ?ъ씠?쒕컮? 硫붿씤 肄섑뀗痢???異⑸룎 ?쒓굅

4. UX-07 IA ?⑥닚??- ?듭떖 ?ъ슜???쒕굹由ъ삤瑜?泥??붾㈃ 1李??몄텧
- 蹂댁“ 湲곕뒫? ?묎린/2李?吏꾩엯?쇰줈 ?대룞

## 5) 寃利?寃뚯씠??(媛??④퀎 怨듯넻)
- ?꾩닔 紐낅졊:
  - `python manage.py check`
  - ?④퀎蹂?愿???뚯뒪??- 理쒖냼 ?뚭? ?명듃:
  - `python manage.py test products.tests.test_views core.tests.test_home_view products.tests.test_dashboard_modals core.tests.test_ui_auth -v 1`
- 諛고룷 ???뺤씤:
  - phone/iPad/desktop 吏꾩엯 ?뺤콉
  - 寃??紐⑤떖 ?몄텧/鍮꾨끂異?(`GLOBAL_SEARCH_ENABLED`)
  - 紐⑤떖 ?닿린/?リ린 諛?二쇱슂 ?쇱슦??
## 6) ?μ븷 ???濡ㅻ갚
- ?쒕툝由??묎렐 ?댁뒋:
  - `ALLOW_TABLET_ACCESS=False/True`濡?利됱떆 ?좉?
- 寃??IA ?몄텧 ?댁뒋:
  - `GLOBAL_SEARCH_ENABLED=False`濡?寃??湲곕뒫留??낅┰ 鍮꾪솢?깊솕
- V2 ?덉씠?꾩썐 ?댁뒋:
  - `HOME_V2_ENABLED=False`濡?利됱떆 V1 ?뚭?

## 7) 遺꾩꽍??湲곕줉 洹쒖튃
- 紐⑤뱺 蹂寃쎌? `docs/handoff/HANDOFF_ux_rollout_snapshot_2026-02-18.md`???꾩쟻 湲곕줉
- ?뚯뒪??紐낅졊/寃곌낵瑜??붿빟???꾨땲??"紐낅졊 + ?듦낵 ?щ?" ?뺥깭濡??④릿??- ?ы쁽 議곌굔(UA, ?뚮옒洹멸컪, URL ?뚮씪誘명꽣)???④퍡 湲곕줉?쒕떎
