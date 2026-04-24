"use strict";

(function () {
    function getCookie(name) {
        const parts = document.cookie ? document.cookie.split(";") : [];
        for (const part of parts) {
            const trimmed = part.trim();
            if (trimmed.startsWith(`${name}=`)) {
                return decodeURIComponent(trimmed.slice(name.length + 1));
            }
        }
        return "";
    }

    async function requestJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify(payload || {}),
        });
        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            data = { feedback: "오류" };
        }
        if (!response.ok) {
            const message = data.feedback || "오류";
            throw new Error(message);
        }
        return data;
    }

    function replaceEndpoint(startUrl, sessionId, actionName) {
        return startUrl.replace(/start\/$/, `${sessionId}/${actionName}/`);
    }

    function setText(node, text) {
        if (node) {
            node.textContent = text || "";
        }
    }

    function insertAtCursor(input, value) {
        const start = input.selectionStart ?? input.value.length;
        const end = input.selectionEnd ?? input.value.length;
        input.value = `${input.value.slice(0, start)}${value}${input.value.slice(end)}`;
        const next = start + value.length;
        input.focus();
        input.setSelectionRange(next, next);
    }

    function backspaceAtCursor(input) {
        const start = input.selectionStart ?? input.value.length;
        const end = input.selectionEnd ?? input.value.length;
        if (start !== end) {
            input.value = `${input.value.slice(0, start)}${input.value.slice(end)}`;
            input.setSelectionRange(start, start);
            return;
        }
        if (start > 0) {
            input.value = `${input.value.slice(0, start - 1)}${input.value.slice(start)}`;
            input.setSelectionRange(start - 1, start - 1);
        }
    }

    function removeStateClasses(root) {
        root.classList.remove("is-success", "is-error", "is-hint", "is-ai-move");
    }

    function flashClass(node, className, duration) {
        if (!node) {
            return;
        }
        node.classList.remove(className);
        void node.offsetWidth;
        node.classList.add(className);
        window.setTimeout(() => {
            node.classList.remove(className);
        }, duration || 520);
    }

    function setFeedbackClass(root, payload, fallback) {
        removeStateClasses(root);
        const feedback = String((payload && payload.feedback) || fallback || "");
        const result = String((payload && payload.result) || "");
        if (result === "win" || result === "solved" || feedback === "승리" || feedback === "정답") {
            root.classList.add("is-success");
            return;
        }
        if (result === "lose" || feedback === "AI 승리" || feedback === "다시" || feedback.includes("수 없") || feedback.includes("확인")) {
            root.classList.add("is-error");
            return;
        }
        if (feedback === "힌트") {
            root.classList.add("is-hint");
        }
    }

    function addBurst(root) {
        const panel = root.querySelector(".mg-board-panel");
        if (!panel) {
            return;
        }
        const oldBurst = panel.querySelector(".mg-burst");
        if (oldBurst) {
            oldBurst.remove();
        }
        const burst = document.createElement("div");
        burst.className = "mg-burst";
        const colors = ["#22c55e", "#facc15", "#38bdf8", "#a78bfa", "#fb7185"];
        for (let index = 0; index < 10; index += 1) {
            const sparkle = document.createElement("span");
            sparkle.textContent = "★";
            sparkle.style.setProperty("--x", `${12 + (index * 8)}%`);
            sparkle.style.setProperty("--y", `${22 + ((index % 4) * 14)}%`);
            sparkle.style.setProperty("--c", colors[index % colors.length]);
            burst.appendChild(sparkle);
        }
        panel.appendChild(burst);
        window.setTimeout(() => burst.remove(), 760);
    }

    function initNim() {
        const root = document.querySelector("[data-mg-nim]");
        if (!root) {
            return;
        }

        const startUrl = root.dataset.startUrl;
        const startButton = document.getElementById("mg-nim-start");
        const pilesNode = document.getElementById("mg-nim-piles");
        const statusNode = document.getElementById("mg-nim-status");
        const thoughtNode = document.getElementById("mg-nim-thought");
        let sessionId = "";
        let finished = false;

        function selectedDifficulty() {
            const checked = root.querySelector('input[name="mg-nim-level"]:checked');
            return checked ? checked.value : "mcts";
        }

        function render(payload, options) {
            const renderOptions = options || {};
            sessionId = payload.session_id || sessionId;
            const state = payload.state || {};
            finished = Boolean(state.is_terminal) || payload.result === "win" || payload.result === "lose";
            setText(statusNode, payload.feedback || "내 차례");
            setText(thoughtNode, payload.thought || "");
            setFeedbackClass(root, payload);
            if (payload.ai_move) {
                root.classList.add("is-ai-move");
            }
            if (payload.result === "win" || payload.result === "lose") {
                addBurst(root);
            }
            pilesNode.classList.remove("mg-piles--preview");
            pilesNode.innerHTML = "";

            const piles = Array.isArray(state.piles) ? state.piles : [];
            piles.forEach((pileSize, pileIndex) => {
                const pile = document.createElement("section");
                pile.className = "mg-pile";
                if (pileIndex === renderOptions.selectedPileIndex) {
                    pile.classList.add("is-selected");
                }
                if (payload.ai_move && payload.ai_move.pile_index === pileIndex) {
                    pile.classList.add("is-ai-move");
                }

                const head = document.createElement("div");
                head.className = "mg-pile-head";
                head.innerHTML = `<span>${pileIndex + 1}번</span><span>${pileSize}개</span>`;
                pile.appendChild(head);

                const stones = document.createElement("div");
                stones.className = "mg-stones";
                for (let index = 0; index < pileSize; index += 1) {
                    const stone = document.createElement("span");
                    stone.className = "mg-stone";
                    stones.appendChild(stone);
                }
                pile.appendChild(stones);

                const actions = document.createElement("div");
                actions.className = "mg-take-row";
                for (let take = 1; take <= 3; take += 1) {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.className = "mg-take";
                    button.textContent = `${take}`;
                    button.dataset.pileIndex = String(pileIndex);
                    button.dataset.take = String(take);
                    button.disabled = finished || take > pileSize;
                    button.setAttribute("aria-label", `${pileIndex + 1}번 ${take}개`);
                    actions.appendChild(button);
                }
                pile.appendChild(actions);
                pilesNode.appendChild(pile);
            });
        }

        async function start() {
            startButton.disabled = true;
            setText(statusNode, "보드 준비");
            setText(thoughtNode, "");
            removeStateClasses(root);
            try {
                render(await requestJson(startUrl, { difficulty: selectedDifficulty() }));
                startButton.textContent = "새 판";
            } catch (error) {
                removeStateClasses(root);
                root.classList.add("is-error");
                setText(statusNode, error.message);
            } finally {
                startButton.disabled = false;
            }
        }

        startButton.addEventListener("click", start);
        pilesNode.addEventListener("click", async (event) => {
            const button = event.target.closest(".mg-take");
            if (!button || !sessionId || finished) {
                return;
            }
            button.disabled = true;
            try {
                const moveUrl = replaceEndpoint(startUrl, sessionId, "move");
                render(await requestJson(moveUrl, {
                    pile_index: Number(button.dataset.pileIndex),
                    take: Number(button.dataset.take),
                }), { selectedPileIndex: Number(button.dataset.pileIndex) });
            } catch (error) {
                removeStateClasses(root);
                root.classList.add("is-error");
                setText(statusNode, error.message);
                button.disabled = false;
            }
        });
    }

    function initTwentyFour() {
        const root = document.querySelector("[data-mg-twenty-four]");
        if (!root) {
            return;
        }

        const startUrl = root.dataset.startUrl;
        const startButton = document.getElementById("mg-tf-start");
        const hintButton = document.getElementById("mg-tf-hint");
        const form = document.getElementById("mg-tf-form");
        const input = document.getElementById("mg-tf-expression");
        const submitButton = form.querySelector('button[type="submit"]');
        const padNode = document.getElementById("mg-tf-pad");
        const numbersNode = document.getElementById("mg-tf-numbers");
        const statusNode = document.getElementById("mg-tf-status");
        const hintNode = document.getElementById("mg-tf-hint-text");
        let sessionId = "";
        let solved = false;

        function setInputButtonsDisabled(disabled) {
            padNode.querySelectorAll("button").forEach((button) => {
                button.disabled = disabled;
            });
            numbersNode.querySelectorAll(".mg-number").forEach((button) => {
                button.disabled = disabled;
            });
        }

        function render(payload, options) {
            const renderOptions = options || {};
            sessionId = payload.session_id || sessionId;
            const state = payload.state || {};
            solved = payload.result === "solved";
            setFeedbackClass(root, payload);
            numbersNode.classList.remove("mg-number-row--preview");
            numbersNode.innerHTML = "";
            const numbers = Array.isArray(state.numbers) ? state.numbers : [];
            numbers.forEach((number) => {
                const node = document.createElement("button");
                node.type = "button";
                node.className = "mg-number";
                node.textContent = String(number);
                node.dataset.token = String(number);
                node.setAttribute("aria-label", `${number} 넣기`);
                numbersNode.appendChild(node);
                if (renderOptions.popNumbers) {
                    flashClass(node, "is-pop", 420);
                }
            });
            input.disabled = !sessionId || solved;
            submitButton.disabled = !sessionId || solved;
            hintButton.disabled = !sessionId || solved;
            setInputButtonsDisabled(!sessionId || solved);
            if (solved) {
                input.disabled = true;
            }
            setText(statusNode, payload.value ? `${payload.feedback}: ${payload.value}` : (payload.feedback || "식"));
            if (payload.hint) {
                setText(hintNode, payload.hint);
                root.classList.add("is-hint");
                flashClass(hintNode, "is-pop", 520);
            }
            if (payload.result === "solved") {
                addBurst(root);
            }
            if (payload.feedback === "다시") {
                flashClass(input, "is-error", 420);
            }
        }

        startButton.addEventListener("click", async () => {
            startButton.disabled = true;
            setText(statusNode, "카드 준비");
            setText(hintNode, "");
            removeStateClasses(root);
            input.classList.remove("is-error");
            try {
                render(await requestJson(startUrl, {}), { popNumbers: true });
                input.value = "";
                input.focus();
                startButton.textContent = "새 카드";
            } catch (error) {
                removeStateClasses(root);
                root.classList.add("is-error");
                setText(statusNode, error.message);
            } finally {
                startButton.disabled = false;
            }
        });

        numbersNode.addEventListener("click", (event) => {
            const button = event.target.closest(".mg-number");
            if (!button || !sessionId || solved) {
                return;
            }
            insertAtCursor(input, button.dataset.token || "");
            flashClass(button, "is-pop", 260);
        });

        padNode.addEventListener("click", (event) => {
            const button = event.target.closest("button");
            if (!button || !sessionId || solved) {
                return;
            }
            if (button.dataset.action === "clear") {
                input.value = "";
                input.focus();
                return;
            }
            if (button.dataset.action === "backspace") {
                backspaceAtCursor(input);
                input.focus();
                return;
            }
            insertAtCursor(input, button.dataset.token || "");
        });

        setInputButtonsDisabled(true);

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!sessionId || solved) {
                return;
            }
            submitButton.disabled = true;
            try {
                const answerUrl = replaceEndpoint(startUrl, sessionId, "answer");
                render(await requestJson(answerUrl, { expression: input.value }));
            } catch (error) {
                removeStateClasses(root);
                root.classList.add("is-error");
                flashClass(input, "is-error", 420);
                setText(statusNode, error.message);
            } finally {
                if (!solved) {
                    submitButton.disabled = false;
                }
            }
        });

        hintButton.addEventListener("click", async () => {
            if (!sessionId || solved) {
                return;
            }
            hintButton.disabled = true;
            try {
                const hintUrl = replaceEndpoint(startUrl, sessionId, "hint");
                render(await requestJson(hintUrl, {}));
                flashClass(hintButton, "is-pop", 520);
            } catch (error) {
                removeStateClasses(root);
                root.classList.add("is-error");
                setText(statusNode, error.message);
            } finally {
                if (!solved) {
                    hintButton.disabled = false;
                }
            }
        });
    }

    initNim();
    initTwentyFour();
}());
