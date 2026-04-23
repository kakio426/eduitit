function ensureMessageboxToastBridge() {
    if (typeof window.showToast === "function") return;
    const rootId = "messagebox-toast-root";
    const toneClassMap = {
        success: "border-emerald-200 bg-emerald-50 text-emerald-900",
        error: "border-rose-200 bg-rose-50 text-rose-900",
        info: "border-slate-200 bg-slate-900 text-white",
    };
    window.showToast = function(message, tone = "info") {
        const root = document.getElementById(rootId);
        if (!root || !message) return;
        const toast = document.createElement("div");
        toast.setAttribute("role", "status");
        toast.className = `pointer-events-auto rounded-2xl border px-4 py-3 text-sm font-semibold shadow-xl transition duration-200 opacity-0 translate-y-2 ${toneClassMap[tone] || toneClassMap.info}`;
        toast.textContent = String(message);
        root.appendChild(toast);
        window.requestAnimationFrame(() => {
            toast.classList.remove("opacity-0", "translate-y-2");
        });
        window.setTimeout(() => {
            toast.classList.add("opacity-0", "translate-y-2");
            window.setTimeout(() => toast.remove(), 220);
        }, 2800);
    };
}

function messageboxPage(options = {}) {
    return {
        initialCaptureId: String(options.initialCaptureId || ""),
        messageComposerOpen: false,
        messageCaptureManualDate: "",
        messageCaptureManualNote: "",
        messageCaptureSaveMode: "",
        messageCaptureActiveCandidateId: "",
        messageCaptureActiveCandidateRef: null,
        messageCaptureCalendarMonthKey: "",
        messageCaptureDragCandidateId: "",
        messageCaptureSourcePreviewOpen: true,
        messageboxDeletingLinkedItemKeys: [],
        isDeletingMessageArchiveCapture: false,

        init() {
            ensureMessageboxToastBridge();
            const rawHost = this.$root && this.$root._x_dataStack && this.$root._x_dataStack.length
                ? this.$root._x_dataStack[0]
                : (this.$el && this.$el._x_dataStack && this.$el._x_dataStack.length
                    ? this.$el._x_dataStack[0]
                    : this);
            if (!rawHost.messageboxBridgeInitialized) {
                initCalendarMessageHub(rawHost, {
                    enabled: !!options.enabled,
                    itemTypesEnabled: !!options.itemTypesEnabled,
                    messageLimitsScriptId: "message-capture-limits-data",
                    messageUrlsScriptId: "message-capture-urls-data",
                });
                rawHost.messageboxBridgeInitialized = true;
            }
            this.messageboxBridgeInitialized = true;

            this.messageArchiveCounts = {
                all: 0,
                kept: 0,
                dated: 0,
                linked: 0,
                done: 0,
            };
            this.messageArchiveSelectionShouldReveal = false;
            this.wrapMessageboxMethods();

            if (!this.messageCaptureEnabled) {
                return;
            }

            this.resetMessageCaptureFlow();
            Promise.resolve(this.loadMessageArchive({ reset: true, preferredCaptureId: this.initialCaptureId }))
                .finally(() => {
                    this.applyInitialLocationIntent();
                });
        },

        wrapMessageboxMethods() {
            const baseResetFlow = this.resetMessageCaptureFlow.bind(this);
            const baseApplyResult = this.applyMessageCaptureResult.bind(this);
            const baseApplyArchiveResult = this.applyMessageCaptureArchiveSaveResult.bind(this);
            const baseApplyArchiveDetail = this.applyArchiveDetailToMessageCapture.bind(this);
            const baseReplayArchiveCapture = this.replayMessageArchiveCapture.bind(this);
            const baseSelectArchiveItem = this.selectMessageArchiveItem.bind(this);
            const baseSubmitCommit = this.submitMessageCaptureCommit.bind(this);

            this.requestJson = async (url, fetchOptions = {}) => {
                return calendarMessageHubRequestJson(url, fetchOptions, {
                    logContext: "messagebox",
                });
            };

            this.resetMessageCaptureFlow = () => {
                baseResetFlow();
                this.messageComposerOpen = false;
                this.messageCaptureManualDate = "";
                this.messageCaptureManualNote = "";
                this.messageCaptureSaveMode = "";
                this.messageCaptureAdvancedOpen = false;
                this.resetMessageCapturePlannerState();
            };

            this.applyMessageCaptureResult = (payload) => {
                baseApplyResult(payload);
                this.messageComposerOpen = true;
                this.syncManualInputsFromPayload(payload);
                this.messageCaptureSourcePreviewOpen = false;
                this.messageCaptureAdvancedOpen = false;
                this.syncMessageCapturePlannerState();
                if (!this.messageCapturePlannerIsDesktop()) {
                    this.revealMessageCaptureConfirm();
                }
            };

            this.applyMessageCaptureArchiveSaveResult = (payload) => {
                baseApplyArchiveResult(payload);
                this.messageComposerOpen = true;
                this.syncManualInputsFromPayload(payload);
                this.resetMessageCapturePlannerState();
            };

            this.applyArchiveDetailToMessageCapture = (detailPayload) => {
                baseApplyArchiveDetail(detailPayload);
                this.messageComposerOpen = true;
                this.syncManualInputsFromPayload(detailPayload);
                this.messageCaptureSourcePreviewOpen = true;
                this.syncMessageCapturePlannerState();
                this.focusMessageInput({ preserveStep: true, focusInput: false });
            };

            this.selectMessageArchiveItem = async (captureId) => {
                const nextCaptureId = String(captureId || "");
                if (!nextCaptureId) return;
                const shouldReveal = !!this.messageArchiveSelectionShouldReveal;
                this.messageArchiveSelectionShouldReveal = false;
                if (shouldReveal) {
                    if (this.isCompactArchiveLayout()) {
                        this.scrollMessageArchiveDetailIntoView({ behavior: "smooth", focus: false });
                    } else {
                        this.scrollMessageArchiveItemIntoView(nextCaptureId, { behavior: "smooth" });
                    }
                }
                await baseSelectArchiveItem(nextCaptureId);
                this.syncCaptureQuery(nextCaptureId);
                if (shouldReveal) {
                    this.updateMessageboxHash("messagebox-archive");
                    this.afterMessageboxDomUpdate(() => {
                        this.scrollMessageArchiveItemIntoView(nextCaptureId, { behavior: "smooth" });
                        if (this.isCompactArchiveLayout()) {
                            this.scrollMessageArchiveDetailIntoView({ behavior: "smooth", focus: true });
                        }
                    });
                }
            };

            this.openMessageArchiveFromSuccess = async () => {
                const preferredCaptureId = this.messageCaptureCaptureId || this.selectedCaptureId();
                await this.loadMessageArchive({ reset: true, preferredCaptureId });
                this.focusMessageArchive({ captureId: preferredCaptureId });
            };

            this.replayMessageArchiveCapture = async () => {
                const detail = this.messageArchiveSelectedCapture;
                if (!detail) return;

                const visibleCandidates = Array.isArray(detail.candidates)
                    ? detail.candidates.filter((candidate) => !candidate.already_saved)
                    : [];
                const firstEditableCandidateId = visibleCandidates.length > 0
                    ? String(visibleCandidates[0].candidate_id || "")
                    : "";

                if (firstEditableCandidateId) {
                    const prepared = this.prepareSelectedArchiveCaptureForEditing({
                        candidateId: firstEditableCandidateId,
                    });
                    if (prepared) {
                        this.openMessageCaptureCandidateEditor(firstEditableCandidateId);
                        window.showToast("보관한 메시지를 바로 일정 확인 화면으로 열었어요.", "success");
                        return;
                    }
                }

                if (this.prepareSelectedArchiveCaptureForEditing({ addManualCandidate: true })) {
                    window.showToast("보관한 메시지에서 직접 날짜를 정하는 화면으로 열었어요.", "info");
                    return;
                }

                await baseReplayArchiveCapture();
            };

            this.startAnotherMessageCapture = () => {
                this.resetMessageCaptureFlow();
                this.focusMessageInput();
            };

            this.submitMessageCaptureCommit = async () => {
                if (!this.messageCaptureCaptureId) {
                    const candidateSnapshot = Array.isArray(this.messageCaptureCandidates)
                        ? this.messageCaptureCandidates.map((candidate) => ({ ...candidate }))
                        : [];
                    const summarySnapshot = String(this.messageCaptureSummaryText || "");
                    const activeCandidateId = String(this.messageCaptureActiveCandidateId || "");
                    const savedPayload = await this.saveMessageCaptureDraft({
                        loadArchive: true,
                        toast: false,
                    });
                    if (!savedPayload) {
                        return;
                    }
                    if (candidateSnapshot.length > 0) {
                        this.messageCaptureCandidates = candidateSnapshot;
                        this.messageCaptureSummaryText = summarySnapshot;
                        this.syncMessageCapturePlannerState({
                            preferredCandidateId: activeCandidateId,
                        });
                    }
                    this.messageCaptureSuccessMode = "";
                    this.messageCaptureSavedMessage = "";
                    this.messageCaptureSavedEvents = [];
                    this.messageCaptureStep = "confirm";
                    this.messageCaptureSourcePreviewOpen = false;
                }
                const commitResult = await baseSubmitCommit();
                const firstSavedEventId = Array.isArray(this.messageCaptureSavedEvents) && this.messageCaptureSavedEvents.length > 0
                    ? String(this.messageCaptureSavedEvents[0].id || "")
                    : "";
                const firstSavedEventUrl = Array.isArray(this.messageCaptureSavedEvents) && this.messageCaptureSavedEvents.length > 0
                    ? this.buildCalendarFocusUrl(this.messageCaptureSavedEvents[0].calendar_url || "", firstSavedEventId)
                    : "";
                if (this.messageCaptureSuccessMode === "commit" && firstSavedEventUrl) {
                    window.location.href = firstSavedEventUrl;
                    return;
                }
                return commitResult;
            };
        },

        buildCalendarFocusUrl(rawUrl, itemOrEvent = "") {
            const baseUrl = String(rawUrl || "").trim();
            if (!baseUrl) {
                return "";
            }
            let eventId = "";
            if (itemOrEvent && typeof itemOrEvent === "object") {
                eventId = String(itemOrEvent.item_type || "") === "event"
                    ? String(itemOrEvent.id || "")
                    : "";
            } else {
                eventId = String(itemOrEvent || "");
            }
            eventId = eventId.trim();
            if (!eventId) {
                return baseUrl;
            }
            try {
                const parsed = new URL(baseUrl, window.location.origin);
                parsed.searchParams.set("highlight_event", eventId);
                if (parsed.origin === window.location.origin) {
                    return `${parsed.pathname}${parsed.search}${parsed.hash || ""}`;
                }
                return parsed.toString();
            } catch (error) {
                return baseUrl;
            }
        },

        focusMessageInput(options = {}) {
            this.messageComposerOpen = true;
            if (!options.preserveStep) {
                this.messageCaptureStep = String(options.step || "input");
            }
            if (options.updateHash !== false) {
                this.updateMessageboxHash("messagebox-compose");
            }
            this.afterMessageboxDomUpdate(() => {
                const input = this.$refs && this.$refs.messageCaptureInput ? this.$refs.messageCaptureInput : null;
                const composeSection = input && typeof input.closest === "function"
                    ? input.closest("[data-messagebox-compose='true']")
                    : null;
                if (composeSection && typeof composeSection.scrollIntoView === "function") {
                    composeSection.scrollIntoView({
                        behavior: options.behavior || "smooth",
                        block: "start",
                    });
                }
                if (options.focusInput === false) {
                    return;
                }
                if (input && typeof input.focus === "function") {
                    input.focus();
                }
            });
        },

        blurActiveMessageboxElement() {
            if (typeof document === "undefined") return;
            const active = document.activeElement;
            if (!active || active === document.body) return;
            const tagName = String(active.tagName || "").toLowerCase();
            const isEditable = !!active.isContentEditable
                || tagName === "input"
                || tagName === "textarea"
                || tagName === "select";
            if (isEditable && typeof active.blur === "function") {
                active.blur();
            }
        },

        findMessageCaptureConfirmElement() {
            if (typeof document === "undefined") return null;
            const root = this.$root || document.querySelector("[data-messagebox-root='true']");
            if (!root || typeof root.querySelector !== "function") return null;
            return root.querySelector("[data-message-capture-confirm='true']");
        },

        findMessageCaptureConfirmSummaryElement() {
            if (typeof document === "undefined") return null;
            const root = this.$root || document.querySelector("[data-messagebox-root='true']");
            if (!root || typeof root.querySelector !== "function") return null;
            return root.querySelector("[data-message-capture-confirm-summary='true']");
        },

        revealMessageCaptureConfirm(options = {}) {
            if (options.updateHash !== false) {
                this.updateMessageboxHash("messagebox-compose");
            }
            this.blurActiveMessageboxElement();
            const behavior = options.behavior || "smooth";
            const revealConfirmSection = (nextBehavior) => {
                const summaryCard = this.findMessageCaptureConfirmSummaryElement();
                const confirmSection = summaryCard || this.findMessageCaptureConfirmElement();
                if (!confirmSection) {
                    return;
                }
                const rootStyle = typeof window !== "undefined" && window.getComputedStyle
                    ? window.getComputedStyle(document.documentElement)
                    : null;
                const navHeight = rootStyle
                    ? Number.parseFloat(rootStyle.getPropertyValue("--main-nav-height")) || 88
                    : 88;
                const topOffset = navHeight + 16;
                const nextTop = Math.max(
                    0,
                    window.scrollY + confirmSection.getBoundingClientRect().top - topOffset,
                );
                window.scrollTo({
                    top: nextTop,
                    behavior: nextBehavior,
                });
            };
            this.afterMessageboxDomUpdate(() => {
                revealConfirmSection(behavior);
                window.setTimeout(() => revealConfirmSection("auto"), 120);
                window.setTimeout(() => revealConfirmSection("auto"), 320);
                window.setTimeout(() => revealConfirmSection("auto"), 900);
                window.setTimeout(() => revealConfirmSection("auto"), 1500);
            });
        },

        focusMessageArchive(options = {}) {
            const captureId = String(options.captureId || this.selectedCaptureId() || "");
            const shouldRevealSelection = !!options.revealSelection;
            if (this.messageCaptureStep === "input") {
                this.messageComposerOpen = false;
            }
            if (options.updateHash !== false) {
                this.updateMessageboxHash("messagebox-archive");
            }
            this.afterMessageboxDomUpdate(() => {
                const section = this.$refs && this.$refs.messageArchiveSection ? this.$refs.messageArchiveSection : null;
                if (section && typeof section.scrollIntoView === "function") {
                    section.scrollIntoView({
                        behavior: options.behavior || "smooth",
                        block: "start",
                    });
                }
                if (captureId && shouldRevealSelection) {
                    window.setTimeout(() => {
                        this.scrollMessageArchiveItemIntoView(captureId, { behavior: options.behavior || "smooth" });
                    }, 80);
                }
                if (captureId && shouldRevealSelection && options.preferDetail && this.isCompactArchiveLayout()) {
                    window.setTimeout(() => {
                        this.scrollMessageArchiveDetailIntoView({ behavior: options.behavior || "smooth", focus: true });
                    }, 180);
                }
            });
        },

        applyInitialLocationIntent() {
            if (typeof window === "undefined" || !window.location) return;
            const hash = String(window.location.hash || "").trim();
            if (hash === "#messagebox-archive") {
                this.focusMessageArchive({
                    behavior: "auto",
                    captureId: this.initialCaptureId || this.selectedCaptureId(),
                    preferDetail: !!(this.initialCaptureId || this.selectedCaptureId()),
                    updateHash: false,
                });
                return;
            }
            if (this.initialCaptureId) {
                this.focusMessageArchive({
                    behavior: "auto",
                    captureId: this.initialCaptureId,
                    preferDetail: true,
                    updateHash: false,
                });
                return;
            }
            if (hash === "#messagebox-compose") {
                this.focusMessageInput({ behavior: "auto", updateHash: false });
            }
        },

        closeMessageComposer() {
            if (this.messageCaptureStep !== "input") {
                this.resetMessageCaptureFlow();
            }
            this.messageComposerOpen = false;
            this.focusMessageArchive({ behavior: "smooth" });
        },

        openMessageArchiveCapture(captureId) {
            this.messageArchiveSelectionShouldReveal = true;
            return this.selectMessageArchiveItem(captureId);
        },

        async refreshMessageArchiveAfterMutation(preferredCaptureId = "") {
            const targetId = String(preferredCaptureId || "");
            for (let attempt = 0; attempt < 8; attempt += 1) {
                if (!this.isLoadingMessageArchive) {
                    await this.loadMessageArchive({ reset: true, preferredCaptureId: targetId });
                    return true;
                }
                await new Promise((resolve) => window.setTimeout(resolve, 120));
            }
            return false;
        },

        resetMessageCapturePlannerState() {
            this.messageCaptureActiveCandidateId = "";
            this.messageCaptureActiveCandidateRef = this.emptyMessageCaptureCandidate();
            this.messageCaptureCalendarMonthKey = this.normalizeMessageCaptureMonthKey(this.defaultManualCandidateDate());
            this.messageCaptureDragCandidateId = "";
            this.messageCaptureSourcePreviewOpen = true;
        },

        emptyMessageCaptureCandidate() {
            const defaultDate = this.defaultManualCandidateDate();
            return {
                candidate_id: "",
                kind: "event",
                badge_text: "",
                badge_class: "border-slate-200 bg-slate-50 text-slate-700",
                title: "",
                summary: "",
                selected: false,
                already_saved: false,
                needs_check: false,
                is_all_day: true,
                has_time: false,
                start_date: defaultDate,
                end_date: defaultDate,
                start_clock: "09:00",
                end_clock: "10:00",
                end_time_auto: true,
                edit_open: false,
                is_manual: false,
                is_removed: false,
            };
        },

        hasActiveMessageCaptureCandidate() {
            return !!String(this.messageCaptureActiveCandidateId || "").trim();
        },

        normalizeMessageCaptureMonthKey(dateKey) {
            const fallbackDate = this.defaultManualCandidateDate();
            const normalizedValue = String(dateKey || fallbackDate).trim() || fallbackDate;
            const parsed = this.parseDateKey(normalizedValue);
            parsed.setDate(1);
            return this.dateKey(parsed);
        },

        messageCaptureDragEnabled() {
            if (typeof window === "undefined" || !window.matchMedia) return false;
            return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
        },

        messageCapturePlannerIsDesktop() {
            if (typeof window === "undefined" || !window.matchMedia) return false;
            return window.matchMedia("(min-width: 1200px)").matches;
        },

        messageCapturePlannerCandidates() {
            return Array.isArray(this.messageCaptureCandidates)
                ? this.messageCaptureCandidates.filter((candidate) => !candidate.is_removed)
                : [];
        },

        messageCaptureEditableCandidates() {
            return this.messageCapturePlannerCandidates().filter((candidate) => !candidate.already_saved);
        },

        messageCaptureActiveCandidate() {
            const targetId = String(this.messageCaptureActiveCandidateId || "");
            if (!targetId) return null;
            if (
                this.messageCaptureActiveCandidateRef
                && String(this.messageCaptureActiveCandidateRef.candidate_id || "") === targetId
            ) {
                return this.messageCaptureActiveCandidateRef;
            }
            return this.messageCapturePlannerCandidates().find(
                (candidate) => String(candidate.candidate_id || "") === targetId,
            ) || null;
        },

        syncMessageCapturePlannerState(options = {}) {
            const editableCandidates = this.messageCaptureEditableCandidates();
            const allCandidates = this.messageCapturePlannerCandidates();
            const preferredCandidateId = String(options.preferredCandidateId || "").trim();
            let nextActiveCandidate = null;

            if (preferredCandidateId) {
                nextActiveCandidate = allCandidates.find(
                    (candidate) => String(candidate.candidate_id || "") === preferredCandidateId,
                ) || null;
            }
            if (!nextActiveCandidate && this.messageCaptureActiveCandidateId) {
                nextActiveCandidate = editableCandidates.find(
                    (candidate) => String(candidate.candidate_id || "") === String(this.messageCaptureActiveCandidateId),
                ) || null;
            }
            if (!nextActiveCandidate) {
                nextActiveCandidate = editableCandidates[0] || null;
            }

            this.messageCaptureActiveCandidateId = nextActiveCandidate
                ? String(nextActiveCandidate.candidate_id || "")
                : "";
            this.messageCaptureActiveCandidateRef = nextActiveCandidate || this.emptyMessageCaptureCandidate();

            const monthAnchorDate = options.monthDate
                || (nextActiveCandidate ? (nextActiveCandidate.start_date || nextActiveCandidate.end_date) : "")
                || this.defaultManualCandidateDate();
            this.messageCaptureCalendarMonthKey = this.normalizeMessageCaptureMonthKey(monthAnchorDate);

            if (this.messageCaptureStep !== "confirm") {
                this.messageCaptureDragCandidateId = "";
            }
        },

        selectMessageCaptureCandidate(candidateId, options = {}) {
            const targetId = String(candidateId || "");
            if (!targetId) return;
            this.syncMessageCapturePlannerState({
                preferredCandidateId: targetId,
                monthDate: options.keepMonth ? this.messageCaptureCalendarMonthKey : "",
            });
        },

        openMessageCaptureCandidateEditor(candidateId, options = {}) {
            const targetId = String(candidateId || "");
            if (!targetId) return;
            this.selectMessageCaptureCandidate(targetId, options);
            this.afterMessageboxDomUpdate(() => {
                const calendarPanel = this.$refs && this.$refs.messageCaptureCalendarPanel
                    ? this.$refs.messageCaptureCalendarPanel
                    : null;
                if (!this.messageCapturePlannerIsDesktop() && calendarPanel && typeof calendarPanel.scrollIntoView === "function") {
                    calendarPanel.scrollIntoView({
                        behavior: "smooth",
                        block: "start",
                    });
                }
                const titleInput = this.$refs && this.$refs.messageCaptureActiveTitleInput
                    ? this.$refs.messageCaptureActiveTitleInput
                    : null;
                if (options.focusTitle && titleInput && typeof titleInput.focus === "function") {
                    titleInput.focus({ preventScroll: true });
                }
            });
        },

        messageCaptureActiveCandidateBadgeText() {
            const candidate = this.messageCaptureActiveCandidate();
            if (!candidate) return "";
            return candidate.badge_text || "";
        },

        messageCaptureActiveCandidateDateLabel() {
            const candidate = this.messageCaptureActiveCandidate();
            if (!candidate) return "후보를 먼저 선택해 주세요.";
            return this.formatMessageCaptureCandidateDate(candidate);
        },

        moveMessageCaptureCalendarMonth(offset) {
            const baseDate = this.parseDateKey(this.messageCaptureCalendarMonthKey || this.defaultManualCandidateDate());
            baseDate.setMonth(baseDate.getMonth() + Number(offset || 0), 1);
            this.messageCaptureCalendarMonthKey = this.normalizeMessageCaptureMonthKey(this.dateKey(baseDate));
        },

        messageCaptureCalendarMonthLabel() {
            const parsed = this.parseDateKey(this.messageCaptureCalendarMonthKey || this.defaultManualCandidateDate());
            return `${parsed.getFullYear()}년 ${parsed.getMonth() + 1}월`;
        },

        messageCaptureCalendarDays() {
            const monthStart = this.parseDateKey(this.messageCaptureCalendarMonthKey || this.defaultManualCandidateDate());
            monthStart.setDate(1);
            const visibleStart = new Date(monthStart);
            visibleStart.setDate(monthStart.getDate() - monthStart.getDay());
            const activeCandidate = this.messageCaptureActiveCandidate();
            const activeStart = activeCandidate ? String(activeCandidate.start_date || "") : "";
            const activeEnd = activeCandidate ? String(activeCandidate.end_date || activeStart || "") : "";
            const monthKey = this.dateKey(monthStart);
            const todayKey = this.dateKey(new Date());
            const candidateCounts = {};

            for (const candidate of this.messageCapturePlannerCandidates()) {
                const startKey = String(candidate.start_date || "").trim();
                const endKey = String(candidate.end_date || startKey).trim();
                if (!startKey) continue;
                const startDate = this.parseDateKey(startKey);
                const endDate = this.parseDateKey(endKey);
                for (
                    let cursor = new Date(startDate);
                    cursor.getTime() <= endDate.getTime();
                    cursor.setDate(cursor.getDate() + 1)
                ) {
                    const cursorKey = this.dateKey(cursor);
                    candidateCounts[cursorKey] = Number(candidateCounts[cursorKey] || 0) + 1;
                }
            }

            return Array.from({ length: 42 }, (_, index) => {
                const dayDate = new Date(visibleStart);
                dayDate.setDate(visibleStart.getDate() + index);
                const dayKey = this.dateKey(dayDate);
                const isInCurrentMonth = dayKey.slice(0, 7) === monthKey.slice(0, 7);
                const isInActiveRange = !!activeStart && dayKey >= activeStart && dayKey <= activeEnd;
                return {
                    key: dayKey,
                    day_number: dayDate.getDate(),
                    in_current_month: isInCurrentMonth,
                    is_today: dayKey === todayKey,
                    is_active_range: isInActiveRange,
                    has_candidates: Number(candidateCounts[dayKey] || 0) > 0,
                    candidate_count: Number(candidateCounts[dayKey] || 0),
                };
            });
        },

        messageCaptureCalendarDayButtonClass(day) {
            const classes = [];
            if (!day.in_current_month) {
                classes.push("border-slate-100", "bg-slate-50", "text-slate-300");
            } else if (day.is_active_range) {
                classes.push("border-sky-300", "bg-sky-50", "text-slate-900", "shadow-sm");
            } else {
                classes.push("border-slate-200", "bg-white", "text-slate-700", "hover:border-slate-300", "hover:bg-slate-50");
            }
            if (day.is_today) {
                classes.push("ring-2", "ring-amber-200");
            }
            if (this.messageCaptureDragCandidateId) {
                classes.push("cursor-copy");
            }
            return classes.join(" ");
        },

        beginMessageCaptureCandidateDrag(candidateId, dragEvent) {
            const targetId = String(candidateId || "");
            if (!targetId) return;
            this.messageCaptureDragCandidateId = targetId;
            this.selectMessageCaptureCandidate(targetId, { keepMonth: true });
            const dataTransfer = dragEvent && dragEvent.dataTransfer ? dragEvent.dataTransfer : null;
            if (dataTransfer) {
                dataTransfer.effectAllowed = "move";
                dataTransfer.setData("text/plain", targetId);
            }
        },

        clearMessageCaptureCandidateDrag() {
            this.messageCaptureDragCandidateId = "";
        },

        messageCaptureRangeLength(candidate) {
            if (!candidate || !candidate.start_date) return 0;
            if (Number.isInteger(candidate.range_days) && candidate.range_days >= 0) {
                return candidate.range_days;
            }
            const startDate = this.parseDateKey(candidate.start_date);
            const endDate = this.parseDateKey(candidate.end_date || candidate.start_date);
            const diffMs = endDate.getTime() - startDate.getTime();
            return Math.max(0, Math.round(diffMs / (24 * 60 * 60 * 1000)));
        },

        normalizeMessageCaptureCandidateDates(candidate) {
            if (!candidate) return 0;
            const startDate = String(candidate.start_date || "").trim();
            if (!startDate) {
                candidate.start_date = "";
                candidate.end_date = "";
                candidate.range_days = 0;
                return 0;
            }
            let endDate = String(candidate.end_date || startDate).trim() || startDate;
            if (endDate < startDate) {
                endDate = startDate;
            }
            candidate.start_date = startDate;
            candidate.end_date = endDate;
            candidate.range_days = this.messageCaptureRangeLength({
                start_date: startDate,
                end_date: endDate,
            });
            return candidate.range_days;
        },

        buildMessageCaptureAutoEnd(candidate) {
            if (!candidate || !candidate.start_date || !candidate.start_clock) return null;
            const start = new Date(`${candidate.start_date}T${candidate.start_clock}`);
            if (Number.isNaN(start.getTime())) {
                return null;
            }
            const end = new Date(start.getTime() + (60 * 60 * 1000));
            return {
                end_date: `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, "0")}-${String(end.getDate()).padStart(2, "0")}`,
                end_clock: `${String(end.getHours()).padStart(2, "0")}:${String(end.getMinutes()).padStart(2, "0")}`,
            };
        },

        syncMessageCaptureCandidateAutoEnd(candidate, options = {}) {
            if (!candidate || !candidate.has_time || !candidate.start_date || !candidate.start_clock) return;
            const start = new Date(`${candidate.start_date}T${candidate.start_clock}`);
            if (Number.isNaN(start.getTime())) {
                return;
            }
            const currentEndDate = String(candidate.end_date || candidate.start_date || "").trim();
            const currentEndClock = String(candidate.end_clock || "").trim();
            const currentEnd = new Date(`${currentEndDate || candidate.start_date}T${currentEndClock || "00:00"}`);
            const shouldUpdate = !!options.force
                || !!candidate.end_time_auto
                || !currentEndDate
                || !currentEndClock
                || Number.isNaN(currentEnd.getTime())
                || currentEnd <= start;
            if (!shouldUpdate) {
                return;
            }
            const autoEnd = this.buildMessageCaptureAutoEnd(candidate);
            if (!autoEnd) {
                return;
            }
            candidate.end_date = autoEnd.end_date;
            candidate.end_clock = autoEnd.end_clock;
            candidate.end_time_auto = true;
            this.normalizeMessageCaptureCandidateDates(candidate);
        },

        handleMessageCaptureCandidateStartTimeChange(candidate) {
            this.syncMessageCaptureCandidateAutoEnd(candidate);
        },

        markMessageCaptureCandidateEndManual(candidate) {
            if (!candidate) return;
            candidate.end_time_auto = false;
        },

        applyMessageCaptureCandidateToDate(candidate, targetDateKey) {
            if (!candidate) {
                this.messageCaptureErrorText = "먼저 날짜를 바꿀 후보를 선택해 주세요.";
                window.showToast(this.messageCaptureErrorText, "info");
                return;
            }
            const normalizedTargetDate = String(targetDateKey || "").trim();
            if (!normalizedTargetDate) return;

            const spanDays = this.messageCaptureRangeLength(candidate);
            const nextStartDate = this.parseDateKey(normalizedTargetDate);
            const nextEndDate = new Date(nextStartDate);
            nextEndDate.setDate(nextEndDate.getDate() + spanDays);

            candidate.start_date = normalizedTargetDate;
            candidate.end_date = this.dateKey(nextEndDate);
            candidate.range_days = spanDays;
            candidate.selected = !candidate.already_saved;
            candidate.edit_open = true;
            this.messageCaptureErrorText = "";
            this.messageCaptureCalendarMonthKey = this.normalizeMessageCaptureMonthKey(normalizedTargetDate);
            if (candidate.has_time && candidate.end_time_auto) {
                this.syncMessageCaptureCandidateAutoEnd(candidate, { force: true });
            }
        },

        applyMessageCaptureCandidateStartDate(candidate, nextDateKey) {
            if (!candidate) return;
            const normalizedTargetDate = String(nextDateKey || "").trim();
            if (!normalizedTargetDate) {
                candidate.start_date = "";
                candidate.end_date = "";
                candidate.range_days = 0;
                return;
            }
            const spanDays = this.messageCaptureRangeLength(candidate);
            const nextStartDate = this.parseDateKey(normalizedTargetDate);
            const nextEndDate = new Date(nextStartDate);
            nextEndDate.setDate(nextEndDate.getDate() + spanDays);
            candidate.start_date = normalizedTargetDate;
            candidate.end_date = this.dateKey(nextEndDate);
            candidate.range_days = spanDays;
            this.messageCaptureCalendarMonthKey = this.normalizeMessageCaptureMonthKey(normalizedTargetDate);
            if (candidate.has_time && candidate.end_time_auto) {
                this.syncMessageCaptureCandidateAutoEnd(candidate, { force: true });
            }
        },

        applyMessageCaptureCandidateEndDate(candidate, nextDateKey) {
            if (!candidate) return;
            if (!candidate.start_date) {
                candidate.start_date = String(nextDateKey || "").trim();
            }
            candidate.end_date = String(nextDateKey || "").trim();
            this.normalizeMessageCaptureCandidateDates(candidate);
            this.messageCaptureCalendarMonthKey = this.normalizeMessageCaptureMonthKey(
                candidate.start_date || candidate.end_date || this.messageCaptureCalendarMonthKey,
            );
        },

        applyMessageCaptureCandidateTimeToggle(candidate, hasTime) {
            if (!candidate) return;
            candidate.has_time = !!hasTime;
            if (candidate.has_time) {
                this.syncMessageCaptureCandidateAutoEnd(candidate, {
                    force: candidate.end_time_auto !== false,
                });
            }
        },

        handleMessageCaptureCalendarDrop(targetDateKey, dropEvent) {
            const activeCandidate = this.messageCaptureActiveCandidate();
            const dropTransfer = dropEvent && dropEvent.dataTransfer ? dropEvent.dataTransfer : null;
            const draggedCandidateId = String(
                this.messageCaptureDragCandidateId
                || (dropTransfer ? dropTransfer.getData("text/plain") : "")
                || "",
            );
            const dropCandidate = draggedCandidateId
                ? this.messageCapturePlannerCandidates().find(
                    (candidate) => String(candidate.candidate_id || "") === draggedCandidateId,
                )
                : activeCandidate;
            this.applyMessageCaptureCandidateToDate(dropCandidate || activeCandidate, targetDateKey);
            this.clearMessageCaptureCandidateDrag();
        },

        applyActiveMessageCaptureDate(targetDateKey) {
            this.applyMessageCaptureCandidateToDate(this.messageCaptureActiveCandidate(), targetDateKey);
        },

        prepareSelectedArchiveCaptureForEditing(options = {}) {
            const detail = this.messageArchiveSelectedCapture;
            if (!detail) return false;
            this.applyArchiveDetailToMessageCapture(detail);

            const targetCandidateId = String(options.candidateId || "");
            if (targetCandidateId) {
                this.selectMessageCaptureCandidate(targetCandidateId);
            }

            if (options.addManualCandidate) {
                this.addManualMessageCaptureCandidate({ prefillFromSource: true });
            }

            this.focusMessageInput({ preserveStep: true, focusInput: false });
            return true;
        },

        editSelectedArchiveCandidate(candidateId) {
            if (!this.prepareSelectedArchiveCaptureForEditing({ candidateId })) return;
            this.openMessageCaptureCandidateEditor(candidateId);
        },

        addManualCandidateFromSelectedArchive() {
            this.prepareSelectedArchiveCaptureForEditing({ addManualCandidate: true });
        },

        afterMessageboxDomUpdate(callback) {
            if (typeof callback !== "function") return;
            if (typeof this.$nextTick === "function") {
                this.$nextTick(() => {
                    window.requestAnimationFrame(() => callback());
                });
                return;
            }
            window.requestAnimationFrame(() => callback());
        },

        updateMessageboxHash(fragment) {
            if (!window.history || typeof window.history.replaceState !== "function") return;
            const url = new URL(window.location.href);
            url.hash = fragment ? `#${fragment}` : "";
            window.history.replaceState({}, "", url.toString());
        },

        isCompactArchiveLayout() {
            if (!window.matchMedia) return false;
            return window.matchMedia("(max-width: 1023px)").matches;
        },

        findMessageArchiveItemElement(captureId) {
            const captureIdText = String(captureId || "");
            if (!captureIdText || typeof document === "undefined") return null;
            const root = this.$root || document.querySelector("[data-messagebox-root='true']");
            if (!root || typeof root.querySelectorAll !== "function") return null;
            const items = root.querySelectorAll("[data-messagebox-archive-item='true']");
            for (const item of items) {
                if (String(item.getAttribute("data-capture-id") || "") === captureIdText) {
                    return item;
                }
            }
            return null;
        },

        scrollMessageArchiveItemIntoView(captureId, options = {}) {
            const item = this.findMessageArchiveItemElement(captureId);
            if (!item || typeof item.scrollIntoView !== "function") return;
            item.scrollIntoView({
                behavior: options.behavior || "smooth",
                block: "nearest",
                inline: "nearest",
            });
        },

        scrollMessageArchiveDetailIntoView(options = {}) {
            const detail = this.$refs && this.$refs.messageArchiveDetail ? this.$refs.messageArchiveDetail : null;
            if (!detail) return;
            if (typeof detail.scrollIntoView === "function") {
                detail.scrollIntoView({
                    behavior: options.behavior || "smooth",
                    block: "start",
                });
            }
            if (options.focus && typeof detail.focus === "function") {
                window.setTimeout(() => {
                    detail.focus({ preventScroll: true });
                }, 40);
            }
        },

        syncManualInputsFromPayload(payload) {
            this.messageCaptureManualDate = String((payload && payload.manual_date) || "").trim();
            this.messageCaptureManualNote = String((payload && payload.manual_note) || "").trim();
        },

        truncateMessageCaptureText(value, maxLength) {
            const normalized = String(value || "").replace(/\s+/g, " ").trim();
            const limit = Number(maxLength || 0);
            if (!normalized || limit <= 0 || normalized.length <= limit) {
                return normalized;
            }
            const trimmed = normalized.slice(0, Math.max(0, limit - 3)).trim();
            return trimmed ? `${trimmed}...` : normalized.slice(0, limit);
        },

        messageCaptureSourceLines() {
            return String(this.messageCaptureInputText || "")
                .split(/\r?\n/)
                .map((line) => line.replace(/\s+/g, " ").trim())
                .filter(Boolean);
        },

        buildManualMessageCaptureDraftTitle() {
            const sourceLine = this.messageCaptureSourceLines()[0] || "";
            const cleanedSourceLine = sourceLine
                .replace(/^[\-*]+?\s*/, "")
                .replace(/^\[[^\]]+\]\s*/, "")
                .replace(
                    /^(?:20\d{2}[./-]\d{1,2}[./-]\d{1,2}|\d{1,2}[./-]\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일(?:\s*\([월화수목금토일]\))?)\s*/,
                    "",
                )
                .trim();
            const titleCandidates = [
                cleanedSourceLine,
                this.messageCaptureManualNote,
                sourceLine,
                this.messageCaptureSummaryText,
            ];
            for (const candidate of titleCandidates) {
                const normalized = this.truncateMessageCaptureText(candidate, 80);
                if (normalized) {
                    return normalized;
                }
            }
            return "메시지 확인";
        },

        buildManualMessageCaptureDraftSummary() {
            const rawText = String(this.messageCaptureInputText || "").trim();
            const manualNote = String(this.messageCaptureManualNote || "").trim();
            const parts = [];
            if (manualNote) {
                parts.push(`메모: ${manualNote}`);
            }
            if (rawText) {
                parts.push(rawText);
            }
            const combined = parts.join("\n\n").trim();
            if (!combined || combined.length <= 5000) {
                return combined;
            }
            const trimmed = combined.slice(0, 4997).trim();
            return trimmed ? `${trimmed}...` : combined.slice(0, 5000);
        },

        buildManualMessageCaptureCandidateSeed() {
            return {
                title: this.buildManualMessageCaptureDraftTitle(),
                summary: this.buildManualMessageCaptureDraftSummary(),
            };
        },

        appendManualInputs(formData) {
            if (this.messageCaptureManualDate) {
                formData.append("manual_date", this.messageCaptureManualDate);
            }
            if (this.messageCaptureManualNote) {
                formData.append("manual_note", this.messageCaptureManualNote);
            }
        },

        hasMessageCaptureSourceInput() {
            return !!String(this.messageCaptureInputText || "").trim() || this.messageCaptureFiles.length > 0;
        },

        messageCaptureTextHasDateSignal() {
            const rawText = String(this.messageCaptureInputText || "").trim();
            if (!rawText) {
                return false;
            }
            const dateSignalPatterns = [
                /20\d{2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2}/,
                /(?:^|[^0-9])\d{1,2}\s*[./-]\s*\d{1,2}(?=$|[^0-9])/,
                /\d{1,2}\s*월\s*\d{1,2}\s*일(?:\s*\([월화수목금토일]\))?/,
                /(?:^|[^0-9])\d{1,2}\s*일(?:\s*\([월화수목금토일]\))?/,
                /(^|[^가-힣A-Za-z0-9])(오늘|내일|모레|글피)(?=$|[^가-힣A-Za-z0-9])/,
            ];
            return dateSignalPatterns.some((pattern) => pattern.test(rawText));
        },

        shouldSkipMessageCaptureParseRequest() {
            return false;
        },

        ensureMessageCaptureSourceInput() {
            if (this.hasMessageCaptureSourceInput()) {
                return true;
            }
            this.messageCaptureErrorText = "메시지 텍스트 또는 첨부파일을 하나 이상 입력해 주세요.";
            window.showToast(this.messageCaptureErrorText, "error");
            return false;
        },

        buildMessageCaptureSourceFormData() {
            const formData = new FormData();
            formData.append("raw_text", this.messageCaptureInputText);
            formData.append("source_hint", this.messageCaptureSourceHint || "unknown");
            formData.append("idempotency_key", this.messageCaptureIdempotencyKey);
            this.appendManualInputs(formData);
            this.messageCaptureFiles.forEach((fileItem) => {
                formData.append("files", fileItem.file);
            });
            return formData;
        },

        async saveMessageCaptureDraft(options = {}) {
            if (!this.messageCaptureEnabled) {
                window.showToast("업무 메시지 보관함이 아직 열리지 않았습니다.", "info");
                return null;
            }
            const saveUrl = this.buildMessageCaptureSaveUrl();
            if (!saveUrl) {
                window.showToast("보관함 저장 경로를 찾지 못했습니다.", "error");
                return null;
            }
            if (!this.ensureMessageCaptureSourceInput()) {
                return null;
            }
            this.messageCaptureSaveMode = String(options.purpose || "archive");
            this.isSavingMessageCaptureArchive = true;
            this.messageCaptureErrorText = "";
            try {
                const payload = await this.requestJson(saveUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                    body: this.buildMessageCaptureSourceFormData(),
                });
                this.applyMessageCaptureArchiveSaveResult(payload);
                if (options.loadArchive !== false) {
                    try {
                        await this.refreshMessageArchiveAfterMutation(payload.capture_id || "");
                    } catch (archiveError) {
                        if (typeof console !== "undefined" && typeof console.warn === "function") {
                            console.warn("[messagebox] archive refresh skipped after save", archiveError);
                        }
                    }
                }
                if (options.toast !== false) {
                    window.showToast(payload.message || "메시지를 보관함에 저장했어요.", "success");
                }
                return payload;
            } catch (error) {
                this.messageCaptureErrorText = error.message || "보관함 저장에 실패했습니다.";
                if (options.errorToast !== false) {
                    window.showToast(this.messageCaptureErrorText, "error");
                }
                return null;
            } finally {
                this.isSavingMessageCaptureArchive = false;
                this.messageCaptureSaveMode = "";
            }
        },

        prepareManualPlannerFromSavedCapture(payload, options = {}) {
            if (payload && !this.messageCaptureCaptureId) {
                this.messageCaptureCaptureId = String(payload.capture_id || "");
            } else if (!payload && options.clearCaptureId) {
                this.messageCaptureCaptureId = "";
            }
            this.messageCaptureSuccessMode = "";
            this.messageCaptureSavedMessage = "";
            this.messageCaptureSavedEvents = [];
            this.messageCaptureWarnings = [];
            this.messageCaptureErrorText = "";
            this.messageCaptureStep = "confirm";
            this.messageCaptureSourcePreviewOpen = true;
            this.messageCaptureSummaryText = "";
            this.messageCaptureCandidates = [];
            this.addManualMessageCaptureCandidate({
                toast: false,
                focusTitle: options.focusTitle !== false,
                prefillFromSource: true,
            });
        },

        async startManualMessageCaptureFromInput(options = {}) {
            if (!this.ensureMessageCaptureSourceInput()) {
                return false;
            }
            if (options.skipSave) {
                this.prepareManualPlannerFromSavedCapture(null, {
                    clearCaptureId: true,
                    focusTitle: options.focusTitle !== false,
                });
                if (options.toast !== false) {
                    window.showToast(options.toastMessage || "직접 날짜를 정하는 화면으로 열었어요.", "info");
                }
                return true;
            }
            const payload = this.messageCaptureCaptureId
                ? { capture_id: this.messageCaptureCaptureId }
                : await this.saveMessageCaptureDraft({
                    loadArchive: true,
                    purpose: "manual",
                    toast: false,
                    errorToast: options.errorToast,
                });
            if (!payload) {
                return false;
            }
            this.prepareManualPlannerFromSavedCapture(payload, {
                focusTitle: options.focusTitle !== false,
            });
            if (options.toast !== false) {
                window.showToast(options.toastMessage || "직접 날짜를 정하는 화면으로 열었어요.", "info");
            }
            return true;
        },

        shouldAutoSwitchParseFailureToManual(error) {
            const status = Number((error && error.status) || 0);
            const payload = error && error.payload ? error.payload : {};
            const code = String(payload.code || "").trim().toLowerCase();
            if (status === 429 || status === 503) {
                return true;
            }
            if ([
                "daily_limit_exceeded",
                "llm_unavailable",
                "parse_limit_exceeded",
                "provider_unavailable",
                "rate_limited",
            ].includes(code)) {
                return true;
            }
            const combinedText = `${String((error && error.message) || "")} ${code}`.toLowerCase();
            return status >= 500 && /(deepseek|llm|provider|api)/.test(combinedText);
        },

        buildMessageCaptureArchiveUrl(page = 1) {
            const base = this.messageCaptureUrls.archive || "";
            if (!base) return "";
            const params = new URLSearchParams();
            const query = String(this.messageArchiveQuery || "").trim();
            if (query) params.set("query", query);
            if (this.messageArchiveFilter && this.messageArchiveFilter !== "all") {
                params.set("workflow_status", this.messageArchiveFilter);
            }
            params.set("page", String(page || 1));
            const queryString = params.toString();
            return queryString ? `${base}?${queryString}` : base;
        },

        setMessageArchiveFilter(filterValue) {
            this.messageArchiveFilter = String(filterValue || "all");
            this.loadMessageArchive({ reset: true, preferredCaptureId: this.selectedCaptureId() });
        },

        workflowFilterButtonClass(filterKey) {
            const active = this.messageArchiveFilter === filterKey;
            return active
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-300 bg-white text-slate-700";
        },

        workflowBadgeClass(status) {
            const map = {
                kept: "border-slate-200 bg-slate-100 text-slate-700",
                dated: "border-sky-200 bg-sky-50 text-sky-700",
                linked: "border-emerald-200 bg-emerald-50 text-emerald-700",
                done: "border-amber-200 bg-amber-50 text-amber-800",
            };
            return map[String(status || "kept")] || map.kept;
        },

        messageCaptureWorkflowPreviewText() {
            const editableCandidates = this.messageCaptureEditableCandidates();
            const visibleCandidateCount = this.messageCapturePlannerCandidates().length;
            if (editableCandidates.length > 0 && editableCandidates.every((candidate) => candidate.is_manual)) {
                return `직접 고친 일정 ${editableCandidates.length}개`;
            }
            if (this.messageCaptureManualDate) {
                return `${this.formatMessageCaptureDay(this.messageCaptureManualDate)} 다시 보기 메시지`;
            }
            return `저장할 일정 ${visibleCandidateCount}개`;
        },

        messageCaptureDoneTitle() {
            return this.messageCaptureSuccessMode === "archive"
                ? "메시지를 다시 보기로 보관했어요."
                : "캘린더에 저장했어요.";
        },

        messageCaptureSavedDateSummary() {
            if (!Array.isArray(this.messageCaptureSavedEvents) || this.messageCaptureSavedEvents.length === 0) {
                return "";
            }
            const uniqueDateLabels = [];
            const seenDateKeys = new Set();
            for (const event of this.messageCaptureSavedEvents) {
                const parsed = this.parseArchiveDateTime(event && event.start_time ? event.start_time : "");
                if (!parsed) continue;
                const dateKey = `${parsed.getFullYear()}-${parsed.getMonth() + 1}-${parsed.getDate()}`;
                if (seenDateKeys.has(dateKey)) continue;
                seenDateKeys.add(dateKey);
                uniqueDateLabels.push(`${parsed.getMonth() + 1}월 ${parsed.getDate()}일`);
            }
            if (uniqueDateLabels.length === 0) {
                return "";
            }
            if (uniqueDateLabels.length === 1) {
                return `${uniqueDateLabels[0]} 일정으로 저장됐어요.`;
            }
            return `${uniqueDateLabels[0]} 외 ${uniqueDateLabels.length - 1}개 날짜에 저장됐어요.`;
        },

        formatManualDateLabel(value) {
            if (!value) return "";
            if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
                return this.formatMessageCaptureDay(String(value));
            }
            const parsed = this.parseArchiveDateTime(value);
            if (!parsed) return String(value);
            return `${parsed.getMonth() + 1}월 ${parsed.getDate()}일`;
        },

        selectedCaptureId() {
            return this.messageArchiveSelectedCapture ? String(this.messageArchiveSelectedCapture.capture_id || "") : "";
        },

        nextMessageArchiveCaptureId(excludingCaptureId) {
            const targetId = String(excludingCaptureId || "");
            if (!targetId || !Array.isArray(this.messageArchiveItems) || this.messageArchiveItems.length === 0) {
                return "";
            }
            const currentIndex = this.messageArchiveItems.findIndex(
                (item) => String(item.capture_id || "") === targetId,
            );
            if (currentIndex < 0) {
                return "";
            }
            const nextItem = this.messageArchiveItems[currentIndex + 1] || this.messageArchiveItems[currentIndex - 1] || null;
            return nextItem ? String(nextItem.capture_id || "") : "";
        },

        syncCaptureQuery(captureId) {
            if (!window.history || typeof window.history.replaceState !== "function") return;
            const url = new URL(window.location.href);
            if (captureId) {
                url.searchParams.set("capture", captureId);
            } else {
                url.searchParams.delete("capture");
            }
            window.history.replaceState({}, "", url.toString());
        },

        messageCaptureCandidateBadgeMeta(kind) {
            const normalizedKind = String(kind || "event").trim().toLowerCase();
            const map = {
                event: {
                    kind: "event",
                    badge_text: "행사",
                    badge_class: "border-indigo-200 bg-indigo-50 text-indigo-700",
                },
                meeting: {
                    kind: "meeting",
                    badge_text: "회의",
                    badge_class: "border-sky-200 bg-sky-50 text-sky-700",
                },
                class: {
                    kind: "class",
                    badge_text: "수업",
                    badge_class: "border-emerald-200 bg-emerald-50 text-emerald-700",
                },
                consulting: {
                    kind: "consulting",
                    badge_text: "상담",
                    badge_class: "border-slate-200 bg-slate-100 text-slate-700",
                },
                training: {
                    kind: "training",
                    badge_text: "연수",
                    badge_class: "border-amber-200 bg-amber-50 text-amber-700",
                },
                exam: {
                    kind: "exam",
                    badge_text: "평가",
                    badge_class: "border-rose-200 bg-rose-50 text-rose-700",
                },
                deadline: {
                    kind: "deadline",
                    badge_text: "마감",
                    badge_class: "border-rose-200 bg-rose-50 text-rose-700",
                },
                prep: {
                    kind: "prep",
                    badge_text: "준비",
                    badge_class: "border-amber-200 bg-amber-50 text-amber-700",
                },
            };
            return map[normalizedKind] || map.event;
        },

        normalizeMessageCaptureCandidate(raw) {
            const start = raw.start_time ? new Date(raw.start_time) : null;
            const end = raw.end_time ? new Date(raw.end_time) : (start ? new Date(raw.start_time) : null);
            const fallbackDate = this.messageCaptureManualDate || this.dateKey(new Date());
            const badgeMeta = this.messageCaptureCandidateBadgeMeta(raw.kind || "event");
            const hasExplicitTimedRange = !!start && !!raw.end_time && !raw.is_all_day;
            const normalizedCandidate = {
                candidate_id: String(raw.candidate_id || ""),
                kind: badgeMeta.kind,
                badge_text: raw.badge_text || badgeMeta.badge_text,
                badge_class: badgeMeta.badge_class,
                title: String(raw.title || "").trim(),
                summary: String(raw.summary || "").trim(),
                evidence_text: String(raw.evidence_text || "").trim(),
                selected: raw.already_saved ? false : raw.is_recommended !== false,
                already_saved: !!raw.already_saved,
                needs_check: !!raw.needs_check,
                is_all_day: !!raw.is_all_day,
                has_time: false,
                start_date: start ? this.dateKey(start) : fallbackDate,
                end_date: end ? this.dateKey(end) : (start ? this.dateKey(start) : fallbackDate),
                start_clock: start ? this.toTimeInput(start) : "09:00",
                end_clock: end ? this.toTimeInput(end) : "10:00",
                end_time_auto: !hasExplicitTimedRange || ((end.getTime() - start.getTime()) === (60 * 60 * 1000)),
                edit_open: !!raw.is_manual,
                is_manual: !!raw.is_manual,
                is_removed: !!raw.is_removed,
            };
            this.normalizeMessageCaptureCandidateDates(normalizedCandidate);
            return normalizedCandidate;
        },

        applyMessageCaptureCandidateKind(candidate, nextKind) {
            if (!candidate) return;
            const badgeMeta = this.messageCaptureCandidateBadgeMeta(nextKind);
            candidate.kind = badgeMeta.kind;
            candidate.badge_text = badgeMeta.badge_text;
            candidate.badge_class = badgeMeta.badge_class;
        },

        defaultManualCandidateDate() {
            return this.messageCaptureManualDate || this.dateKey(new Date());
        },

        addManualMessageCaptureCandidate(options = {}) {
            const defaultDate = this.defaultManualCandidateDate();
            const candidateSeed = options.prefillFromSource ? this.buildManualMessageCaptureCandidateSeed() : { title: "", summary: "" };
            const candidate = this.normalizeMessageCaptureCandidate({
                candidate_id: `manual:${this.createMessageCaptureIdempotencyKey()}`,
                kind: "event",
                title: candidateSeed.title || "",
                summary: candidateSeed.summary || "",
                start_time: `${defaultDate}T09:00`,
                end_time: `${defaultDate}T10:00`,
                is_all_day: false,
                is_recommended: true,
                is_manual: true,
            });
            candidate.selected = true;
            candidate.edit_open = true;
            candidate.has_time = false;
            this.messageCaptureCandidates = this.messageCaptureCandidates.concat(candidate);
            this.messageCaptureStep = "confirm";
            this.messageCaptureErrorText = "";
            this.syncMessageCapturePlannerState({
                preferredCandidateId: candidate.candidate_id,
                monthDate: defaultDate,
            });
            const editableCandidates = this.messageCaptureEditableCandidates();
            if (editableCandidates.length > 0 && editableCandidates.every((item) => item.is_manual)) {
                this.messageCaptureSummaryText = `직접 정한 일정 후보 ${editableCandidates.length}개`;
            }
            this.openMessageCaptureCandidateEditor(candidate.candidate_id, {
                focusTitle: options.focusTitle !== false,
            });
            if (options.toast !== false) {
                window.showToast("직접 수정할 일정 후보 칸을 추가했어요.", "info");
            }
        },

        removeMessageCaptureCandidate(candidateId) {
            const targetId = String(candidateId || "");
            if (!targetId) return;
            const targetCandidate = Array.isArray(this.messageCaptureCandidates)
                ? this.messageCaptureCandidates.find(
                    (candidate) => String(candidate.candidate_id || "") === targetId,
                ) || null
                : null;
            if (!targetCandidate || targetCandidate.already_saved) {
                return;
            }
            const shouldRemoveLocally = targetCandidate.is_manual || targetId.startsWith("manual:") || !this.messageCaptureCaptureId;
            if (shouldRemoveLocally) {
                this.messageCaptureCandidates = this.messageCaptureCandidates.filter(
                    (candidate) => String(candidate.candidate_id || "") !== targetId,
                );
            } else {
                this.messageCaptureCandidates = this.messageCaptureCandidates.map((candidate) => {
                    if (String(candidate.candidate_id || "") !== targetId) {
                        return candidate;
                    }
                    return {
                        ...candidate,
                        selected: false,
                        edit_open: false,
                        is_removed: true,
                    };
                });
            }
            this.syncMessageCapturePlannerState();
            const editableCandidates = this.messageCaptureEditableCandidates();
            if (editableCandidates.length > 0 && editableCandidates.every((candidate) => candidate.is_manual)) {
                this.messageCaptureSummaryText = `직접 정한 일정 후보 ${editableCandidates.length}개`;
            } else if (editableCandidates.length === 0 && String(this.messageCaptureSummaryText || "").startsWith("직접 정한 일정 후보")) {
                this.messageCaptureSummaryText = "";
            }
        },

        buildSelectedMessageCaptureCandidatesPayload() {
            const normalized = [];
            for (const candidate of this.messageCaptureCandidates) {
                const isSelected = !!candidate.selected && !candidate.already_saved;
                const title = String(candidate.title || "").trim();
                if (!isSelected) {
                    normalized.push({
                        candidate_id: candidate.candidate_id,
                        selected: false,
                        kind: candidate.kind,
                    });
                    continue;
                }
                if (!title) {
                    this.messageCaptureErrorText = "일정 제목을 입력해 주세요.";
                    return null;
                }
                const times = this.buildMessageCaptureCandidateTimes(candidate);
                if (!times) return null;
                normalized.push({
                    candidate_id: candidate.candidate_id,
                    selected: true,
                    kind: candidate.kind,
                    title,
                    start_time: times.start_time,
                    end_time: times.end_time,
                    is_all_day: times.is_all_day,
                    summary: String(candidate.summary || "").trim(),
                });
            }
            return normalized;
        },

        async submitMessageCaptureParse() {
            if (!this.messageCaptureEnabled) {
                window.showToast("업무 메시지 보관함이 아직 열리지 않았습니다.", "info");
                return;
            }
            const parseUrl = this.buildMessageCaptureParseUrl();
            if (!parseUrl) {
                window.showToast("메시지 읽기 경로를 찾지 못했습니다.", "error");
                return;
            }
            if (!this.ensureMessageCaptureSourceInput()) {
                return;
            }
            if (this.shouldSkipMessageCaptureParseRequest()) {
                const switchedToManual = await this.startManualMessageCaptureFromInput({
                    skipSave: true,
                    toastMessage: "날짜가 보여야 자동으로 읽을 수 있어요. 직접 날짜를 정하는 화면으로 열었어요.",
                    errorToast: false,
                });
                if (switchedToManual) {
                    return;
                }
            }
            this.blurActiveMessageboxElement();
            this.isParsingMessageCapture = true;
            this.messageCaptureErrorText = "";
            try {
                const payload = await this.requestJson(parseUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                    body: this.buildMessageCaptureSourceFormData(),
                });
                this.applyMessageCaptureResult(payload);
                try {
                    await this.refreshMessageArchiveAfterMutation(payload.capture_id || this.selectedCaptureId());
                } catch (archiveError) {
                    if (typeof console !== "undefined" && typeof console.warn === "function") {
                        console.warn("[messagebox] archive refresh skipped after parse", archiveError);
                    }
                }
                window.showToast("AI가 찾은 일정이 맞으면 바로 저장하고, 틀릴 때만 고치세요.", "success");
            } catch (error) {
                if (this.shouldAutoSwitchParseFailureToManual(error)) {
                    const switchedToManual = await this.startManualMessageCaptureFromInput({
                        toastMessage: "자동으로 못 찾아서 직접 날짜를 정하는 화면으로 이어서 열었어요.",
                        errorToast: false,
                    });
                    if (switchedToManual) {
                        return;
                    }
                }
                this.messageCaptureErrorText = error.message || "메시지 읽기에 실패했습니다.";
                window.showToast(this.messageCaptureErrorText, "error");
            } finally {
                this.isParsingMessageCapture = false;
            }
        },

        async submitMessageCaptureArchiveSave() {
            await this.saveMessageCaptureDraft({
                loadArchive: true,
                toast: true,
            });
        },

        selectedCaptureCompleteButtonText() {
            if (!this.messageArchiveSelectedCapture) {
                return "처리 완료";
            }
            return this.messageArchiveSelectedCapture.completed_at ? "다시 볼 메시지로 되돌리기" : "처리 완료";
        },

        async toggleSelectedCaptureComplete() {
            const captureId = this.selectedCaptureId();
            if (!captureId) return;
            const completeUrl = this.buildMessageCaptureCompleteUrl(captureId);
            if (!completeUrl) {
                window.showToast("완료 처리 경로를 찾지 못했습니다.", "error");
                return;
            }
            try {
                const payload = await this.requestJson(completeUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                });
                this.messageArchiveSelectedCapture = payload;
                await this.refreshMessageArchiveAfterMutation(captureId);
                window.showToast(payload.message || "상태를 바꿨어요.", "success");
            } catch (error) {
                window.showToast(error.message || "완료 처리에 실패했습니다.", "error");
            }
        },

        async deleteSelectedMessageArchiveCapture() {
            const capture = this.messageArchiveSelectedCapture;
            const captureId = this.selectedCaptureId();
            const deleteUrl = String((capture && capture.delete_url) || this.buildMessageCaptureDeleteUrl(captureId) || "").trim();
            if (!captureId || !deleteUrl) {
                window.showToast("메시지 삭제 경로를 찾지 못했습니다.", "error");
                return;
            }
            if (this.isDeletingMessageArchiveCapture) {
                return;
            }
            const captureLabel = String((capture && (capture.summary_text || capture.preview_text)) || "이 메시지").trim() || "이 메시지";
            const linkedCount = this.selectedCaptureLinkedItems().length;
            const confirmText = linkedCount > 0
                ? `${captureLabel} 보관 기록을 지울까요? 캘린더에 연결된 ${linkedCount}개 항목은 그대로 남습니다.`
                : `${captureLabel} 보관 기록을 지울까요?`;
            if (!window.confirm(confirmText)) {
                return;
            }

            this.isDeletingMessageArchiveCapture = true;
            try {
                const payload = await this.requestJson(deleteUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                });
                const nextCaptureId = this.nextMessageArchiveCaptureId(captureId);
                if (this.messageCaptureCaptureId === captureId) {
                    this.messageCaptureCaptureId = "";
                    this.messageCaptureServerAttachments = [];
                }
                await this.refreshMessageArchiveAfterMutation(nextCaptureId);
                window.showToast(payload.message || "보관 메시지를 지웠어요.", "success");
            } catch (error) {
                window.showToast(error.message || "보관 메시지 삭제에 실패했습니다.", "error");
            } finally {
                this.isDeletingMessageArchiveCapture = false;
            }
        },

        hasSelectedCaptureLinkedItems() {
            return this.selectedCaptureLinkedItems().length > 0;
        },

        selectedCaptureLinkedItems() {
            if (!this.messageArchiveSelectedCapture) return [];
            const events = Array.isArray(this.messageArchiveSelectedCapture.saved_events)
                ? this.messageArchiveSelectedCapture.saved_events.map((item) => ({
                    ...item,
                    item_type: "event",
                    detail_text: this.formatArchiveSavedEventDate(item),
                }))
                : [];
            const tasks = Array.isArray(this.messageArchiveSelectedCapture.saved_tasks)
                ? this.messageArchiveSelectedCapture.saved_tasks.map((item) => ({
                    ...item,
                    item_type: "task",
                    detail_text: this.formatTaskLinkedDate(item),
                }))
                : [];
            return events.concat(tasks);
        },

        formatTaskLinkedDate(task) {
            if (!task || !task.due_at) {
                return "기한 미지정";
            }
            const parsed = this.parseArchiveDateTime(task.due_at);
            if (!parsed) return String(task.due_at);
            if (task.has_time) {
                return `${parsed.getMonth() + 1}월 ${parsed.getDate()}일 ${this.pad(parsed.getHours())}:${this.pad(parsed.getMinutes())}`;
            }
            return `${parsed.getMonth() + 1}월 ${parsed.getDate()}일`;
        },

        linkedItemDeleteKey(linked) {
            const itemType = String((linked && linked.item_type) || "event");
            const itemId = String((linked && linked.id) || "");
            return itemId ? `${itemType}:${itemId}` : "";
        },

        isDeletingLinkedItem(linked) {
            const targetKey = this.linkedItemDeleteKey(linked);
            if (!targetKey) return false;
            return this.messageboxDeletingLinkedItemKeys.includes(targetKey);
        },

        setDeletingLinkedItem(linked, isDeleting) {
            const targetKey = this.linkedItemDeleteKey(linked);
            if (!targetKey) return;
            if (isDeleting) {
                if (!this.messageboxDeletingLinkedItemKeys.includes(targetKey)) {
                    this.messageboxDeletingLinkedItemKeys = this.messageboxDeletingLinkedItemKeys.concat(targetKey);
                }
                return;
            }
            this.messageboxDeletingLinkedItemKeys = this.messageboxDeletingLinkedItemKeys.filter((item) => item !== targetKey);
        },

        linkedItemDeleteLabel(linked) {
            return String((linked && linked.item_type) || "") === "task" ? "할 일" : "일정";
        },

        async deleteLinkedItem(linked, options = {}) {
            const deleteUrl = String((linked && linked.delete_url) || "").trim();
            const itemLabel = this.linkedItemDeleteLabel(linked);
            if (!deleteUrl) {
                window.showToast(`${itemLabel} 삭제 경로를 찾지 못했습니다.`, "error");
                return;
            }
            if (this.isDeletingLinkedItem(linked)) {
                return;
            }
            const title = String((linked && linked.title) || itemLabel).trim() || itemLabel;
            if (!window.confirm(`${title} ${itemLabel === "할 일" ? "항목을" : "일정을"} 삭제할까요? 캘린더에서도 바로 사라집니다.`)) {
                return;
            }

            this.setDeletingLinkedItem(linked, true);
            try {
                await this.requestJson(deleteUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                });

                const deletedId = String((linked && linked.id) || "");
                if (deletedId) {
                    this.messageCaptureSavedEvents = this.messageCaptureSavedEvents.filter(
                        (item) => String(item.id || "") !== deletedId,
                    );
                }

                const captureId = String(options.captureId || this.selectedCaptureId() || "");
                if (options.refreshArchive !== false && captureId) {
                    await this.refreshMessageArchiveAfterMutation(captureId);
                }

                window.showToast(`${itemLabel}을 삭제했어요.`, "success");
            } catch (error) {
                window.showToast(error.message || `${itemLabel} 삭제에 실패했습니다.`, "error");
            } finally {
                this.setDeletingLinkedItem(linked, false);
            }
        },

        deleteSavedEventFromDone(savedEvent) {
            return this.deleteLinkedItem(
                {
                    ...savedEvent,
                    item_type: "event",
                },
                {
                    captureId: this.messageCaptureCaptureId,
                    refreshArchive: this.messageArchiveLoadedOnce && !!this.messageCaptureCaptureId,
                },
            );
        },
    };
}
