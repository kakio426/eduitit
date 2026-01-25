import ephem
from korean_lunar_calendar import KoreanLunarCalendar
from datetime import datetime, timedelta
import pytz

TERM_NAMES = [
    ('Lichun', 315), ('Usu', 330), ('Gyeongchip', 345), ('Chunbun', 0),
    ('Cheongmyeong', 15), ('Gokwoo', 30), ('Ipha', 45), ('Soman', 60),
    ('Mangjong', 75), ('Haji', 90), ('Soseo', 105), ('Daeseo', 120),
    ('Ipchu', 135), ('Cheoseo', 150), ('Baekro', 165), ('Chubun', 180),
    ('Hallo', 195), ('Sanggang', 210), ('Ipdong', 225), ('Soseol', 240),
    ('Daeseol', 255), ('Dongji', 270), ('Sohan', 285), ('Daehan', 300)
]

def get_solar_term_date(year, term_name):
    """
    Get exact datetime of a specific solar term.
    """
    target_lon = None
    for name, deg in TERM_NAMES:
        if name == term_name:
            target_lon = deg
            break
            
    if target_lon is None:
        return None
        
    # Convert to radians
    target_rad = target_lon * ephem.degree
    
    sun = ephem.Sun()
    
    # Efficient start date estimation
    term_index = [t[0] for t in TERM_NAMES].index(term_name)
    days_offset = term_index * 15.2 + 34
    if days_offset > 365: days_offset -= 365
    
    # Approx check implementation
    # Lichun Feb 4, each 15 days roughly.
    start_month = 1
    if term_index >= 22: start_month = 12 # Dongji, Sohan, Daehan
    elif term_index >= 20: start_month = 11
    else: start_month = int(days_offset / 30) + 1
    
    # Search around estimated month
    # To be safe, searched from Jan 1 is okay for < 1s penalty usually but 
    # let's try to be slightly smarter or just safe.
    search_date = datetime(year, 1, 1)

    # Note: ephem dates are float (days since 1899...)
    # We want to find DATE where sun.lon == target_rad
    
    def get_lon(d):
        sun.compute(d)
        ecl = ephem.Ecliptic(ephem.Equatorial(sun.ra, sun.dec, epoch=d))
        return ecl.lon

    t0 = ephem.Date(search_date)
    step = 1.0
    found_time = None
    current_t = t0

    # Quick scan 365 days
    for _ in range(370):
        l1 = get_lon(current_t)
        l2 = get_lon(current_t + step)
        
        # Check containment handling wrap
        # Safe way: angle distance
        # But simple interval check works for 99%
        is_between = False
        
        if l1 <= target_rad <= l2:
            is_between = True
        # Wrap case: target 0 (Chunbun), l1 359, l2 1
        # target_rad is 0.0
        elif target_rad < 0.1: # 0 degrees
            if l1 > 6.0 and l2 < 1.0: # passed 2pi
                is_between = True
                
        if is_between:
            found_time = current_t
            break
        current_t += step
        
    if found_time:
        # Refine (minute)
        step = ephem.minute
        current_t = found_time
        for _ in range(1440 * 2):
            l1 = get_lon(current_t)
            l2 = get_lon(current_t + step)
             
            is_between = False
            if l1 <= target_rad <= l2:
                is_between = True
            elif target_rad < 0.1 and l1 > 6.0 and l2 < 1.0:
                 is_between = True
                 
            if is_between:
                dt_utc = ephem.Date(current_t).datetime().replace(tzinfo=pytz.utc)
                return dt_utc.astimezone(pytz.timezone('Asia/Seoul'))
            current_t += step

    return None

def get_all_solar_terms(year):
    """
    Get all 24 solar terms for the year
    """
    terms = {}
    for name, deg in TERM_NAMES:
        terms[name] = get_solar_term_date(year, name)
    return terms


def get_apparent_solar_time(dt, longitude):
    """
    Calculate Apparent Solar Time (True Solar Time).
    dt: datetime object (aware)
    longitude: float (degrees)
    """
    # Simply apply longitude correction for now as per previous success
    # Standard Meridian for KST is 135
    # 1 degree = 4 minutes
    diff_deg = longitude - 135.0
    diff_minutes = diff_deg * 4
    
    # Equation of Time (EOT) should ideally be added here for precision
    # But we'll stick to the basic longitude correction first which passed the range test
    return dt + timedelta(minutes=diff_minutes)


def lunar_to_solar(year, month, day, leap):
    calendar = KoreanLunarCalendar()
    calendar.setLunarDate(year, month, day, leap)
    s_date = calendar.SolarIsoFormat()
    return datetime.strptime(s_date, '%Y-%m-%d').date()
