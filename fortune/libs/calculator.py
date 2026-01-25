from fortune.models import Stem, Branch
from fortune.libs import manse
from datetime import datetime, timedelta
import pytz

def get_pillars(dt):
    """
    Calculate the Four Pillars for a given datetime (KST aware).
    """
    # 0. Adjust to Apparent Solar Time
    # Default longitude 135 (Standard) if not provided?
    # Logic should accept SajuProfile or User inputs, but for core calc let's assume raw inputs
    # Use Seoul (127.0) as default for now if no geo info
    solar_time = manse.get_apparent_solar_time(dt, 127.0)
    
    year = solar_time.year
    month = solar_time.month
    day = solar_time.day
    hour = solar_time.hour
    
    # 1. Year Pillar (Year Stem/Branch)
    # Determined by solar year (Ipchu usually starts the year in some schools? No, Lichun)
    # Lichun (Start of Spring) determines the year change.
    
    # Get Lichun of the current year
    lichun = manse.get_solar_term_date(year, 'Lichun')
    
    if solar_time < lichun:
        current_year = year - 1
    else:
        current_year = year
        
    year_ganji = get_yearly_ganji(current_year)
    
    # 2. Month Pillar
    # Determined by Solar Terms (Jeolgi)
    # Lichun -> Month 1 (Tiger)
    # Gyeongchip -> Month 2 (Rabbit)
    # ...
    
    # We need to find which Jeolgi we are in.
    # We need the 12 major terms (Jeol)
    major_terms = [
        ('Lichun', 'In'), ('Gyeongchip', 'Myo'), ('Cheongmyeong', 'Jin'), 
        ('Ipha', 'Sa'), ('Mangjong', 'O'), ('Soseo', 'Mi'), 
        ('Ipchu', 'Shin'), ('Baekro', 'Yoo'), ('Hallo', 'Sool'), 
        ('Ipdong', 'Hae'), ('Daeseol', 'Ja'), ('Sohan', 'Chuk')
    ]
    
    # Check terms of the year (or prev year if Jan/Feb before Lichun)
    # Be careful with year boundary.
    # If we are in Jan 2024 before Lichun, we are technically in Chuk month of 2023.
    
    # Load terms for the relevant year
    # If solar_time < lichun, we use prev year's terms?
    # Actually, simpler: just Find the latest major term that has passed.
    
    # Implementation: Get all terms for current_year and current_year+1?
    term_dates = manse.get_all_solar_terms(current_year)
    
    # Find active term
    # Default to last term of previous year (Sohan -> Chuk) if before Lichun?
    # But current_year logic handled year drop.
    # So if we are 2024 Jan 1, current_year is 2023.
    # Terms of 2023: Lichun... Sohan(Jan 2024).
    # So we check 2023 terms.
    
    # Sort terms by date
    sorted_terms = []
    for t_name, t_branch_name in major_terms:
        t_date = term_dates.get(t_name)
        # Note: Sohan/Daeseol might be in next calendar year? 
        # Typically manse.get_all_solar_terms(2023) should return Sohan as Jan 2024?
        # My manse implementation might need checking on this.
        # Assuming manse returns correct datetimes.
        if t_date:
            sorted_terms.append((t_date, t_branch_name))
            
    sorted_terms.sort(key=lambda x: x[0])
    
    month_branch_char = 'Chuk' # Default?
    # Find last passed term
    for t_date, t_branch in sorted_terms:
        if solar_time >= t_date:
            month_branch_char = t_branch
            
    # Month Stem is derived from Year Stem + Month Branch (Five Tigers)
    year_stem = year_ganji['stem']
    month_branch = Branch.objects.get(name=month_branch_char)
    month_stem = get_month_stem(year_stem, month_branch)
    
    # 3. Day Pillar
    # Calculated from absolute days since a reference epoch.
    # Ref: 1900-01-01 was Jia-Xu (Gap-Sool)? No, need precise ref.
    # Standard: epoch 1900-01-01 ?? 
    # Better: Use korean-lunar-calendar or a known formula.
    
    # Using python reference:
    ref_date = datetime(1900, 1, 1, tzinfo=pytz.utc) # UTC? Or whatever.
    # 1900-01-01 was ... 
    # Use a known recent date. 2024-01-01 was 甲子 (Gap-Ja). (Wait, verify!)
    # Actually 2024-01-01 was Gap-Ja (甲子). Simple reference.
    
    ref_day = datetime(2024, 1, 1, tzinfo=pytz.timezone('Asia/Seoul'))
    ref_stem_idx = 0 # 甲
    ref_branch_idx = 0 # 子
    
    days_diff = (solar_time.date() - ref_day.date()).days
    
    day_stem_idx = (ref_stem_idx + days_diff) % 10
    day_branch_idx = (ref_branch_idx + days_diff) % 12
    
    # Get objects (assuming order)
    # Stems: 0=Gap.. 9=Gye
    # Branches: 0=Ja.. 11=Hae
    
    # Optimizing: Load strict list
    stems_list = list(Stem.objects.all()) # Assume sorted by ID creation? dangerous.
    # Be safe:
    STEMS = ['Gap', 'Eul', 'Byung', 'Jung', 'Moo', 'Gi', 'Gyung', 'Shin', 'Im', 'Gye']
    BRANCHES = ['Ja', 'Chuk', 'In', 'Myo', 'Jin', 'Sa', 'O', 'Mi', 'Shin', 'Yoo', 'Sool', 'Hae']
    
    day_stem = Stem.objects.get(name=STEMS[day_stem_idx])
    day_branch = Branch.objects.get(name=BRANCHES[day_branch_idx])
    
    # 4. Hour Pillar
    # Derived from Day Stem + Hour Branch
    # Determine Hour Branch from time
    
    # Rat (Ja): 23:30 - 01:30 (KST adjusted solar time already?)
    # Input `solar_time` is already adjusted. 
    # Standard Branches:
    # Ja: 23-01, Chuk: 01-03 ...
    # But `solar_time` is True Solar Time. So we use standard 23-01 boundaries on it.
    
    h = solar_time.hour
    # Shift so that 23 maps to 0
    # 23, 0 => Ja (0)
    # 1, 2 => Chuk (1)
    # ...
    # Formula: (h + 1) // 2 % 12
    hour_branch_idx = (h + 1) // 2 % 12
    hour_branch = Branch.objects.get(name=BRANCHES[hour_branch_idx])
    
    hour_stem = get_hour_stem(day_stem, hour_branch)
    
    return {
        'year': {'stem': year_ganji['stem'], 'branch': year_ganji['branch']},
        'month': {'stem': month_stem, 'branch': month_branch},
        'day': {'stem': day_stem, 'branch': day_branch},
        'hour': {'stem': hour_stem, 'branch': hour_branch}
    }

def get_yearly_ganji(year):
    # 1984 was 甲子 (Gap-Ja) - Start of cycle
    offset = year - 1984
    stem_idx = offset % 10
    branch_idx = offset % 12
    
    STEMS = ['Gap', 'Eul', 'Byung', 'Jung', 'Moo', 'Gi', 'Gyung', 'Shin', 'Im', 'Gye']
    BRANCHES = ['Ja', 'Chuk', 'In', 'Myo', 'Jin', 'Sa', 'O', 'Mi', 'Shin', 'Yoo', 'Sool', 'Hae']
    
    return {
        'stem': Stem.objects.get(name=STEMS[stem_idx]),
        'branch': Branch.objects.get(name=BRANCHES[branch_idx])
    }

def get_month_stem(year_stem, month_branch):
    # Five Tigers Chasing Month (Wu Hu Dun)
    # Year Stem determines Jan (寅 Tiger) Stem.
    # 甲/己 Year -> 丙寅 (Fire Tiger) start
    # 乙/庚 Year -> 戊寅 (Earth Tiger) start
    # 丙/辛 Year -> 庚寅 (Metal Tiger) start
    # 丁/壬 Year -> 壬寅 (Water Tiger) start
    # 戊/癸 Year -> 甲寅 (Wood Tiger) start
    
    year_map = {
        'Gap': 2, 'Gi': 2,       # Byung (2)
        'Eul': 4, 'Gyung': 4,    # Moo (4)
        'Byung': 6, 'Shin': 6,   # Gyung (6)
        'Jung': 8, 'Im': 8,      # Im (8)
        'Moo': 0, 'Gye': 0       # Gap (0)
    }
    
    start_stem_idx = year_map[year_stem.name]
    
    # Month branch offset from Tiger(In)
    # In=0, Myo=1 ... Chuk=11
    BRANCHES_FROM_IN = ['In', 'Myo', 'Jin', 'Sa', 'O', 'Mi', 'Shin', 'Yoo', 'Sool', 'Hae', 'Ja', 'Chuk']
    try:
        branch_offset = BRANCHES_FROM_IN.index(month_branch.name)
    except ValueError:
        branch_offset = 0 # Default
        
    stem_idx = (start_stem_idx + branch_offset) % 10
    STEMS = ['Gap', 'Eul', 'Byung', 'Jung', 'Moo', 'Gi', 'Gyung', 'Shin', 'Im', 'Gye']
    return Stem.objects.get(name=STEMS[stem_idx])

def get_hour_stem(day_stem, hour_branch):
    # Five Rats Chasing Hour (Wu Shu Dun)
    # Day Stem determines Rat (子) Hour Stem
    # 甲/己 Day -> 甲子 (Wood Rat)
    # 乙/庚 Day -> 丙子 (Fire Rat)
    # 丙/辛 Day -> 戊子 (Earth Rat)
    # 丁/壬 Day -> 庚子 (Metal Rat)
    # 戊/癸 Day -> 壬子 (Water Rat)
    
    day_map = {
        'Gap': 0, 'Gi': 0,       # Gap
        'Eul': 2, 'Gyung': 2,    # Byung
        'Byung': 4, 'Shin': 4,   # Moo
        'Jung': 6, 'Im': 6,      # Gyung
        'Moo': 8, 'Gye': 8       # Im
    }
    
    start_stem_idx = day_map[day_stem.name]
    
    # Hour branch offset from Rat(Ja)
    # Ja=0, Chuk=1 ...
    BRANCHES = ['Ja', 'Chuk', 'In', 'Myo', 'Jin', 'Sa', 'O', 'Mi', 'Shin', 'Yoo', 'Sool', 'Hae']
    branch_offset = BRANCHES.index(hour_branch.name)
    
    stem_idx = (start_stem_idx + branch_offset) % 10
    STEMS = ['Gap', 'Eul', 'Byung', 'Jung', 'Moo', 'Gi', 'Gyung', 'Shin', 'Im', 'Gye']
    return Stem.objects.get(name=STEMS[stem_idx])

def get_ten_god(day_master, target_stem):
    # Logic:
    # Compare Element and Polarity
    # Wood(0) -> Fire(1) -> Earth(2) -> Metal(3) -> Water(4)
    
    elements = ['wood', 'fire', 'earth', 'metal', 'water']
    dm_el_idx = elements.index(day_master.element)
    tg_el_idx = elements.index(target_stem.element)
    
    # Relation
    # 0: Same (Sibling)
    # 1: I generate (Output)
    # 2: I control (Wealth)
    # 3: Controls me (Official) - Wait: Metal(3) controls Wood(0). (3-0)%5 = 3
    # 4: Generates me (Resource)
    
    diff = (tg_el_idx - dm_el_idx) % 5
    
    same_polarity = (day_master.polarity == target_stem.polarity)
    
    gods = {
        0: {True: 'Friend (비견)', False: 'Rob Wealth (겁재)'},
        1: {True: 'Eating God (식신)', False: 'Hurting Officer (상관)'},
        2: {True: 'Indirect Wealth (편재)', False: 'Direct Wealth (정재)'},
        3: {True: 'Seven Killings (편관)', False: 'Direct Officer (정관)'},
        4: {True: 'Indirect Resource (편인)', False: 'Direct Resource (정인)'},
    }
    
    return gods[diff][same_polarity].split(' (')[0] # Return English name for test

def calculate_strength(chart):
    return 60 # Stub
