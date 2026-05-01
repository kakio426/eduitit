(function () {
    const WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.3.136/pdf.worker.min.js';

    function qs(id) {
        return document.getElementById(id);
    }

    function clone(value) {
        return JSON.parse(JSON.stringify(value || {}));
    }

    function debounce(fn, wait) {
        let timer = null;
        return function debounced() {
            const args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function () {
                fn.apply(null, args);
            }, wait);
        };
    }

    async function readJsonResponse(response) {
        const text = await response.text();
        if (!text) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch (error) {
            return {};
        }
    }

    class LiveSessionApp {
        constructor(config) {
            this.config = config;
            this.role = config.role;
            this.sessionId = config.sessionId;
            this.seq = 0;
            this.pageStates = {};
            this.pageHistory = {};
            this.currentPage = 1;
            this.totalPages = Number(config.pageCount || 0);
            this.zoomScale = 1;
            this.followMode = true;
            this.viewerRole = config.role;
            this.viewportState = {
                bookmarks: [],
                blackout: false,
                spotlight: { enabled: false, x: 0.5, y: 0.5 },
                teacher_note: '',
            };
            this.currentRenderToken = 0;
            this.remotePreviewObject = null;
            this.reconnectTimer = null;
            this.shapeState = null;
            this.activeTool = this.role === 'teacher' ? 'pen' : 'view';
            this.pointerThrottleAt = 0;
            this.shapePreviewThrottleAt = 0;
            this.deviceId = this.resolveDeviceId();
            this.suppressFabricEvents = false;
            this.sessionEnded = false;
            this.destroyed = false;
        }

        resolveDeviceId() {
            const key = 'textbooks-live-device-' + this.role + '-' + this.sessionId;
            let value = window.localStorage.getItem(key);
            if (!value) {
                value = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : ('device-' + Math.random().toString(16).slice(2));
                window.localStorage.setItem(key, value);
            }
            return value;
        }

        async init() {
            this.cacheDom();
            if (!window.pdfjsLib || !window.fabric) {
                this.toast('PDF.js 또는 Fabric.js 로드에 실패했습니다.', 'error');
                return;
            }
            window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_URL;

            try {
                const bootstrap = await this.fetchBootstrap();
                this.applyBootstrap(bootstrap);
                await this.loadPdf();
                this.bindUi();
                await this.renderPage(this.currentPage, { pushHistory: true });
                await this.renderThumbnails();
                this.applyViewportState();
                this.updateParticipants(bootstrap.participants || []);
                this.connectSocket();
            } catch (error) {
                console.error(error);
                this.toast(error && error.message ? error.message : '다시 시도', 'error');
            }
        }

        cacheDom() {
            this.viewerShell = qs('viewer-shell');
            this.viewerScroll = qs('viewer-scroll');
            this.stageEl = qs('page-stage') || this.viewerScroll || this.viewerShell;
            this.pdfCanvasEl = qs('pdf-canvas');
            this.overlayCanvasEl = qs('overlay-canvas');
            this.pageIndicatorEl = qs('page-indicator');
            this.thumbStripEl = qs('thumb-strip');
            this.participantCountEl = qs('participant-count');
            this.participantListEl = qs('participant-list');
            this.bookmarkListEl = qs('bookmark-list');
            this.teacherNoteEl = qs('teacher-note');
            this.followBadgeEl = qs('follow-badge');
            this.blackoutLayerEl = qs('blackout-layer');
            this.spotlightLayerEl = qs('spotlight-layer');
            this.laserPointerEl = qs('laser-pointer');
            this.toastStackEl = qs('toast-stack');
            this.prevPageBtn = qs('prev-page-btn');
            this.nextPageBtn = qs('next-page-btn');
            this.followModeInput = qs('follow-mode-input');
            this.blackoutBtn = qs('blackout-btn');
            this.spotlightBtn = qs('spotlight-btn');
            this.fullscreenBtn = qs('fullscreen-btn');
            this.colorInput = qs('color-input');
            this.widthInput = qs('width-input');
            this.undoBtn = qs('undo-btn');
            this.redoBtn = qs('redo-btn');
            this.clearPageBtn = qs('clear-page-btn');
            this.eraseObjectBtn = qs('erase-object-btn');
            this.bookmarkCurrentBtn = qs('bookmark-current-btn');
            this.endSessionBtn = qs('end-session-btn');
            this.toolButtons = Array.from(document.querySelectorAll('[data-tool]'));
        }

        async fetchBootstrap() {
            const response = await fetch(this.config.bootstrapUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
            });
            const payload = await readJsonResponse(response);
            if (!response.ok) {
                throw new Error(payload.error || '다시 시도');
            }
            if (!payload.session || !payload.material) {
                throw new Error('다시 시도');
            }
            return payload;
        }

        applyBootstrap(data) {
            this.seq = Number(data.session.last_seq || 0);
            this.currentPage = Number(data.session.current_page || 1);
            this.totalPages = Number(data.material.page_count || this.totalPages || 1);
            this.zoomScale = Number(data.session.zoom_scale || 1);
            this.followMode = Boolean(data.session.follow_mode);
            this.viewerRole = data.viewer_role || this.role;
            this.pageStates = data.page_states || {};
            this.viewportState = Object.assign({
                bookmarks: [],
                blackout: false,
                spotlight: { enabled: false, x: 0.5, y: 0.5 },
                teacher_note: '',
            }, data.session.viewport || {});
            if (this.teacherNoteEl) {
                this.teacherNoteEl.value = this.viewportState.teacher_note || '';
            }
            if (this.followModeInput) {
                this.followModeInput.checked = this.followMode;
            }
            this.updateFollowUi();
            this.renderBookmarkList();
        }

        async loadPdf() {
            const task = window.pdfjsLib.getDocument(this.config.pdfUrl);
            this.pdfDoc = await task.promise;
            this.totalPages = this.pdfDoc.numPages;
        }

        connectSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = protocol + '//' + window.location.host + this.config.wsUrl + '?role=' + encodeURIComponent(this.role) + '&device_id=' + encodeURIComponent(this.deviceId);
            this.socket = new WebSocket(url);

            this.socket.addEventListener('open', () => {
                this.toast('실시간 연결이 준비되었습니다.', 'success');
            });
            this.socket.addEventListener('message', (event) => {
                try {
                    this.handleSocketMessage(JSON.parse(event.data));
                } catch (error) {
                    console.error(error);
                    this.toast('실시간 지연', 'warn');
                }
            });
            this.socket.addEventListener('close', () => {
                if (this.sessionEnded || this.destroyed) {
                    return;
                }
                this.toast('실시간 지연', 'warn');
                window.clearTimeout(this.reconnectTimer);
                this.reconnectTimer = window.setTimeout(async () => {
                    try {
                        const bootstrap = await this.fetchBootstrap();
                        this.applyBootstrap(bootstrap);
                        await this.renderPage(this.currentPage, { pushHistory: false });
                    } catch (error) {
                        console.error(error);
                        this.toast('다시 시도', 'error');
                    }
                    this.connectSocket();
                }, 1500);
            });
        }

        bindUi() {
            if (this.prevPageBtn) {
                this.prevPageBtn.addEventListener('click', () => this.goToPage(this.currentPage - 1));
            }
            if (this.nextPageBtn) {
                this.nextPageBtn.addEventListener('click', () => this.goToPage(this.currentPage + 1));
            }
            if (this.role !== 'teacher') {
                return;
            }
            this.toolButtons.forEach((button) => {
                button.addEventListener('click', () => this.setTool(button.dataset.tool));
            });
            this.setTool('pen');
            this.configureBrush();
            if (this.colorInput) {
                this.colorInput.addEventListener('input', () => this.configureBrush());
            }
            if (this.widthInput) {
                this.widthInput.addEventListener('change', () => this.configureBrush());
            }
            if (this.undoBtn) {
                this.undoBtn.addEventListener('click', () => this.undo());
            }
            if (this.redoBtn) {
                this.redoBtn.addEventListener('click', () => this.redo());
            }
            if (this.clearPageBtn) {
                this.clearPageBtn.addEventListener('click', () => this.clearCurrentPage());
            }
            if (this.eraseObjectBtn) {
                this.eraseObjectBtn.addEventListener('click', () => this.eraseSelection());
            }
            if (this.followModeInput) {
                this.followModeInput.addEventListener('change', () => {
                    this.followMode = this.followModeInput.checked;
                    this.updateFollowUi();
                    this.sendEnvelope('session.follow', {
                        follow_mode: this.followMode,
                        current_page: this.currentPage,
                        zoom_scale: this.zoomScale,
                    });
                });
            }
            if (this.blackoutBtn) {
                this.blackoutBtn.addEventListener('click', () => {
                    this.viewportState.blackout = !this.viewportState.blackout;
                    this.pushViewportSnapshot();
                });
            }
            if (this.spotlightBtn) {
                this.spotlightBtn.addEventListener('click', () => {
                    const nextState = !(this.viewportState.spotlight && this.viewportState.spotlight.enabled);
                    this.viewportState.spotlight = Object.assign({ x: 0.5, y: 0.5 }, this.viewportState.spotlight || {}, { enabled: nextState });
                    this.pushViewportSnapshot();
                });
            }
            if (this.bookmarkCurrentBtn) {
                this.bookmarkCurrentBtn.addEventListener('click', () => this.toggleBookmark(this.currentPage));
            }
            if (this.fullscreenBtn) {
                this.fullscreenBtn.addEventListener('click', () => {
                    if (this.viewerShell && this.viewerShell.requestFullscreen) {
                        this.viewerShell.requestFullscreen();
                    }
                });
            }
            if (this.teacherNoteEl) {
                this.teacherNoteEl.addEventListener('input', debounce(() => {
                    this.viewportState.teacher_note = this.teacherNoteEl.value;
                    this.pushViewportSnapshot();
                }, 1000));
            }
            if (this.endSessionBtn) {
                this.endSessionBtn.addEventListener('click', async () => {
                    try {
                        const response = await fetch(this.config.endUrl, {
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': this.config.csrfToken,
                                'X-Requested-With': 'XMLHttpRequest',
                            },
                            credentials: 'same-origin',
                        });
                        if (response.ok) {
                            this.toast('수업을 종료했습니다.', 'success');
                        } else {
                            this.toast('다시 시도', 'error');
                        }
                    } catch (error) {
                        console.error(error);
                        this.toast('다시 시도', 'error');
                    }
                });
            }
            document.addEventListener('keydown', (event) => {
                if (event.key === 'Delete' || event.key === 'Backspace') {
                    this.eraseSelection();
                }
            });
            window.addEventListener('beforeunload', () => {
                this.destroyed = true;
                window.clearTimeout(this.reconnectTimer);
                if (this.socket && this.socket.readyState <= WebSocket.OPEN) {
                    this.socket.close();
                }
            });
        }
        updateFollowUi() {
            if (this.followBadgeEl) {
                this.followBadgeEl.textContent = this.followMode ? '선생님 화면 따라가는 중' : '개별 페이지 탐색 가능';
            }
            if (this.prevPageBtn && this.nextPageBtn && this.role === 'student') {
                const hidden = this.followMode;
                this.prevPageBtn.classList.toggle('hidden', hidden);
                this.nextPageBtn.classList.toggle('hidden', hidden);
            }
        }

        async renderPage(pageNumber, options) {
            const page = Math.max(1, Math.min(pageNumber, this.totalPages));
            this.currentPage = page;
            const renderToken = ++this.currentRenderToken;
            const pdfPage = await this.pdfDoc.getPage(page);
            const availableWidth = Math.max(360, this.viewerShell.clientWidth - 32);
            const baseViewport = pdfPage.getViewport({ scale: 1 });
            const fitScale = availableWidth / baseViewport.width;
            const viewport = pdfPage.getViewport({ scale: fitScale * (this.zoomScale || 1) });

            this.stageEl.style.width = viewport.width + 'px';
            this.stageEl.style.height = viewport.height + 'px';
            this.pdfCanvasEl.width = viewport.width;
            this.pdfCanvasEl.height = viewport.height;
            this.overlayCanvasEl.width = viewport.width;
            this.overlayCanvasEl.height = viewport.height;
            if (this.blackoutLayerEl) {
                this.blackoutLayerEl.style.width = viewport.width + 'px';
                this.blackoutLayerEl.style.height = viewport.height + 'px';
            }
            if (this.spotlightLayerEl) {
                this.spotlightLayerEl.style.width = viewport.width + 'px';
                this.spotlightLayerEl.style.height = viewport.height + 'px';
            }

            const context = this.pdfCanvasEl.getContext('2d', { alpha: false });
            await pdfPage.render({ canvasContext: context, viewport: viewport }).promise;
            if (renderToken !== this.currentRenderToken) {
                return;
            }

            this.setupFabric(viewport.width, viewport.height);
            await this.loadCanvasState(this.pageStates[String(page)] || {});
            this.ensureHistory(page, this.pageStates[String(page)] || {});
            if (options && options.pushHistory) {
                this.pushHistory(page, this.pageStates[String(page)] || {});
            }
            this.updatePageIndicator();
            this.applyViewportState();
        }

        setupFabric(width, height) {
            if (!this.fabricCanvas) {
                this.fabricCanvas = new window.fabric.Canvas('overlay-canvas', {
                    selection: this.role === 'teacher',
                    preserveObjectStacking: true,
                    stopContextMenu: true,
                });
                this.fabricCanvas.on('path:created', (event) => {
                    if (this.role !== 'teacher' || this.suppressFabricEvents) {
                        return;
                    }
                    event.path.selectable = true;
                    event.path.evented = true;
                    this.commitCanvasState('annotation.upsert');
                });
                this.fabricCanvas.on('mouse:down', (event) => this.handleFabricMouseDown(event));
                this.fabricCanvas.on('mouse:move', (event) => this.handleFabricMouseMove(event));
                this.fabricCanvas.on('mouse:up', () => this.handleFabricMouseUp());
            }
            this.fabricCanvas.setWidth(width);
            this.fabricCanvas.setHeight(height);
            this.fabricCanvas.selection = this.role === 'teacher' && this.activeTool === 'select';
            this.fabricCanvas.skipTargetFind = !(this.role === 'teacher' && this.activeTool === 'select');
            this.fabricCanvas.defaultCursor = this.role === 'teacher' ? 'crosshair' : 'default';
            this.configureBrush();
        }

        async loadCanvasState(state) {
            const safeState = state && state.objects ? state : { version: '5.3.0', width: this.fabricCanvas.getWidth(), height: this.fabricCanvas.getHeight(), objects: [] };
            this.suppressFabricEvents = true;
            this.fabricCanvas.clear();
            await new Promise((resolve) => {
                this.fabricCanvas.loadFromJSON(safeState, () => {
                    this.scaleObjects(safeState.width, safeState.height);
                    this.fabricCanvas.getObjects().forEach((obj) => {
                        obj.selectable = this.role === 'teacher' && this.activeTool === 'select';
                        obj.evented = this.role === 'teacher' && this.activeTool === 'select';
                    });
                    this.fabricCanvas.renderAll();
                    resolve();
                });
            });
            this.removeRemotePreview();
            this.suppressFabricEvents = false;
        }

        scaleObjects(baseWidth, baseHeight) {
            if (!baseWidth || !baseHeight) {
                return;
            }
            const ratioX = this.fabricCanvas.getWidth() / baseWidth;
            const ratioY = this.fabricCanvas.getHeight() / baseHeight;
            if (Math.abs(ratioX - 1) < 0.01 && Math.abs(ratioY - 1) < 0.01) {
                return;
            }
            this.fabricCanvas.getObjects().forEach((obj) => {
                obj.left *= ratioX;
                obj.top *= ratioY;
                obj.scaleX *= ratioX;
                obj.scaleY *= ratioY;
                obj.setCoords();
            });
        }

        handleFabricMouseDown(event) {
            if (this.role !== 'teacher') {
                return;
            }
            if (this.activeTool !== 'rect' && this.activeTool !== 'ellipse') {
                return;
            }
            const pointer = this.fabricCanvas.getPointer(event.e);
            this.shapeState = {
                startX: pointer.x,
                startY: pointer.y,
                object: this.activeTool === 'rect'
                    ? new window.fabric.Rect({
                        left: pointer.x,
                        top: pointer.y,
                        width: 1,
                        height: 1,
                        fill: 'rgba(0,0,0,0)',
                        stroke: this.colorInput.value,
                        strokeWidth: Number(this.widthInput.value || 4),
                        selectable: false,
                        evented: false,
                    })
                    : new window.fabric.Ellipse({
                        left: pointer.x,
                        top: pointer.y,
                        rx: 1,
                        ry: 1,
                        fill: 'rgba(0,0,0,0)',
                        stroke: this.colorInput.value,
                        strokeWidth: Number(this.widthInput.value || 4),
                        selectable: false,
                        evented: false,
                    }),
            };
            this.fabricCanvas.add(this.shapeState.object);
        }

        handleFabricMouseMove(event) {
            if (this.role !== 'teacher') {
                return;
            }
            const pointer = this.fabricCanvas.getPointer(event.e);
            this.handlePointerBroadcast(pointer);
            if (!this.shapeState) {
                return;
            }
            const object = this.shapeState.object;
            const width = Math.abs(pointer.x - this.shapeState.startX);
            const height = Math.abs(pointer.y - this.shapeState.startY);
            if (object.type === 'rect') {
                object.set({
                    left: Math.min(pointer.x, this.shapeState.startX),
                    top: Math.min(pointer.y, this.shapeState.startY),
                    width: Math.max(width, 1),
                    height: Math.max(height, 1),
                });
            } else {
                object.set({
                    left: Math.min(pointer.x, this.shapeState.startX),
                    top: Math.min(pointer.y, this.shapeState.startY),
                    rx: Math.max(width / 2, 1),
                    ry: Math.max(height / 2, 1),
                });
            }
            object.setCoords();
            this.fabricCanvas.renderAll();
            this.sendShapePreview();
        }

        handleFabricMouseUp() {
            if (this.role !== 'teacher' || !this.shapeState) {
                return;
            }
            this.shapeState.object.selectable = true;
            this.shapeState.object.evented = true;
            this.shapeState = null;
            this.commitCanvasState('annotation.upsert');
        }
        handlePointerBroadcast(pointer) {
            if (this.role !== 'teacher') {
                return;
            }
            const spotlightEnabled = this.viewportState.spotlight && this.viewportState.spotlight.enabled;
            if (this.activeTool !== 'laser' && !spotlightEnabled) {
                return;
            }
            const now = Date.now();
            if (now - this.pointerThrottleAt < 40) {
                return;
            }
            this.pointerThrottleAt = now;
            const payload = {
                page_index: this.currentPage,
                x: pointer.x / this.fabricCanvas.getWidth(),
                y: pointer.y / this.fabricCanvas.getHeight(),
                spotlight: Boolean(spotlightEnabled),
            };
            if (spotlightEnabled) {
                this.viewportState.spotlight.x = payload.x;
                this.viewportState.spotlight.y = payload.y;
                this.applyViewportState();
            }
            this.sendEnvelope('pointer.move', payload);
        }

        sendShapePreview() {
            if (!this.shapeState) {
                return;
            }
            const now = Date.now();
            if (now - this.shapePreviewThrottleAt < 40) {
                return;
            }
            this.shapePreviewThrottleAt = now;
            const object = this.shapeState.object;
            this.sendEnvelope('annotation.preview', {
                page_index: this.currentPage,
                shape: object.type,
                left: object.left / this.fabricCanvas.getWidth(),
                top: object.top / this.fabricCanvas.getHeight(),
                width: (object.width || object.rx * 2) / this.fabricCanvas.getWidth(),
                height: (object.height || object.ry * 2) / this.fabricCanvas.getHeight(),
                color: object.stroke,
                strokeWidth: object.strokeWidth,
            });
        }

        configureBrush() {
            if (!this.fabricCanvas || this.role !== 'teacher') {
                return;
            }
            this.fabricCanvas.isDrawingMode = this.activeTool === 'pen' || this.activeTool === 'highlighter';
            this.fabricCanvas.selection = this.activeTool === 'select';
            this.fabricCanvas.skipTargetFind = this.activeTool !== 'select';
            if (this.fabricCanvas.isDrawingMode) {
                const brush = this.fabricCanvas.freeDrawingBrush;
                const baseColor = this.colorInput ? this.colorInput.value : '#ef4444';
                brush.color = this.activeTool === 'highlighter' ? this.hexToRgba(baseColor, 0.28) : baseColor;
                brush.width = Number(this.widthInput ? this.widthInput.value : 4);
            }
            this.fabricCanvas.getObjects().forEach((obj) => {
                const selectable = this.activeTool === 'select';
                obj.selectable = selectable;
                obj.evented = selectable;
            });
            this.fabricCanvas.renderAll();
            this.toolButtons.forEach((button) => {
                button.classList.toggle('is-active', button.dataset.tool === this.activeTool);
            });
        }

        setTool(tool) {
            this.activeTool = tool;
            this.configureBrush();
        }

        serializeCanvas() {
            if (!this.fabricCanvas) {
                return {};
            }
            const json = this.fabricCanvas.toJSON();
            json.width = this.fabricCanvas.getWidth();
            json.height = this.fabricCanvas.getHeight();
            return json;
        }

        commitCanvasState(eventType) {
            const state = this.serializeCanvas();
            this.pageStates[String(this.currentPage)] = state;
            this.pushHistory(this.currentPage, state);
            this.sendEnvelope(eventType, { page_index: this.currentPage, fabric_json: state });
            this.removeRemotePreview();
        }

        ensureHistory(page, state) {
            const key = String(page);
            if (!this.pageHistory[key]) {
                this.pageHistory[key] = { stack: [clone(state && state.objects ? state : { width: this.fabricCanvas.getWidth(), height: this.fabricCanvas.getHeight(), objects: [] })], index: 0 };
            }
        }

        pushHistory(page, state) {
            const key = String(page);
            const payload = clone(state && state.objects ? state : { width: this.fabricCanvas.getWidth(), height: this.fabricCanvas.getHeight(), objects: [] });
            const serialized = JSON.stringify(payload);
            this.ensureHistory(page, payload);
            const bucket = this.pageHistory[key];
            const current = JSON.stringify(bucket.stack[bucket.index] || {});
            if (current === serialized) {
                return;
            }
            bucket.stack = bucket.stack.slice(0, bucket.index + 1);
            bucket.stack.push(payload);
            bucket.index = bucket.stack.length - 1;
        }

        async undo() {
            const bucket = this.pageHistory[String(this.currentPage)];
            if (!bucket || bucket.index < 1) {
                return;
            }
            bucket.index -= 1;
            const state = clone(bucket.stack[bucket.index]);
            this.pageStates[String(this.currentPage)] = state;
            await this.loadCanvasState(state);
            this.sendEnvelope('annotation.upsert', { page_index: this.currentPage, fabric_json: state });
        }

        async redo() {
            const bucket = this.pageHistory[String(this.currentPage)];
            if (!bucket || bucket.index >= bucket.stack.length - 1) {
                return;
            }
            bucket.index += 1;
            const state = clone(bucket.stack[bucket.index]);
            this.pageStates[String(this.currentPage)] = state;
            await this.loadCanvasState(state);
            this.sendEnvelope('annotation.upsert', { page_index: this.currentPage, fabric_json: state });
        }

        async clearCurrentPage() {
            if (!this.fabricCanvas) {
                return;
            }
            this.fabricCanvas.clear();
            const state = this.serializeCanvas();
            this.pageStates[String(this.currentPage)] = state;
            this.pushHistory(this.currentPage, state);
            this.sendEnvelope('annotation.delete', { page_index: this.currentPage, fabric_json: state });
        }

        eraseSelection() {
            if (!this.fabricCanvas || this.role !== 'teacher') {
                return;
            }
            const active = this.fabricCanvas.getActiveObject();
            if (!active) {
                return;
            }
            this.fabricCanvas.remove(active);
            this.fabricCanvas.discardActiveObject();
            this.fabricCanvas.renderAll();
            this.commitCanvasState('annotation.delete');
        }

        sendEnvelope(type, payload) {
            this.seq += 1;
            const envelope = {
                type: type,
                seq: this.seq,
                actor: this.role,
                payload: payload || {},
                sent_at: new Date().toISOString(),
            };
            if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
                return;
            }
            this.socket.send(JSON.stringify(envelope));
        }
        async handleSocketMessage(message) {
            if (!message || !message.type) {
                return;
            }
            switch (message.type) {
                case 'presence.join':
                case 'presence.leave':
                    this.updateParticipants((message.payload || {}).participants || []);
                    break;
                case 'session.navigate':
                    this.currentPage = Number((message.payload || {}).current_page || this.currentPage);
                    this.zoomScale = Number((message.payload || {}).zoom_scale || this.zoomScale || 1);
                    if (this.role !== 'teacher' && this.followMode) {
                        await this.renderPage(this.currentPage, { pushHistory: false });
                    }
                    this.updatePageIndicator();
                    break;
                case 'session.follow': {
                    const payload = message.payload || {};
                    this.followMode = Boolean(payload.follow_mode);
                    if (payload.current_page) {
                        this.currentPage = Number(payload.current_page || this.currentPage);
                    }
                    if (payload.zoom_scale) {
                        this.zoomScale = Number(payload.zoom_scale || this.zoomScale || 1);
                    }
                    this.updateFollowUi();
                    if (this.followMode && this.role === 'student') {
                        await this.renderPage(this.currentPage, { pushHistory: false });
                    }
                    break;
                }
                case 'session.snapshot':
                    this.currentPage = Number((message.payload || {}).current_page || this.currentPage);
                    this.zoomScale = Number((message.payload || {}).zoom_scale || this.zoomScale || 1);
                    this.viewportState = Object.assign({}, this.viewportState, (message.payload || {}).viewport || {});
                    this.applyViewportState();
                    this.renderBookmarkList();
                    if (this.role !== 'teacher' && this.followMode) {
                        await this.renderPage(this.currentPage, { pushHistory: false });
                    }
                    break;
                case 'annotation.preview':
                    this.renderRemotePreview(message.payload || {});
                    break;
                case 'annotation.upsert':
                case 'annotation.delete': {
                    const payload = message.payload || {};
                    const pageIndex = String(payload.page_index || this.currentPage);
                    this.pageStates[pageIndex] = payload.fabric_json || {};
                    this.removeRemotePreview();
                    if (Number(pageIndex) === this.currentPage) {
                        await this.loadCanvasState(this.pageStates[pageIndex]);
                    }
                    break;
                }
                case 'pointer.move':
                    this.applyRemotePointer(message.payload || {});
                    break;
                case 'session.end':
                    this.sessionEnded = true;
                    window.clearTimeout(this.reconnectTimer);
                    this.toast('수업이 종료되었습니다.', 'warn');
                    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                        this.socket.close();
                    }
                    break;
                case 'error':
                    this.toast((message.payload || {}).message || '오류가 발생했습니다.', 'error');
                    break;
                default:
                    break;
            }
        }

        async goToPage(page) {
            const nextPage = Math.max(1, Math.min(page, this.totalPages));
            await this.renderPage(nextPage, { pushHistory: false });
            await this.renderThumbnails();
            if (this.role === 'teacher') {
                this.sendEnvelope('session.navigate', {
                    current_page: nextPage,
                    zoom_scale: this.zoomScale,
                });
            }
        }

        async renderThumbnails() {
            if (!this.thumbStripEl || !this.pdfDoc) {
                return;
            }
            const start = Math.max(1, this.currentPage - 2);
            const end = Math.min(this.totalPages, this.currentPage + 2);
            this.thumbStripEl.innerHTML = '';
            for (let pageNumber = start; pageNumber <= end; pageNumber += 1) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'w-full rounded-[22px] border p-3 text-left transition ' + (pageNumber === this.currentPage ? 'border-sky-400 bg-sky-400/10' : 'border-white/10 bg-white/5');
                const canvas = document.createElement('canvas');
                canvas.className = 'w-full rounded-2xl bg-black';
                const label = document.createElement('div');
                label.className = 'mt-2 text-sm font-bold';
                label.textContent = pageNumber + '쪽';
                button.appendChild(canvas);
                button.appendChild(label);
                button.addEventListener('click', () => this.goToPage(pageNumber));
                this.thumbStripEl.appendChild(button);
                const pdfPage = await this.pdfDoc.getPage(pageNumber);
                const viewport = pdfPage.getViewport({ scale: 0.22 });
                canvas.width = viewport.width;
                canvas.height = viewport.height;
                await pdfPage.render({ canvasContext: canvas.getContext('2d'), viewport: viewport }).promise;
            }
        }

        updateParticipants(participants) {
            if (this.participantCountEl) {
                this.participantCountEl.textContent = '참여 ' + participants.filter((item) => item.role === 'student' && item.is_connected).length + '명';
            }
            if (this.participantListEl) {
                this.participantListEl.innerHTML = '';
                if (!participants.length) {
                    this.participantListEl.innerHTML = '<div class="text-slate-400">아직 연결된 학생이 없습니다.</div>';
                    return;
                }
                participants.forEach((participant) => {
                    const row = document.createElement('div');
                    row.className = 'flex items-center justify-between rounded-2xl bg-white/5 px-3 py-2';
                    row.innerHTML = '<span>' + this.escapeHtml(participant.display_name || participant.role) + '</span><span class="text-xs ' + (participant.is_connected ? 'text-emerald-300' : 'text-slate-400') + '">' + (participant.is_connected ? '접속중' : '대기') + '</span>';
                    this.participantListEl.appendChild(row);
                });
            }
        }

        toggleBookmark(page) {
            const current = new Set(this.viewportState.bookmarks || []);
            if (current.has(page)) {
                current.delete(page);
            } else {
                current.add(page);
            }
            this.viewportState.bookmarks = Array.from(current).sort(function (a, b) { return a - b; });
            this.renderBookmarkList();
            this.pushViewportSnapshot();
        }

        renderBookmarkList() {
            if (!this.bookmarkListEl) {
                return;
            }
            const bookmarks = this.viewportState.bookmarks || [];
            this.bookmarkListEl.innerHTML = '';
            if (!bookmarks.length) {
                this.bookmarkListEl.innerHTML = '<div class="text-slate-400">북마크한 페이지가 없습니다.</div>';
                return;
            }
            bookmarks.forEach((page) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'w-full rounded-2xl bg-white/5 px-3 py-2 text-left font-bold hover:bg-white/10';
                button.textContent = page + '쪽';
                button.addEventListener('click', () => this.goToPage(page));
                this.bookmarkListEl.appendChild(button);
            });
        }

        pushViewportSnapshot() {
            this.applyViewportState();
            this.renderBookmarkList();
            this.sendEnvelope('session.snapshot', {
                current_page: this.currentPage,
                zoom_scale: this.zoomScale,
                viewport: this.viewportState,
            });
        }

        applyViewportState() {
            const spotlight = Object.assign({ enabled: false, x: 0.5, y: 0.5 }, this.viewportState.spotlight || {});
            if (this.blackoutLayerEl) {
                this.blackoutLayerEl.classList.toggle('hidden', !!spotlight.enabled || !this.viewportState.blackout);
            }
            if (this.spotlightLayerEl) {
                this.spotlightLayerEl.classList.toggle('hidden', !spotlight.enabled);
                if (spotlight.enabled) {
                    const x = Math.round(spotlight.x * this.stageEl.clientWidth);
                    const y = Math.round(spotlight.y * this.stageEl.clientHeight);
                    this.spotlightLayerEl.style.background = 'radial-gradient(circle 120px at ' + x + 'px ' + y + 'px, transparent 0 95px, rgba(0, 0, 0, 0.88) 130px)';
                }
            }
            if (this.followModeInput && this.role === 'teacher') {
                this.followModeInput.checked = this.followMode;
            }
            this.updateFollowUi();
        }

        applyRemotePointer(payload) {
            if (!this.laserPointerEl || Number(payload.page_index || this.currentPage) !== this.currentPage) {
                return;
            }
            const x = (payload.x || 0.5) * this.stageEl.clientWidth;
            const y = (payload.y || 0.5) * this.stageEl.clientHeight;
            this.laserPointerEl.style.left = x + 'px';
            this.laserPointerEl.style.top = y + 'px';
            this.laserPointerEl.classList.remove('hidden');
            window.clearTimeout(this.laserTimeout);
            this.laserTimeout = window.setTimeout(() => {
                this.laserPointerEl.classList.add('hidden');
            }, 220);

            if (payload.spotlight) {
                this.viewportState.spotlight = Object.assign({}, this.viewportState.spotlight || {}, { enabled: true, x: payload.x, y: payload.y });
                this.applyViewportState();
            }
        }
        renderRemotePreview(payload) {
            if (!payload || Number(payload.page_index || this.currentPage) !== this.currentPage || !this.fabricCanvas) {
                return;
            }
            this.removeRemotePreview();
            const common = {
                left: payload.left * this.fabricCanvas.getWidth(),
                top: payload.top * this.fabricCanvas.getHeight(),
                stroke: payload.color || '#38bdf8',
                strokeWidth: Number(payload.strokeWidth || 3),
                fill: 'rgba(0,0,0,0)',
                selectable: false,
                evented: false,
                strokeDashArray: [10, 6],
            };
            if (payload.shape === 'ellipse') {
                this.remotePreviewObject = new window.fabric.Ellipse(Object.assign(common, {
                    rx: Math.max((payload.width * this.fabricCanvas.getWidth()) / 2, 1),
                    ry: Math.max((payload.height * this.fabricCanvas.getHeight()) / 2, 1),
                }));
            } else {
                this.remotePreviewObject = new window.fabric.Rect(Object.assign(common, {
                    width: Math.max(payload.width * this.fabricCanvas.getWidth(), 1),
                    height: Math.max(payload.height * this.fabricCanvas.getHeight(), 1),
                }));
            }
            this.fabricCanvas.add(this.remotePreviewObject);
            this.fabricCanvas.renderAll();
        }

        removeRemotePreview() {
            if (this.remotePreviewObject && this.fabricCanvas) {
                this.fabricCanvas.remove(this.remotePreviewObject);
                this.remotePreviewObject = null;
                this.fabricCanvas.renderAll();
            }
        }

        updatePageIndicator() {
            if (this.pageIndicatorEl) {
                this.pageIndicatorEl.textContent = this.currentPage + ' / ' + this.totalPages;
            }
        }

        hexToRgba(hex, alpha) {
            const value = hex.replace('#', '');
            const bigint = parseInt(value, 16);
            const r = (bigint >> 16) & 255;
            const g = (bigint >> 8) & 255;
            const b = bigint & 255;
            return 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alpha + ')';
        }
        toast(message, tone) {
            if (!this.toastStackEl) {
                return;
            }
            const color = tone === 'error' ? 'bg-rose-500' : tone === 'warn' ? 'bg-amber-500 text-slate-950' : 'bg-emerald-500 text-slate-950';
            const el = document.createElement('div');
            el.className = 'live-toast rounded-2xl px-4 py-3 text-sm font-black text-white shadow-xl ' + color;
            el.textContent = message;
            this.toastStackEl.appendChild(el);
            window.setTimeout(() => el.remove(), 2600);
        }

        escapeHtml(value) {
            return String(value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }
    }

    window.TextbookLiveSessionApp = {
        init: function init(config) {
            const app = new LiveSessionApp(config);
            app.init();
            return app;
        },
    };
})();
