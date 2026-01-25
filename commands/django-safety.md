# Django Template Safety Rules

Django 템플릿 파일(.html)을 수정할 때 발생하는 `TemplateSyntaxError`를 방지하기 위한 핵심 규칙입니다.

## 1. 템플릿 태그 줄바꿈 금지 (Critical)
Django의 템플릿 태그(`{% ... %}`, `{{ ... }}`)는 반드시 **한 줄**에 작성해야 합니다. 줄바꿈이 포함되면 구문 오류가 발생합니다.

### ❌ 절대 하지 말 것 (에러 발생)
```html
<!-- if 태그가 줄바꿈됨 -->
{% if product.card_size 
    == 'hero' %}
    ...
{% endif %}

<!-- 변수 태그가 줄바꿈됨 -->
{{ product.title|
   truncatechars:20 }}
```

### ✅ 올바른 작성법
```html
<!-- 태그는 항상 한 줄에 -->
{% if product.card_size == 'hero' %}
    ...
{% endif %}

<!-- 긴 경우에도 한 줄 유지 -->
{{ product.title|truncatechars:20 }}
```

## 2. 긴 조건문 처리
조건문이 너무 길어질 경우, `with` 태그를 사용하거나 모델/뷰에서 프로퍼티로 처리하는 것을 권장합니다. 하지만 템플릿 내에서 해결해야 한다면 **절대 줄바꿈하지 말고 옆으로 길게 작성**하세요.

## 3. 아이콘/이모지 렌더링
`{{ ... }}` 태그가 HTML 속성(class 등) 내부에 들어갈 때 공백이나 줄바꿈이 들어가지 않도록 주의하세요.

```html
<!-- ❌ 공백 위험 -->
<i class="{ { product.icon } }"></i>

<!-- ✅ 타이트하게 작성 -->
<i class="{{ product.icon }}"></i>
```
