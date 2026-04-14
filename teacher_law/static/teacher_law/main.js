(function () {
    function parseJsonScript(id, fallbackValue) {
        const element = document.getElementById(id);
        if (!element) return fallbackValue;
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error("[teacher-law] failed to parse json script", id, error);
            return fallbackValue;
        }
    }

    function dispatchToast(message, tag) {
        if (!message) return;
        window.dispatchEvent(new CustomEvent("eduitit:toast", {
            detail: { message, tag: tag || "info" },
        }));
    }

    function formatDate(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return "";
        return new Intl.DateTimeFormat("ko-KR", {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        }).format(date);
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function buildCitationHtml(citation) {
        const sourceUrl = String(citation.source_url || "").trim();
        const title = [citation.title || citation.law_name, citation.reference_label || citation.article_label].filter(Boolean).join(" · ");
        return `
            <div class="teacher-law-citation">
                <div class="teacher-law-citation-title">${escapeHtml(title)}</div>
                <p class="teacher-law-citation-quote">${escapeHtml(citation.quote || "")}</p>
                ${sourceUrl ? `
                <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" class="teacher-law-citation-link">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i>
                    공식 출처 보기
                </a>` : ""}
            </div>
        `;
    }

    function partitionCitations(assistantMessage) {
        const citations = Array.isArray(assistantMessage.citations) ? assistantMessage.citations : [];
        const lawCitations = Array.isArray(assistantMessage.law_citations) && assistantMessage.law_citations.length
            ? assistantMessage.law_citations
            : citations.filter(function (citation) { return citation.source_type !== "case"; });
        const caseCitations = Array.isArray(assistantMessage.case_citations) && assistantMessage.case_citations.length
            ? assistantMessage.case_citations
            : citations.filter(function (citation) { return citation.source_type === "case"; });
        return { lawCitations, caseCitations };
    }

    function buildEvidenceOverviewHtml(lawCitations, caseCitations) {
        if (!lawCitations.length && !caseCitations.length) return "";
        return `
            <div class="teacher-law-section-title">근거</div>
            <div class="teacher-law-evidence-overview">
                ${lawCitations.slice(0, 2).map(function (citation) {
                    return `
                        <div class="teacher-law-evidence-pill">
                            <span class="teacher-law-evidence-label">법령</span>
                            <span>${escapeHtml(citation.title || citation.law_name || "")}</span>
                        </div>
                    `;
                }).join("")}
                ${caseCitations.slice(0, 1).map(function (citation) {
                    return `
                        <div class="teacher-law-evidence-pill teacher-law-evidence-pill--case">
                            <span class="teacher-law-evidence-label">판례</span>
                            <span>${escapeHtml(citation.title || citation.law_name || "")}</span>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    }

    function formatCaseConfidenceLabel(confidence) {
        const normalized = String(confidence || "").trim().toLowerCase();
        if (normalized === "high") return "높음";
        if (normalized === "medium") return "보통";
        if (normalized === "low") return "낮음";
        return "";
    }

    function buildLatestPairHtml(pair) {
        if (!pair || !pair.user_message || !pair.assistant_message) {
            return buildLatestEmptyHtml();
        }
        const userMessage = pair.user_message;
        const assistantMessage = pair.assistant_message;
        const actionItems = Array.isArray(assistantMessage.action_items) ? assistantMessage.action_items.filter(Boolean) : [];
        const clarifyQuestions = Array.isArray(assistantMessage.clarify_questions)
            ? assistantMessage.clarify_questions.filter(Boolean)
            : [];
        const partitioned = partitionCitations(assistantMessage);
        const lawCitations = partitioned.lawCitations;
        const caseCitations = partitioned.caseCitations;
        const reasoningSummary = String(assistantMessage.reasoning_summary || "").trim();
        const representativeCase = assistantMessage.representative_case || (caseCitations.length ? caseCitations[0] : null);
        const representativeCaseConfidence = String(
            assistantMessage.representative_case_confidence || (representativeCase && representativeCase.match_confidence) || ""
        ).trim();
        const representativeCaseMismatchReasons = Array.isArray(assistantMessage.representative_case_mismatch_reasons)
            ? assistantMessage.representative_case_mismatch_reasons.filter(Boolean)
            : (representativeCase && Array.isArray(representativeCase.match_mismatch_reasons)
                ? representativeCase.match_mismatch_reasons.filter(Boolean)
                : []);
        const representativeCaseNotice = String(assistantMessage.representative_case_notice || "").trim();
        const precedentNote = String(assistantMessage.precedent_note || "").trim();
        const overviewCases = representativeCase ? [representativeCase] : caseCitations;
        const actionHtml = actionItems.length
            ? `
                <div class="teacher-law-section-title">할 일</div>
                <ul class="teacher-law-list">
                    ${actionItems.map(function (item) { return `<li>${escapeHtml(item)}</li>`; }).join("")}
                </ul>
            `
            : "";
        const reasoningHtml = reasoningSummary
            ? `
                <div class="teacher-law-section-title">판단 이유</div>
                <p class="teacher-law-citation-quote">${escapeHtml(reasoningSummary)}</p>
            `
            : "";
        const clarifyQuestionHtml = clarifyQuestions.length
            ? `
                <div class="teacher-law-section-title">먼저 확인할 것</div>
                <ul class="teacher-law-list">
                    ${clarifyQuestions.map(function (item) { return `<li>${escapeHtml(item)}</li>`; }).join("")}
                </ul>
            `
            : "";
        const evidenceOverviewHtml = buildEvidenceOverviewHtml(lawCitations, overviewCases);
        const lawCitationHtml = lawCitations.length
            ? `
                <div class="teacher-law-section-title">기본 법령</div>
                ${lawCitations.map(buildCitationHtml).join("")}
            `
            : "";
        const representativeCaseMetaHtml = representativeCase
            ? (() => {
                const parts = [];
                const confidenceLabel = formatCaseConfidenceLabel(representativeCaseConfidence);
                if (confidenceLabel) {
                    parts.push(`<p class="teacher-law-citation-quote">판례 신뢰도 · ${escapeHtml(confidenceLabel)}</p>`);
                }
                if (representativeCaseMismatchReasons.length) {
                    parts.push(`
                        <ul class="teacher-law-list">
                            ${representativeCaseMismatchReasons.map(function (item) {
                                return `<li>${escapeHtml(item)}</li>`;
                            }).join("")}
                        </ul>
                    `);
                }
                if (representativeCaseNotice) {
                    parts.push(`<p class="teacher-law-citation-quote">${escapeHtml(representativeCaseNotice)}</p>`);
                }
                return parts.length ? `<div class="teacher-law-citation">${parts.join("")}</div>` : "";
            })()
            : "";
        const caseCitationHtml = representativeCase
            ? `
                <div class="teacher-law-section-title">대표 판례</div>
                ${buildCitationHtml(representativeCase)}
                ${representativeCaseMetaHtml}
            `
            : precedentNote
                ? `
                    <div class="teacher-law-section-title">대표 판례</div>
                    <div class="teacher-law-citation">
                        <p class="teacher-law-citation-quote">${escapeHtml(precedentNote)}</p>
                    </div>
                `
                : "";
        const disclaimerHtml = assistantMessage.disclaimer
            ? `<p class="teacher-law-disclaimer mt-4">${escapeHtml(assistantMessage.disclaimer)}</p>`
            : "";
        const urgencyHtml = assistantMessage.needs_human_help
            ? `<span class="teacher-law-urgency-badge">사람 상담 권장</span>`
            : "";
        const clarifyHtml = assistantMessage.answer_held
            ? `<span class="teacher-law-clarify-badge">추가 확인 필요</span>`
            : "";
        return `
            <div class="teacher-law-question-card">
                <div class="teacher-law-question-label">내 질문</div>
                <div class="teacher-law-question-text">${escapeHtml(userMessage.body || "")}</div>
            </div>
            <article class="teacher-law-answer-card">
                <div class="teacher-law-answer-meta">
                    <span>법률 가이드</span>
                    <div class="flex items-center gap-3">
                        ${clarifyHtml}
                        ${urgencyHtml}
                        <time datetime="${escapeHtml(assistantMessage.created_at || "")}">${escapeHtml(formatDate(assistantMessage.created_at))}</time>
                    </div>
                </div>
                <p class="teacher-law-summary">${escapeHtml(assistantMessage.summary || assistantMessage.body || "")}</p>
                ${reasoningHtml}
                ${clarifyQuestionHtml}
                ${evidenceOverviewHtml}
                ${actionHtml}
                ${lawCitationHtml}
                ${caseCitationHtml}
                ${disclaimerHtml}
            </article>
        `;
    }

    function buildLatestPlaceholderHtml(progressText) {
        return `
            <div class="teacher-law-question-card" data-teacher-law-placeholder="true">
                <div class="teacher-law-question-label">답변 준비 중</div>
                <div class="teacher-law-question-text" data-teacher-law-placeholder-summary="true">${escapeHtml(progressText)}</div>
            </div>
        `;
    }

    function buildLatestEmptyHtml() {
        return `
            <div class="teacher-law-empty" data-teacher-law-latest-empty="true">
                <p class="text-lg font-black text-slate-900">최신 답변 대기 중</p>
                <p class="mt-2 text-sm leading-6">질문 보내기</p>
            </div>
        `;
    }

    function buildHistoryPairHtml(pair) {
        if (!pair || !pair.user_message || !pair.assistant_message) return "";
        return `
            <article class="teacher-law-history-card">
                <div class="teacher-law-history-question">${escapeHtml(pair.user_message.body || "")}</div>
                <div class="teacher-law-history-answer">${escapeHtml(pair.assistant_message.summary || pair.assistant_message.body || "")}</div>
                <div class="teacher-law-history-meta">${escapeHtml(formatDate(pair.assistant_message.created_at))}</div>
            </article>
        `;
    }

    function buildHistoryEmptyHtml() {
        return `
            <div class="teacher-law-empty" data-teacher-law-history-empty="true">
                <p class="text-base font-black text-slate-900">이전 답변이 없습니다.</p>
                <p class="mt-2 text-sm leading-6">첫 질문 대기 중</p>
            </div>
        `;
    }

    function showInlineError(element, message) {
        if (!element) return;
        element.textContent = message || "";
        element.classList.toggle("is-visible", Boolean(message));
    }

    function getCheckedValue(root, name) {
        const checked = root.querySelector(`input[name="${name}"]:checked`);
        return checked ? String(checked.value || "").trim() : "";
    }

    function setCheckedValue(root, name, value) {
        root.querySelectorAll(`input[name="${name}"]`).forEach(function (input) {
            input.checked = String(input.value || "") === String(value || "");
        });
    }

    function clearRadioValue(root, name) {
        root.querySelectorAll(`input[name="${name}"]`).forEach(function (input) {
            input.checked = false;
        });
    }

    function focusInputToEnd(input) {
        if (!input) return;
        input.focus();
        if (typeof input.setSelectionRange === "function") {
            const length = String(input.value || "").length;
            input.setSelectionRange(length, length);
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const root = document.querySelector("[data-teacher-law-root='true']");
        if (!root) return;

        const askUrl = parseJsonScript("teacher-law-ask-url", "");
        const latestPairData = parseJsonScript("teacher-law-latest-pair", null);
        const historyPairData = parseJsonScript("teacher-law-history-data", []);
        const form = root.querySelector("[data-teacher-law-form='true']");
        const input = root.querySelector("[data-teacher-law-input='true']");
        const sendButton = root.querySelector("[data-teacher-law-send='true']");
        const progress = root.querySelector("[data-teacher-law-progress='true']");
        const progressText = root.querySelector("[data-teacher-law-progress-text='true']");
        const errorBox = root.querySelector("[data-teacher-law-error='true']");
        const latestContainer = root.querySelector("[data-teacher-law-latest-container='true']");
        const historyList = root.querySelector("[data-teacher-law-history-list='true']");
        const scrollRegion = root.querySelector("[data-teacher-law-scroll-region='true']");
        const quickButtons = Array.from(root.querySelectorAll("[data-teacher-law-quick-question='true']"));
        const incidentRadios = Array.from(root.querySelectorAll("[data-teacher-law-incident-option='true']"));
        const goalRadios = Array.from(root.querySelectorAll("[data-teacher-law-goal-option='true']"));
        const sceneRadios = Array.from(root.querySelectorAll("[data-teacher-law-scene-option='true']"));
        const counterpartRadios = Array.from(root.querySelectorAll("[data-teacher-law-counterpart-option='true']"));
        const sceneGroup = root.querySelector("[data-teacher-law-scene-group='true']");
        const counterpartGroup = root.querySelector("[data-teacher-law-counterpart-group='true']");
        const fieldGroups = {
            question: null,
            incident_type: root.querySelector("[data-teacher-law-field-group='incident_type']"),
            legal_goal: root.querySelector("[data-teacher-law-field-group='legal_goal']"),
            scene: root.querySelector("[data-teacher-law-field-group='scene']"),
            counterpart: root.querySelector("[data-teacher-law-field-group='counterpart']"),
        };

        let isSubmitting = false;
        let progressTimers = [];
        let longWaitTimer = null;
        let latestPair = latestPairData && latestPairData.user_message && latestPairData.assistant_message ? latestPairData : null;
        let historyPairs = Array.isArray(historyPairData) ? historyPairData.filter(Boolean) : [];
        const uiBlocked = root.dataset.uiBlocked === "true";

        function currentRequirement() {
            const selected = incidentRadios.find(function (radio) { return radio.checked; });
            return selected ? String(selected.dataset.requires || "").trim() : "";
        }

        function applyFieldErrors(fieldErrors) {
            const normalized = fieldErrors || {};
            Object.keys(fieldGroups).forEach(function (key) {
                const group = fieldGroups[key];
                if (!group) return;
                group.classList.toggle("is-error", Boolean(normalized[key]));
            });
        }

        function buildFieldErrors() {
            const errors = {};
            const incidentType = getCheckedValue(root, "incident_type");
            const legalGoal = getCheckedValue(root, "legal_goal");
            const requirement = currentRequirement();
            const question = String(input.value || "").trim();

            if (!question) errors.question = "질문 입력";
            if (!incidentType) errors.incident_type = "사건 유형 선택";
            if (!legalGoal) errors.legal_goal = "궁금한 것 선택";
            if (requirement === "scene" && !getCheckedValue(root, "scene")) {
                errors.scene = "장면 선택";
            }
            if (requirement === "counterpart" && !getCheckedValue(root, "counterpart")) {
                errors.counterpart = "상대 선택";
            }
            return errors;
        }

        function renderLatestPair(html) {
            if (!latestContainer) return;
            latestContainer.innerHTML = html;
        }

        function renderLatest() {
            renderLatestPair(buildLatestPairHtml(latestPair));
        }

        function renderHistory() {
            if (!historyList) return;
            if (!historyPairs.length) {
                historyList.innerHTML = buildHistoryEmptyHtml();
                return;
            }
            historyList.innerHTML = historyPairs.map(buildHistoryPairHtml).join("");
        }

        function scrollConversationToBottom(options) {
            if (!scrollRegion) return;
            window.requestAnimationFrame(function () {
                const scrollStyles = window.getComputedStyle(scrollRegion);
                const canUseInnerScroll = scrollStyles.overflowY !== "visible" && scrollRegion.scrollHeight > scrollRegion.clientHeight + 4;
                if (canUseInnerScroll) {
                    scrollRegion.scrollTop = scrollRegion.scrollHeight;
                    return;
                }
                if (!options || !options.page) {
                    return;
                }
                const target = latestContainer && latestContainer.lastElementChild
                    ? latestContainer.lastElementChild
                    : latestContainer;
                if (target && typeof target.scrollIntoView === "function") {
                    target.scrollIntoView({ behavior: "smooth", block: "end" });
                }
            });
        }

        function clearProgressTimers() {
            progressTimers.forEach(function (timerId) { window.clearTimeout(timerId); });
            progressTimers = [];
            if (longWaitTimer) {
                window.clearTimeout(longWaitTimer);
                longWaitTimer = null;
            }
        }

        function updateDependentVisibility() {
            const requirement = currentRequirement();
            if (sceneGroup) sceneGroup.hidden = requirement !== "scene";
            if (counterpartGroup) counterpartGroup.hidden = requirement !== "counterpart";
            if (requirement !== "scene") clearRadioValue(root, "scene");
            if (requirement !== "counterpart") clearRadioValue(root, "counterpart");
        }

        function updateSubmitEnabled() {
            const hasErrors = Object.keys(buildFieldErrors()).length > 0;
            const disabled = isSubmitting || uiBlocked || hasErrors;
            if (input) input.disabled = isSubmitting || uiBlocked;
            incidentRadios.concat(goalRadios, sceneRadios, counterpartRadios).forEach(function (radio) {
                radio.disabled = isSubmitting || uiBlocked;
            });
            quickButtons.forEach(function (button) {
                button.disabled = isSubmitting || uiBlocked;
            });
            if (sendButton) sendButton.disabled = disabled;
        }

        function syncPlaceholderText(message) {
            const placeholder = latestContainer.querySelector("[data-teacher-law-placeholder-summary='true']");
            if (placeholder) placeholder.textContent = message;
        }

        function startProgressSequence() {
            if (!progress || !progressText) return;
            progress.classList.add("is-visible");
            progressText.textContent = "법령 확인 중";
            renderLatestPair(buildLatestPlaceholderHtml("법령 확인 중"));
            progressTimers = [
                window.setTimeout(function () {
                    progressText.textContent = "조문 확인 중";
                    syncPlaceholderText("조문 확인 중");
                }, 2000),
                window.setTimeout(function () {
                    progressText.textContent = "답변 정리 중";
                    syncPlaceholderText("답변 정리 중");
                }, 4500),
            ];
            longWaitTimer = window.setTimeout(function () {
                const message = "근거 다시 확인 중";
                progressText.textContent = message;
                syncPlaceholderText(message);
            }, 9000);
        }

        function stopProgressSequence() {
            clearProgressTimers();
            if (progress) progress.classList.remove("is-visible");
            renderLatest();
        }

        function buildPairFromResponse(data, question) {
            const userMessage = data.user_message || { body: question, created_at: new Date().toISOString() };
            const assistantMessage = data.assistant_message || null;
            if (!assistantMessage) return null;
            return {
                pair_id: assistantMessage.id || Date.now(),
                user_message: userMessage,
                assistant_message: assistantMessage,
            };
        }

        async function submitQuestion() {
            const fieldErrors = buildFieldErrors();
            applyFieldErrors(fieldErrors);
            if (Object.keys(fieldErrors).length) {
                const message = Object.values(fieldErrors)[0] || "필수 항목 선택";
                showInlineError(errorBox, message);
                dispatchToast(message, "warning");
                updateSubmitEnabled();
                return;
            }

            const question = String(input.value || "").trim();
            const payload = {
                question: question,
                incident_type: getCheckedValue(root, "incident_type"),
                legal_goal: getCheckedValue(root, "legal_goal"),
                scene: getCheckedValue(root, "scene"),
                counterpart: getCheckedValue(root, "counterpart"),
            };

            showInlineError(errorBox, "");
            applyFieldErrors({});
            isSubmitting = true;
            updateSubmitEnabled();
            startProgressSequence();

            try {
                const response = await fetch(askUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": form.querySelector("[name='csrfmiddlewaretoken']").value,
                    },
                    body: JSON.stringify(payload),
                });
                const data = await response.json().catch(function () { return {}; });
                if (!response.ok) {
                    if (data.field_errors) applyFieldErrors(data.field_errors);
                    throw new Error(data.message || "답변을 준비하지 못했습니다.");
                }
                const responseStatus = data.status || "ok";
                const nextPair = buildPairFromResponse(data, question);
                if (latestPair) {
                    historyPairs = [latestPair].concat(historyPairs).slice(0, 6);
                }
                latestPair = nextPair;
                stopProgressSequence();
                renderHistory();
                if (responseStatus === "clarify") {
                    if (input) input.value = question;
                    updateDependentVisibility();
                    focusInputToEnd(input);
                } else {
                    if (input) input.value = "";
                    clearRadioValue(root, "incident_type");
                    clearRadioValue(root, "legal_goal");
                    clearRadioValue(root, "scene");
                    clearRadioValue(root, "counterpart");
                    updateDependentVisibility();
                }
                updateSubmitEnabled();
                scrollConversationToBottom({ page: true });
                if (responseStatus === "clarify") {
                    dispatchToast("추가 확인 필요: 질문은 그대로 두고 필요한 사실만 덧붙여 주세요.", "info");
                }
            } catch (error) {
                stopProgressSequence();
                const message = error && error.message ? error.message : "답변을 준비하지 못했습니다.";
                showInlineError(errorBox, message);
                dispatchToast(message, "error");
            } finally {
                isSubmitting = false;
                updateSubmitEnabled();
            }
        }

        function applyQuickPreset(button) {
            const question = String(button.dataset.question || "").trim();
            const incidentType = String(button.dataset.incidentType || "").trim();
            const legalGoal = String(button.dataset.legalGoal || "").trim();
            const scene = String(button.dataset.scene || "").trim();
            const counterpart = String(button.dataset.counterpart || "").trim();

            if (question) input.value = question;
            if (incidentType) setCheckedValue(root, "incident_type", incidentType);
            if (legalGoal) setCheckedValue(root, "legal_goal", legalGoal);
            updateDependentVisibility();
            if (scene) setCheckedValue(root, "scene", scene);
            if (counterpart) setCheckedValue(root, "counterpart", counterpart);
            applyFieldErrors({});
            showInlineError(errorBox, "");
            updateSubmitEnabled();
            input.focus();
        }

        renderLatest();
        renderHistory();
        updateDependentVisibility();
        updateSubmitEnabled();
        scrollConversationToBottom();

        form.addEventListener("submit", function (event) {
            event.preventDefault();
            if (uiBlocked || isSubmitting) return;
            submitQuestion();
        });

        input.addEventListener("input", function () {
            applyFieldErrors({});
            if (errorBox && errorBox.classList.contains("is-visible")) showInlineError(errorBox, "");
            updateSubmitEnabled();
        });

        incidentRadios.concat(goalRadios, sceneRadios, counterpartRadios).forEach(function (radio) {
            radio.addEventListener("change", function () {
                updateDependentVisibility();
                applyFieldErrors({});
                showInlineError(errorBox, "");
                updateSubmitEnabled();
            });
        });

        quickButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                if (uiBlocked || isSubmitting) return;
                applyQuickPreset(button);
            });
        });
    });
}());
