(function () {
    function buildSocketUrl(path) {
        if (!path) {
            return '';
        }
        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return protocol + '//' + window.location.host + path;
    }

    function updateBadge(name, value) {
        document.querySelectorAll('[data-schoolcomm-badge="' + name + '"]').forEach(function (node) {
            node.textContent = String(value == null ? 0 : value);
        });
    }

    function setRoomStatus(root, message, isError) {
        var node = root.querySelector('[data-schoolcomm-room-status="true"]');
        if (!node) {
            return;
        }
        if (!message) {
            node.textContent = '';
            node.classList.add('hidden');
            return;
        }
        node.textContent = message;
        node.classList.remove('hidden');
        node.classList.toggle('border-amber-200', !!isError);
        node.classList.toggle('bg-amber-50', !!isError);
        node.classList.toggle('text-amber-700', !!isError);
    }

    function connectUserSocket(root) {
        var rawPath = root.getAttribute('data-schoolcomm-user-ws-url') || '';
        var socketUrl = buildSocketUrl(rawPath);
        if (!socketUrl) {
            return;
        }
        var socket = new WebSocket(socketUrl);
        socket.onmessage = function (event) {
            try {
                var data = JSON.parse(event.data || '{}');
                if (data.type !== 'notification.summary') {
                    return;
                }
                var payload = data.payload || {};
                updateBadge('total_unread', payload.total_unread);
                updateBadge('notice_unread', payload.notice_unread);
                updateBadge('suggestion_count', payload.suggestion_count);
            } catch (error) {
                console.warn('[schoolcomm] failed to parse user socket payload', error);
            }
        };
    }

    function getRoomRefreshState(root) {
        if (!root._schoolcommRoomState) {
            root._schoolcommRoomState = {
                inFlight: false,
                queued: false,
                timerId: 0,
            };
        }
        return root._schoolcommRoomState;
    }

    function captureRoomUiState(fragment) {
        var state = {
            scrollTop: window.pageYOffset || window.scrollY || 0,
            openThreadPanels: [],
            openAssetPanels: [],
            replyDrafts: {},
        };

        fragment.querySelectorAll('[data-schoolcomm-thread-panel]').forEach(function (node) {
            if (node.open) {
                state.openThreadPanels.push(node.getAttribute('data-schoolcomm-thread-panel'));
            }
        });

        fragment.querySelectorAll('[data-schoolcomm-asset-panel]').forEach(function (node) {
            if (node.open) {
                state.openAssetPanels.push(node.getAttribute('data-schoolcomm-asset-panel'));
            }
        });

        fragment.querySelectorAll('[data-schoolcomm-reply-textarea]').forEach(function (node) {
            var key = node.getAttribute('data-schoolcomm-reply-textarea');
            if (!key) {
                return;
            }
            state.replyDrafts[key] = node.value || '';
        });

        return state;
    }

    function restoreRoomUiState(fragment, state) {
        (state.openThreadPanels || []).forEach(function (key) {
            var node = fragment.querySelector('[data-schoolcomm-thread-panel="' + key + '"]');
            if (node) {
                node.open = true;
            }
        });

        (state.openAssetPanels || []).forEach(function (key) {
            var node = fragment.querySelector('[data-schoolcomm-asset-panel="' + key + '"]');
            if (node) {
                node.open = true;
            }
        });

        Object.keys(state.replyDrafts || {}).forEach(function (key) {
            var node = fragment.querySelector('[data-schoolcomm-reply-textarea="' + key + '"]');
            if (node) {
                node.value = state.replyDrafts[key];
            }
        });

        window.requestAnimationFrame(function () {
            window.scrollTo({ top: state.scrollTop || 0, behavior: 'auto' });
        });
    }

    function refreshRoomFragment(root, roomState) {
        roomState = roomState || getRoomRefreshState(root);
        var refreshUrl = root.getAttribute('data-schoolcomm-room-refresh-url') || '';
        var fragment = root.querySelector('[data-schoolcomm-room-fragment="true"]');
        if (!refreshUrl || !fragment) {
            return Promise.resolve(false);
        }

        var uiState = captureRoomUiState(fragment);
        roomState.inFlight = true;

        return window.fetch(refreshUrl, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        }).then(function (response) {
            if (!response.ok) {
                throw new Error('fragment refresh failed: ' + response.status);
            }
            return response.text();
        }).then(function (html) {
            fragment.innerHTML = html;
            restoreRoomUiState(fragment, uiState);
            setRoomStatus(root, '', false);
            return true;
        }).catch(function (error) {
            console.warn('[schoolcomm] failed to refresh room fragment', error);
            setRoomStatus(root, '새 메시지를 불러오지 못했습니다. 화면 새로고침 후 다시 확인해 주세요.', true);
            return false;
        }).finally(function () {
            roomState.inFlight = false;
            if (roomState.queued) {
                roomState.queued = false;
                scheduleRoomRefresh(root, roomState);
            }
        });
    }

    function scheduleRoomRefresh(root, roomState) {
        if (roomState.timerId) {
            window.clearTimeout(roomState.timerId);
        }
        roomState.timerId = window.setTimeout(function () {
            if (roomState.inFlight) {
                roomState.queued = true;
                return;
            }
            refreshRoomFragment(root, roomState);
        }, 180);
    }

    function connectRoomSocket(root) {
        var rawPath = root.getAttribute('data-schoolcomm-room-ws-url') || '';
        var socketUrl = buildSocketUrl(rawPath);
        if (!socketUrl) {
            return;
        }

        var roomState = getRoomRefreshState(root);

        var socket = new WebSocket(socketUrl);
        socket.onmessage = function (event) {
            try {
                var data = JSON.parse(event.data || '{}');
                if (!data.type || data.type === 'room.snapshot') {
                    return;
                }
                scheduleRoomRefresh(root, roomState);
            } catch (error) {
                console.warn('[schoolcomm] failed to parse room socket payload', error);
            }
        };
    }

    function setMemberFeedback(feedbackNode, message) {
        if (!feedbackNode) {
            return;
        }
        if (!message) {
            feedbackNode.textContent = '';
            feedbackNode.classList.add('hidden');
            return;
        }
        feedbackNode.textContent = message;
        feedbackNode.classList.remove('hidden');
    }

    function initMemberPicker(root) {
        root.querySelectorAll('[data-schoolcomm-member-picker="true"]').forEach(function (picker) {
            var searchInput = picker.querySelector('[data-schoolcomm-member-search="true"]');
            var rows = Array.prototype.slice.call(picker.querySelectorAll('[data-schoolcomm-member-row="true"]'));
            var checkboxes = Array.prototype.slice.call(picker.querySelectorAll('[data-schoolcomm-member-checkbox="true"]'));
            var countNode = picker.querySelector('[data-schoolcomm-selected-count="true"]');
            var feedbackNode = picker.querySelector('[data-schoolcomm-member-feedback="true"]');
            var submitButton = picker.querySelector('[data-schoolcomm-member-submit="true"]');
            var maxSelections = 4;

            function selectedCount() {
                return checkboxes.filter(function (checkbox) {
                    return checkbox.checked;
                }).length;
            }

            function syncSelectionUi() {
                var count = selectedCount();
                if (countNode) {
                    countNode.textContent = String(count);
                }
                if (submitButton) {
                    submitButton.disabled = count === 0;
                    submitButton.classList.toggle('opacity-50', count === 0);
                    submitButton.classList.toggle('cursor-not-allowed', count === 0);
                }
            }

            function filterRows() {
                var keyword = (searchInput && searchInput.value ? searchInput.value : '').trim().toLowerCase();
                rows.forEach(function (row) {
                    var haystack = (row.getAttribute('data-search-text') || '').toLowerCase();
                    var matches = !keyword || haystack.indexOf(keyword) !== -1;
                    row.classList.toggle('is-hidden', !matches);
                });
            }

            checkboxes.forEach(function (checkbox) {
                checkbox.addEventListener('change', function () {
                    if (selectedCount() > maxSelections) {
                        checkbox.checked = false;
                        setMemberFeedback(feedbackNode, '최대 4명까지 선택할 수 있습니다.');
                    } else {
                        setMemberFeedback(feedbackNode, '');
                    }
                    syncSelectionUi();
                });
            });

            if (searchInput) {
                searchInput.addEventListener('input', filterRows);
            }

            filterRows();
            syncSelectionUi();
        });
    }

    function focusCalendarTarget(panel, focusKey) {
        if (!panel) {
            return;
        }
        var target = null;
        if (focusKey) {
            target = panel.querySelector('[data-schoolcomm-calendar-key="' + focusKey + '"]');
        }
        if (!target) {
            target = panel.querySelector('[data-schoolcomm-calendar-heading="true"]');
        }
        if (!target || typeof target.focus !== 'function') {
            return;
        }
        try {
            target.focus({ preventScroll: true });
        } catch (error) {
            target.focus();
        }
    }

    function replaceCalendarPanel(root, html, focusKey) {
        var currentPanel = root.querySelector('[data-schoolcomm-calendar-panel="true"]');
        if (!currentPanel) {
            return false;
        }

        var container = document.createElement('div');
        container.innerHTML = html;
        var nextPanel = container.querySelector('[data-schoolcomm-calendar-panel="true"]');
        if (!nextPanel) {
            return false;
        }

        currentPanel.replaceWith(nextPanel);
        focusCalendarTarget(nextPanel, focusKey);
        return true;
    }

    function shouldInterceptCalendarClick(event, link) {
        if (!link || event.defaultPrevented) {
            return false;
        }
        if (event.button !== 0) {
            return false;
        }
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return false;
        }
        if ((link.getAttribute('target') || '').trim() === '_blank') {
            return false;
        }
        if (link.hasAttribute('download')) {
            return false;
        }
        return typeof window.fetch === 'function';
    }

    function initCalendarPanel(root) {
        if (!root.querySelector('[data-schoolcomm-calendar-panel="true"]')) {
            return;
        }

        var calendarState = {
            requestId: 0,
            abortController: null,
        };

        root.addEventListener('click', function (event) {
            var link = event.target.closest('[data-schoolcomm-calendar-link="true"]');
            if (!link || !root.contains(link) || !shouldInterceptCalendarClick(event, link)) {
                return;
            }

            var currentPanel = root.querySelector('[data-schoolcomm-calendar-panel="true"]');
            if (!currentPanel) {
                return;
            }

            var navigationUrl = new URL(link.href, window.location.origin);
            if (navigationUrl.origin !== window.location.origin) {
                return;
            }

            event.preventDefault();

            var fragmentUrl = new URL(navigationUrl.toString());
            fragmentUrl.searchParams.set('fragment', 'calendar_panel');
            var focusKey = link.getAttribute('data-schoolcomm-calendar-key') || '';
            var requestId = calendarState.requestId + 1;
            calendarState.requestId = requestId;

            if (calendarState.abortController) {
                calendarState.abortController.abort();
            }
            calendarState.abortController = typeof AbortController !== 'undefined' ? new AbortController() : null;

            currentPanel.setAttribute('aria-busy', 'true');

            window.fetch(fragmentUrl.toString(), {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                signal: calendarState.abortController ? calendarState.abortController.signal : undefined,
            }).then(function (response) {
                if (!response.ok) {
                    throw new Error('calendar fragment refresh failed: ' + response.status);
                }
                return response.text();
            }).then(function (html) {
                if (requestId !== calendarState.requestId) {
                    return;
                }
                if (!replaceCalendarPanel(root, html, focusKey)) {
                    throw new Error('calendar fragment missing panel');
                }
                if (window.history && typeof window.history.replaceState === 'function') {
                    window.history.replaceState(window.history.state, '', navigationUrl.pathname + navigationUrl.search + navigationUrl.hash);
                }
            }).catch(function (error) {
                if (error && error.name === 'AbortError') {
                    return;
                }
                console.warn('[schoolcomm] failed to refresh calendar panel', error);
                window.location.assign(navigationUrl.toString());
            }).finally(function () {
                if (requestId !== calendarState.requestId) {
                    return;
                }
                var panel = root.querySelector('[data-schoolcomm-calendar-panel="true"]');
                if (panel) {
                    panel.removeAttribute('aria-busy');
                }
                calendarState.abortController = null;
            });
        });
    }

    function setChatReplyState(root, payload) {
        var stateNode = root.querySelector('[data-schoolcomm-chat-reply-state="true"]');
        var inputNode = root.querySelector('[data-schoolcomm-chat-parent-input="true"]');
        var senderNode = root.querySelector('[data-schoolcomm-chat-reply-sender="true"]');
        var previewNode = root.querySelector('[data-schoolcomm-chat-reply-preview="true"]');
        var textarea = root.querySelector('[data-schoolcomm-chat-composer-text="true"]');

        if (!stateNode || !inputNode) {
            return;
        }

        if (!payload || !payload.parentMessageId) {
            inputNode.value = '';
            if (senderNode) {
                senderNode.textContent = '';
            }
            if (previewNode) {
                previewNode.textContent = '';
            }
            stateNode.classList.add('hidden');
            return;
        }

        inputNode.value = String(payload.parentMessageId);
        if (senderNode) {
            senderNode.textContent = payload.senderName || '상대';
        }
        if (previewNode) {
            previewNode.textContent = payload.preview || '원본 메시지에 답글을 남깁니다.';
        }
        stateNode.classList.remove('hidden');
        if (textarea && typeof textarea.focus === 'function') {
            textarea.focus();
        }
    }

    function requestFormSubmit(form) {
        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
            return;
        }

        var submitEvent = new Event('submit', { bubbles: true, cancelable: true });
        if (form.dispatchEvent(submitEvent)) {
            form.submit();
        }
    }

    function setChatComposerSubmitting(composer, textarea, isSubmitting) {
        var submitButton = composer.querySelector('button[type="submit"]');
        var fileInput = composer.querySelector('input[type="file"]');

        composer.setAttribute('aria-busy', isSubmitting ? 'true' : 'false');
        textarea.disabled = !!isSubmitting;
        if (fileInput) {
            fileInput.disabled = !!isSubmitting;
        }
        if (submitButton) {
            submitButton.disabled = !!isSubmitting;
            submitButton.classList.toggle('opacity-60', !!isSubmitting);
            submitButton.classList.toggle('cursor-wait', !!isSubmitting);
        }
    }

    function readComposerError(response) {
        var fallbackMessage = '메시지를 보내지 못했습니다. 다시 확인해 주세요.';
        var contentType = response.headers.get('content-type') || '';

        if (contentType.indexOf('application/json') !== -1) {
            return response.json().then(function (payload) {
                return (payload && payload.error) || fallbackMessage;
            }).catch(function () {
                return fallbackMessage;
            });
        }

        return response.text().then(function (text) {
            var trimmed = (text || '').trim();
            return trimmed || fallbackMessage;
        }).catch(function () {
            return fallbackMessage;
        });
    }

    function submitChatComposer(root, composer, textarea) {
        var roomState = getRoomRefreshState(root);
        var formData = new FormData(composer);

        setChatComposerSubmitting(composer, textarea, true);
        setRoomStatus(root, '', false);

        return window.fetch(composer.action, {
            method: (composer.method || 'POST').toUpperCase(),
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                Accept: 'application/json',
            },
        }).then(function (response) {
            if (response.ok) {
                return response.json();
            }
            return readComposerError(response).then(function (message) {
                throw new Error(message);
            });
        }).then(function (payload) {
            composer.reset();
            setChatReplyState(root, null);
            return refreshRoomFragment(root, roomState).then(function (refreshed) {
                if (!refreshed) {
                    var redirectUrl = new URL(window.location.href);
                    redirectUrl.hash = 'message-' + (payload.message && payload.message.id ? payload.message.id : '');
                    window.location.assign(redirectUrl.toString());
                    return;
                }
                if (typeof textarea.focus === 'function') {
                    textarea.focus();
                }
            });
        }).catch(function (error) {
            var message = error && error.message ? error.message : '메시지를 보내지 못했습니다. 다시 확인해 주세요.';
            setRoomStatus(root, message, true);
            window.alert(message);
        }).finally(function () {
            setChatComposerSubmitting(composer, textarea, false);
        });
    }

    function initChatReplyComposer(root) {
        var composer = root.querySelector('[data-schoolcomm-chat-composer="true"]');
        var textarea = root.querySelector('[data-schoolcomm-chat-composer-text="true"]');
        if (!composer || !textarea) {
            return;
        }

        textarea.addEventListener('keydown', function (event) {
            if (event.key !== 'Enter') {
                return;
            }
            if (event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) {
                return;
            }
            if (event.isComposing || event.keyCode === 229) {
                return;
            }

            event.preventDefault();
            requestFormSubmit(composer);
        });

        composer.addEventListener('submit', function (event) {
            if (!window.fetch || !window.FormData) {
                return;
            }
            event.preventDefault();
            submitChatComposer(root, composer, textarea);
        });

        root.addEventListener('click', function (event) {
            var replyTrigger = event.target.closest('[data-schoolcomm-chat-reply-trigger="true"]');
            if (replyTrigger && root.contains(replyTrigger)) {
                event.preventDefault();
                setChatReplyState(root, {
                    parentMessageId: replyTrigger.getAttribute('data-schoolcomm-parent-message-id') || '',
                    senderName: replyTrigger.getAttribute('data-schoolcomm-parent-sender') || '',
                    preview: replyTrigger.getAttribute('data-schoolcomm-parent-preview') || '',
                });
                return;
            }

            var cancelTrigger = event.target.closest('[data-schoolcomm-chat-reply-cancel="true"]');
            if (cancelTrigger && root.contains(cancelTrigger)) {
                event.preventDefault();
                setChatReplyState(root, null);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-schoolcomm-root="true"]');
        if (!root) {
            return;
        }
        connectUserSocket(root);
        connectRoomSocket(root);
        initMemberPicker(root);
        initCalendarPanel(root);
        initChatReplyComposer(root);
    });
})();
