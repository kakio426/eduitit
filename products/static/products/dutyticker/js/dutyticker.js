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
        this.theme = window.__DT_INITIAL_THEME__ || 'deep_space';
        this.roleRotateInFlight = false;
        this.isBroadcasting = false;
        this.broadcastMessage = '';
        this.isSoundEnabled = localStorage.getItem('dt-broadcast-sound') !== 'false';
        this.ttsEnabled = false;
        this.ttsMinutesBefore = 5;
        this.ttsVoiceUri = '';
        this.ttsRate = 0.95;
        this.ttsPitch = 1.0;
        this.ttsAutoAnnouncementStorageKey = 'dt-auto-tts-history-v1';
        this.ttsAutoAnnouncementHistory = { date: '', tokens: [] };
        this.selectedRoleId = null;
        this.pendingConflict = null;
        this.spotlightStudentId = null;
        this.callModeIndex = 0;
        this.callModeRoles = [];
        this.callModeAutoTimer = null;
        this.callModeAutoPlaying = false;
        this.boundGlobalKeydown = null;
        this.boundWindowResize = null;
        this.boundFullscreenChange = null;
        this.resizeRaf = null;
        this.layoutRaf = null;
        this.layoutObserver = null;
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
        this.bgmDefaultVolumePercent = 140;
        this.bgmGainBoost = 2.2;
        this.bgmTrackVolumeCap = 0.72;
        this.soundEffectGainBoost = 2.2;
        this.soundEffectVolumeCap = 0.34;
        this.bgmVolumePercent = this.bgmDefaultVolumePercent;
        this.boundBgmUnlock = null;
        this.bgmTrackPanelOpen = false;
        this.boundBgmPanelOutsideClick = null;
        this.boundBgmPanelEscape = null;
        this.missionFontSizeOrder = ['xxxs', 'xxs', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl', 'xxxl'];
        this.missionFontSize = 'md';
        this.missionFontStorageKey = 'dt-mission-font-size-v1';
        this.missionSaveRequestId = 0;
        this.missionSaving = false;
        this.missionResetInFlight = false;
        this.missionPanelCollapsed = true;
        this.missionPanelStorageKey = 'dt-mission-panel-collapsed-v1';
        this.missionQuickPhraseStorageKey = 'dt-mission-quick-phrase-v1';
        this.missionQuickPhrases = [];
        this.missionQuickPhraseLimit = 20;
        this.missionQuickPhrase = null;
        this.missionQuickSelectedId = null;
        this.breakAutoConfigStorageKey = 'dt-break-auto-config-v1';
        this.breakAutoRuntimeStorageKey = 'dt-break-auto-runtime-v1';
        this.breakAutoConfig = this.getDefaultBreakAutoConfig();
        this.breakAutoRuntime = this.getDefaultBreakAutoRuntime();
        this.breakAutoActiveSlotCode = '';
        this.breakAutoEligibleMaxSeconds = 15 * 60;

        this.timerSeconds = 300;
        this.timerMaxSeconds = 300;
        this.isTimerRunning = false;
        this.timerInterval = null;
        this.timerEndAt = null;
        this.timerStorageKey = 'dt-focus-timer-state-v1';
        this.audioCtx = null;
        this.headerClockTimer = null;
        this.headerClockMinuteKey = '';
        this.hasLoadedData = false;
    }

    init() {
        console.log("DutyTicker: Initializing...");
        this.applyThemeToDom(this.theme);
        this.startHeaderClock();
        this.loadData();
        this.setupEventListeners();
        this.setupAdaptiveLayoutObserver();
        this.restoreMissionFontSize();
        this.applyMissionFontSize();
        this.restoreMissionQuickPhrase();
        this.restoreBreakAutoConfig();
        this.restoreBreakAutoRuntime();
        this.updateMissionQuickPhraseUI();
        this.restoreMissionPanelState();
        this.applyMissionPanelState();
        this.applyRoleViewMode();
        this.restoreRoleTickerState();
        this.setupRoleTickerControls();
        this.updateRoleTickerUI();
        this.restoreTimerState();
        this.updateTimerDisplay();
        this.restoreTtsAutoAnnouncementHistory();
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

        const broadcastUseSchedule = document.getElementById('broadcastUseScheduleBtn');
        if (broadcastUseSchedule) broadcastUseSchedule.onclick = () => this.fillBroadcastWithNextAnnouncement();

        const broadcastSpeakNow = document.getElementById('broadcastSpeakNowBtn');
        if (broadcastSpeakNow) broadcastSpeakNow.onclick = () => this.speakBroadcastInput();

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
        this.bindButtonAction('missionQuickSaveBtn', () => this.saveMissionQuickPhraseFromCurrent());
        this.bindButtonAction('missionQuickApplyBtn', () => this.openMissionQuickPhraseModal());
        this.bindButtonAction('missionQuickModalCloseBtn', () => this.closeMissionQuickPhraseModal());
        this.bindButtonAction('missionQuickLoadCurrentBtn', () => this.loadCurrentMissionIntoQuickPhraseForm());
        this.bindButtonAction('missionQuickCreateBtn', () => this.createMissionQuickPhraseFromModal());
        this.bindButtonAction('missionQuickUpdateBtn', () => this.updateSelectedMissionQuickPhrase());
        this.bindButtonAction('missionQuickApplySelectedBtn', () => this.applyMissionQuickPhrase());
        this.bindButtonAction('missionQuickDeleteBtn', () => this.deleteSelectedMissionQuickPhrase());
        this.bindButtonAction('missionQuickDeleteAllBtn', () => this.clearMissionQuickPhrases());
        this.bindButtonAction('missionQuickAssignBreakAutoBtn', () => this.assignSelectedMissionQuickPhraseToBreakAuto());
        this.setupBreakAutoConfigControls();

        this.setupInlineMissionEditor();

        // Ensure timer display is correct on start
        this.updateTimerDisplay();

        if (!this.boundWindowResize) {
            this.boundWindowResize = () => {
                if (this.resizeRaf) cancelAnimationFrame(this.resizeRaf);
                this.resizeRaf = requestAnimationFrame(() => {
                    this.applyStudentGridLayoutMode();
                    this.requestAdaptiveLayoutRefresh();
                });
            };
            window.addEventListener('resize', this.boundWindowResize, { passive: true });
        }

        if (!this.boundFullscreenChange) {
            this.boundFullscreenChange = () => this.requestAdaptiveLayoutRefresh();
            document.addEventListener('fullscreenchange', this.boundFullscreenChange);
        }
    }

    startHeaderClock() {
        this.updateHeaderClock();
        if (this.headerClockTimer) clearInterval(this.headerClockTimer);
        this.headerClockTimer = setInterval(() => this.updateHeaderClock(), 1000);
    }

    updateHeaderClock() {
        const now = new Date();
        const dateStr = now
            .toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short' })
            .replace(/\s/g, '\u00A0');
        const timeStr = now
            .toLocaleTimeString('ko-KR', { hour12: true, hour: 'numeric', minute: '2-digit' })
            .replace(/\s/g, '\u00A0');

        const dateEl = document.getElementById('headerDate');
        const timeEl = document.getElementById('headerTime');
        if (dateEl) dateEl.textContent = dateStr;
        if (timeEl) timeEl.textContent = timeStr;

        if (!this.hasLoadedData) return;

        const minuteKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}-${now.getHours()}-${now.getMinutes()}`;
        if (minuteKey !== this.headerClockMinuteKey) {
            this.headerClockMinuteKey = minuteKey;
            this.renderSchedule();
        }
    }

    setupAdaptiveLayoutObserver() {
        if (this.layoutObserver || typeof ResizeObserver !== 'function') return;

        const targets = [
            document.getElementById('mainAppContainer'),
            document.querySelector('.dt-left-column'),
            document.querySelector('.dt-timer-card'),
            document.getElementById('mainStudentCard'),
            document.getElementById('mainStudentGridWrap'),
        ].filter(Boolean);

        if (!targets.length) return;

        this.layoutObserver = new ResizeObserver(() => this.requestAdaptiveLayoutRefresh());
        targets.forEach((target) => this.layoutObserver.observe(target));
    }

    requestAdaptiveLayoutRefresh() {
        if (this.layoutRaf) cancelAnimationFrame(this.layoutRaf);
        this.layoutRaf = requestAnimationFrame(() => {
            this.layoutRaf = null;
            this.applyAdaptiveLayoutState();
        });
    }

    applyAdaptiveLayoutState() {
        const app = document.getElementById('mainAppContainer');
        const leftColumn = document.querySelector('.dt-left-column');
        const timerCard = document.querySelector('.dt-timer-card');
        if (!app || !leftColumn || !timerCard) return;

        const previousDensity = app.getAttribute('data-layout-density') || '';
        const previousDisplayMode = app.getAttribute('data-display-mode') || '';
        const leftHeight = leftColumn.getBoundingClientRect().height;
        const timerHeight = timerCard.getBoundingClientRect().height;
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
        const availableHeight = Math.min(
            viewportHeight > 0 ? viewportHeight : Number.POSITIVE_INFINITY,
            leftHeight > 0 ? leftHeight : Number.POSITIVE_INFINITY
        );
        const effectiveAvailableHeight = Number.isFinite(availableHeight)
            ? availableHeight
            : Math.max(viewportHeight, leftHeight, 0);
        const isStudentPanelExpanded = !this.missionPanelCollapsed;
        const isMissionFontLarge = ['lg', 'xl', 'xxl', 'xxxl'].includes(this.missionFontSize);
        const isMissionFontHuge = ['xl', 'xxl', 'xxxl'].includes(this.missionFontSize);
        const isDisplayFullscreen = !!document.fullscreenElement;
        const displayMode = isDisplayFullscreen ? 'fullscreen' : 'windowed';

        let density = isDisplayFullscreen ? 'hero' : 'presentation';
        if (!isDisplayFullscreen) {
            const shouldUseCompact = (
                viewportHeight < 720
                || timerHeight < 430
                || (isStudentPanelExpanded && effectiveAvailableHeight < 760)
                || (isStudentPanelExpanded && isMissionFontHuge && timerHeight < 560)
            );
            const shouldUseBalanced = shouldUseCompact || (
                viewportHeight < 820
                || timerHeight < 520
                || (isStudentPanelExpanded && effectiveAvailableHeight < 900)
                || (isStudentPanelExpanded && isMissionFontLarge && timerHeight < 620)
            );
            density = shouldUseCompact ? 'compact' : (shouldUseBalanced ? 'balanced' : 'presentation');
        }

        app.setAttribute('data-display-mode', displayMode);
        app.setAttribute('data-layout-density', density);
        if (previousDensity !== density || previousDisplayMode !== displayMode) {
            this.renderSchedule();
        }
        this.applyStudentGridLayoutMode();
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

    bindInputAction(id, eventName, handler) {
        const input = document.getElementById(id);
        if (!input) return;
        const boundKey = `dtBound${eventName}`;
        if (input.dataset[boundKey] === '1') return;
        input.addEventListener(eventName, handler);
        input.dataset[boundKey] = '1';
    }

    setupBreakAutoConfigControls() {
        this.bindInputAction('breakAutoEnabledInput', 'change', (event) => {
            this.handleBreakAutoEnabledToggle(event.target.checked);
        });
        this.bindInputAction('breakAutoMinutesInput', 'change', () => this.handleBreakAutoMinutesCommit());
        this.bindInputAction('breakAutoMinutesInput', 'blur', () => this.handleBreakAutoMinutesCommit());
        this.bindInputAction('breakAutoMinutesInput', 'keydown', (event) => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            this.handleBreakAutoMinutesCommit();
        });
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

    getCsrfToken() {
        return this.getCookie('csrftoken') || this.api.csrfToken || '';
    }

    async secureFetch(url, options = {}) {
        const csrftoken = this.getCsrfToken();
        if (!options.headers) options.headers = {};
        if (csrftoken) options.headers['X-CSRFToken'] = csrftoken;
        if (!options.headers['X-Requested-With']) options.headers['X-Requested-With'] = 'XMLHttpRequest';
        if (!options.credentials) options.credentials = 'same-origin';
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

    applyThemeToDom(theme = this.theme) {
        const nextTheme = String(theme || 'deep_space');
        this.theme = nextTheme;
        document.documentElement.setAttribute('data-theme', nextTheme);
        document.documentElement.style.colorScheme = nextTheme === 'deep_space' ? 'dark' : 'light';
        window.__DT_INITIAL_THEME__ = nextTheme;
    }

    buildFreshUrl(url) {
        const token = `dt=${Date.now()}`;
        return String(url || '').includes('?') ? `${url}&${token}` : `${url}?${token}`;
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

    minutesToTimeString(totalMinutes) {
        if (!Number.isFinite(totalMinutes)) return '';
        const safeTotal = Math.max(0, Math.min(1439, Math.floor(totalMinutes)));
        const hours = Math.floor(safeTotal / 60);
        const minutes = safeTotal % 60;
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
    }

    getLocalDateKey(date = new Date()) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    getDefaultBreakAutoConfig() {
        return {
            enabled: false,
            timerMinutes: 10,
            phraseId: '',
            phraseSnapshot: null,
        };
    }

    getDefaultBreakAutoRuntime() {
        return {
            date: '',
            runs: {},
        };
    }

    normalizeBreakAutoTimerMinutes(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return 10;
        return Math.max(1, Math.min(60, Math.round(parsed)));
    }

    sanitizeBreakAutoPhraseSnapshot(rawSnapshot = null) {
        if (!rawSnapshot || typeof rawSnapshot !== 'object') return null;

        const title = this.sanitizeMissionText(rawSnapshot.title || '', 'title');
        const desc = this.sanitizeMissionText(rawSnapshot.desc || '', 'desc');
        const label = this.buildMissionQuickPhraseLabel(title, desc, String(rawSnapshot.label || ''));
        if (!title && !desc && !label) return null;

        return {
            label,
            title,
            desc,
        };
    }

    restoreBreakAutoConfig() {
        try {
            const raw = localStorage.getItem(this.breakAutoConfigStorageKey);
            if (!raw) {
                this.breakAutoConfig = this.getDefaultBreakAutoConfig();
                return;
            }

            const parsed = JSON.parse(raw);
            const nextConfig = this.getDefaultBreakAutoConfig();
            nextConfig.enabled = parsed?.enabled === true;
            nextConfig.timerMinutes = this.normalizeBreakAutoTimerMinutes(parsed?.timerMinutes);
            nextConfig.phraseId = String(parsed?.phraseId || '').trim();
            nextConfig.phraseSnapshot = this.sanitizeBreakAutoPhraseSnapshot(parsed?.phraseSnapshot);
            if (!nextConfig.phraseSnapshot) nextConfig.enabled = false;
            this.breakAutoConfig = nextConfig;
        } catch (error) {
            console.warn('DutyTicker: failed to restore break auto config', error);
            this.breakAutoConfig = this.getDefaultBreakAutoConfig();
        }
    }

    saveBreakAutoConfig() {
        const nextConfig = {
            enabled: this.breakAutoConfig.enabled === true && !!this.breakAutoConfig.phraseSnapshot,
            timerMinutes: this.normalizeBreakAutoTimerMinutes(this.breakAutoConfig.timerMinutes),
            phraseId: String(this.breakAutoConfig.phraseId || '').trim(),
            phraseSnapshot: this.sanitizeBreakAutoPhraseSnapshot(this.breakAutoConfig.phraseSnapshot),
        };
        if (!nextConfig.phraseSnapshot) {
            nextConfig.enabled = false;
            nextConfig.phraseId = '';
        }
        this.breakAutoConfig = nextConfig;

        try {
            localStorage.setItem(this.breakAutoConfigStorageKey, JSON.stringify(nextConfig));
        } catch (error) {
            console.warn('DutyTicker: failed to save break auto config', error);
        }
    }

    restoreBreakAutoRuntime() {
        try {
            const raw = localStorage.getItem(this.breakAutoRuntimeStorageKey);
            if (!raw) {
                this.breakAutoRuntime = this.getDefaultBreakAutoRuntime();
                return;
            }

            const parsed = JSON.parse(raw);
            const runs = parsed?.runs && typeof parsed.runs === 'object' ? parsed.runs : {};
            const normalizedRuns = {};
            Object.entries(runs).forEach(([slotCode, row]) => {
                if (!slotCode || !row || typeof row !== 'object') return;
                normalizedRuns[String(slotCode)] = {
                    appliedAt: Number(row.appliedAt) || Date.now(),
                    appliedTitle: this.sanitizeMissionText(row.appliedTitle || '', 'title'),
                    appliedDesc: this.sanitizeMissionText(row.appliedDesc || '', 'desc'),
                    prevTitle: this.sanitizeMissionText(row.prevTitle || '', 'title'),
                    prevDesc: this.sanitizeMissionText(row.prevDesc || '', 'desc'),
                };
            });

            this.breakAutoRuntime = {
                date: String(parsed?.date || ''),
                runs: normalizedRuns,
            };
        } catch (error) {
            console.warn('DutyTicker: failed to restore break auto runtime', error);
            this.breakAutoRuntime = this.getDefaultBreakAutoRuntime();
        }
    }

    saveBreakAutoRuntime() {
        try {
            localStorage.setItem(this.breakAutoRuntimeStorageKey, JSON.stringify(this.breakAutoRuntime));
        } catch (error) {
            console.warn('DutyTicker: failed to save break auto runtime', error);
        }
    }

    ensureBreakAutoRuntime(date = new Date()) {
        const todayKey = this.getLocalDateKey(date);
        if (this.breakAutoRuntime.date === todayKey) return;
        this.breakAutoRuntime = {
            date: todayKey,
            runs: {},
        };
        this.breakAutoActiveSlotCode = '';
        this.saveBreakAutoRuntime();
    }

    getBreakAutoRun(slotCode, date = new Date()) {
        this.ensureBreakAutoRuntime(date);
        return this.breakAutoRuntime.runs[String(slotCode)] || null;
    }

    setBreakAutoRun(slotCode, runData, date = new Date()) {
        if (!slotCode || !runData || typeof runData !== 'object') return;
        this.ensureBreakAutoRuntime(date);
        this.breakAutoRuntime.runs[String(slotCode)] = {
            appliedAt: Number(runData.appliedAt) || Date.now(),
            appliedTitle: this.sanitizeMissionText(runData.appliedTitle || '', 'title'),
            appliedDesc: this.sanitizeMissionText(runData.appliedDesc || '', 'desc'),
            prevTitle: this.sanitizeMissionText(runData.prevTitle || '', 'title'),
            prevDesc: this.sanitizeMissionText(runData.prevDesc || '', 'desc'),
        };
        this.saveBreakAutoRuntime();
    }

    clearBreakAutoRun(slotCode, date = new Date()) {
        this.ensureBreakAutoRuntime(date);
        if (!Object.prototype.hasOwnProperty.call(this.breakAutoRuntime.runs, String(slotCode))) return;
        delete this.breakAutoRuntime.runs[String(slotCode)];
        this.saveBreakAutoRuntime();
    }

    getBreakAutoPhraseSnapshot() {
        return this.sanitizeBreakAutoPhraseSnapshot(this.breakAutoConfig.phraseSnapshot);
    }

    isBreakAutoEnabled() {
        return this.breakAutoConfig.enabled === true && !!this.getBreakAutoPhraseSnapshot();
    }

    getBreakAutoSlotDurationSeconds(slot, now = new Date()) {
        const startAt = this.getBreakSlotDate(slot, 'startTime', now);
        const endAt = this.getBreakSlotDate(slot, 'endTime', now);
        if (!startAt || !endAt || endAt <= startAt) return 0;
        return Math.max(0, Math.ceil((endAt.getTime() - startAt.getTime()) / 1000));
    }

    isBreakAutoEligibleSlot(slot, now = new Date()) {
        const slotType = String(slot?.slot_type || '').trim();
        if (!slotType || slotType === 'period') return false;
        if (slotType === 'break') return true;

        // Some schools use the 4-5 transition as a short recess even if the slot is still labeled lunch.
        const durationSeconds = this.getBreakAutoSlotDurationSeconds(slot, now);
        return durationSeconds > 0 && durationSeconds <= this.breakAutoEligibleMaxSeconds;
    }

    getBreakSlots(now = new Date()) {
        return this.todaySchedule
            .filter((slot) => this.isBreakAutoEligibleSlot(slot, now))
            .sort((a, b) => {
                const aStart = this.timeStringToMinutes(a?.startTime);
                const bStart = this.timeStringToMinutes(b?.startTime);
                return aStart - bStart;
            });
    }

    getBreakSlotDate(slot, timeKey, now = new Date()) {
        const target = String(slot?.[timeKey] || '').trim();
        const match = target.match(/^(\d{1,2}):(\d{2})$/);
        if (!match) return null;
        const date = new Date(now);
        date.setHours(Number(match[1]), Number(match[2]), 0, 0);
        return date;
    }

    getCurrentBreakSlot(now = new Date()) {
        const currentTime = now.getTime();
        return this.getBreakSlots(now).find((slot) => {
            const startAt = this.getBreakSlotDate(slot, 'startTime', now);
            const endAt = this.getBreakSlotDate(slot, 'endTime', now);
            if (!startAt || !endAt || endAt <= startAt) return false;
            return currentTime >= startAt.getTime() && currentTime < endAt.getTime();
        }) || null;
    }

    getBreakSlotRemainingSeconds(slot, now = new Date()) {
        const endAt = this.getBreakSlotDate(slot, 'endTime', now);
        if (!endAt) return 0;
        return Math.max(0, Math.ceil((endAt.getTime() - now.getTime()) / 1000));
    }

    isMissionMatchingSnapshot(snapshot) {
        if (!snapshot) return false;
        const currentTitle = this.sanitizeMissionText(this.missionTitle, 'title');
        const currentDesc = this.sanitizeMissionText(this.missionDesc, 'desc');
        return currentTitle === this.sanitizeMissionText(snapshot.title || '', 'title')
            && currentDesc === this.sanitizeMissionText(snapshot.desc || '', 'desc');
    }

    applyMissionLocally({ title, desc } = {}) {
        this.missionTitle = this.sanitizeMissionText(title ?? this.missionTitle, 'title');
        this.missionDesc = this.sanitizeMissionText(desc ?? this.missionDesc, 'desc');
        this.renderMission();
    }

    restoreBreakAutoMissionFromRun(slotCode, run) {
        if (!slotCode || !run) return;
        this.applyMissionLocally({
            title: run.appliedTitle,
            desc: run.appliedDesc,
        });
        this.breakAutoActiveSlotCode = String(slotCode);
    }

    cleanupBreakAutoRuntime(now = new Date(), activeSlotCode = '') {
        this.ensureBreakAutoRuntime(now);
        const activeCode = String(activeSlotCode || '');
        const slotMap = new Map(this.getBreakSlots(now).map((slot) => [String(slot.slot_code || ''), slot]));
        let didChange = false;

        Object.entries(this.breakAutoRuntime.runs).forEach(([slotCode, run]) => {
            const normalizedSlotCode = String(slotCode || '');
            if (!normalizedSlotCode || normalizedSlotCode === activeCode) return;

            const slot = slotMap.get(normalizedSlotCode);
            const endAt = slot ? this.getBreakSlotDate(slot, 'endTime', now) : null;
            const hasEnded = !slot || !endAt || now.getTime() >= endAt.getTime();
            if (!hasEnded) return;

            const appliedSnapshot = {
                title: run?.appliedTitle || '',
                desc: run?.appliedDesc || '',
            };
            if (
                this.breakAutoActiveSlotCode === normalizedSlotCode
                && this.isMissionMatchingSnapshot(appliedSnapshot)
            ) {
                this.applyMissionLocally({
                    title: run?.prevTitle || '',
                    desc: run?.prevDesc || '',
                });
            }

            delete this.breakAutoRuntime.runs[normalizedSlotCode];
            if (this.breakAutoActiveSlotCode === normalizedSlotCode) {
                this.breakAutoActiveSlotCode = '';
            }
            didChange = true;
        });

        if (didChange) this.saveBreakAutoRuntime();
    }

    applyBreakAutoToSlot(slot, now = new Date()) {
        const slotCode = String(slot?.slot_code || '').trim();
        const phraseSnapshot = this.getBreakAutoPhraseSnapshot();
        if (!slotCode || !phraseSnapshot) return;

        const runData = {
            appliedAt: now.getTime(),
            appliedTitle: phraseSnapshot.title,
            appliedDesc: phraseSnapshot.desc,
            prevTitle: this.sanitizeMissionText(this.missionTitle, 'title'),
            prevDesc: this.sanitizeMissionText(this.missionDesc, 'desc'),
        };

        this.setBreakAutoRun(slotCode, runData, now);
        this.restoreBreakAutoMissionFromRun(slotCode, runData);

        const configuredSeconds = this.normalizeBreakAutoTimerMinutes(this.breakAutoConfig.timerMinutes) * 60;
        const remainingSeconds = this.getBreakSlotRemainingSeconds(slot, now);
        const timerSeconds = remainingSeconds > 0
            ? Math.min(configuredSeconds, remainingSeconds)
            : configuredSeconds;
        const slotType = String(slot?.slot_type || '').trim();
        const slotLabel = slotType === 'break'
            ? (String(slot?.slot_label || '').trim() || '쉬는시간')
            : '쉬는시간';

        this.setTimerMode(timerSeconds, true);
        this.showToast(`${slotLabel} 자동 시작`, 'success');
    }

    syncBreakAutoState(now = new Date()) {
        if (!this.hasLoadedData) return;

        const activeSlot = this.getCurrentBreakSlot(now);
        const activeSlotCode = String(activeSlot?.slot_code || '');
        this.cleanupBreakAutoRuntime(now, activeSlotCode);

        if (!activeSlotCode) {
            this.breakAutoActiveSlotCode = '';
            return;
        }

        const existingRun = this.getBreakAutoRun(activeSlotCode, now);
        if (existingRun) {
            if (
                this.breakAutoActiveSlotCode !== activeSlotCode
                || this.isMissionMatchingSnapshot({
                    title: existingRun.appliedTitle,
                    desc: existingRun.appliedDesc,
                })
            ) {
                this.restoreBreakAutoMissionFromRun(activeSlotCode, existingRun);
            }
            return;
        }

        if (!this.isBreakAutoEnabled()) return;
        this.applyBreakAutoToSlot(activeSlot, now);
    }

    handleBreakAutoEnabledToggle(checked) {
        if (checked && !this.getBreakAutoPhraseSnapshot()) {
            this.breakAutoConfig.enabled = false;
            this.saveBreakAutoConfig();
            this.renderBreakAutoConfigCard();
            this.updateMissionQuickPhraseUI();
            this.showToast('먼저 자동으로 쓸 문구를 지정해 주세요.', 'error');
            return;
        }

        this.breakAutoConfig.enabled = checked === true;
        this.saveBreakAutoConfig();
        this.renderBreakAutoConfigCard();
        this.updateMissionQuickPhraseUI();
        if (this.breakAutoConfig.enabled) this.syncBreakAutoState(new Date());
    }

    handleBreakAutoMinutesCommit() {
        const input = document.getElementById('breakAutoMinutesInput');
        if (!input) return;
        const nextMinutes = this.normalizeBreakAutoTimerMinutes(input.value);
        input.value = String(nextMinutes);
        this.breakAutoConfig.timerMinutes = nextMinutes;
        this.saveBreakAutoConfig();
        this.renderBreakAutoConfigCard();
    }

    assignSelectedMissionQuickPhraseToBreakAuto() {
        const selected = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        if (!selected) {
            this.showToast('자동 문구로 지정할 항목을 먼저 선택해 주세요.', 'error');
            return;
        }

        this.breakAutoConfig.phraseId = selected.id;
        this.breakAutoConfig.phraseSnapshot = {
            label: selected.label,
            title: selected.title,
            desc: selected.desc,
        };
        this.breakAutoConfig.enabled = true;
        this.saveBreakAutoConfig();
        this.renderBreakAutoConfigCard();
        this.updateMissionQuickPhraseUI();
        this.syncBreakAutoState(new Date());
        this.showToast(`'${selected.label}' 문구를 쉬는시간 자동 문구로 지정했습니다.`, 'success');
    }

    getBreakAutoSummaryText() {
        const snapshot = this.getBreakAutoPhraseSnapshot();
        if (!snapshot) return '자동 문구 없음';
        return snapshot.desc || snapshot.title || snapshot.label || '자동 문구';
    }

    renderBreakAutoConfigCard() {
        const statusEl = document.getElementById('breakAutoStatusText');
        const hintEl = document.getElementById('breakAutoHintText');
        const enabledInput = document.getElementById('breakAutoEnabledInput');
        const minutesInput = document.getElementById('breakAutoMinutesInput');
        const labelEl = document.getElementById('breakAutoPhraseLabel');
        const previewEl = document.getElementById('breakAutoPhrasePreview');
        const assignBtn = document.getElementById('missionQuickAssignBreakAutoBtn');
        const selected = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        const snapshot = this.getBreakAutoPhraseSnapshot();
        const isEnabled = this.isBreakAutoEnabled();

        if (statusEl) {
            statusEl.textContent = isEnabled ? '자동ON' : '자동OFF';
            statusEl.classList.toggle('bg-emerald-500/20', isEnabled);
            statusEl.classList.toggle('text-emerald-200', isEnabled);
            statusEl.classList.toggle('border-emerald-300/25', isEnabled);
            statusEl.classList.toggle('bg-slate-800/80', !isEnabled);
            statusEl.classList.toggle('text-slate-300', !isEnabled);
            statusEl.classList.toggle('border-slate-600/70', !isEnabled);
        }

        if (hintEl) {
            if (!snapshot) {
                hintEl.textContent = '저장 문구에서 하나를 선택해 자동 문구로 지정하면 쉬는시간마다 한 번만 자동 시작합니다.';
            } else if (!this.missionQuickPhrases.length) {
                hintEl.textContent = '저장 목록이 비어도 마지막 자동 문구는 이 브라우저에서 계속 유지됩니다.';
            } else {
                hintEl.textContent = '쉬는시간마다 문구와 타이머를 한 번만 자동으로 적용합니다.';
            }
        }

        if (enabledInput) {
            enabledInput.checked = isEnabled;
            enabledInput.disabled = !snapshot;
        }

        if (minutesInput) minutesInput.value = String(this.normalizeBreakAutoTimerMinutes(this.breakAutoConfig.timerMinutes));
        if (labelEl) labelEl.textContent = snapshot?.label || '자동 문구 없음';
        if (previewEl) previewEl.textContent = snapshot ? this.getBreakAutoSummaryText() : '문구관리에서 저장 문구를 선택해 자동 문구로 지정하세요.';
        if (assignBtn) {
            assignBtn.disabled = !selected;
            assignBtn.textContent = selected ? '선택 문구를 자동 문구로 지정' : '선택 문구를 먼저 고르세요';
        }
    }

    restoreTtsAutoAnnouncementHistory() {
        try {
            const raw = sessionStorage.getItem(this.ttsAutoAnnouncementStorageKey);
            if (!raw) {
                this.ensureTtsAutoAnnouncementHistory();
                return;
            }
            const parsed = JSON.parse(raw);
            const tokens = Array.isArray(parsed?.tokens) ? parsed.tokens.map((token) => String(token)) : [];
            this.ttsAutoAnnouncementHistory = {
                date: String(parsed?.date || ''),
                tokens,
            };
        } catch (_error) {
            this.ttsAutoAnnouncementHistory = { date: '', tokens: [] };
        }
        this.ensureTtsAutoAnnouncementHistory();
    }

    saveTtsAutoAnnouncementHistory() {
        try {
            sessionStorage.setItem(this.ttsAutoAnnouncementStorageKey, JSON.stringify(this.ttsAutoAnnouncementHistory));
        } catch (_error) {
            // sessionStorage unavailable: keep in-memory state only
        }
    }

    ensureTtsAutoAnnouncementHistory(date = new Date()) {
        const todayKey = this.getLocalDateKey(date);
        if (this.ttsAutoAnnouncementHistory.date !== todayKey) {
            this.ttsAutoAnnouncementHistory = {
                date: todayKey,
                tokens: [],
            };
            this.saveTtsAutoAnnouncementHistory();
        }
    }

    hasAutoAnnouncementToken(token, date = new Date()) {
        this.ensureTtsAutoAnnouncementHistory(date);
        return this.ttsAutoAnnouncementHistory.tokens.includes(String(token));
    }

    markAutoAnnouncementToken(token, date = new Date()) {
        this.ensureTtsAutoAnnouncementHistory(date);
        const normalizedToken = String(token);
        if (this.ttsAutoAnnouncementHistory.tokens.includes(normalizedToken)) return;
        this.ttsAutoAnnouncementHistory.tokens.push(normalizedToken);
        this.saveTtsAutoAnnouncementHistory();
    }

    normalizeTtsMinutesBefore(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return 5;
        return Math.max(0, Math.min(10, Math.round(parsed)));
    }

    normalizeTtsRate(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return 0.95;
        return Math.max(0.7, Math.min(1.3, parsed));
    }

    normalizeTtsPitch(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return 1.0;
        return Math.max(0.8, Math.min(1.2, parsed));
    }

    buildScheduleAnnouncementText(periodLabel, subjectName) {
        const safePeriodLabel = String(periodLabel || '교시').trim() || '교시';
        const safeSubjectName = String(subjectName || '수업').trim() || '수업';
        if (this.ttsMinutesBefore > 0) {
            return `${safePeriodLabel} ${this.ttsMinutesBefore}분 전입니다. ${safePeriodLabel}는 ${safeSubjectName}입니다!`;
        }
        return `${safePeriodLabel}는 ${safeSubjectName}입니다!`;
    }

    getTodayScheduleAnnouncementRows() {
        const dateKey = this.getLocalDateKey();
        return this.todaySchedule
            .filter((slot) => slot && slot.slot_type === 'period')
            .map((slot) => {
                const periodNumber = Number(slot.period);
                const periodLabel = Number.isFinite(periodNumber) && periodNumber > 0
                    ? `${periodNumber}교시`
                    : String(slot.slot_label || '').trim() || '교시';
                const rawSubject = String(slot.name || '').trim();
                const subjectName = rawSubject && rawSubject !== periodLabel ? rawSubject : '미정';
                const spokenSubject = rawSubject && rawSubject !== periodLabel ? rawSubject : '수업';
                const startTime = String(slot.startTime || '').trim();
                const startMinutes = this.timeStringToMinutes(startTime);
                if (!Number.isFinite(startMinutes)) return null;

                const announceMinutes = Math.max(0, startMinutes - this.ttsMinutesBefore);
                const rowId = String(slot.id || slot.slot_code || `${periodLabel}-${startTime}`);
                return {
                    id: rowId,
                    periodLabel,
                    subjectName,
                    spokenSubject,
                    startTime,
                    startMinutes,
                    announceMinutes,
                    announceTime: this.minutesToTimeString(announceMinutes),
                    announcementText: this.buildScheduleAnnouncementText(periodLabel, spokenSubject),
                    autoToken: `${dateKey}-${rowId}-${announceMinutes}`,
                };
            })
            .filter(Boolean)
            .sort((a, b) => a.startMinutes - b.startMinutes);
    }

    getNextScheduleAnnouncement(now = new Date()) {
        const rows = this.getTodayScheduleAnnouncementRows();
        if (!rows.length) return null;

        const nowMinutes = (now.getHours() * 60) + now.getMinutes();
        const futureRow = rows.find((row) => nowMinutes <= row.announceMinutes);
        if (futureRow) {
            return { ...futureRow, status: 'future' };
        }

        const readyRow = rows.find((row) => nowMinutes < row.startMinutes);
        if (readyRow) {
            return { ...readyRow, status: 'ready' };
        }

        return { ...rows[rows.length - 1], status: 'past' };
    }

    updateBroadcastModalTtsInfo() {
        const summaryEl = document.getElementById('broadcastScheduleSummary');
        const statusEl = document.getElementById('broadcastScheduleStatus');
        if (!summaryEl || !statusEl) return;

        const nextRow = this.getNextScheduleAnnouncement();
        const autoState = this.ttsEnabled ? `${this.ttsMinutesBefore}분 전 자동 안내 켜짐` : '자동 안내 꺼짐';
        const soundState = this.isSoundEnabled ? '소리 켜짐' : '소리 꺼짐';

        if (!nextRow) {
            summaryEl.textContent = '오늘 시간표가 없습니다.';
            statusEl.textContent = `${autoState} · ${soundState}`;
            return;
        }

        if (nextRow.status === 'past') {
            summaryEl.textContent = '오늘 자동 안내가 모두 끝났습니다.';
            statusEl.textContent = `${autoState} · ${soundState}`;
            return;
        }

        summaryEl.textContent = `${nextRow.periodLabel} · ${nextRow.subjectName} · ${nextRow.announceTime}`;
        if (nextRow.status === 'ready') {
            statusEl.textContent = `지금 읽기 가능한 시간입니다. ${autoState} · ${soundState}`;
            return;
        }
        statusEl.textContent = `${autoState} · ${soundState}`;
    }

    getAvailableSpeechVoices() {
        const synth = window.speechSynthesis || null;
        if (!synth) return [];

        const voices = synth.getVoices() || [];
        if (!voices.length) return [];

        const koreanVoices = voices.filter((voice) => String(voice.lang || '').toLowerCase().startsWith('ko'));
        if (koreanVoices.length) {
            return koreanVoices.concat(
                voices.filter((voice) => !String(voice.lang || '').toLowerCase().startsWith('ko'))
            );
        }
        return voices;
    }

    resolveTtsVoice() {
        const voices = this.getAvailableSpeechVoices();
        if (!voices.length) return null;

        return voices.find((voice) => (voice.voiceURI || voice.name) === this.ttsVoiceUri)
            || voices.find((voice) => voice.default)
            || voices[0];
    }

    createTtsUtterance(text) {
        const utterance = new SpeechSynthesisUtterance(String(text || '').trim());
        utterance.lang = 'ko-KR';
        utterance.rate = this.ttsRate;
        utterance.pitch = this.ttsPitch;
        const selectedVoice = this.resolveTtsVoice();
        if (selectedVoice) {
            utterance.voice = selectedVoice;
        }
        return utterance;
    }

    speakTtsText(text, { label = '안내', useToast = true } = {}) {
        const content = String(text || '').trim();
        if (!content) {
            if (useToast) this.showToast('읽을 문구가 없습니다.', 'error');
            return false;
        }

        const synth = window.speechSynthesis || null;
        if (!synth || typeof SpeechSynthesisUtterance === 'undefined') {
            if (useToast) this.showToast('이 브라우저는 음성 읽기를 지원하지 않습니다.', 'error');
            return false;
        }

        if (!this.isSoundEnabled) {
            if (useToast) this.showToast('소리가 꺼져 있습니다. 상단 스피커 버튼을 켜 주세요.', 'error');
            return false;
        }

        try {
            const utterance = this.createTtsUtterance(content);
            synth.cancel();
            synth.speak(utterance);
            if (useToast) this.showToast(`${label}를 읽는 중입니다.`, 'success');
            return true;
        } catch (error) {
            console.error(error);
            if (useToast) this.showToast('음성 읽기를 시작하지 못했습니다.', 'error');
            return false;
        }
    }

    fillBroadcastWithNextAnnouncement() {
        const input = document.getElementById('broadcastInput');
        if (!input) return;

        const nextRow = this.getNextScheduleAnnouncement();
        if (!nextRow || nextRow.status === 'past') {
            this.showToast('오늘 남은 교시 안내가 없습니다.', 'error');
            return;
        }

        input.value = nextRow.announcementText;
        input.focus();
        this.showToast(`${nextRow.periodLabel} 안내 문구를 불러왔습니다.`, 'success');
    }

    speakBroadcastInput() {
        const input = document.getElementById('broadcastInput');
        const text = input ? input.value : '';
        this.speakTtsText(text, { label: '안내 문구' });
    }

    checkAndTriggerScheduledAnnouncement(now = new Date()) {
        if (!this.hasLoadedData || !this.ttsEnabled) return;

        const nowMinutes = (now.getHours() * 60) + now.getMinutes();
        const targetRow = this.getTodayScheduleAnnouncementRows().find((row) => row.announceMinutes === nowMinutes);
        if (!targetRow) return;
        if (this.hasAutoAnnouncementToken(targetRow.autoToken, now)) return;

        const spoke = this.speakTtsText(targetRow.announcementText, {
            label: `${targetRow.periodLabel} 안내`,
            useToast: false,
        });
        if (!spoke) return;

        this.markAutoAnnouncementToken(targetRow.autoToken, now);
        this.showToast(`${targetRow.periodLabel} ${targetRow.subjectName} 안내를 읽었습니다.`, 'success');
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
            const numericSeconds = Number(this.timerSeconds);
            const safeSeconds = Number.isFinite(numericSeconds)
                ? Math.max(0, Math.min(Math.floor(numericSeconds), safeMax))
                : safeMax;
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
            const rawSeconds = Number(parsed.timerSeconds);
            const restoredSeconds = Number.isFinite(rawSeconds)
                ? Math.max(0, Math.min(Math.floor(rawSeconds), restoredMax))
                : restoredMax;
            const now = Date.now();
            const restoredEndAt = Number(parsed.timerEndAt);
            const shouldResume = parsed.isTimerRunning === true && Number.isFinite(restoredEndAt) && restoredEndAt > now;

            this.timerMaxSeconds = restoredMax;

            if (shouldResume) {
                this.isTimerRunning = true;
                this.timerEndAt = restoredEndAt;
                this.timerSeconds = this.getRemainingTimerSeconds(now);
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

    getRemainingTimerSeconds(referenceNow = Date.now()) {
        if (!this.isTimerRunning || !Number.isFinite(this.timerEndAt)) {
            const safeMax = this.normalizeTimerSeconds(this.timerMaxSeconds, 300);
            const current = Number(this.timerSeconds);
            return Number.isFinite(current)
                ? Math.max(0, Math.min(Math.floor(current), safeMax))
                : safeMax;
        }
        return Math.max(0, Math.ceil((this.timerEndAt - referenceNow) / 1000));
    }

    finishTimer() {
        this.timerSeconds = 0;
        this.isTimerRunning = false;
        this.stopTimerTicker();
        this.timerEndAt = null;
        this.updateTimerDisplay();
        this.saveTimerState();
        this.playAlert();
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
            const response = await this.secureFetch(
                this.buildFreshUrl(this.getApiUrl('dataUrl', '/products/dutyticker/api/data/')),
                { method: 'GET', cache: 'no-store' }
            );
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
            this.ttsEnabled = data.settings.tts_enabled === true;
            this.ttsMinutesBefore = this.normalizeTtsMinutesBefore(data.settings.tts_minutes_before);
            this.ttsVoiceUri = String(data.settings.tts_voice_uri || '').trim();
            this.ttsRate = this.normalizeTtsRate(data.settings.tts_rate);
            this.ttsPitch = this.normalizeTtsPitch(data.settings.tts_pitch);

            // Apply Theme to DOM
            this.applyThemeToDom(this.theme);
            this.applyRoleViewMode();

            const today = new Date().getDay();
            this.todaySchedule = data.schedule[today] || [];
            this.hasLoadedData = true;

            this.renderAll();
            this.checkAndTriggerScheduledAnnouncement(new Date());
        } catch (error) {
            this.hasLoadedData = false;
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
        this.requestAdaptiveLayoutRefresh();
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

        this.updateBroadcastModalTtsInfo();
        this.checkAndTriggerScheduledAnnouncement(new Date());
        this.syncBreakAutoState(new Date());

        if (periodSchedule.length === 0) {
            container.innerHTML = '<span class="dt-header-schedule-empty">오늘 시간표 없음</span>';
            return;
        }

        const now = new Date();
        const nowMinutes = (now.getHours() * 60) + now.getMinutes();
        const showAllMorningSlots = nowMinutes >= (8 * 60) && nowMinutes <= ((8 * 60) + 50);

        const normalizedSlots = periodSchedule.map((slot) => {
            const periodNumber = Number(slot.period);
            const periodLabel = Number.isFinite(periodNumber) && periodNumber > 0
                ? `${periodNumber}교시`
                : String(slot.slot_label || '').trim() || '교시';
            const rawSubject = String(slot.name || '').trim();
            const subjectName = rawSubject && rawSubject !== periodLabel ? rawSubject : '미정';
            const startTime = String(slot.startTime || '').trim();
            const endTime = String(slot.endTime || '').trim();
            const startMinutes = this.timeStringToMinutes(startTime);
            const endMinutes = this.timeStringToMinutes(endTime);
            const hasTimeRange = Number.isFinite(startMinutes) && Number.isFinite(endMinutes);
            const isCurrent = hasTimeRange && nowMinutes >= startMinutes && nowMinutes < endMinutes;
            const isUpcoming = hasTimeRange && nowMinutes >= (startMinutes - 10) && nowMinutes < startMinutes;

            return {
                periodLabel,
                subjectName,
                startTime,
                endTime,
                startMinutes,
                hasTimeRange,
                isCurrent,
                isUpcoming,
            };
        });

        if (showAllMorningSlots) {
            container.innerHTML = normalizedSlots.map((slot) => {
                const titleText = slot.hasTimeRange
                    ? `${slot.periodLabel} · ${slot.subjectName} (${slot.startTime}-${slot.endTime})`
                    : `${slot.periodLabel} · ${slot.subjectName}`;
                const chipClass = slot.isCurrent
                    ? 'dt-header-schedule-item is-current'
                    : (slot.isUpcoming ? 'dt-header-schedule-item is-upcoming' : 'dt-header-schedule-item');
                return `
                    <span class="${chipClass}" title="${this.escapeHtml(titleText)}">
                        <span class="dt-header-schedule-period">${this.escapeHtml(slot.periodLabel)}</span>
                        <span class="dt-header-schedule-sep">·</span>
                        <span class="dt-header-schedule-subject">${this.escapeHtml(slot.subjectName)}</span>
                    </span>
                `;
            }).join('');
            return;
        }

        const candidateSlots = normalizedSlots.filter((slot) => slot.hasTimeRange && (slot.isCurrent || slot.isUpcoming));

        if (!candidateSlots.length) {
            const app = document.getElementById('mainAppContainer');
            const isWindowedDense = app
                && app.getAttribute('data-display-mode') === 'windowed'
                && app.getAttribute('data-layout-density') !== 'hero';
            const emptyMessage = isWindowedDense ? '다음 교시 대기 중' : '다음 교시 10분 전부터 표시됩니다';
            container.innerHTML = `<span class="dt-header-schedule-empty">${emptyMessage}</span>`;
            return;
        }

        const focusSlot = candidateSlots.find((slot) => slot.isCurrent)
            || [...candidateSlots].sort((a, b) => a.startMinutes - b.startMinutes)[0];

        const chipClass = `dt-header-schedule-item ${focusSlot.isCurrent ? 'is-current' : 'is-upcoming'}`;
        const periodText = focusSlot.isUpcoming ? `곧 ${focusSlot.periodLabel}` : focusSlot.periodLabel;
        const titleText = `${focusSlot.periodLabel} · ${focusSlot.subjectName} (${focusSlot.startTime}-${focusSlot.endTime})`;

        container.innerHTML = `
            <span class="${chipClass}" title="${this.escapeHtml(titleText)}">
                <span class="dt-header-schedule-period">${this.escapeHtml(periodText)}</span>
                <span class="dt-header-schedule-sep">·</span>
                <span class="dt-header-schedule-subject">${this.escapeHtml(focusSlot.subjectName)}</span>
            </span>
        `;
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
        this.requestAdaptiveLayoutRefresh();
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
        this.roleViewMode = this.normalizeRoleViewMode(this.roleViewMode);

        if (app) app.setAttribute('data-role-view-mode', this.roleViewMode);
        this.updateRoleCardSubtitle();
    }

    normalizeSpotlightStudentId(rawStudentId = this.spotlightStudentId) {
        const numericId = Number(rawStudentId);
        return Number.isFinite(numericId) && numericId > 0 ? numericId : null;
    }

    getSpotlightStudentName() {
        const spotlightStudentId = this.normalizeSpotlightStudentId();
        if (spotlightStudentId === null) return '';

        const spotlightStudent = this.students.find((student) => Number(student.id) === spotlightStudentId);
        return spotlightStudent ? spotlightStudent.name : '';
    }

    updateRoleCardSubtitle(spotlightRoleCount = 0) {
        const subtitle = document.getElementById('roleCardSubtitle');
        if (!subtitle) return;

        const spotlightStudentName = this.getSpotlightStudentName();
        if (spotlightStudentName && spotlightRoleCount > 0) {
            subtitle.textContent = `${spotlightStudentName} 학생 역할 ${spotlightRoleCount}개를 지금 강조해서 보여줍니다.`;
            return;
        }

        if (spotlightStudentName) {
            subtitle.textContent = `${spotlightStudentName} 학생은 아직 배정된 역할이 없습니다.`;
            return;
        }

        subtitle.textContent = this.roleViewMode === 'readable'
            ? '멀리서도 보이도록 역할과 이름을 크게 보여줍니다.'
            : '핵심 역할과 담당 학생만 크게 보여줍니다.';
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
            this.updateRoleCardSubtitle();
            return;
        }

        const spotlightStudentId = this.normalizeSpotlightStudentId();
        const spotlightRoleIdSet = new Set(
            spotlightStudentId === null
                ? []
                : this.roles
                    .filter((role) => Number(role.assigneeId) === spotlightStudentId)
                    .map((role) => Number(role.id))
        );
        const hasSpotlightRole = spotlightRoleIdSet.size > 0;

        const orderedRoles = [...this.roles].sort((a, b) => {
            const aSpot = spotlightRoleIdSet.has(Number(a.id)) ? 0 : 1;
            const bSpot = spotlightRoleIdSet.has(Number(b.id)) ? 0 : 1;
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
            const isSpotlightRole = spotlightRoleIdSet.has(numericRoleId);
            const spotlightClass = isSpotlightRole
                ? 'dt-role-current-spotlight'
                : (hasSpotlightRole ? 'dt-role-current-muted' : '');
            const spotlightBadge = isSpotlightRole
                ? '<span class="dt-role-spotlight-badge inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black border"><i class="fa-solid fa-bolt text-[9px]"></i>현재 강조</span>'
                : '';
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

        this.updateRoleCardSubtitle(spotlightRoleIdSet.size);
        this.ensureRoleTickerRunning();
        const activeRow = this.paintRoleTickerFocus({ force: true });
        if (activeRow) this.scrollRoleRowIntoViewIfNeeded(activeRow);
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

    clearRoleTickerClasses(rows = this.getRoleRows()) {
        rows.forEach((row) => {
            row.classList.remove('dt-role-cycle-focus');
            row.classList.remove('dt-role-cycle-enter');
        });
    }

    triggerRoleTickerEntry(row) {
        if (!row) return;
        row.classList.remove('dt-role-cycle-enter');
        void row.offsetWidth;
        row.classList.add('dt-role-cycle-enter');
        window.setTimeout(() => row.classList.remove('dt-role-cycle-enter'), 820);
    }

    isRoleRowFullyVisible(row) {
        if (!row) return false;
        const container = document.getElementById('mainRoleList');
        if (!container) return true;

        const rowRect = row.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        return rowRect.top >= (containerRect.top + 8) && rowRect.bottom <= (containerRect.bottom - 8);
    }

    scrollRoleRowIntoViewIfNeeded(row) {
        if (!row || this.isRoleRowFullyVisible(row)) return;
        const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        row.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'nearest', inline: 'nearest' });
    }

    paintRoleTickerFocus({ force = false, animateEntry = false } = {}) {
        const rows = this.getRoleRows();
        if (!rows.length) return null;
        if (!this.roleTickerEnabled) {
            this.clearRoleTickerClasses(rows);
            return null;
        }

        if (this.roleTickerIndex < 0 || this.roleTickerIndex >= rows.length || force) {
            this.roleTickerIndex = Math.max(0, Math.min(rows.length - 1, this.roleTickerIndex));
        }

        let activeRow = null;
        rows.forEach((row, index) => {
            const isActive = index === this.roleTickerIndex;
            row.classList.toggle('dt-role-cycle-focus', isActive);
            if (isActive) activeRow = row;
            else row.classList.remove('dt-role-cycle-enter');
        });

        if (animateEntry) this.triggerRoleTickerEntry(activeRow);
        return activeRow;
    }

    stepRoleTicker() {
        const rows = this.getRoleRows();
        if (rows.length <= 1) return;

        this.roleTickerIndex = (this.roleTickerIndex + 1) % rows.length;
        const activeRow = this.paintRoleTickerFocus({ animateEntry: true });
        this.scrollRoleRowIntoViewIfNeeded(activeRow);
    }

    toggleRoleTicker() {
        this.roleTickerEnabled = !this.roleTickerEnabled;
        this.updateRoleTickerUI();
        this.saveRoleTickerState();

        if (!this.roleTickerEnabled) {
            this.stopRoleTicker();
            this.clearRoleTickerClasses();
            return;
        }

        this.roleTickerIndex = -1;
        this.ensureRoleTickerRunning();
        this.stepRoleTicker();
    }

    applyStudentGridLayoutMode() {
        const grid = document.getElementById('mainStudentGrid');
        const card = document.getElementById('mainStudentCard');
        const app = document.getElementById('mainAppContainer');
        const gridWrap = document.getElementById('mainStudentGridWrap');
        if (!grid || !card) return;

        const isDesktop = window.matchMedia('(min-width: 1024px)').matches;
        const studentCount = this.students.length;
        const shouldUseComfortFit = isDesktop && studentCount > 0 && studentCount <= 36;
        const layoutDensity = app ? String(app.getAttribute('data-layout-density') || 'presentation') : 'presentation';
        const gridWrapHeight = gridWrap ? gridWrap.getBoundingClientRect().height : 0;
        let gridColumns = '5';

        if (
            shouldUseComfortFit
            && !this.missionPanelCollapsed
            && (
                layoutDensity === 'compact'
                || gridWrapHeight < 210
                || studentCount >= 21
            )
        ) {
            gridColumns = '6';
        }

        grid.classList.toggle('dt-student-grid-fit-25', shouldUseComfortFit);
        if (shouldUseComfortFit) grid.dataset.gridColumns = gridColumns;
        else delete grid.dataset.gridColumns;
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

        const spotlightStudentId = this.normalizeSpotlightStudentId();

        container.innerHTML = this.students.map(student => {
            const isDone = student.status === 'done';
            const studentId = Number.isFinite(Number(student.id)) ? Number(student.id) : 0;
            const safeStudentNumber = this.escapeHtml(student.number);
            const safeStudentName = this.escapeHtml(student.name);
            const isSpotlight = spotlightStudentId !== null && spotlightStudentId === Number(student.id);
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
        const currentSpotlightStudentId = this.normalizeSpotlightStudentId();
        const nextStudentId = currentSpotlightStudentId === Number(studentId) ? null : Number(studentId);
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
        const remaining = this.getRemainingTimerSeconds();

        if (remaining <= 0) {
            this.finishTimer();
            return;
        }

        if (remaining !== this.timerSeconds) {
            this.timerSeconds = remaining;
            this.updateTimerDisplay();
            this.saveTimerState();
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
            this.timerSeconds = this.getRemainingTimerSeconds();
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

        const baseSeconds = this.isTimerRunning ? this.getRemainingTimerSeconds() : this.timerSeconds;
        const nextSeconds = baseSeconds + (Math.floor(minuteValue) * 60);
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
        const safeSeconds = Math.max(0, Math.floor(Number(this.timerSeconds) || 0));
        const m = Math.floor(safeSeconds / 60);
        const s = safeSeconds % 60;
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

    showToast(message, tone = 'info') {
        const toast = document.getElementById('dtActionToast');
        if (!toast) return;

        toast.textContent = String(message || '').trim() || '작업을 완료했습니다.';
        toast.classList.remove('border-emerald-300/40', 'bg-emerald-500/90', 'border-rose-300/40', 'bg-rose-500/92', 'border-slate-700', 'bg-slate-900/92');
        if (tone === 'success') {
            toast.classList.add('border-emerald-300/40', 'bg-emerald-500/90');
        } else if (tone === 'error') {
            toast.classList.add('border-rose-300/40', 'bg-rose-500/92');
        } else {
            toast.classList.add('border-slate-700', 'bg-slate-900/92');
        }

        toast.classList.remove('hidden', 'opacity-0', 'translate-y-2');
        toast.classList.add('opacity-100', 'translate-y-0');
        if (this.toastTimer) clearTimeout(this.toastTimer);
        this.toastTimer = setTimeout(() => this.hideToast(), 2400);
    }

    hideToast() {
        const toast = document.getElementById('dtActionToast');
        if (!toast) return;
        toast.classList.remove('opacity-100', 'translate-y-0');
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.classList.add('hidden'), 220);
    }

    requestResetConfirmation({ title, message, confirmLabel, onConfirm }) {
        this.pendingResetAction = typeof onConfirm === 'function' ? onConfirm : null;
        const titleEl = document.getElementById('resetConfirmTitle');
        const messageEl = document.getElementById('resetConfirmMessage');
        const actionBtn = document.getElementById('resetConfirmActionBtn');
        if (titleEl) titleEl.textContent = title || '확인';
        if (messageEl) messageEl.textContent = message || '이 작업을 진행할까요?';
        if (actionBtn) actionBtn.textContent = confirmLabel || '확인';
        this.openModal('resetConfirmModal');
    }

    cancelPendingResetAction() {
        this.pendingResetAction = null;
        this.closeModal('resetConfirmModal');
    }

    async confirmPendingResetAction() {
        const action = this.pendingResetAction;
        this.pendingResetAction = null;
        this.closeModal('resetConfirmModal');
        if (typeof action === 'function') await action();
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
        const spotlightStudentId = this.normalizeSpotlightStudentId();
        const spotlightIndex = spotlightStudentId === null
            ? -1
            : this.callModeRoles.findIndex((role) => Number(role.assigneeId) === spotlightStudentId);

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
        this.updateBroadcastModalTtsInfo();
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
            this.showToast(msg ? '알림사항을 저장했습니다.' : '알림사항을 비웠습니다.', 'success');
        } catch (error) {
            console.error(error);
            this.broadcastMessage = prevMessage;
            this.isBroadcasting = prevState;
            this.renderNotices();
            this.showToast(error?.message || '알림사항을 저장하지 못했습니다.', 'error');
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

        const insertPlainText = (text) => {
            const selection = window.getSelection();
            if (!selection || !selection.rangeCount) return;
            const range = selection.getRangeAt(0);
            range.deleteContents();
            const node = document.createTextNode(text);
            range.insertNode(node);
            range.setStartAfter(node);
            range.collapse(true);
            selection.removeAllRanges();
            selection.addRange(range);
        };

        const stripPasteFormatting = (event) => {
            event.preventDefault();
            const text = event.clipboardData?.getData('text/plain') || '';
            if (typeof document.execCommand === 'function') {
                document.execCommand('insertText', false, text);
                return;
            }
            insertPlainText(text);
        };

        titleEl.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                titleEl.blur();
            }
        });
        descEl.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter') return;
            if (event.shiftKey) {
                event.preventDefault();
                insertPlainText('\n');
                return;
            }
            event.preventDefault();
            descEl.blur();
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

    restoreMissionQuickPhrase() {
        try {
            const raw = localStorage.getItem(this.missionQuickPhraseStorageKey);
            if (!raw) {
                this.missionQuickPhrases = [];
                this.missionQuickPhrase = null;
                this.missionQuickSelectedId = null;
                return;
            }

            const parsed = JSON.parse(raw);
            const rawList = Array.isArray(parsed)
                ? parsed
                : (parsed && typeof parsed === 'object' ? [parsed] : []);
            const normalizedList = rawList
                .map((item, index) => {
                    const title = this.sanitizeMissionText(item?.title || '', 'title');
                    const desc = this.sanitizeMissionText(item?.desc || '', 'desc');
                    if (!title && !desc) return null;
                    const label = this.buildMissionQuickPhraseLabel(title, desc, String(item?.label || ''));
                    return {
                        id: String(item?.id || `legacy-${index + 1}`),
                        label,
                        title,
                        desc,
                        savedAt: Number(item?.savedAt) || Date.now(),
                    };
                })
                .filter((item) => !!item)
                .slice(0, this.missionQuickPhraseLimit);

            this.missionQuickPhrases = normalizedList;
            this.missionQuickPhrase = normalizedList[0] || null;
            this.missionQuickSelectedId = normalizedList[0]?.id || null;
        } catch (error) {
            console.warn('DutyTicker: failed to restore mission quick phrase', error);
            this.missionQuickPhrases = [];
            this.missionQuickPhrase = null;
            this.missionQuickSelectedId = null;
        }
    }

    saveMissionQuickPhraseToStorage() {
        try {
            if (!this.missionQuickPhrases.length) {
                localStorage.removeItem(this.missionQuickPhraseStorageKey);
                return;
            }
            localStorage.setItem(this.missionQuickPhraseStorageKey, JSON.stringify(this.missionQuickPhrases));
        } catch (error) {
            console.warn('DutyTicker: failed to save mission quick phrase', error);
        }
    }

    buildMissionQuickPhraseLabel(title, desc, preferredLabel = '') {
        const cleanPreferred = String(preferredLabel || '').trim();
        if (cleanPreferred) return cleanPreferred.slice(0, 14);

        const source = String(title || desc || '문구').trim();
        if (!source) return '문구';
        return source.length > 14 ? `${source.slice(0, 14)}…` : source;
    }

    formatMissionQuickPhraseSavedAt(savedAt) {
        const date = new Date(Number(savedAt) || Date.now());
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    getCurrentMissionQuickPhraseDraft() {
        const titleEl = document.getElementById('mainMissionTitle');
        const descEl = document.getElementById('mainMissionDesc');
        return {
            title: this.sanitizeMissionText(titleEl ? titleEl.innerText : this.missionTitle, 'title'),
            desc: this.sanitizeMissionText(descEl ? descEl.innerText : this.missionDesc, 'desc'),
        };
    }

    getMissionQuickPhraseFormValues() {
        const titleInput = document.getElementById('missionQuickTitleInput');
        const descInput = document.getElementById('missionQuickDescInput');
        return {
            title: this.sanitizeMissionText(titleInput ? titleInput.value : '', 'title'),
            desc: this.sanitizeMissionText(descInput ? descInput.value : '', 'desc'),
        };
    }

    setMissionQuickPhraseFormValues({ title = '', desc = '' } = {}) {
        const titleInput = document.getElementById('missionQuickTitleInput');
        const descInput = document.getElementById('missionQuickDescInput');
        if (titleInput) titleInput.value = title;
        if (descInput) descInput.value = desc;
    }

    getMissionQuickPhraseById(phraseId) {
        if (!phraseId) return null;
        return this.missionQuickPhrases.find((item) => item.id === String(phraseId)) || null;
    }

    syncBreakAutoSnapshotFromSavedPhrase() {
        const phraseId = String(this.breakAutoConfig.phraseId || '').trim();
        if (!phraseId) return;
        const matchedPhrase = this.getMissionQuickPhraseById(phraseId);
        if (!matchedPhrase) return;

        this.breakAutoConfig.phraseSnapshot = {
            label: matchedPhrase.label,
            title: matchedPhrase.title,
            desc: matchedPhrase.desc,
        };
        this.saveBreakAutoConfig();
    }

    syncMissionQuickPhraseSelection(selectedId = null) {
        const targetId = String(selectedId || this.missionQuickSelectedId || '').trim();
        const selected = this.getMissionQuickPhraseById(targetId) || this.missionQuickPhrases[0] || null;
        this.missionQuickSelectedId = selected ? selected.id : null;
        return selected;
    }

    createMissionQuickPhraseEntry(title, desc) {
        const now = Date.now();
        const duplicateCount = this.missionQuickPhrases.filter(
            (item) => item.title === title && item.desc === desc
        ).length;
        const baseLabel = this.buildMissionQuickPhraseLabel(title, desc);
        const label = duplicateCount > 0 ? `${baseLabel} (${duplicateCount + 1})` : baseLabel;
        return {
            id: `phrase-${now}-${Math.random().toString(36).slice(2, 8)}`,
            label,
            title,
            desc,
            savedAt: now,
        };
    }

    setMissionQuickPhraseModalHint(message) {
        const hintEl = document.getElementById('missionQuickModalHint');
        if (hintEl) hintEl.textContent = message;
    }

    updateMissionQuickPhraseUI() {
        const applyBtn = document.getElementById('missionQuickApplyBtn');
        const applyLabel = document.getElementById('missionQuickApplyLabel');
        const autoBadge = document.getElementById('missionQuickAutoBadge');
        const saveBtn = document.getElementById('missionQuickSaveBtn');
        if (!applyBtn) return;

        const count = this.missionQuickPhrases.length;
        applyBtn.disabled = false;
        applyBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        if (applyLabel) {
            applyLabel.textContent = count > 0 ? `문구관리(${count})` : '문구관리';
        } else {
            applyBtn.textContent = count > 0 ? `문구관리(${count})` : '문구관리';
        }
        applyBtn.setAttribute('title', count > 0 ? '저장한 문구를 불러오고 수정하거나 삭제합니다.' : '저장한 문구를 관리합니다.');
        if (saveBtn) saveBtn.setAttribute('title', count > 0 ? `현재 문구를 새 항목으로 저장 (저장 ${count}개)` : '현재 문구를 새 항목으로 저장');
        if (autoBadge) autoBadge.classList.toggle('hidden', !this.isBreakAutoEnabled());
        this.renderBreakAutoConfigCard();
    }

    renderMissionQuickPhraseModal() {
        const listEl = document.getElementById('missionQuickPhraseList');
        if (!listEl) return;

        const countEl = document.getElementById('missionQuickModalCount');
        const updateBtn = document.getElementById('missionQuickUpdateBtn');
        const applyBtn = document.getElementById('missionQuickApplySelectedBtn');
        const deleteBtn = document.getElementById('missionQuickDeleteBtn');
        const deleteAllBtn = document.getElementById('missionQuickDeleteAllBtn');
        const count = this.missionQuickPhrases.length;
        const selected = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);

        this.renderBreakAutoConfigCard();

        if (countEl) countEl.textContent = `저장 ${count}개`;
        if (updateBtn) updateBtn.disabled = !selected;
        if (applyBtn) applyBtn.disabled = !selected;
        if (deleteBtn) deleteBtn.disabled = !selected;
        if (deleteAllBtn) deleteAllBtn.disabled = count === 0;

        if (!count) {
            listEl.innerHTML = `
                <div class="rounded-2xl border border-dashed border-slate-700 bg-slate-900/45 p-5 text-center">
                    <p class="text-sm font-black text-slate-200">저장된 문구가 없습니다.</p>
                    <p class="mt-1 text-xs text-slate-400">아래 편집칸에서 새 문구를 저장하거나 현재 문구를 먼저 가져오세요.</p>
                </div>
            `;
            this.setMissionQuickPhraseModalHint('현재 문구를 불러오거나 새 문구를 입력해 저장하세요.');
            return;
        }

        listEl.innerHTML = this.missionQuickPhrases.map((item) => {
            const isSelected = selected && item.id === selected.id;
            const previewText = item.desc || item.title || '저장 문구';
            return `
                <button type="button"
                    onclick="window.dtApp.selectMissionQuickPhrase('${item.id}')"
                    class="dt-phrase-list-item ${isSelected ? 'is-selected' : ''} w-full rounded-2xl border border-slate-700 bg-slate-900/55 px-4 py-3 text-left transition hover:bg-slate-800/80">
                    <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                            <p class="text-sm font-black text-white break-keep">${this.escapeHtml(item.label)}</p>
                            <p class="mt-1 text-xs leading-relaxed text-slate-400 break-words">${this.escapeHtml(previewText)}</p>
                        </div>
                        <span class="shrink-0 text-[10px] font-black text-slate-500">${this.escapeHtml(this.formatMissionQuickPhraseSavedAt(item.savedAt))}</span>
                    </div>
                </button>
            `;
        }).join('');

        this.setMissionQuickPhraseModalHint(selected
            ? '선택한 문구를 적용하거나 수정, 삭제할 수 있습니다.'
            : '목록에서 문구를 하나 선택하세요.');
    }

    openMissionQuickPhraseModal() {
        const selected = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        if (selected) this.setMissionQuickPhraseFormValues(selected);
        else this.loadCurrentMissionIntoQuickPhraseForm();
        this.renderMissionQuickPhraseModal();
        this.openModal('missionQuickPhraseModal');
        const titleInput = document.getElementById('missionQuickTitleInput');
        if (titleInput) setTimeout(() => titleInput.focus(), 30);
    }

    closeMissionQuickPhraseModal() {
        this.closeModal('missionQuickPhraseModal');
    }

    selectMissionQuickPhrase(phraseId) {
        const selected = this.syncMissionQuickPhraseSelection(phraseId);
        if (!selected) return;
        this.setMissionQuickPhraseFormValues(selected);
        this.renderMissionQuickPhraseModal();
    }

    loadCurrentMissionIntoQuickPhraseForm() {
        const draft = this.getCurrentMissionQuickPhraseDraft();
        this.setMissionQuickPhraseFormValues(draft);
        this.setMissionQuickPhraseModalHint('현재 화면 문구를 편집칸으로 가져왔습니다. 새 항목 저장 또는 선택 항목 수정이 가능합니다.');
    }

    saveMissionQuickPhraseFromCurrent() {
        const { title, desc } = this.getCurrentMissionQuickPhraseDraft();
        if (!title && !desc) {
            this.showToast('저장할 문구가 없습니다.', 'error');
            return;
        }

        const entry = this.createMissionQuickPhraseEntry(title, desc);
        this.missionQuickPhrases.unshift(entry);
        if (this.missionQuickPhrases.length > this.missionQuickPhraseLimit) {
            this.missionQuickPhrases = this.missionQuickPhrases.slice(0, this.missionQuickPhraseLimit);
        }

        this.missionQuickPhrase = this.missionQuickPhrases[0] || null;
        this.missionQuickSelectedId = entry.id;
        this.saveMissionQuickPhraseToStorage();
        this.syncBreakAutoSnapshotFromSavedPhrase();
        this.updateMissionQuickPhraseUI();
        this.setMissionQuickPhraseFormValues(entry);
        this.renderMissionQuickPhraseModal();
        this.showToast(`반복 문구를 저장했습니다. (총 ${this.missionQuickPhrases.length}개)`, 'success');
    }

    createMissionQuickPhraseFromModal() {
        const { title, desc } = this.getMissionQuickPhraseFormValues();
        if (!title && !desc) {
            this.showToast('저장할 문구를 입력해 주세요.', 'error');
            return;
        }

        const entry = this.createMissionQuickPhraseEntry(title, desc);
        this.missionQuickPhrases.unshift(entry);
        if (this.missionQuickPhrases.length > this.missionQuickPhraseLimit) {
            this.missionQuickPhrases = this.missionQuickPhrases.slice(0, this.missionQuickPhraseLimit);
        }

        this.missionQuickPhrase = this.missionQuickPhrases[0] || null;
        this.missionQuickSelectedId = entry.id;
        this.saveMissionQuickPhraseToStorage();
        this.syncBreakAutoSnapshotFromSavedPhrase();
        this.updateMissionQuickPhraseUI();
        this.setMissionQuickPhraseFormValues(entry);
        this.renderMissionQuickPhraseModal();
        this.setMissionQuickPhraseModalHint('새 문구를 저장했습니다.');
        this.showToast('새 문구를 저장했습니다.', 'success');
    }

    updateSelectedMissionQuickPhrase() {
        const selected = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        if (!selected) {
            this.showToast('수정할 문구를 먼저 선택해 주세요.', 'error');
            return;
        }

        const { title, desc } = this.getMissionQuickPhraseFormValues();
        if (!title && !desc) {
            this.showToast('저장할 문구를 입력해 주세요.', 'error');
            return;
        }

        const currentIndex = this.missionQuickPhrases.findIndex((item) => item.id === selected.id);
        if (currentIndex < 0) {
            this.showToast('선택한 문구를 찾지 못했습니다.', 'error');
            return;
        }

        const updated = {
            ...selected,
            label: this.buildMissionQuickPhraseLabel(title, desc),
            title,
            desc,
            savedAt: Date.now(),
        };

        this.missionQuickPhrases.splice(currentIndex, 1);
        this.missionQuickPhrases.unshift(updated);
        this.missionQuickPhrase = updated;
        this.missionQuickSelectedId = updated.id;
        this.saveMissionQuickPhraseToStorage();
        this.syncBreakAutoSnapshotFromSavedPhrase();
        this.updateMissionQuickPhraseUI();
        this.setMissionQuickPhraseFormValues(updated);
        this.renderMissionQuickPhraseModal();
        this.setMissionQuickPhraseModalHint('선택한 문구를 수정했습니다.');
        this.showToast('선택한 문구를 수정했습니다.', 'success');
    }

    async applyMissionQuickPhrase(phraseId = null) {
        const selected = phraseId
            ? this.getMissionQuickPhraseById(phraseId)
            : this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        if (!selected) {
            this.showToast('적용할 문구를 먼저 선택해 주세요.', 'error');
            return;
        }

        const selectedIndex = this.missionQuickPhrases.findIndex((item) => item.id === selected.id);
        this.missionQuickPhrase = selected;
        this.missionQuickSelectedId = selected.id;

        if (selectedIndex > 0) {
            this.missionQuickPhrases.splice(selectedIndex, 1);
            this.missionQuickPhrases.unshift(selected);
            this.saveMissionQuickPhraseToStorage();
            this.syncBreakAutoSnapshotFromSavedPhrase();
            this.updateMissionQuickPhraseUI();
        }

        await this.handleUpdateMission({
            title: selected.title,
            desc: selected.desc,
        });
        this.setMissionQuickPhraseFormValues(selected);
        this.renderMissionQuickPhraseModal();
        this.closeMissionQuickPhraseModal();
        this.showToast(`'${selected.label}' 문구를 적용했습니다.`, 'success');
    }

    deleteSelectedMissionQuickPhrase() {
        const selected = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        if (!selected) {
            this.showToast('삭제할 문구를 먼저 선택해 주세요.', 'error');
            return;
        }

        this.requestResetConfirmation({
            title: '문구 삭제',
            message: `'${selected.label}' 문구를 삭제할까요?`,
            confirmLabel: '선택 삭제',
            onConfirm: async () => {
                this.missionQuickPhrases = this.missionQuickPhrases.filter((item) => item.id !== selected.id);
                this.missionQuickPhrase = this.missionQuickPhrases[0] || null;
                this.missionQuickSelectedId = this.missionQuickPhrases[0]?.id || null;
                this.saveMissionQuickPhraseToStorage();
                this.updateMissionQuickPhraseUI();

                const nextSelected = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
                if (nextSelected) this.setMissionQuickPhraseFormValues(nextSelected);
                else this.loadCurrentMissionIntoQuickPhraseForm();
                this.renderMissionQuickPhraseModal();
                this.setMissionQuickPhraseModalHint('선택한 문구를 삭제했습니다.');
                this.showToast('선택한 문구를 삭제했습니다.', 'success');
            },
        });
    }

    clearMissionQuickPhrases() {
        if (!this.missionQuickPhrases.length) return;
        this.requestResetConfirmation({
            title: '문구 전체 삭제',
            message: '저장한 문구를 모두 삭제할까요?',
            confirmLabel: '전체 삭제',
            onConfirm: async () => {
                this.missionQuickPhrases = [];
                this.missionQuickPhrase = null;
                this.missionQuickSelectedId = null;
                this.saveMissionQuickPhraseToStorage();
                this.updateMissionQuickPhraseUI();
                this.loadCurrentMissionIntoQuickPhraseForm();
                this.renderMissionQuickPhraseModal();
                this.setMissionQuickPhraseModalHint('저장 문구를 모두 비웠습니다.');
                this.showToast('저장 문구를 모두 비웠습니다.', 'success');
            },
        });
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
            const sizeLabelMap = {
                xxxs: '가장작게',
                xxs: '최소',
                xs: '아주작게',
                sm: '작게',
                md: '보통',
                lg: '크게',
                xl: '아주크게',
                xxl: '최대',
                xxxl: '가장크게',
            };
            label.textContent = sizeLabelMap[this.missionFontSize] || '보통';
        }

        this.requestAdaptiveLayoutRefresh();
    }

    changeMissionFontSize(direction = 0) {
        const step = Number(direction);
        if (!Number.isFinite(step) || step === 0) return;
        const currentIndex = this.missionFontSizeOrder.indexOf(this.missionFontSize);
        const defaultIndex = this.missionFontSizeOrder.indexOf('md');
        const safeIndex = currentIndex >= 0 ? currentIndex : (defaultIndex >= 0 ? defaultIndex : 0);
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
        this.requestResetConfirmation({
            title: '오늘의 역할 초기화',
            message: '오늘의 역할에 표시된 학생 이름과 완료 표시를 비웁니다.',
            confirmLabel: '역할 배정 비우기',
            onConfirm: async () => this.performResetRoleAssignments(),
        });
    }

    async performResetRoleAssignments() {
        if (this.roleRotateInFlight) return;
        const resetBtn = document.getElementById('roleResetAssignmentsBtn') || document.getElementById('roleRotateNowBtn');

        try {
            this.roleRotateInFlight = true;
            if (resetBtn) resetBtn.disabled = true;

            const response = await this.secureFetch(
                this.getApiUrl('resetAssignmentsUrl', '/products/dutyticker/api/assignments/reset/'),
                { method: 'POST' }
            );
            await this.parseJsonResponse(response, '학생 배정 초기화에 실패했습니다.');
            await this.loadData();
            this.showToast('오늘의 역할 배정을 비웠습니다.', 'success');
        } catch (error) {
            console.error(error);
            this.showToast(error?.message || '학생 배정 초기화에 실패했습니다. 잠시 후 다시 시도해 주세요.', 'error');
        } finally {
            this.roleRotateInFlight = false;
            if (resetBtn) resetBtn.disabled = false;
        }
    }

    async resetStudentMissionProgress() {
        if (this.missionResetInFlight) return;
        this.requestResetConfirmation({
            title: '미션 현황 초기화',
            message: '미션현황 체크를 모두 해제합니다.',
            confirmLabel: '미션 현황 초기화',
            onConfirm: async () => this.performResetStudentMissionProgress(),
        });
    }

    async performResetStudentMissionProgress() {
        if (this.missionResetInFlight) return;
        const resetBtn = document.getElementById('missionProgressResetBtn');

        try {
            this.missionResetInFlight = true;
            if (resetBtn) resetBtn.disabled = true;

            const response = await this.secureFetch(
                this.getApiUrl('resetStudentMissionsUrl', '/products/dutyticker/api/students/reset-mission/'),
                { method: 'POST' }
            );
            await this.parseJsonResponse(response, '학생 미션 상태 초기화에 실패했습니다.');
            await this.loadData();
            this.showToast('미션현황 체크를 모두 해제했습니다.', 'success');
        } catch (error) {
            console.error(error);
            this.showToast(error?.message || '학생 미션 상태 초기화에 실패했습니다. 잠시 후 다시 시도해 주세요.', 'error');
        } finally {
            this.missionResetInFlight = false;
            if (resetBtn) resetBtn.disabled = false;
        }
    }

    async resetToMockup() {
        this.requestResetConfirmation({
            title: '기본 데이터로 초기화',
            message: '현재 학급 상태를 기본 데이터로 되돌립니다.',
            confirmLabel: '기본값으로 되돌리기',
            onConfirm: async () => {
                try {
                    const response = await this.secureFetch(this.getApiUrl('resetUrl', '/products/dutyticker/api/reset/'), { method: 'POST' });
                    await this.parseJsonResponse(response, '데이터 초기화에 실패했습니다.');
                    this.pauseTimer();
                    this.timerMaxSeconds = 300;
                    this.timerSeconds = 300;
                    this.syncCustomTimerInput();
                    this.updateTimerDisplay();
                    this.saveTimerState();
                    await this.loadData();
                    this.showToast('기본 데이터로 초기화했습니다.', 'success');
                } catch (error) {
                    console.error(error);
                    this.showToast(error?.message || '데이터 초기화에 실패했습니다. 잠시 후 다시 시도해 주세요.', 'error');
                }
            },
        });
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
                this.bgmVolumePercent = this.bgmDefaultVolumePercent;
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
            this.bgmVolumePercent = this.normalizeBgmVolumePercent(parsed.volumePercent, this.bgmDefaultVolumePercent);

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

    normalizeBgmVolumePercent(value, fallback = this.bgmDefaultVolumePercent) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return fallback;
        const rounded = Math.round(numeric);
        return Math.max(0, Math.min(200, rounded));
    }

    getBgmMasterVolumeGain() {
        return this.normalizeBgmVolumePercent(this.bgmVolumePercent, this.bgmDefaultVolumePercent) / 100;
    }

    getBgmTrackTargetVolume(track) {
        const trackVolume = Number(track?.volume);
        const baseVolume = Math.max(0.08, Math.min(0.32, Number.isFinite(trackVolume) ? trackVolume : 0.16));
        const gain = this.getBgmMasterVolumeGain();
        // Keep classroom TV output comfortably audible even on quieter speakers.
        return Math.max(0, Math.min(this.bgmTrackVolumeCap, baseVolume * this.bgmGainBoost * gain));
    }

    getSoundEffectVolume(volume) {
        const numeric = Number(volume);
        const baseVolume = Number.isFinite(numeric) ? numeric : 0.2;
        const masterGain = this.getBgmMasterVolumeGain();
        return Math.max(0, Math.min(this.soundEffectVolumeCap, baseVolume * this.soundEffectGainBoost * masterGain));
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
        const targetVolume = this.getSoundEffectVolume(vol);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = waveType;
        osc.frequency.setValueAtTime(freq, start);
        gain.gain.setValueAtTime(0, start);
        gain.gain.linearRampToValueAtTime(targetVolume, start + 0.05);
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
        if (!this.isSoundEnabled && window.speechSynthesis) {
            window.speechSynthesis.cancel();
        }
        this.updateSoundUI();
        this.showToast(this.isSoundEnabled ? '방송 소리를 켰습니다.' : '방송 소리를 껐습니다.', 'success');
    }

    updateSoundUI() {
        const btn = document.getElementById('toggleSoundBtn');
        if (!btn) return;
        btn.innerHTML = this.isSoundEnabled ? '<i class="fa-solid fa-volume-high"></i>' : '<i class="fa-solid fa-volume-xmark"></i>';
        btn.classList.toggle('text-indigo-400', this.isSoundEnabled);
        btn.setAttribute('title', this.isSoundEnabled ? '방송 소리 켜짐' : '방송 소리 꺼짐');
        this.updateBroadcastModalTtsInfo();
    }

    toggleFullscreen() {
        const el = document.getElementById('mainAppContainer') || document.documentElement;
        if (!document.fullscreenElement) el.requestFullscreen().catch(() => { });
        else document.exitFullscreen();
    }
}
