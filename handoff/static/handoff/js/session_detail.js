(function () {
    var config = window.handoffSessionConfig || {};
    var receiptList = document.getElementById("receiptList");
    if (!receiptList) return;

    var filterButtons = Array.prototype.slice.call(document.querySelectorAll(".filter-btn"));
    var searchInput = document.getElementById("searchInput");
    var emptyState = document.getElementById("emptyState");
    var countTotal = document.getElementById("countTotal");
    var countReceived = document.getElementById("countReceived");
    var countPending = document.getElementById("countPending");
    var copyPendingButton = document.getElementById("copyPendingBtn");
    var undoToast = document.getElementById("undoToast");
    var undoText = document.getElementById("undoText");
    var undoButton = document.getElementById("undoButton");

    var rows = Array.prototype.slice.call(document.querySelectorAll(".receipt-row"));
    var currentFilter = "pending";
    var undoTimer = null;
    var undoTarget = null;

    function getChosung(text) {
        var chosung = [
            "ㄱ",
            "ㄲ",
            "ㄴ",
            "ㄷ",
            "ㄸ",
            "ㄹ",
            "ㅁ",
            "ㅂ",
            "ㅃ",
            "ㅅ",
            "ㅆ",
            "ㅇ",
            "ㅈ",
            "ㅉ",
            "ㅊ",
            "ㅋ",
            "ㅌ",
            "ㅍ",
            "ㅎ",
        ];
        var result = "";
        for (var i = 0; i < text.length; i += 1) {
            var code = text.charCodeAt(i);
            if (code >= 44032 && code <= 55203) {
                result += chosung[Math.floor((code - 44032) / 588)];
            } else {
                result += text[i];
            }
        }
        return result.toLowerCase();
    }

    function initSearchTokens() {
        rows.forEach(function (row) {
            var name = (row.dataset.name || "").trim();
            row.dataset.nameLower = name.toLowerCase();
            row.dataset.nameChosung = getChosung(name);
        });
    }

    function updateFilterButtons() {
        filterButtons.forEach(function (button) {
            var active = button.dataset.filter === currentFilter;
            if (active) {
                button.classList.remove("bg-white", "text-gray-700", "border", "border-gray-200");
                button.classList.add("bg-rose-600", "text-white");
            } else {
                button.classList.remove("bg-rose-600", "text-white");
                button.classList.add("bg-white", "text-gray-700", "border", "border-gray-200");
            }
        });
    }

    function rowMatchesFilter(row) {
        var state = row.dataset.state;
        if (currentFilter === "all") return true;
        return state === currentFilter;
    }

    function rowMatchesSearch(row, query) {
        if (!query) return true;
        var name = row.dataset.nameLower || "";
        var chosung = row.dataset.nameChosung || "";
        return name.indexOf(query) >= 0 || chosung.indexOf(query) >= 0;
    }

    function renderRows() {
        var query = (searchInput ? searchInput.value : "").trim().toLowerCase();
        var visibleCount = 0;
        rows.forEach(function (row) {
            var visible = rowMatchesFilter(row) && rowMatchesSearch(row, query);
            row.classList.toggle("hidden", !visible);
            if (visible) visibleCount += 1;
        });
        if (emptyState) {
            emptyState.classList.toggle("hidden", visibleCount > 0);
        }
    }

    function updateCounts(counts) {
        if (countTotal) countTotal.textContent = String(counts.total);
        if (countReceived) countReceived.textContent = String(counts.received);
        if (countPending) countPending.textContent = String(counts.pending);
    }

    function getMetaText(receipt) {
        if (receipt.state === "received") {
            var chunks = [];
            if (receipt.received_at_display) chunks.push(receipt.received_at_display + " 처리");
            if (receipt.processed_by) chunks.push(receipt.processed_by);
            if (receipt.handoff_type_label) chunks.push(receipt.handoff_type_label);
            if (receipt.memo) chunks.push(receipt.memo);
            if (chunks.length) return chunks.join(" · ");
            return "수령 완료";
        }
        return "아직 수령 확인 전";
    }

    function setRowState(row, receipt) {
        var nextState = receipt.state;
        row.dataset.state = nextState;

        var badge = row.querySelector(".state-badge");
        if (badge) {
            badge.textContent = receipt.state_label;
            badge.classList.remove("bg-emerald-100", "text-emerald-700", "bg-rose-100", "text-rose-700");
            if (nextState === "received") {
                badge.classList.add("bg-emerald-100", "text-emerald-700");
            } else {
                badge.classList.add("bg-rose-100", "text-rose-700");
            }
        }

        row.classList.remove("border-gray-200", "border-emerald-200", "bg-emerald-50/40");
        if (nextState === "received") {
            row.classList.add("border-emerald-200", "bg-emerald-50/40");
        } else {
            row.classList.add("border-gray-200");
        }

        var meta = row.querySelector(".receipt-meta");
        if (meta) meta.textContent = getMetaText(receipt);

        var form = row.querySelector(".receipt-state-form");
        if (!form) return;
        var hiddenState = form.querySelector("input[name='state']");
        var button = form.querySelector(".state-button");
        if (!hiddenState || !button) return;

        if (nextState === "received") {
            hiddenState.value = "pending";
            button.textContent = "되돌리기";
            button.classList.remove("bg-emerald-600", "hover:bg-emerald-500", "text-white");
            button.classList.add("bg-gray-200", "hover:bg-gray-300", "text-gray-700");
        } else {
            hiddenState.value = "received";
            button.textContent = "수령 체크";
            button.classList.remove("bg-gray-200", "hover:bg-gray-300", "text-gray-700");
            button.classList.add("bg-emerald-600", "hover:bg-emerald-500", "text-white");
        }
    }

    function hideUndoToast() {
        if (!undoToast) return;
        undoToast.classList.add("hidden");
        undoTarget = null;
        if (undoTimer) {
            clearTimeout(undoTimer);
            undoTimer = null;
        }
    }

    function showUndoToast(row, previousState, changedState, memberName) {
        if (!undoToast || !undoText || !undoButton) return;
        if (changedState !== "received" || previousState !== "pending") {
            hideUndoToast();
            return;
        }
        undoTarget = {
            row: row,
            state: "pending",
        };
        undoText.textContent = memberName + " 수령 처리됨";
        undoToast.classList.remove("hidden");
        if (undoTimer) clearTimeout(undoTimer);
        undoTimer = setTimeout(function () {
            hideUndoToast();
        }, 5000);
    }

    function showAlertError(message) {
        window.alert(message || "처리 중 오류가 발생했습니다.");
    }

    async function parseJsonSafe(response) {
        try {
            return await response.json();
        } catch (error) {
            return {};
        }
    }

    async function submitState(row, targetState, sourceButton, suppressUndo) {
        var form = row.querySelector(".receipt-state-form");
        if (!form) return;
        var hiddenState = form.querySelector("input[name='state']");
        if (!hiddenState) return;

        var previousState = row.dataset.state;
        hiddenState.value = targetState;

        var formData = new FormData(form);
        var button = sourceButton || form.querySelector(".state-button");
        if (button) button.disabled = true;

        try {
            var response = await fetch(form.action, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    Accept: "application/json",
                },
                body: formData,
            });
            var data = await parseJsonSafe(response);
            if (!response.ok || !data.success) {
                throw new Error(data.error || "상태 업데이트에 실패했습니다.");
            }

            setRowState(row, data.receipt);
            updateCounts(data.counts);
            renderRows();
            if (!suppressUndo) {
                showUndoToast(row, previousState, data.receipt.state, data.receipt.member_name);
            }
        } catch (error) {
            showAlertError(error.message);
            hiddenState.value = previousState === "received" ? "pending" : "received";
        } finally {
            if (button) button.disabled = false;
        }
    }

    function buildPendingNoticeText() {
        var pendingNames = rows
            .filter(function (row) {
                return row.dataset.state === "pending";
            })
            .map(function (row) {
                return row.dataset.name || "";
            })
            .filter(Boolean);

        if (!pendingNames.length) {
            return "전원 수령 확인 완료되었습니다.";
        }
        var sessionTitle = document.title.split(" - ")[0] || "배부 세션";
        return "[" + sessionTitle + "] 아직 수령 확인이 필요한 분: " + pendingNames.join(", ");
    }

    async function copyPendingNotice() {
        var text = buildPendingNoticeText();
        try {
            await navigator.clipboard.writeText(text);
            window.alert("미수령 안내문을 복사했습니다.");
        } catch (error) {
            showAlertError("클립보드 복사에 실패했습니다.");
        }
    }

    function bindFilters() {
        filterButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                currentFilter = button.dataset.filter || "pending";
                updateFilterButtons();
                renderRows();
            });
        });
        if (searchInput) {
            searchInput.addEventListener("input", renderRows);
        }
    }

    function bindReceiptForms() {
        rows.forEach(function (row) {
            var form = row.querySelector(".receipt-state-form");
            if (!form) return;
            form.addEventListener("submit", function (event) {
                if (!config.isOpen) return;
                event.preventDefault();
                var hiddenState = form.querySelector("input[name='state']");
                var button = form.querySelector(".state-button");
                var targetState = hiddenState ? hiddenState.value : "received";
                submitState(row, targetState, button, false);
            });
        });
    }

    function bindUndo() {
        if (!undoButton) return;
        undoButton.addEventListener("click", function () {
            if (!undoTarget || !undoTarget.row) return;
            submitState(undoTarget.row, undoTarget.state, null, true);
            hideUndoToast();
        });
    }

    function bindCopyButton() {
        if (!copyPendingButton) return;
        copyPendingButton.addEventListener("click", function () {
            copyPendingNotice();
        });
    }

    initSearchTokens();
    bindFilters();
    bindReceiptForms();
    bindUndo();
    bindCopyButton();
    updateFilterButtons();
    renderRows();
})();
