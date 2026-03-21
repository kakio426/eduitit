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
            experiencedMode: false,

            init() {
                this.cacheDom();
                this.restoreExperience();
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
                this.helperChipPhoto = byId('helper-chip-photo');
                this.helperChipShare = byId('helper-chip-share');
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
                this.textForm = byId('text-form');
                this.textInput = byId('text-input');
                this.sendTextBtn = byId('send-text-btn');
                this.imageForm = byId('image-form');
                this.imageInput = byId('image-input');
                this.photoTrigger = byId('photo-trigger');
                this.composerTipRow = byId('composer-tip-row');
                this.composerTipDesktop = byId('composer-tip-desktop');
                this.composerTipMobile = byId('composer-tip-mobile');
                this.endSessionBtn = byId('end-session-btn');
                this.toastRoot = byId('toast-root');
            },

            bindForms() {
                this.textForm.addEventListener('submit', (event) => {
                    event.preventDefault();
                    this.sendText(this.textInput.value);
                });
                this.imageForm.addEventListener('submit', (event) => {
                    event.preventDefault();
                    this.sendImage(this.imageInput.files[0]);
                });
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
                this.imageInput.addEventListener('change', () => {
                    if (this.imageInput.files[0]) {
                        this.sendImage(this.imageInput.files[0]);
                    }
                });
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
                this.copyTextBtn.addEventListener('click', async () => {
                    try {
                        await navigator.clipboard.writeText(this.session.current_text || '');
                        this.toast('텍스트를 복사했습니다.', 'success');
                    } catch (_error) {
                        this.toast('텍스트 복사에 실패했습니다.', 'error');
                    }
                });

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

                this.endSessionBtn.addEventListener('click', () => {
                    this.post(this.root.dataset.endSessionUrl, new FormData(), null, '내용을 지우고 마쳤습니다.');
                });

                this.photoTrigger.addEventListener('click', () => {
                    this.imageInput.click();
                });
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
                    this.markExperienced();
                    this.render();
                    if (onSuccess) {
                        onSuccess();
                    }
                    if (successMessage) {
                        this.toast(successMessage, 'success');
                    }
                } catch (error) {
                    this.toast(error.message || '전송에 실패했습니다.', 'error');
                }
            },

            render() {
                const kind = this.session.current_kind || 'empty';
                const isText = kind === 'text';
                const isImage = kind === 'image';
                if (isText || isImage || this.session.status === 'ended') {
                    this.markExperienced();
                }
                this.emptyState.classList.toggle('hidden', isText || isImage);
                this.textPanel.classList.toggle('hidden', !isText);
                this.imagePanel.classList.toggle('hidden', !isImage);

                if (this.sessionStatus) {
                    if (kind === 'text') {
                        this.sessionStatus.textContent = '텍스트 도착';
                    } else if (kind === 'image') {
                        this.sessionStatus.textContent = '사진 도착';
                    } else if (this.session.status === 'ended') {
                        this.sessionStatus.textContent = '지금은 비어 있음';
                    } else {
                        this.sessionStatus.textContent = '전송 준비';
                    }
                }
                if (this.sessionExpiry) {
                    this.sessionExpiry.textContent = this.session.status === 'ended'
                        ? '내용은 삭제되었고 통로만 남아 있습니다.'
                        : '마지막 활동 후 10분 유휴면 자동 삭제됩니다.';
                }
                if (this.helperChipPaste && this.helperChipPhoto && this.helperChipShare && this.helperChipRepeat) {
                    this.helperChipPaste.classList.toggle('hidden', this.experiencedMode);
                    this.helperChipPhoto.classList.toggle('hidden', this.experiencedMode);
                    this.helperChipShare.classList.toggle('hidden', this.experiencedMode);
                    this.helperChipRepeat.classList.toggle('hidden', !this.experiencedMode);
                }
                if (this.composerTipRow && this.composerTipDesktop && this.composerTipMobile) {
                    this.composerTipRow.classList.toggle('opacity-70', this.experiencedMode);
                    this.composerTipDesktop.textContent = this.experiencedMode
                        ? '붙여넣기 또는 Enter로 바로 전송'
                        : '데스크톱은 화면 어디서든 Ctrl+V';
                    this.composerTipMobile.textContent = this.experiencedMode
                        ? '사진은 버튼 한 번이면 충분합니다'
                        : '휴대폰은 입력창 또는 사진 버튼';
                }
                if (this.emptyState) {
                    this.emptyState.dataset.density = this.experiencedMode ? 'compact' : 'full';
                }
                if (this.emptyBadge && this.emptyTitle && this.emptyBody) {
                    if (this.session.status === 'ended') {
                        this.emptyBadge.textContent = '내용 정리됨';
                        this.emptyTitle.textContent = '방금 보낸 내용은 바로 지워졌습니다.';
                        this.emptyBody.textContent = '통로는 그대로 남아 있으니, 다시 붙여넣거나 사진을 고르면 새 전송이 바로 시작됩니다.';
                    } else if (this.experiencedMode) {
                        this.emptyBadge.textContent = '바로 보내기';
                        this.emptyTitle.textContent = '이제 바로 붙여넣거나 사진만 고르세요.';
                        this.emptyBody.textContent = '처음 연결은 끝났습니다. 여기서는 바로 보내고, 다른 기기에서는 바로 복사하거나 저장하면 됩니다.';
                    } else {
                        this.emptyBadge.textContent = '전송 준비';
                        this.emptyTitle.textContent = '두 기기에서 같은 통로만 열어 두세요.';
                        this.emptyBody.textContent = '데스크톱은 그냥 붙여넣기, 휴대폰은 아래 입력창이나 공유하기에서 바로 보내면 됩니다.';
                    }
                }
                if (this.emptyPillRow) {
                    this.emptyPillRow.classList.toggle('hidden', this.experiencedMode);
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
                this.resizeComposer();
                this.syncComposerState();
            },

            connectSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                this.ws = new WebSocket(protocol + '//' + window.location.host + this.root.dataset.wsUrl);
                this.ws.addEventListener('open', () => {
                    this.connectionBadge.textContent = '실시간 연결됨';
                    this.startPing();
                });
                this.ws.addEventListener('message', (event) => {
                    try {
                        this.handleMessage(JSON.parse(event.data));
                    } catch (_error) {
                        this.toast('실시간 업데이트를 읽지 못했습니다.', 'error');
                    }
                });
                this.ws.addEventListener('close', () => {
                    this.connectionBadge.textContent = '다시 연결 중';
                    window.clearInterval(this.pingTimer);
                    window.setTimeout(() => this.connectSocket(), 1500);
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

            restoreExperience() {
                this.experiencedMode = window.localStorage.getItem('quickdrop-experienced') === '1';
            },

            markExperienced() {
                if (this.experiencedMode) {
                    return;
                }
                this.experiencedMode = true;
                try {
                    window.localStorage.setItem('quickdrop-experienced', '1');
                } catch (_error) {
                    return;
                }
            },

            toast(message, tone) {
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
