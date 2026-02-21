/**
 * DutyTicker Logic Manager (Premium V3 - Correct Path)
 * Fixed: Pathing issue where JS was in wrong static folder.
 * Fixed: Modal flex/hidden logic.
 * Fixed: Timer initialization.
 */
class DutyTickerManager {
    constructor() {
        this.roles = [];
        this.students = [];
        this.todaySchedule = [];
        this.isBroadcasting = false;
        this.broadcastMessage = '';
        this.isSoundEnabled = localStorage.getItem('dt-broadcast-sound') !== 'false';

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
        return fetch(url, options);
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
            const response = await fetch('/dutyticker/api/data/');
            const data = await response.json();

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

            const today = new Date().getDay();
            this.todaySchedule = data.schedule[today] || [];

            this.renderAll();
        } catch (error) {
            console.error("Fetch Error:", error);
        }
    }

    renderAll() {
        this.renderSchedule();
        this.renderMission();
        this.renderRoleList();
        this.renderStudentGrid();
        this.renderNotices();
    }

    renderSchedule() {
        const container = document.getElementById('headerScheduleStrip');
        if (!container) return;
        if (this.todaySchedule.length === 0) {
            container.innerHTML = '<span class="text-slate-500 text-[10px] uppercase px-4 opacity-50">일정 없음</span>';
            return;
        }
        container.innerHTML = this.todaySchedule.map(s => `
            <div class="px-3 py-1 bg-white/5 rounded-xl border border-white/5 whitespace-nowrap text-xs font-bold text-slate-200">
                <span class="text-indigo-400 mr-1">${this.escapeHtml(s.period)}</span> ${this.escapeHtml(s.name)}
            </div>
        `).join('');
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

        const roleIcons = {
            '칠판 지우기': 'fa-solid fa-broom',
            '우유': 'fa-solid fa-glass-water',
            '불 끄기': 'fa-solid fa-lightbulb',
            '컴퓨터': 'fa-solid fa-laptop',
            '식물': 'fa-solid fa-leaf'
        };

        container.innerHTML = this.roles.map(role => {
            const iconClass = roleIcons[role.name] || 'fa-solid fa-circle-user';
            const isCompleted = role.status === 'completed';
            const roleId = Number.isFinite(Number(role.id)) ? Number(role.id) : 0;
            const safeTimeSlot = this.escapeHtml(role.timeSlot || 'TASK');
            const safeRoleName = this.escapeHtml(role.name);
            const safeAssignee = this.escapeHtml(role.assignee || '미배정');
            return `
                <div class="flex items-center p-4 bg-slate-800/30 backdrop-blur-md rounded-[1.5rem] border border-white/5 hover:bg-slate-700/40 transition-all cursor-pointer group shadow-lg"
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
                             <p class="${isCompleted ? 'opacity-30 line-through' : ''}">${safeRoleName}</p>
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

        container.innerHTML = this.students.map(student => {
            const isDone = student.status === 'done';
            const studentId = Number.isFinite(Number(student.id)) ? Number(student.id) : 0;
            const safeStudentNumber = this.escapeHtml(student.number);
            const safeStudentName = this.escapeHtml(student.name);
            return `
                <div class="relative p-2 rounded-2xl border border-slate-700 bg-slate-800/50 flex flex-col items-center gap-1 cursor-pointer transition group ${isDone ? 'border-emerald-500/50 bg-emerald-500/10' : ''}"
                    onclick="window.dtApp.handleStudentStatusToggle(${studentId})">
                    <div class="w-9 h-9 rounded-full flex items-center justify-center text-sm font-black transition-all ${isDone ? 'bg-emerald-500 text-slate-900' : 'bg-slate-700 text-slate-300 group-hover:bg-indigo-500'}">
                        ${safeStudentNumber}
                    </div>
                    <span class="text-xs font-bold ${isDone ? 'text-emerald-400' : 'text-slate-400'}">${safeStudentName}</span>
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
            textEl.textContent = "클릭해서 공지사항을 입력하세요.";
            textEl.classList.remove('text-yellow-100');
        }
    }

    updateProgress() {
        const total = this.students.length;
        if (total === 0) return;
        const done = this.students.filter(s => s.status === 'done').length;
        const percent = Math.round((done / total) * 100);
        const bar = document.getElementById('missionProgressBar');
        const text = document.getElementById('missionProgressText');
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
            await this.secureFetch(`/dutyticker/api/student/${studentId}/toggle_mission/`, { method: 'POST' });
        } catch (e) {
            student.status = original;
            this.renderStudentGrid();
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

    async assignStudent(studentId) {
        if (!this.selectedRoleId) return;
        try {
            await this.secureFetch('/dutyticker/api/assign/', {
                method: 'POST',
                body: JSON.stringify({ role_id: this.selectedRoleId, student_id: studentId })
            });
            this.loadData();
            this.closeModal('studentModal');
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
            await this.secureFetch(`/dutyticker/api/assignment/${role.assignmentId}/toggle/`, {
                method: 'POST',
                body: JSON.stringify({ is_completed: nextStatus })
            });
            this.loadData();
        } catch (error) {
            console.error(error);
            this.loadData();
        }
    }

    openBroadcastModal() { this.openModal('broadcastModal'); document.getElementById('broadcastInput').focus(); }
    closeBroadcastModal() { this.closeModal('broadcastModal'); }

    async handleStartBroadcast() {
        const msg = document.getElementById('broadcastInput').value;
        this.broadcastMessage = msg;
        this.isBroadcasting = !!msg;
        this.closeBroadcastModal();
        this.renderNotices();
        await this.secureFetch('/dutyticker/api/broadcast/update/', {
            method: 'POST',
            body: JSON.stringify({ message: msg })
        });
    }

    openMissionModal() {
        document.getElementById('missionTitleInput').value = this.missionTitle;
        document.getElementById('missionDescInput').value = this.missionDesc;
        this.openModal('missionModal');
    }
    closeMissionModal() { this.closeModal('missionModal'); }

    async handleUpdateMission() {
        const title = document.getElementById('missionTitleInput').value;
        const desc = document.getElementById('missionDescInput').value;
        this.missionTitle = title;
        this.missionDesc = desc;
        this.renderMission();
        this.closeMissionModal();
        await this.secureFetch('/dutyticker/api/mission/update/', {
            method: 'POST',
            body: JSON.stringify({ title, description: desc })
        });
    }

    async rotateRolesManually() {
        try {
            await this.secureFetch('/dutyticker/api/rotate/', { method: 'POST' });
            this.loadData();
        } catch (error) {
            console.error(error);
        }
    }

    async resetToMockup() {
        const shouldReset = confirm('정말로 기본 데이터로 초기화할까요? 현재 학급 상태가 초기화됩니다.');
        if (!shouldReset) return;

        try {
            await this.secureFetch('/dutyticker/api/reset/', { method: 'POST' });
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
