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
        this.timeSlots = [];
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
        this.soundEffectGainBoost = 2.2;
        this.soundEffectVolumeCap = 0.34;
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
        this.missionAutomations = [];
        this.missionAutomationPanelExpanded = false;
        this.missionAutomationSelectedId = null;
        this.missionAutomationDraftSlotCode = '';
        this.missionAutomationDraftPhrase = null;
        this.missionAutomationRuntimeStorageKey = 'dt-mission-automation-runtime-v1';
        this.missionAutomationRuntime = this.getDefaultMissionAutomationRuntime();
        this.missionAutomationActiveId = '';
        this.breakAutoConfigStorageKey = 'dt-break-auto-config-v1';
        this.breakAutoRuntimeStorageKey = 'dt-break-auto-runtime-v1';
        this.breakAutoConfig = this.getDefaultBreakAutoConfig();
        this.breakAutoRuntime = this.getDefaultBreakAutoRuntime();
        this.breakAutoActiveSlotCode = '';

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
        this.restoreMissionAutomationRuntime();
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
        this.bindButtonAction('missionAutomationToggleBtn', () => this.toggleMissionAutomationPanel());
        this.bindButtonAction('missionAutomationApplyAllBtn', () => this.applySelectedMissionQuickPhraseToAllAutomationSlots());
        this.setupMissionAutomationControls();

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

    getCurrentPeriodSlot(now = new Date()) {
        const currentTime = now.getTime();
        return this.todaySchedule.find((slot) => {
            const slotType = String(slot?.slot_type || '').trim();
            if (slotType !== 'period') return false;
            const startAt = this.getScheduleSlotDate(slot, 'startTime', now);
            const endAt = this.getScheduleSlotDate(slot, 'endTime', now);
            if (!startAt || !endAt || endAt <= startAt) return false;
            return currentTime >= startAt.getTime() && currentTime < endAt.getTime();
        }) || null;
    }

    getHeaderOperationSnapshot(now = new Date()) {
        const soundText = this.isSoundEnabled ? '방송 소리 켜짐' : '방송 소리 꺼짐';
        const ttsText = this.ttsEnabled ? `${this.ttsMinutesBefore}분 전 자동 안내` : '자동 안내 꺼짐';
        const activeAutomation = this.getActiveMissionAutomation(now);
        const currentSlot = this.getCurrentMissionAutomationSlot(now) || this.getCurrentPeriodSlot(now);
        const nextAnnouncement = this.getNextScheduleAnnouncement(now);
        const activeSlotLabel = String(currentSlot?.slot_label || '').trim() || this.getSchedulePeriodLabel(currentSlot);

        if (this.isBroadcasting && String(this.broadcastMessage || '').trim()) {
            return {
                tone: 'alert',
                badge: '알림',
                value: '교실 안내 송출 중',
                hint: String(this.broadcastMessage || '').trim().slice(0, 52),
            };
        }

        if (activeAutomation) {
            return {
                tone: 'active',
                badge: '자동',
                value: activeAutomation.name || '자동 운영',
                hint: `${activeAutomation.startTime} - ${activeAutomation.endTime} · ${soundText}`,
            };
        }

        if (currentSlot) {
            const slotType = String(currentSlot?.slot_type || '').trim();
            const detailText = slotType === 'period'
                ? (this.getScheduleSubjectName(currentSlot) || `${currentSlot.startTime} - ${currentSlot.endTime}`)
                : `${currentSlot.startTime} - ${currentSlot.endTime}`;
            return {
                tone: 'active',
                badge: slotType === 'period' ? '수업' : '운영',
                value: slotType === 'period' ? `${activeSlotLabel} 진행 중` : `${activeSlotLabel} 운영 중`,
                hint: `${detailText} · ${soundText}`,
            };
        }

        if (nextAnnouncement && nextAnnouncement.status !== 'past') {
            return {
                tone: 'pending',
                badge: '대기',
                value: `${nextAnnouncement.periodLabel} 준비`,
                hint: `${nextAnnouncement.subjectName} · ${nextAnnouncement.announceTime} · ${soundText}`,
            };
        }

        return {
            tone: 'idle',
            badge: '기본',
            value: '일반 운영',
            hint: `${soundText} · ${ttsText}`,
        };
    }

    renderHeaderOverview() {
        const roleValueEl = document.getElementById('headerRoleSummaryValue');
        const roleHintEl = document.getElementById('headerRoleSummaryHint');
        const studentValueEl = document.getElementById('headerStudentSummaryValue');
        const studentHintEl = document.getElementById('headerStudentSummaryHint');
        const opsCardEl = document.getElementById('headerOpsSummaryCard');
        const opsBadgeEl = document.getElementById('headerOpsSummaryBadge');
        const opsValueEl = document.getElementById('headerOpsSummaryValue');
        const opsHintEl = document.getElementById('headerOpsSummaryHint');

        if (!roleValueEl || !roleHintEl || !studentValueEl || !studentHintEl || !opsCardEl || !opsBadgeEl || !opsValueEl || !opsHintEl) {
            return;
        }

        if (!this.hasLoadedData) {
            roleValueEl.textContent = '연결 준비';
            roleHintEl.textContent = '역할 현황을 불러오는 중입니다.';
            studentValueEl.textContent = '연결 준비';
            studentHintEl.textContent = '학생 현황을 불러오는 중입니다.';
            opsBadgeEl.textContent = '대기';
            opsValueEl.textContent = '운영 보드 준비 중';
            opsHintEl.textContent = this.isSoundEnabled ? '방송 소리 켜짐' : '방송 소리 꺼짐';
            opsCardEl.dataset.state = 'idle';
            opsBadgeEl.dataset.state = 'idle';
            return;
        }

        const totalRoles = this.roles.length;
        const assignedRoles = this.roles.filter((role) => Number.isFinite(Number(role.assigneeId))).length;
        const completedRoles = this.roles.filter((role) => role.status === 'completed').length;
        const pendingRoles = Math.max(totalRoles - assignedRoles, 0);
        roleValueEl.textContent = totalRoles ? `${assignedRoles}/${totalRoles}` : '역할 없음';
        roleHintEl.textContent = totalRoles
            ? `완료 ${completedRoles} · 미배정 ${pendingRoles}`
            : '설정에서 역할을 추가해 주세요.';

        const totalStudents = this.students.length;
        const doneStudents = this.students.filter((student) => student.status === 'done').length;
        const remainingStudents = Math.max(totalStudents - doneStudents, 0);
        const progressPercent = totalStudents ? Math.round((doneStudents / totalStudents) * 100) : 0;
        studentValueEl.textContent = totalStudents ? `${doneStudents}/${totalStudents}` : '학생 없음';
        studentHintEl.textContent = totalStudents
            ? `미션 완료 ${progressPercent}% · 남음 ${remainingStudents}`
            : '설정에서 학생을 불러와 주세요.';

        const snapshot = this.getHeaderOperationSnapshot(new Date());
        opsCardEl.dataset.state = snapshot.tone;
        opsBadgeEl.dataset.state = snapshot.tone;
        opsBadgeEl.textContent = snapshot.badge;
        opsValueEl.textContent = snapshot.value;
        opsHintEl.textContent = snapshot.hint;
    }

    setupAdaptiveLayoutObserver() {
        if (this.layoutObserver || typeof ResizeObserver !== 'function') return;

        // Observe only the outer app shell. Inner timer/student cards resize as a
        // consequence of adaptive layout changes, and re-observing them creates
        // a visible feedback loop when the mission panel opens.
        const targets = [
            document.getElementById('mainAppContainer'),
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

    getAdaptiveDensityOrder(displayMode = 'windowed') {
        return displayMode === 'fullscreen'
            ? ['hero', 'presentation', 'balanced', 'compact']
            : ['presentation', 'balanced', 'compact'];
    }

    measureMissionStackState() {
        if (this.missionPanelCollapsed) {
            return {
                gap: Number.POSITIVE_INFINITY,
                pressure: 0,
                timerMainOverflow: 0,
                timerCardOverflow: 0,
                fit: 'normal',
                needsMoreCompression: false,
            };
        }

        const timerMain = document.querySelector('.dt-timer-main');
        const timerCard = document.querySelector('.dt-timer-card');
        const timerDisplay = document.getElementById('mainTimerDisplay');
        const missionStage = document.querySelector('.dt-mission-stage');

        if (!timerMain || !timerCard || !timerDisplay || !missionStage) {
            return {
                gap: Number.POSITIVE_INFINITY,
                pressure: 0,
                timerMainOverflow: 0,
                timerCardOverflow: 0,
                fit: 'normal',
                needsMoreCompression: false,
            };
        }

        const displayRect = timerDisplay.getBoundingClientRect();
        const missionRect = missionStage.getBoundingClientRect();
        const gap = missionRect.top - displayRect.bottom;
        const timerMainOverflow = Math.max(0, Math.ceil(timerMain.scrollHeight - timerMain.clientHeight));
        const timerCardOverflow = Math.max(0, Math.ceil(timerCard.scrollHeight - timerCard.clientHeight));
        const desiredGap = 14;
        const pressure = Math.max(desiredGap - gap, timerMainOverflow, timerCardOverflow);

        let fit = 'normal';
        if (pressure > 22 || gap < -12 || timerMainOverflow > 18 || timerCardOverflow > 18) {
            fit = 'critical';
        } else if (pressure > 6 || gap < 6 || timerMainOverflow > 8 || timerCardOverflow > 8) {
            fit = 'tight';
        }

        return {
            gap,
            pressure,
            timerMainOverflow,
            timerCardOverflow,
            fit,
            needsMoreCompression: pressure > 2,
        };
    }

    resolveAdaptiveDensity(app, displayMode, baseDensity) {
        const densityOrder = this.getAdaptiveDensityOrder(displayMode);
        const startIndex = Math.max(0, densityOrder.indexOf(baseDensity));
        let resolvedDensity = densityOrder[startIndex] || densityOrder[0] || baseDensity;
        let measurement = {
            fit: 'normal',
            needsMoreCompression: false,
        };

        for (let index = startIndex; index < densityOrder.length; index += 1) {
            resolvedDensity = densityOrder[index];
            app.setAttribute('data-layout-density', resolvedDensity);
            measurement = this.measureMissionStackState();
            if (!measurement.needsMoreCompression || index === densityOrder.length - 1) break;
        }

        return {
            density: resolvedDensity,
            fit: measurement.fit || 'normal',
        };
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
        app.setAttribute('data-mission-stack-fit', 'normal');
        const resolvedLayout = this.resolveAdaptiveDensity(app, displayMode, density);
        density = resolvedLayout.density;
        app.setAttribute('data-layout-density', density);
        app.setAttribute('data-mission-stack-fit', this.missionPanelCollapsed ? 'normal' : resolvedLayout.fit);
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

    setupMissionAutomationControls() {
        // Slot-linked automation uses click-based selection cards only.
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

    getBreakSlots() {
        return this.todaySchedule
            .filter((slot) => slot && slot.slot_type === 'break')
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
        const slotLabel = String(slot?.slot_label || '').trim() || '쉬는시간';

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

    getDefaultMissionAutomationRuntime() {
        return {
            date: '',
            runs: {},
        };
    }

    normalizeMissionAutomationTimerMinutes(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return 10;
        return Math.max(1, Math.min(60, Math.round(parsed)));
    }

    sanitizeMissionAutomationName(value) {
        return String(value || '').trim().slice(0, 50);
    }

    sanitizeMissionAutomationPhrase(rawPhrase = null) {
        if (!rawPhrase || typeof rawPhrase !== 'object') return null;
        const title = this.sanitizeMissionText(rawPhrase.title || '', 'title');
        const desc = this.sanitizeMissionText(rawPhrase.desc || '', 'desc');
        const label = this.buildMissionQuickPhraseLabel(title, desc, String(rawPhrase.label || ''));
        if (!label && !title && !desc) return null;
        return {
            label: label || '자동 문구',
            title,
            desc,
        };
    }

    normalizeMissionAutomationRow(rawItem = {}) {
        const slotCode = String(rawItem.slotCode || '').trim();
        const name = this.sanitizeMissionAutomationName(rawItem.name || '');
        const startTime = String(rawItem.startTime || '').trim();
        const endTime = String(rawItem.endTime || '').trim();
        const phrase = this.sanitizeMissionAutomationPhrase(rawItem.phrase);
        if (!slotCode || !name || !startTime || !endTime || !phrase) return null;
        const rawId = rawItem.id !== undefined && rawItem.id !== null ? String(rawItem.id) : slotCode;
        return {
            id: rawId,
            slotCode,
            name,
            startTime,
            endTime,
            enabled: rawItem.enabled === true,
            phrase,
        };
    }

    setTimeSlots(rows = []) {
        const nextRows = Array.isArray(rows) ? rows : [];
        this.timeSlots = nextRows.map((row) => ({
            slotCode: String(row.slotCode || '').trim(),
            slotLabel: String(row.slotLabel || '').trim(),
            slotType: String(row.slotType || '').trim(),
            startTime: String(row.startTime || '').trim(),
            endTime: String(row.endTime || '').trim(),
            period: Number(row.period) || null,
        })).filter((row) => row.slotCode && row.slotLabel && row.startTime && row.endTime);
    }

    setMissionAutomations(rows = []) {
        const normalizedRows = Array.isArray(rows)
            ? rows.map((row) => this.normalizeMissionAutomationRow(row)).filter(Boolean)
            : [];
        this.missionAutomations = normalizedRows;
        const stillSelected = normalizedRows.find((row) => row.id === this.missionAutomationSelectedId) || null;
        this.missionAutomationSelectedId = stillSelected ? stillSelected.id : null;
    }

    restoreMissionAutomationRuntime() {
        try {
            const raw = localStorage.getItem(this.missionAutomationRuntimeStorageKey);
            if (!raw) {
                this.missionAutomationRuntime = this.getDefaultMissionAutomationRuntime();
                return;
            }

            const parsed = JSON.parse(raw);
            const runs = parsed?.runs && typeof parsed.runs === 'object' ? parsed.runs : {};
            const normalizedRuns = {};
            Object.entries(runs).forEach(([automationId, row]) => {
                if (!automationId || !row || typeof row !== 'object') return;
                normalizedRuns[String(automationId)] = {
                    appliedAt: Number(row.appliedAt) || Date.now(),
                    appliedTitle: this.sanitizeMissionText(row.appliedTitle || '', 'title'),
                    appliedDesc: this.sanitizeMissionText(row.appliedDesc || '', 'desc'),
                    prevTitle: this.sanitizeMissionText(row.prevTitle || '', 'title'),
                    prevDesc: this.sanitizeMissionText(row.prevDesc || '', 'desc'),
                };
            });
            this.missionAutomationRuntime = {
                date: String(parsed?.date || ''),
                runs: normalizedRuns,
            };
        } catch (error) {
            console.warn('DutyTicker: failed to restore mission automation runtime', error);
            this.missionAutomationRuntime = this.getDefaultMissionAutomationRuntime();
        }
    }

    saveMissionAutomationRuntime() {
        try {
            localStorage.setItem(this.missionAutomationRuntimeStorageKey, JSON.stringify(this.missionAutomationRuntime));
        } catch (error) {
            console.warn('DutyTicker: failed to save mission automation runtime', error);
        }
    }

    ensureMissionAutomationRuntime(date = new Date()) {
        const todayKey = this.getLocalDateKey(date);
        if (this.missionAutomationRuntime.date === todayKey) return;
        this.missionAutomationRuntime = {
            date: todayKey,
            runs: {},
        };
        this.missionAutomationActiveId = '';
        this.saveMissionAutomationRuntime();
    }

    getMissionAutomationRun(automationId, date = new Date()) {
        this.ensureMissionAutomationRuntime(date);
        return this.missionAutomationRuntime.runs[String(automationId)] || null;
    }

    setMissionAutomationRun(automationId, runData, date = new Date()) {
        if (!automationId || !runData || typeof runData !== 'object') return;
        this.ensureMissionAutomationRuntime(date);
        this.missionAutomationRuntime.runs[String(automationId)] = {
            appliedAt: Number(runData.appliedAt) || Date.now(),
            appliedTitle: this.sanitizeMissionText(runData.appliedTitle || '', 'title'),
            appliedDesc: this.sanitizeMissionText(runData.appliedDesc || '', 'desc'),
            prevTitle: this.sanitizeMissionText(runData.prevTitle || '', 'title'),
            prevDesc: this.sanitizeMissionText(runData.prevDesc || '', 'desc'),
        };
        this.saveMissionAutomationRuntime();
    }

    getSortedMissionAutomations() {
        return [...this.missionAutomations].sort((a, b) => {
            const aStart = this.timeStringToMinutes(a?.startTime);
            const bStart = this.timeStringToMinutes(b?.startTime);
            if (aStart !== bStart) return aStart - bStart;
            return String(a?.name || '').localeCompare(String(b?.name || ''), 'ko');
        });
    }

    getMissionAutomationById(automationId) {
        if (!automationId) return null;
        return this.missionAutomations.find((row) => row.id === String(automationId)) || null;
    }

    getMissionAutomationBySlotCode(slotCode) {
        if (!slotCode) return null;
        return this.missionAutomations.find((row) => String(row.slotCode || '') === String(slotCode)) || null;
    }

    serializeMissionAutomations(rows = this.getSortedMissionAutomations()) {
        return rows.map((item) => ({
            slotCode: item.slotCode,
            enabled: item.enabled === true,
            phrase: item.phrase,
        }));
    }

    getAvailableMissionAutomationSlots() {
        return this.timeSlots
            .filter((slot) => slot && slot.slotType && slot.slotType !== 'period')
            .sort((a, b) => this.timeStringToMinutes(a?.startTime) - this.timeStringToMinutes(b?.startTime));
    }

    getMissionAutomationSlotByCode(slotCode) {
        if (!slotCode) return null;
        return this.getAvailableMissionAutomationSlots().find((slot) => slot.slotCode === String(slotCode)) || null;
    }

    getTodaySlotByCode(slotCode) {
        if (!slotCode) return null;
        return this.todaySchedule.find((slot) => String(slot?.slot_code || '') === String(slotCode)) || null;
    }

    getScheduleSlotDate(slot, timeKey, now = new Date()) {
        const target = String(slot?.[timeKey] || '').trim();
        const match = target.match(/^(\d{1,2}):(\d{2})$/);
        if (!match) return null;
        const date = new Date(now);
        date.setHours(Number(match[1]), Number(match[2]), 0, 0);
        return date;
    }

    getCurrentMissionAutomationSlot(now = new Date()) {
        const currentTime = now.getTime();
        return this.todaySchedule.find((slot) => {
            const slotType = String(slot?.slot_type || '').trim();
            if (!slot || !slotType || slotType === 'period') return false;
            const startAt = this.getScheduleSlotDate(slot, 'startTime', now);
            const endAt = this.getScheduleSlotDate(slot, 'endTime', now);
            if (!startAt || !endAt || endAt <= startAt) return false;
            return currentTime >= startAt.getTime() && currentTime < endAt.getTime();
        }) || null;
    }

    getActiveMissionAutomation(now = new Date()) {
        const activeSlotCode = String(this.getCurrentMissionAutomationSlot(now)?.slot_code || '').trim();
        if (!activeSlotCode) return null;
        return this.getSortedMissionAutomations().find((item) => (
            item
            && item.enabled === true
            && item.phrase
            && String(item.slotCode || '').trim() === activeSlotCode
        )) || null;
    }

    getMissionAutomationRemainingSeconds(item, now = new Date()) {
        const slot = this.getTodaySlotByCode(item?.slotCode);
        const endAt = this.getScheduleSlotDate(slot, 'endTime', now);
        if (!endAt) return 0;
        return Math.max(0, Math.ceil((endAt.getTime() - now.getTime()) / 1000));
    }

    restoreMissionAutomationFromRun(automationId, run) {
        if (!automationId || !run) return;
        this.applyMissionLocally({
            title: run.appliedTitle,
            desc: run.appliedDesc,
        });
        this.missionAutomationActiveId = String(automationId);
    }

    cleanupMissionAutomationRuntime(now = new Date(), activeAutomationId = '') {
        this.ensureMissionAutomationRuntime(now);
        const activeId = String(activeAutomationId || '');
        const automationMap = new Map(this.missionAutomations.map((item) => [String(item.id), item]));
        let didChange = false;

        Object.entries(this.missionAutomationRuntime.runs).forEach(([automationId, run]) => {
            const normalizedId = String(automationId || '');
            if (!normalizedId || normalizedId === activeId) return;

            const item = automationMap.get(normalizedId);
            const slot = item ? this.getTodaySlotByCode(item.slotCode) : null;
            const endAt = slot ? this.getScheduleSlotDate(slot, 'endTime', now) : null;
            const hasEnded = !item || !endAt || now.getTime() >= endAt.getTime();
            if (!hasEnded) return;

            if (
                this.missionAutomationActiveId === normalizedId
                && this.isMissionMatchingSnapshot({
                    title: run?.appliedTitle || '',
                    desc: run?.appliedDesc || '',
                })
            ) {
                this.applyMissionLocally({
                    title: run?.prevTitle || '',
                    desc: run?.prevDesc || '',
                });
            }

            delete this.missionAutomationRuntime.runs[normalizedId];
            if (this.missionAutomationActiveId === normalizedId) {
                this.missionAutomationActiveId = '';
            }
            didChange = true;
        });

        if (didChange) this.saveMissionAutomationRuntime();
    }

    applyMissionAutomation(item, now = new Date()) {
        const automationId = String(item?.id || '').trim();
        if (!automationId || !item?.phrase) return;

        const runData = {
            appliedAt: now.getTime(),
            appliedTitle: item.phrase.title,
            appliedDesc: item.phrase.desc,
            prevTitle: this.sanitizeMissionText(this.missionTitle, 'title'),
            prevDesc: this.sanitizeMissionText(this.missionDesc, 'desc'),
        };

        this.setMissionAutomationRun(automationId, runData, now);
        this.restoreMissionAutomationFromRun(automationId, runData);

        const remainingSeconds = this.getMissionAutomationRemainingSeconds(item, now);
        const timerSeconds = remainingSeconds > 0 ? remainingSeconds : this.timerMaxSeconds;

        this.setTimerMode(timerSeconds, true);
        this.showToast(`${item.name} 자동 시작`, 'success');
    }

    syncMissionAutomationState(now = new Date()) {
        if (!this.hasLoadedData) return;

        const activeAutomation = this.getActiveMissionAutomation(now);
        const activeAutomationId = String(activeAutomation?.id || '');
        this.cleanupMissionAutomationRuntime(now, activeAutomationId);

        if (!activeAutomationId) {
            this.missionAutomationActiveId = '';
            return;
        }

        const existingRun = this.getMissionAutomationRun(activeAutomationId, now);
        if (existingRun) {
            if (
                this.missionAutomationActiveId !== activeAutomationId
                || this.isMissionMatchingSnapshot({
                    title: existingRun.appliedTitle,
                    desc: existingRun.appliedDesc,
                })
            ) {
                this.restoreMissionAutomationFromRun(activeAutomationId, existingRun);
            }
            return;
        }

        this.applyMissionAutomation(activeAutomation, now);
    }

    setMissionAutomationHint(message) {
        const hintEl = document.getElementById('missionAutomationHint');
        if (hintEl) hintEl.textContent = message;
    }

    renderMissionPhrasePanel() {
        const summaryEl = document.getElementById('missionPhrasePanelSummary');
        const selectionEl = document.getElementById('missionQuickModalSelection');
        const selectedPhrase = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        const savedCount = this.missionQuickPhrases.length;

        if (summaryEl) {
            if (selectedPhrase) {
                summaryEl.textContent = `저장 ${savedCount}개 · 자동 적용 문구: ${selectedPhrase.label}`;
            } else if (savedCount > 0) {
                summaryEl.textContent = `저장 ${savedCount}개 · 목록에서 고르면 시간표 자동 적용 문구가 바로 바뀝니다.`;
            } else {
                summaryEl.textContent = '저장 문구가 아직 없습니다. 현재 문구를 저장해 목록을 만드세요.';
            }
        }

        if (selectionEl) {
            if (selectedPhrase) {
                selectionEl.textContent = `현재 선택: ${selectedPhrase.label}`;
            } else if (savedCount > 0) {
                selectionEl.textContent = '현재 선택: 없음';
            } else {
                selectionEl.textContent = '현재 선택: 저장 문구 없음';
            }
        }
    }

    toggleMissionAutomationPanel(forceExpanded = null) {
        if (typeof forceExpanded === 'boolean') {
            this.missionAutomationPanelExpanded = forceExpanded;
        } else {
            this.missionAutomationPanelExpanded = !this.missionAutomationPanelExpanded;
        }
        this.renderMissionAutomationPanel();
    }

    renderMissionAutomationPanel() {
        const body = document.getElementById('missionAutomationPanelBody');
        const toggleBtn = document.getElementById('missionAutomationToggleBtn');
        const statusEl = document.getElementById('missionAutomationActiveStatus');
        const activeAutomation = this.getActiveMissionAutomation();
        const isExpanded = this.missionAutomationPanelExpanded === true;

        if (body) body.classList.toggle('hidden', !isExpanded);

        if (toggleBtn) {
            toggleBtn.innerHTML = isExpanded
                ? '<i class="fa-solid fa-chevron-up"></i> 시간별 예외 접기'
                : '<i class="fa-solid fa-chevron-down"></i> 시간별 예외 열기';
            toggleBtn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        }

        if (statusEl) {
            statusEl.textContent = activeAutomation ? `현재 적용: ${activeAutomation.name}` : '현재 적용 없음';
            statusEl.classList.toggle('border-emerald-300/30', !!activeAutomation);
            statusEl.classList.toggle('bg-emerald-500/15', !!activeAutomation);
            statusEl.classList.toggle('text-emerald-100', !!activeAutomation);
            statusEl.classList.toggle('border-slate-600', !activeAutomation);
            statusEl.classList.toggle('bg-slate-900/75', !activeAutomation);
            statusEl.classList.toggle('text-slate-300', !activeAutomation);
        }
    }

    setMissionAutomationDraftPhrase(phrase) {
        this.missionAutomationDraftPhrase = this.sanitizeMissionAutomationPhrase(phrase);
    }

    setMissionAutomationFormValues({
        slotCode = '',
        enabled = true,
        phrase = null,
    } = {}) {
        const enabledInput = document.getElementById('missionAutomationEnabledInput');

        this.missionAutomationDraftSlotCode = String(slotCode || '').trim();
        if (enabledInput) enabledInput.checked = enabled !== false;
        this.setMissionAutomationDraftPhrase(phrase);
    }

    getMissionAutomationFormValues() {
        const enabledInput = document.getElementById('missionAutomationEnabledInput');

        return {
            slotCode: String(this.missionAutomationDraftSlotCode || '').trim(),
            enabled: enabledInput ? enabledInput.checked === true : true,
            phrase: this.sanitizeMissionAutomationPhrase(this.missionAutomationDraftPhrase),
        };
    }

    syncMissionAutomationSelection(selectedId = null) {
        const targetId = String(selectedId || this.missionAutomationSelectedId || '').trim();
        const selected = this.getMissionAutomationById(targetId) || null;
        this.missionAutomationSelectedId = selected ? selected.id : null;
        return selected;
    }

    getMissionAutomationSummary(item) {
        if (!item?.phrase) return '문구 미연결';
        return item.phrase.desc || item.phrase.title || item.phrase.label || '자동 문구';
    }

    selectMissionAutomationSlot(slotCode) {
        const slot = this.getMissionAutomationSlotByCode(slotCode);
        if (!slot) return;
        const linkedAutomation = this.missionAutomations.find((item) => item.slotCode === slot.slotCode) || null;
        if (linkedAutomation && linkedAutomation.id !== this.missionAutomationSelectedId) {
            this.selectMissionAutomation(linkedAutomation.id);
            return;
        }
        this.missionAutomationDraftSlotCode = slot.slotCode;
        this.renderMissionAutomationManager();
    }

    renderMissionAutomationManager() {
        const slotListEl = document.getElementById('missionAutomationSlotList');
        const slotSummaryEl = document.getElementById('missionAutomationSlotSummary');
        const countEl = document.getElementById('missionAutomationCount');
        const phraseLabelEl = document.getElementById('missionAutomationPhraseLabel');
        const phrasePreviewEl = document.getElementById('missionAutomationPhrasePreview');
        const applyAllBtn = document.getElementById('missionAutomationApplyAllBtn');
        this.renderMissionAutomationPanel();
        if (!slotListEl) return;

        const sortedAutomations = this.getSortedMissionAutomations();
        const configuredCount = sortedAutomations.length;
        const enabledCount = sortedAutomations.filter((item) => item.enabled === true).length;
        const phrase = this.sanitizeMissionAutomationPhrase(this.missionAutomationDraftPhrase);
        const availableSlots = this.getAvailableMissionAutomationSlots();
        const activeAutomation = this.getActiveMissionAutomation();
        const activeAutomationId = String(activeAutomation?.id || '');
        const totalSlotCount = availableSlots.length;

        if (countEl) {
            countEl.textContent = totalSlotCount
                ? `자동 ${enabledCount}칸 ON / 전체 ${totalSlotCount}칸`
                : '자동 시간 없음';
        }
        if (phraseLabelEl) phraseLabelEl.textContent = phrase?.label || '문구를 먼저 골라 주세요.';
        if (phrasePreviewEl) {
            phrasePreviewEl.textContent = phrase
                ? (phrase.desc || phrase.title || phrase.label)
                : '위 저장 문구에서 하나를 고르면 아침시간, 쉬는시간, 점심시간 전체에 바로 적용할 수 있습니다.';
        }
        if (slotSummaryEl) {
            if (!totalSlotCount) {
                slotSummaryEl.textContent = '설정된 자동 적용 시간이 없습니다. 시간표 설정에서 먼저 확인해 주세요.';
            } else if (!configuredCount) {
                slotSummaryEl.textContent = `아침시간, 쉬는시간, 점심시간 ${totalSlotCount}칸 전체에 아직 자동 적용 문구가 없습니다.`;
            } else if (enabledCount === totalSlotCount && configuredCount === totalSlotCount) {
                slotSummaryEl.textContent = `아침시간, 쉬는시간, 점심시간 ${totalSlotCount}칸 전체에 자동 적용됩니다.`;
            } else {
                slotSummaryEl.textContent = `전체 ${totalSlotCount}칸 중 ${enabledCount}칸은 자동 적용 중이고, 나머지는 시간별 예외로 조정되어 있습니다.`;
            }
        }
        if (applyAllBtn) {
            const shouldDisable = !phrase || totalSlotCount === 0;
            applyAllBtn.disabled = shouldDisable;
            applyAllBtn.classList.toggle('cursor-not-allowed', shouldDisable);
            applyAllBtn.classList.toggle('opacity-50', shouldDisable);
        }

        if (!totalSlotCount) {
            slotListEl.innerHTML = `
                <div class="rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 p-4 text-center">
                    <p class="text-sm font-black text-slate-200">연결할 시간이 없습니다.</p>
                    <p class="mt-1 text-xs text-slate-400">설정에서 아침시간, 쉬는시간, 점심시간을 먼저 확인해 주세요.</p>
                </div>
            `;
            this.setMissionAutomationHint('설정된 자동 적용 시간이 없습니다. 시간표 설정에서 아침시간, 쉬는시간, 점심시간을 먼저 확인해 주세요.');
            return;
        }

        slotListEl.innerHTML = availableSlots.map((slot) => {
            const linkedAutomation = this.getMissionAutomationBySlotCode(slot.slotCode);
            const hasAutomation = !!linkedAutomation;
            const isActive = hasAutomation && activeAutomationId && String(linkedAutomation.id) === activeAutomationId;
            const statusText = hasAutomation
                ? (linkedAutomation.enabled ? '이 시간 자동 켜짐' : '이 시간 예외로 꺼짐')
                : '아직 따로 정한 문구 없음';
            const statusClass = hasAutomation
                ? (linkedAutomation.enabled
                    ? 'border-emerald-300/30 bg-emerald-500/15 text-emerald-100'
                    : 'border-amber-300/30 bg-amber-500/15 text-amber-100')
                : 'border-slate-700 bg-slate-900/80 text-slate-300';
            const phraseLabel = hasAutomation
                ? linkedAutomation.phrase?.label || '자동 문구'
                : (phrase?.label || '선택된 문구 없음');
            const phraseSummary = hasAutomation
                ? this.getMissionAutomationSummary(linkedAutomation)
                : (phrase
                    ? (phrase.desc || phrase.title || phrase.label)
                    : '시간표 전체 적용 전에 이 시간만 따로 고를 수도 있습니다.');
            const actionDisabled = !phrase;
            const actionLabel = actionDisabled
                ? '문구 먼저 선택'
                : (hasAutomation ? '이 시간만 이 문구로 바꾸기' : '이 시간만 따로 지정');
            return `
                <div class="rounded-[1.2rem] border ${isActive ? 'border-emerald-300/30 bg-emerald-500/10' : 'border-slate-700/70 bg-slate-900/65'} p-4">
                    <div class="flex flex-wrap items-start justify-between gap-3">
                        <div class="min-w-0">
                            <div class="flex flex-wrap items-center gap-2">
                                <p class="text-sm font-black text-white break-keep">${this.escapeHtml(slot.slotLabel)}</p>
                                <span class="rounded-full border px-2.5 py-1 text-[10px] font-black ${statusClass}">${statusText}</span>
                                ${isActive ? '<span class="rounded-full border border-sky-300/30 bg-sky-500/15 px-2.5 py-1 text-[10px] font-black text-sky-100">현재 적용</span>' : ''}
                            </div>
                            <p class="mt-1 text-[11px] font-black tracking-[0.08em] text-slate-400">${this.escapeHtml(slot.startTime)} ~ ${this.escapeHtml(slot.endTime)}</p>
                        </div>
                    </div>
                    <div class="mt-3 rounded-2xl border border-slate-700/70 bg-slate-950/55 p-3">
                        <p class="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">${hasAutomation ? '이 시간 문구' : '이 시간에 적용할 문구'}</p>
                        <p class="mt-2 text-sm font-black text-white break-keep">${this.escapeHtml(phraseLabel)}</p>
                        <p class="mt-2 text-xs leading-relaxed text-slate-300 break-words">${this.escapeHtml(phraseSummary)}</p>
                    </div>
                    <div class="mt-4 flex flex-wrap gap-2">
                        <button type="button"
                            onclick="window.dtApp.assignSelectedMissionQuickPhraseToAutomationSlot('${slot.slotCode}')"
                            ${actionDisabled ? 'disabled' : ''}
                            class="inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-xs font-black transition ${actionDisabled ? 'cursor-not-allowed border border-slate-700 bg-slate-900/80 text-slate-500 opacity-50' : 'bg-indigo-600 text-white hover:bg-indigo-500'}">
                            <i class="fa-solid fa-wand-magic-sparkles"></i>
                            ${actionLabel}
                        </button>
                        <label class="inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-950/75 px-4 py-2.5 ${hasAutomation ? '' : 'opacity-60'}">
                            <input type="checkbox"
                                ${hasAutomation && linkedAutomation.enabled ? 'checked' : ''}
                                ${hasAutomation ? '' : 'disabled'}
                                onchange="window.dtApp.toggleMissionAutomationSlotEnabled('${slot.slotCode}', this.checked)"
                                class="h-4 w-4 rounded border-slate-500 bg-slate-950 text-emerald-400 focus:ring-emerald-400">
                            <span class="text-xs font-black uppercase tracking-[0.14em] text-slate-300">이 시간 자동 켜기</span>
                        </label>
                        ${hasAutomation ? `
                            <button type="button"
                                onclick="window.dtApp.deleteMissionAutomationBySlot('${slot.slotCode}')"
                                class="inline-flex items-center justify-center gap-2 rounded-2xl border border-rose-400/20 bg-rose-500/15 px-4 py-2.5 text-xs font-black text-rose-100 transition hover:bg-rose-500/25">
                                <i class="fa-solid fa-link-slash"></i>
                                이 시간만 해제
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        if (phrase) {
            this.setMissionAutomationHint(`'${phrase.label}' 문구를 시간표 전체에 적용하거나, 필요한 시간만 예외로 바꿀 수 있습니다.`);
        } else if (configuredCount) {
            this.setMissionAutomationHint('저장 문구를 하나 고르면 시간표 전체를 다시 적용하고, 필요한 시간만 예외로 조정할 수 있습니다.');
        } else {
            this.setMissionAutomationHint('저장 문구 하나를 고르면 아침시간, 쉬는시간, 점심시간 전체에 바로 자동 적용합니다.');
        }
    }

    buildMissionAutomationDraftForSlot(slotCode, { phrase = null, enabled = true } = {}) {
        const slot = this.getMissionAutomationSlotByCode(slotCode);
        if (!slot) {
            this.showToast('자동화 시간을 다시 확인해 주세요.', 'error');
            return null;
        }
        const normalizedPhrase = this.sanitizeMissionAutomationPhrase(phrase);
        if (!normalizedPhrase) {
            this.showToast('연결할 저장 문구를 먼저 선택해 주세요.', 'error');
            return null;
        }
        return {
            slotCode: slot.slotCode,
            name: slot.slotLabel,
            startTime: slot.startTime,
            endTime: slot.endTime,
            enabled: enabled === true,
            phrase: normalizedPhrase,
        };
    }

    async assignSelectedMissionQuickPhraseToAutomationSlot(slotCode) {
        const linkedAutomation = this.getMissionAutomationBySlotCode(slotCode);
        const draft = this.buildMissionAutomationDraftForSlot(slotCode, {
            phrase: this.missionAutomationDraftPhrase,
            enabled: linkedAutomation ? linkedAutomation.enabled === true : true,
        });
        if (!draft) return;

        const nextRows = this.serializeMissionAutomations(
            this.getSortedMissionAutomations().filter((item) => String(item.slotCode || '') !== draft.slotCode)
        );
        nextRows.push({
            slotCode: draft.slotCode,
            enabled: draft.enabled,
            phrase: draft.phrase,
        });

        try {
            this.missionAutomationPanelExpanded = true;
            await this.saveMissionAutomations(nextRows, {
                successMessage: `'${draft.name}' 시간만 다른 문구로 바꿨습니다.`,
            });
            this.setMissionAutomationHint(`'${draft.name}' 시간만 '${draft.phrase.label}' 문구로 바꿨습니다.`);
        } catch (error) {
            console.error(error);
            this.showToast(error?.message || '자동화를 저장하지 못했습니다.', 'error');
        }
    }

    async applySelectedMissionQuickPhraseToAllAutomationSlots() {
        const phrase = this.sanitizeMissionAutomationPhrase(this.missionAutomationDraftPhrase);
        const availableSlots = this.getAvailableMissionAutomationSlots();
        if (!phrase) {
            this.showToast('전체에 연결할 저장 문구를 먼저 선택해 주세요.', 'error');
            return;
        }
        if (!availableSlots.length) {
            this.showToast('설정된 자동화 시간이 없습니다.', 'error');
            return;
        }

        const nextRows = availableSlots.map((slot) => ({
            slotCode: slot.slotCode,
            enabled: true,
            phrase,
        }));

        try {
            this.missionAutomationPanelExpanded = false;
            await this.saveMissionAutomations(nextRows, {
                successMessage: '선택 문구를 시간표 전체에 적용했습니다.',
            });
            this.setMissionAutomationHint(`'${phrase.label}' 문구를 아침시간, 쉬는시간, 점심시간 전체에 적용했습니다.`);
        } catch (error) {
            console.error(error);
            this.showToast(error?.message || '전체 자동화를 저장하지 못했습니다.', 'error');
        }
    }

    async toggleMissionAutomationSlotEnabled(slotCode, enabled) {
        const linkedAutomation = this.getMissionAutomationBySlotCode(slotCode);
        if (!linkedAutomation) {
            this.showToast('먼저 문구를 연결한 뒤 켜고 끌 수 있습니다.', 'error');
            this.renderMissionAutomationManager();
            return;
        }

        const nextRows = this.serializeMissionAutomations().map((item) => (
            String(item.slotCode || '') === String(slotCode)
                ? { slotCode: item.slotCode, enabled: enabled === true, phrase: item.phrase }
                : item
        ));

        try {
            this.missionAutomationPanelExpanded = true;
            await this.saveMissionAutomations(nextRows, {
                successMessage: `'${linkedAutomation.name}' 시간 자동 적용을 ${enabled ? '켰습니다' : '껐습니다'}.`,
            });
            this.setMissionAutomationHint(`'${linkedAutomation.name}' 시간 자동 적용을 ${enabled ? '켜 두었습니다' : '잠시 꺼 두었습니다'}.`);
        } catch (error) {
            console.error(error);
            this.showToast(error?.message || '자동화 상태를 바꾸지 못했습니다.', 'error');
        }
    }

    deleteMissionAutomationBySlot(slotCode) {
        const linkedAutomation = this.getMissionAutomationBySlotCode(slotCode);
        if (!linkedAutomation) {
            this.showToast('해제할 자동화가 없습니다.', 'error');
            return;
        }

        this.requestResetConfirmation({
            title: '이 시간 자동 해제',
            message: `'${linkedAutomation.name}' 시간 자동 적용을 해제할까요?`,
            confirmLabel: '이 시간만 해제',
            onConfirm: async () => {
                const nextRows = this.serializeMissionAutomations(
                    this.getSortedMissionAutomations().filter((item) => String(item.slotCode || '') !== String(slotCode))
                );
                try {
                    this.missionAutomationPanelExpanded = true;
                    await this.saveMissionAutomations(nextRows, {
                        successMessage: `'${linkedAutomation.name}' 시간 자동 적용을 해제했습니다.`,
                    });
                    this.setMissionAutomationHint(`'${linkedAutomation.name}' 시간 자동 적용을 해제했습니다.`);
                } catch (error) {
                    console.error(error);
                    this.showToast(error?.message || '자동화를 해제하지 못했습니다.', 'error');
                }
            },
        });
    }

    prepareNewMissionAutomation(showHint = true) {
        const selectedPhrase = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        this.missionAutomationSelectedId = null;
        if (showHint) this.missionAutomationPanelExpanded = true;
        this.setMissionAutomationFormValues({
            slotCode: '',
            enabled: true,
            phrase: selectedPhrase
                ? { label: selectedPhrase.label, title: selectedPhrase.title, desc: selectedPhrase.desc }
                : null,
        });
        this.renderMissionAutomationManager();
        if (showHint) {
            this.setMissionAutomationHint('저장 문구를 고른 뒤 시간표 전체에 적용하거나, 필요한 시간만 예외로 조정해 주세요.');
        }
    }

    selectMissionAutomation(automationId) {
        const selected = this.syncMissionAutomationSelection(automationId);
        if (!selected) return;
        this.missionAutomationPanelExpanded = true;
        this.setMissionAutomationFormValues(selected);
        this.renderMissionAutomationManager();
    }

    assignSelectedMissionQuickPhraseToAutomation() {
        const selectedPhrase = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);
        if (!selectedPhrase) {
            this.showToast('연결할 저장 문구를 먼저 선택해 주세요.', 'error');
            return;
        }

        this.setMissionAutomationDraftPhrase({
            label: selectedPhrase.label,
            title: selectedPhrase.title,
            desc: selectedPhrase.desc,
        });
        this.renderMissionAutomationManager();
        this.setMissionAutomationHint(`'${selectedPhrase.label}' 문구를 시간표 자동 적용 문구로 골랐습니다.`);
        this.showToast('선택 문구를 시간표 자동 적용 문구로 골랐습니다.', 'success');
    }

    buildMissionAutomationDraftFromForm() {
        const draft = this.getMissionAutomationFormValues();
        const slot = this.getMissionAutomationSlotByCode(draft.slotCode);
        if (!slot) {
            this.showToast('반복 시간을 먼저 골라 주세요.', 'error');
            return null;
        }
        if (!draft.phrase) {
            this.showToast('자동화에 연결할 문구를 먼저 골라 주세요.', 'error');
            return null;
        }
        return {
            slotCode: slot.slotCode,
            name: slot.slotLabel,
            startTime: slot.startTime,
            endTime: slot.endTime,
            enabled: draft.enabled,
            phrase: draft.phrase,
        };
    }

    isSameMissionAutomation(left, right) {
        if (!left || !right) return false;
        const leftPhrase = this.sanitizeMissionAutomationPhrase(left.phrase);
        const rightPhrase = this.sanitizeMissionAutomationPhrase(right.phrase);
        return String(left.slotCode || '') === String(right.slotCode || '')
            && (left.enabled === true) === (right.enabled === true)
            && String(leftPhrase?.label || '') === String(rightPhrase?.label || '')
            && String(leftPhrase?.title || '') === String(rightPhrase?.title || '')
            && String(leftPhrase?.desc || '') === String(rightPhrase?.desc || '');
    }

    async saveMissionAutomations(nextRows, { targetSelection = null, successMessage = '자동화를 저장했습니다.' } = {}) {
        const response = await this.secureFetch(this.getApiUrl('missionAutomationsUrl', '/products/dutyticker/api/mission-automations/update/'), {
            method: 'POST',
            body: JSON.stringify({ automations: nextRows }),
        });
        const payload = await this.parseJsonResponse(response, '자동화를 저장하지 못했습니다.');
        this.setMissionAutomations(payload.automations || []);

        const matched = targetSelection
            ? this.missionAutomations.find((item) => this.isSameMissionAutomation(item, targetSelection))
            : null;
        if (matched) {
            this.missionAutomationSelectedId = matched.id;
            this.setMissionAutomationFormValues(matched);
        } else {
            this.missionAutomationSelectedId = null;
            this.missionAutomationDraftSlotCode = '';
        }

        this.updateMissionQuickPhraseUI();
        this.renderMissionAutomationManager();
        this.syncMissionAutomationState(new Date());
        this.showToast(successMessage, 'success');
        return payload;
    }

    async createMissionAutomation() {
        const draft = this.buildMissionAutomationDraftFromForm();
        if (!draft) return;

        const nextRows = this.getSortedMissionAutomations().map((item) => ({
            slotCode: item.slotCode,
            enabled: item.enabled,
            phrase: item.phrase,
        }));
        if (nextRows.length >= 12) {
            this.showToast('자동화는 12개까지만 저장할 수 있습니다.', 'error');
            return;
        }
        nextRows.push(draft);

        try {
            await this.saveMissionAutomations(nextRows, {
                targetSelection: draft,
                successMessage: `'${draft.name}' 자동화를 저장했습니다.`,
            });
            this.setMissionAutomationHint('새 자동화를 저장했습니다.');
        } catch (error) {
            console.error(error);
            this.showToast(error?.message || '자동화를 저장하지 못했습니다.', 'error');
        }
    }

    async updateSelectedMissionAutomation() {
        const selected = this.syncMissionAutomationSelection(this.missionAutomationSelectedId);
        if (!selected) {
            this.showToast('수정할 자동화를 먼저 선택해 주세요.', 'error');
            return;
        }

        const draft = this.buildMissionAutomationDraftFromForm();
        if (!draft) return;

        const nextRows = this.getSortedMissionAutomations().map((item) => (
            item.id === selected.id
                ? draft
                : {
                    slotCode: item.slotCode,
                    enabled: item.enabled,
                    phrase: item.phrase,
                }
        ));

        try {
            await this.saveMissionAutomations(nextRows, {
                targetSelection: draft,
                successMessage: `'${draft.name}' 자동화를 수정했습니다.`,
            });
            this.setMissionAutomationHint('선택한 자동화를 수정했습니다.');
        } catch (error) {
            console.error(error);
            this.showToast(error?.message || '자동화를 수정하지 못했습니다.', 'error');
        }
    }

    deleteSelectedMissionAutomation() {
        const selected = this.syncMissionAutomationSelection(this.missionAutomationSelectedId);
        if (!selected) {
            this.showToast('삭제할 자동화를 먼저 선택해 주세요.', 'error');
            return;
        }

        this.requestResetConfirmation({
            title: '자동화 삭제',
            message: `'${selected.name}' 자동화를 삭제할까요?`,
            confirmLabel: '선택 삭제',
            onConfirm: async () => {
                const nextRows = this.getSortedMissionAutomations()
                    .filter((item) => item.id !== selected.id)
                    .map((item) => ({
                        slotCode: item.slotCode,
                        enabled: item.enabled,
                        phrase: item.phrase,
                    }));
                try {
                    await this.saveMissionAutomations(nextRows, {
                        successMessage: '선택한 자동화를 삭제했습니다.',
                    });
                    this.missionAutomationSelectedId = null;
                    this.prepareNewMissionAutomation(false);
                    this.setMissionAutomationHint('선택한 자동화를 삭제했습니다.');
                } catch (error) {
                    console.error(error);
                    this.showToast(error?.message || '자동화를 삭제하지 못했습니다.', 'error');
                }
            },
        });
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

    getSchedulePeriodLabel(slot) {
        const periodNumber = Number(slot?.period);
        return Number.isFinite(periodNumber) && periodNumber > 0
            ? `${periodNumber}교시`
            : String(slot?.slot_label || '').trim() || '교시';
    }

    getScheduleSubjectName(slot) {
        const periodLabel = this.getSchedulePeriodLabel(slot);
        const rawSubject = String(slot?.name || '').trim();
        return rawSubject && rawSubject !== periodLabel ? rawSubject : '';
    }

    getTodayScheduleAnnouncementRows() {
        const dateKey = this.getLocalDateKey();
        return this.todaySchedule
            .filter((slot) => slot && slot.slot_type === 'period')
            .map((slot) => {
                const periodLabel = this.getSchedulePeriodLabel(slot);
                const subjectName = this.getScheduleSubjectName(slot);
                const spokenSubject = subjectName || '수업';
                const startTime = String(slot.startTime || '').trim();
                const startMinutes = this.timeStringToMinutes(startTime);
                if (!subjectName || !Number.isFinite(startMinutes)) return null;

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
            this.setTimeSlots(data.timeSlots || []);
            this.setMissionAutomations(data.automations || []);

            // Apply Theme to DOM
            this.applyThemeToDom(this.theme);
            this.applyRoleViewMode();

            const today = new Date().getDay();
            this.todaySchedule = data.schedule[today] || [];
            this.hasLoadedData = true;

            this.renderMissionAutomationManager();
            this.updateMissionQuickPhraseUI();
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

        this.renderHeaderOverview();
    }

    renderAll() {
        this.renderSchedule();
        this.renderMission();
        this.renderRoleList();
        this.renderStudentGrid();
        this.renderNotices();
        this.renderHeaderOverview();
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
            .filter((slot) => slot && slot.slot_type === 'period' && this.getScheduleSubjectName(slot))
            .sort((a, b) => Number(a?.period || 0) - Number(b?.period || 0));

        this.updateBroadcastModalTtsInfo();
        this.checkAndTriggerScheduledAnnouncement(new Date());
        this.syncMissionAutomationState(new Date());

        if (periodSchedule.length === 0) {
            container.innerHTML = '<span class="dt-header-schedule-empty">오늘 시간표 없음</span>';
            this.renderHeaderOverview();
            return;
        }

        const now = new Date();
        const nowMinutes = (now.getHours() * 60) + now.getMinutes();
        const morningSlot = this.getTodaySlotByCode('morning');
        const morningStart = this.timeStringToMinutes(morningSlot?.startTime);
        const morningEnd = this.timeStringToMinutes(morningSlot?.endTime);
        const showAllMorningSlots = Number.isFinite(morningStart)
            && Number.isFinite(morningEnd)
            && nowMinutes >= morningStart
            && nowMinutes < morningEnd;

        const normalizedSlots = periodSchedule.map((slot) => {
            const periodLabel = this.getSchedulePeriodLabel(slot);
            const subjectName = this.getScheduleSubjectName(slot);
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
            this.renderHeaderOverview();
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
            this.renderHeaderOverview();
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
        this.renderHeaderOverview();
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
            this.renderHeaderOverview();
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
        this.renderHeaderOverview();
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

        this.renderHeaderOverview();
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
            this.renderHeaderOverview();
            return;
        }
        const done = this.students.filter(s => s.status === 'done').length;
        const percent = Math.round((done / total) * 100);
        if (bar) bar.style.width = `${percent}%`;
        if (text) text.textContent = `${percent}% (${done}/${total})`;
        this.renderHeaderOverview();
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
        const saveBtn = document.getElementById('missionQuickSaveBtn');
        if (!applyBtn) return;

        const count = this.missionQuickPhrases.length;
        applyBtn.disabled = false;
        applyBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        if (applyLabel) {
            applyLabel.textContent = '문구관리';
        } else {
            applyBtn.textContent = '문구관리';
        }
        applyBtn.setAttribute('title', count > 0 ? `저장 문구 ${count}개를 관리합니다.` : '저장한 문구를 관리합니다.');
        if (saveBtn) saveBtn.setAttribute('title', count > 0 ? `현재 문구를 새 항목으로 저장 (저장 ${count}개)` : '현재 문구를 새 항목으로 저장');
        this.renderMissionAutomationManager();
        this.renderMissionPhrasePanel();
    }

    renderMissionQuickPhraseModal() {
        const listEl = document.getElementById('missionQuickPhraseList');
        if (!listEl) return;

        const countEl = document.getElementById('missionQuickModalCount');
        const createBtn = document.getElementById('missionQuickCreateBtn');
        const updateBtn = document.getElementById('missionQuickUpdateBtn');
        const applyBtn = document.getElementById('missionQuickApplySelectedBtn');
        const deleteBtn = document.getElementById('missionQuickDeleteBtn');
        const deleteAllBtn = document.getElementById('missionQuickDeleteAllBtn');
        const count = this.missionQuickPhrases.length;
        const selected = this.syncMissionQuickPhraseSelection(this.missionQuickSelectedId);

        this.renderMissionAutomationManager();
        this.renderMissionPhrasePanel();

        if (countEl) countEl.textContent = `저장 ${count}개`;
        if (createBtn) createBtn.textContent = selected ? '새 문구로 저장' : '문구 저장';
        if (updateBtn) updateBtn.disabled = !selected;
        if (updateBtn) updateBtn.classList.toggle('hidden', !selected);
        if (applyBtn) applyBtn.disabled = !selected;
        if (deleteBtn) deleteBtn.disabled = !selected;
        if (deleteBtn) deleteBtn.classList.toggle('hidden', !selected);
        if (deleteAllBtn) deleteAllBtn.disabled = count === 0;

        if (!count) {
            listEl.innerHTML = `
                <div class="rounded-2xl border border-dashed border-slate-700 bg-slate-900/45 p-5 text-center">
                    <p class="text-sm font-black text-slate-200">저장된 문구가 없습니다.</p>
                    <p class="mt-1 text-xs text-slate-400">아래에서 새 문구를 저장하거나 현재 문구를 먼저 가져오세요.</p>
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
        this.missionAutomationPanelExpanded = false;
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
        this.setMissionAutomationDraftPhrase({
            label: selected.label,
            title: selected.title,
            desc: selected.desc,
        });
        this.renderMissionQuickPhraseModal();
        this.renderMissionAutomationManager();
        this.renderMissionPhrasePanel();
        this.setMissionQuickPhraseModalHint('고른 문구를 시간표 자동 적용 문구로 골랐습니다.');
    }

    loadCurrentMissionIntoQuickPhraseForm() {
        const draft = this.getCurrentMissionQuickPhraseDraft();
        this.setMissionQuickPhraseFormValues(draft);
        this.setMissionQuickPhraseModalHint('현재 화면 문구를 가져왔습니다. 새 문구로 저장하거나 선택 문구를 수정할 수 있습니다.');
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
        this.setMissionAutomationDraftPhrase(entry);
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
        this.setMissionAutomationDraftPhrase(entry);
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
        this.setMissionAutomationDraftPhrase(updated);
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
        this.setMissionAutomationDraftPhrase(selected);
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
                if (nextSelected) {
                    this.setMissionQuickPhraseFormValues(nextSelected);
                    this.setMissionAutomationDraftPhrase(nextSelected);
                } else {
                    this.loadCurrentMissionIntoQuickPhraseForm();
                    this.setMissionAutomationDraftPhrase(null);
                }
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
                this.setMissionAutomationDraftPhrase(null);
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

    getSoundEffectVolume(volume) {
        const numeric = Number(volume);
        const baseVolume = Number.isFinite(numeric) ? numeric : 0.2;
        return Math.max(0, Math.min(this.soundEffectVolumeCap, baseVolume * this.soundEffectGainBoost));
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
        this.renderHeaderOverview();
    }

    openCurrentPageInNewWindow() {
        const targetUrl = this.buildFreshUrl(window.location.href || '/products/dutyticker/');
        let nextWindow = null;
        try {
            nextWindow = window.open(targetUrl, 'eduititDutyTickerDisplayWindow');
        } catch (error) {
            console.error(error);
        }

        if (!nextWindow) {
            this.showToast('새 창이 차단되었습니다. 브라우저에서 팝업 허용 후 다시 시도해 주세요.', 'error');
            return;
        }

        try {
            nextWindow.focus();
        } catch (error) {
            console.warn('DutyTicker: failed to focus display window', error);
        }

        this.showToast('알림판을 새 창으로 열었습니다. 이 창에서는 에듀잇티를 계속 사용하시면 됩니다.', 'success');
    }

    toggleFullscreen() {
        const el = document.getElementById('mainAppContainer') || document.documentElement;
        if (!document.fullscreenElement) el.requestFullscreen().catch(() => { });
        else document.exitFullscreen();
    }
}
