/**
 * DutyTicker Logic Manager (Premium V3 - Correct Path)
 * Fixed: Pathing issue where JS was in wrong static folder.
 * Fixed: Modal flex/hidden logic.
 * Fixed: Timer initialization.
 */
class DutyTickerManager {
    constructor() {
        this.api = window.dtApiEndpoints || {};
        this.roles = [];
        this.students = [];
        this.todaySchedule = [];
        this.isBroadcasting = false;
        this.broadcastMessage = '';
        this.isSoundEnabled = localStorage.getItem('dt-broadcast-sound') !== 'false';
        this.selectedRoleId = null;
        this.pendingConflict = null;
        this.spotlightStudentId = null;
        this.callModeIndex = 0;
        this.callModeRoles = [];
        this.callModeAutoTimer = null;
        this.callModeAutoPlaying = false;
        this.boundGlobalKeydown = null;

        this.timerSeconds = 300;
        this.timerMaxSeconds = 300;
        this.isTimerRunning = false;
        this.timerInterval = null;
        this.timerEndAt = null;
        this.timerStorageKey = 'dt-focus-timer-state-v1';
        this.audioCtx = null;
    }

    init() {
        console.log("DutyTicker: Initializing...");
        this.loadData();
        this.setupEventListeners();
        this.restoreTimerState();
        this.updateTimerDisplay();
        this.updateSoundUI();
        this.bindGlobalShortcuts();

        // Anti-cache check
        console.log("DutyTicker V3 Loaded and Ready");
    }

    setupEventListeners() {
        const broadcastSubmit = document.getElementById('broadcastSubmitBtn');
        if (broadcastSubmit) broadcastSubmit.onclick = () => this.handleStartBroadcast();

        const broadcastCancel = document.getElementById('broadcastCancelBtn');
        if (broadcastCancel) broadcastCancel.onclick = () => this.closeBroadcastModal();

        const customTimerInput = document.getElementById('customTimerMinutesInput');
        if (customTimerInput) {
            customTimerInput.value = String(Math.max(1, Math.round(this.timerMaxSeconds / 60)));
            customTimerInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    this.applyCustomTimerMinutes();
                }
            });
        }

        // Ensure timer display is correct on start
        this.updateTimerDisplay();
    }

    bindGlobalShortcuts() {
        if (this.boundGlobalKeydown) return;
        this.boundGlobalKeydown = (event) => {
            const callModal = document.getElementById('callModeModal');
            const isCallModeOpen = !!callModal && !callModal.classList.contains('hidden');
            if (!isCallModeOpen) return;

            if (event.key === 'ArrowRight') {
                event.preventDefault();
                this.nextCallRole();
            } else if (event.key === 'ArrowLeft') {
                event.preventDefault();
                this.prevCallRole();
            } else if (event.key === 'Escape') {
                event.preventDefault();
                this.closeCallMode();
            }
        };
        document.addEventListener('keydown', this.boundGlobalKeydown);
    }

    // --- CSRF Helper ---
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    async secureFetch(url, options = {}) {
        const csrftoken = this.getCookie('csrftoken');
        if (!options.headers) options.headers = {};
        if (csrftoken) options.headers['X-CSRFToken'] = csrftoken;
        if (options.body && !options.headers['Content-Type']) {
            options.headers['Content-Type'] = 'application/json;charset=UTF-8';
        }
        return fetch(url, options);
    }

    async parseJsonResponse(response, fallbackMessage = '요청을 처리하지 못했습니다.') {
        let payload = null;
        try {
            payload = await response.json();
        } catch (_error) {
            payload = null;
        }

        if (!response.ok) {
            const reason = payload?.error || payload?.message || fallbackMessage;
            throw new Error(reason);
        }

        if (payload && payload.success === false) {
            throw new Error(payload.error || fallbackMessage);
        }

        return payload || {};
    }

    getApiUrl(key, fallback = '') {
        return this.api[key] || fallback;
    }

    buildTemplateUrl(templateValue, idValue) {
        const template = String(templateValue || '');
        if (!template) return '';
        return template.replace('999999', encodeURIComponent(String(idValue)));
    }

    getToggleMissionUrl(studentId) {
        return this.buildTemplateUrl(
            this.getApiUrl('toggleMissionUrlTemplate', '/products/dutyticker/api/student/999999/toggle_mission/'),
            studentId
        );
    }

    getToggleAssignmentUrl(assignmentId) {
        return this.buildTemplateUrl(
            this.getApiUrl('toggleAssignmentUrlTemplate', '/products/dutyticker/api/assignment/999999/toggle/'),
            assignmentId
        );
    }

    // --- Safety / State Helpers ---
    escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => {
            switch (char) {
                case '&': return '&amp;';
                case '<': return '&lt;';
                case '>': return '&gt;';
                case '"': return '&quot;';
                case "'": return '&#39;';
                default: return char;
            }
        });
    }

    normalizeTimerSeconds(value, fallback = 300) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return fallback;
        const floored = Math.floor(numeric);
        if (floored < 1) return fallback;
        return Math.min(floored, 59940);
    }

    saveTimerState() {
        try {
            const safeMax = this.normalizeTimerSeconds(this.timerMaxSeconds, 300);
            const safeSeconds = Math.min(this.normalizeTimerSeconds(this.timerSeconds, safeMax), safeMax);
            const timerEndAt = this.isTimerRunning
                ? (Number.isFinite(this.timerEndAt) ? this.timerEndAt : Date.now() + (safeSeconds * 1000))
                : null;

            localStorage.setItem(this.timerStorageKey, JSON.stringify({
                timerSeconds: safeSeconds,
                timerMaxSeconds: safeMax,
                isTimerRunning: this.isTimerRunning,
                timerEndAt,
            }));
        } catch (error) {
            console.warn('DutyTicker: failed to save timer state', error);
        }
    }

    restoreTimerState() {
        try {
            const raw = localStorage.getItem(this.timerStorageKey);
            if (!raw) return;

            const parsed = JSON.parse(raw);
            const restoredMax = this.normalizeTimerSeconds(parsed.timerMaxSeconds, 300);
            const restoredSeconds = Math.min(this.normalizeTimerSeconds(parsed.timerSeconds, restoredMax), restoredMax);
            const now = Date.now();
            const restoredEndAt = Number(parsed.timerEndAt);
            const shouldResume = parsed.isTimerRunning === true && Number.isFinite(restoredEndAt) && restoredEndAt > now;

            this.timerMaxSeconds = restoredMax;

            if (shouldResume) {
                this.timerEndAt = restoredEndAt;
                this.timerSeconds = Math.max(1, Math.ceil((restoredEndAt - now) / 1000));
                this.isTimerRunning = true;
                this.startTimerTicker();
            } else {
                this.timerSeconds = restoredSeconds;
                this.timerEndAt = null;
                this.isTimerRunning = false;
            }

            this.syncCustomTimerInput();
        } catch (error) {
            console.warn('DutyTicker: failed to restore timer state', error);
        }
    }

    startTimerTicker() {
        if (this.timerInterval) clearInterval(this.timerInterval);
        this.timerInterval = setInterval(() => this.handleTimerTick(), 250);
    }

    stopTimerTicker() {
        if (this.timerInterval) clearInterval(this.timerInterval);
        this.timerInterval = null;
    }

    // --- Data ---
    async loadData() {
        try {
            const response = await fetch(this.getApiUrl('dataUrl', '/products/dutyticker/api/data/'));
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || '데이터를 불러오지 못했습니다.');
            }

            this.roles = data.roles.map(role => {
                const assignment = data.assignments.find(a => a.role_id === role.id);
                return {
                    id: role.id,
                    name: role.name,
                    timeSlot: role.time_slot,
                    assignee: assignment ? assignment.student_name : '미배정',
                    assigneeId: assignment ? assignment.student_id : null,
                    status: assignment && assignment.is_completed ? 'completed' : 'pending',
                    assignmentId: assignment ? assignment.id : null,
                };
            });

            this.students = data.students.map(s => ({
                id: s.id,
                name: s.name,
                number: s.number,
                status: s.is_mission_completed ? 'done' : 'pending'
            }));

            this.broadcastMessage = data.settings.last_broadcast || '';
            this.isBroadcasting = !!this.broadcastMessage;
            this.missionTitle = data.settings.mission_title || "수학 익힘책 풀기";
            this.missionDesc = data.settings.mission_desc || "24~25페이지 풀고 채점하기";
            this.spotlightStudentId = Number(data.settings.spotlight_student_id) || null;
            this.theme = data.settings.theme || 'deep_space';

            // Apply Theme to DOM
            document.documentElement.setAttribute('data-theme', this.theme);

            const today = new Date().getDay();
            this.todaySchedule = data.schedule[today] || [];

            this.renderAll();
        } catch (error) {
            console.error("Fetch Error:", error);
            this.renderLoadFailure();
        }
    }

    renderLoadFailure() {
        const roleContainer = document.getElementById('mainRoleList');
        if (roleContainer) {
            roleContainer.innerHTML = `
                <div class="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-center">
                    <p class="text-sm font-bold text-rose-200">역할 데이터를 불러오지 못했습니다.</p>
                    <button type="button" onclick="window.dtApp.loadData()" class="mt-3 px-4 py-2 rounded-xl bg-rose-500/80 hover:bg-rose-400 text-white text-sm font-bold transition">
                        다시 시도
                    </button>
                </div>
            `;
        }

        const studentContainer = document.getElementById('mainStudentGrid');
        if (studentContainer) {
            studentContainer.innerHTML = `
                <div class="col-span-full rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-center">
                    <p class="text-sm font-bold text-rose-200">학생 데이터를 불러오지 못했습니다.</p>
                    <button type="button" onclick="window.dtApp.loadData()" class="mt-3 px-4 py-2 rounded-xl bg-rose-500/80 hover:bg-rose-400 text-white text-sm font-bold transition">
                        다시 시도
                    </button>
                </div>
            `;
        }
    }

    renderAll() {
        this.renderSchedule();
        this.renderMission();
        this.renderRoleList();
        this.renderStudentGrid();
        this.renderNotices();
        const callModal = document.getElementById('callModeModal');
        const isCallModeOpen = !!callModal && !callModal.classList.contains('hidden');
        if (isCallModeOpen) this.renderCallMode();
    }

    renderSchedule() {
        const container = document.getElementById('headerScheduleStrip');
        if (!container) return;

        const periodSchedule = this.todaySchedule
            .filter((slot) => slot && slot.slot_type === 'period')
            .sort((a, b) => Number(a?.period || 0) - Number(b?.period || 0));

        if (periodSchedule.length === 0) {
            container.innerHTML = '<span class="text-slate-500 text-[11px] font-bold px-1 opacity-70">오늘 시간표 없음</span>';
            return;
        }

        container.innerHTML = periodSchedule.map((slot) => {
            const periodNumber = Number(slot.period);
            const periodLabel = Number.isFinite(periodNumber) && periodNumber > 0
                ? `${periodNumber}교시`
                : String(slot.slot_label || '');
            const rawSubject = String(slot.name || '').trim();
            const subjectName = rawSubject && rawSubject !== periodLabel ? rawSubject : '미정';

            return `
                <span class="text-[11px] xl:text-xs font-bold text-slate-100/90 whitespace-nowrap">
                    <span class="text-indigo-300">${this.escapeHtml(periodLabel)}</span><span class="text-slate-500 mx-0.5">:</span><span class="text-slate-200">${this.escapeHtml(subjectName)}</span>
                </span>
            `;
        }).join('');
    }

    renderMission() {
        const titleEl = document.getElementById('mainMissionTitle');
        const descEl = document.getElementById('mainMissionDesc');
        if (titleEl) titleEl.textContent = this.missionTitle;
        if (descEl) descEl.textContent = this.missionDesc;
    }

    renderRoleList() {
        const container = document.getElementById('mainRoleList');
        if (!container) return;

        if (!this.roles.length) {
            container.innerHTML = `
                <div class="rounded-2xl border border-slate-700 bg-slate-800/50 p-5 text-center">
                    <p class="text-sm font-bold text-slate-300">등록된 역할이 없습니다.</p>
                    <a href="/products/dutyticker/admin/" class="inline-flex mt-3 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold transition">
                        설정에서 역할 추가
                    </a>
                </div>
            `;
            return;
        }

        const roleIcons = {
            '칠판 지우기': 'fa-solid fa-broom',
            '우유': 'fa-solid fa-glass-water',
            '불 끄기': 'fa-solid fa-lightbulb',
            '컴퓨터': 'fa-solid fa-laptop',
            '식물': 'fa-solid fa-leaf'
        };

        const spotlightStudentId = Number(this.spotlightStudentId);
        const spotlightRoleIds = this.roles
            .filter((role) => Number(role.assigneeId) === spotlightStudentId)
            .map((role) => Number(role.id));

        const orderedRoles = [...this.roles].sort((a, b) => {
            const aSpot = spotlightRoleIds.includes(Number(a.id)) ? 0 : 1;
            const bSpot = spotlightRoleIds.includes(Number(b.id)) ? 0 : 1;
            if (aSpot !== bSpot) return aSpot - bSpot;
            if (a.status !== b.status) return a.status === 'completed' ? 1 : -1;
            return Number(a.id) - Number(b.id);
        });

        container.innerHTML = orderedRoles.map(role => {
            const iconClass = roleIcons[role.name] || 'fa-solid fa-circle-user';
            const isCompleted = role.status === 'completed';
            const roleId = Number.isFinite(Number(role.id)) ? Number(role.id) : 0;
            const safeTimeSlot = this.escapeHtml(role.timeSlot || 'TASK');
            const safeRoleName = this.escapeHtml(role.name);
            const safeAssignee = this.escapeHtml(role.assignee || '미배정');
            const numericRoleId = Number(role.id);
            const isSpotlightRole = spotlightRoleIds.includes(numericRoleId);
            const spotlightClass = isSpotlightRole ? 'dt-role-current-spotlight' : '';
            const spotlightBadge = isSpotlightRole
                ? '<span class="ml-2 inline-flex items-center px-2 py-0.5 rounded-lg text-[10px] font-black bg-indigo-500/30 text-indigo-100 border border-indigo-300/40">집중</span>'
                : '';
            return `
                <div class="flex items-center p-4 bg-slate-800/30 backdrop-blur-md rounded-[1.5rem] border border-white/5 hover:bg-slate-700/40 transition-all cursor-pointer group shadow-lg ${spotlightClass}"
                    onclick="window.dtApp.openStudentModal(${roleId})">
                    <div class="w-14 h-14 bg-slate-900/60 rounded-2xl flex items-center justify-center border border-white/5 group-hover:border-indigo-500/50 transition-all">
                        <i class="${iconClass} text-2xl ${isCompleted ? 'text-emerald-400' : 'text-slate-400 group-hover:text-indigo-400'}"></i>
                    </div>
                    <div class="flex-1 ml-5">
                        <div class="flex justify-between items-center mb-1">
                            <p class="text-[10px] text-slate-500 font-extrabold tracking-[0.2em]">${safeTimeSlot}</p>
                            ${isCompleted ? '<span class="text-emerald-400 text-[10px] font-black uppercase"><i class="fa-solid fa-check-circle"></i> DONE</span>' : ''}
                        </div>
                        <div class="flex justify-between items-center text-xl font-black text-slate-100">
                             <p class="${isCompleted ? 'opacity-30 line-through' : ''}">${safeRoleName}${spotlightBadge}</p>
                              <div class="text-sm text-indigo-300 bg-indigo-500/10 px-3 py-1.5 rounded-xl border border-indigo-500/20">${safeAssignee}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderStudentGrid() {
        const container = document.getElementById('mainStudentGrid');
        if (!container) return;

        if (!this.students.length) {
            container.innerHTML = `
                <div class="col-span-full rounded-2xl border border-slate-700 bg-slate-800/50 p-5 text-center">
                    <p class="text-sm font-bold text-slate-300">등록된 학생이 없습니다.</p>
                    <a href="/products/dutyticker/admin/" class="inline-flex mt-3 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold transition">
                        설정에서 학생 추가
                    </a>
                </div>
            `;
            this.updateProgress();
            return;
        }

        container.innerHTML = this.students.map(student => {
            const isDone = student.status === 'done';
            const studentId = Number.isFinite(Number(student.id)) ? Number(student.id) : 0;
            const safeStudentNumber = this.escapeHtml(student.number);
            const safeStudentName = this.escapeHtml(student.name);
            const isSpotlight = Number(this.spotlightStudentId) === Number(student.id);
            return `
                <div class="relative p-2 rounded-2xl border border-slate-700 bg-slate-800/50 flex flex-col items-center gap-1 cursor-pointer transition group ${isDone ? 'border-emerald-500/50 bg-emerald-500/10' : ''} ${isSpotlight ? 'ring-2 ring-indigo-400 bg-indigo-500/10' : ''}"
                    onclick="window.dtApp.handleStudentStatusToggle(${studentId})">
                    <button
                        type="button"
                        onclick="event.stopPropagation(); window.dtApp.toggleSpotlightStudent(${studentId})"
                        class="absolute top-1 right-1 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black transition ${isSpotlight ? 'bg-indigo-500 text-white' : 'bg-slate-700 text-slate-300 hover:bg-indigo-500 hover:text-white'}"
                        title="${isSpotlight ? '반짝임 해제' : '반짝이기'}"
                    >
                        <i class="fa-solid fa-sparkles"></i>
                    </button>
                    <div class="w-9 h-9 rounded-full flex items-center justify-center text-sm font-black transition-all ${isDone ? 'bg-emerald-500 text-slate-900' : 'bg-slate-700 text-slate-300 group-hover:bg-indigo-500'}">
                        ${safeStudentNumber}
                    </div>
                    <span class="text-xs font-bold ${isDone ? 'text-emerald-400' : 'text-slate-400'} ${isSpotlight ? 'text-indigo-200' : ''}">${safeStudentName}</span>
                </div>
            `;
        }).join('');
        this.updateProgress();
    }

    renderNotices() {
        const textEl = document.getElementById('dashboardBroadcastText');
        const titleEl = document.getElementById('noticeTitleDisplay');
        if (!textEl || !titleEl) return;

        if (this.isBroadcasting && this.broadcastMessage) {
            titleEl.innerHTML = '<i class="fa-solid fa-bell text-yellow-500"></i> 알림사항';
            textEl.textContent = this.broadcastMessage;
            textEl.classList.add('text-yellow-100');
        } else {
            titleEl.innerHTML = '<i class="fa-regular fa-bell text-slate-500"></i> 알림사항 없음';
            textEl.textContent = "클릭해서 아이들에게 전달할 공지사항이나 준비물을 입력하세요.";
            textEl.classList.remove('text-yellow-100');
        }
    }

    updateProgress() {
        const total = this.students.length;
        const bar = document.getElementById('missionProgressBar');
        const text = document.getElementById('missionProgressText');
        if (total === 0) {
            if (bar) bar.style.width = '0%';
            if (text) text.textContent = '0%';
            return;
        }
        const done = this.students.filter(s => s.status === 'done').length;
        const percent = Math.round((done / total) * 100);
        if (bar) bar.style.width = `${percent}%`;
        if (text) text.textContent = `${percent}%`;
    }

    // --- Actions ---
    async handleStudentStatusToggle(studentId) {
        const student = this.students.find(s => s.id === studentId);
        if (!student) return;

        const original = student.status;
        student.status = student.status === 'done' ? 'pending' : 'done';
        this.renderStudentGrid();

        if (student.status === 'done') this.playSuccessSound();

        try {
            const response = await this.secureFetch(this.getToggleMissionUrl(studentId), { method: 'POST' });
            await this.parseJsonResponse(response, '학생 미션 상태를 바꾸지 못했습니다.');
        } catch (e) {
            console.error(e);
            student.status = original;
            this.renderStudentGrid();
        }
    }

    async toggleSpotlightStudent(studentId) {
        const nextStudentId = Number(this.spotlightStudentId) === Number(studentId) ? null : Number(studentId);
        const prevStudentId = this.spotlightStudentId;

        this.spotlightStudentId = nextStudentId;
        this.renderStudentGrid();
        this.renderRoleList();

        const callModal = document.getElementById('callModeModal');
        if (callModal && !callModal.classList.contains('hidden')) {
            this.renderCallMode();
        }

        try {
            const response = await this.secureFetch(this.getApiUrl('spotlightUrl', '/products/dutyticker/api/spotlight/update/'), {
                method: 'POST',
                body: JSON.stringify({ student_id: nextStudentId }),
            });
            const payload = await this.parseJsonResponse(response, '반짝임 학생 저장에 실패했습니다.');
            this.spotlightStudentId = Number(payload.spotlight_student_id) || null;
            this.renderStudentGrid();
            this.renderRoleList();
        } catch (error) {
            console.error(error);
            this.spotlightStudentId = prevStudentId;
            this.renderStudentGrid();
            this.renderRoleList();
        }
    }

    // --- Timer ---
    toggleTimer() {
        console.log("Timer Toggled");
        if (this.isTimerRunning) this.pauseTimer();
        else this.startTimer();
    }

    handleTimerTick() {
        if (!this.isTimerRunning || !this.timerEndAt) return;
        const remaining = Math.max(0, Math.ceil((this.timerEndAt - Date.now()) / 1000));

        if (remaining !== this.timerSeconds) {
            this.timerSeconds = remaining;
            this.updateTimerDisplay();
            this.saveTimerState();
        }

        if (remaining === 0) {
            this.pauseTimer();
            this.playAlert();
        }
    }

    startTimer() {
        if (this.isTimerRunning) return;

        if (this.timerSeconds <= 0) {
            this.timerSeconds = this.timerMaxSeconds > 0 ? this.timerMaxSeconds : 60;
        }

        this.isTimerRunning = true;
        this.timerEndAt = Date.now() + (this.timerSeconds * 1000);
        this.resumeAudioContext();
        this.updateTimerDisplay();
        this.saveTimerState();

        this.startTimerTicker();
    }

    pauseTimer() {
        if (this.isTimerRunning && this.timerEndAt) {
            this.timerSeconds = Math.max(0, Math.ceil((this.timerEndAt - Date.now()) / 1000));
        }

        this.isTimerRunning = false;
        this.stopTimerTicker();
        this.timerEndAt = null;
        this.updateTimerDisplay();
        this.saveTimerState();
    }

    resetTimer() {
        this.pauseTimer();
        this.timerSeconds = this.timerMaxSeconds;
        this.syncCustomTimerInput();
        this.updateTimerDisplay();
        this.saveTimerState();
    }

    addTimerMinutes(minutes = 1) {
        const minuteValue = Number(minutes);
        if (!Number.isFinite(minuteValue) || minuteValue <= 0) return;

        const nextSeconds = this.timerSeconds + (Math.floor(minuteValue) * 60);
        const clampedSeconds = Math.min(nextSeconds, 59940);

        this.timerSeconds = clampedSeconds;
        this.timerMaxSeconds = clampedSeconds;

        if (this.isTimerRunning) {
            this.timerEndAt = Date.now() + (this.timerSeconds * 1000);
        }

        this.syncCustomTimerInput();
        this.updateTimerDisplay();
        this.saveTimerState();
    }

    applyCustomTimerMinutes() {
        const input = document.getElementById('customTimerMinutesInput');
        if (!input) return;

        const rawValue = Number(input.value);
        if (!Number.isFinite(rawValue)) return;

        const minutes = Math.min(999, Math.max(1, Math.floor(rawValue)));
        input.value = String(minutes);
        this.setTimerMode(minutes * 60, true);
    }

    setTimerMode(sec, autoStart = false) {
        const normalizedSec = Number(sec);
        if (!Number.isFinite(normalizedSec) || normalizedSec <= 0) return;
        const safeSeconds = this.normalizeTimerSeconds(normalizedSec, this.timerMaxSeconds || 300);

        this.pauseTimer();
        this.timerMaxSeconds = safeSeconds;
        this.timerSeconds = this.timerMaxSeconds;
        this.syncCustomTimerInput();
        this.updateTimerDisplay();
        this.saveTimerState();

        if (autoStart) this.startTimer();
    }

    syncCustomTimerInput() {
        const input = document.getElementById('customTimerMinutesInput');
        if (!input) return;
        const mins = Math.min(999, Math.max(1, Math.round(this.timerMaxSeconds / 60)));
        input.value = String(mins);
    }

    updateTimerDisplay() {
        const m = Math.floor(this.timerSeconds / 60);
        const s = this.timerSeconds % 60;
        const text = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        const display = document.getElementById('mainTimerDisplay');
        if (display) {
            display.textContent = text;
            display.setAttribute('aria-pressed', this.isTimerRunning ? 'true' : 'false');
            display.setAttribute('aria-label', this.isTimerRunning ? `타이머 일시정지 (${text})` : `타이머 시작 (${text})`);
            if (this.isTimerRunning) {
                display.classList.add('text-yellow-400', 'scale-105');
                display.classList.remove('text-white');
            } else {
                display.classList.remove('text-yellow-400', 'scale-105');
                display.classList.add('text-white');
            }
        }
    }

    // --- Modals ---
    openModal(id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        setTimeout(() => modal.classList.add('opacity-100'), 10);
    }

    closeModal(id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        modal.classList.remove('opacity-100');
        setTimeout(() => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }, 300);
    }

    openStudentModal(roleId) {
        this.selectedRoleId = roleId;
        const role = this.roles.find(r => r.id === roleId);
        if (!role) return;

        const titleEl = document.getElementById('studentModalTitle');
        const listEl = document.getElementById('studentListGrid');
        if (titleEl) titleEl.textContent = `'${role.name}' 담당자`;
        if (listEl) {
            const selectedAssigneeId = Number(role.assigneeId);
            listEl.innerHTML = this.students.map(s => `
            <button onclick="window.dtApp.assignStudent(${Number.isFinite(Number(s.id)) ? Number(s.id) : 0})" 
                class="p-4 bg-slate-700/50 border border-slate-600 rounded-xl font-bold ${selectedAssigneeId === Number(s.id) ? 'ring-2 ring-indigo-500 bg-indigo-900/50' : ''}">
                <span class="text-xs opacity-50">${this.escapeHtml(s.number)}번</span><br>${this.escapeHtml(s.name)}
            </button>
        `).join('');
        }

        const roleToggleBtn = document.getElementById('toggleRoleStatusBtn');
        if (roleToggleBtn) {
            roleToggleBtn.onclick = () => this.toggleSelectedRoleStatus();
        }
        this.openModal('studentModal');
    }

    closeStudentModal() {
        this.closeModal('studentModal');
    }

    async assignRoleRequest(roleId, studentId) {
        const response = await this.secureFetch(this.getApiUrl('assignUrl', '/products/dutyticker/api/assign/'), {
            method: 'POST',
            body: JSON.stringify({ role_id: roleId, student_id: studentId })
        });
        return this.parseJsonResponse(response, '역할 배정을 저장하지 못했습니다.');
    }

    openConflictModal(conflict) {
        this.pendingConflict = conflict;
        const studentEl = document.getElementById('conflictStudentName');
        const fromRoleEl = document.getElementById('conflictFromRole');
        const toRoleEl = document.getElementById('conflictToRole');
        if (studentEl) studentEl.textContent = conflict.studentName;
        if (fromRoleEl) fromRoleEl.textContent = conflict.fromRoleName;
        if (toRoleEl) toRoleEl.textContent = conflict.toRoleName;
        this.openModal('assignmentConflictModal');
    }

    closeConflictModal() {
        this.pendingConflict = null;
        this.closeModal('assignmentConflictModal');
    }

    async resolveConflict(action) {
        const conflict = this.pendingConflict;
        if (!conflict) return;
        this.closeConflictModal();
        this.closeStudentModal();
        try {
            if (action === 'swap') {
                await this.assignRoleRequest(conflict.toRoleId, conflict.studentId);
                await this.assignRoleRequest(conflict.fromRoleId, conflict.toRolePreviousStudentId || null);
            } else if (action === 'move') {
                await this.assignRoleRequest(conflict.fromRoleId, null);
                await this.assignRoleRequest(conflict.toRoleId, conflict.studentId);
            } else {
                return;
            }
            this.loadData();
        } catch (error) {
            console.error(error);
            this.loadData();
        }
    }

    async assignStudent(studentId) {
        if (!this.selectedRoleId) return;
        const targetRole = this.roles.find(r => Number(r.id) === Number(this.selectedRoleId));
        if (!targetRole) return;

        const conflictingRole = this.roles.find(
            (role) => Number(role.id) !== Number(this.selectedRoleId) && Number(role.assigneeId) === Number(studentId)
        );

        if (conflictingRole) {
            this.openConflictModal({
                studentId: Number(studentId),
                studentName: conflictingRole.assignee || '담당 학생',
                fromRoleId: Number(conflictingRole.id),
                fromRoleName: conflictingRole.name,
                toRoleId: Number(targetRole.id),
                toRoleName: targetRole.name,
                toRolePreviousStudentId: targetRole.assigneeId ? Number(targetRole.assigneeId) : null,
            });
            return;
        }

        try {
            await this.assignRoleRequest(this.selectedRoleId, studentId);
            this.loadData();
            this.closeStudentModal();
        } catch (e) { console.error(e); }
    }

    async toggleSelectedRoleStatus() {
        if (!this.selectedRoleId) return;
        const role = this.roles.find(r => r.id === this.selectedRoleId);
        if (!role || !role.assignmentId) {
            this.closeStudentModal();
            return;
        }

        const nextStatus = role.status !== 'completed';
        role.status = nextStatus ? 'completed' : 'pending';
        this.renderRoleList();
        this.closeStudentModal();

        try {
            const response = await this.secureFetch(this.getToggleAssignmentUrl(role.assignmentId), {
                method: 'POST',
                body: JSON.stringify({ is_completed: nextStatus })
            });
            await this.parseJsonResponse(response, '역할 완료 상태를 저장하지 못했습니다.');
            this.loadData();
        } catch (error) {
            console.error(error);
            this.loadData();
        }
    }

    syncCallModeRoles() {
        const previousRoleId = this.callModeRoles[this.callModeIndex]?.id;
        this.callModeRoles = this.roles.filter((role) => Number(role.assigneeId));

        if (!this.callModeRoles.length) {
            this.callModeIndex = 0;
            return;
        }

        if (Number(previousRoleId)) {
            const previousIndex = this.callModeRoles.findIndex((role) => Number(role.id) === Number(previousRoleId));
            if (previousIndex >= 0) {
                this.callModeIndex = previousIndex;
                return;
            }
        }

        if (this.callModeIndex >= this.callModeRoles.length) {
            this.callModeIndex = 0;
        }
    }

    flashCallModeCard() {
        const card = document.getElementById('callModeFocusCard');
        if (!card || typeof card.animate !== 'function') return;
        card.animate(
            [
                { transform: 'scale(0.985)', filter: 'brightness(0.92)' },
                { transform: 'scale(1.015)', filter: 'brightness(1.1)' },
                { transform: 'scale(1)', filter: 'brightness(1)' },
            ],
            { duration: 620, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' }
        );
    }

    openCallMode() {
        this.syncCallModeRoles();
        const spotlightStudentId = Number(this.spotlightStudentId);
        const spotlightIndex = this.callModeRoles.findIndex((role) => Number(role.assigneeId) === spotlightStudentId);

        if (spotlightIndex >= 0) this.callModeIndex = spotlightIndex;

        this.callModeAutoPlaying = this.callModeRoles.length > 1;
        this.openModal('callModeModal');
        this.renderCallMode();
        if (this.callModeAutoPlaying) this.startCallModeAuto();
        else this.stopCallModeAuto();
        if (this.callModeRoles.length) this.playCallChime();
    }

    closeCallMode() {
        this.stopCallModeAuto();
        this.callModeAutoPlaying = false;
        this.closeModal('callModeModal');
    }

    renderCallMode() {
        this.syncCallModeRoles();

        const timeSlotEl = document.getElementById('callModeTimeSlot');
        const roleNameEl = document.getElementById('callModeRoleName');
        const studentNameEl = document.getElementById('callModeStudentName');
        const indexTextEl = document.getElementById('callModeIndexText');
        const autoBtn = document.getElementById('callModeAutoBtn');

        if (!this.callModeRoles.length) {
            if (timeSlotEl) timeSlotEl.textContent = '배정 필요';
            if (roleNameEl) roleNameEl.textContent = '배정된 역할이 없습니다';
            if (studentNameEl) studentNameEl.textContent = '설정 화면에서 먼저 역할을 배정하세요';
            if (indexTextEl) indexTextEl.textContent = '0 / 0';
            if (autoBtn) {
                autoBtn.textContent = '자동 재생 불가';
                autoBtn.disabled = true;
                autoBtn.classList.remove('bg-emerald-600/90', 'hover:bg-emerald-500', 'bg-slate-700', 'hover:bg-slate-600');
                autoBtn.classList.add('bg-slate-700', 'cursor-not-allowed');
            }
            this.stopCallModeAuto();
            this.callModeAutoPlaying = false;
            return;
        }

        if (this.callModeIndex >= this.callModeRoles.length) this.callModeIndex = 0;
        const selectedRole = this.callModeRoles[this.callModeIndex];
        if (timeSlotEl) timeSlotEl.textContent = selectedRole.timeSlot || 'TASK';
        if (roleNameEl) roleNameEl.textContent = selectedRole.name || '역할 이름';
        if (studentNameEl) studentNameEl.textContent = selectedRole.assignee || '미배정';
        if (indexTextEl) indexTextEl.textContent = `${this.callModeIndex + 1} / ${this.callModeRoles.length}`;

        if (autoBtn) {
            autoBtn.disabled = this.callModeRoles.length <= 1;
            autoBtn.textContent = this.callModeAutoPlaying ? '자동 재생 끄기' : '자동 재생 켜기';
            autoBtn.classList.remove('bg-emerald-600/90', 'hover:bg-emerald-500', 'bg-slate-700', 'hover:bg-slate-600', 'cursor-not-allowed');
            if (this.callModeRoles.length <= 1) {
                autoBtn.classList.add('bg-slate-700', 'cursor-not-allowed');
            } else if (this.callModeAutoPlaying) {
                autoBtn.classList.add('bg-emerald-600/90', 'hover:bg-emerald-500');
            } else {
                autoBtn.classList.add('bg-slate-700', 'hover:bg-slate-600');
            }
        }

        this.flashCallModeCard();
    }

    nextCallRole(fromAuto = false) {
        this.syncCallModeRoles();
        if (!this.callModeRoles.length) return;
        this.callModeIndex = (this.callModeIndex + 1) % this.callModeRoles.length;
        this.renderCallMode();
        this.playCallChime(fromAuto ? 'soft' : 'normal');
    }

    prevCallRole() {
        this.syncCallModeRoles();
        if (!this.callModeRoles.length) return;
        this.callModeIndex = (this.callModeIndex - 1 + this.callModeRoles.length) % this.callModeRoles.length;
        this.renderCallMode();
        this.playCallChime();
    }

    startCallModeAuto() {
        this.stopCallModeAuto();
        if (this.callModeRoles.length <= 1) return;
        this.callModeAutoTimer = setInterval(() => {
            this.nextCallRole(true);
        }, 4500);
    }

    stopCallModeAuto() {
        if (this.callModeAutoTimer) {
            clearInterval(this.callModeAutoTimer);
            this.callModeAutoTimer = null;
        }
    }

    toggleCallAuto() {
        this.syncCallModeRoles();
        if (this.callModeRoles.length <= 1) return;
        this.callModeAutoPlaying = !this.callModeAutoPlaying;
        if (this.callModeAutoPlaying) this.startCallModeAuto();
        else this.stopCallModeAuto();
        this.renderCallMode();
    }

    openBroadcastModal() {
        const input = document.getElementById('broadcastInput');
        if (input) input.value = this.broadcastMessage || '';
        this.openModal('broadcastModal');
        if (input) input.focus();
    }

    closeBroadcastModal() {
        this.closeModal('broadcastModal');
    }

    async handleStartBroadcast() {
        const input = document.getElementById('broadcastInput');
        const msg = input ? input.value : '';
        const prevMessage = this.broadcastMessage;
        const prevState = this.isBroadcasting;

        this.broadcastMessage = msg;
        this.isBroadcasting = !!msg;
        this.closeBroadcastModal();
        this.renderNotices();

        try {
            const response = await this.secureFetch(this.getApiUrl('broadcastUrl', '/products/dutyticker/api/broadcast/update/'), {
                method: 'POST',
                body: JSON.stringify({ message: msg })
            });
            await this.parseJsonResponse(response, '알림사항을 저장하지 못했습니다.');
        } catch (error) {
            console.error(error);
            this.broadcastMessage = prevMessage;
            this.isBroadcasting = prevState;
            this.renderNotices();
        }
    }

    openMissionModal() {
        const titleInput = document.getElementById('missionTitleInput');
        const descInput = document.getElementById('missionDescInput');
        if (titleInput) titleInput.value = this.missionTitle;
        if (descInput) descInput.value = this.missionDesc;
        this.openModal('missionModal');
    }

    closeMissionModal() {
        this.closeModal('missionModal');
    }

    async handleUpdateMission() {
        const titleInput = document.getElementById('missionTitleInput');
        const descInput = document.getElementById('missionDescInput');
        const title = titleInput ? titleInput.value : this.missionTitle;
        const desc = descInput ? descInput.value : this.missionDesc;
        const prevTitle = this.missionTitle;
        const prevDesc = this.missionDesc;

        this.missionTitle = title;
        this.missionDesc = desc;
        this.renderMission();
        this.closeMissionModal();

        try {
            const response = await this.secureFetch(this.getApiUrl('missionUrl', '/products/dutyticker/api/mission/update/'), {
                method: 'POST',
                body: JSON.stringify({ title, description: desc })
            });
            await this.parseJsonResponse(response, '미션 내용을 저장하지 못했습니다.');
        } catch (error) {
            console.error(error);
            this.missionTitle = prevTitle;
            this.missionDesc = prevDesc;
            this.renderMission();
        }
    }

    async rotateRolesManually() {
        try {
            const response = await this.secureFetch(this.getApiUrl('rotateUrl', '/products/dutyticker/api/rotate/'), { method: 'POST' });
            await this.parseJsonResponse(response, '역할 순환에 실패했습니다.');
            this.loadData();
        } catch (error) {
            console.error(error);
        }
    }

    async resetToMockup() {
        const shouldReset = confirm('정말로 기본 데이터로 초기화할까요? 현재 학급 상태가 초기화됩니다.');
        if (!shouldReset) return;

        try {
            const response = await this.secureFetch(this.getApiUrl('resetUrl', '/products/dutyticker/api/reset/'), { method: 'POST' });
            await this.parseJsonResponse(response, '데이터 초기화에 실패했습니다.');
            this.pauseTimer();
            this.timerMaxSeconds = 300;
            this.timerSeconds = 300;
            this.syncCustomTimerInput();
            this.updateTimerDisplay();
            this.saveTimerState();
            this.loadData();
        } catch (error) {
            console.error(error);
        }
    }

    // --- Utils ---
    getAudioCtx() {
        if (this.audioCtx) return this.audioCtx;

        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return null;

        this.audioCtx = new AudioContextClass();
        return this.audioCtx;
    }

    resumeAudioContext() {
        const ctx = this.getAudioCtx();
        if (!ctx || typeof ctx.resume !== 'function') return;
        if (ctx.state === 'suspended') {
            ctx.resume().catch(() => { });
        }
    }

    playNote(freq, start, dur, vol = 0.2) {
        if (!this.isSoundEnabled) return;
        const ctx = this.getAudioCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.frequency.setValueAtTime(freq, start);
        gain.gain.setValueAtTime(0, start);
        gain.gain.linearRampToValueAtTime(vol, start + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.01, start + dur);
        osc.start(start); osc.stop(start + dur + 0.1);
    }

    playAlert() {
        const ctx = this.getAudioCtx();
        if (!ctx) return;
        const now = ctx.currentTime;
        this.playNote(880, now, 0.1, 0.4); this.playNote(440, now + 0.15, 0.4, 0.4);
    }

    playSuccessSound() {
        const ctx = this.getAudioCtx();
        if (!ctx) return;
        const now = ctx.currentTime;
        this.playNote(523.25, now, 0.05); this.playNote(659.25, now + 0.05, 0.1);
    }

    playCallChime(mode = 'normal') {
        this.resumeAudioContext();
        const ctx = this.getAudioCtx();
        if (!ctx || !this.isSoundEnabled) return;
        const now = ctx.currentTime + 0.02;

        if (mode === 'soft') {
            this.playNote(659.25, now, 0.18, 0.05);
            this.playNote(783.99, now + 0.16, 0.2, 0.045);
            this.playNote(987.77, now + 0.34, 0.22, 0.04);
            return;
        }

        this.playNote(659.25, now, 0.2, 0.08);
        this.playNote(783.99, now + 0.14, 0.22, 0.07);
        this.playNote(987.77, now + 0.3, 0.26, 0.06);
    }

    toggleBroadcastSound() {
        this.isSoundEnabled = !this.isSoundEnabled;
        localStorage.setItem('dt-broadcast-sound', this.isSoundEnabled);
        this.updateSoundUI();
    }

    updateSoundUI() {
        const btn = document.getElementById('toggleSoundBtn');
        if (!btn) return;
        btn.innerHTML = this.isSoundEnabled ? '<i class="fa-solid fa-volume-high"></i>' : '<i class="fa-solid fa-volume-xmark"></i>';
        btn.classList.toggle('text-indigo-400', this.isSoundEnabled);
    }

    toggleFullscreen() {
        const el = document.getElementById('mainAppContainer') || document.documentElement;
        if (!document.fullscreenElement) el.requestFullscreen().catch(() => { });
        else document.exitFullscreen();
    }
}
