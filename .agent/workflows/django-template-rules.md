---
description: Django Template Tag Rules to Prevent Rendering Errors
---

# Django Template Tag Formatting Rules

To prevent rendering errors where tags like `{{ ... }}` appear as literal text on the screen, the following rules MUST be strictly followed:

## 1. No Newlines inside Mustache Tags
NEVER insert a newline character inside a `{{ ... }}` block. The opening `{{` and closing `}}` along with the content MUST remain on the same single line.

- **❌ WRONG (Causes literal rendering):**
  ```html
  {{
    user.nickname
  }}
  ```

- **✅ CORRECT:**
  ```html
  {{ user.nickname }}
  ```

## 2. No Newlines inside Logic Tags
Similarly, avoid breaking logic tags `{% ... %}` across multiple lines unless they are complex block tags (like `{% if %}`, `{% for %}`). Even for blocks, the tag delimiters `{%` and `%}` themselves must be on the same line as their immediate content.

- **❌ WRONG:**
  ```html
  {%
    if user.is_authenticated
  %}
  ```

- **✅ CORRECT:**
  ```html
  {% if user.is_authenticated %}
  ```

## 3. Strict Verification
Before every `git commit`, verify that no `{{` tag has been split by a formatter or manual edit.
