(function () {
    function parseJsonScript(id, fallbackValue) {
        const element = document.getElementById(id);
        if (!element) return fallbackValue;
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error("[developer-chat] failed to parse", id, error);
            return fallbackValue;
        }
    }

    function formatRelativeDate(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return "";
        return new Intl.DateTimeFormat("ko-KR", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        }).format(date);
    }

    function buildThreadUrl(template, threadId) {
        return String(template || "").replace("__thread_id__", String(threadId));
    }

    document.addEventListener("DOMContentLoaded", () => {
        const root = document.querySelector('[data-developer-chat-root="true"]');
        if (!root) return;

        const urls = parseJsonScript("developer-chat-api-urls-data", {});
        const isAdmin = parseJsonScript("developer-chat-admin-flag", false) === true;
        const initialThreadId = String(parseJsonScript("developer-chat-initial-thread-id", "") || "");
        const csrfToken = document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";

        const elements = {
            threadList: root.querySelector('[data-developer-chat-thread-list="true"]'),
            panelTitle: root.querySelector('[data-developer-chat-panel-title="true"]'),
            panelSubtitle: root.querySelector('[data-developer-chat-panel-subtitle="true"]'),
            status: root.querySelector('[data-developer-chat-status="true"]'),
            emptyState: root.querySelector('[data-developer-chat-empty="true"]'),
            messageWrap: root.querySelector('[data-developer-chat-message-wrap="true"]'),
            messageList: root.querySelector('[data-developer-chat-message-list="true"]'),
            composer: root.querySelector('[data-developer-chat-composer="true"]'),
            input: root.querySelector('[data-developer-chat-input="true"]'),
            sendButton: root.querySelector('[data-developer-chat-send="true"]'),
            deleteButton: root.querySelector('[data-developer-chat-delete="true"]'),
            search: root.querySelector('[data-developer-chat-search="true"]'),
            refreshButtons: Array.from(root.querySelectorAll('[data-developer-chat-refresh="true"]')),
            toastRoot: document.getElementById("developer-chat-toast-root"),
        };

        const state = {
            isAdmin,
            initialThreadId,
            threads: [],
            selectedThreadId: "",
            selectedThread: null,
            searchQuery: "",
            isLoadingThreads: false,
            isLoadingDetail: false,
            isSending: false,
            isDeleting: false,
            searchTimer: null,
        };

        function showToast(message, type) {
            if (!elements.toastRoot || !message) return;
            const toast = document.createElement("div");
            toast.className = `developer-chat-toast developer-chat-toast--${type || "info"}`;
            toast.textContent = message;
            elements.toastRoot.appendChild(toast);
            window.setTimeout(() => {
                toast.remove();
            }, 2600);
        }

        async function fetchJson(url, options) {
            const response = await fetch(url, options);
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.message || "요청을 처리하지 못했습니다.");
            }
            return data;
        }

        function setLoadingState() {
            const disabled = state.isLoadingThreads || state.isLoadingDetail || state.isSending || state.isDeleting;
            elements.sendButton.disabled = disabled || !state.selectedThreadId;
            if (elements.deleteButton) {
                elements.deleteButton.disabled = disabled || !state.selectedThreadId;
            }
            elements.refreshButtons.forEach((button) => {
                button.disabled = state.isSending || state.isDeleting;
            });
        }

        function sortThreads() {
            state.threads.sort((left, right) => {
                const leftTime = left.last_message_at ? Date.parse(left.last_message_at) : 0;
                const rightTime = right.last_message_at ? Date.parse(right.last_message_at) : 0;
                return rightTime - leftTime || Number(right.unread_count || 0) - Number(left.unread_count || 0);
            });
        }

        function renderThreadList() {
            elements.threadList.innerHTML = "";
            if (state.isLoadingThreads && state.threads.length === 0) {
                const loading = document.createElement("div");
                loading.className = "developer-chat-message-empty";
                loading.textContent = "대화 목록을 불러오는 중입니다.";
                elements.threadList.appendChild(loading);
                return;
            }

            if (state.threads.length === 0) {
                const empty = document.createElement("div");
                empty.className = "developer-chat-message-empty";
                empty.textContent = state.isAdmin
                    ? "아직 시작된 사용자 대화가 없습니다."
                    : "아직 대화가 시작되지 않았어요.";
                elements.threadList.appendChild(empty);
                return;
            }

            state.threads.forEach((thread) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "developer-chat-thread-item";
                if (String(thread.id) === String(state.selectedThreadId)) {
                    button.classList.add("is-selected");
                }
                button.dataset.threadId = String(thread.id);
                button.innerHTML = `
                    <div class="developer-chat-thread-top">
                        <div class="min-w-0">
                            <div class="developer-chat-thread-title">${thread.title}</div>
                            <div class="developer-chat-thread-subtitle">${thread.subtitle || ""}</div>
                        </div>
                        ${thread.unread_count ? `<span class="developer-chat-thread-unread">${thread.unread_count}</span>` : ""}
                    </div>
                    <div class="developer-chat-thread-preview">${thread.last_message_preview || ""}</div>
                    <div class="developer-chat-thread-bottom">
                        <span class="developer-chat-thread-status">${thread.status_label || "대화"}</span>
                        <span class="developer-chat-thread-time">${formatRelativeDate(thread.last_message_at)}</span>
                    </div>
                `;
                button.addEventListener("click", () => {
                    selectThread(thread.id);
                });
                elements.threadList.appendChild(button);
            });
        }

        function renderEmptyState(message) {
            elements.emptyState.classList.add("is-visible");
            elements.messageWrap.style.display = "none";
            if (message) {
                const body = elements.emptyState.querySelector("p");
                if (body) body.textContent = message;
            }
        }

        function renderMessages(messages) {
            elements.messageList.innerHTML = "";
            if (!messages.length) {
                const empty = document.createElement("div");
                empty.className = "developer-chat-message-empty";
                empty.textContent = state.isAdmin
                    ? "아직 이 대화에 오간 메시지가 없습니다."
                    : "첫 메시지를 보내면 이 자리에서 답장이 이어집니다.";
                elements.messageList.appendChild(empty);
                return;
            }

            messages.forEach((message) => {
                const row = document.createElement("div");
                row.className = `developer-chat-message-row ${message.is_mine ? "developer-chat-message-row--mine" : "developer-chat-message-row--other"}`;
                row.innerHTML = `
                    <div class="developer-chat-message-bubble ${message.is_mine ? "developer-chat-message-bubble--mine" : "developer-chat-message-bubble--other"}">
                        <p class="developer-chat-message-sender">${message.sender_name}</p>
                        <p class="developer-chat-message-body"></p>
                        <div class="developer-chat-message-meta">
                            <span class="developer-chat-message-time">${formatRelativeDate(message.created_at)}</span>
                        </div>
                    </div>
                `;
                row.querySelector(".developer-chat-message-body").textContent = message.body || "";
                elements.messageList.appendChild(row);
            });

            elements.messageList.scrollTop = elements.messageList.scrollHeight;
        }

        function renderSelectedThread() {
            const thread = state.selectedThread;
            if (!thread) {
                elements.panelTitle.textContent = "대화를 선택하면 바로 이어집니다.";
                elements.panelSubtitle.textContent = state.isAdmin
                    ? "왼쪽 목록에서 사용자를 선택해 주세요."
                    : "첫 문의를 남기면 여기서 답장이 이어집니다.";
                elements.status.textContent = "대기 중";
                renderEmptyState();
                setLoadingState();
                return;
            }

            elements.emptyState.classList.remove("is-visible");
            elements.messageWrap.style.display = "";
            elements.panelTitle.textContent = state.isAdmin
                ? thread.participant.display_name
                : "개발자야 도와줘";
            elements.panelSubtitle.textContent = state.isAdmin
                ? thread.participant.secondary_label
                : (thread.assigned_admin_name
                    ? `${thread.assigned_admin_name}님이 확인 중입니다.`
                    : "보낸 문의와 개발자 답장을 이 자리에서 계속 이어갈 수 있어요.");
            elements.status.textContent = thread.status_label || "대화 중";
            renderMessages(thread.messages || []);
            setLoadingState();
        }

        function upsertThreadSummary(thread) {
            const summary = {
                id: thread.id,
                title: thread.title,
                subtitle: thread.subtitle,
                participant_name: thread.participant_name,
                participant_username: thread.participant_username,
                participant_email: thread.participant_email,
                last_message_preview: thread.last_message_preview,
                last_message_at: thread.last_message_at,
                status_label: thread.status_label,
                unread_count: thread.unread_count,
            };
            const existingIndex = state.threads.findIndex((item) => String(item.id) === String(thread.id));
            if (existingIndex >= 0) {
                state.threads.splice(existingIndex, 1, summary);
            } else {
                state.threads.unshift(summary);
            }
            sortThreads();
        }

        async function markSelectedThreadRead(threadId) {
            if (!threadId) return;
            try {
                const data = await fetchJson(buildThreadUrl(urls.read_template, threadId), {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken,
                    },
                });
                state.threads = state.threads.map((thread) => (
                    String(thread.id) === String(threadId)
                        ? { ...thread, unread_count: Number(data.unread_count || 0) }
                        : thread
                ));
                if (state.selectedThread && String(state.selectedThread.id) === String(threadId)) {
                    state.selectedThread.unread_count = Number(data.unread_count || 0);
                }
                renderThreadList();
            } catch (error) {
                console.error("[developer-chat] mark-read failed", error);
            }
        }

        async function loadThreadDetail(threadId, options) {
            if (!threadId) {
                state.selectedThread = null;
                renderSelectedThread();
                return;
            }

            state.isLoadingDetail = true;
            setLoadingState();
            try {
                const data = await fetchJson(buildThreadUrl(urls.detail_template, threadId));
                state.selectedThread = data.thread || null;
                upsertThreadSummary(state.selectedThread);
                renderThreadList();
                renderSelectedThread();
                if ((options?.markRead ?? true) && document.visibilityState === "visible") {
                    await markSelectedThreadRead(threadId);
                }
            } catch (error) {
                state.selectedThread = null;
                renderSelectedThread();
                showToast(error.message, "error");
            } finally {
                state.isLoadingDetail = false;
                setLoadingState();
            }
        }

        async function selectThread(threadId) {
            state.selectedThreadId = String(threadId || "");
            renderThreadList();
            await loadThreadDetail(threadId, { markRead: true });
        }

        async function loadThreads(options) {
            state.isLoadingThreads = true;
            setLoadingState();
            renderThreadList();

            try {
                const queryString = state.searchQuery ? `?q=${encodeURIComponent(state.searchQuery)}` : "";
                const data = await fetchJson(`${urls.list}${queryString}`);
                state.threads = Array.isArray(data.threads) ? data.threads : [];
                sortThreads();

                const desiredThreadId = String(
                    state.selectedThreadId
                    || (options?.preferInitialThread !== false ? state.initialThreadId : "")
                    || (state.threads[0] ? state.threads[0].id : "")
                );
                renderThreadList();

                if (!desiredThreadId) {
                    state.selectedThreadId = "";
                    state.selectedThread = null;
                    renderSelectedThread();
                    return;
                }

                const stillExists = state.threads.some((thread) => String(thread.id) === desiredThreadId);
                if (!stillExists && state.threads.length > 0) {
                    state.selectedThreadId = String(state.threads[0].id);
                } else {
                    state.selectedThreadId = desiredThreadId;
                }

                await loadThreadDetail(state.selectedThreadId, { markRead: options?.markRead ?? true });
            } catch (error) {
                showToast(error.message, "error");
                console.error("[developer-chat] load-threads failed", error);
            } finally {
                state.isLoadingThreads = false;
                setLoadingState();
                renderThreadList();
            }
        }

        async function handleSend(event) {
            event.preventDefault();
            const body = elements.input.value.trim();
            if (!body) {
                showToast("메시지 내용을 입력해 주세요.", "error");
                return;
            }
            if (!state.selectedThreadId) {
                showToast("대화방을 불러오는 중입니다. 잠시 후 다시 시도해 주세요.", "error");
                return;
            }

            state.isSending = true;
            setLoadingState();
            try {
                const data = await fetchJson(buildThreadUrl(urls.send_template, state.selectedThreadId), {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken,
                    },
                    body: JSON.stringify({ body }),
                });
                elements.input.value = "";
                state.selectedThread = data.thread || null;
                upsertThreadSummary(state.selectedThread);
                renderThreadList();
                renderSelectedThread();
            } catch (error) {
                showToast(error.message, "error");
            } finally {
                state.isSending = false;
                setLoadingState();
            }
        }

        async function handleDelete() {
            if (!state.selectedThreadId || !state.selectedThread) {
                showToast("삭제할 대화를 먼저 선택해 주세요.", "error");
                return;
            }

            const confirmMessage = state.isAdmin
                ? `${state.selectedThread.participant.display_name}님과의 대화를 삭제할까요?`
                : "이 대화를 삭제할까요?";
            if (!window.confirm(`${confirmMessage}\n삭제하면 메시지를 되돌릴 수 없습니다.`)) {
                return;
            }

            state.isDeleting = true;
            setLoadingState();
            try {
                const deletingThreadId = state.selectedThreadId;
                await fetchJson(buildThreadUrl(urls.delete_template, deletingThreadId), {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken,
                    },
                });
                state.threads = state.threads.filter((thread) => String(thread.id) !== String(deletingThreadId));
                state.selectedThreadId = "";
                state.selectedThread = null;
                renderThreadList();
                renderSelectedThread();
                showToast("대화를 삭제했어요.", "info");
                await loadThreads({ markRead: false, preferInitialThread: false });
            } catch (error) {
                showToast(error.message, "error");
            } finally {
                state.isDeleting = false;
                setLoadingState();
            }
        }

        elements.composer.addEventListener("submit", handleSend);
        elements.input.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSend(event);
            }
        });
        if (elements.deleteButton) {
            elements.deleteButton.addEventListener("click", handleDelete);
        }

        if (elements.search) {
            elements.search.addEventListener("input", (event) => {
                state.searchQuery = event.target.value.trim();
                window.clearTimeout(state.searchTimer);
                state.searchTimer = window.setTimeout(() => {
                    loadThreads({ markRead: false, preferInitialThread: false });
                }, 220);
            });
        }

        elements.refreshButtons.forEach((button) => {
            button.addEventListener("click", () => {
                loadThreads({ markRead: false, preferInitialThread: false });
            });
        });

        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "visible" && state.selectedThreadId) {
                markSelectedThreadRead(state.selectedThreadId);
            }
        });

        window.setInterval(() => {
            loadThreads({ markRead: false, preferInitialThread: false });
        }, 15000);

        loadThreads({ markRead: true, preferInitialThread: true });
    });
}());
