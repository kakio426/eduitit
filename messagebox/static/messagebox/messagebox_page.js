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
        messageCaptureManualDate: "",
        messageCaptureManualNote: "",

        init() {
            ensureMessageboxToastBridge();
            initCalendarMessageHub(this, {
                enabled: !!options.enabled,
                itemTypesEnabled: !!options.itemTypesEnabled,
                messageLimitsScriptId: "message-capture-limits-data",
                messageUrlsScriptId: "message-capture-urls-data",
            });

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
            const baseSelectArchiveItem = this.selectMessageArchiveItem.bind(this);

            this.resetMessageCaptureFlow = () => {
                baseResetFlow();
                this.messageCaptureManualDate = "";
                this.messageCaptureManualNote = "";
            };

            this.applyMessageCaptureResult = (payload) => {
                baseApplyResult(payload);
                this.syncManualInputsFromPayload(payload);
            };

            this.applyMessageCaptureArchiveSaveResult = (payload) => {
                baseApplyArchiveResult(payload);
                this.syncManualInputsFromPayload(payload);
            };

            this.applyArchiveDetailToMessageCapture = (detailPayload) => {
                baseApplyArchiveDetail(detailPayload);
                this.syncManualInputsFromPayload(detailPayload);
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

            this.startAnotherMessageCapture = () => {
                this.resetMessageCaptureFlow();
                this.focusMessageInput();
            };
        },

        focusMessageInput(options = {}) {
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

        focusMessageArchive(options = {}) {
            const captureId = String(options.captureId || this.selectedCaptureId() || "");
            const shouldRevealSelection = !!options.revealSelection;
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
            if (hash === "#messagebox-compose") {
                this.focusMessageInput({ behavior: "auto", updateHash: false });
            }
        },

        openMessageArchiveCapture(captureId) {
            this.messageArchiveSelectionShouldReveal = true;
            return this.selectMessageArchiveItem(captureId);
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

        appendManualInputs(formData) {
            if (this.messageCaptureManualDate) {
                formData.append("manual_date", this.messageCaptureManualDate);
            }
            if (this.messageCaptureManualNote) {
                formData.append("manual_note", this.messageCaptureManualNote);
            }
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
            if (this.messageCaptureManualDate) {
                return `${this.formatMessageCaptureDay(this.messageCaptureManualDate)}에 다시 보기`;
            }
            return `후보 ${this.messageCaptureCandidates.length}개 확인`;
        },

        messageCaptureDoneTitle() {
            return this.messageCaptureSuccessMode === "archive"
                ? "메시지를 보관했어요."
                : "캘린더에 연결했어요.";
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
            return {
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
                has_time: !!start && !!end && !raw.is_all_day,
                start_date: start ? this.dateKey(start) : fallbackDate,
                end_date: end ? this.dateKey(end) : (start ? this.dateKey(start) : fallbackDate),
                start_clock: start ? this.toTimeInput(start) : "09:00",
                end_clock: end ? this.toTimeInput(end) : "10:00",
                edit_open: !!raw.is_manual,
                is_manual: !!raw.is_manual,
            };
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

        addManualMessageCaptureCandidate() {
            const defaultDate = this.defaultManualCandidateDate();
            const candidate = this.normalizeMessageCaptureCandidate({
                candidate_id: `manual:${this.createMessageCaptureIdempotencyKey()}`,
                kind: "event",
                title: "",
                summary: "",
                start_time: `${defaultDate}T09:00`,
                end_time: `${defaultDate}T10:00`,
                is_all_day: false,
                is_recommended: true,
                is_manual: true,
            });
            candidate.selected = true;
            candidate.edit_open = true;
            candidate.has_time = true;
            this.messageCaptureCandidates = this.messageCaptureCandidates.concat(candidate);
            this.messageCaptureStep = "confirm";
            this.messageCaptureErrorText = "";
            window.showToast("직접 수정할 일정 칸을 추가했어요.", "info");
        },

        removeMessageCaptureCandidate(candidateId) {
            const targetId = String(candidateId || "");
            if (!targetId) return;
            this.messageCaptureCandidates = this.messageCaptureCandidates.filter(
                (candidate) => String(candidate.candidate_id || "") !== targetId,
            );
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
            if (!this.messageCaptureInputText.trim() && this.messageCaptureFiles.length === 0) {
                this.messageCaptureErrorText = "메시지 텍스트 또는 첨부파일을 하나 이상 입력해 주세요.";
                window.showToast(this.messageCaptureErrorText, "error");
                return;
            }
            this.isParsingMessageCapture = true;
            this.messageCaptureErrorText = "";
            const formData = new FormData();
            formData.append("raw_text", this.messageCaptureInputText);
            formData.append("source_hint", this.messageCaptureSourceHint || "unknown");
            formData.append("idempotency_key", this.messageCaptureIdempotencyKey);
            this.appendManualInputs(formData);
            this.messageCaptureFiles.forEach((fileItem) => {
                formData.append("files", fileItem.file);
            });
            try {
                const payload = await this.requestJson(parseUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                    body: formData,
                });
                this.applyMessageCaptureResult(payload);
                window.showToast("날짜 후보를 찾았어요. 확인 후 연결하세요.", "success");
            } catch (error) {
                this.messageCaptureErrorText = error.message || "메시지 읽기에 실패했습니다.";
                window.showToast(this.messageCaptureErrorText, "error");
            } finally {
                this.isParsingMessageCapture = false;
            }
        },

        async submitMessageCaptureArchiveSave() {
            if (!this.messageCaptureEnabled) {
                window.showToast("업무 메시지 보관함이 아직 열리지 않았습니다.", "info");
                return;
            }
            const saveUrl = this.buildMessageCaptureSaveUrl();
            if (!saveUrl) {
                window.showToast("보관함 저장 경로를 찾지 못했습니다.", "error");
                return;
            }
            if (!this.messageCaptureInputText.trim() && this.messageCaptureFiles.length === 0) {
                this.messageCaptureErrorText = "메시지 텍스트 또는 첨부파일을 하나 이상 입력해 주세요.";
                window.showToast(this.messageCaptureErrorText, "error");
                return;
            }
            this.isSavingMessageCaptureArchive = true;
            this.messageCaptureErrorText = "";
            const formData = new FormData();
            formData.append("raw_text", this.messageCaptureInputText);
            formData.append("source_hint", this.messageCaptureSourceHint || "unknown");
            formData.append("idempotency_key", this.messageCaptureIdempotencyKey);
            this.appendManualInputs(formData);
            this.messageCaptureFiles.forEach((fileItem) => {
                formData.append("files", fileItem.file);
            });
            try {
                const payload = await this.requestJson(saveUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                    body: formData,
                });
                this.applyMessageCaptureArchiveSaveResult(payload);
                await this.loadMessageArchive({ reset: true, preferredCaptureId: payload.capture_id || "" });
                window.showToast(payload.message || "메시지를 보관함에 저장했어요.", "success");
            } catch (error) {
                this.messageCaptureErrorText = error.message || "보관함 저장에 실패했습니다.";
                window.showToast(this.messageCaptureErrorText, "error");
            } finally {
                this.isSavingMessageCaptureArchive = false;
            }
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
                await this.loadMessageArchive({ reset: true, preferredCaptureId: captureId });
                window.showToast(payload.message || "상태를 바꿨어요.", "success");
            } catch (error) {
                window.showToast(error.message || "완료 처리에 실패했습니다.", "error");
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
    };
}
