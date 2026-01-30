import os
import sys
from io import StringIO
from django.core.management import call_command

# 설정 파일 지정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')

import django
django.setup()

# 출력 캡처
out = StringIO()
sys.stdout = out
sys.stderr = out

print("Running collectstatic...")
try:
    call_command('collectstatic', interactive=False, verbosity=2, clear=True) # verbosity 높임, clear 추가
    print("\nSUCCESS: collectstatic finished.")
except Exception as e:
    print(f"\nERROR: {e}")

# 파일로 저장
with open('collectstatic_debug.log', 'w', encoding='utf-8') as f:
    f.write(out.getvalue())

# 결과 요약 출력 (콘솔용)
sys.stdout = sys.__stdout__
print("Log saved to collectstatic_debug.log")
