(function () {
    function parseJsonScript(id, fallback) {
        var node = document.getElementById(id);
        if (!node) {
            return fallback;
        }
        try {
            return JSON.parse(node.textContent || '');
        } catch (error) {
            return fallback;
        }
    }

    function getHomeV2Config() {
        return parseJsonScript('home-v2-frontend-config', {}) || {};
    }

    function getCsrfToken() {
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        if (field && field.value) {
            return field.value;
        }
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function showFeedback(message, type) {
        if (window.showToast) {
            window.showToast(message, type || 'info');
            return;
        }
        if ((type || 'info') === 'error') {
            alert(message);
        }
    }

    window.homeV4Shell = function () {
        return {
            openSection: '',
            menuSheetOpen: false,
            quickdropHomeDraftText: '',
            quickdropHomeErrorText: '',
            quickdropHomeLastSentText: '',
            isSendingQuickdropHomeText: false,

            focusQuickdropHomeDraftInput: function (form) {
                var scopedInput = form && typeof form.querySelector === 'function'
                    ? form.querySelector('textarea[name="text"]')
                    : document.querySelector('[data-home-v4-quickdrop-form="true"] textarea[name="text"], [data-home-v4-mobile-quickdrop-form="true"] textarea[name="text"]');
                if (scopedInput && typeof scopedInput.focus === 'function') {
                    scopedInput.focus();
                }
            },

            quickdropHomeHasSummary: function (initialSummary) {
                var latestText = String(this.quickdropHomeLastSentText || '').trim();
                var fallbackSummary = String(initialSummary || '').trim();
                return Boolean(latestText || fallbackSummary);
            },

            quickdropHomeSummaryText: function (initialSummary) {
                var latestText = String(this.quickdropHomeLastSentText || '').trim();
                if (latestText) {
                    return latestText;
                }
                return String(initialSummary || '').trim();
            },

            submitQuickdropHomeText: async function (event) {
                var form = event && event.currentTarget ? event.currentTarget : null;
                var action = form && form.action ? String(form.action) : '';
                var draftText = String(this.quickdropHomeDraftText || '').trim();
                var csrfToken = getCsrfToken();
                if (!draftText) {
                    this.quickdropHomeErrorText = '보낼 글을 먼저 입력해 주세요.';
                    showFeedback(this.quickdropHomeErrorText, 'info');
                    this.focusQuickdropHomeDraftInput(form);
                    return;
                }
                if (!action) {
                    this.quickdropHomeErrorText = '바로전송 경로를 찾지 못했습니다.';
                    showFeedback(this.quickdropHomeErrorText, 'error');
                    return;
                }
                if (!csrfToken) {
                    this.quickdropHomeErrorText = '보안 토큰을 확인할 수 없습니다. 새로고침 후 다시 시도해 주세요.';
                    showFeedback(this.quickdropHomeErrorText, 'error');
                    return;
                }
                this.isSendingQuickdropHomeText = true;
                this.quickdropHomeErrorText = '';
                var formData = new FormData(form || undefined);
                formData.set('text', draftText);
                try {
                    var response = await fetch(action, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: formData,
                    });
                    var payload = {};
                    try {
                        payload = await response.json();
                    } catch (jsonError) {
                        payload = {};
                    }
                    if (!response.ok) {
                        throw new Error(payload.error || '바로전송에 실패했습니다.');
                    }
                    var session = payload && payload.session ? payload.session : {};
                    this.quickdropHomeLastSentText = String(session.current_text || draftText).trim();
                    this.quickdropHomeDraftText = '';
                    if (form && typeof form.reset === 'function') {
                        form.reset();
                    }
                    showFeedback('바로전송으로 보냈어요.', 'success');
                    this.focusQuickdropHomeDraftInput(form);
                } catch (error) {
                    this.quickdropHomeErrorText = error && error.message ? error.message : '바로전송에 실패했습니다.';
                    showFeedback(this.quickdropHomeErrorText, 'error');
                } finally {
                    this.isSendingQuickdropHomeText = false;
                }
            },
        };
    };

    function launchCard(card) {
        var href = card.dataset.launchHref || (card.dataset.productId ? '/products/' + card.dataset.productId + '/' : '');
        if (!href) {
            return;
        }
        if (card.dataset.launchExternal === 'true') {
            window.open(href, '_blank', 'noopener');
            return;
        }
        window.location.href = href;
    }

    function initHomeV2Interactions() {
        var config = getHomeV2Config();
        var favoriteIds = new Set();
        var favoriteData = parseJsonScript('home-favorite-ids-data', []);
        if (Array.isArray(favoriteData)) {
            favoriteData.forEach(function (value) {
                var parsed = parseInt(value, 10);
                if (!Number.isNaN(parsed)) {
                    favoriteIds.add(parsed);
                }
            });
        }

        function updateFavoriteButtonState(button, isFavorite) {
            if (!button) {
                return;
            }
            button.setAttribute('aria-pressed', isFavorite ? 'true' : 'false');
            button.classList.toggle('border-amber-300', isFavorite);
            button.classList.toggle('text-amber-500', isFavorite);
            button.classList.toggle('bg-amber-50', isFavorite);
            button.classList.toggle('border-slate-200', !isFavorite);
            button.classList.toggle('text-slate-300', !isFavorite);
            button.classList.toggle('bg-white', !isFavorite);
            button.title = isFavorite ? '즐겨찾기 해제' : '즐겨찾기';
        }

        function syncFavoriteButtons() {
            document.querySelectorAll('[data-favorite-toggle="true"]').forEach(function (button) {
                var pid = parseInt(button.dataset.productId || '', 10);
                var isFavorite = !Number.isNaN(pid) && favoriteIds.has(pid);
                updateFavoriteButtonState(button, isFavorite);
            });
        }

        document.querySelectorAll('.product-card').forEach(function (card) {
            card.addEventListener('click', function (event) {
                if (event.target.closest('[data-favorite-toggle="true"]')) {
                    return;
                }
                launchCard(card);
            });
            card.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    launchCard(card);
                }
            });
        });

        document.querySelectorAll('[data-favorite-toggle="true"]').forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();

                var pid = parseInt(this.dataset.productId || '', 10);
                if (Number.isNaN(pid) || !config.toggleFavoriteUrl) {
                    return;
                }

                var csrfToken = getCsrfToken();
                if (!csrfToken) {
                    showFeedback('보안 토큰을 확인할 수 없습니다. 새로고침 후 다시 시도해 주세요.', 'error');
                    return;
                }

                fetch(config.toggleFavoriteUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({ product_id: pid }),
                })
                    .then(function (response) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            if (!response.ok || payload.status !== 'ok') {
                                throw new Error(payload.error || '즐겨찾기 처리에 실패했습니다.');
                            }
                            return payload;
                        });
                    })
                    .then(function (payload) {
                        if (payload.is_favorite) {
                            favoriteIds.add(pid);
                            showFeedback('즐겨찾기에 추가했습니다.', 'success');
                        } else {
                            favoriteIds.delete(pid);
                            showFeedback('즐겨찾기에서 제거했습니다.', 'success');
                        }
                        syncFavoriteButtons();
                    })
                    .catch(function (error) {
                        showFeedback(error.message || '즐겨찾기 처리 중 오류가 발생했습니다.', 'error');
                    });
            });
        });

        document.addEventListener('click', function (event) {
            var element = event.target.closest('[data-track]');
            if (!element) {
                return;
            }
            var productId = element.dataset.productId || (element.closest('[data-product-id]') || {}).dataset?.productId;
            if (!productId || !config.trackUsageUrl) {
                return;
            }
            var token = getCsrfToken();
            if (!token) {
                return;
            }
            var sourceMap = {
                quick_action: 'home_quick',
                mini_card: 'home_section',
                mini_app_open: 'home_mini',
                game_card: 'home_game',
                game_banner: 'home_game',
                section_more_toggle: 'home_section',
            };
            fetch(config.trackUsageUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': token,
                },
                body: JSON.stringify({
                    product_id: parseInt(productId, 10),
                    action: 'launch',
                    source: sourceMap[element.dataset.track] || 'other',
                }),
            })
                .then(function (response) {
                    if (!response.ok) {
                        showFeedback('사용 기록 저장에 실패했습니다.', 'error');
                    }
                })
                .catch(function () {
                    showFeedback('사용 기록 저장 중 네트워크 오류가 발생했습니다.', 'error');
                });
        });

        syncFavoriteButtons();
    }

    document.addEventListener('DOMContentLoaded', initHomeV2Interactions);
})();
