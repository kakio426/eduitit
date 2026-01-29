from fortune.libs.calculator import get_pillars
from datetime import datetime
import pytz
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

dt = datetime(1963, 6, 4, 12, 0, tzinfo=pytz.timezone('Asia/Seoul'))
pillars = get_pillars(dt)
print(f"YEAR: {pillars['year']['stem'].name}{pillars['year']['branch'].name}")
print(f"MONTH: {pillars['month']['stem'].name}{pillars['month']['branch'].name}")
print(f"DAY: {pillars['day']['stem'].name}{pillars['day']['branch'].name}")
print(f"HOUR: {pillars['hour']['stem'].name}{pillars['hour']['branch'].name}")
