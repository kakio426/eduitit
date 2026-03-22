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

            init() {
                this.cacheDom();
                this.render();
                this.bindForms();
                this.bindClipboard();
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
                this.textPanel = byId('text-panel');
                this.textOutput = byId('text-output');
                this.messageTime = byId('message-time');
                this.copyTextBtn = byId('copy-text-btn');
                this.imagePanel = byId('image-panel');
                this.imageOutput = byId('image-output');
                this.imageFilename = byId('image-filename');
                this.saveImageBtn = byId('save-image-btn');
                this.historyPanel = byId('history-panel');
                this.historySummary = byId('history-summary');
                this.historyEmpty = byId('history-empty');
                this.historyList = byId('history-list');
                this.textForm = byId('text-form');
                this.textInput = byId('text-input');
                this.sendTextBtn = byId('send-text-btn');
                this.imageForm = byId('image-form');
                this.imageInput = byId('image-input');
                this.photoTrigger = byId('photo-trigger');
                this.composerTipDesktop = byId('composer-tip-desktop');
                this.composerTipMobile = byId('composer-tip-mobile');
                this.endSessionBtn = byId('end-session-btn');
                this.toastRoot = byId('toast-root');
            },

            isCompactMobile() {
                return window.matchMedia('(max-width: 639px)').matches;
            },

            sessionFingerprint(payload) {
                return JSON.stringify(payload || {});
            },

            bindForms() {
                if (this.textForm) {
                    this.textForm.addEventListener('submit', (event) => {
                        event.preventDefault();
                        this.sendText(this.textInput.value);
                    });
                }
                if (this.imageForm) {
                    this.imageForm.addEventListener('submit', (event) => {
                        event.preventDefault();
                        this.sendImage(this.imageInput.files[0]);
                    });
                }
                if (this.textInput) {
                    this.textInput.addEventListener('input', () => {
                        this.resizeComposer();
                        this.syncComposerState();
                    });
                    this.textInput.addEventListener('keydown', (event) => {
                        if (event.key !== 'Enter' || event.shiftKey || event.isComposing) {
                            return;
                        }
                        const value = (this.textInput.value || '').trim();
                        if (!value) {
                            return;
                        }
                        event.preventDefault();
                        this.sendText(this.textInput.value);
                    });
                }
                if (this.imageInput) {
                    this.imageInput.addEventListener('change', () => {
                        if (this.imageInput.files[0]) {
                            this.sendImage(this.imageInput.files[0]);
                        }
                    });
                }
            },

            bindClipboard() {
                document.addEventListener('paste', (event) => {
                    const clipboard = event.clipboardData;
                    if (!clipboard) {
                        return;
                    }

                    const imageItem = Array.from(clipboard.items || []).find((item) => item.type && item.type.indexOf('image/') === 0);
                    if (imageItem) {
                        const file = imageItem.getAsFile();
                        if (file) {
                            event.preventDefault();
                            this.sendImage(file);
                            return;
                        }
                    }

                    const text = clipboard.getData('text');
                    if (text && text.trim()) {
                        event.preventDefault();
                        this.sendText(text);
                    }
                });
            },

            bindActions() {
                if (this.copyTextBtn) {
                    this.copyTextBtn.addEventListener('click', async () => {
                        try {
                            await navigator.clipboard.writeText(this.session.current_text || '');
                            this.toast('텍스트를 복사했습니다.', 'success');
                        } catch (_error) {
                            this.toast('텍스트 복사에 실패했습니다.', 'error');
                        }
                    });
                }

                if (this.saveImageBtn) {
                    this.saveImageBtn.addEventListener('click', async () => {
                        if (!this.session.current_image_url) {
                            return;
                        }
                        try {
                            const response = await fetch(this.session.current_image_url, { credentials: 'same-origin' });
                            if (!response.ok) {
                                throw new Error('image fetch failed');
                            }
                            const blob = await response.blob();
                            const filename = this.session.current_filename || 'shared-image';
                            const file = new File([blob], filename, { type: blob.type || 'image/png' });

                            if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
                                await navigator.share({ files: [file], title: filename });
                                return;
                            }

                            const link = document.createElement('a');
                            link.href = URL.createObjectURL(blob);
                            link.download = filename;
                            link.click();
                            window.setTimeout(function () {
                                URL.revokeObjectURL(link.href);
                            }, 300);
                        } catch (_error) {
                            this.toast('이미지를 저장할 수 없습니다.', 'error');
                        }
                    });
                }

                if (this.endSessionBtn) {
                    this.endSessionBtn.addEventListener('click', () => {
                        this.post(this.root.dataset.endSessionUrl, new FormData(), null, '오늘 내용을 비웠습니다.');
                    });
                }

                if (this.photoTrigger) {
                    this.photoTrigger.addEventListener('click', () => {
                        this.imageInput.click();
                    });
                }
            },

            async sendText(text) {
                const payload = new FormData();
                payload.append('text', text);
                await this.post(this.root.dataset.sendTextUrl, payload, () => {
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

            async sendImage(file) {
                if (!file) {
                    return;
                }
                const payload = new FormData();
                payload.append('image', file, file.name || 'shared-image.png');
                await this.post(this.root.dataset.sendImageUrl, payload, () => {
                    this.imageInput.value = '';
                }, '이미지를 보냈습니다.');
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
                const todayItems = Array.isArray(this.session.today_items) ? this.session.today_items : [];
                const isCompactMobile = this.isCompactMobile();

                if (this.emptyState) {
                    this.emptyState.classList.toggle('hidden', isText || isImage);
                }
                if (this.textPanel) {
                    this.textPanel.classList.toggle('hidden', !isText);
                }
                if (this.imagePanel) {
                    this.imagePanel.classList.toggle('hidden', !isImage);
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
                        this.emptyBody.textContent = isCompactMobile
                            ? '다시 붙여넣거나 사진을 고르면 됩니다.'
                            : '다시 붙여넣거나 사진을 고르면 새 기록이 바로 쌓입니다.';
                    } else {
                        this.emptyBadge.textContent = '전송 준비';
                        this.emptyTitle.textContent = isCompactMobile
                            ? '붙여넣기나 사진 선택만 하면 됩니다.'
                            : 'PC끼리도, 휴대폰끼리도 바로 옮기세요.';
                        this.emptyBody.textContent = isCompactMobile
                            ? '같은 통로만 열어 두면 텍스트와 사진이 바로 넘어갑니다.'
                            : '붙여넣기나 사진 선택만 하면 방금 보낸 내용은 위에, 오늘 기록은 아래에 남습니다.';
                    }
                }

                if (this.textOutput) {
                    this.textOutput.textContent = this.session.current_text || '';
                }
                if (this.messageTime) {
                    this.messageTime.textContent = this.session.updated_at ? formatTime(this.session.updated_at) : '';
                }
                if (this.imageOutput) {
                    this.imageOutput.src = this.session.current_image_url || '';
                }
                if (this.imageFilename) {
                    const imageMeta = [];
                    if (this.session.current_filename) {
                        imageMeta.push(this.session.current_filename);
                    }
                    if (this.session.updated_at) {
                        imageMeta.push(formatTime(this.session.updated_at));
                    }
                    this.imageFilename.textContent = imageMeta.join(' · ') || '사진 파일';
                }
                if (this.historySummary) {
                    this.historySummary.textContent = '오늘 ' + String(todayItems.length) + '개';
                }
                if (this.historyPanel) {
                    this.historyPanel.classList.toggle('hidden', isCompactMobile && todayItems.length === 0);
                }
                if (this.endSessionBtn) {
                    this.endSessionBtn.classList.toggle('hidden', todayItems.length === 0);
                }
                this.renderHistory(todayItems);
                this.resizeComposer();
                this.syncComposerState();
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

                const visibleItems = this.isCompactMobile() ? items.slice(0, 6) : items;
                const fragment = document.createDocumentFragment();
                visibleItems.forEach((item, index) => {
                    fragment.appendChild(this.buildHistoryItem(item, index === visibleItems.length - 1));
                });
                this.historyList.appendChild(fragment);
            },

            buildHistoryItem(item, isLatest) {
                const card = document.createElement('article');
                card.className = 'rounded-[22px] border px-4 py-3 shadow-sm ' + (
                    isLatest
                        ? 'border-[#cfe0ff] bg-[#f4f8ff]'
                        : 'border-[#e6ecff] bg-white'
                );

                const header = document.createElement('div');
                header.className = 'flex items-center justify-between gap-3';

                const left = document.createElement('div');
                left.className = 'min-w-0 flex items-center gap-2';

                const badge = document.createElement('span');
                badge.className = 'flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-[#e8efff] text-sm font-black text-[#1f4fd1]';
                badge.textContent = item.kind === 'image' ? '🖼' : 'T';

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
                left.appendChild(badge);
                left.appendChild(meta);

                const right = document.createElement('span');
                right.className = 'shrink-0 rounded-full px-2.5 py-1 text-[11px] font-black ' + (
                    item.kind === 'image'
                        ? 'bg-[#fff1dd] text-[#9a5e00]'
                        : 'bg-[#edf3ff] text-[#1f4fd1]'
                );
                right.textContent = isLatest ? '방금' : (item.kind === 'image' ? '사진' : '텍스트');

                header.appendChild(left);
                header.appendChild(right);

                const body = document.createElement('div');
                body.className = 'mt-3 rounded-[18px] bg-[#f8faff] px-4 py-3 text-sm leading-6 text-slate-600';
                if (item.kind === 'image') {
                    body.textContent = item.filename || '사진을 보냈습니다.';
                } else {
                    body.textContent = item.text || '';
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

            syncComposerState() {
                if (!this.sendTextBtn || !this.textInput) {
                    return;
                }
                const hasValue = Boolean((this.textInput.value || '').trim());
                this.sendTextBtn.disabled = !hasValue;
                this.sendTextBtn.classList.toggle('opacity-50', !hasValue);
                this.sendTextBtn.classList.toggle('cursor-not-allowed', !hasValue);
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
