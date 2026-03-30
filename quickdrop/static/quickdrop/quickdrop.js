(function () {
    function byId(id) {
        return document.getElementById(id);
    }

    function csrfToken(form) {
        const input = form ? form.querySelector('input[name="csrfmiddlewaretoken"]') : null;
        return input ? input.value : '';
    }

    function formatTime(isoString) {
        if (!isoString) {
            return '';
        }
        const value = new Date(isoString);
        if (Number.isNaN(value.getTime())) {
            return '';
        }
        return new Intl.DateTimeFormat('ko-KR', {
            month: 'long',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
        }).format(value);
    }

    function normalizeTextContent(value) {
        return String(value || '').trim();
    }

    function fileExtensionLabel(filename) {
        const name = String(filename || '').trim();
        const parts = name.split('.');
        if (parts.length > 1) {
            const extension = String(parts[parts.length - 1] || '').trim();
            if (extension) {
                return extension.slice(0, 6).toUpperCase();
            }
        }
        return 'FILE';
    }

    function createTrashIcon() {
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('viewBox', '0 0 24 24');
        icon.setAttribute('fill', 'none');
        icon.setAttribute('stroke', 'currentColor');
        icon.setAttribute('stroke-width', '1.9');
        icon.setAttribute('stroke-linecap', 'round');
        icon.setAttribute('stroke-linejoin', 'round');
        icon.classList.add('h-4', 'w-4');

        [
            'M3 6h18',
            'M8 6V4h8v2',
            'M19 6l-1 13a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6',
            'M10 11v6',
            'M14 11v6',
        ].forEach((pathValue) => {
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', pathValue);
            icon.appendChild(path);
        });

        return icon;
    }

    function inferClipboardFilename(file) {
        const mimeType = String(file && file.type ? file.type : '');
        const rawExtension = mimeType.indexOf('/') >= 0 ? mimeType.split('/')[1] : 'bin';
        const extension = rawExtension.replace(/[^a-zA-Z0-9]/g, '') || 'bin';
        return 'clipboard-' + Date.now() + '.' + extension;
    }

    function createApp(root, bootstrap) {
        return {
            root: root,
            session: bootstrap.session || {},
            ws: null,
            pingTimer: null,
            pollTimer: null,
            reconnectTimer: null,
            isPosting: false,
            isPulling: false,
            wsConnected: false,
            snapshotPollDelay: 15000,
            queuedFile: null,
            didHandleHistoryFocus: false,

            init() {
                this.cacheDom();
                this.render();
                this.bindForms();
                this.bindActions();
                this.registerServiceWorker();
                this.connectSocket();
            },

            cacheDom() {
                this.connectionBadge = byId('connection-badge');
                this.sessionStatus = byId('session-status');
                this.sessionExpiry = byId('session-expiry');
                this.helperChipPaste = byId('helper-chip-paste');
                this.helperChipRepeat = byId('helper-chip-repeat');
                this.emptyState = byId('empty-state');
                this.emptyBadge = byId('empty-badge');
                this.emptyTitle = byId('empty-title');
                this.emptyBody = byId('empty-body');
                this.emptyPillRow = byId('empty-pill-row');
                this.imagePanel = byId('image-panel');
                this.imageOutput = byId('image-output');
                this.imagePreviewShell = byId('image-preview-shell');
                this.filePreviewShell = byId('file-preview-shell');
                this.fileOutputName = byId('file-output-name');
                this.fileOutputBadge = byId('file-output-badge');
                this.imageFilename = byId('image-filename');
                this.copyCurrentBtn = byId('copy-current-btn');
                this.downloadCurrentBtn = byId('download-current-btn');
                this.historyPanel = byId('history-panel');
                this.historySummary = byId('history-summary');
                this.historyEmpty = byId('history-empty');
                this.historyList = byId('history-list');
                this.textForm = byId('text-form');
                this.textInput = byId('text-input');
                this.sendTextBtn = byId('send-text-btn');
                this.fileInput = byId('file-input');
                this.selectedFileRow = byId('selected-file-row');
                this.selectedFileName = byId('selected-file-name');
                this.clearFileBtn = byId('clear-file-btn');
                this.photoTrigger = byId('photo-trigger');
                this.composerTipDesktop = byId('composer-tip-desktop');
                this.composerTipMobile = byId('composer-tip-mobile');
                this.endSessionBtn = byId('end-session-btn');
                this.toastRoot = byId('toast-root');
            },

            isCompactMobile() {
                return window.matchMedia('(max-width: 639px)').matches;
            },

            wantsHistoryFocus() {
                const params = new URLSearchParams(window.location.search);
                return params.get('focus') === 'history' || window.location.hash === '#history-panel';
            },

            sessionFingerprint(payload) {
                return JSON.stringify(payload || {});
            },

            bindForms() {
                if (this.textForm) {
                    this.textForm.addEventListener('submit', (event) => {
                        if (this.hasNativeSelectedFile()) {
                            this.prepareNativeFileSubmit();
                            return;
                        }
                        event.preventDefault();
                        this.restoreTextSubmitMode();
                        const queuedFile = this.getQueuedFile();
                        if (queuedFile) {
                            this.sendFile(queuedFile);
                            return;
                        }
                        this.sendText(this.textInput.value);
                    });
                }
                if (this.textInput) {
                    this.textInput.addEventListener('input', () => {
                        this.resizeComposer();
                        this.syncComposerState();
                    });
                    this.textInput.addEventListener('paste', (event) => {
                        this.capturePastedFile(event);
                    });
                    this.textInput.addEventListener('keydown', (event) => {
                        if (event.key !== 'Enter' || event.shiftKey || event.isComposing) {
                            return;
                        }
                        const queuedFile = this.getQueuedFile();
                        const hasFile = Boolean(queuedFile);
                        const value = (this.textInput.value || '').trim();
                        if (!value && !hasFile) {
                            return;
                        }
                        event.preventDefault();
                        if (this.hasNativeSelectedFile()) {
                            this.prepareNativeFileSubmit();
                            this.textForm.submit();
                            return;
                        }
                        if (queuedFile) {
                            this.sendFile(queuedFile);
                            return;
                        }
                        this.sendText(this.textInput.value);
                    });
                }
                if (this.fileInput) {
                    this.fileInput.addEventListener('change', () => {
                        this.restoreTextSubmitMode();
                        this.setQueuedFile(this.fileInput.files[0] || null);
                    });
                }
            },

            bindActions() {
                if (this.copyCurrentBtn) {
                    this.copyCurrentBtn.addEventListener('click', async () => {
                        if ((this.session.current_kind || '') !== 'image' || !this.session.current_download_url) {
                            return;
                        }
                        if (!navigator.clipboard || typeof window.ClipboardItem === 'undefined') {
                            this.toast('이 브라우저에서는 이미지 복사를 지원하지 않습니다.', 'error');
                            return;
                        }
                        try {
                            const asset = await this.fetchCurrentAsset();
                            await navigator.clipboard.write([
                                new window.ClipboardItem({
                                    [asset.blob.type || 'image/png']: asset.blob,
                                }),
                            ]);
                            this.toast('이미지를 복사했습니다.', 'success');
                        } catch (_error) {
                            this.toast('이미지를 복사할 수 없습니다.', 'error');
                        }
                    });
                }

                if (this.downloadCurrentBtn) {
                    this.downloadCurrentBtn.addEventListener('click', async () => {
                        if (!this.session.current_download_url) {
                            return;
                        }
                        if ((this.session.current_kind || '') === 'file') {
                            this.startNativeDownload(this.session.current_download_url, this.session.current_filename || 'shared-file');
                            return;
                        }
                        try {
                            const asset = await this.fetchCurrentAsset();
                            this.downloadBlobAsset(asset);
                        } catch (_error) {
                            const message = (this.session.current_kind || '') === 'image'
                                ? '이미지를 저장할 수 없습니다.'
                                : '파일을 받을 수 없습니다.';
                            this.toast(message, 'error');
                        }
                    });
                }

                if (this.endSessionBtn) {
                    this.endSessionBtn.addEventListener('click', () => {
                        this.post(this.root.dataset.endSessionUrl, new FormData(), null, '오늘 내용을 비웠습니다.');
                    });
                }

                if (this.clearFileBtn) {
                    this.clearFileBtn.addEventListener('click', () => {
                        this.clearSelectedFile();
                    });
                }
            },

            async sendText(text) {
                const payload = new FormData();
                payload.append('text', text);
                await this.post(this.root.dataset.sendTextUrl, payload, () => {
                    this.restoreTextSubmitMode();
                    this.textInput.value = '';
                    this.resizeComposer();
                    this.syncComposerState();
                    if (window.matchMedia('(pointer: fine)').matches) {
                        this.textInput.focus();
                    } else {
                        this.textInput.blur();
                    }
                }, '텍스트를 보냈습니다.');
            },

            async sendFile(file) {
                if (!file) {
                    return;
                }
                const payload = new FormData();
                payload.append('file', file, file.name || 'shared-file');
                await this.post(this.root.dataset.sendFileUrl, payload, () => {
                    this.clearSelectedFile({ keepFocus: true, silent: true });
                }, '파일을 보냈습니다.');
            },

            async post(url, body, onSuccess, successMessage) {
                this.isPosting = true;
                try {
                    const response = await fetch(url, {
                        method: 'POST',
                        body: body,
                        credentials: 'same-origin',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': csrfToken(this.textForm),
                        },
                    });
                    const data = await response.json();
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || 'request failed');
                    }
                    if (data.session && Object.keys(data.session).length) {
                        this.session = data.session;
                    }
                    this.render();
                    if (onSuccess) {
                        onSuccess();
                    }
                    if (successMessage) {
                        this.toast(successMessage, 'success');
                    }
                } catch (error) {
                    this.toast(error.message || '전송에 실패했습니다.', 'error');
                } finally {
                    this.isPosting = false;
                }
            },

            async fetchCurrentAsset() {
                const response = await fetch(this.session.current_download_url, { credentials: 'same-origin' });
                if (!response.ok) {
                    throw new Error('download failed');
                }
                return {
                    blob: await response.blob(),
                    filename: this.session.current_filename || 'shared-file',
                };
            },

            async downloadBlobAsset(asset) {
                const file = new File([asset.blob], asset.filename, {
                    type: asset.blob.type || 'application/octet-stream',
                });

                if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
                    await navigator.share({ files: [file], title: asset.filename });
                    return;
                }

                const link = document.createElement('a');
                link.href = URL.createObjectURL(asset.blob);
                link.download = asset.filename;
                link.click();
                window.setTimeout(function () {
                    URL.revokeObjectURL(link.href);
                }, 300);
            },

            startNativeDownload(url, filename) {
                const link = document.createElement('a');
                link.href = url;
                link.download = filename || 'shared-file';
                document.body.appendChild(link);
                link.click();
                link.remove();
            },

            startSnapshotPolling(immediate) {
                if (!this.root.dataset.snapshotUrl) {
                    return;
                }
                if (this.pollTimer) {
                    return;
                }
                if (immediate) {
                    this.pullSnapshot();
                }
                this.pollTimer = window.setInterval(() => {
                    if (document.visibilityState === 'hidden' || this.isPosting || this.isPulling || this.wsConnected) {
                        return;
                    }
                    this.pullSnapshot();
                }, this.snapshotPollDelay);
            },

            stopSnapshotPolling() {
                window.clearInterval(this.pollTimer);
                this.pollTimer = null;
            },

            async pullSnapshot() {
                if (!this.root.dataset.snapshotUrl || this.isPulling) {
                    return;
                }
                this.isPulling = true;
                try {
                    const response = await fetch(this.root.dataset.snapshotUrl, {
                        credentials: 'same-origin',
                        cache: 'no-store',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    if (!response.ok) {
                        throw new Error('snapshot failed');
                    }
                    const data = await response.json();
                    if (!data.ok || !data.session) {
                        throw new Error('snapshot payload missing');
                    }
                    if (this.sessionFingerprint(data.session) !== this.sessionFingerprint(this.session)) {
                        this.session = data.session;
                        this.render();
                    }
                } catch (_error) {
                    return;
                } finally {
                    this.isPulling = false;
                }
            },

            render() {
                const kind = this.session.current_kind || 'empty';
                const isText = kind === 'text';
                const isImage = kind === 'image';
                const isFile = kind === 'file';
                const todayItems = Array.isArray(this.session.today_items) ? this.session.today_items : [];
                const isCompactMobile = this.isCompactMobile();

                if (this.emptyState) {
                    this.emptyState.classList.toggle('hidden', isText || isImage || isFile);
                }
                if (this.imagePanel) {
                    this.imagePanel.classList.toggle('hidden', !(isImage || isFile));
                }

                if (this.sessionStatus) {
                    if (todayItems.length) {
                        this.sessionStatus.textContent = '오늘 ' + String(todayItems.length) + '개';
                    } else if (this.session.status === 'ended') {
                        this.sessionStatus.textContent = '지금은 비어 있음';
                    } else {
                        this.sessionStatus.textContent = '전송 준비';
                    }
                }
                if (this.sessionExpiry) {
                    this.sessionExpiry.textContent = isCompactMobile ? '오늘 기록 유지' : '오늘 기록은 내일 정리됩니다';
                }
                if (this.helperChipPaste) {
                    this.helperChipPaste.textContent = 'PC끼리 · 휴대폰끼리 · PC와 휴대폰 모두 가능';
                }
                if (this.helperChipRepeat) {
                    this.helperChipRepeat.textContent = '이 기기는 기억되어 다시 로그인하지 않아도 열 수 있습니다';
                }

                if (this.emptyBadge && this.emptyTitle && this.emptyBody) {
                    if (this.session.status === 'ended') {
                        this.emptyBadge.textContent = '오늘 내용 비움';
                        this.emptyTitle.textContent = '오늘 기록을 비웠습니다.';
                        this.emptyBody.textContent = '새로 보내면 다시 여기에 쌓입니다.';
                    } else {
                        this.emptyBadge.textContent = '전송 준비';
                        this.emptyTitle.textContent = '아직 받은 내용이 없습니다.';
                        this.emptyBody.textContent = '보낸 내용이 여기에 쌓입니다.';
                    }
                }

                if (this.imageOutput) {
                    this.imageOutput.src = this.session.current_preview_url || '';
                }
                if (this.imagePreviewShell) {
                    this.imagePreviewShell.classList.toggle('hidden', !isImage);
                }
                if (this.filePreviewShell) {
                    this.filePreviewShell.classList.toggle('hidden', !isFile);
                }
                if (this.fileOutputName) {
                    this.fileOutputName.textContent = this.session.current_filename || '선택한 파일';
                }
                if (this.fileOutputBadge) {
                    this.fileOutputBadge.textContent = fileExtensionLabel(this.session.current_filename);
                }
                if (this.imageFilename) {
                    const imageMeta = [];
                    if (this.session.current_filename) {
                        imageMeta.push(this.session.current_filename);
                    }
                    if (this.session.updated_at) {
                        imageMeta.push(formatTime(this.session.updated_at));
                    }
                    this.imageFilename.textContent = imageMeta.join(' · ') || '파일';
                }
                if (this.downloadCurrentBtn) {
                    this.downloadCurrentBtn.textContent = isImage ? '저장' : '파일 받기';
                }
                if (this.copyCurrentBtn) {
                    this.copyCurrentBtn.classList.toggle('hidden', !isImage);
                }
                if (this.historySummary) {
                    this.historySummary.textContent = '오늘 ' + String(todayItems.length) + '개';
                }
                if (this.historyPanel) {
                    this.historyPanel.classList.toggle('hidden', isCompactMobile && todayItems.length === 0 && !this.wantsHistoryFocus());
                }
                if (this.endSessionBtn) {
                    this.endSessionBtn.classList.toggle('hidden', todayItems.length === 0);
                }
                this.renderHistory(todayItems);
                this.maybeFocusHistory();
                this.resizeComposer();
                this.syncComposerState();
            },

            maybeFocusHistory() {
                if (this.didHandleHistoryFocus || !this.historyPanel || !this.wantsHistoryFocus()) {
                    return;
                }
                if (this.historyPanel.classList.contains('hidden')) {
                    return;
                }
                this.didHandleHistoryFocus = true;
                window.requestAnimationFrame(() => {
                    this.historyPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    if (typeof this.historyPanel.focus === 'function') {
                        this.historyPanel.focus();
                    }
                });
            },

            renderHistory(items) {
                if (!this.historyList || !this.historyEmpty) {
                    return;
                }

                this.historyList.innerHTML = '';
                this.historyEmpty.classList.toggle('hidden', items.length > 0);
                if (!items.length) {
                    return;
                }

                const visibleItems = this.isCompactMobile() ? items.slice(-6) : items;
                const orderedItems = visibleItems.slice().reverse();
                const fragment = document.createDocumentFragment();
                orderedItems.forEach((item, index) => {
                    fragment.appendChild(this.buildHistoryItem(item, index === 0));
                });
                this.historyList.appendChild(fragment);
            },

            buildHistoryItem(item, isLatest) {
                const isCompactMobile = this.isCompactMobile();
                const card = document.createElement('article');
                card.className = isCompactMobile
                    ? 'rounded-[18px] border border-[#dbe4ee] bg-white px-4 py-3'
                    : 'rounded-[20px] border px-4 py-3 ' + (
                        isLatest
                            ? 'border-[#bfdbfe] bg-[#eff6ff]'
                            : 'border-[#dbe4ee] bg-white'
                    );

                const header = document.createElement('div');
                header.className = 'flex items-center justify-between gap-3';

                const left = document.createElement('div');
                left.className = 'min-w-0';

                const meta = document.createElement('div');
                meta.className = 'min-w-0';

                const label = document.createElement('p');
                label.className = 'truncate text-sm font-black text-[#14213d]';
                label.textContent = item.sender_label || '연결된 기기';

                const time = document.createElement('p');
                time.className = 'text-xs text-slate-400';
                time.textContent = formatTime(item.created_at);

                meta.appendChild(label);
                meta.appendChild(time);
                left.appendChild(meta);

                header.appendChild(left);

                if (item.delete_url) {
                    const deleteButton = document.createElement('button');
                    deleteButton.type = 'button';
                    deleteButton.className = 'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#dbe4ee] bg-white text-slate-400 transition hover:border-[#cbd5e1] hover:text-[#d64564]';
                    deleteButton.setAttribute('aria-label', '이 기록 지우기');
                    deleteButton.appendChild(createTrashIcon());
                    deleteButton.addEventListener('click', () => {
                        this.deleteItem(item.delete_url);
                    });
                    header.appendChild(deleteButton);
                }

                const body = document.createElement('div');
                if (item.kind === 'image' || item.kind === 'file') {
                    body.className = 'mt-3 rounded-[16px] border border-[#dbe4ee] bg-[#f8fafc] px-4 py-3';
                    const badge = document.createElement('span');
                    badge.className = 'inline-flex items-center rounded-full px-3 py-1 text-[11px] font-black tracking-[0.08em] ' + (
                        item.kind === 'image'
                            ? 'bg-[#dbeafe] text-[#2563eb]'
                            : 'bg-[#e2e8f0] text-[#334155]'
                    );
                    badge.textContent = item.kind === 'image' ? '사진' : fileExtensionLabel(item.filename);

                    const fileName = document.createElement('p');
                    fileName.className = 'mt-3 break-all text-sm font-bold leading-6 text-[#0f172a]';
                    fileName.textContent = item.filename || (item.kind === 'image' ? '사진을 보냈습니다.' : '파일을 보냈습니다.');

                    body.appendChild(badge);
                    body.appendChild(fileName);
                } else {
                    body.className = isCompactMobile
                        ? 'mt-2 text-sm leading-6 text-slate-600'
                        : 'mt-3 rounded-[16px] bg-[#f8fafc] px-4 py-3 text-sm leading-6 text-slate-600';
                    body.textContent = normalizeTextContent(item.text);
                }

                card.appendChild(header);
                card.appendChild(body);
                return card;
            },

            connectSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const socket = new WebSocket(protocol + '//' + window.location.host + this.root.dataset.wsUrl);
                this.ws = socket;
                socket.addEventListener('open', () => {
                    this.wsConnected = true;
                    this.stopSnapshotPolling();
                    if (this.connectionBadge) {
                        this.connectionBadge.textContent = '실시간 연결';
                    }
                    this.startPing();
                    this.pullSnapshot();
                });
                socket.addEventListener('message', (event) => {
                    try {
                        this.handleMessage(JSON.parse(event.data));
                    } catch (_error) {
                        this.toast('실시간 업데이트를 읽지 못했습니다.', 'error');
                    }
                });
                socket.addEventListener('close', () => {
                    if (this.ws !== socket) {
                        return;
                    }
                    this.wsConnected = false;
                    if (this.connectionBadge) {
                        this.connectionBadge.textContent = '자동 갱신 중';
                    }
                    window.clearInterval(this.pingTimer);
                    this.startSnapshotPolling(true);
                    window.clearTimeout(this.reconnectTimer);
                    this.reconnectTimer = window.setTimeout(() => this.connectSocket(), 4000);
                });
            },

            startPing() {
                window.clearInterval(this.pingTimer);
                this.pingTimer = window.setInterval(() => {
                    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send(JSON.stringify({ type: 'ping' }));
                    }
                }, 45000);
            },

            handleMessage(message) {
                if (!message || !message.type) {
                    return;
                }
                if (message.type === 'session.snapshot' || message.type === 'item.replace' || message.type === 'session.ended') {
                    this.session = message.payload || {};
                    this.render();
                }
            },

            registerServiceWorker() {
                if (!('serviceWorker' in navigator) || !this.root.dataset.serviceWorkerUrl) {
                    return;
                }
                navigator.serviceWorker.register(this.root.dataset.serviceWorkerUrl, { scope: '/quickdrop/' }).catch(() => {
                    this.toast('앱 설치 준비를 마치지 못했습니다.', 'error');
                });
            },

            resizeComposer() {
                if (!this.textInput) {
                    return;
                }
                this.textInput.style.height = 'auto';
                this.textInput.style.height = String(this.textInput.scrollHeight) + 'px';
            },

            capturePastedFile(event) {
                const clipboard = event.clipboardData;
                if (!clipboard || !clipboard.items || !clipboard.items.length) {
                    return false;
                }
                const fileItem = Array.from(clipboard.items).find((item) => item.kind === 'file');
                if (!fileItem) {
                    return false;
                }
                const file = fileItem.getAsFile();
                if (!file) {
                    return false;
                }
                event.preventDefault();
                const filename = file.name && file.name.trim() ? file.name : inferClipboardFilename(file);
                const queuedFile = new File([file], filename, {
                    type: file.type || 'application/octet-stream',
                    lastModified: Date.now(),
                });
                this.setQueuedFile(queuedFile, { keepFocus: true });
                this.toast((queuedFile.type || '').startsWith('image/')
                    ? '붙여넣은 이미지를 담았습니다. 보내기를 누르세요.'
                    : '붙여넣은 파일을 담았습니다. 보내기를 누르세요.');
                return true;
            },

            getQueuedFile() {
                return this.queuedFile || null;
            },

            hasNativeSelectedFile() {
                return Boolean(this.fileInput && this.fileInput.files && this.fileInput.files[0]);
            },

            prepareNativeFileSubmit() {
                if (!this.textForm) {
                    return;
                }
                this.textForm.action = this.root.dataset.sendFileUrl;
                this.textForm.enctype = 'multipart/form-data';
                if (this.sendTextBtn) {
                    this.sendTextBtn.disabled = true;
                    this.sendTextBtn.textContent = '올리는 중...';
                }
            },

            restoreTextSubmitMode() {
                if (!this.textForm) {
                    return;
                }
                this.textForm.action = this.root.dataset.sendTextUrl;
                this.textForm.enctype = 'multipart/form-data';
            },

            setQueuedFile(file, options) {
                const settings = options || {};
                this.queuedFile = file || null;
                if (!file && this.fileInput) {
                    this.fileInput.value = '';
                }
                this.syncSelectedFile();
                this.syncComposerState();
                if (settings.keepFocus && window.matchMedia('(pointer: fine)').matches && this.textInput) {
                    this.textInput.focus();
                }
            },

            syncSelectedFile() {
                if (!this.selectedFileRow || !this.selectedFileName) {
                    return;
                }
                const file = this.getQueuedFile();
                this.selectedFileRow.classList.toggle('hidden', !file);
                this.selectedFileRow.classList.toggle('flex', Boolean(file));
                this.selectedFileName.textContent = file ? file.name : '';
            },

            clearSelectedFile(options) {
                const settings = options || {};
                if (!this.fileInput) {
                    return;
                }
                this.restoreTextSubmitMode();
                this.fileInput.value = '';
                this.queuedFile = null;
                this.syncSelectedFile();
                this.syncComposerState();
                if (!settings.silent && window.matchMedia('(pointer: fine)').matches && this.textInput) {
                    this.textInput.focus();
                }
            },

            syncComposerState() {
                if (!this.sendTextBtn || !this.textInput) {
                    return;
                }
                const hasText = Boolean((this.textInput.value || '').trim());
                const hasFile = Boolean(this.getQueuedFile());
                const enabled = hasText || hasFile;
                this.sendTextBtn.disabled = !enabled;
                this.sendTextBtn.classList.toggle('cursor-not-allowed', !enabled);
                this.sendTextBtn.textContent = hasFile ? '파일 보내기' : '보내기';
            },

            async deleteItem(url) {
                if (!url) {
                    return;
                }
                await this.post(url, new FormData(), null, '기록을 지웠습니다.');
            },

            toast(message, tone) {
                if (!this.toastRoot) {
                    return;
                }
                const item = document.createElement('div');
                item.className = 'rounded-2xl px-4 py-3 text-sm font-black text-white shadow-xl ' + (
                    tone === 'error' ? 'bg-[#d64564]' : 'bg-[#14213d]'
                );
                item.textContent = message;
                this.toastRoot.appendChild(item);
                window.setTimeout(function () {
                    item.remove();
                }, 2200);
            },
        };
    }

    const root = byId('quickdrop-root');
    const bootstrapEl = byId('quickdrop-bootstrap');
    if (!root || !bootstrapEl) {
        return;
    }
    const bootstrap = JSON.parse(bootstrapEl.textContent);
    createApp(root, bootstrap).init();
})();
