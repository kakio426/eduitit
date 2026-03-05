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
        this.rotationMode = 'manual_sequential';
        this.roleViewMode = 'compact';
        this.roleRotateInFlight = false;
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
        this.boundWindowResize = null;
        this.resizeRaf = null;
        this.roleTickerEnabled = true;
        this.roleTickerIntervalMs = 4200;
        this.roleTickerTimer = null;
        this.roleTickerIndex = -1;
        this.roleTickerStorageKey = 'dt-role-ticker-enabled-v1';
        this.randomDrawnStudentIds = new Set();
        this.randomCurrentStudentId = null;
        this.bgmTracks = window.dtBgmTracks || {};
        this.bgmTrackOrder = Object.keys(this.bgmTracks);
        this.bgmTrackKey = this.bgmTrackOrder[0] || '';
        this.bgmEnabled = false;
        this.bgmLoopMode = 'all';
        this.bgmEnabledTrackKeys = new Set(this.bgmTrackOrder);
        this.bgmAwaitUserGesture = false;
        this.bgmAudioEl = null;
        this.bgmFadeRaf = null;
        this.bgmStorageKey = 'dt-bgm-state-v1';
        this.bgmVolumePercent = 100;
        this.boundBgmUnlock = null;
        this.bgmTrackPanelOpen = false;
        this.boundBgmPanelOutsideClick = null;
        this.boundBgmPanelEscape = null;
        this.missionFontSizeOrder = ['sm', 'md', 'lg'];
        this.missionFontSize = 'md';
        this.missionFontStorageKey = 'dt-mission-font-size-v1';
        this.missionSaveRequestId = 0;
        this.missionSaving = false;
        this.missionPanelCollapsed = true;
        this.missionPanelStorageKey = 'dt-mission-panel-collapsed-v1';

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
        this.restoreMissionFontSize();
        this.applyMissionFontSize();
        this.restoreMissionPanelState();
        this.applyMissionPanelState();
        this.applyRoleViewMode();
        this.restoreRoleTickerState();
        this.setupRoleTickerControls();
        this.updateRoleTickerUI();
        this.restoreTimerState();
        this.updateTimerDisplay();
        this.updateSoundUI();
        this.setupBgm();
        this.restoreBgmState();
        this.updateBgmUI();
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

        this.bindButtonAction('mainTimerDisplay', () => this.toggleTimer());
        this.bindButtonAction('timerAddMinuteBtn', () => this.addTimerMinutes(1));
        this.bindButtonAction('timerPreset5Btn', () => this.setTimerMode(300, true));
        this.bindButtonAction('timerPreset10Btn', () => this.setTimerMode(600, true));
        this.bindButtonAction('timerCustomApplyBtn', () => this.applyCustomTimerMinutes());
        this.bindButtonAction('timerResetBtn', () => this.resetTimer());
        this.bindButtonAction('missionPanelToggleBtn', () => this.toggleMissionPanel());

        this.setupInlineMissionEditor();

        // Ensure timer display is correct on start
        this.updateTimerDisplay();

        if (!this.boundWindowResize) {
            this.boundWindowResize = () => {
                if (this.resizeRaf) cancelAnimationFrame(this.resizeRaf);
                this.resizeRaf = requestAnimationFrame(() => this.applyStudentGridLayoutMode());
            };
            window.addEventListener('resize', this.boundWindowResize, { passive: true });
        }
    }

    bindButtonAction(id, handler) {
        const button = document.getElementById(id);
        if (!button) return;
        if (button.dataset.dtBound === '1') return;
        button.addEventListener('click', (event) => {
            event.preventDefault();
            handler();
        });
        button.dataset.dtBound = '1';
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

    timeStringToMinutes(value) {
        const match = String(value || '').trim().match(/^(\d{1,2}):(\d{2})$/);
        if (!match) return Number.NaN;
        const hours = Number(match[1]);
        const minutes = Number(match[2]);
        if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return Number.NaN;
        if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return Number.NaN;
        return (hours * 60) + minutes;
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
            this.syncRandomPickerStudents();

            this.broadcastMessage = data.settings.last_broadcast || '';
            this.isBroadcasting = !!this.broadcastMessage;
            this.missionTitle = data.settings.mission_title ?? "수학 익힘책 풀기";
            this.missionDesc = data.settings.mission_desc ?? "24~25페이지 풀고 채점하기";
            this.rotationMode = data.settings.rotation_mode || 'manual_sequential';
            this.roleViewMode = data.settings.role_view_mode || 'compact';
            this.spotlightStudentId = Number(data.settings.spotlight_student_id) || null;
            this.theme = data.settings.theme || 'deep_space';

            // Apply Theme to DOM
            document.documentElement.setAttribute('data-theme', this.theme);
            this.applyRoleViewMode();

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
        this.renderRandomPicker();
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
            container.innerHTML = '<span class="dt-header-schedule-empty">오늘 시간표 없음</span>';
            return;
        }

        const now = new Date();
        const nowMinutes = (now.getHours() * 60) + now.getMinutes();

        container.innerHTML = periodSchedule.map((slot) => {
            const periodNumber = Number(slot.period);
            const periodLabel = Number.isFinite(periodNumber) && periodNumber > 0
                ? `${periodNumber}교시`
                : String(slot.slot_label || '');
            const rawSubject = String(slot.name || '').trim();
            const subjectName = rawSubject && rawSubject !== periodLabel ? rawSubject : '미정';
            const startTime = String(slot.startTime || '').trim();
            const endTime = String(slot.endTime || '').trim();
            const startMinutes = this.timeStringToMinutes(startTime);
            const endMinutes = this.timeStringToMinutes(endTime);
            const hasTimeRange = Number.isFinite(startMinutes) && Number.isFinite(endMinutes);
            const isCurrent = hasTimeRange && nowMinutes >= startMinutes && nowMinutes < endMinutes;
            const chipClass = `dt-header-schedule-item${isCurrent ? ' is-current' : ''}`;
            const titleText = hasTimeRange
                ? `${periodLabel} · ${subjectName} (${startTime}-${endTime})`
                : `${periodLabel} · ${subjectName}`;

            return `
                <span class="${chipClass}" title="${this.escapeHtml(titleText)}">
                    <span class="dt-header-schedule-period">${this.escapeHtml(periodLabel)}</span>
                    <span class="dt-header-schedule-sep">·</span>
                    <span class="dt-header-schedule-subject">${this.escapeHtml(subjectName)}</span>
                </span>
            `;
        }).join('');
    }

    renderMission() {
        const titleEl = document.getElementById('mainMissionTitle');
        const descEl = document.getElementById('mainMissionDesc');
        if (titleEl && document.activeElement !== titleEl) titleEl.textContent = this.missionTitle;
        if (descEl && document.activeElement !== descEl) descEl.textContent = this.missionDesc;
    }

    restoreMissionPanelState() {
        try {
            const saved = localStorage.getItem(this.missionPanelStorageKey);
            if (saved === null) {
                this.missionPanelCollapsed = true;
                return;
            }
            this.missionPanelCollapsed = saved === '1';
        } catch (error) {
            this.missionPanelCollapsed = true;
            console.warn('DutyTicker: failed to restore mission panel state', error);
        }
    }

    saveMissionPanelState() {
        try {
            localStorage.setItem(this.missionPanelStorageKey, this.missionPanelCollapsed ? '1' : '0');
        } catch (error) {
            console.warn('DutyTicker: failed to save mission panel state', error);
        }
    }

    applyMissionPanelState() {
        const card = document.getElementById('mainStudentCard');
        const toggleBtn = document.getElementById('missionPanelToggleBtn');
        const toggleText = document.getElementById('missionPanelToggleText');
        const app = document.getElementById('mainAppContainer');
        const expanded = !this.missionPanelCollapsed;

        if (card) card.classList.toggle('is-collapsed', this.missionPanelCollapsed);
        if (app) app.setAttribute('data-mission-panel', this.missionPanelCollapsed ? 'collapsed' : 'expanded');
        if (toggleBtn) {
            toggleBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            toggleBtn.setAttribute('aria-label', expanded ? '미션 현황 접기' : '미션 현황 펼치기');
            toggleBtn.setAttribute('title', expanded ? '미션 현황 접기' : '미션 현황 펼치기');
        }
        if (toggleText) toggleText.textContent = expanded ? '접기' : '펼치기';

        this.applyStudentGridLayoutMode();
    }

    toggleMissionPanel() {
        this.missionPanelCollapsed = !this.missionPanelCollapsed;
        this.applyMissionPanelState();
        this.saveMissionPanelState();
    }

    normalizeRoleViewMode(rawMode) {
        return String(rawMode || '').trim().toLowerCase() === 'readable' ? 'readable' : 'compact';
    }

    applyRoleViewMode() {
        const app = document.getElementById('mainAppContainer');
        const subtitle = document.getElementById('roleCardSubtitle');
        this.roleViewMode = this.normalizeRoleViewMode(this.roleViewMode);

        if (app) app.setAttribute('data-role-view-mode', this.roleViewMode);
        if (subtitle) {
            subtitle.textContent = this.roleViewMode === 'readable'
                ? '멀리서도 보이도록 역할과 이름을 크게 보여줍니다.'
                : '핵심 역할과 담당 학생만 크게 보여줍니다.';
        }
    }

    renderRoleList() {
        const container = document.getElementById('mainRoleList');
        if (!container) return;

        if (!this.roles.length) {
            container.innerHTML = `
                <div class="dt-role-empty rounded-2xl border p-5 text-center">
                    <p class="dt-role-empty-text text-sm font-bold">등록된 역할이 없습니다.</p>
                    <a href="/products/dutyticker/admin/" class="inline-flex mt-3 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold transition">
                        설정에서 역할 추가
                    </a>
                </div>
            `;
            this.stopRoleTicker();
            return;
        }

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
            const isCompleted = role.status === 'completed';
            const roleId = Number.isFinite(Number(role.id)) ? Number(role.id) : 0;
            const safeTimeSlot = this.escapeHtml(role.timeSlot || 'TASK');
            const safeRoleName = this.escapeHtml(role.name);
            const safeAssignee = this.escapeHtml(role.assignee || '미배정');
            const numericRoleId = Number(role.id);
            const isSpotlightRole = spotlightRoleIds.includes(numericRoleId);
            const spotlightClass = isSpotlightRole ? 'dt-role-current-spotlight' : '';
            const spotlightBadge = isSpotlightRole
                ? '<span class="dt-role-spotlight-badge inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black border"><i class="fa-solid fa-bolt text-[9px]"></i>집중</span>'
                : '';
            const statusDotClass = isCompleted ? 'is-completed' : 'is-pending';
            const statusBadge = isCompleted
                ? '<span class="dt-role-status-text is-completed inline-flex items-center gap-1"><i class="fa-solid fa-check-circle text-[11px]"></i>완료</span>'
                : '';
            const assigneeToneClass = isCompleted ? 'is-completed' : 'is-pending';
            return `
                <div class="dt-role-row border cursor-pointer ${spotlightClass}"
                    role="button"
                    tabindex="0"
                    onclick="window.dtApp.openStudentModal(${roleId})"
                    onkeydown="if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); window.dtApp.openStudentModal(${roleId}); }">
                    <div class="dt-role-main min-w-0">
                        <div class="dt-role-content min-w-0">
                            <p class="dt-role-name ${isCompleted ? 'is-completed' : ''}">${safeRoleName}</p>
                            <div class="dt-role-meta">
                                <p class="dt-role-slot">${safeTimeSlot}</p>
                                ${spotlightBadge}
                                <span class="dt-role-status-dot ${statusDotClass}" aria-hidden="true"></span>
                                ${statusBadge}
                            </div>
                        </div>
                        <div class="dt-role-assignee-wrap">
                            <div class="dt-role-assignee ${assigneeToneClass}" title="${safeAssignee}">${safeAssignee}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        this.ensureRoleTickerRunning();
        this.paintRoleTickerFocus({ force: true });
    }

    setupRoleTickerControls() {
        const toggleBtn = document.getElementById('roleTickerToggleBtn');
        if (!toggleBtn) return;
        if (toggleBtn.dataset.dtBound === '1') return;
        toggleBtn.addEventListener('click', (event) => {
            event.preventDefault();
            this.toggleRoleTicker();
        });
        toggleBtn.dataset.dtBound = '1';
    }

    restoreRoleTickerState() {
        try {
            const raw = localStorage.getItem(this.roleTickerStorageKey);
            if (raw === null) {
                this.roleTickerEnabled = true;
                return;
            }
            this.roleTickerEnabled = raw !== 'false';
        } catch (error) {
            console.warn('DutyTicker: failed to restore role ticker state', error);
            this.roleTickerEnabled = true;
        }
    }

    saveRoleTickerState() {
        try {
            localStorage.setItem(this.roleTickerStorageKey, this.roleTickerEnabled ? 'true' : 'false');
        } catch (error) {
            console.warn('DutyTicker: failed to save role ticker state', error);
        }
    }

    updateRoleTickerUI() {
        const toggleBtn = document.getElementById('roleTickerToggleBtn');
        if (!toggleBtn) return;

        const isOn = this.roleTickerEnabled;
        toggleBtn.innerHTML = `<i class="fa-solid fa-wave-square"></i> ${isOn ? '자동순환 ON' : '자동순환 OFF'}`;
        toggleBtn.classList.toggle('is-active', isOn);
        toggleBtn.setAttribute('aria-pressed', isOn ? 'true' : 'false');
        toggleBtn.setAttribute('title', isOn ? '자동순환 끄기' : '자동순환 켜기');
    }

    ensureRoleTickerRunning() {
        this.stopRoleTicker();
        if (!this.roleTickerEnabled) return;

        const rows = this.getRoleRows();
        if (rows.length <= 1) return;

        this.roleTickerTimer = setInterval(() => {
            this.stepRoleTicker();
        }, this.roleTickerIntervalMs);
    }

    stopRoleTicker() {
        if (this.roleTickerTimer) {
            clearInterval(this.roleTickerTimer);
            this.roleTickerTimer = null;
        }
    }

    getRoleRows() {
        const container = document.getElementById('mainRoleList');
        if (!container) return [];
        return Array.from(container.querySelectorAll('.dt-role-row'));
    }

    paintRoleTickerFocus({ force = false } = {}) {
        const rows = this.getRoleRows();
        if (!rows.length) return;
        if (!this.roleTickerEnabled) {
            rows.forEach((row) => row.classList.remove('dt-role-cycle-focus'));
            return;
        }

        if (this.roleTickerIndex < 0 || this.roleTickerIndex >= rows.length || force) {
            this.roleTickerIndex = Math.max(0, Math.min(rows.length - 1, this.roleTickerIndex));
        }

        rows.forEach((row, index) => row.classList.toggle('dt-role-cycle-focus', index === this.roleTickerIndex));
    }

    stepRoleTicker() {
        const rows = this.getRoleRows();
        if (rows.length <= 1) return;

        this.roleTickerIndex = (this.roleTickerIndex + 1) % rows.length;
        this.paintRoleTickerFocus();

        const activeRow = rows[this.roleTickerIndex];
        if (!activeRow) return;
        activeRow.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    }

    toggleRoleTicker() {
        this.roleTickerEnabled = !this.roleTickerEnabled;
        this.updateRoleTickerUI();
        this.saveRoleTickerState();

        if (!this.roleTickerEnabled) {
            this.stopRoleTicker();
            const rows = this.getRoleRows();
            rows.forEach((row) => row.classList.remove('dt-role-cycle-focus'));
            return;
        }

        this.roleTickerIndex = -1;
        this.ensureRoleTickerRunning();
        this.stepRoleTicker();
    }

    applyStudentGridLayoutMode() {
        const grid = document.getElementById('mainStudentGrid');
        const card = document.getElementById('mainStudentCard');
        if (!grid || !card) return;

        const isDesktop = window.matchMedia('(min-width: 1024px)').matches;
        const studentCount = this.students.length;
        const shouldUseComfortFit = isDesktop && studentCount > 0 && studentCount <= 30;

        grid.classList.toggle('dt-student-grid-fit-25', shouldUseComfortFit);
        grid.classList.remove('dt-student-density-low', 'dt-student-density-mid', 'dt-student-density-high');
        if (shouldUseComfortFit) {
            if (studentCount <= 10) grid.classList.add('dt-student-density-low');
            else if (studentCount <= 20) grid.classList.add('dt-student-density-mid');
            else grid.classList.add('dt-student-density-high');
        }
        grid.classList.add('overflow-y-auto');
        grid.classList.remove('overflow-y-hidden');
        grid.classList.toggle('pr-2', !shouldUseComfortFit);
        grid.classList.toggle('pr-1', shouldUseComfortFit);
        grid.classList.remove('pr-0');

        card.classList.toggle('dt-student-card-fit-25', shouldUseComfortFit);
    }

    getStudentNameSizeClass(name) {
        const normalized = String(name || '').trim();
        const length = Array.from(normalized).length;
        if (length <= 3) return 'dt-student-name-short';
        if (length <= 5) return 'dt-student-name-mid';
        return 'dt-student-name-long';
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
            this.applyStudentGridLayoutMode();
            this.updateProgress();
            return;
        }

        container.innerHTML = this.students.map(student => {
            const isDone = student.status === 'done';
            const studentId = Number.isFinite(Number(student.id)) ? Number(student.id) : 0;
            const safeStudentNumber = this.escapeHtml(student.number);
            const safeStudentName = this.escapeHtml(student.name);
            const isSpotlight = Number(this.spotlightStudentId) === Number(student.id);
            const nameSizeClass = this.getStudentNameSizeClass(student.name);
            const tileStateClass = `${isDone ? 'is-done' : ''} ${isSpotlight ? 'is-spotlight' : ''}`.trim();
            const studentTitle = `${safeStudentNumber}번 ${safeStudentName}`;
            return `
                <div class="dt-student-tile relative border cursor-pointer ${tileStateClass}"
                    role="button"
                    tabindex="0"
                    aria-label="${studentTitle}"
                    onclick="window.dtApp.handleStudentStatusToggle(${studentId})"
                    onkeydown="if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); window.dtApp.handleStudentStatusToggle(${studentId}); }"
                    ondblclick="event.preventDefault(); window.dtApp.toggleSpotlightStudent(${studentId});"
                    oncontextmenu="event.preventDefault(); window.dtApp.toggleSpotlightStudent(${studentId});">
                    <span class="dt-student-name ${nameSizeClass}" title="${studentTitle}">${safeStudentName}</span>
                </div>
            `;
        }).join('');
        this.applyStudentGridLayoutMode();
        this.updateProgress();
    }

    renderNotices() {
        const textEl = document.getElementById('dashboardBroadcastText');
        const titleEl = document.getElementById('noticeTitleDisplay');
        const messageWrap = document.getElementById('noticeMessageWrap');
        const divider = document.getElementById('noticeDivider');
        const card = document.getElementById('noticeCard');
        if (!textEl || !titleEl) return;

        if (this.isBroadcasting && this.broadcastMessage) {
            titleEl.innerHTML = '<i class="fa-solid fa-bell text-yellow-500"></i> 알림사항';
            textEl.textContent = this.broadcastMessage;
            textEl.classList.add('text-yellow-100');
            if (messageWrap) messageWrap.classList.remove('hidden');
            if (divider) divider.classList.remove('hidden');
            if (card) card.classList.remove('dt-notice-card-empty');
        } else {
            titleEl.innerHTML = '<i class="fa-regular fa-bell text-slate-500"></i> 알림사항';
            textEl.textContent = '';
            textEl.classList.remove('text-yellow-100');
            if (messageWrap) messageWrap.classList.add('hidden');
            if (divider) divider.classList.add('hidden');
            if (card) card.classList.add('dt-notice-card-empty');
        }
    }

    syncRandomPickerStudents() {
        const validIds = new Set(
            this.students
                .map((student) => Number(student.id))
                .filter((id) => Number.isFinite(id))
        );

        this.randomDrawnStudentIds = new Set(
            [...this.randomDrawnStudentIds].filter((studentId) => validIds.has(Number(studentId)))
        );

        const currentId = Number(this.randomCurrentStudentId);
        if (!Number.isFinite(currentId) || !validIds.has(currentId)) {
            this.randomCurrentStudentId = null;
            return;
        }

        this.randomCurrentStudentId = currentId;
        this.randomDrawnStudentIds.add(currentId);
    }

    getRandomPickerAvailableStudents() {
        const drawnIds = this.randomDrawnStudentIds;
        return this.students.filter((student) => {
            const studentId = Number(student.id);
            return Number.isFinite(studentId) && !drawnIds.has(studentId);
        });
    }

    renderRandomPicker() {
        const nameEl = document.getElementById('randomDrawName');
        const metaEl = document.getElementById('randomDrawMeta');
        const drawBtn = document.getElementById('randomDrawBtn');
        const resetBtn = document.getElementById('randomDrawResetBtn');
        if (!nameEl || !metaEl || !drawBtn || !resetBtn) return;

        const total = this.students.length;
        const pickedCount = this.randomDrawnStudentIds.size;
        const remaining = Math.max(total - pickedCount, 0);
        const selectedStudent = this.students.find(
            (student) => Number(student.id) === Number(this.randomCurrentStudentId)
        );

        if (total === 0) {
            nameEl.textContent = '학생이 없어요';
            nameEl.classList.add('is-empty');
            metaEl.textContent = '0 / 0';
            drawBtn.disabled = true;
            drawBtn.textContent = '학생 없음';
            drawBtn.classList.add('opacity-60', 'cursor-not-allowed');
            resetBtn.disabled = true;
            resetBtn.classList.add('opacity-60', 'cursor-not-allowed');
            return;
        }

        metaEl.textContent = `${pickedCount} / ${total} · 남은 ${remaining}`;

        if (selectedStudent) {
            nameEl.textContent = `${selectedStudent.number}번 ${selectedStudent.name}`;
            nameEl.classList.remove('is-empty');
        } else {
            nameEl.textContent = '버튼을 눌러 한 명 뽑으세요';
            nameEl.classList.add('is-empty');
        }

        const done = remaining === 0;
        drawBtn.disabled = done;
        drawBtn.textContent = done ? '모두 뽑음' : '한 명 뽑기';
        drawBtn.classList.toggle('opacity-60', done);
        drawBtn.classList.toggle('cursor-not-allowed', done);

        const canReset = pickedCount > 0 || !!selectedStudent;
        resetBtn.disabled = !canReset;
        resetBtn.classList.toggle('opacity-60', !canReset);
        resetBtn.classList.toggle('cursor-not-allowed', !canReset);
    }

    drawRandomStudent() {
        if (!this.students.length) {
            this.renderRandomPicker();
            return;
        }

        const availableStudents = this.getRandomPickerAvailableStudents();
        if (!availableStudents.length) {
            this.renderRandomPicker();
            return;
        }

        const pickedStudent = availableStudents[Math.floor(Math.random() * availableStudents.length)];
        const pickedStudentId = Number(pickedStudent.id);
        this.randomCurrentStudentId = pickedStudentId;
        this.randomDrawnStudentIds.add(pickedStudentId);
        this.renderRandomPicker();
        this.playCallChime('soft');

        const nameEl = document.getElementById('randomDrawName');
        if (nameEl && typeof nameEl.animate === 'function') {
            nameEl.animate(
                [
                    { transform: 'scale(0.94)', opacity: 0.55 },
                    { transform: 'scale(1.06)', opacity: 1 },
                    { transform: 'scale(1)', opacity: 1 },
                ],
                { duration: 420, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' }
            );
        }
    }

    resetRandomPicker() {
        this.randomDrawnStudentIds.clear();
        this.randomCurrentStudentId = null;
        this.renderRandomPicker();
    }

    updateProgress() {
        const total = this.students.length;
        const bar = document.getElementById('missionProgressBar');
        const text = document.getElementById('missionProgressText');
        if (total === 0) {
            if (bar) bar.style.width = '0%';
            if (text) text.textContent = '0% (0/0)';
            return;
        }
        const done = this.students.filter(s => s.status === 'done').length;
        const percent = Math.round((done / total) * 100);
        if (bar) bar.style.width = `${percent}%`;
        if (text) text.textContent = `${percent}% (${done}/${total})`;
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
        const remaining = Math.max(0, Math.floor((this.timerEndAt - Date.now()) / 1000));

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
        this.handleTimerTick();
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
        this.timerMaxSeconds = 300;
        this.timerSeconds = 300;
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

    sanitizeMissionText(value, field) {
        const raw = String(value || '').replace(/\u00a0/g, ' ').replace(/\r/g, '');
        if (field === 'title') return raw.replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim();
        return raw.split('\n').map((line) => line.replace(/\s+/g, ' ').trim()).join('\n').trim();
    }

    setupInlineMissionEditor() {
        const titleEl = document.getElementById('mainMissionTitle');
        const descEl = document.getElementById('mainMissionDesc');
        if (!titleEl || !descEl) return;

        const stripPasteFormatting = (event) => {
            event.preventDefault();
            const text = event.clipboardData?.getData('text/plain') || '';
            document.execCommand('insertText', false, text);
        };

        titleEl.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                titleEl.blur();
            }
        });
        titleEl.addEventListener('paste', stripPasteFormatting);
        descEl.addEventListener('paste', stripPasteFormatting);

        const onBlurSave = () => this.saveInlineMissionEdit();
        titleEl.addEventListener('blur', onBlurSave);
        descEl.addEventListener('blur', onBlurSave);
    }

    async saveInlineMissionEdit() {
        const titleEl = document.getElementById('mainMissionTitle');
        const descEl = document.getElementById('mainMissionDesc');
        if (!titleEl || !descEl) return;

        const title = this.sanitizeMissionText(titleEl.innerText, 'title');
        const desc = this.sanitizeMissionText(descEl.innerText, 'desc');

        if (title === this.missionTitle && desc === this.missionDesc) {
            this.renderMission();
            return;
        }

        await this.handleUpdateMission({ title, desc });
    }

    async handleUpdateMission({ title, desc } = {}) {
        const nextTitle = this.sanitizeMissionText(title ?? this.missionTitle, 'title');
        const nextDesc = this.sanitizeMissionText(desc ?? this.missionDesc, 'desc');
        const prevTitle = this.missionTitle;
        const prevDesc = this.missionDesc;
        const requestId = ++this.missionSaveRequestId;

        this.missionSaving = true;
        this.missionTitle = nextTitle;
        this.missionDesc = nextDesc;
        this.renderMission();

        try {
            const response = await this.secureFetch(this.getApiUrl('missionUrl', '/products/dutyticker/api/mission/update/'), {
                method: 'POST',
                body: JSON.stringify({ title: nextTitle, description: nextDesc })
            });
            await this.parseJsonResponse(response, '미션 내용을 저장하지 못했습니다.');
        } catch (error) {
            console.error(error);
            if (requestId !== this.missionSaveRequestId) return;
            this.missionTitle = prevTitle;
            this.missionDesc = prevDesc;
            this.renderMission();
        } finally {
            if (requestId === this.missionSaveRequestId) this.missionSaving = false;
        }
    }

    restoreMissionFontSize() {
        try {
            const saved = localStorage.getItem(this.missionFontStorageKey);
            if (saved && this.missionFontSizeOrder.includes(saved)) {
                this.missionFontSize = saved;
            }
        } catch (error) {
            console.warn('DutyTicker: failed to restore mission font size', error);
        }
    }

    saveMissionFontSize() {
        try {
            localStorage.setItem(this.missionFontStorageKey, this.missionFontSize);
        } catch (error) {
            console.warn('DutyTicker: failed to save mission font size', error);
        }
    }

    applyMissionFontSize() {
        const app = document.getElementById('mainAppContainer');
        if (app) app.setAttribute('data-mission-size', this.missionFontSize);

        const label = document.getElementById('missionFontSizeLabel');
        if (label) {
            label.textContent = this.missionFontSize === 'sm'
                ? '작게'
                : this.missionFontSize === 'lg'
                    ? '크게'
                    : '보통';
        }
    }

    changeMissionFontSize(direction = 0) {
        const step = Number(direction);
        if (!Number.isFinite(step) || step === 0) return;
        const currentIndex = this.missionFontSizeOrder.indexOf(this.missionFontSize);
        const safeIndex = currentIndex >= 0 ? currentIndex : 1;
        const nextIndex = Math.max(0, Math.min(this.missionFontSizeOrder.length - 1, safeIndex + (step > 0 ? 1 : -1)));
        this.missionFontSize = this.missionFontSizeOrder[nextIndex];
        this.applyMissionFontSize();
        this.saveMissionFontSize();
    }

    async rotateRolesManually() {
        return this.resetRoleAssignments();
    }

    async resetRoleAssignments() {
        if (this.roleRotateInFlight) return;
        const resetBtn = document.getElementById('roleResetAssignmentsBtn') || document.getElementById('roleRotateNowBtn');
        const shouldReset = confirm('역할은 유지하고 담당 학생 배정만 초기화할까요?');
        if (!shouldReset) return;

        try {
            this.roleRotateInFlight = true;
            if (resetBtn) resetBtn.disabled = true;

            const response = await this.secureFetch(
                this.getApiUrl('resetAssignmentsUrl', '/products/dutyticker/api/assignments/reset/'),
                { method: 'POST' }
            );
            await this.parseJsonResponse(response, '학생 배정 초기화에 실패했습니다.');
            await this.loadData();
        } catch (error) {
            console.error(error);
            alert(error?.message || '학생 배정 초기화에 실패했습니다. 잠시 후 다시 시도해 주세요.');
        } finally {
            this.roleRotateInFlight = false;
            if (resetBtn) resetBtn.disabled = false;
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
            alert(error?.message || '데이터 초기화에 실패했습니다. 잠시 후 다시 시도해 주세요.');
        }
    }

    // --- BGM ---
    setupBgm() {
        if (!this.bgmTrackOrder.length) return;

        const audioContainer = document.getElementById('audioContainer');
        if (audioContainer) {
            const audioEl = document.createElement('audio');
            audioEl.id = 'bgmAudio';
            audioEl.preload = 'metadata';
            audioEl.loop = false;
            audioEl.volume = 0;
            audioEl.setAttribute('aria-hidden', 'true');
            audioEl.addEventListener('ended', () => this.handleBgmTrackEnded());
            audioContainer.innerHTML = '';
            audioContainer.appendChild(audioEl);
            this.bgmAudioEl = audioEl;
        }

        const rail = document.getElementById('bgmTrackRail');
        if (rail) {
            rail.addEventListener('click', (event) => {
                const target = event.target;
                if (!(target instanceof HTMLElement)) return;
                const playKey = target.dataset.bgmPlay || '';
                if (!playKey) return;
                event.preventDefault();
                this.setBgmTrack(playKey, { persist: true, userInitiated: true, autoplay: true });
            });

            rail.addEventListener('change', (event) => {
                const target = event.target;
                if (!(target instanceof HTMLInputElement)) return;
                if (target.type !== 'checkbox') return;
                const trackKey = target.dataset.bgmToggle || '';
                if (!trackKey) return;

                if (target.checked) this.bgmEnabledTrackKeys.add(trackKey);
                else this.bgmEnabledTrackKeys.delete(trackKey);

                const playableKeys = this.getPlayableBgmTrackKeys();
                if (!playableKeys.length) {
                    this.bgmEnabled = false;
                    this.bgmTrackKey = this.bgmTrackOrder[0] || '';
                    this.pauseBgm({ save: false });
                } else if (!this.bgmEnabledTrackKeys.has(this.bgmTrackKey)) {
                    this.bgmTrackKey = playableKeys[0];
                    if (this.bgmEnabled) this.playBgm({ userInitiated: true, forceReload: true });
                }

                this.saveBgmState();
                this.updateBgmUI();
            });
        }

        const volumeRange = document.getElementById('bgmVolumeRange');
        if (volumeRange && volumeRange.dataset.dtBound !== '1') {
            volumeRange.addEventListener('input', (event) => {
                const target = event.target;
                if (!(target instanceof HTMLInputElement)) return;
                this.setBgmVolumePercent(target.value, { persist: false, applyNow: true });
            });
            volumeRange.addEventListener('change', (event) => {
                const target = event.target;
                if (!(target instanceof HTMLInputElement)) return;
                this.setBgmVolumePercent(target.value, { persist: true, applyNow: true });
            });
            volumeRange.dataset.dtBound = '1';
        }

        if (!this.boundBgmPanelOutsideClick) {
            this.boundBgmPanelOutsideClick = (event) => {
                const controls = document.getElementById('bgmControls');
                if (!controls || !(event.target instanceof Node)) return;
                if (controls.contains(event.target)) return;
                this.toggleBgmTrackPanel(false);
            };
            document.addEventListener('click', this.boundBgmPanelOutsideClick, true);
        }

        if (!this.boundBgmPanelEscape) {
            this.boundBgmPanelEscape = (event) => {
                if (event.key !== 'Escape') return;
                this.toggleBgmTrackPanel(false);
            };
            document.addEventListener('keydown', this.boundBgmPanelEscape);
        }

        this.renderBgmTrackRail();
        this.updateBgmUI();
        this.ensureBgmUnlockListener();
    }

    toggleBgmTrackPanel(forceOpen = null) {
        const rail = document.getElementById('bgmTrackRail');
        const shouldOpen = forceOpen === null ? !this.bgmTrackPanelOpen : !!forceOpen;
        this.bgmTrackPanelOpen = shouldOpen;
        if (!rail) return;
        rail.classList.toggle('is-open', shouldOpen);
    }

    ensureBgmUnlockListener() {
        if (this.boundBgmUnlock) return;
        this.boundBgmUnlock = () => {
            this.resumeAudioContext();
            if (this.bgmAwaitUserGesture && this.bgmEnabled) {
                this.playBgm({ userInitiated: true });
            }
        };
        document.addEventListener('pointerdown', this.boundBgmUnlock, { passive: true });
        document.addEventListener('keydown', this.boundBgmUnlock);
    }

    saveBgmState() {
        try {
            localStorage.setItem(this.bgmStorageKey, JSON.stringify({
                enabled: this.bgmEnabled,
                trackKey: this.bgmTrackKey,
                loopMode: this.bgmLoopMode,
                enabledTrackKeys: [...this.bgmEnabledTrackKeys],
                volumePercent: this.bgmVolumePercent,
            }));
        } catch (error) {
            console.warn('DutyTicker: failed to save BGM state', error);
        }
    }

    restoreBgmState() {
        if (!this.bgmTrackOrder.length) return;
        try {
            const raw = localStorage.getItem(this.bgmStorageKey);
            if (!raw) {
                this.bgmEnabledTrackKeys = new Set(this.bgmTrackOrder);
                this.bgmLoopMode = 'all';
                this.bgmTrackKey = this.bgmTrackOrder[0];
                this.bgmVolumePercent = 100;
                this.renderBgmTrackRail();
                this.updateBgmUI();
                this.saveBgmState();
                return;
            }

            const parsed = JSON.parse(raw);
            const validTrackSet = new Set(this.bgmTrackOrder);
            const rawRestoredTrackKeys = Array.isArray(parsed.enabledTrackKeys)
                ? parsed.enabledTrackKeys.filter((key) => validTrackSet.has(String(key)))
                : this.bgmTrackOrder.slice();
            const restoredTrackKeys = rawRestoredTrackKeys.length ? rawRestoredTrackKeys : this.bgmTrackOrder.slice();

            this.bgmEnabledTrackKeys = new Set(restoredTrackKeys);
            this.bgmLoopMode = parsed.loopMode === 'one' ? 'one' : 'all';
            this.bgmVolumePercent = this.normalizeBgmVolumePercent(parsed.volumePercent, 100);

            const requestedTrack = String(parsed.trackKey || '');
            if (validTrackSet.has(requestedTrack)) this.bgmTrackKey = requestedTrack;
            else this.bgmTrackKey = this.bgmTrackOrder[0];

            const canPlay = this.getPlayableBgmTrackKeys().length > 0;
            this.bgmEnabled = parsed.enabled === true && canPlay;

            this.renderBgmTrackRail();
            this.updateBgmUI();
            if (this.bgmEnabled) this.playBgm({ userInitiated: false, forceReload: true });
        } catch (error) {
            console.warn('DutyTicker: failed to restore BGM state', error);
            this.renderBgmTrackRail();
            this.updateBgmUI();
        }
    }

    getPlayableBgmTrackKeys() {
        return this.bgmTrackOrder.filter((key) => this.bgmEnabledTrackKeys.has(key));
    }

    normalizeBgmVolumePercent(value, fallback = 100) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return fallback;
        const rounded = Math.round(numeric);
        return Math.max(0, Math.min(200, rounded));
    }

    getBgmMasterVolumeGain() {
        return this.normalizeBgmVolumePercent(this.bgmVolumePercent, 100) / 100;
    }

    getBgmTrackTargetVolume(track) {
        const baseVolume = Math.max(0.06, Math.min(0.28, Number(track?.volume) || 0.16));
        const gain = this.getBgmMasterVolumeGain();
        return Math.max(0, Math.min(1, baseVolume * gain));
    }

    setBgmVolumePercent(value, { persist = true, applyNow = true } = {}) {
        this.bgmVolumePercent = this.normalizeBgmVolumePercent(value, this.bgmVolumePercent);

        if (applyNow && this.bgmAudioEl) {
            const track = this.bgmTracks[this.bgmTrackKey] || {};
            const nextVolume = this.getBgmTrackTargetVolume(track);
            if (this.bgmEnabled && !this.bgmAudioEl.paused) {
                void this.fadeBgmVolume(nextVolume, 120);
            } else {
                this.bgmAudioEl.volume = nextVolume;
            }
        }

        if (persist) this.saveBgmState();
        this.updateBgmUI();
    }

    renderBgmTrackRail() {
        const rail = document.getElementById('bgmTrackRail');
        if (!rail) return;
        if (!this.bgmTrackOrder.length) {
            rail.innerHTML = '<span class="text-[10px] text-slate-500 font-bold px-1">곡 없음</span>';
            return;
        }

        rail.innerHTML = this.bgmTrackOrder.map((trackKey, index) => {
            const track = this.bgmTracks[trackKey] || {};
            const enabled = this.bgmEnabledTrackKeys.has(trackKey);
            const isCurrent = this.bgmTrackKey === trackKey;
            const rawLabel = String(track.label || `트랙 ${index + 1}`);
            const shortLabel = rawLabel.includes('·') ? rawLabel.split('·').pop().trim() : rawLabel;
            const chipLabel = `${String(index + 1).padStart(2, '0')} ${this.escapeHtml(shortLabel)}`;
            const checked = enabled ? 'checked' : '';
            const chipClass = `dt-bgm-chip ${isCurrent ? 'is-current' : ''} ${enabled ? '' : 'is-muted'}`;

            return `
                <div class="${chipClass}">
                    <input type="checkbox" data-bgm-toggle="${this.escapeHtml(trackKey)}" ${checked} aria-label="${this.escapeHtml(rawLabel)} 재생 포함">
                    <button type="button" class="dt-bgm-chip-btn" data-bgm-play="${this.escapeHtml(trackKey)}" title="${this.escapeHtml(rawLabel)}">${chipLabel}</button>
                </div>
            `;
        }).join('');
    }

    updateBgmUI() {
        const toggleBtn = document.getElementById('bgmToggleBtn');
        const loopBtn = document.getElementById('bgmLoopModeBtn');
        const prevBtn = document.getElementById('bgmPrevBtn');
        const nextBtn = document.getElementById('bgmNextBtn');
        const panelBtn = document.getElementById('bgmTrackPanelBtn');
        const volumeRange = document.getElementById('bgmVolumeRange');
        const volumeValue = document.getElementById('bgmVolumeValue');

        const playableCount = this.getPlayableBgmTrackKeys().length;
        const hasTracks = this.bgmTrackOrder.length > 0;
        const canPlay = hasTracks && playableCount > 0;

        if (toggleBtn) {
            toggleBtn.disabled = !canPlay;
            toggleBtn.textContent = !canPlay
                ? 'BGM 없음'
                : this.bgmEnabled
                    ? (this.bgmAwaitUserGesture ? '재생대기' : 'BGM ON')
                    : 'BGM OFF';
            toggleBtn.classList.toggle('opacity-60', !canPlay);
            toggleBtn.classList.toggle('cursor-not-allowed', !canPlay);
            toggleBtn.classList.toggle('bg-indigo-600', this.bgmEnabled && canPlay);
            toggleBtn.classList.toggle('text-white', this.bgmEnabled && canPlay);
        }

        if (loopBtn) {
            loopBtn.disabled = !canPlay;
            loopBtn.textContent = this.bgmLoopMode === 'one' ? '1곡' : '전체';
            loopBtn.classList.toggle('opacity-60', !canPlay);
            loopBtn.classList.toggle('cursor-not-allowed', !canPlay);
        }

        if (prevBtn) {
            prevBtn.disabled = playableCount <= 1;
            prevBtn.classList.toggle('opacity-60', playableCount <= 1);
            prevBtn.classList.toggle('cursor-not-allowed', playableCount <= 1);
        }

        if (nextBtn) {
            nextBtn.disabled = playableCount <= 1;
            nextBtn.classList.toggle('opacity-60', playableCount <= 1);
            nextBtn.classList.toggle('cursor-not-allowed', playableCount <= 1);
        }

        if (panelBtn) {
            panelBtn.disabled = !hasTracks;
            panelBtn.textContent = `목록 ${playableCount}/${this.bgmTrackOrder.length}`;
            panelBtn.classList.toggle('opacity-60', !hasTracks);
            panelBtn.classList.toggle('cursor-not-allowed', !hasTracks);
        }

        if (volumeRange) {
            volumeRange.value = String(this.bgmVolumePercent);
            volumeRange.disabled = !hasTracks;
            volumeRange.classList.toggle('opacity-50', !hasTracks);
            volumeRange.classList.toggle('cursor-not-allowed', !hasTracks);
        }

        if (volumeValue) volumeValue.textContent = `${this.bgmVolumePercent}%`;

        if (!hasTracks) this.toggleBgmTrackPanel(false);

        this.renderBgmTrackRail();
    }

    toggleBgm() {
        if (!this.getPlayableBgmTrackKeys().length) {
            this.bgmEnabled = false;
            this.updateBgmUI();
            return;
        }

        this.bgmEnabled = !this.bgmEnabled;
        if (this.bgmEnabled) this.playBgm({ userInitiated: true });
        else this.pauseBgm({ save: false });
        this.saveBgmState();
        this.updateBgmUI();
    }

    toggleBgmLoopMode() {
        this.bgmLoopMode = this.bgmLoopMode === 'one' ? 'all' : 'one';
        if (this.bgmAudioEl) this.bgmAudioEl.loop = this.bgmLoopMode === 'one';
        this.saveBgmState();
        this.updateBgmUI();
    }

    setBgmTrack(trackKey, { persist = true, userInitiated = false, autoplay = true } = {}) {
        const nextTrackKey = String(trackKey || '');
        if (!this.bgmTrackOrder.includes(nextTrackKey)) return;

        this.bgmTrackKey = nextTrackKey;
        this.bgmEnabledTrackKeys.add(nextTrackKey);

        if (persist) this.saveBgmState();
        this.updateBgmUI();
        if (autoplay && this.bgmEnabled) this.playBgm({ userInitiated, forceReload: true });
    }

    nextBgmTrack(userInitiated = true) {
        const playable = this.getPlayableBgmTrackKeys();
        if (!playable.length) return;
        const currentIndex = Math.max(0, playable.indexOf(this.bgmTrackKey));
        const nextTrack = playable[(currentIndex + 1) % playable.length];
        this.setBgmTrack(nextTrack, { persist: true, userInitiated, autoplay: true });
    }

    prevBgmTrack(userInitiated = true) {
        const playable = this.getPlayableBgmTrackKeys();
        if (!playable.length) return;
        const currentIndex = Math.max(0, playable.indexOf(this.bgmTrackKey));
        const prevTrack = playable[(currentIndex - 1 + playable.length) % playable.length];
        this.setBgmTrack(prevTrack, { persist: true, userInitiated, autoplay: true });
    }

    async fadeBgmVolume(targetVolume, duration = 260) {
        const audio = this.bgmAudioEl;
        if (!audio) return;
        const safeTarget = Math.max(0, Math.min(1, Number(targetVolume) || 0));
        if (duration <= 0) {
            audio.volume = safeTarget;
            return;
        }

        const startVolume = Number(audio.volume) || 0;
        const startAt = performance.now();

        if (this.bgmFadeRaf) cancelAnimationFrame(this.bgmFadeRaf);

        await new Promise((resolve) => {
            const step = (now) => {
                const progress = Math.min(1, (now - startAt) / duration);
                const eased = 1 - ((1 - progress) * (1 - progress));
                audio.volume = startVolume + ((safeTarget - startVolume) * eased);
                if (progress < 1) {
                    this.bgmFadeRaf = requestAnimationFrame(step);
                } else {
                    this.bgmFadeRaf = null;
                    resolve();
                }
            };
            this.bgmFadeRaf = requestAnimationFrame(step);
        });
    }

    async playBgm({ userInitiated = false, forceReload = false } = {}) {
        const audio = this.bgmAudioEl;
        if (!audio || !this.bgmEnabled) return;

        const playable = this.getPlayableBgmTrackKeys();
        if (!playable.length) {
            this.bgmEnabled = false;
            this.updateBgmUI();
            return;
        }

        if (!this.bgmEnabledTrackKeys.has(this.bgmTrackKey)) {
            this.bgmTrackKey = playable[0];
        }

        const track = this.bgmTracks[this.bgmTrackKey];
        if (!track || !track.src) return;

        const targetVolume = this.getBgmTrackTargetVolume(track);
        const currentTrack = audio.dataset.trackKey || '';
        const shouldReload = forceReload || currentTrack !== this.bgmTrackKey;

        if (shouldReload) {
            if (!audio.paused) await this.fadeBgmVolume(0, 180);
            audio.pause();
            audio.src = String(track.src);
            audio.load();
            audio.dataset.trackKey = this.bgmTrackKey;
        }

        audio.loop = this.bgmLoopMode === 'one';
        audio.volume = 0.001;
        this.resumeAudioContext();

        try {
            await audio.play();
            this.bgmAwaitUserGesture = false;
            await this.fadeBgmVolume(targetVolume, userInitiated ? 300 : 460);
            this.saveBgmState();
            this.updateBgmUI();
        } catch (error) {
            this.bgmAwaitUserGesture = true;
            this.updateBgmUI();
        }
    }

    async pauseBgm({ save = true } = {}) {
        const audio = this.bgmAudioEl;
        if (!audio) return;
        await this.fadeBgmVolume(0, 180);
        audio.pause();
        if (save) this.saveBgmState();
        this.updateBgmUI();
    }

    handleBgmTrackEnded() {
        if (!this.bgmEnabled) return;
        if (this.bgmLoopMode === 'one') {
            this.playBgm({ userInitiated: false, forceReload: true });
            return;
        }
        this.nextBgmTrack(false);
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

    playNote(freq, start, dur, vol = 0.2, waveType = 'sine') {
        if (!this.isSoundEnabled) return;
        const ctx = this.getAudioCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = waveType;
        osc.frequency.setValueAtTime(freq, start);
        gain.gain.setValueAtTime(0, start);
        gain.gain.linearRampToValueAtTime(vol, start + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.01, start + dur);
        osc.start(start); osc.stop(start + dur + 0.1);
    }

    playAlert() {
        const display = document.getElementById('mainTimerDisplay');
        if (display && typeof display.animate === 'function') {
            display.animate(
                [
                    { transform: 'scale(1)', filter: 'drop-shadow(0 0 0 rgba(250, 204, 21, 0))' },
                    { transform: 'scale(1.06)', filter: 'drop-shadow(0 0 18px rgba(250, 204, 21, 0.72))' },
                    { transform: 'scale(1)', filter: 'drop-shadow(0 0 0 rgba(250, 204, 21, 0))' },
                ],
                { duration: 480, iterations: 3, easing: 'ease-out' }
            );
        }

        this.resumeAudioContext();
        const ctx = this.getAudioCtx();
        if (!ctx || !this.isSoundEnabled) return;
        const now = ctx.currentTime + 0.02;
        const cycleOffsets = [0, 1.18];

        cycleOffsets.forEach((offset) => {
            this.playNote(659.25, now + offset, 0.22, 0.12, 'sine');
            this.playNote(523.25, now + offset + 0.3, 0.3, 0.1, 'sine');
            this.playNote(392.0, now + offset + 0.72, 0.36, 0.075, 'sine');
        });
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

