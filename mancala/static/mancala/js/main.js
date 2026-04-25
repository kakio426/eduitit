import * as THREE from "../vendor/three/three.module.min.js";

const root = document.querySelector("[data-mancala-root]");

if (root) {
    const canvas = root.querySelector("[data-mancala-canvas]");
    const loading = root.querySelector("[data-mancala-loading]");
    const statusEl = root.querySelector("[data-mancala-status]");
    const turnChip = root.querySelector("[data-turn-chip]");
    const playHint = root.querySelector("[data-play-hint]");
    const tutorBurst = root.querySelector("[data-tutor-burst]");
    const scorePlayer0 = root.querySelector("[data-score-player0]");
    const scorePlayer1 = root.querySelector("[data-score-player1]");
    const newButton = root.querySelector("[data-new-game]");
    const undoButton = root.querySelector("[data-undo]");
    const aiToggle = root.querySelector("[data-ai-toggle]");
    const guideOpen = root.querySelector("[data-guide-open]");
    const guideModal = root.querySelector("[data-guide-modal]");
    const guideCloseButtons = root.querySelectorAll("[data-guide-close]");
    const csrfToken = root.querySelector("[data-csrf-token]")?.value || "";
    const moveUrl = root.dataset.moveUrl;
    const initialPayload = JSON.parse(document.getElementById("mancala-initial-payload").textContent);

    const pitSpecs = buildPitSpecs();
    const pitsByBoardIndex = new Map(pitSpecs.map((pit) => [pit.boardIndex, pit]));
    const pitsByAction = new Map(pitSpecs.filter((pit) => pit.action !== null).map((pit) => [pit.action, pit]));
    const state = {
        board: initialPayload.state.board.slice(),
        legalActions: initialPayload.state.legal_actions.slice(),
        currentPlayer: initialPayload.state.current_player,
        terminal: initialPayload.state.terminal,
        history: [],
        snapshots: [{ history: [], gameState: initialPayload.state }],
        aiMode: true,
        busy: false,
        hoveredAction: null,
    };
    let guideReturnFocus = null;
    let statusResetTimer = null;
    let burstTimer = null;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf7f1df);

    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    camera.position.set(0, 6.4, 8.3);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const seedGroup = new THREE.Group();
    const labelGroup = new THREE.Group();
    const coachGroup = new THREE.Group();
    const pitMeshes = [];
    const movingSeeds = new THREE.Group();

    const seedGeometry = new THREE.SphereGeometry(0.145, 24, 18);
    const seedMaterials = {
        deep: new THREE.MeshStandardMaterial({ color: 0x673ab7, roughness: 0.34, metalness: 0.08 }),
        lavender: new THREE.MeshStandardMaterial({ color: 0xe6e6fa, roughness: 0.28, metalness: 0.04 }),
    };

    scene.add(seedGroup);
    scene.add(labelGroup);
    scene.add(coachGroup);
    scene.add(movingSeeds);
    setupLights();
    createBoard();
    pitSpecs.forEach(createPit);
    renderSeeds(state.board);
    renderLabels(state.board);
    syncUi();
    restoreGuidance();
    resize();
    loading?.classList.add("is-hidden");
    renderer.setAnimationLoop(render);

    window.addEventListener("resize", resize);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerleave", () => {
        state.hoveredAction = null;
        if (!state.busy) {
            restoreGuidance();
            setHint(hintText());
        }
    });
    canvas.addEventListener("pointerdown", onPointerDown);
    newButton?.addEventListener("click", resetGame);
    undoButton?.addEventListener("click", undoMove);
    aiToggle?.addEventListener("click", toggleAiMode);
    guideOpen?.addEventListener("click", openGuide);
    guideCloseButtons.forEach((button) => button.addEventListener("click", closeGuide));
    document.addEventListener("keydown", onGuideKeydown);

    function buildPitSpecs() {
        const specs = [
            { boardIndex: 0, action: null, player: 1, x: -5.55, z: 0, radius: 0.78, isStore: true },
            { boardIndex: 7, action: null, player: 0, x: 5.55, z: 0, radius: 0.78, isStore: true },
        ];
        for (let index = 0; index < 6; index += 1) {
            const x = -3.55 + index * 1.42;
            specs.push({ boardIndex: index + 1, action: index + 1, player: 0, x, z: 1.32, radius: 0.56, isStore: false });
            const opponentIndex = 13 - index;
            specs.push({ boardIndex: opponentIndex, action: opponentIndex, player: 1, x, z: -1.32, radius: 0.56, isStore: false });
        }
        return specs;
    }

    function setupLights() {
        const hemi = new THREE.HemisphereLight(0xfff8e7, 0x476043, 2.3);
        scene.add(hemi);

        const key = new THREE.DirectionalLight(0xffffff, 2.5);
        key.position.set(4, 7, 5);
        key.castShadow = true;
        key.shadow.mapSize.set(1024, 1024);
        scene.add(key);

        const fill = new THREE.PointLight(0xf4ce62, 55, 12);
        fill.position.set(-4, 3, -2);
        scene.add(fill);
    }

    function createBoard() {
        const boardMaterial = new THREE.MeshStandardMaterial({
            color: 0x9b6037,
            roughness: 0.66,
            metalness: 0.02,
        });
        const board = new THREE.Mesh(new THREE.BoxGeometry(12.6, 0.52, 4.8), boardMaterial);
        board.position.set(0, -0.26, 0);
        board.receiveShadow = true;
        board.castShadow = true;
        scene.add(board);

        const rimMaterial = new THREE.MeshStandardMaterial({ color: 0x6f3d22, roughness: 0.72 });
        [
            { x: 0, z: -2.56, sx: 13, sz: 0.22 },
            { x: 0, z: 2.56, sx: 13, sz: 0.22 },
            { x: -6.42, z: 0, sx: 0.22, sz: 4.8 },
            { x: 6.42, z: 0, sx: 0.22, sz: 4.8 },
        ].forEach((part) => {
            const rim = new THREE.Mesh(new THREE.BoxGeometry(part.sx, 0.22, part.sz), rimMaterial);
            rim.position.set(part.x, 0.02, part.z);
            rim.castShadow = true;
            scene.add(rim);
        });
    }

    function createPit(pit) {
        const disk = new THREE.Mesh(
            new THREE.CylinderGeometry(pit.radius, pit.radius * 0.92, 0.08, 48),
            new THREE.MeshStandardMaterial({ color: 0x432818, roughness: 0.82 })
        );
        disk.position.set(pit.x, 0.06, pit.z);
        disk.receiveShadow = true;
        scene.add(disk);

        const ring = new THREE.Mesh(
            new THREE.TorusGeometry(pit.radius * 1.02, 0.045, 10, 54),
            new THREE.MeshStandardMaterial({ color: 0xbe8a52, roughness: 0.48, emissive: 0x000000 })
        );
        ring.rotation.x = Math.PI / 2;
        ring.position.set(pit.x, 0.12, pit.z);
        scene.add(ring);

        const hit = new THREE.Mesh(
            new THREE.CylinderGeometry(pit.radius * 1.08, pit.radius * 1.08, 0.28, 36),
            new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
        );
        hit.position.set(pit.x, 0.16, pit.z);
        hit.userData.action = pit.action;
        hit.userData.boardIndex = pit.boardIndex;
        hit.userData.selectable = pit.action !== null;
        scene.add(hit);
        pitMeshes.push(hit);

        pit.disk = disk;
        pit.ring = ring;
    }

    function onPointerMove(event) {
        if (state.busy || state.terminal) {
            return;
        }
        const action = actionFromPointer(event);
        if (action === state.hoveredAction) {
            return;
        }
        state.hoveredAction = action;
        if (isLegalAction(action)) {
            highlightAction(action);
            setHint(previewHint(action));
        } else {
            restoreGuidance();
            setHint(hintText());
        }
    }

    function onPointerDown(event) {
        if (state.busy || state.terminal) {
            return;
        }
        const action = actionFromPointer(event);
        if (!isLegalAction(action)) {
            showInvalidSelection(action);
            return;
        }
        highlightAction(action);
        setHint(previewHint(action));
        window.setTimeout(() => submitMove(action), 180);
    }

    function actionFromPointer(event) {
        const rect = canvas.getBoundingClientRect();
        pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        raycaster.setFromCamera(pointer, camera);
        const hit = raycaster.intersectObjects(pitMeshes, false)[0];
        return hit?.object?.userData?.action ?? null;
    }

    function isLegalAction(action) {
        return Number.isInteger(action) && state.legalActions.includes(action);
    }

    function showInvalidSelection(action) {
        if (!Number.isInteger(action)) {
            return;
        }
        const pit = pitsByAction.get(action);
        if (!pit) {
            return;
        }
        setTemporaryStatus(pit.player === state.currentPlayer ? "씨앗 있는 칸" : "내 쪽 선택");
    }

    async function submitMove(action) {
        if (state.busy || !isLegalAction(action)) {
            return;
        }
        setBusy(true, state.aiMode ? "AI 생각" : "이동 중");
        try {
            const response = await fetch(moveUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    history: state.history,
                    action,
                    mode: state.aiMode ? "ai" : "local",
                }),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || payload.ok === false) {
                throw new Error(payload.error || "이동 실패");
            }

            for (const move of payload.moves) {
                await animateMove(move);
                await showMoveResult(move);
            }
            applyGameState(payload.state, payload.history);
            state.snapshots.push({ history: payload.history.slice(), gameState: payload.state });
        } catch (error) {
            showError(error.message || "이동 실패");
            renderSeeds(state.board);
            renderLabels(state.board);
        } finally {
            setBusy(false);
            syncUi();
        }
    }

    function applyGameState(gameState, history) {
        state.board = gameState.board.slice();
        state.legalActions = gameState.legal_actions.slice();
        state.currentPlayer = gameState.current_player;
        state.terminal = gameState.terminal;
        state.history = history.slice();
        renderSeeds(state.board);
        renderLabels(state.board);
        restoreGuidance();
    }

    async function animateMove(move) {
        const beforeBoard = move.before.board.slice();
        const workingBoard = beforeBoard.slice();
        const originPit = pitsByBoardIndex.get(move.action);
        const originColor = seedMaterialForIndex(move.action);

        workingBoard[move.action] = 0;
        renderSeeds(workingBoard);
        renderLabels(workingBoard);

        for (const destination of move.path) {
            await animateSeedArc(originPit, pitsByBoardIndex.get(destination), originColor);
            workingBoard[destination] += 1;
            renderSeeds(workingBoard);
            renderLabels(workingBoard);
        }

        state.board = move.after.board.slice();
        renderSeeds(state.board);
        renderLabels(state.board);
    }

    function animateSeedArc(fromPit, toPit, material) {
        if (!fromPit || !toPit) {
            return Promise.resolve();
        }
        const seed = new THREE.Mesh(seedGeometry, material);
        seed.castShadow = true;
        movingSeeds.add(seed);

        const start = new THREE.Vector3(fromPit.x, 0.38, fromPit.z);
        const end = new THREE.Vector3(toPit.x, 0.42, toPit.z);
        const duration = 330;
        const started = performance.now();

        return new Promise((resolve) => {
            function tick(now) {
                const raw = Math.min(1, (now - started) / duration);
                const eased = raw < 0.5 ? 2 * raw * raw : 1 - Math.pow(-2 * raw + 2, 2) / 2;
                seed.position.lerpVectors(start, end, eased);
                seed.position.y += Math.sin(eased * Math.PI) * 1.25;
                seed.rotation.x += 0.12;
                seed.rotation.z += 0.08;
                if (raw < 1) {
                    requestAnimationFrame(tick);
                } else {
                    movingSeeds.remove(seed);
                    resolve();
                }
            }
            requestAnimationFrame(tick);
        });
    }

    function renderSeeds(board) {
        seedGroup.clear();
        pitSpecs.forEach((pit) => {
            const count = board[pit.boardIndex] || 0;
            for (let index = 0; index < count; index += 1) {
                const seed = new THREE.Mesh(seedGeometry, seedMaterialForIndex(pit.boardIndex, index));
                const point = seedPoint(pit, index);
                seed.position.set(point.x, point.y, point.z);
                seed.castShadow = true;
                seedGroup.add(seed);
            }
        });
    }

    function renderLabels(board) {
        labelGroup.clear();
        pitSpecs.forEach((pit) => {
            const label = createNumberSprite(board[pit.boardIndex] || 0, pit.isStore);
            label.position.set(pit.x, pit.isStore ? 1.05 : 0.82, pit.z);
            labelGroup.add(label);
        });
    }

    function seedPoint(pit, index) {
        const angle = index * 2.399963;
        const ring = Math.sqrt(index + 1) * (pit.isStore ? 0.105 : 0.078);
        const radius = Math.min(pit.radius * 0.6, ring);
        const stack = Math.floor(index / (pit.isStore ? 12 : 8));
        return {
            x: pit.x + Math.cos(angle) * radius,
            y: 0.22 + stack * 0.075,
            z: pit.z + Math.sin(angle) * radius,
        };
    }

    function createNumberSprite(value, isStore) {
        const size = 128;
        const labelCanvas = document.createElement("canvas");
        labelCanvas.width = size;
        labelCanvas.height = size / 2;
        const context = labelCanvas.getContext("2d");
        context.fillStyle = "rgba(255, 255, 255, 0.88)";
        roundRect(context, 20, 8, 88, 48, 18);
        context.fill();
        context.fillStyle = isStore ? "#5a3d00" : "#2c2118";
        context.font = "900 34px sans-serif";
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillText(String(value), 64, 33);

        const texture = new THREE.CanvasTexture(labelCanvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(isStore ? 0.78 : 0.66, isStore ? 0.39 : 0.33, 1);
        return sprite;
    }

    function roundRect(context, x, y, width, height, radius) {
        context.beginPath();
        context.moveTo(x + radius, y);
        context.arcTo(x + width, y, x + width, y + height, radius);
        context.arcTo(x + width, y + height, x, y + height, radius);
        context.arcTo(x, y + height, x, y, radius);
        context.arcTo(x, y, x + width, y, radius);
        context.closePath();
    }

    function seedMaterialForIndex(boardIndex, seedIndex = 0) {
        if (boardIndex === 0 || boardIndex >= 8) {
            return seedIndex % 3 === 0 ? seedMaterials.deep : seedMaterials.lavender;
        }
        return seedIndex % 3 === 0 ? seedMaterials.lavender : seedMaterials.deep;
    }

    function highlightAction(action, options = {}) {
        paintBaseHighlights();
        renderCoachMarker(options.recommended ? action : null);
        const player = state.currentPlayer;
        const path = buildSowPath(state.board, action, player);
        const originPit = pitsByAction.get(action);
        if (originPit) {
            originPit.ring.material.color.set(options.recommended ? 0xf4ce62 : 0x673ab7);
            originPit.ring.material.emissive.set(options.recommended ? 0x5a3d00 : 0x2b154f);
        }
        new Set(path).forEach((boardIndex) => {
            const pit = pitsByBoardIndex.get(boardIndex);
            if (!pit) {
                return;
            }
            pit.ring.material.color.set(0xf4ce62);
            pit.ring.material.emissive.set(0x5a3d00);
        });
    }

    function restoreGuidance() {
        const recommendedAction = findRecommendedAction();
        if (recommendedAction) {
            highlightAction(recommendedAction, { recommended: true });
            return;
        }
        paintBaseHighlights();
        renderCoachMarker(null);
    }

    function paintBaseHighlights() {
        pitSpecs.forEach((pit) => {
            pit.ring.scale.set(1, 1, 1);
            if (isLegalAction(pit.action)) {
                pit.ring.material.color.set(0x3d6540);
                pit.ring.material.emissive.set(0x102510);
            } else {
                pit.ring.material.color.set(0xbe8a52);
                pit.ring.material.emissive.set(0x000000);
            }
        });
    }

    function renderCoachMarker(action) {
        coachGroup.clear();
        const pit = pitsByAction.get(action);
        if (!pit) {
            return;
        }
        const marker = createCoachSprite("추천");
        marker.position.set(pit.x, 1.16, pit.z + 0.16);
        coachGroup.add(marker);
    }

    function createCoachSprite(text) {
        const labelCanvas = document.createElement("canvas");
        labelCanvas.width = 192;
        labelCanvas.height = 96;
        const context = labelCanvas.getContext("2d");
        context.shadowColor = "rgba(90, 61, 0, 0.26)";
        context.shadowBlur = 14;
        context.fillStyle = "#f4ce62";
        roundRect(context, 32, 18, 128, 50, 24);
        context.fill();
        context.shadowBlur = 0;
        context.fillStyle = "#2c2118";
        context.font = "900 30px sans-serif";
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillText(text, 96, 43);

        const texture = new THREE.CanvasTexture(labelCanvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(0.82, 0.41, 1);
        return sprite;
    }

    function findRecommendedAction() {
        if (state.terminal || state.busy || state.currentPlayer !== 0) {
            return null;
        }
        return state.legalActions.find((action) => {
            const path = buildSowPath(state.board, action, state.currentPlayer);
            return path[path.length - 1] === 7;
        }) ?? null;
    }

    function previewHint(action) {
        const path = buildSowPath(state.board, action, state.currentPlayer);
        const last = path[path.length - 1];
        if (last === ownStoreIndex(state.currentPlayer)) {
            return state.currentPlayer === 0 ? "오른쪽 큰 칸까지 갑니다" : "저장소까지 갑니다";
        }
        if (last !== undefined && isOwnPit(last, state.currentPlayer) && (state.board[last] || 0) === 0) {
            return "빈 칸에 끝나면 가져오기";
        }
        return "씨앗 길을 보세요";
    }

    function buildSowPath(board, action, player) {
        const path = [];
        let index = action;
        const seeds = board[action] || 0;
        for (let count = 0; count < seeds; count += 1) {
            index = (index + 1) % 14;
            const opponentStore = player === 0 ? 0 : 7;
            if (index === opponentStore) {
                index = (index + 1) % 14;
            }
            path.push(index);
        }
        return path;
    }

    function resetGame() {
        if (state.busy) {
            return;
        }
        state.snapshots = [{ history: [], gameState: initialPayload.state }];
        applyGameState(initialPayload.state, []);
        syncUi();
        restoreGuidance();
    }

    function undoMove() {
        if (state.busy || state.snapshots.length <= 1) {
            return;
        }
        state.snapshots.pop();
        const snapshot = state.snapshots[state.snapshots.length - 1];
        applyGameState(snapshot.gameState, snapshot.history);
        syncUi();
        restoreGuidance();
    }

    function toggleAiMode() {
        if (state.busy) {
            return;
        }
        state.aiMode = !state.aiMode;
        aiToggle?.classList.toggle("is-active", state.aiMode);
        aiToggle?.setAttribute("aria-pressed", state.aiMode ? "true" : "false");
        syncUi();
    }

    function openGuide() {
        if (!guideModal) {
            return;
        }
        guideReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : guideOpen;
        guideModal.hidden = false;
        guideModal.classList.add("is-open");
        const focusTarget = guideModal.querySelector("[data-guide-close-primary]") || guideModal.querySelector("button");
        window.requestAnimationFrame(() => focusTarget?.focus());
    }

    function closeGuide() {
        if (!guideModal || guideModal.hidden) {
            return;
        }
        guideModal.classList.remove("is-open");
        guideModal.hidden = true;
        guideReturnFocus?.focus();
        guideReturnFocus = null;
    }

    function onGuideKeydown(event) {
        if (event.key === "Escape" && guideModal && !guideModal.hidden) {
            closeGuide();
        }
    }

    function setBusy(isBusy, label = "") {
        clearTemporaryStatus();
        state.busy = isBusy;
        if (label) {
            setStatus(label);
        }
        [newButton, undoButton, aiToggle].forEach((button) => {
            if (button) {
                button.disabled = isBusy;
            }
        });
        setHint(isBusy ? busyHint(label) : hintText());
    }

    function syncUi() {
        scorePlayer0.textContent = String(state.board[7] || 0);
        scorePlayer1.textContent = String(state.board[0] || 0);
        undoButton.disabled = state.busy || state.snapshots.length <= 1;
        aiToggle?.classList.toggle("is-active", state.aiMode);
        aiToggle?.setAttribute("aria-pressed", state.aiMode ? "true" : "false");
        setStatus(statusText());
        setHint(hintText());
    }

    function statusText() {
        if (state.terminal) {
            if ((state.board[7] || 0) === (state.board[0] || 0)) {
                return "무승부";
            }
            return (state.board[7] || 0) > (state.board[0] || 0) ? "승리" : "AI 승리";
        }
        if (state.currentPlayer === 0) {
            return "내 차례";
        }
        return state.aiMode ? "AI 차례" : "상대 차례";
    }

    function setStatus(text) {
        statusEl.textContent = text;
        turnChip.textContent = text;
    }

    function hintText() {
        if (state.terminal) {
            return "새 판으로 다시 시작";
        }
        if (state.currentPlayer === 0) {
            return findRecommendedAction() ? "추천 칸을 눌러 보세요" : "초록 칸을 누르세요";
        }
        return state.aiMode ? "AI가 두는 중" : "상대 줄 차례";
    }

    function busyHint(label) {
        if (label === "AI 생각") {
            return "씨앗 길을 보세요";
        }
        return "씨앗 이동 중";
    }

    function setHint(text) {
        if (playHint) {
            playHint.textContent = text;
        }
    }

    function setTemporaryStatus(text) {
        clearTemporaryStatus();
        setStatus(text);
        statusResetTimer = window.setTimeout(() => {
            statusResetTimer = null;
            if (!state.busy) {
                syncUi();
            }
        }, 950);
    }

    function clearTemporaryStatus() {
        if (statusResetTimer) {
            window.clearTimeout(statusResetTimer);
            statusResetTimer = null;
        }
    }

    function showError(message) {
        setStatus(message);
        window.dispatchEvent(new CustomEvent("eduitit:toast", {
            detail: { message, tag: "error" },
        }));
    }

    async function showMoveResult(move) {
        const result = moveResult(move);
        if (!result) {
            return;
        }
        showTutorBurst(result.text);
        setStatus(result.text);
        setHint(result.hint);
        await wait(620);
    }

    function moveResult(move) {
        const player = move.before.current_player;
        const last = move.path[move.path.length - 1];
        const store = ownStoreIndex(player);
        const isPlayerMove = player === 0;

        if (last === store && move.after.current_player === player && !move.after.terminal) {
            return {
                text: isPlayerMove ? "한 번 더!" : "AI 한 번 더",
                hint: isPlayerMove ? "한 번 더 둘 수 있어요" : "AI가 이어서 둡니다",
            };
        }

        if (last !== undefined && isOwnPit(last, player)) {
            const opposite = 14 - last;
            const storeGain = (move.after.board[store] || 0) - (move.before.board[store] || 0);
            const captured = (move.before.board[last] || 0) === 0
                && (move.before.board[opposite] || 0) > 0
                && (move.after.board[opposite] || 0) === 0
                && storeGain > 1;
            if (captured) {
                return {
                    text: isPlayerMove ? "가져오기!" : "AI 가져오기",
                    hint: isPlayerMove ? "맞은편 씨앗을 가져왔어요" : "AI가 씨앗을 가져갔어요",
                };
            }
        }

        const gain = (move.after.board[store] || 0) - (move.before.board[store] || 0);
        if (gain > 0) {
            return {
                text: isPlayerMove ? `내 저장소 +${gain}` : `AI 저장소 +${gain}`,
                hint: isPlayerMove ? "오른쪽 큰 칸에 들어갔어요" : "AI 저장소에 들어갔어요",
            };
        }
        return null;
    }

    function ownStoreIndex(player) {
        return player === 0 ? 7 : 0;
    }

    function isOwnPit(boardIndex, player) {
        return player === 0
            ? boardIndex >= 1 && boardIndex <= 6
            : boardIndex >= 8 && boardIndex <= 13;
    }

    function showTutorBurst(text) {
        if (!tutorBurst) {
            return;
        }
        if (burstTimer) {
            window.clearTimeout(burstTimer);
        }
        tutorBurst.textContent = text;
        tutorBurst.hidden = false;
        tutorBurst.classList.remove("is-visible");
        void tutorBurst.offsetWidth;
        tutorBurst.classList.add("is-visible");
        burstTimer = window.setTimeout(() => {
            tutorBurst.hidden = true;
            tutorBurst.classList.remove("is-visible");
            burstTimer = null;
        }, 780);
    }

    function wait(duration) {
        return new Promise((resolve) => {
            window.setTimeout(resolve, duration);
        });
    }

    function resize() {
        const rect = canvas.getBoundingClientRect();
        const width = Math.max(320, rect.width);
        const height = Math.max(320, rect.height);
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        const narrow = width < 760 || width / height < 1.08;
        camera.fov = narrow ? 50 : 40;
        camera.position.set(0, narrow ? 7.45 : 6.4, narrow ? 10.4 : 8.3);
        camera.lookAt(0, 0, 0);
        camera.updateProjectionMatrix();
    }

    function render() {
        seedGroup.children.forEach((seed, index) => {
            seed.rotation.y += 0.0015 + (index % 3) * 0.0004;
        });
        const recommendedAction = findRecommendedAction();
        pitSpecs.forEach((pit) => {
            if (pit.action === recommendedAction) {
                const pulse = 1 + Math.sin(performance.now() * 0.007) * 0.08;
                pit.ring.scale.set(pulse, pulse, pulse);
            } else if (pit.ring.scale.x !== 1) {
                pit.ring.scale.set(1, 1, 1);
            }
        });
        renderer.render(scene, camera);
    }
}
