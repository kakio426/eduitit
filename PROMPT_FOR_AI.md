# Role
You are a Senior Django Developer & UI/UX Specialist. You need to implement the "Multi-School Reservation System" (app name: reservations) following the context below.

# Context & Constraints
- **Project:** Eduitit (Django 4.2+, Tailwind, Alpine.js, HTMX)
- **Style:** Claymorphism (Use `.clay-card`, `.clay-btn` classes standard)
- **Rules:** Follow `CLAUDE.md` and `SERVICE_INTEGRATION_STANDARD.md` strictly.
- **Goal:** Implement Phase 1 ~ Phase 3 sequentially.

# 🛠️ Specific Model Specs (Use this exact structure)
To prevent database changes later, use these field definitions for `reservations/models.py`:

```python
class School(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, allow_unicode=True) # URL key like 'seoul-es'
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    
class SchoolConfig(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE)
    max_periods = models.IntegerField(default=6) # 1~N periods
    reservation_window_days = models.IntegerField(default=14) # How far in future to book
    
class SpecialRoom(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    name = models.CharField(max_length=50) # e.g., 과학실
    icon = models.CharField(max_length=10, default="📍")
    color = models.CharField(max_length=20, default="text-purple-500") # Tailwind class
    equipment_info = models.TextField(blank=True) # e.g., 현미경 15대
    
class Reservation(models.Model):
    room = models.ForeignKey(SpecialRoom, on_delete=models.CASCADE)
    date = models.DateField()
    period = models.IntegerField() # 1~max_periods
    grade = models.IntegerField()
    class_no = models.IntegerField()
    name = models.CharField(max_length=20)
    memo = models.CharField(max_length=100, blank=True) # 한 줄 메모
    created_at = models.DateTimeField(auto_now_add=True)
    # Add unique constraint for (room, date, period)

class RecurringSchedule(models.Model):
    room = models.ForeignKey(SpecialRoom, on_delete=models.CASCADE)
    day_of_week = models.IntegerField() # 0(Mon)~6(Sun)
    period = models.IntegerField()
    name = models.CharField(max_length=50) # e.g., "6-1 고정수업"

class BlackoutDate(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=50)
```

# 🎨 UI Implementation Instructions (MANDATORY)
You MUST implement the UI based on the attached HTML prototype below.
- **Hybrid Layout:** Use `hidden lg:block` to switch between Timeline (PC) and Card List (Mobile).
- **HTMX:** The timetable area must be refreshable via HTMX polling (every 30s).
- **Claymorphism:** Keep the exact look & feel (`clay-card`, shadows).
- **Navigation:** Ensure `pt-32` padding at top for NavBar.

# [ATTACHMENT] UI Prototype HTML Code
(Use this code as your base template for `reservations/index.html`)

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <style>
        /* Claymorphism Base */
        .clay-card {
            background-color: #E0E5EC;
            border-radius: 1.5rem;
            box-shadow: 8px 8px 16px #a3b1c6, -8px -8px 16px #ffffff;
            border: 1px solid rgba(255,255,255,0.4);
            /* Mobile overflow fix */
            max-width: 100%;
            overflow: hidden; 
        }
        @media (max-width: 768px) {
             .clay-card { box-shadow: 0 4px 12px rgba(163, 177, 198, 0.4), 0 -2px 8px rgba(255, 255, 255, 0.6); }
        }
        .clay-btn {
            background-color: #E0E5EC;
            border-radius: 0.75rem;
            box-shadow: 5px 5px 10px #a3b1c6, -5px -5px 10px #ffffff;
            transition: all 0.2s ease;
        }
        .clay-btn:active {
            box-shadow: inset 5px 5px 10px #a3b1c6, inset -5px -5px 10px #ffffff;
        }
        .clay-btn-primary {
            background-color: #8B5CF6; /* Purple-500 */
            color: white;
            box-shadow: 5px 5px 10px #764ccf, -5px -5px 10px #a06cff;
        }
    </style>
</head>
<body class="bg-[#E0E5EC] text-gray-700">

    <!-- CONCEPT A: PC Timeline View (Desktop Only) -->
    <div class="hidden lg:block clay-card p-6 overflow-x-auto mb-8">
        <div class="min-w-[800px]">
            <!-- Header Row -->
            <div class="grid grid-cols-9 gap-2 mb-4 text-center font-bold text-gray-600">
                <div class="text-left pl-2">장소</div>
                <div>1교시</div>
                <div>2교시</div>
                <div>3교시</div>
                <div>4교시</div>
                <div>5교시</div>
                <div>6교시</div>
                <div>7교시</div>
                <div>방과후</div>
            </div>

            <!-- Row 1: 과학실 -->
            <div class="grid grid-cols-9 gap-2 mb-3 items-center">
                <div class="font-bold text-gray-700 pl-2">🧬 과학실</div>
                
                <!-- Fixed Class -->
                <div class="bg-gray-200 text-gray-500 rounded-lg p-2 text-xs flex flex-col items-center justify-center h-14 shadow-inner">
                    <i class="fas fa-lock mb-1"></i>
                    <span>6-1 (고정)</span>
                </div>
                
                <!-- Available -->
                <button class="clay-btn h-14 flex items-center justify-center text-purple-500 hover:text-purple-700 group">
                    <i class="fas fa-plus text-lg group-hover:scale-110 transition-transform"></i>
                </button>
                
                <!-- User Reservation -->
                <div class="bg-purple-100 border border-purple-200 text-purple-700 rounded-lg p-2 text-xs flex flex-col items-center justify-center h-14 relative group">
                    <span class="font-bold">5-2 김교사</span>
                    <span class="text-[10px] text-gray-500">실험</span>
                </div>
            </div>
        </div>
    </div>

    <!-- CONCEPT B: Mobile Card List View (Mobile Only) -->
    <div class="block lg:hidden space-y-4">
        <!-- Date Selector -->
        <div class="clay-card p-4 flex justify-between items-center">
            <h3 class="font-bold text-lg">📅 2026.02.12 (목)</h3>
            <button class="clay-btn w-8 h-8 flex items-center justify-center"><i class="fas fa-chevron-right"></i></button>
        </div>

        <!-- Room Tabs -->
        <div class="flex gap-2 overflow-x-auto pb-2">
            <button class="clay-btn-primary px-4 py-2 rounded-full whitespace-nowrap text-sm font-bold shadow-inner">🧬 과학실</button>
            <button class="clay-btn px-4 py-2 rounded-full whitespace-nowrap text-sm text-gray-500">💻 컴퓨터실</button>
        </div>

        <!-- Slots List -->
        <div class="clay-card p-4 space-y-3">
            <!-- Slot: Fixed -->
            <div class="flex items-center gap-3 p-3 bg-gray-100 rounded-xl border border-gray-200 opacity-70">
                <div class="w-12 text-center">
                    <span class="block text-sm font-bold text-gray-600">1교시</span>
                </div>
                <div class="flex-1 border-l-2 border-gray-300 pl-3">
                    <span class="text-sm font-bold text-gray-500"><i class="fas fa-lock mr-1"></i> 6-1 (고정)</span>
                </div>
            </div>

            <!-- Slot: Available -->
            <div class="flex items-center gap-3 p-3 clay-btn group cursor-pointer">
                <div class="w-12 text-center">
                    <span class="block text-sm font-bold text-gray-700">2교시</span>
                </div>
                <div class="flex-1 border-l-2 border-gray-200 pl-3 flex justify-between items-center">
                    <span class="text-sm text-gray-400 group-hover:text-purple-500">예약 가능</span>
                    <span class="bg-purple-100 text-purple-600 text-xs px-2 py-1 rounded-full"><i class="fas fa-plus mr-1"></i>예약</span>
                </div>
            </div>
        </div>
    </div>

</body>
</html>
```
