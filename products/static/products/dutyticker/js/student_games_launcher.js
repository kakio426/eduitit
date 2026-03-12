(function () {
    if (window.__studentGamesLauncherLoaded) {
        return;
    }
    window.__studentGamesLauncherLoaded = true;

    function getCsrfToken() {
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        if (field && field.value) {
            return field.value;
        }
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function notify(message, type) {
        if (window.showToast) {
            window.showToast(message, type || 'info');
            return;
        }
        alert(message);
    }

    async function parseIssueResponse(response) {
        var payload = {};
        try {
            payload = await response.json();
        } catch (error) {
            payload = {};
        }
        if (!response.ok || !payload.success) {
            throw new Error(payload.error || '학생용 링크를 준비하지 못했습니다. 잠시 후 다시 시도해 주세요.');
        }
        return payload;
    }

    function initLauncher(modal) {
        if (!modal || modal.dataset.studentGamesBound === 'true') {
            return;
        }
        modal.dataset.studentGamesBound = 'true';

        var modalId = modal.id;
        var issueUrl = modal.dataset.studentGamesIssueUrl || '';
        var openButtons = document.querySelectorAll('[data-student-games-open="' + modalId + '"]');
        var closeButtons = modal.querySelectorAll('[data-student-games-close]');
        var reissueButtons = modal.querySelectorAll('[data-student-games-reissue]');
        var copyButton = modal.querySelector('[data-student-games-copy]');
        var readyBlock = modal.querySelector('[data-student-games-ready]');
        var loadingBlock = modal.querySelector('[data-student-games-loading]');
        var errorBlock = modal.querySelector('[data-student-games-error]');
        var idleBlock = modal.querySelector('[data-student-games-idle]');
        var errorMessage = modal.querySelector('[data-student-games-error-message]');
        var qrImage = modal.querySelector('[data-student-games-qr-image]');
        var urlInput = modal.querySelector('[data-student-games-url]');
        var previewLink = modal.querySelector('[data-student-games-preview]');
        var expiryLabel = modal.querySelector('[data-student-games-expiry]');
        var panel = modal.firstElementChild;
        var currentPayload = null;
        var expiresAtMs = 0;

        function setState(state, message) {
            if (idleBlock) idleBlock.classList.toggle('hidden', state !== 'idle');
            if (loadingBlock) loadingBlock.classList.toggle('hidden', state !== 'loading');
            if (errorBlock) errorBlock.classList.toggle('hidden', state !== 'error');
            if (readyBlock) readyBlock.classList.toggle('hidden', state !== 'ready');
            if (message && errorMessage) {
                errorMessage.textContent = message;
            }
        }

        function showModal() {
            modal.classList.remove('hidden');
            requestAnimationFrame(function () {
                modal.classList.remove('opacity-0');
                if (panel) {
                    panel.classList.remove('scale-95');
                }
            });
        }

        function hideModal() {
            modal.classList.add('opacity-0');
            if (panel) {
                panel.classList.add('scale-95');
            }
            setTimeout(function () {
                modal.classList.add('hidden');
            }, 180);
        }

        function applyPayload(payload) {
            currentPayload = payload;
            expiresAtMs = Date.now() + ((payload.expires_in_minutes || 0) * 60 * 1000);
            if (qrImage) {
                qrImage.src = payload.qr_data_url || '';
            }
            if (urlInput) {
                urlInput.value = payload.launch_url || '';
            }
            if (previewLink) {
                previewLink.href = payload.launch_url || '#';
            }
            if (expiryLabel) {
                expiryLabel.textContent = '유효시간: ' + (payload.expires_in_minutes || 0) + '분';
            }
        }

        async function issueLink() {
            if (!issueUrl) {
                setState('error', '학생용 링크 발급 경로를 찾지 못했습니다.');
                notify('학생용 링크 발급 경로를 찾지 못했습니다.', 'error');
                return;
            }

            setState('loading');
            try {
                var response = await fetch(issueUrl, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                    },
                    credentials: 'same-origin',
                });
                var payload = await parseIssueResponse(response);
                applyPayload(payload);
                setState('ready');
            } catch (error) {
                var message = error && error.message
                    ? error.message
                    : '학생용 링크를 준비하지 못했습니다. 잠시 후 다시 시도해 주세요.';
                setState('error', message);
                notify(message, 'error');
            }
        }

        function shouldRefreshOnOpen() {
            if (!currentPayload || !currentPayload.launch_url) {
                return true;
            }
            return Date.now() >= expiresAtMs;
        }

        openButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                showModal();
                if (shouldRefreshOnOpen()) {
                    issueLink();
                } else {
                    setState('ready');
                }
            });
        });

        closeButtons.forEach(function (button) {
            button.addEventListener('click', hideModal);
        });

        reissueButtons.forEach(function (button) {
            button.addEventListener('click', issueLink);
        });

        if (copyButton) {
            copyButton.addEventListener('click', async function () {
                if (!urlInput || !urlInput.value) {
                    notify('먼저 학생용 링크를 발급해 주세요.', 'error');
                    return;
                }
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(urlInput.value);
                    } else {
                        urlInput.select();
                        document.execCommand('copy');
                        window.getSelection().removeAllRanges();
                    }
                    notify('학생용 링크를 복사했습니다.', 'success');
                } catch (error) {
                    notify('링크 복사에 실패했습니다. 직접 선택해서 복사해 주세요.', 'error');
                }
            });
        }

        modal.addEventListener('click', function (event) {
            if (event.target === modal) {
                hideModal();
            }
        });

        setState('idle');
    }

    function initAll() {
        document.querySelectorAll('[data-student-games-launcher="true"]').forEach(initLauncher);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();
