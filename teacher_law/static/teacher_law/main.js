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

    function buildUserMessageHtml(message) {
        return `
            <div class="teacher-law-message-row teacher-law-message-row--user">
                <article class="teacher-law-message-card teacher-law-message-card--user">
                    <div class="teacher-law-meta teacher-law-meta--user">
                        <span>질문</span>
                        <time datetime="${escapeHtml(message.created_at || "")}">${escapeHtml(formatDate(message.created_at))}</time>
                    </div>
                    <p class="teacher-law-summary">${escapeHtml(message.body || "")}</p>
                </article>
            </div>
        `;
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

    function buildAssistantMessageHtml(message) {
        const actionItems = Array.isArray(message.action_items) ? message.action_items.filter(Boolean) : [];
        const citations = Array.isArray(message.citations) ? message.citations : [];
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
        const disclaimerHtml = message.disclaimer
            ? `<p class="teacher-law-disclaimer">${escapeHtml(message.disclaimer)}</p>`
            : "";
        return `
            <div class="teacher-law-message-row teacher-law-message-row--assistant">
                <article class="teacher-law-message-card teacher-law-message-card--assistant">
                    <div class="teacher-law-meta teacher-law-meta--assistant">
                        <span>법률 가이드</span>
                        <time datetime="${escapeHtml(message.created_at || "")}">${escapeHtml(formatDate(message.created_at))}</time>
                    </div>
                    <p class="teacher-law-summary">${escapeHtml(message.summary || message.body || "")}</p>
                    ${actionHtml}
                    ${citationHtml}
                    ${disclaimerHtml}
                </article>
            </div>
        `;
    }

    function buildPlaceholderHtml(progressText) {
        return `
            <div class="teacher-law-message-row teacher-law-message-row--placeholder" data-teacher-law-placeholder="true">
                <article class="teacher-law-message-card teacher-law-message-card--placeholder">
                    <div class="teacher-law-meta teacher-law-meta--assistant">
                        <span>법률 가이드 준비 중</span>
                        <span>진행 중</span>
                    </div>
                    <p class="teacher-law-summary">${escapeHtml(progressText)}</p>
                </article>
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
        const initialMessages = parseJsonScript("teacher-law-message-data", []);
        const form = root.querySelector("[data-teacher-law-form='true']");
        const input = root.querySelector("[data-teacher-law-input='true']");
        const sendButton = root.querySelector("[data-teacher-law-send='true']");
        const progress = root.querySelector("[data-teacher-law-progress='true']");
        const progressText = root.querySelector("[data-teacher-law-progress-text='true']");
        const errorBox = root.querySelector("[data-teacher-law-error='true']");
        const messageList = root.querySelector("[data-teacher-law-message-list='true']");
        const quickButtons = Array.from(root.querySelectorAll("[data-teacher-law-quick-question='true']"));

        let isSubmitting = false;
        let progressTimers = [];
        let longWaitTimer = null;

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
            if (input) input.disabled = nextState;
            if (sendButton) sendButton.disabled = nextState;
            quickButtons.forEach((button) => {
                button.disabled = nextState;
            });
        }

        function ensureEmptyStateRemoved() {
            const empty = messageList.querySelector("[data-teacher-law-empty='true']");
            if (empty) empty.remove();
        }

        function appendMessageHtml(html) {
            ensureEmptyStateRemoved();
            messageList.insertAdjacentHTML("beforeend", html);
            messageList.scrollTop = messageList.scrollHeight;
        }

        function removePlaceholder() {
            const placeholder = messageList.querySelector("[data-teacher-law-placeholder='true']");
            if (placeholder) placeholder.remove();
        }

        function syncPlaceholderText(message) {
            const placeholder = messageList.querySelector("[data-teacher-law-placeholder='true'] .teacher-law-summary");
            if (placeholder) placeholder.textContent = message;
        }

        function startProgressSequence() {
            if (!progress || !progressText) return;
            progress.classList.add("is-visible");
            progressText.textContent = "질문 정리 중...";
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
            removePlaceholder();
        }

        async function submitQuestion(question) {
            if (!question || isSubmitting) return;
            showInlineError(errorBox, "");
            setSubmittingState(true);
            ensureEmptyStateRemoved();
            appendMessageHtml(buildPlaceholderHtml("질문 정리 중..."));
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
                stopProgressSequence();
                appendMessageHtml(buildUserMessageHtml(data.user_message || { body: question, created_at: new Date().toISOString() }));
                appendMessageHtml(buildAssistantMessageHtml(data.assistant_message || {}));
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

        if (Array.isArray(initialMessages) && initialMessages.length) {
            messageList.scrollTop = messageList.scrollHeight;
        }

        form.addEventListener("submit", function (event) {
            event.preventDefault();
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
                const question = String(button.dataset.question || "").trim();
                if (!question) return;
                input.value = question;
                input.focus();
            });
        });
    });
}());
