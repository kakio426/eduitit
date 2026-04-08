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
        const title = [citation.law_name, citation.article_label].filter(Boolean).join(" · ");
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

    function buildLatestPairHtml(pair) {
        if (!pair || !pair.user_message || !pair.assistant_message) {
            return buildLatestEmptyHtml();
        }
        const userMessage = pair.user_message;
        const assistantMessage = pair.assistant_message;
        const actionItems = Array.isArray(assistantMessage.action_items) ? assistantMessage.action_items.filter(Boolean) : [];
        const citations = Array.isArray(assistantMessage.citations) ? assistantMessage.citations : [];
        const actionHtml = actionItems.length
            ? `
                <div class="teacher-law-section-title">지금 바로 할 일</div>
                <ul class="teacher-law-list">
                    ${actionItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
                </ul>
            `
            : "";
        const citationHtml = citations.length
            ? `
                <div class="teacher-law-section-title">근거 조문</div>
                ${citations.map(buildCitationHtml).join("")}
            `
            : "";
        const disclaimerHtml = assistantMessage.disclaimer
            ? `<p class="teacher-law-disclaimer mt-4">${escapeHtml(assistantMessage.disclaimer)}</p>`
            : "";
        const urgencyHtml = assistantMessage.needs_human_help
            ? `<span class="teacher-law-urgency-badge">사람 상담 권장</span>`
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
                        ${urgencyHtml}
                        <time datetime="${escapeHtml(assistantMessage.created_at || "")}">${escapeHtml(formatDate(assistantMessage.created_at))}</time>
                    </div>
                </div>
                <p class="teacher-law-summary">${escapeHtml(assistantMessage.summary || assistantMessage.body || "")}</p>
                ${actionHtml}
                ${citationHtml}
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
                <p class="text-lg font-black text-slate-900">질문을 보내면 가장 최근 답변이 여기 가장 크게 표시됩니다.</p>
                <p class="mt-2 text-sm leading-6">지금 교실에서 바로 확인해야 하는 상황을 한 문장으로 적어 주세요.</p>
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
                <p class="text-base font-black text-slate-900">아직 이전 답변은 없습니다.</p>
                <p class="mt-2 text-sm leading-6">첫 질문을 보내면 최신 답변 아래에 이전 기록이 차례대로 쌓입니다.</p>
            </div>
        `;
    }

    function showInlineError(element, message) {
        if (!element) return;
        element.textContent = message || "";
        element.classList.toggle("is-visible", Boolean(message));
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
        const quickButtons = Array.from(root.querySelectorAll("[data-teacher-law-quick-question='true']"));

        let isSubmitting = false;
        let progressTimers = [];
        let longWaitTimer = null;
        let latestPair = latestPairData && latestPairData.user_message && latestPairData.assistant_message ? latestPairData : null;
        let historyPairs = Array.isArray(historyPairData) ? historyPairData.filter(Boolean) : [];
        const uiBlocked = root.dataset.uiBlocked === "true";

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

        function clearProgressTimers() {
            progressTimers.forEach((timerId) => window.clearTimeout(timerId));
            progressTimers = [];
            if (longWaitTimer) {
                window.clearTimeout(longWaitTimer);
                longWaitTimer = null;
            }
        }

        function setSubmittingState(nextState) {
            isSubmitting = nextState;
            const disabled = nextState || uiBlocked;
            if (input) input.disabled = disabled;
            if (sendButton) sendButton.disabled = disabled;
            quickButtons.forEach(function (button) {
                button.disabled = disabled;
            });
        }

        function syncPlaceholderText(message) {
            const placeholder = latestContainer.querySelector("[data-teacher-law-placeholder-summary='true']");
            if (placeholder) placeholder.textContent = message;
        }

        function startProgressSequence() {
            if (!progress || !progressText) return;
            progress.classList.add("is-visible");
            progressText.textContent = "질문 정리 중...";
            renderLatestPair(buildLatestPlaceholderHtml("질문 정리 중..."));
            progressTimers = [
                window.setTimeout(function () {
                    progressText.textContent = "관련 법령 검색 중...";
                    syncPlaceholderText("관련 법령 검색 중...");
                }, 2000),
                window.setTimeout(function () {
                    progressText.textContent = "근거 조문 확인 중...";
                    syncPlaceholderText("근거 조문 확인 중...");
                }, 4000),
                window.setTimeout(function () {
                    progressText.textContent = "가이드 정리 중...";
                    syncPlaceholderText("가이드 정리 중...");
                }, 6000),
            ];
            longWaitTimer = window.setTimeout(function () {
                const message = "조금 오래 걸리고 있어요. 근거를 다시 확인하는 중입니다.";
                progressText.textContent = message;
                syncPlaceholderText(message);
            }, 10000);
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

        async function submitQuestion(question) {
            if (!question || isSubmitting || uiBlocked) return;
            showInlineError(errorBox, "");
            setSubmittingState(true);
            startProgressSequence();

            try {
                const response = await fetch(askUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": form.querySelector("[name='csrfmiddlewaretoken']").value,
                    },
                    body: JSON.stringify({ question }),
                });
                const data = await response.json().catch(function () {
                    return {};
                });
                if (!response.ok) {
                    throw new Error(data.message || "답변을 준비하지 못했습니다.");
                }
                const nextPair = buildPairFromResponse(data, question);
                if (latestPair) {
                    historyPairs = [latestPair].concat(historyPairs).slice(0, 6);
                }
                latestPair = nextPair;
                stopProgressSequence();
                renderHistory();
                if (input) input.value = "";
            } catch (error) {
                stopProgressSequence();
                const message = error && error.message ? error.message : "답변을 준비하지 못했습니다.";
                showInlineError(errorBox, message);
                dispatchToast(message, "error");
            } finally {
                setSubmittingState(false);
            }
        }

        renderLatest();
        renderHistory();
        setSubmittingState(false);

        form.addEventListener("submit", function (event) {
            event.preventDefault();
            if (uiBlocked) return;
            const question = String(input.value || "").trim();
            if (!question) {
                const message = "질문을 입력해 주세요.";
                showInlineError(errorBox, message);
                dispatchToast(message, "warning");
                input.focus();
                return;
            }
            submitQuestion(question);
        });

        quickButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                if (uiBlocked) return;
                const question = String(button.dataset.question || "").trim();
                if (!question) return;
                input.value = question;
                input.focus();
            });
        });
    });
}());
