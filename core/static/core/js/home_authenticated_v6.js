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

    function getHomeFrontendConfig() {
        return parseJsonScript('home-frontend-config', {}) || {};
    }

    function getCsrfToken() {
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        if (field && field.value) {
            return field.value;
        }
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function ensureFallbackToastRoot() {
        var root = document.getElementById('home-feedback-fallback-root');
        if (root) {
            return root;
        }
        root = document.createElement('div');
        root.id = 'home-feedback-fallback-root';
        root.style.position = 'fixed';
        root.style.right = '1rem';
        root.style.bottom = '1rem';
        root.style.zIndex = '9999';
        root.style.display = 'grid';
        root.style.gap = '0.5rem';
        document.body.appendChild(root);
        return root;
    }

    function renderFallbackToast(message, type) {
        var root = ensureFallbackToastRoot();
        var toast = document.createElement('div');
        var tone = (type || 'info') === 'error'
            ? { border: '#fecaca', background: '#fff1f2', color: '#9f1239' }
            : { border: '#cbd5e1', background: '#ffffff', color: '#0f172a' };
        toast.textContent = message;
        toast.style.maxWidth = '22rem';
        toast.style.padding = '0.8rem 0.95rem';
        toast.style.borderRadius = '0.9rem';
        toast.style.border = '1px solid ' + tone.border;
        toast.style.background = tone.background;
        toast.style.color = tone.color;
        toast.style.fontSize = '0.9rem';
        toast.style.fontWeight = '700';
        toast.style.boxShadow = '0 14px 30px rgba(15, 23, 42, 0.12)';
        root.appendChild(toast);
        window.setTimeout(function () {
            toast.remove();
        }, 3200);
    }

    function showFeedback(message, type) {
        if (window.showToast) {
            window.showToast(message, type || 'info');
            return;
        }
        renderFallbackToast(message, type || 'info');
    }

    function getHtmxSource(event) {
        if (!event || !event.detail) {
            return null;
        }
        if (event.detail.requestConfig && event.detail.requestConfig.elt) {
            return event.detail.requestConfig.elt;
        }
        return event.target || null;
    }

    function getInlineErrorBox(source) {
        if (!source || !source.dataset || !source.dataset.inlineErrorTarget) {
            return null;
        }
        return document.querySelector(source.dataset.inlineErrorTarget);
    }

    function clearInlineError(source) {
        var box = getInlineErrorBox(source);
        if (!box) {
            return;
        }
        box.hidden = true;
        box.classList.add('hidden');
        var message = box.querySelector('[data-inline-error-message]');
        if (message) {
            message.textContent = '';
        }
        var retry = box.querySelector('[data-inline-error-retry]');
        if (retry) {
            retry.onclick = null;
        }
    }

    function extractResponseMessage(event, fallback) {
        var xhr = event && event.detail ? event.detail.xhr : null;
        if (!xhr) {
            return fallback;
        }
        var responseText = String(xhr.responseText || '').trim();
        if (!responseText) {
            return fallback;
        }
        if (responseText.charAt(0) === '{') {
            try {
                var parsed = JSON.parse(responseText);
                if (parsed && parsed.error) {
                    return String(parsed.error);
                }
            } catch (error) {
                // Ignore JSON parse errors and keep trying plain text extraction.
            }
        }
        try {
            var doc = new DOMParser().parseFromString(responseText, 'text/html');
            var text = doc && doc.body ? String(doc.body.textContent || '').replace(/\s+/g, ' ').trim() : '';
            return text || fallback;
        } catch (error) {
            return responseText || fallback;
        }
    }

    function renderInlineError(source, message) {
        var box = getInlineErrorBox(source);
        if (!box) {
            return;
        }
        var messageNode = box.querySelector('[data-inline-error-message]');
        if (messageNode) {
            messageNode.textContent = message;
        }
        var retry = box.querySelector('[data-inline-error-retry]');
        if (retry) {
            retry.onclick = function () {
                if (source.tagName === 'FORM' && typeof source.requestSubmit === 'function') {
                    source.requestSubmit();
                    return;
                }
                if (typeof source.click === 'function') {
                    source.click();
                }
            };
        }
        box.hidden = false;
        box.classList.remove('hidden');
    }

    function escapeRegExp(value) {
        return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function trimLine(value) {
        return String(value || '')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function compactLines(value) {
        return String(value || '')
            .split(/\n+/)
            .map(trimLine)
            .filter(Boolean);
    }

    function compactSentences(value) {
        return String(value || '')
            .split(/[\n.!?]+/)
            .map(trimLine)
            .filter(Boolean);
    }

    function firstMatch(value, pattern) {
        var match = String(value || '').match(pattern);
        return match ? trimLine(match[0]) : '';
    }

    function normalizeIdList(values) {
        if (!Array.isArray(values)) {
            return [];
        }
        return values
            .map(function (value) {
                return parseInt(value, 10);
            })
            .filter(function (value, index, array) {
                return !Number.isNaN(value) && array.indexOf(value) === index;
            });
    }

    function providerLabel(provider) {
        var normalized = String(provider || '').trim().toLowerCase();
        if (normalized === 'deepseek') {
            return 'DeepSeek';
        }
        if (normalized === 'openclaw' || normalized === 'local') {
            return 'OpenClaw';
        }
        return normalized ? normalized : '';
    }

    function initHomeV6DesktopRail() {
        var rail = document.querySelector('[data-home-v6-nav-rail="true"]');
        if (!rail || rail.dataset.jsBound === 'true') {
            return;
        }

        rail.dataset.jsBound = 'true';

        var groups = Array.prototype.slice.call(rail.querySelectorAll('[data-home-v6-nav-section]'));
        if (!groups.length) {
            return;
        }

        var activeSectionKey = '';

        function getSectionKey(group) {
            return group && group.dataset ? String(group.dataset.homeV6NavSection || '') : '';
        }

        function setPanelState(panel, isOpen, displayValue) {
            if (!panel) {
                return;
            }
            panel.removeAttribute('x-cloak');
            panel.hidden = !isOpen;
            panel.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
            panel.style.display = isOpen ? (displayValue || 'block') : 'none';
        }

        function syncRailState(nextKey) {
            activeSectionKey = String(nextKey || '');
            groups.forEach(function (group) {
                var key = getSectionKey(group);
                var isActive = key && key === activeSectionKey;
                var button = group.querySelector('.home-v6-nav-rail-button:not(.home-v6-nav-rail-button--direct)');
                var flyout = group.querySelector('[data-home-v6-nav-flyout]');
                var tooltip = group.querySelector('[data-home-v6-nav-tooltip]');
                group.classList.toggle('is-open', isActive);
                if (button) {
                    button.setAttribute('aria-expanded', isActive ? 'true' : 'false');
                }
                setPanelState(flyout, isActive, 'block');
                setPanelState(tooltip, isActive, 'block');
            });
        }

        syncRailState('');

        groups.forEach(function (group) {
            var key = getSectionKey(group);
            var button = group.querySelector('.home-v6-nav-rail-button:not(.home-v6-nav-rail-button--direct)');
            var directLink = group.querySelector('.home-v6-nav-rail-button--direct');

            if (!key) {
                return;
            }

            group.addEventListener('mouseenter', function () {
                syncRailState(key);
            });

            group.addEventListener('mouseleave', function () {
                syncRailState('');
            });

            group.addEventListener('focusin', function () {
                syncRailState(key);
            });

            group.addEventListener('focusout', function (event) {
                if (!group.contains(event.relatedTarget)) {
                    syncRailState('');
                }
            });

            if (button) {
                button.addEventListener('click', function (event) {
                    event.preventDefault();
                    syncRailState(activeSectionKey === key ? '' : key);
                });
            }

            if (directLink) {
                directLink.addEventListener('click', function () {
                    syncRailState('');
                });
            }
        });

        document.addEventListener('click', function (event) {
            if (!rail.contains(event.target)) {
                syncRailState('');
            }
        });
    }

    function appendQueryParams(href, params) {
        var baseHref = trimLine(href);
        if (!baseHref) {
            return '';
        }
        try {
            var url = new URL(baseHref, window.location.origin);
            Object.keys(params || {}).forEach(function (key) {
                var value = trimLine(params[key]);
                if (value) {
                    url.searchParams.set(key, value);
                }
            });
            if (url.origin === window.location.origin) {
                return url.pathname + url.search + url.hash;
            }
            return url.toString();
        } catch (error) {
            return baseHref;
        }
    }

    window.homeV6Shell = function () {
        var frontendConfig = getHomeFrontendConfig();
        var workspaceConfig = parseJsonScript('home-v7-agent-workspace', {}) || {};
        return {
            openSection: '',
            menuSheetOpen: false,
            quickdropHomeDraftText: '',
            quickdropHomeErrorText: '',
            quickdropHomeLastSentText: '',
            isSendingQuickdropHomeText: false,
            workspaceInput: '',
            agentModeMenuOpen: false,
            activeModeKey: workspaceConfig.initial_mode || '',
            agentModes: Array.isArray(workspaceConfig.modes) ? workspaceConfig.modes : [],
            agentPreview: {
                badge: '',
                title: '',
                summary: '',
                sections: [],
                note: '',
                confirmHref: '',
                confirmLabel: '',
            },
            agentPreviewMeta: {
                source: '',
                provider: '',
                model: '',
                providerLabel: '',
            },
            agentExecution: null,
            agentExecutionDraft: {},
            agentExecutionFieldErrors: {},
            isAgentLoading: false,
            isAgentExecuting: false,
            favoriteIds: normalizeIdList(frontendConfig.favoriteProductIds || parseJsonScript('home-favorite-ids-data', [])),

            init: function () {
                frontendConfig = getHomeFrontendConfig();
                workspaceConfig = parseJsonScript('home-v7-agent-workspace', workspaceConfig) || {};
                this.agentModes = Array.isArray(workspaceConfig.modes) ? workspaceConfig.modes : this.agentModes;
                this.favoriteIds = normalizeIdList(frontendConfig.favoriteProductIds || parseJsonScript('home-favorite-ids-data', []));
                if (!this.activeModeKey && this.agentModes.length) {
                    this.activeModeKey = this.agentModes[0].key;
                }
                this.showIdlePreview();
                var self = this;
                window.addEventListener('home-v6:favorites-updated', function (event) {
                    self.favoriteIds = normalizeIdList(event && event.detail ? event.detail.productIds : []);
                });
            },

            get activeMode() {
                return this.agentModes.find(function (mode) {
                    return mode.key === this.activeModeKey;
                }, this) || this.agentModes[0] || {};
            },

            focusQuickdropHomeDraftInput: function (form) {
                var scopedInput = form && typeof form.querySelector === 'function'
                    ? form.querySelector('textarea[name="text"]')
                    : document.querySelector(
                        '[data-home-v6-quickdrop-form="true"] textarea[name="text"], ' +
                        '[data-home-v6-mobile-quickdrop-form="true"] textarea[name="text"]'
                    );
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
                var submitButton = form ? form.querySelector('button[type="submit"]') : null;
                var successMessage = submitButton && submitButton.dataset && submitButton.dataset.successMessage
                    ? String(submitButton.dataset.successMessage)
                    : '바로전송으로 보냈어요.';
                var actionName = submitButton && submitButton.dataset && submitButton.dataset.errorAction
                    ? String(submitButton.dataset.errorAction)
                    : '바로전송';
                if (!draftText) {
                    this.quickdropHomeErrorText = '보낼 글을 먼저 입력해 주세요.';
                    showFeedback(this.quickdropHomeErrorText, 'info');
                    this.focusQuickdropHomeDraftInput(form);
                    return;
                }
                if (!action) {
                    this.quickdropHomeErrorText = actionName + ' 경로를 찾지 못했습니다.';
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
                        throw new Error(payload.error || (actionName + '에 실패했습니다.'));
                    }
                    var session = payload && payload.session ? payload.session : {};
                    this.quickdropHomeLastSentText = String(session.current_text || draftText).trim();
                    this.quickdropHomeDraftText = '';
                    if (form && typeof form.reset === 'function') {
                        form.reset();
                    }
                    showFeedback(successMessage, 'success');
                    this.focusQuickdropHomeDraftInput(form);
                } catch (error) {
                    this.quickdropHomeErrorText = error && error.message ? error.message : (actionName + '에 실패했습니다.');
                    showFeedback(this.quickdropHomeErrorText, 'error');
                } finally {
                    this.isSendingQuickdropHomeText = false;
                }
            },

            focusWorkspace: function () {
                var textarea = document.querySelector('[data-home-v6-agent-input="true"]');
                if (textarea && typeof textarea.focus === 'function') {
                    textarea.focus();
                }
            },

            normalizeModeAlias: function (value) {
                return String(value || '')
                    .replace(/\s+/g, '')
                    .toLowerCase();
            },

            modeAliases: function (mode) {
                var seen = new Set();
                return [mode.label, mode.service_key]
                    .concat(Array.isArray(mode.aliases) ? mode.aliases : [])
                    .map(trimLine)
                    .filter(function (alias) {
                        var normalized = this.normalizeModeAlias(alias);
                        if (!normalized || seen.has(normalized)) {
                            return false;
                        }
                        seen.add(normalized);
                        return true;
                    }, this);
            },

            parseModeCommand: function (value) {
                var text = trimLine(value);
                if (!text) {
                    return { modeKey: '', remainder: '' };
                }
                var bestMatch = null;
                this.agentModes.forEach(function (mode) {
                    this.modeAliases(mode).forEach(function (alias) {
                        var aliasText = trimLine(alias);
                        if (!aliasText) {
                            return;
                        }
                        var exactMatch = this.normalizeModeAlias(text) === this.normalizeModeAlias(aliasText);
                        if (exactMatch) {
                            if (!bestMatch || aliasText.length > bestMatch.score) {
                                bestMatch = {
                                    modeKey: mode.key,
                                    remainder: '',
                                    score: aliasText.length,
                                };
                            }
                            return;
                        }
                        var aliasPattern = new RegExp(
                            '^' + escapeRegExp(aliasText).replace(/\s+/g, '\\s*') + '(?:\\s*[:>\\-]\\s*|\\s+)',
                            'i'
                        );
                        if (!aliasPattern.test(text)) {
                            return;
                        }
                        var remainder = trimLine(text.replace(aliasPattern, ''));
                        if (!bestMatch || aliasText.length > bestMatch.score) {
                            bestMatch = {
                                modeKey: mode.key,
                                remainder: remainder,
                                score: aliasText.length,
                            };
                        }
                    }, this);
                }, this);
                return bestMatch || { modeKey: '', remainder: text };
            },

            isFavorite: function (productId) {
                var normalized = parseInt(productId, 10);
                return !Number.isNaN(normalized) && this.favoriteIds.indexOf(normalized) !== -1;
            },

            isAgentModeFavorite: function () {
                return this.isFavorite(this.activeMode.product_id);
            },

            setFavoriteState: function (productId, isFavorite) {
                var normalized = parseInt(productId, 10);
                if (Number.isNaN(normalized)) {
                    return;
                }
                var nextIds = this.favoriteIds.filter(function (value) {
                    return value !== normalized;
                });
                if (isFavorite) {
                    nextIds.push(normalized);
                }
                this.favoriteIds = nextIds;
                window.dispatchEvent(new CustomEvent('home-v6:favorites-updated', {
                    detail: { productIds: nextIds.slice() },
                }));
            },

            previewProviderStatus: function (payload) {
                var name = providerLabel(payload && payload.provider ? payload.provider : '');
                return {
                    source: payload && payload.provider ? 'ai' : '',
                    provider: payload && payload.provider ? payload.provider : '',
                    model: payload && payload.model ? payload.model : '',
                    providerLabel: name ? name + ' 미리보기' : '',
                };
            },

            buildModeContinueHref: function (mode) {
                var targetMode = mode || this.activeMode || {};
                var href = trimLine(targetMode.after_action_href || targetMode.service_href || '');
                if (!href) {
                    return '';
                }
                if (targetMode.key === 'notice') {
                    return appendQueryParams(href, {
                        keywords: this.workspaceInput,
                    });
                }
                if (targetMode.key === 'schedule') {
                    return appendQueryParams(href, {
                        date: String(this.agentExecutionDraft.start_time || '').slice(0, 10),
                    });
                }
                if (targetMode.key === 'reservation') {
                    return appendQueryParams(href, {
                        date: this.agentExecutionDraft.date,
                    });
                }
                return href;
            },

            buildPreviewSkeleton: function (overrides) {
                var mode = this.activeMode || {};
                return Object.assign({
                    badge: mode.label || '미리보기',
                    title: '',
                    summary: '',
                    sections: [],
                    note: '',
                    confirmHref: this.buildModeContinueHref(mode),
                    confirmLabel: mode.after_action_label || mode.confirm_label || '',
                }, overrides || {});
            },

            normalizePreview: function (preview, meta) {
                var base = this.buildPreviewSkeleton();
                var payload = preview && typeof preview === 'object' ? preview : {};
                var sections = Array.isArray(payload.sections) ? payload.sections : [];
                var normalizedSections = sections
                    .map(function (section) {
                        if (!section || typeof section !== 'object') {
                            return null;
                        }
                        var title = trimLine(section.title);
                        var items = Array.isArray(section.items)
                            ? section.items.map(trimLine).filter(Boolean).slice(0, 4)
                            : [];
                        if (!title || !items.length) {
                            return null;
                        }
                        return {
                            title: title,
                            items: items,
                        };
                    })
                    .filter(Boolean);
                var note = trimLine(payload.note || base.note);
                if (meta && meta.source === 'fallback' && note) {
                    note = note + ' 규칙형 미리보기로 보여주고 있습니다.';
                }
                return Object.assign({}, base, {
                    badge: trimLine(payload.badge || base.badge),
                    title: trimLine(payload.title || base.title),
                    summary: trimLine(payload.summary || base.summary),
                    sections: normalizedSections.length ? normalizedSections : base.sections,
                    note: note,
                    confirmHref: trimLine(payload.confirmHref || base.confirmHref),
                    confirmLabel: trimLine(payload.confirmLabel || base.confirmLabel),
                });
            },

            previewResultLines: function () {
                var preview = this.agentPreview && typeof this.agentPreview === 'object' ? this.agentPreview : {};
                var sections = Array.isArray(preview.sections) ? preview.sections : [];
                var lines = [];
                var seen = new Set();

                function pushLine(value) {
                    var line = trimLine(value);
                    if (!line || seen.has(line)) {
                        return;
                    }
                    seen.add(line);
                    lines.push(line);
                }

                if (sections[0] && Array.isArray(sections[0].items)) {
                    sections[0].items.forEach(pushLine);
                }
                if (!lines.length) {
                    pushLine(preview.summary);
                }
                return lines.slice(0, this.activeModeKey === 'notice' ? 6 : 8);
            },

            clonePayload: function (value) {
                try {
                    return JSON.parse(JSON.stringify(value || {}));
                } catch (error) {
                    return {};
                }
            },

            buildIdempotencyKey: function (prefix, value) {
                var text = String(value || '');
                var hash = 0;
                for (var index = 0; index < text.length; index += 1) {
                    hash = ((hash << 5) - hash) + text.charCodeAt(index);
                    hash |= 0;
                }
                return [prefix || 'home-agent', Math.abs(hash), text.length].join(':');
            },

            clearExecution: function () {
                this.agentExecution = null;
                this.agentExecutionDraft = {};
                this.agentExecutionFieldErrors = {};
            },

            normalizeFieldErrors: function (fieldErrors) {
                var source = fieldErrors && typeof fieldErrors === 'object' ? fieldErrors : {};
                var normalized = {};
                Object.keys(source).forEach(function (fieldName) {
                    var message = trimLine(source[fieldName]);
                    if (message) {
                        normalized[String(fieldName)] = message;
                    }
                });
                return normalized;
            },

            setExecutionFieldErrors: function (fieldErrors) {
                this.agentExecutionFieldErrors = this.normalizeFieldErrors(fieldErrors);
            },

            executionFieldError: function (fieldName) {
                return trimLine(this.agentExecutionFieldErrors && this.agentExecutionFieldErrors[fieldName]);
            },

            clearExecutionFieldError: function (fieldName) {
                if (!this.agentExecutionFieldErrors || !this.agentExecutionFieldErrors[fieldName]) {
                    return;
                }
                var nextErrors = Object.assign({}, this.agentExecutionFieldErrors);
                delete nextErrors[fieldName];
                this.agentExecutionFieldErrors = nextErrors;
            },

            firstExecutionErrorField: function () {
                var fieldOrder = ['question', 'incident_type', 'legal_goal', 'scene', 'counterpart'];
                for (var index = 0; index < fieldOrder.length; index += 1) {
                    if (this.executionFieldError(fieldOrder[index])) {
                        return fieldOrder[index];
                    }
                }
                return '';
            },

            focusAgentExecutionField: function (fieldName) {
                var target = fieldName
                    ? document.querySelector('[data-home-v6-agent-field="' + String(fieldName) + '"]')
                    : null;
                if (!target) {
                    return;
                }
                if (typeof target.scrollIntoView === 'function') {
                    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
                if (typeof target.focus === 'function') {
                    target.focus();
                }
            },

            normalizeExecution: function (execution) {
                var payload = execution && typeof execution === 'object' ? execution : {};
                var kind = trimLine(payload.kind);
                if (!kind) {
                    return null;
                }
                return {
                    kind: kind,
                    title: trimLine(payload.title),
                    submitLabel: trimLine(payload.submit_label || '저장'),
                    draft: payload.draft && typeof payload.draft === 'object' ? this.clonePayload(payload.draft) : {},
                    choices: Array.isArray(payload.choices) ? payload.choices.map(function (choice) {
                        if (!choice || typeof choice !== 'object') {
                            return null;
                        }
                        return {
                            id: String(choice.id || ''),
                            label: trimLine(choice.label),
                            values: choice.values && typeof choice.values === 'object' ? this.clonePayload(choice.values) : {},
                        };
                    }, this).filter(Boolean) : [],
                    schoolOptions: Array.isArray(payload.school_options) ? payload.school_options.map(function (school) {
                        if (!school || typeof school !== 'object') {
                            return null;
                        }
                        return {
                            slug: trimLine(school.slug),
                            name: trimLine(school.name),
                            reservationUrl: trimLine(school.reservation_url),
                            rooms: Array.isArray(school.rooms) ? school.rooms.map(function (room) {
                                return {
                                    id: String(room && room.id ? room.id : ''),
                                    name: trimLine(room && room.name ? room.name : ''),
                                };
                            }).filter(function (room) {
                                return room.id && room.name;
                            }) : [],
                            periods: Array.isArray(school.periods) ? school.periods.map(function (period) {
                                return {
                                    id: String(period && period.id ? period.id : ''),
                                    label: trimLine(period && period.label ? period.label : ''),
                                    displayLabel: trimLine(period && period.display_label ? period.display_label : ''),
                                };
                            }).filter(function (period) {
                                return period.id;
                            }) : [],
                        };
                    }).filter(Boolean) : [],
                    incidentOptions: Array.isArray(payload.incident_options) ? payload.incident_options.map(function (item) {
                        return {
                            value: trimLine(item && item.value ? item.value : ''),
                            label: trimLine(item && item.label ? item.label : ''),
                            requires: trimLine(item && item.requires ? item.requires : ''),
                        };
                    }).filter(function (item) {
                        return item.value && item.label;
                    }) : [],
                    goalOptions: Array.isArray(payload.goal_options) ? payload.goal_options.map(function (item) {
                        return {
                            value: trimLine(item && item.value ? item.value : ''),
                            label: trimLine(item && item.label ? item.label : ''),
                        };
                    }).filter(function (item) {
                        return item.value && item.label;
                    }) : [],
                    sceneOptions: Array.isArray(payload.scene_options) ? payload.scene_options.map(function (item) {
                        return {
                            value: trimLine(item && item.value ? item.value : ''),
                            label: trimLine(item && item.label ? item.label : ''),
                        };
                    }).filter(function (item) {
                        return item.value && item.label;
                    }) : [],
                    counterpartOptions: Array.isArray(payload.counterpart_options) ? payload.counterpart_options.map(function (item) {
                        return {
                            value: trimLine(item && item.value ? item.value : ''),
                            label: trimLine(item && item.label ? item.label : ''),
                        };
                    }).filter(function (item) {
                        return item.value && item.label;
                    }) : [],
                    warnings: Array.isArray(payload.warnings) ? payload.warnings.map(trimLine).filter(Boolean).slice(0, 3) : [],
                };
            },

            setExecution: function (execution) {
                var normalized = this.normalizeExecution(execution);
                if (!normalized) {
                    this.clearExecution();
                    return;
                }
                this.agentExecution = normalized;
                this.agentExecutionDraft = this.clonePayload(normalized.draft);
                this.agentExecutionFieldErrors = {};
                if (normalized.kind === 'schedule' && normalized.choices.length) {
                    this.selectScheduleExecutionChoice(
                        this.agentExecutionDraft.choice_id || normalized.choices[0].id,
                        normalized
                    );
                    return;
                }
                this.normalizeExecutionDraft();
            },

            selectScheduleExecutionChoice: function (choiceId, executionOverride) {
                var execution = executionOverride || this.agentExecution;
                if (!execution || execution.kind !== 'schedule') {
                    return;
                }
                if (executionOverride) {
                    this.agentExecution = executionOverride;
                }
                var targetId = String(choiceId || '');
                var choice = execution.choices.find(function (item) {
                    return String(item.id) === targetId;
                }) || execution.choices[0];
                if (!choice) {
                    this.agentExecutionDraft = {};
                    return;
                }
                this.agentExecutionDraft = Object.assign({}, this.clonePayload(choice.values), {
                    choice_id: String(choice.id),
                });
            },

            reservationSchoolOptions: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'reservation') {
                    return [];
                }
                return Array.isArray(this.agentExecution.schoolOptions) ? this.agentExecution.schoolOptions : [];
            },

            selectedReservationSchool: function () {
                var schoolSlug = trimLine(this.agentExecutionDraft.school_slug || '');
                var options = this.reservationSchoolOptions();
                return options.find(function (school) {
                    return school.slug === schoolSlug;
                }) || options[0] || null;
            },

            reservationRoomOptions: function () {
                var school = this.selectedReservationSchool();
                return school && Array.isArray(school.rooms) ? school.rooms : [];
            },

            reservationPeriodOptions: function () {
                var school = this.selectedReservationSchool();
                return school && Array.isArray(school.periods) ? school.periods : [];
            },

            teacherLawIncidentOptions: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'teacher-law') {
                    return [];
                }
                return Array.isArray(this.agentExecution.incidentOptions) ? this.agentExecution.incidentOptions : [];
            },

            teacherLawGoalOptions: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'teacher-law') {
                    return [];
                }
                return Array.isArray(this.agentExecution.goalOptions) ? this.agentExecution.goalOptions : [];
            },

            teacherLawSceneOptions: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'teacher-law') {
                    return [];
                }
                return Array.isArray(this.agentExecution.sceneOptions) ? this.agentExecution.sceneOptions : [];
            },

            teacherLawCounterpartOptions: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'teacher-law') {
                    return [];
                }
                return Array.isArray(this.agentExecution.counterpartOptions) ? this.agentExecution.counterpartOptions : [];
            },

            selectedTeacherLawIncident: function () {
                var incidentType = trimLine(this.agentExecutionDraft.incident_type || '');
                return this.teacherLawIncidentOptions().find(function (item) {
                    return item.value === incidentType;
                }) || null;
            },

            teacherLawNeedsScene: function () {
                var incident = this.selectedTeacherLawIncident();
                return Boolean(incident && incident.requires === 'scene');
            },

            teacherLawNeedsCounterpart: function () {
                var incident = this.selectedTeacherLawIncident();
                return Boolean(incident && incident.requires === 'counterpart');
            },

            validateExecutionDraft: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'teacher-law') {
                    return {};
                }
                var errors = {};
                if (!trimLine(this.agentExecutionDraft.question || '')) {
                    errors.question = '질문을 입력해 주세요.';
                }
                if (!trimLine(this.agentExecutionDraft.incident_type || '')) {
                    errors.incident_type = '사건 유형을 먼저 골라 주세요.';
                }
                if (!trimLine(this.agentExecutionDraft.legal_goal || '')) {
                    errors.legal_goal = '궁금한 것을 먼저 골라 주세요.';
                }
                if (this.teacherLawNeedsScene() && !trimLine(this.agentExecutionDraft.scene || '')) {
                    errors.scene = '장면을 하나 골라 주세요.';
                }
                if (this.teacherLawNeedsCounterpart() && !trimLine(this.agentExecutionDraft.counterpart || '')) {
                    errors.counterpart = '상대를 하나 골라 주세요.';
                }
                return errors;
            },

            normalizeExecutionDraft: function () {
                if (!this.agentExecution) {
                    return;
                }
                if (this.agentExecution.kind === 'teacher-law') {
                    if (!this.teacherLawNeedsScene()) {
                        this.agentExecutionDraft.scene = '';
                    }
                    if (!this.teacherLawNeedsCounterpart()) {
                        this.agentExecutionDraft.counterpart = '';
                    }
                    return;
                }
                if (this.agentExecution.kind !== 'reservation') {
                    return;
                }
                var schoolOptions = this.reservationSchoolOptions();
                var school = this.selectedReservationSchool() || schoolOptions[0] || null;
                if (school && !trimLine(this.agentExecutionDraft.school_slug)) {
                    this.agentExecutionDraft.school_slug = school.slug;
                }
                if (!school) {
                    return;
                }

                var roomId = String(this.agentExecutionDraft.room_id || '');
                var roomExists = this.reservationRoomOptions().some(function (room) {
                    return String(room.id) === roomId;
                });
                if (!roomExists) {
                    this.agentExecutionDraft.room_id = this.reservationRoomOptions().length === 1
                        ? String(this.reservationRoomOptions()[0].id)
                        : '';
                }

                var periodId = String(this.agentExecutionDraft.period || '');
                var periodExists = this.reservationPeriodOptions().some(function (period) {
                    return String(period.id) === periodId;
                });
                if (!periodExists) {
                    this.agentExecutionDraft.period = '';
                }

                var ownerType = trimLine(this.agentExecutionDraft.owner_type || '');
                if (ownerType !== 'class' && ownerType !== 'custom') {
                    ownerType = trimLine(this.agentExecutionDraft.grade || '') && trimLine(this.agentExecutionDraft.class_no || '')
                        ? 'class'
                        : 'custom';
                }
                this.agentExecutionDraft.owner_type = ownerType;
                if (ownerType === 'class') {
                    this.agentExecutionDraft.target_label = '';
                    return;
                }
                this.agentExecutionDraft.grade = '';
                this.agentExecutionDraft.class_no = '';
            },

            executeAgentService: async function () {
                if (!this.agentExecution) {
                    return;
                }
                this.normalizeExecutionDraft();
                var localFieldErrors = this.validateExecutionDraft();
                if (Object.keys(localFieldErrors).length) {
                    this.setExecutionFieldErrors(localFieldErrors);
                    showFeedback(localFieldErrors[this.firstExecutionErrorField()] || '입력을 먼저 확인해 주세요.', 'error');
                    this.focusAgentExecutionField(this.firstExecutionErrorField());
                    return;
                }
                this.agentExecutionFieldErrors = {};
                var runtime = workspaceConfig.agent_runtime || {};
                var csrfToken = getCsrfToken();
                if (!runtime.execute_url || !csrfToken) {
                    showFeedback('저장 연결 정보가 없습니다.', 'error');
                    return;
                }
                this.isAgentExecuting = true;
                try {
                    var response = await fetch(runtime.execute_url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: JSON.stringify({
                            mode_key: this.activeModeKey,
                            data: this.agentExecutionDraft,
                        }),
                    });
                    var payload = {};
                    try {
                        payload = await response.json();
                    } catch (jsonError) {
                        payload = {};
                    }
                    if (!response.ok || payload.status !== 'ok') {
                        this.setExecutionFieldErrors(payload.field_errors);
                        this.focusAgentExecutionField(this.firstExecutionErrorField());
                        throw new Error(payload.error || '저장하지 못했습니다.');
                    }
                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: payload.provider || this.activeMode.service_key || '',
                        model: payload.model || '',
                        providerLabel: '',
                    };
                    this.agentPreview = this.normalizePreview(payload.preview, this.agentPreviewMeta);
                    this.clearExecution();
                    showFeedback(payload.message || '저장했습니다.', 'success');
                } catch (error) {
                    showFeedback(error && error.message ? error.message : '저장하지 못했습니다.', 'error');
                } finally {
                    this.isAgentExecuting = false;
                }
            },

            buildIdlePreview: function () {
                return this.buildPreviewSkeleton({
                    badge: '',
                    title: '',
                    summary: '',
                    sections: [],
                    note: '',
                    confirmHref: '',
                    confirmLabel: '',
                });
            },

            showIdlePreview: function () {
                this.agentPreview = this.buildIdlePreview();
                this.agentPreviewMeta = {
                    source: '',
                    provider: '',
                    model: '',
                    providerLabel: '',
                };
                this.clearExecution();
            },

            selectAgentMode: function (modeKey) {
                this.activeModeKey = modeKey;
                this.agentModeMenuOpen = false;
                if (trimLine(this.workspaceInput)) {
                    this.runAgentPreview();
                    return;
                }
                this.showIdlePreview();
            },

            useExample: function (text) {
                this.workspaceInput = trimLine(text);
                this.runAgentPreview();
            },

            buildPreviewRequestPayload: function (text) {
                return {
                    mode_key: this.activeModeKey,
                    text: text,
                    selected_date_label: workspaceConfig.selected_date_label || '',
                    provider: workspaceConfig.agent_runtime && workspaceConfig.agent_runtime.provider
                        ? workspaceConfig.agent_runtime.provider
                        : '',
                    context: {
                        service_key: this.activeMode.service_key || '',
                        workflow_keys: Array.isArray(this.activeMode.workflow_keys) ? this.activeMode.workflow_keys : [],
                        tacit_rule_keys: Array.isArray(this.activeMode.tacit_rule_keys) ? this.activeMode.tacit_rule_keys : [],
                        context_questions: Array.isArray(workspaceConfig.context_questions) ? workspaceConfig.context_questions : [],
                        signal_sources: Array.isArray(workspaceConfig.signal_sources) ? workspaceConfig.signal_sources : [],
                    },
                };
            },

            buildLocalPreview: function (text) {
                if (this.activeModeKey === 'quickdrop') {
                    return this.buildQuickdropPreview(text);
                }
                if (this.activeModeKey === 'tts') {
                    return this.buildTtsPreview(text);
                }
                if (this.activeModeKey === 'schedule') {
                    return this.buildSchedulePreview(text);
                }
                if (this.activeModeKey === 'teacher-law') {
                    return this.buildTeacherLawPreview(text);
                }
                if (this.activeModeKey === 'reservation') {
                    return this.buildReservationPreview(text);
                }
                if (this.activeModeKey === 'pdf') {
                    return this.buildPdfPreview(text);
                }
                if (this.activeModeKey === 'message-save') {
                    return this.buildMessageSavePreview(text);
                }
                return this.buildNoticePreview(text);
            },

            runAgentPreview: async function () {
                var text = trimLine(this.workspaceInput);
                var previewStrategy = String(this.activeMode.preview_strategy || 'llm').toLowerCase();
                if (!text) {
                    this.showIdlePreview();
                    return;
                }

                if (previewStrategy === 'direct') {
                    this.clearExecution();
                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: '',
                        model: '',
                        providerLabel: '',
                    };
                    this.agentPreview = this.normalizePreview(this.buildLocalPreview(text), this.agentPreviewMeta);
                    return;
                }

                var runtime = workspaceConfig.agent_runtime || {};
                var csrfToken = getCsrfToken();
                this.isAgentLoading = true;
                try {
                    if (!runtime.preview_url || !csrfToken) {
                        throw new Error('AI preview 연결 정보가 없습니다.');
                    }
                    var response = await fetch(runtime.preview_url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: JSON.stringify(this.buildPreviewRequestPayload(text)),
                    });
                    var payload = {};
                    try {
                        payload = await response.json();
                    } catch (jsonError) {
                        payload = {};
                    }
                    if (!response.ok || payload.status !== 'ok') {
                        throw new Error(payload.error || 'AI 미리보기를 불러오지 못했습니다.');
                    }
                    this.agentPreview = this.normalizePreview(payload.preview, this.previewProviderStatus(payload));
                    this.agentPreviewMeta = this.previewProviderStatus(payload);
                    this.setExecution(payload.execution);
                } catch (error) {
                    if (previewStrategy === 'service') {
                        this.showIdlePreview();
                    } else {
                        this.agentPreviewMeta = {
                            source: 'fallback',
                            provider: '',
                            model: '',
                            providerLabel: '규칙형 미리보기',
                        };
                        this.agentPreview = this.normalizePreview(this.buildLocalPreview(text), this.agentPreviewMeta);
                    }
                    showFeedback(error && error.message ? error.message : 'AI 미리보기를 불러오지 못했습니다.', 'info');
                } finally {
                    this.isAgentLoading = false;
                }
            },

            buildQuickdropPreview: function (text) {
                return this.buildPreviewSkeleton({
                    title: '바로전송 준비 완료',
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: [text],
                        },
                    ],
                    note: '',
                });
            },

            buildTtsPreview: function (text) {
                var items = compactLines(text).slice(0, 4);
                return this.buildPreviewSkeleton({
                    title: '읽을 문장을 정리했습니다.',
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: items.length ? items : [text],
                        },
                    ],
                    note: '',
                });
            },

            buildNoticePreview: function (text) {
                var sentences = compactSentences(text);
                var keyPoints = sentences.slice(0, 3);
                return this.buildPreviewSkeleton({
                    title: '알림장 초안',
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: keyPoints.length ? keyPoints : [text],
                        },
                    ],
                    note: '',
                });
            },

            buildSchedulePreview: function (text) {
                var lines = compactLines(text);
                var defaultDate = workspaceConfig.selected_date_label || '선택 날짜';
                var candidates = lines.slice(0, 4).map(function (line, index) {
                    var dateHint = firstMatch(line, /\d{1,2}월\s*\d{1,2}일|오늘|내일|모레|다음\s*주\s*[월화수목금토일]요일/);
                    var timeHint = firstMatch(line, /\d{1,2}:\d{2}|\d{1,2}교시/);
                    return (dateHint || defaultDate) + ' · ' + (timeHint || '시간 확인') + ' · ' + (line || ('일정 ' + (index + 1)));
                });
                var missing = [];
                if (!/\d{1,2}월\s*\d{1,2}일|오늘|내일|모레|다음\s*주\s*[월화수목금토일]요일/.test(text)) {
                    missing.push('날짜 입력 필요');
                }
                if (!/\d{1,2}:\d{2}|\d{1,2}교시/.test(text)) {
                    missing.push('시간 입력 필요');
                }
                return this.buildPreviewSkeleton({
                    title: '캘린더 등록 후보',
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: (candidates.length ? candidates : [text]).concat(missing).slice(0, 5),
                        },
                    ],
                    note: '',
                });
            },

            buildTeacherLawPreview: function (text) {
                var checks = [
                    '발생 날짜와 당사자 정리',
                    '문자, 통화, 촬영물 등 남은 기록 확인',
                    '학교 내부 보고와 공유 범위 확인',
                ];
                if (/촬영|영상|사진/.test(text)) {
                    checks.unshift('촬영 동의 범위와 제공 의무 여부 확인');
                }
                if (/학부모|보호자/.test(text)) {
                    checks.unshift('학부모 요구 내용과 회신 시점을 기록');
                }
                return this.buildPreviewSkeleton({
                    title: '법률 검토 메모',
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: checks.slice(0, 4),
                        },
                    ],
                    note: '',
                });
            },

            buildReservationPreview: function (text) {
                var dateHint = firstMatch(text, /\d{1,2}월\s*\d{1,2}일|오늘|내일|모레|다음\s*주\s*[월화수목금토일]요일/);
                var periodHint = firstMatch(text, /\d{1,2}교시/);
                var timeHint = firstMatch(text, /\d{1,2}:\d{2}/);
                var roomHint = firstMatch(text, /(과학실|컴퓨터실|방송실|도서관|미술실|체육관|영어실|음악실|강당|특별실)/);
                var missing = [];
                if (!dateHint) {
                    missing.push('날짜');
                }
                if (!periodHint && !timeHint) {
                    missing.push('교시 또는 시간');
                }
                if (!roomHint) {
                    missing.push('장소');
                }
                var reservationItems = [
                    '날짜 · ' + (dateHint || '입력 필요'),
                    '시간 · ' + (periodHint || timeHint || '입력 필요'),
                    '장소 · ' + (roomHint || '입력 필요'),
                ];
                if (missing.length) {
                    reservationItems = reservationItems.concat(missing.map(function (item) {
                        return item + ' 입력 필요';
                    }));
                }
                return this.buildPreviewSkeleton({
                    title: '예약 요청 후보',
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: reservationItems.slice(0, 6),
                        },
                    ],
                    note: '',
                });
            },

            buildPdfPreview: function (text) {
                var lines = compactSentences(text);
                return this.buildPreviewSkeleton({
                    title: '문서 정리 초안',
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: lines.slice(0, 3).length ? lines.slice(0, 3) : [text],
                        },
                    ],
                    note: '',
                });
            },

            buildMessageSavePreview: function (text) {
                var lines = compactLines(text).slice(0, 4);
                return this.buildPreviewSkeleton({
                    title: '보관할 메시지',
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: lines.length ? lines : [text],
                        },
                    ],
                    note: '',
                });
            },

            executeModeAction: async function () {
                if (this.activeMode.action_kind === 'open-service') {
                    var targetUrl = trimLine(this.activeMode.direct_url || this.activeMode.service_href || '');
                    if (!targetUrl) {
                        showFeedback('서비스 화면을 찾지 못했습니다.', 'error');
                        return;
                    }
                    window.location.href = targetUrl;
                    return;
                }

                var text = trimLine(this.workspaceInput);
                if (!text) {
                    showFeedback('내용을 먼저 넣어 주세요.', 'info');
                    this.focusWorkspace();
                    return;
                }

                if (this.activeMode.action_kind === 'quickdrop-send') {
                    this.clearExecution();
                    if (!this.activeMode.direct_url) {
                        showFeedback('바로전송 연결을 찾지 못했습니다.', 'error');
                        return;
                    }
                    var quickdropResponse = await fetch(this.activeMode.direct_url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'X-CSRFToken': getCsrfToken(),
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: new URLSearchParams({ text: text }).toString(),
                    });
                    var quickdropPayload = await quickdropResponse.json().catch(function () {
                        return {};
                    });
                    if (!quickdropResponse.ok) {
                        showFeedback(
                            quickdropPayload.detail || quickdropPayload.error || quickdropPayload.message || '전송하지 못했습니다.',
                            'error'
                        );
                        return;
                    }
                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: 'quickdrop',
                        model: '',
                        providerLabel: '즉시 전송',
                    };
                    this.agentPreview = this.normalizePreview({
                        badge: this.activeMode.label || '바로전송',
                        title: '전송했습니다.',
                        summary: trimLine(text).slice(0, 100),
                        sections: [
                            {
                                title: '보낸 내용',
                                items: [text],
                            },
                        ],
                        note: '연결된 기기와 전송함에서 바로 확인할 수 있습니다.',
                    }, this.agentPreviewMeta);
                    showFeedback('바로전송으로 보냈습니다.', 'success');
                    return;
                }

                if (this.activeMode.action_kind === 'tts-read') {
                    this.clearExecution();
                    if (!('speechSynthesis' in window) || typeof window.SpeechSynthesisUtterance !== 'function') {
                        showFeedback('이 브라우저에서는 읽어주기를 지원하지 않습니다.', 'error');
                        return;
                    }
                    var utterance = new window.SpeechSynthesisUtterance(text);
                    utterance.lang = 'ko-KR';
                    window.speechSynthesis.cancel();
                    window.speechSynthesis.speak(utterance);
                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: 'tts',
                        model: '',
                        providerLabel: '브라우저 TTS',
                    };
                    this.agentPreview = this.normalizePreview(this.buildTtsPreview(text), this.agentPreviewMeta);
                    showFeedback('지금 읽고 있습니다.', 'success');
                    return;
                }

                if (this.activeMode.action_kind === 'message-capture-save') {
                    this.clearExecution();
                    var saveCsrfToken = getCsrfToken();
                    if (!this.activeMode.direct_url) {
                        showFeedback('메시지 저장 연결을 찾지 못했습니다.', 'error');
                        return;
                    }
                    if (!saveCsrfToken) {
                        showFeedback('보안 토큰을 확인할 수 없습니다. 새로고침 후 다시 시도해 주세요.', 'error');
                        return;
                    }
                    var saveResponse = await fetch(this.activeMode.direct_url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'X-CSRFToken': saveCsrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: new URLSearchParams({
                            raw_text: text,
                            source_hint: 'home-agent-workspace',
                            idempotency_key: this.buildIdempotencyKey('message-save', text),
                        }).toString(),
                    });
                    var savePayload = await saveResponse.json().catch(function () {
                        return {};
                    });
                    if (!saveResponse.ok) {
                        showFeedback(
                            savePayload.detail || savePayload.error || savePayload.message || '메시지를 저장하지 못했습니다.',
                            'error'
                        );
                        return;
                    }
                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: 'messagebox',
                        model: '',
                        providerLabel: '메시지 보관',
                    };
                    this.agentPreview = this.normalizePreview({
                        badge: this.activeMode.label || '메시지 저장',
                        title: '보관했습니다.',
                        summary: trimLine(savePayload.summary_text || ''),
                        sections: [
                            {
                                title: '결과',
                                items: compactLines(savePayload.preview_text || text).slice(0, 4),
                            },
                        ],
                        note: '',
                    }, this.agentPreviewMeta);
                    showFeedback(savePayload.message || '메시지를 보관함에 저장했어요.', 'success');
                    return;
                }

                await this.runAgentPreview();
            },

            toggleActiveModeFavorite: async function () {
                var productId = parseInt(this.activeMode.product_id, 10);
                var csrfToken = getCsrfToken();
                if (Number.isNaN(productId) || !frontendConfig.toggleFavoriteUrl) {
                    return;
                }
                if (!csrfToken) {
                    showFeedback('보안 토큰을 확인할 수 없습니다. 새로고침 후 다시 시도해 주세요.', 'error');
                    return;
                }
                try {
                    var response = await fetch(frontendConfig.toggleFavoriteUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: JSON.stringify({ product_id: productId }),
                    });
                    var payload = await response.json().catch(function () {
                        return {};
                    });
                    if (!response.ok || payload.status !== 'ok') {
                        throw new Error(payload.error || '즐겨찾기 처리에 실패했습니다.');
                    }
                    this.setFavoriteState(productId, Boolean(payload.is_favorite));
                    showFeedback(payload.is_favorite ? '즐겨찾기에 추가했습니다.' : '즐겨찾기에서 제거했습니다.', 'success');
                } catch (error) {
                    showFeedback(error && error.message ? error.message : '즐겨찾기 처리 중 오류가 발생했습니다.', 'error');
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

    function initHomeV6Interactions() {
        if (window.__homeCommonInteractionsInitialized) {
            return;
        }
        window.__homeCommonInteractionsInitialized = true;

        initHomeV6DesktopRail();

        var config = getHomeFrontendConfig();
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

        function broadcastFavoriteIds() {
            window.dispatchEvent(new CustomEvent('home-v6:favorites-updated', {
                detail: { productIds: Array.from(favoriteIds) },
            }));
        }

        window.addEventListener('home-v6:favorites-updated', function (event) {
            var nextIds = normalizeIdList(event && event.detail ? event.detail.productIds : []);
            favoriteIds.clear();
            nextIds.forEach(function (value) {
                favoriteIds.add(value);
            });
            syncFavoriteButtons();
        });

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
                        broadcastFavoriteIds();
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
                    return response.json().catch(function () { return {}; }).then(function (payload) {
                        if (!response.ok) {
                            throw new Error(payload.error || '사용 기록 저장에 실패했습니다.');
                        }
                        if (payload && payload.buddy) {
                            document.dispatchEvent(new CustomEvent('teacherBuddy:progress', {
                                detail: payload.buddy,
                            }));
                        }
                        return payload;
                    });
                })
                .catch(function (error) {
                    showFeedback(error && error.message ? error.message : '사용 기록 저장 중 네트워크 오류가 발생했습니다.', 'error');
                });
        });

        document.body.addEventListener('htmx:beforeRequest', function (event) {
            clearInlineError(getHtmxSource(event));
        });

        document.body.addEventListener('htmx:afterRequest', function (event) {
            var source = getHtmxSource(event);
            if (!source || !event.detail || !event.detail.successful) {
                return;
            }
            clearInlineError(source);
            if (
                source.dataset
                && source.dataset.resetOnSuccess === 'true'
                && source.tagName === 'FORM'
                && typeof source.reset === 'function'
            ) {
                source.reset();
            }
        });

        document.body.addEventListener('htmx:responseError', function (event) {
            var source = getHtmxSource(event);
            if (!source || !source.dataset || !source.dataset.inlineErrorTarget) {
                return;
            }
            var fallback = (source.dataset.inlineErrorAction || '요청') + ' 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
            var message = extractResponseMessage(event, fallback);
            renderInlineError(source, message);
            showFeedback(message, 'error');
        });

        document.body.addEventListener('htmx:sendError', function (event) {
            var source = getHtmxSource(event);
            if (!source || !source.dataset || !source.dataset.inlineErrorTarget) {
                return;
            }
            var message = (source.dataset.inlineErrorAction || '요청') + ' 중 네트워크 오류가 발생했습니다. 같은 내용으로 다시 시도해 주세요.';
            renderInlineError(source, message);
            showFeedback(message, 'error');
        });

        syncFavoriteButtons();
        broadcastFavoriteIds();
    }

    document.addEventListener('DOMContentLoaded', initHomeV6Interactions);
})();
