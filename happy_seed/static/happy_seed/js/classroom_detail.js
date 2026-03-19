(function () {
    var root = document.getElementById("happy-seed-detail-root");
    var workspace = document.getElementById("happy-seed-workspace");
    var overlay = document.getElementById("HAPPY_SEED_PRESENTATION");

    if (!root || !workspace || !overlay) {
        return;
    }

    var kickerEl = document.getElementById("PRESENTATION_KICKER");
    var iconEl = document.getElementById("PRESENTATION_ICON");
    var headlineEl = document.getElementById("PRESENTATION_HEADLINE");
    var bodyEl = document.getElementById("PRESENTATION_BODY");
    var rewardEl = document.getElementById("PRESENTATION_REWARD");
    var spinnerEl = document.getElementById("PRESENTATION_SPINNER");
    var footerEl = document.getElementById("PRESENTATION_FOOTER");
    var nextButton = document.getElementById("BTN_PRESENTATION_NEXT");
    var restoreFocusEl = null;
    var storagePrefix = "happy-seed:" + (root.dataset.classroomId || "default");
    var seedAmountStorageKey = storagePrefix + ":seed-amount";
    var actionModeStorageKey = storagePrefix + ":action-mode";

    function getCsrfToken() {
        var cookieMatch = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (cookieMatch) {
            return decodeURIComponent(cookieMatch[1]);
        }
        var tokenInput = document.querySelector("[name=csrfmiddlewaretoken]");
        return tokenInput ? tokenInput.value : "";
    }

    function showToast(message, tag) {
        if (!message) {
            return false;
        }
        if (typeof window.dispatchEvent === "function") {
            window.dispatchEvent(
                new CustomEvent("eduitit:toast", {
                    detail: {
                        message: message,
                        tag: tag || "info",
                    },
                })
            );
            return true;
        }
        return false;
    }

    function getWorkspaceState() {
        return workspace.querySelector("[data-classroom-workspace]");
    }

    function getSeedAmountSelect() {
        var workspaceState = getWorkspaceState();
        return workspaceState ? workspaceState.querySelector("[data-seed-amount-select]") : null;
    }

    function getActionModeSelect() {
        var workspaceState = getWorkspaceState();
        return workspaceState ? workspaceState.querySelector("[data-action-mode-select]") : null;
    }

    function getSelectedSeedAmount() {
        var select = getSeedAmountSelect();
        var fallback = select ? String(select.value || "1") : "1";
        try {
            var storedValue = window.localStorage.getItem(seedAmountStorageKey);
            if (storedValue === "1" || storedValue === "3" || storedValue === "5") {
                return storedValue;
            }
        } catch (error) {
            return fallback;
        }
        return fallback;
    }

    function getSelectedActionMode() {
        var select = getActionModeSelect();
        var fallback = select ? String(select.value || "grant") : "grant";
        try {
            var storedValue = window.localStorage.getItem(actionModeStorageKey);
            if (storedValue === "grant" || storedValue === "grant_and_draw" || storedValue === "draw") {
                return storedValue;
            }
        } catch (error) {
            return fallback;
        }
        return fallback;
    }

    function persistSelection(key, value) {
        try {
            window.localStorage.setItem(key, value);
        } catch (error) {
            return;
        }
    }

    function getSeedsPerBloom() {
        var workspaceState = getWorkspaceState();
        var value = workspaceState ? Number(workspaceState.dataset.seedsPerBloom || "10") : 10;
        return Number.isFinite(value) && value > 0 ? value : 10;
    }

    function hasRewards() {
        var workspaceState = getWorkspaceState();
        return !!workspaceState && workspaceState.dataset.hasRewards === "true";
    }

    function isPresentationOpen() {
        return !overlay.classList.contains("hidden");
    }

    function syncBodyScrollLock() {
        if (isPresentationOpen()) {
            document.body.classList.add("overflow-hidden");
        } else {
            document.body.classList.remove("overflow-hidden");
        }
    }

    async function refreshWorkspace() {
        var response = await fetch(root.dataset.workspaceUrl, {
            headers: {
                "X-Requested-With": "fetch",
            },
        });
        if (!response.ok) {
            throw new Error("운영 화면을 새로고침하지 못했습니다.");
        }
        workspace.innerHTML = await response.text();
        syncWorkspaceControls();
    }

    async function requestJson(url, options) {
        var response = await fetch(url, options);
        var payload = null;
        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }

        if (!response.ok || !payload || !payload.ok) {
            throw new Error(
                payload && payload.error && payload.error.message
                    ? payload.error.message
                    : "요청을 처리하지 못했습니다."
            );
        }
        return payload.data || {};
    }

    function setPresentationState(state, payload) {
        var data = payload || {};
        var isLoading = state === "loading";
        var isResult = state === "result";
        var accent = data.accent || state || "idle";

        overlay.dataset.accent = accent;

        kickerEl.textContent = isLoading ? "추첨 중" : isResult ? "추첨 결과" : "발표 모드";
        iconEl.textContent = data.icon || (accent === "win" ? "🌸" : accent === "grow" ? "🌱" : "✨");
        headlineEl.textContent = data.headline || "발표 준비";
        bodyEl.textContent = data.body || "학생 카드의 큰 버튼을 누르면 결과가 큰 화면으로 바로 전환됩니다.";
        footerEl.textContent =
            data.footer || "나의 작은 행동 하나하나가 나의 미래, 너의 미래, 우리 모두의 미래를 행복으로 바꿉니다.";

        if (data.rewardName) {
            rewardEl.textContent = "🎁 " + data.rewardName;
            rewardEl.classList.remove("hidden");
        } else {
            rewardEl.textContent = "";
            rewardEl.classList.add("hidden");
        }

        spinnerEl.classList.toggle("hidden", !isLoading);
        nextButton.classList.toggle("hidden", !isResult);
    }

    async function enterFullscreen() {
        if (!overlay.requestFullscreen || document.fullscreenElement) {
            return;
        }
        try {
            await overlay.requestFullscreen();
        } catch (error) {
            return;
        }
    }

    async function exitFullscreenIfNeeded() {
        if (!document.fullscreenElement || !document.exitFullscreen) {
            return;
        }
        try {
            await document.exitFullscreen();
        } catch (error) {
            return;
        }
    }

    async function openPresentation(trigger, state, payload) {
        restoreFocusEl = trigger || restoreFocusEl || document.getElementById("BTN_PRESENTATION_TOOL");
        overlay.classList.remove("hidden");
        overlay.setAttribute("aria-hidden", "false");
        setPresentationState(state || "idle", payload || {});
        syncBodyScrollLock();
        await enterFullscreen();
    }

    async function closePresentation() {
        overlay.classList.add("hidden");
        overlay.setAttribute("aria-hidden", "true");
        setPresentationState("idle", {});
        await exitFullscreenIfNeeded();
        syncBodyScrollLock();

        var fallbackButton = document.getElementById("BTN_PRESENTATION_TOOL");
        var focusTarget =
            restoreFocusEl && document.contains(restoreFocusEl)
                ? restoreFocusEl
                : fallbackButton && document.contains(fallbackButton)
                  ? fallbackButton
                  : null;
        if (focusTarget && typeof focusTarget.focus === "function") {
            focusTarget.focus();
        }
    }

    function createRequestId() {
        return window.crypto && typeof window.crypto.randomUUID === "function"
            ? window.crypto.randomUUID()
            : String(Date.now());
    }

    function getActionState(card) {
        var actionMode = getSelectedActionMode();
        var seedAmount = Number(getSelectedSeedAmount() || "1");
        var studentSeeds = Number(card.dataset.seedsBalance || "0");
        var studentTickets = Number(card.dataset.tokensAvailable || "0");
        var consentApproved = card.dataset.consentApproved === "true";
        var rewardsReady = hasRewards();
        var seedsPerBloom = getSeedsPerBloom();
        var drawDisabledReason = card.dataset.drawDisabledReason || "지금은 바로 뽑기할 수 없어요.";

        if (actionMode === "grant") {
            return {
                mode: actionMode,
                label: "+" + seedAmount + " 지급",
                enabled: true,
                helper: "같은 위치를 눌러 연속 지급할 수 있어요.",
            };
        }

        if (actionMode === "draw") {
            return {
                mode: actionMode,
                label: "바로 뽑기",
                enabled: consentApproved && rewardsReady && studentTickets > 0,
                helper:
                    consentApproved && rewardsReady && studentTickets > 0
                        ? "결과가 바로 발표 모드로 이어집니다."
                        : drawDisabledReason,
            };
        }

        var projectedTickets = studentTickets;
        if (seedsPerBloom > 0) {
            projectedTickets += Math.floor((studentSeeds + seedAmount) / seedsPerBloom);
        }

        var disabledReason = "";
        if (!rewardsReady) {
            disabledReason = "보상 설정 후 사용할 수 있어요.";
        } else if (!consentApproved) {
            disabledReason = "동의 완료 후 사용할 수 있어요.";
        } else if (projectedTickets < 1) {
            disabledReason = "이번 지급으로는 바로 뽑기할 티켓이 부족해요.";
        }

        return {
            mode: actionMode,
            label: "+" + seedAmount + " 후 바로 뽑기",
            enabled: disabledReason === "",
            helper:
                disabledReason === ""
                    ? "씨앗 지급 뒤 바로 발표 모드로 전환됩니다."
                    : disabledReason,
        };
    }

    function applyPrimaryActionState(card) {
        var button = card.querySelector("[data-student-primary-action]");
        var helper = card.querySelector("[data-student-action-helper]");
        if (!button || !helper) {
            return;
        }

        var state = getActionState(card);
        button.dataset.actionMode = state.mode;
        button.dataset.actionSeedAmount = getSelectedSeedAmount();
        button.textContent = state.label;
        button.disabled = !state.enabled;
        helper.textContent = state.helper;

        if (state.enabled) {
            button.className =
                "w-full rounded-[1.25rem] bg-slate-900 px-4 py-3 text-sm font-black text-white transition hover:bg-slate-800";
            helper.className = "mt-2 min-h-[20px] text-xs text-slate-400";
        } else {
            button.className =
                "w-full cursor-not-allowed rounded-[1.25rem] bg-slate-200 px-4 py-3 text-sm font-black text-slate-400 transition";
            helper.className = "mt-2 min-h-[20px] text-xs text-amber-600";
        }
    }

    function syncWorkspaceControls() {
        var seedSelect = getSeedAmountSelect();
        var actionModeSelect = getActionModeSelect();
        var selectedSeedAmount = getSelectedSeedAmount();
        var selectedActionMode = getSelectedActionMode();

        if (seedSelect) {
            seedSelect.value = selectedSeedAmount;
        }
        if (actionModeSelect) {
            actionModeSelect.value = selectedActionMode;
        }

        Array.prototype.forEach.call(
            workspace.querySelectorAll("[data-student-card]"),
            function (card) {
                applyPrimaryActionState(card);
            }
        );
    }

    async function handleSeedGrantAction(card, button, seedAmount) {
        var studentName = card.dataset.studentName || "학생";
        var url = card.dataset.seedGrantUrl;

        button.disabled = true;
        try {
            var data = await requestJson(url, {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: new URLSearchParams({
                    amount: String(seedAmount),
                    detail: "운영 화면 전역 액션 지급",
                }).toString(),
            });
            showToast(data.message || studentName + " 학생에게 씨앗을 지급했습니다.", "success");
            await refreshWorkspace();
        } catch (error) {
            if (!showToast(error.message || "씨앗 지급에 실패했습니다.", "error")) {
                window.alert(error.message || "씨앗 지급에 실패했습니다.");
            }
            applyPrimaryActionState(card);
        }
    }

    async function handleDrawAction(card, button) {
        var studentId = card.dataset.studentId;
        var studentName = card.dataset.studentName || "학생";
        var requestId = createRequestId();

        button.disabled = true;
        try {
            await openPresentation(button, "loading", {
                icon: "🎯",
                accent: "loading",
                headline: studentName + " 학생 추첨 중",
                body: "결과를 불러오고 있습니다. 아이들과 함께 기다려 주세요.",
            });

            var data = await requestJson(root.dataset.drawApiUrl, {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                    "Idempotency-Key": requestId,
                    "X-Request-Id": requestId,
                },
                body: JSON.stringify({
                    student_id: studentId,
                    idempotency_key: requestId,
                }),
            });

            var presentation = data.presentation || {};
            setPresentationState("result", {
                accent: presentation.accent || (data.result === "WIN" ? "win" : "grow"),
                icon: data.result === "WIN" ? "🌸" : "🌱",
                headline: presentation.headline,
                body: presentation.body,
                rewardName: presentation.reward_name,
                footer: presentation.footer,
            });
            showToast(studentName + " 학생 추첨 결과를 발표 모드로 전환했습니다.", "success");
            refreshWorkspace().catch(function (error) {
                showToast(error.message || "운영 화면 새로고침에 실패했습니다.", "error");
            });
        } catch (error) {
            setPresentationState("idle", {
                icon: "⚠️",
                accent: "idle",
                headline: "다시 시도해 주세요",
                body: error.message || "추첨을 처리하지 못했습니다.",
            });
            if (!showToast(error.message || "추첨에 실패했습니다.", "error")) {
                window.alert(error.message || "추첨에 실패했습니다.");
            }
            applyPrimaryActionState(card);
        }
    }

    async function handleGrantAndDrawAction(card, button, seedAmount) {
        var studentId = card.dataset.studentId;
        var studentName = card.dataset.studentName || "학생";
        var requestId = createRequestId();

        button.disabled = true;
        try {
            await openPresentation(button, "loading", {
                icon: "🌱",
                accent: "loading",
                headline: studentName + " 학생 지급 후 추첨 중",
                body: "씨앗을 지급하고 바로 결과를 불러오고 있습니다.",
            });

            var data = await requestJson(root.dataset.grantDrawApiUrl, {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                    "Idempotency-Key": requestId,
                    "X-Request-Id": requestId,
                },
                body: JSON.stringify({
                    student_id: studentId,
                    seed_amount: Number(seedAmount),
                    idempotency_key: requestId,
                }),
            });

            var presentation = data.presentation || {};
            setPresentationState("result", {
                accent: presentation.accent || (data.result === "WIN" ? "win" : "grow"),
                icon: data.result === "WIN" ? "🌸" : "🌱",
                headline: presentation.headline,
                body: presentation.body,
                rewardName: presentation.reward_name,
                footer: presentation.footer,
            });
            showToast(
                studentName + " 학생에게 씨앗 " + seedAmount + "개 지급 후 바로 추첨했습니다.",
                "success"
            );
            refreshWorkspace().catch(function (error) {
                showToast(error.message || "운영 화면 새로고침에 실패했습니다.", "error");
            });
        } catch (error) {
            setPresentationState("idle", {
                icon: "⚠️",
                accent: "idle",
                headline: "다시 시도해 주세요",
                body: error.message || "지급 후 바로 뽑기를 처리하지 못했습니다.",
            });
            if (!showToast(error.message || "지급 후 바로 뽑기에 실패했습니다.", "error")) {
                window.alert(error.message || "지급 후 바로 뽑기에 실패했습니다.");
            }
            applyPrimaryActionState(card);
        }
    }

    async function handlePrimaryAction(button) {
        var card = button.closest("[data-student-card]");
        if (!card || button.disabled) {
            return;
        }

        var mode = button.dataset.actionMode || getSelectedActionMode();
        var seedAmount = button.dataset.actionSeedAmount || getSelectedSeedAmount();

        if (mode === "grant") {
            await handleSeedGrantAction(card, button, seedAmount);
            return;
        }

        if (mode === "grant_and_draw") {
            await handleGrantAndDrawAction(card, button, seedAmount);
            return;
        }

        await handleDrawAction(card, button);
    }

    async function handleGroupMission(form) {
        var submitButton = form.querySelector("button[type=submit]");
        var groupIdInput = form.querySelector("[name=group_id]");
        var winnersCountInput =
            form.querySelector("[data-group-winners-count]") || form.querySelector("[name=draw_count]");

        if (!groupIdInput || !winnersCountInput) {
            return;
        }

        if (submitButton) {
            submitButton.disabled = true;
        }

        try {
            var data = await requestJson(root.dataset.groupMissionApiUrl, {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify({
                    group_id: groupIdInput.value,
                    winners_count: Number(winnersCountInput.value || "1"),
                }),
            });
            var winnerNames = (data.winner_names || []).join(", ");
            showToast(
                winnerNames
                    ? winnerNames + " 학생에게 모둠 티켓을 지급했습니다."
                    : "모둠 미션 보상을 적용했습니다.",
                "success"
            );
            await refreshWorkspace();
        } catch (error) {
            if (!showToast(error.message || "모둠 미션 보상 적용에 실패했습니다.", "error")) {
                window.alert(error.message || "모둠 미션 보상 적용에 실패했습니다.");
            }
            if (submitButton) {
                submitButton.disabled = false;
            }
        }
    }

    document.addEventListener("change", function (event) {
        var seedAmountSelect = event.target.closest("[data-seed-amount-select]");
        if (seedAmountSelect) {
            persistSelection(seedAmountStorageKey, String(seedAmountSelect.value || "1"));
            syncWorkspaceControls();
            return;
        }

        var actionModeSelect = event.target.closest("[data-action-mode-select]");
        if (actionModeSelect) {
            persistSelection(actionModeStorageKey, String(actionModeSelect.value || "grant"));
            syncWorkspaceControls();
        }
    });

    document.addEventListener("click", function (event) {
        var presentationButton = event.target.closest("[data-presentation-open]");
        if (presentationButton) {
            event.preventDefault();
            openPresentation(presentationButton, "idle", {
                accent: "idle",
                icon: "✨",
                headline: "발표 준비",
                body: "학생 카드의 큰 버튼을 누르면 결과가 큰 화면으로 바로 전환됩니다.",
            });
            return;
        }

        var actionButton = event.target.closest("[data-student-primary-action]");
        if (actionButton) {
            event.preventDefault();
            handlePrimaryAction(actionButton);
            return;
        }

        var closeButton = event.target.closest("[data-presentation-close]");
        if (closeButton) {
            event.preventDefault();
            closePresentation();
            return;
        }

        var nextPresentationButton = event.target.closest("[data-presentation-next]");
        if (nextPresentationButton) {
            event.preventDefault();
            closePresentation();
        }
    });

    document.addEventListener("submit", function (event) {
        var groupMissionForm = event.target.closest("[data-group-mission-form]");
        if (!groupMissionForm) {
            return;
        }
        event.preventDefault();
        handleGroupMission(groupMissionForm);
    });

    overlay.addEventListener("click", function (event) {
        if (event.target === overlay) {
            closePresentation();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") {
            return;
        }
        if (isPresentationOpen()) {
            closePresentation();
        }
    });

    syncWorkspaceControls();
})();
