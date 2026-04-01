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
        var refreshUrl = root.getAttribute('data-schoolcomm-room-refresh-url') || '';
        var fragment = root.querySelector('[data-schoolcomm-room-fragment="true"]');
        if (!refreshUrl || !fragment) {
            return Promise.resolve();
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
        }).catch(function (error) {
            console.warn('[schoolcomm] failed to refresh room fragment', error);
            setRoomStatus(root, '새 메시지를 불러오지 못했습니다. 화면 새로고침 후 다시 확인해 주세요.', true);
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

        var roomState = {
            inFlight: false,
            queued: false,
            timerId: 0,
        };

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

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-schoolcomm-root="true"]');
        if (!root) {
            return;
        }
        connectUserSocket(root);
        connectRoomSocket(root);
        initMemberPicker(root);
    });
})();
