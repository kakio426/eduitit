from fortune.libs.calculator import get_pillars
from datetime import datetime
import pytz

dt = datetime(1963, 6, 4, 12, 0, tzinfo=pytz.timezone('Asia/Seoul'))
p = get_pillars(dt)
print(f"YEAR: {p['year']['stem'].name}{p['year']['branch'].name}")
print(f"MONTH: {p['month']['stem'].name}{p['month']['branch'].name}")
print(f"DAY: {p['day']['stem'].name}{p['day']['branch'].name}")
print(f"HOUR: {p['hour']['stem'].name}{p['hour']['branch'].name}")
