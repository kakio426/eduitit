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

    function quickdropFileExtensionLabel(filename) {
        var name = String(filename || '').trim();
        var parts = name.split('.');
        if (parts.length > 1) {
            var extension = String(parts[parts.length - 1] || '').trim();
            if (extension) {
                return extension.slice(0, 6).toUpperCase();
            }
        }
        return 'FILE';
    }

    function inferQuickdropClipboardFilename(file) {
        var mimeType = String(file && file.type ? file.type : '');
        var rawExtension = mimeType.indexOf('/') >= 0 ? mimeType.split('/')[1] : 'bin';
        var extension = rawExtension.replace(/[^a-zA-Z0-9]/g, '') || 'bin';
        return 'clipboard-' + Date.now() + '.' + extension;
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
        var activeGroup = null;
        var pinnedSectionKey = '';
        var closeDelayTimer = 0;
        var railCloseDelayMs = 220;

        function getSectionKey(group) {
            return group && group.dataset ? String(group.dataset.homeV6NavSection || '') : '';
        }

        function resetPanelPosition(panel) {
            if (!panel) {
                return;
            }
            panel.style.position = '';
            panel.style.left = '';
            panel.style.top = '';
            panel.style.transform = '';
            panel.style.zIndex = '';
            panel.style.maxHeight = '';
        }

        function getPortalRoot() {
            if (rail.__homeV6PortalRoot && rail.__homeV6PortalRoot.isConnected) {
                return rail.__homeV6PortalRoot;
            }
            var pageRoot = rail.closest('.home-v6-page') || document.body;
            var portalRoot = pageRoot.querySelector('[data-home-v6-nav-portal-root="true"]');
            if (!portalRoot) {
                portalRoot = document.createElement('div');
                portalRoot.dataset.homeV6NavPortalRoot = 'true';
                portalRoot.className = 'home-v6-nav-portal-root';
                pageRoot.appendChild(portalRoot);
            }
            rail.__homeV6PortalRoot = portalRoot;
            return portalRoot;
        }

        function getViewportTopBoundary() {
            var rootStyles = window.getComputedStyle(document.documentElement);
            var mainNavHeight = parseFloat(rootStyles.getPropertyValue('--main-nav-height')) || 88;
            return Math.max(16, Math.round(mainNavHeight + 12));
        }

        function syncRailAlignment() {
            var railCard = rail.closest('[data-home-v6-nav-card="rail"]');
            var calendarGrid = document.querySelector('[data-home-v6-calendar-panel="desktop"] [data-classcalendar-home-grid-wrap="true"]');
            if (!railCard || !calendarGrid) {
                if (railCard) {
                    railCard.style.setProperty('--home-v6-rail-align-offset', '0px');
                }
                return;
            }
            var railCardRect = railCard.getBoundingClientRect();
            var calendarGridRect = calendarGrid.getBoundingClientRect();
            var offset = Math.max(0, Math.round(calendarGridRect.top - railCardRect.top));
            railCard.style.setProperty('--home-v6-rail-align-offset', offset + 'px');
        }

        function cancelPendingClose() {
            if (!closeDelayTimer) {
                return;
            }
            window.clearTimeout(closeDelayTimer);
            closeDelayTimer = 0;
        }

        function scheduleRailClose(key) {
            cancelPendingClose();
            closeDelayTimer = window.setTimeout(function () {
                closeDelayTimer = 0;
                if (pinnedSectionKey === key) {
                    return;
                }
                if (activeSectionKey === key) {
                    syncRailState('');
                }
            }, railCloseDelayMs);
        }

        function ensurePanelPortal(panel) {
            if (!panel) {
                return;
            }
            if (!panel.__homeV6PortalMeta) {
                panel.__homeV6PortalMeta = {
                    parent: panel.parentNode,
                    nextSibling: panel.nextSibling,
                };
            }
            var portalRoot = getPortalRoot();
            if (panel.parentNode !== portalRoot) {
                portalRoot.appendChild(panel);
            }
        }

        function restorePanelPortal(panel) {
            if (!panel || !panel.__homeV6PortalMeta) {
                return;
            }
            var meta = panel.__homeV6PortalMeta;
            if (!meta.parent || panel.parentNode === meta.parent) {
                return;
            }
            if (meta.nextSibling && meta.nextSibling.parentNode === meta.parent) {
                meta.parent.insertBefore(panel, meta.nextSibling);
                return;
            }
            meta.parent.appendChild(panel);
        }

        function getPanelTrigger(group) {
            if (!group) {
                return null;
            }
            return group.querySelector('.home-v6-nav-rail-button') || group;
        }

        function ensureGroupPanelCache(group) {
            if (!group) {
                return { flyout: null, tooltip: null };
            }
            if (!group.__homeV6Panels) {
                group.__homeV6Panels = {
                    flyout: group.querySelector('[data-home-v6-nav-flyout]'),
                    tooltip: group.querySelector('[data-home-v6-nav-tooltip]'),
                };
            }
            return group.__homeV6Panels;
        }

        function getGroupPanel(group, panelType) {
            var panels = ensureGroupPanelCache(group);
            return panels[panelType] || null;
        }

        function getGroupPanels(group) {
            var panels = ensureGroupPanelCache(group);
            return [panels.flyout, panels.tooltip].filter(Boolean);
        }

        function targetWithinGroupPanels(group, target) {
            if (!target) {
                return false;
            }
            if (group && group.contains(target)) {
                return true;
            }
            return getGroupPanels(group).some(function (panel) {
                return panel && panel.contains(target);
            });
        }

        function positionPanel(group, panel) {
            if (!group || !panel) {
                return;
            }

            var trigger = getPanelTrigger(group);
            if (!trigger) {
                return;
            }

            var viewportPadding = 16;
            var viewportTopBoundary = getViewportTopBoundary();
            var triggerRect = trigger.getBoundingClientRect();

            panel.style.position = 'fixed';
            panel.style.left = '0px';
            panel.style.top = '0px';
            panel.style.transform = 'translate3d(-9999px, -9999px, 0)';
            panel.style.zIndex = '520';
            panel.style.maxHeight = Math.max(window.innerHeight - viewportTopBoundary - viewportPadding, 160) + 'px';

            var panelRect = panel.getBoundingClientRect();
            var left = triggerRect.right + 10;
            if ((left + panelRect.width) > (window.innerWidth - viewportPadding)) {
                left = Math.max(viewportPadding, triggerRect.left - panelRect.width - 10);
            }

            var top = triggerRect.top - 6;
            var maxTop = Math.max(viewportTopBoundary, window.innerHeight - viewportPadding - panelRect.height);
            if (top < viewportTopBoundary) {
                top = viewportTopBoundary;
            } else if (top > maxTop) {
                top = maxTop;
            }

            panel.style.left = Math.round(left) + 'px';
            panel.style.top = Math.round(top) + 'px';
            panel.style.transform = 'none';
        }

        function setPanelState(group, panel, isOpen, displayValue) {
            if (!panel) {
                return;
            }
            panel.removeAttribute('x-cloak');
            panel.hidden = !isOpen;
            panel.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
            if (isOpen) {
                ensurePanelPortal(panel);
                panel.style.display = displayValue || 'block';
                positionPanel(group, panel);
                return;
            }
            panel.style.display = 'none';
            resetPanelPosition(panel);
            restorePanelPortal(panel);
        }

        function syncRailState(nextKey) {
            if (nextKey) {
                cancelPendingClose();
            }
            activeSectionKey = String(nextKey || '');
            activeGroup = null;
            groups.forEach(function (group) {
                var key = getSectionKey(group);
                var isActive = key && key === activeSectionKey;
                var button = group.querySelector('.home-v6-nav-rail-button:not(.home-v6-nav-rail-button--direct)');
                var flyout = getGroupPanel(group, 'flyout');
                var tooltip = getGroupPanel(group, 'tooltip');
                group.classList.toggle('is-open', isActive);
                if (button) {
                    button.setAttribute('aria-expanded', isActive ? 'true' : 'false');
                }
                setPanelState(group, flyout, isActive, 'block');
                setPanelState(group, tooltip, isActive, 'block');
                if (isActive) {
                    activeGroup = group;
                }
            });
            getPortalRoot().classList.toggle('is-active', Boolean(activeSectionKey));
        }

        function repositionActivePanels() {
            syncRailAlignment();
            if (!activeGroup || !activeSectionKey) {
                return;
            }
            positionPanel(activeGroup, getGroupPanel(activeGroup, 'flyout'));
            positionPanel(activeGroup, getGroupPanel(activeGroup, 'tooltip'));
        }

        syncRailState('');
        syncRailAlignment();

        groups.forEach(function (group) {
            var key = getSectionKey(group);
            var button = group.querySelector('.home-v6-nav-rail-button:not(.home-v6-nav-rail-button--direct)');
            var directLink = group.querySelector('.home-v6-nav-rail-button--direct');
            ensureGroupPanelCache(group);

            if (!key) {
                return;
            }

            group.addEventListener('mouseenter', function () {
                if (pinnedSectionKey && pinnedSectionKey !== key) {
                    return;
                }
                cancelPendingClose();
                syncRailState(key);
            });

            group.addEventListener('mouseleave', function (event) {
                if (pinnedSectionKey === key) {
                    return;
                }
                if (targetWithinGroupPanels(group, event.relatedTarget)) {
                    return;
                }
                scheduleRailClose(key);
            });

            group.addEventListener('focusin', function () {
                if (pinnedSectionKey && pinnedSectionKey !== key) {
                    return;
                }
                cancelPendingClose();
                syncRailState(key);
            });

            group.addEventListener('focusout', function (event) {
                if (pinnedSectionKey === key) {
                    return;
                }
                if (!targetWithinGroupPanels(group, event.relatedTarget)) {
                    scheduleRailClose(key);
                }
            });

            if (button) {
                button.addEventListener('click', function (event) {
                    event.preventDefault();
                    if (activeSectionKey === key && pinnedSectionKey === key) {
                        pinnedSectionKey = '';
                        syncRailState('');
                        return;
                    }
                    pinnedSectionKey = key;
                    syncRailState(key);
                });
            }

            if (directLink) {
                directLink.addEventListener('click', function () {
                    pinnedSectionKey = '';
                    syncRailState('');
                });
            }

            getGroupPanels(group).forEach(function (panel) {
                panel.addEventListener('mouseenter', function () {
                    cancelPendingClose();
                    syncRailState(key);
                });
                panel.addEventListener('mouseleave', function (event) {
                    if (pinnedSectionKey === key) {
                        return;
                    }
                    if (targetWithinGroupPanels(group, event.relatedTarget)) {
                        return;
                    }
                    scheduleRailClose(key);
                });
                panel.addEventListener('focusin', function () {
                    cancelPendingClose();
                    syncRailState(key);
                });
                panel.addEventListener('focusout', function (event) {
                    if (pinnedSectionKey === key) {
                        return;
                    }
                    if (targetWithinGroupPanels(group, event.relatedTarget)) {
                        return;
                    }
                    scheduleRailClose(key);
                });
            });
        });

        window.addEventListener('resize', repositionActivePanels);
        window.addEventListener('scroll', repositionActivePanels, true);

        document.addEventListener('click', function (event) {
            if (!rail.contains(event.target)) {
                cancelPendingClose();
                pinnedSectionKey = '';
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
            quickdropQueuedFile: null,
            quickdropQueuedFileDisplayName: '',
            quickdropErrorText: '',
            quickdropLastSentKind: '',
            quickdropLastSentText: '',
            quickdropLastSentFileName: '',
            isSendingQuickdrop: false,
            isTtsReading: false,
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
            noticeBaseInput: '',
            noticeRefinementLabel: '',
            scheduleEditorOpen: false,
            messageSavePayload: {},
            messageSaveStage: '',
            messageSaveErrorText: '',
            messageSaveSelectedCandidateId: '',
            messageSaveCommitResult: {},
            isSavingMessageSave: false,
            isExtractingMessageSave: false,
            isCommittingMessageSave: false,
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
                var textarea = Array.prototype.slice.call(document.querySelectorAll('[data-home-v6-agent-input="true"]')).find(function (node) {
                    return node && !node.disabled && node.offsetParent !== null;
                }) || null;
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

            clearMessageSaveState: function () {
                this.messageSavePayload = {};
                this.messageSaveStage = '';
                this.isSavingMessageSave = false;
                this.isExtractingMessageSave = false;
                this.isCommittingMessageSave = false;
                this.messageSaveErrorText = '';
                this.messageSaveSelectedCandidateId = '';
                this.messageSaveCommitResult = {};
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
                var fieldOrder = [
                    'title',
                    'start_time',
                    'end_time',
                    'school_slug',
                    'date',
                    'period',
                    'room_id',
                    'grade',
                    'class_no',
                    'target_label',
                    'name',
                    'edit_code',
                    'override_grade_lock',
                    'question',
                    'incident_type',
                    'legal_goal',
                    'scene',
                    'counterpart',
                ];
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
                this.scheduleEditorOpen = false;
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
                this.agentExecutionFieldErrors = {};
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
                if (this.agentExecution && this.agentExecution.kind === 'reservation') {
                    var reservationErrors = {};
                    var ownerType = trimLine(this.agentExecutionDraft.owner_type || 'class');
                    var editCode = trimLine(this.agentExecutionDraft.edit_code || '');
                    if (!trimLine(this.agentExecutionDraft.school_slug || '')) {
                        reservationErrors.school_slug = '예약판을 골라 주세요.';
                    }
                    if (!trimLine(this.agentExecutionDraft.date || '')) {
                        reservationErrors.date = '날짜를 골라 주세요.';
                    }
                    if (!trimLine(this.agentExecutionDraft.period || '')) {
                        reservationErrors.period = '교시를 골라 주세요.';
                    }
                    if (!trimLine(this.agentExecutionDraft.room_id || '')) {
                        reservationErrors.room_id = '장소를 골라 주세요.';
                    }
                    if (ownerType === 'class') {
                        if (!trimLine(this.agentExecutionDraft.grade || '')) {
                            reservationErrors.grade = '학년을 입력해 주세요.';
                        }
                        if (!trimLine(this.agentExecutionDraft.class_no || '')) {
                            reservationErrors.class_no = '반을 입력해 주세요.';
                        }
                    } else if (!trimLine(this.agentExecutionDraft.target_label || '')) {
                        reservationErrors.target_label = '이용 대상을 입력해 주세요.';
                    }
                    if (!trimLine(this.agentExecutionDraft.name || '')) {
                        reservationErrors.name = '이름을 입력해 주세요.';
                    }
                    if (!/^\d{4}$/.test(editCode)) {
                        reservationErrors.edit_code = '수정 코드 4자리를 입력해 주세요.';
                    }
                    return reservationErrors;
                }
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
                    if (this.activeModeKey === 'schedule') {
                        this.scheduleEditorOpen = true;
                    }
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
                        if (this.activeModeKey === 'schedule') {
                            this.scheduleEditorOpen = true;
                        }
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
                this.clearMessageSaveState();
                this.scheduleEditorOpen = false;
                if (this.activeModeKey === 'notice' || !trimLine(this.workspaceInput)) {
                    this.noticeRefinementLabel = '';
                    if (!trimLine(this.workspaceInput)) {
                        this.noticeBaseInput = '';
                    }
                }
            },

            quickdropQuickExamples: function () {
                return [
                    { label: '글', kind: 'text', text: '오늘 6교시 체육관 사용합니다.' },
                    { label: '링크', kind: 'text', text: '학년 회의 링크 https://example.com' },
                    { label: '사진', kind: 'file' },
                    { label: '파일', kind: 'file' },
                ];
            },

            runQuickdropExample: function (item) {
                var payload = item && typeof item === 'object' ? item : {};
                if (payload.kind === 'file') {
                    this.openQuickdropFilePicker();
                    return;
                }
                this.quickdropErrorText = '';
                this.workspaceInput = trimLine(payload.text || '');
                this.focusWorkspace();
            },

            quickdropFileInput: function () {
                return document.querySelector('[data-home-v6-agent-quickdrop-file-input="true"]');
            },

            openQuickdropFilePicker: function () {
                var input = this.quickdropFileInput();
                if (input && typeof input.click === 'function') {
                    input.click();
                }
            },

            queueQuickdropFile: function (file, filenameOverride) {
                this.quickdropQueuedFile = file || null;
                this.quickdropQueuedFileDisplayName = file
                    ? trimLine(filenameOverride || file.name || '')
                    : '';
                this.quickdropErrorText = '';
            },

            queueQuickdropFileFromInput: function (event) {
                var input = event && event.target ? event.target : null;
                var file = input && input.files ? input.files[0] : null;
                this.queueQuickdropFile(file, file ? file.name : '');
            },

            quickdropQueuedFileName: function () {
                return trimLine(this.quickdropQueuedFileDisplayName || '');
            },

            clearQuickdropQueuedFile: function () {
                var input = this.quickdropFileInput();
                if (input) {
                    input.value = '';
                }
                this.quickdropQueuedFile = null;
                this.quickdropQueuedFileDisplayName = '';
                this.quickdropErrorText = '';
            },

            captureQuickdropWorkspacePaste: function (event) {
                var clipboard = event && event.clipboardData ? event.clipboardData : null;
                var items = clipboard && clipboard.items ? Array.prototype.slice.call(clipboard.items) : [];
                var fileItem = items.find(function (item) {
                    return item && item.kind === 'file';
                }) || null;
                var file = fileItem && typeof fileItem.getAsFile === 'function' ? fileItem.getAsFile() : null;
                var displayName = '';
                if (!file) {
                    return;
                }
                event.preventDefault();
                displayName = trimLine(file.name || '') || inferQuickdropClipboardFilename(file);
                this.queueQuickdropFile(file, displayName);
                showFeedback('파일을 담았어요.', 'success');
            },

            quickdropUserBubbleKind: function () {
                var queuedFile = this.quickdropQueuedFile;
                if (queuedFile) {
                    return String(queuedFile.type || '').indexOf('image/') === 0 ? 'image' : 'file';
                }
                if (trimLine(this.workspaceInput)) {
                    return 'text';
                }
                if (this.quickdropLastSentKind === 'text' && trimLine(this.quickdropLastSentText)) {
                    return 'text';
                }
                if ((this.quickdropLastSentKind === 'file' || this.quickdropLastSentKind === 'image') && trimLine(this.quickdropLastSentFileName)) {
                    return this.quickdropLastSentKind;
                }
                return '';
            },

            quickdropUserBubbleText: function () {
                var kind = this.quickdropUserBubbleKind();
                if (kind === 'text') {
                    return trimLine(this.workspaceInput) || trimLine(this.quickdropLastSentText);
                }
                if (kind === 'file' || kind === 'image') {
                    return this.quickdropQueuedFileName() || trimLine(this.quickdropLastSentFileName);
                }
                return '';
            },

            quickdropHasResult: function () {
                return Boolean(
                    this.agentPreviewMeta
                    && this.agentPreviewMeta.provider === 'quickdrop'
                    && (trimLine(this.agentPreview && this.agentPreview.title) || this.previewResultLines().length)
                );
            },

            quickdropHasConversation: function () {
                return Boolean(this.quickdropUserBubbleKind() || this.isSendingQuickdrop || this.quickdropHasResult());
            },

            quickdropResultTitle: function () {
                if (this.quickdropHasResult()) {
                    return trimLine(this.agentPreview && this.agentPreview.title) || '전송 완료';
                }
                if (this.isSendingQuickdrop) {
                    return '전송 중';
                }
                return '';
            },

            quickdropResultKind: function () {
                if (this.quickdropLastSentKind === 'image' || this.quickdropLastSentKind === 'file') {
                    return this.quickdropLastSentKind;
                }
                return 'text';
            },

            quickdropResultBody: function () {
                if (!this.quickdropHasResult()) {
                    return '';
                }
                return trimLine(this.previewResultLines()[0] || (this.agentPreview && this.agentPreview.summary) || '');
            },

            quickdropResultBadge: function () {
                if (this.quickdropResultKind() === 'image') {
                    return '사진';
                }
                return quickdropFileExtensionLabel(this.quickdropLastSentFileName || this.quickdropResultBody());
            },

            quickdropSubmitLabel: function () {
                if (this.isSendingQuickdrop) {
                    return '전송 중';
                }
                if (this.quickdropQueuedFile) {
                    return '파일 전송';
                }
                return '전송';
            },

            buildQuickdropSentPreview: function (kind, value) {
                var normalizedKind = trimLine(kind || 'text');
                return this.buildPreviewSkeleton({
                    badge: this.activeMode.label || '바로전송',
                    title: normalizedKind === 'text'
                        ? '글 전송 완료'
                        : (normalizedKind === 'image' ? '사진 전송 완료' : '파일 전송 완료'),
                    summary: '',
                    sections: [
                        {
                            title: '결과',
                            items: [value],
                        },
                    ],
                    note: '',
                });
            },

            sendQuickdropChat: async function () {
                var queuedFile = this.quickdropQueuedFile;
                var queuedFileName = this.quickdropQueuedFileName();
                var text = trimLine(this.workspaceInput);
                var csrfToken = getCsrfToken();
                var sendTextUrl = trimLine(this.activeMode.direct_url || '');
                var sendFileUrl = trimLine(this.activeMode.send_file_url || '');
                var response;
                var payload;
                var session;
                var sentKind;
                var sentValue;

                if (!queuedFile && !text) {
                    this.quickdropErrorText = '보낼 내용을 넣어 주세요.';
                    showFeedback(this.quickdropErrorText, 'info');
                    this.focusWorkspace();
                    return;
                }
                if (queuedFile && text) {
                    this.quickdropErrorText = '글과 파일은 따로 보내 주세요.';
                    showFeedback(this.quickdropErrorText, 'info');
                    return;
                }
                if (!csrfToken) {
                    this.quickdropErrorText = '보안 토큰을 확인할 수 없습니다.';
                    showFeedback(this.quickdropErrorText, 'error');
                    return;
                }
                if (queuedFile && !sendFileUrl) {
                    this.quickdropErrorText = '첨부 경로를 찾지 못했습니다.';
                    showFeedback(this.quickdropErrorText, 'error');
                    return;
                }
                if (!queuedFile && !sendTextUrl) {
                    this.quickdropErrorText = '전송 경로를 찾지 못했습니다.';
                    showFeedback(this.quickdropErrorText, 'error');
                    return;
                }

                this.quickdropErrorText = '';
                this.isSendingQuickdrop = true;
                this.clearExecution();
                this.agentPreview = this.buildIdlePreview();
                this.agentPreviewMeta = {
                    source: '',
                    provider: '',
                    model: '',
                    providerLabel: '',
                };

                try {
                    if (queuedFile) {
                        var fileData = new FormData();
                        fileData.append('file', queuedFile, queuedFileName || queuedFile.name || 'shared-file');
                        response = await fetch(sendFileUrl, {
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': csrfToken,
                                'X-Requested-With': 'XMLHttpRequest',
                            },
                            body: fileData,
                        });
                    } else {
                        var textData = new FormData();
                        textData.append('text', text);
                        response = await fetch(sendTextUrl, {
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': csrfToken,
                                'X-Requested-With': 'XMLHttpRequest',
                            },
                            body: textData,
                        });
                    }

                    payload = await response.json().catch(function () {
                        return {};
                    });
                    if (!response.ok || payload.ok === false) {
                        throw new Error(payload.error || payload.detail || payload.message || '전송하지 못했습니다.');
                    }

                    session = payload && payload.session ? payload.session : {};
                    sentKind = queuedFile
                        ? (String(session.current_kind || '').toLowerCase() === 'image' ? 'image' : 'file')
                        : 'text';
                    sentValue = sentKind === 'text'
                        ? trimLine(session.current_text || text)
                        : trimLine(session.current_filename || queuedFileName || (queuedFile && queuedFile.name) || '');

                    this.quickdropLastSentKind = sentKind;
                    this.quickdropLastSentText = sentKind === 'text' ? sentValue : '';
                    this.quickdropLastSentFileName = sentKind === 'text' ? '' : sentValue;
                    if (sentKind === 'text') {
                        this.workspaceInput = '';
                    } else {
                        this.clearQuickdropQueuedFile();
                    }

                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: 'quickdrop',
                        model: '',
                        providerLabel: '즉시 전송',
                    };
                    this.agentPreview = this.normalizePreview(
                        this.buildQuickdropSentPreview(sentKind, sentValue),
                        this.agentPreviewMeta
                    );
                    showFeedback(sentKind === 'text' ? '글을 보냈어요.' : '파일을 보냈어요.', 'success');
                } catch (error) {
                    this.quickdropErrorText = error && error.message ? error.message : '전송하지 못했습니다.';
                    showFeedback(this.quickdropErrorText, 'error');
                } finally {
                    this.isSendingQuickdrop = false;
                }
            },

            resetQuickdropChat: function () {
                this.workspaceInput = '';
                this.quickdropErrorText = '';
                this.quickdropLastSentKind = '';
                this.quickdropLastSentText = '';
                this.quickdropLastSentFileName = '';
                this.clearQuickdropQueuedFile();
                this.showIdlePreview();
                this.focusWorkspace();
            },

            pdfUserBubbleText: function () {
                return trimLine(this.workspaceInput);
            },

            pdfHasResult: function () {
                return Boolean(this.previewResultLines().length);
            },

            pdfHasConversation: function () {
                return Boolean(this.pdfUserBubbleText() || this.isAgentLoading || this.pdfHasResult());
            },

            pdfDraftHeading: function () {
                var preview = this.agentPreview && typeof this.agentPreview === 'object' ? this.agentPreview : {};
                return trimLine(preview.title || '문서 정리 초안');
            },

            pdfQuickExamples: function () {
                return [
                    { label: '가정통신문', text: '가정통신문 PDF에서 학부모에게 다시 안내할 핵심만 뽑아 주세요.' },
                    { label: '공문', text: '공문 PDF에서 오늘 처리할 일만 짧게 정리해 주세요.' },
                    { label: '연수 자료', text: '연수 자료 PDF에서 오늘 수업에 바로 쓸 내용만 정리해 주세요.' },
                    { label: '회의 자료', text: '회의 자료 PDF에서 공유할 결정 사항만 정리해 주세요.' },
                ];
            },

            runPdfExample: function (text) {
                var value = trimLine(text);
                if (!value) {
                    return;
                }
                this.workspaceInput = value;
                this.runAgentPreview(value);
            },

            resetPdfChat: function () {
                this.workspaceInput = '';
                this.showIdlePreview();
                this.focusWorkspace();
            },

            copyPdfDraft: async function () {
                var lines = this.previewResultLines();
                if (!lines.length) {
                    showFeedback('복사할 정리가 없습니다.', 'info');
                    return;
                }
                try {
                    await navigator.clipboard.writeText(lines.join('\n'));
                    showFeedback('정리 내용을 복사했습니다.', 'success');
                } catch (error) {
                    showFeedback('복사하지 못했습니다.', 'error');
                }
            },

            ttsUserBubbleText: function () {
                return trimLine(this.workspaceInput);
            },

            ttsHasResult: function () {
                return Boolean(this.previewResultLines().length);
            },

            ttsHasConversation: function () {
                return Boolean(this.ttsUserBubbleText() || this.isAgentLoading || this.ttsHasResult());
            },

            ttsDraftHeading: function () {
                var preview = this.agentPreview && typeof this.agentPreview === 'object' ? this.agentPreview : {};
                return trimLine(preview.title || '읽기 문구');
            },

            ttsQuickExamples: function () {
                return [
                    { label: '이동', text: '지금부터 체육관으로 이동합니다. 줄을 맞춰 조용히 이동합니다.' },
                    { label: '정리', text: '쉬는 시간 종료 1분 전입니다. 자리에 앉아 다음 수업을 준비합니다.' },
                    { label: '조회', text: '지금부터 아침 조회를 시작합니다. 오늘 일정을 함께 확인하겠습니다.' },
                    { label: '하교', text: '오늘 수업이 모두 끝났습니다. 주변을 정리하고 안전하게 하교합니다.' },
                ];
            },

            runTtsExample: function (text) {
                var value = trimLine(text);
                if (!value) {
                    return;
                }
                this.workspaceInput = value;
                this.runAgentPreview(value);
            },

            ttsReadLabel: function () {
                return this.isTtsReading ? '읽는 중' : '바로 읽기';
            },

            playTtsDraft: function () {
                var text = trimLine(this.workspaceInput);
                var utterance;
                var self = this;
                if (!text) {
                    showFeedback('읽을 문장을 먼저 넣어 주세요.', 'info');
                    this.focusWorkspace();
                    return;
                }
                if (!('speechSynthesis' in window) || typeof window.SpeechSynthesisUtterance !== 'function') {
                    showFeedback('이 브라우저에서는 읽어주기를 지원하지 않습니다.', 'error');
                    return;
                }
                utterance = new window.SpeechSynthesisUtterance(text);
                utterance.lang = 'ko-KR';
                utterance.onend = function () {
                    self.isTtsReading = false;
                };
                utterance.onerror = function () {
                    self.isTtsReading = false;
                    showFeedback('읽지 못했습니다.', 'error');
                };
                this.isTtsReading = true;
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
            },

            resetTtsChat: function () {
                this.workspaceInput = '';
                this.isTtsReading = false;
                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                }
                this.showIdlePreview();
                this.focusWorkspace();
            },

            copyTtsDraft: async function () {
                var lines = this.previewResultLines();
                if (!lines.length) {
                    showFeedback('복사할 문구가 없습니다.', 'info');
                    return;
                }
                try {
                    await navigator.clipboard.writeText(lines.join('\n'));
                    showFeedback('문구를 복사했습니다.', 'success');
                } catch (error) {
                    showFeedback('복사하지 못했습니다.', 'error');
                }
            },

            messageSaveQuickExamples: function () {
                return [
                    { label: '학부모 문자', text: '학부모님, 다음 주 수요일 오후 3시에 상담 가능합니다. 가능 여부 회신 부탁드립니다.' },
                    { label: '회의 안내', text: '금요일 14시에 학년 회의실에서 회의합니다. 자료는 10분 전까지 올려 주세요.' },
                    { label: '행사 공지', text: '4월 25일 오전 9시 운동장 집합입니다. 체육대회 준비물은 물과 모자입니다.' },
                    { label: '수업 변경', text: '내일 2교시 과학실 수업이 4교시로 바뀝니다. 실험 준비물은 그대로 가져옵니다.' },
                ];
            },

            runMessageSaveExample: function (text) {
                var value = trimLine(text);
                if (!value) {
                    return;
                }
                this.clearMessageSaveState();
                this.workspaceInput = value;
                this.focusWorkspace();
            },

            handleMessageSaveInputChange: function () {
                var payload = this.messageSavePayload && typeof this.messageSavePayload === 'object' ? this.messageSavePayload : {};
                var savedText = trimLine(payload.raw_text || '');
                this.messageSaveErrorText = '';
                if (!this.messageSaveStage) {
                    return;
                }
                if (trimLine(this.workspaceInput) !== savedText) {
                    this.messageSavePayload = {};
                    this.messageSaveStage = '';
                    this.messageSaveSelectedCandidateId = '';
                    this.messageSaveCommitResult = {};
                }
            },

            messageSaveUserBubbleText: function () {
                return trimLine(this.workspaceInput);
            },

            messageSaveCanSave: function () {
                return Boolean(this.messageSaveUserBubbleText());
            },

            messageSaveHasConversation: function () {
                return Boolean(
                    this.messageSaveUserBubbleText()
                    || this.isSavingMessageSave
                    || this.isExtractingMessageSave
                    || this.isCommittingMessageSave
                    || this.messageSaveStage
                );
            },

            messageSaveShouldShowAssistantBubble: function () {
                return Boolean(
                    this.isSavingMessageSave
                    || this.isExtractingMessageSave
                    || this.isCommittingMessageSave
                    || this.messageSaveStage
                    || this.messageSaveDraftLines().length
                );
            },

            messageSaveDraftTitle: function () {
                if (this.isSavingMessageSave) {
                    return '보관 중';
                }
                if (this.isExtractingMessageSave) {
                    return '일정 찾는 중';
                }
                if (this.isCommittingMessageSave) {
                    return '캘린더 저장 중';
                }
                if (this.messageSaveStage === 'saved') {
                    return '보관 완료';
                }
                if (this.messageSaveStage === 'extracted') {
                    return this.messageSaveCandidateList().length ? '일정 후보' : '일정 확인';
                }
                if (this.messageSaveStage === 'committed') {
                    return '캘린더 저장 완료';
                }
                return '보관할 메시지';
            },

            messageSaveDraftLines: function () {
                return compactLines(this.workspaceInput).slice(0, 4);
            },

            messageSaveParseTemporalParts: function (value) {
                var text = trimLine(value);
                var match = text.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
                var weekdays = ['일', '월', '화', '수', '목', '금', '토'];
                var date;
                if (!match) {
                    return null;
                }
                date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
                if (Number.isNaN(date.getTime())) {
                    return null;
                }
                return {
                    month: Number(match[2]),
                    day: Number(match[3]),
                    weekday: weekdays[date.getDay()],
                    hour: match[4] || '',
                    minute: match[5] || '',
                    hasTime: Boolean(match[4] && match[5]),
                };
            },

            messageSaveTemporalDateLabel: function (value) {
                var parts = this.messageSaveParseTemporalParts(value);
                if (!parts) {
                    return '';
                }
                return parts.month + '월 ' + parts.day + '일 ' + parts.weekday + '요일';
            },

            messageSaveTemporalTimeLabel: function (startValue, endValue, isAllDay) {
                var start = this.messageSaveParseTemporalParts(startValue);
                var end = this.messageSaveParseTemporalParts(endValue);
                if (isAllDay && start) {
                    return '하루 종일';
                }
                if (!start || !start.hasTime) {
                    return '';
                }
                if (end && end.hasTime) {
                    return start.hour + ':' + start.minute + ' - ' + end.hour + ':' + end.minute;
                }
                return start.hour + ':' + start.minute;
            },

            messageSaveRawCandidates: function () {
                var payload = this.messageSavePayload && typeof this.messageSavePayload === 'object' ? this.messageSavePayload : {};
                var candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
                return candidates.filter(function (candidate) {
                    return candidate && !candidate.already_saved;
                }).slice(0, 4);
            },

            messageSaveResolvedSelectedCandidateId: function () {
                var candidates = this.messageSaveRawCandidates();
                var selectedId = String(this.messageSaveSelectedCandidateId || '');
                var hasSelected = candidates.some(function (candidate) {
                    return String(candidate.candidate_id || '') === selectedId;
                });
                if (hasSelected) {
                    return selectedId;
                }
                return candidates.length ? String(candidates[0].candidate_id || '') : '';
            },

            messageSaveCandidateList: function () {
                var resolvedId = this.messageSaveResolvedSelectedCandidateId();
                return this.messageSaveRawCandidates().map(function (candidate, index) {
                    var title = trimLine(candidate.title || candidate.summary || ('일정 ' + (index + 1)));
                    var when = [
                        this.messageSaveTemporalDateLabel(candidate.start_time || candidate.end_time),
                        this.messageSaveTemporalTimeLabel(candidate.start_time, candidate.end_time, candidate.is_all_day),
                    ].filter(Boolean).join(' · ');
                    return {
                        id: String(candidate.candidate_id || index + 1),
                        kind: trimLine(candidate.kind || 'event'),
                        title: title || ('일정 ' + (index + 1)),
                        when: when || '시간 확인',
                        summary: trimLine(candidate.summary || ''),
                        start_time: trimLine(candidate.start_time || ''),
                        end_time: trimLine(candidate.end_time || ''),
                        is_all_day: Boolean(candidate.is_all_day),
                        isActive: String(candidate.candidate_id || index + 1) === resolvedId,
                    };
                }, this);
            },

            messageSaveActiveCandidate: function () {
                var activeId = this.messageSaveResolvedSelectedCandidateId();
                return this.messageSaveCandidateList().find(function (candidate) {
                    return candidate.id === activeId;
                }) || null;
            },

            selectMessageSaveCandidate: function (candidateId) {
                var normalizedId = String(candidateId || '');
                if (!normalizedId) {
                    return;
                }
                this.messageSaveSelectedCandidateId = normalizedId;
                this.messageSaveErrorText = '';
            },

            messageSaveWarnings: function () {
                var payload = this.messageSavePayload && typeof this.messageSavePayload === 'object' ? this.messageSavePayload : {};
                return Array.isArray(payload.warnings) ? payload.warnings.slice(0, 4) : [];
            },

            messageSaveResultLines: function () {
                var payload = this.messageSavePayload && typeof this.messageSavePayload === 'object' ? this.messageSavePayload : {};
                var commitResult = this.messageSaveCommitResult && typeof this.messageSaveCommitResult === 'object' ? this.messageSaveCommitResult : {};
                var lines = [];
                if (this.messageSaveStage === 'saved') {
                    lines = compactLines(payload.preview_text || payload.raw_text || this.workspaceInput).slice(0, 4);
                    return lines;
                }
                if (this.messageSaveStage === 'extracted') {
                    lines = compactLines(payload.summary_text || '').slice(0, 2);
                    if (!lines.length) {
                        lines = compactLines(payload.preview_text || payload.raw_text || this.workspaceInput).slice(0, 4);
                    }
                    return lines;
                }
                if (this.messageSaveStage === 'committed') {
                    var savedEvent = this.messageSaveCommittedEvent();
                    if (savedEvent) {
                        lines = [
                            this.messageSaveTemporalDateLabel(savedEvent.start_time || savedEvent.end_time),
                            this.messageSaveTemporalTimeLabel(savedEvent.start_time, savedEvent.end_time, savedEvent.is_all_day),
                            trimLine(savedEvent.title || ''),
                        ].filter(Boolean);
                    }
                    if (!lines.length) {
                        lines = compactLines(commitResult.message || '').slice(0, 3);
                    }
                    return lines;
                }
                return [];
            },

            messageSaveCommittedEvent: function () {
                var commitResult = this.messageSaveCommitResult && typeof this.messageSaveCommitResult === 'object' ? this.messageSaveCommitResult : {};
                var created = Array.isArray(commitResult.created_events) ? commitResult.created_events : [];
                var reused = Array.isArray(commitResult.reused_events) ? commitResult.reused_events : [];
                return created[0] || reused[0] || null;
            },

            messageSaveOpenHref: function () {
                var payload = this.messageSavePayload && typeof this.messageSavePayload === 'object' ? this.messageSavePayload : {};
                var savedEvent = this.messageSaveCommittedEvent();
                if (this.messageSaveStage === 'committed' && savedEvent) {
                    return trimLine(savedEvent.calendar_url || '');
                }
                if (this.messageSaveStage === 'saved') {
                    return trimLine(payload.messagebox_url || this.activeMode.after_action_href || this.activeMode.service_href || '');
                }
                return '';
            },

            messageSaveOpenLabel: function () {
                return this.messageSaveStage === 'committed' ? '캘린더 열기' : '보관함';
            },

            messageSaveParseSavedUrl: function () {
                var payload = this.messageSavePayload && typeof this.messageSavePayload === 'object' ? this.messageSavePayload : {};
                var captureId = trimLine(payload.capture_id || '');
                var template = trimLine(this.activeMode.parse_saved_template || '');
                if (!captureId || !template) {
                    return '';
                }
                return template.replace('__capture_id__', captureId);
            },

            messageSaveCommitUrl: function () {
                var payload = this.messageSavePayload && typeof this.messageSavePayload === 'object' ? this.messageSavePayload : {};
                var captureId = trimLine(payload.capture_id || '');
                var template = trimLine(this.activeMode.commit_template || '');
                if (!captureId || !template) {
                    return '';
                }
                return template.replace('__capture_id__', captureId);
            },

            messageSaveCanCommit: function () {
                return Boolean(this.messageSaveStage === 'extracted' && this.messageSaveActiveCandidate());
            },

            saveMessageCaptureChat: async function () {
                var text = trimLine(this.workspaceInput);
                var csrfToken = getCsrfToken();
                var saveUrl = trimLine(this.activeMode.direct_url || '');
                var response;
                var payload;

                if (!text) {
                    this.messageSaveErrorText = '저장할 메시지를 먼저 넣어 주세요.';
                    showFeedback(this.messageSaveErrorText, 'info');
                    this.focusWorkspace();
                    return;
                }
                if (!saveUrl) {
                    this.messageSaveErrorText = '메시지 저장 경로를 찾지 못했습니다.';
                    showFeedback(this.messageSaveErrorText, 'error');
                    return;
                }
                if (!csrfToken) {
                    this.messageSaveErrorText = '보안 토큰을 확인할 수 없습니다.';
                    showFeedback(this.messageSaveErrorText, 'error');
                    return;
                }

                this.messageSaveErrorText = '';
                this.isSavingMessageSave = true;
                this.isExtractingMessageSave = false;
                this.isCommittingMessageSave = false;
                this.messageSavePayload = {};
                this.messageSaveStage = '';
                this.messageSaveSelectedCandidateId = '';
                this.messageSaveCommitResult = {};
                this.clearExecution();

                try {
                    response = await fetch(saveUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: new URLSearchParams({
                            raw_text: text,
                            source_hint: 'home-agent-workspace',
                            idempotency_key: this.buildIdempotencyKey('message-save', text),
                        }).toString(),
                    });
                    payload = await response.json().catch(function () {
                        return {};
                    });
                    if (!response.ok) {
                        throw new Error(payload.detail || payload.error || payload.message || '메시지를 저장하지 못했습니다.');
                    }
                    this.messageSavePayload = this.clonePayload(payload);
                    this.messageSaveStage = 'saved';
                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: 'messagebox',
                        model: '',
                        providerLabel: '메시지 보관',
                    };
                    this.agentPreview = this.normalizePreview({
                        badge: this.activeMode.label || '메시지 저장',
                        title: '보관 완료',
                        summary: '',
                        sections: [
                            {
                                title: '결과',
                                items: this.messageSaveResultLines(),
                            },
                        ],
                        note: '',
                    }, this.agentPreviewMeta);
                    showFeedback(payload.message || '메시지를 보관함에 저장했어요.', 'success');
                } catch (error) {
                    this.messageSaveErrorText = error && error.message ? error.message : '메시지를 저장하지 못했습니다.';
                    showFeedback(this.messageSaveErrorText, 'error');
                } finally {
                    this.isSavingMessageSave = false;
                }
            },

            extractSavedMessageCapture: async function () {
                var parseSavedUrl = this.messageSaveParseSavedUrl();
                var csrfToken = getCsrfToken();
                var response;
                var payload;
                var previewLines;

                if (!parseSavedUrl) {
                    this.messageSaveErrorText = '일정을 찾을 메시지를 먼저 저장해 주세요.';
                    showFeedback(this.messageSaveErrorText, 'info');
                    return;
                }
                if (!csrfToken) {
                    this.messageSaveErrorText = '보안 토큰을 확인할 수 없습니다.';
                    showFeedback(this.messageSaveErrorText, 'error');
                    return;
                }

                this.messageSaveErrorText = '';
                this.isExtractingMessageSave = true;

                try {
                    response = await fetch(parseSavedUrl, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    payload = await response.json().catch(function () {
                        return {};
                    });
                    if (!response.ok) {
                        throw new Error(payload.detail || payload.error || payload.message || '보관한 메시지에서 일정을 찾지 못했습니다.');
                    }
                    this.messageSavePayload = this.clonePayload(payload);
                    this.messageSaveStage = 'extracted';
                    this.messageSaveSelectedCandidateId = this.messageSaveResolvedSelectedCandidateId();
                    previewLines = this.messageSaveCandidateList().map(function (candidate) {
                        return [candidate.when, candidate.title].filter(Boolean).join(' · ');
                    });
                    if (!previewLines.length) {
                        previewLines = this.messageSaveWarnings();
                    }
                    if (!previewLines.length) {
                        previewLines = this.messageSaveResultLines();
                    }
                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: 'messagebox',
                        model: '',
                        providerLabel: '메시지 추출',
                    };
                    this.agentPreview = this.normalizePreview({
                        badge: this.activeMode.label || '메시지 저장',
                        title: this.messageSaveCandidateList().length ? '일정 후보' : '일정 확인',
                        summary: '',
                        sections: [
                            {
                                title: '결과',
                                items: previewLines,
                            },
                        ],
                        note: '',
                    }, this.agentPreviewMeta);
                    showFeedback(payload.message || '보관한 메시지에서 일정을 찾았어요.', 'success');
                } catch (error) {
                    this.messageSaveErrorText = error && error.message ? error.message : '보관한 메시지에서 일정을 찾지 못했습니다.';
                    showFeedback(this.messageSaveErrorText, 'error');
                } finally {
                    this.isExtractingMessageSave = false;
                }
            },

            commitMessageSaveCandidate: async function () {
                var commitUrl = this.messageSaveCommitUrl();
                var csrfToken = getCsrfToken();
                var activeCandidate = this.messageSaveActiveCandidate();
                var response;
                var payload;

                if (!activeCandidate) {
                    this.messageSaveErrorText = '저장할 일정을 선택해 주세요.';
                    showFeedback(this.messageSaveErrorText, 'info');
                    return;
                }
                if (!commitUrl) {
                    this.messageSaveErrorText = '캘린더 저장 경로를 찾지 못했습니다.';
                    showFeedback(this.messageSaveErrorText, 'error');
                    return;
                }
                if (!csrfToken) {
                    this.messageSaveErrorText = '보안 토큰을 확인할 수 없습니다.';
                    showFeedback(this.messageSaveErrorText, 'error');
                    return;
                }

                this.messageSaveErrorText = '';
                this.isCommittingMessageSave = true;

                try {
                    response = await fetch(commitUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: JSON.stringify({
                            selected_candidates: [
                                {
                                    candidate_id: activeCandidate.id,
                                    selected: true,
                                    kind: activeCandidate.kind,
                                    title: activeCandidate.title,
                                    start_time: activeCandidate.start_time,
                                    end_time: activeCandidate.end_time,
                                    is_all_day: activeCandidate.is_all_day,
                                    summary: activeCandidate.summary || '',
                                },
                            ],
                            selected_attachment_ids: [],
                        }),
                    });
                    payload = await response.json().catch(function () {
                        return {};
                    });
                    if (!response.ok) {
                        throw new Error(payload.detail || payload.error || payload.message || '캘린더에 저장하지 못했습니다.');
                    }
                    this.messageSaveCommitResult = this.clonePayload(payload);
                    this.messageSaveStage = 'committed';
                    this.agentPreviewMeta = {
                        source: 'direct',
                        provider: 'messagebox',
                        model: '',
                        providerLabel: '캘린더 저장',
                    };
                    this.agentPreview = this.normalizePreview({
                        badge: this.activeMode.label || '메시지 저장',
                        title: '캘린더 저장 완료',
                        summary: '',
                        sections: [
                            {
                                title: '결과',
                                items: this.messageSaveResultLines(),
                            },
                        ],
                        note: '',
                    }, this.agentPreviewMeta);
                    showFeedback(payload.message || '선택한 일정을 저장했어요.', 'success');
                } catch (error) {
                    this.messageSaveErrorText = error && error.message ? error.message : '캘린더에 저장하지 못했습니다.';
                    showFeedback(this.messageSaveErrorText, 'error');
                } finally {
                    this.isCommittingMessageSave = false;
                }
            },

            resetMessageSaveChat: function () {
                this.workspaceInput = '';
                this.showIdlePreview();
                this.focusWorkspace();
            },

            copyMessageSaveDraft: async function () {
                var lines = [];
                if (this.messageSaveStage === 'extracted') {
                    lines = this.messageSaveCandidateList().map(function (candidate) {
                        return [candidate.when, candidate.title].filter(Boolean).join(' · ');
                    });
                    if (!lines.length) {
                        lines = this.messageSaveWarnings();
                    }
                    if (!lines.length) {
                        lines = this.messageSaveResultLines();
                    }
                } else if (this.messageSaveStage === 'committed') {
                    lines = this.messageSaveResultLines();
                } else if (this.messageSaveStage === 'saved') {
                    lines = this.messageSaveResultLines();
                } else {
                    lines = this.messageSaveDraftLines();
                }
                if (!lines.length) {
                    showFeedback('복사할 메시지가 없습니다.', 'info');
                    return;
                }
                try {
                    await navigator.clipboard.writeText(lines.join('\n'));
                    showFeedback('메시지를 복사했습니다.', 'success');
                } catch (error) {
                    showFeedback('복사하지 못했습니다.', 'error');
                }
            },

            parseDateTimeLocalParts: function (value) {
                var text = trimLine(value);
                var match = text.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
                var weekdays = ['일', '월', '화', '수', '목', '금', '토'];
                var year;
                var monthIndex;
                var day;
                var hour;
                var minute;
                var date;
                if (!match) {
                    return null;
                }
                year = Number(match[1]);
                monthIndex = Number(match[2]) - 1;
                day = Number(match[3]);
                hour = Number(match[4]);
                minute = Number(match[5]);
                date = new Date(year, monthIndex, day, hour, minute);
                if (Number.isNaN(date.getTime())) {
                    return null;
                }
                return {
                    month: monthIndex + 1,
                    day: day,
                    weekday: weekdays[date.getDay()],
                    hour: match[4],
                    minute: match[5],
                    time: match[4] + ':' + match[5],
                };
            },

            scheduleUserBubbleText: function () {
                return trimLine(this.workspaceInput);
            },

            scheduleHasExecution: function () {
                return Boolean(this.agentExecution && this.agentExecution.kind === 'schedule' && this.agentExecutionDraft && this.agentExecutionDraft.start_time);
            },

            scheduleHasResult: function () {
                return Boolean(this.scheduleHasExecution() || this.previewResultLines().length);
            },

            scheduleHasConversation: function () {
                return Boolean(this.scheduleUserBubbleText() || this.isAgentLoading || this.scheduleHasResult());
            },

            scheduleDraftHeading: function () {
                var preview = this.agentPreview && typeof this.agentPreview === 'object' ? this.agentPreview : {};
                if (this.scheduleHasExecution()) {
                    return this.scheduleWarnings().length ? '시간 확인' : '일정 후보';
                }
                return trimLine(preview.title || '일정 후보');
            },

            scheduleQuickExamples: function () {
                return [
                    { label: '상담', text: '학부모님, 다음 주 수요일 오후 3시에 상담 가능합니다. 학교 상담실로 와 주세요.' },
                    { label: '회의', text: '금요일 14시에 학년 회의실에서 회의합니다. 자료는 10분 전까지 올려 주세요.' },
                    { label: '행사', text: '4월 25일 오전 9시 운동장 집합입니다. 체육대회 준비물은 물과 모자입니다.' },
                    { label: '변경', text: '내일 2교시 과학실 수업이 4교시로 바뀝니다. 실험 준비물은 그대로 가져옵니다.' },
                ];
            },

            runScheduleExample: function (text) {
                var value = trimLine(text);
                if (!value) {
                    return;
                }
                this.workspaceInput = value;
                this.scheduleEditorOpen = false;
                this.runAgentPreview(value);
            },

            scheduleDraftDateLabel: function () {
                var start = this.parseDateTimeLocalParts(this.agentExecutionDraft && this.agentExecutionDraft.start_time);
                if (!start) {
                    return '';
                }
                return start.month + '월 ' + start.day + '일 ' + start.weekday + '요일';
            },

            scheduleDraftTimeLabel: function () {
                var start = this.parseDateTimeLocalParts(this.agentExecutionDraft && this.agentExecutionDraft.start_time);
                var end = this.parseDateTimeLocalParts(this.agentExecutionDraft && this.agentExecutionDraft.end_time);
                if (this.agentExecutionDraft && this.agentExecutionDraft.is_all_day) {
                    return '하루 종일';
                }
                if (!start) {
                    return '';
                }
                if (!end) {
                    return start.time;
                }
                return start.time + ' - ' + end.time;
            },

            scheduleChoiceList: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'schedule') {
                    return [];
                }
                return (this.agentExecution.choices || []).map(function (choice) {
                    var values = choice && typeof choice.values === 'object' ? choice.values : {};
                    var start = this.parseDateTimeLocalParts(values.start_time);
                    var end = this.parseDateTimeLocalParts(values.end_time);
                    var label = '';
                    if (values.is_all_day && start) {
                        label = start.month + '/' + start.day + ' 하루';
                    } else if (start && end) {
                        label = start.time + ' - ' + end.time;
                    } else if (start) {
                        label = start.time;
                    }
                    if (!label) {
                        label = trimLine(choice.label) || '후보';
                    }
                    return {
                        id: String(choice.id || ''),
                        label: label,
                    };
                }, this).filter(function (choice) {
                    return choice.id && choice.label;
                });
            },

            scheduleSelectedChoiceId: function () {
                return String(this.agentExecutionDraft && this.agentExecutionDraft.choice_id ? this.agentExecutionDraft.choice_id : '');
            },

            scheduleWarnings: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'schedule') {
                    return [];
                }
                return Array.isArray(this.agentExecution.warnings) ? this.agentExecution.warnings : [];
            },

            toggleScheduleEditor: function () {
                this.scheduleEditorOpen = !this.scheduleEditorOpen;
                if (this.scheduleEditorOpen) {
                    this.focusAgentExecutionField('title');
                }
            },

            resetScheduleChat: function () {
                this.workspaceInput = '';
                this.scheduleEditorOpen = false;
                this.showIdlePreview();
                this.focusWorkspace();
            },

            copyScheduleDraft: async function () {
                var lines;
                if (this.scheduleHasExecution()) {
                    lines = [
                        this.scheduleDraftDateLabel(),
                        this.scheduleDraftTimeLabel(),
                        trimLine(this.agentExecutionDraft.title || '새 일정'),
                    ].filter(Boolean);
                } else {
                    lines = this.previewResultLines();
                }
                if (!lines.length) {
                    showFeedback('복사할 일정이 없습니다.', 'info');
                    return;
                }
                try {
                    await navigator.clipboard.writeText(lines.join('\n'));
                    showFeedback('일정을 복사했습니다.', 'success');
                } catch (error) {
                    showFeedback('복사하지 못했습니다.', 'error');
                }
            },

            reservationUserBubbleText: function () {
                return trimLine(this.workspaceInput);
            },

            reservationHasExecution: function () {
                return Boolean(this.agentExecution && this.agentExecution.kind === 'reservation');
            },

            reservationHasResult: function () {
                return Boolean(this.reservationHasExecution() || this.previewResultLines().length);
            },

            reservationHasConversation: function () {
                return Boolean(this.reservationUserBubbleText() || this.isAgentLoading || this.reservationHasResult());
            },

            reservationDraftHeading: function () {
                var preview = this.agentPreview && typeof this.agentPreview === 'object' ? this.agentPreview : {};
                var previewTitle = trimLine(preview.title);
                if (previewTitle === '예약을 넣었습니다.') {
                    return previewTitle;
                }
                if (this.reservationHasExecution()) {
                    return this.reservationWarnings().length ? '추가 확인' : '예약 제안';
                }
                return previewTitle || '예약 제안';
            },

            reservationQuickExamples: function () {
                return [
                    { label: '과학실', text: '다음 주 화요일 3교시에 과학실 예약해줘.' },
                    { label: '음악실', text: '금요일 5교시에 음악실 예약해줘.' },
                    { label: '미술실', text: '4월 25일 2교시에 미술실 사용하려고 해.' },
                    { label: '컴퓨터실', text: '다음 주 목요일 4교시에 컴퓨터실 예약해줘.' },
                ];
            },

            runReservationExample: function (text) {
                var value = trimLine(text);
                if (!value) {
                    return;
                }
                this.workspaceInput = value;
                this.runAgentPreview(value);
            },

            reservationWarnings: function () {
                if (!this.agentExecution || this.agentExecution.kind !== 'reservation') {
                    return [];
                }
                return Array.isArray(this.agentExecution.warnings) ? this.agentExecution.warnings : [];
            },

            reservationBoardLabel: function () {
                var school = this.selectedReservationSchool();
                return school ? school.name : '예약판';
            },

            reservationDateLabel: function () {
                var text = trimLine(this.agentExecutionDraft && this.agentExecutionDraft.date);
                var match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
                var weekdays = ['일', '월', '화', '수', '목', '금', '토'];
                var date;
                if (!match) {
                    return '날짜 확인';
                }
                date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
                if (Number.isNaN(date.getTime())) {
                    return '날짜 확인';
                }
                return Number(match[2]) + '월 ' + Number(match[3]) + '일 ' + weekdays[date.getDay()] + '요일';
            },

            selectedReservationRoom: function () {
                var roomId = String(this.agentExecutionDraft && this.agentExecutionDraft.room_id ? this.agentExecutionDraft.room_id : '');
                return this.reservationRoomOptions().find(function (room) {
                    return String(room.id) === roomId;
                }) || null;
            },

            selectedReservationPeriod: function () {
                var periodId = String(this.agentExecutionDraft && this.agentExecutionDraft.period ? this.agentExecutionDraft.period : '');
                return this.reservationPeriodOptions().find(function (period) {
                    return String(period.id) === periodId;
                }) || null;
            },

            reservationTimeLabel: function () {
                var period = this.selectedReservationPeriod();
                return period ? trimLine(period.displayLabel || period.label) : '교시 선택';
            },

            reservationRoomLabel: function () {
                var room = this.selectedReservationRoom();
                return room ? room.name : '장소 선택';
            },

            reservationIsClassOwner: function () {
                return trimLine(this.agentExecutionDraft && this.agentExecutionDraft.owner_type) !== 'custom';
            },

            reservationPartyLabel: function () {
                var name = trimLine(this.agentExecutionDraft && this.agentExecutionDraft.name);
                if (this.reservationIsClassOwner()) {
                    var grade = trimLine(this.agentExecutionDraft && this.agentExecutionDraft.grade);
                    var classNo = trimLine(this.agentExecutionDraft && this.agentExecutionDraft.class_no);
                    var party = [grade ? grade + '학년' : '', classNo ? classNo + '반' : ''].filter(Boolean).join(' ');
                    return [party, name].filter(Boolean).join(' ').trim() || '대상 확인';
                }
                return [trimLine(this.agentExecutionDraft && this.agentExecutionDraft.target_label), name].filter(Boolean).join(' ').trim() || '대상 확인';
            },

            reservationSetSchool: function (schoolSlug) {
                if (!this.reservationHasExecution()) {
                    return;
                }
                this.agentExecutionDraft.school_slug = trimLine(schoolSlug);
                this.clearExecutionFieldError('school_slug');
                this.clearExecutionFieldError('room_id');
                this.clearExecutionFieldError('period');
                this.normalizeExecutionDraft();
            },

            reservationSetRoom: function (roomId) {
                if (!this.reservationHasExecution()) {
                    return;
                }
                this.agentExecutionDraft.room_id = String(roomId || '');
                this.clearExecutionFieldError('room_id');
            },

            reservationSetPeriod: function (periodId) {
                if (!this.reservationHasExecution()) {
                    return;
                }
                this.agentExecutionDraft.period = String(periodId || '');
                this.clearExecutionFieldError('period');
                this.clearExecutionFieldError('override_grade_lock');
            },

            reservationSetOwnerType: function (ownerType) {
                if (!this.reservationHasExecution()) {
                    return;
                }
                this.agentExecutionDraft.owner_type = trimLine(ownerType) === 'custom' ? 'custom' : 'class';
                this.clearExecutionFieldError('grade');
                this.clearExecutionFieldError('class_no');
                this.clearExecutionFieldError('target_label');
                this.clearExecutionFieldError('override_grade_lock');
                this.normalizeExecutionDraft();
            },

            resetReservationChat: function () {
                this.workspaceInput = '';
                this.showIdlePreview();
                this.focusWorkspace();
            },

            copyReservationDraft: async function () {
                var lines;
                if (this.reservationHasExecution()) {
                    lines = [
                        this.reservationBoardLabel(),
                        this.reservationDateLabel(),
                        this.reservationTimeLabel(),
                        this.reservationRoomLabel(),
                        this.reservationPartyLabel(),
                    ].filter(Boolean);
                } else {
                    lines = this.previewResultLines();
                }
                if (!lines.length) {
                    showFeedback('복사할 예약이 없습니다.', 'info');
                    return;
                }
                try {
                    await navigator.clipboard.writeText(lines.join('\n'));
                    showFeedback('예약 내용을 복사했습니다.', 'success');
                } catch (error) {
                    showFeedback('복사하지 못했습니다.', 'error');
                }
            },

            teacherLawUserBubbleText: function () {
                return trimLine(this.workspaceInput);
            },

            teacherLawHasExecution: function () {
                return Boolean(this.agentExecution && this.agentExecution.kind === 'teacher-law');
            },

            teacherLawHasResult: function () {
                return Boolean(this.teacherLawHasExecution() || this.previewResultLines().length);
            },

            teacherLawHasConversation: function () {
                return Boolean(this.teacherLawUserBubbleText() || this.isAgentLoading || this.teacherLawHasResult());
            },

            teacherLawDraftHeading: function () {
                var preview = this.agentPreview && typeof this.agentPreview === 'object' ? this.agentPreview : {};
                return trimLine(preview.title || '법률 답변');
            },

            teacherLawQuickExamples: function () {
                return [
                    { label: '학부모 민원', text: '학부모가 밤마다 전화를 반복합니다. 어떻게 대응해야 하나요?' },
                    { label: '생활지도', text: '생활지도 중 보호자가 항의 전화를 반복하고 있습니다. 기록은 어떻게 남겨야 하나요?' },
                    { label: '촬영/녹음', text: '수업 장면을 학부모가 녹음했다고 합니다. 먼저 무엇을 확인해야 하나요?' },
                    { label: '폭언', text: '학생 보호자가 통화 중 폭언을 했습니다. 어떤 순서로 대응하면 되나요?' },
                ];
            },

            runTeacherLawExample: function (text) {
                var value = trimLine(text);
                if (!value) {
                    return;
                }
                this.workspaceInput = value;
                this.runAgentPreview(value);
            },

            teacherLawNeedsSetup: function () {
                var preview = this.agentPreview && typeof this.agentPreview === 'object' ? this.agentPreview : {};
                var previewTitle = trimLine(preview.title);
                if (!this.teacherLawHasExecution()) {
                    return false;
                }
                if (previewTitle === '추가 확인') {
                    return true;
                }
                if (!trimLine(this.agentExecutionDraft.incident_type || '')) {
                    return true;
                }
                if (!trimLine(this.agentExecutionDraft.legal_goal || '')) {
                    return true;
                }
                if (this.teacherLawNeedsScene() && !trimLine(this.agentExecutionDraft.scene || '')) {
                    return true;
                }
                if (this.teacherLawNeedsCounterpart() && !trimLine(this.agentExecutionDraft.counterpart || '')) {
                    return true;
                }
                return false;
            },

            teacherLawSetField: function (fieldName, value) {
                var normalizedField = trimLine(fieldName);
                if (!normalizedField || !this.teacherLawHasExecution()) {
                    return;
                }
                this.agentExecutionDraft[normalizedField] = trimLine(value);
                this.clearExecutionFieldError(normalizedField);
                if (normalizedField === 'incident_type') {
                    this.clearExecutionFieldError('scene');
                    this.clearExecutionFieldError('counterpart');
                }
                this.normalizeExecutionDraft();
            },

            teacherLawPrimaryActionLabel: function () {
                return this.teacherLawNeedsSetup() ? '답변 보기' : '저장';
            },

            resetTeacherLawChat: function () {
                this.workspaceInput = '';
                this.showIdlePreview();
                this.focusWorkspace();
            },

            copyTeacherLawDraft: async function () {
                var lines = this.previewResultLines();
                if (!lines.length) {
                    showFeedback('복사할 답변이 없습니다.', 'info');
                    return;
                }
                try {
                    await navigator.clipboard.writeText(lines.join('\n'));
                    showFeedback('답변을 복사했습니다.', 'success');
                } catch (error) {
                    showFeedback('복사하지 못했습니다.', 'error');
                }
            },

            noticeUserBubbleText: function () {
                return trimLine(this.noticeBaseInput || this.workspaceInput);
            },

            noticeHasConversation: function () {
                return Boolean(this.noticeUserBubbleText() || this.isAgentLoading || this.previewResultLines().length);
            },

            noticeDraftTitle: function () {
                var label = trimLine(this.noticeRefinementLabel);
                if (label) {
                    return label + ' 초안';
                }
                var preview = this.agentPreview && typeof this.agentPreview === 'object' ? this.agentPreview : {};
                return trimLine(preview.title || '알림장 초안');
            },

            noticeQuickExamples: function () {
                return [
                    { label: '체험학습', text: '내일 체험학습, 8시 40분까지 등교, 도시락과 물 챙겨 주세요.' },
                    { label: '준비물', text: '내일 미술 준비물, 가위와 풀, 색종이를 보내 주세요.' },
                    { label: '일정 변경', text: '금요일 체육 수업이 실내 활동으로 바뀌었습니다. 실내화 준비해 주세요.' },
                    { label: '주간학습', text: '다음 주 주간학습 안내, 받아쓰기와 수학 익힘, 독서 기록장을 챙겨 주세요.' },
                ];
            },

            runNoticeExample: function (text) {
                var value = trimLine(text);
                if (!value) {
                    return;
                }
                this.noticeBaseInput = value;
                this.noticeRefinementLabel = '';
                this.workspaceInput = value;
                this.runAgentPreview(value);
            },

            rerunNoticeRefinement: function (label, instruction) {
                var baseText = trimLine(this.noticeBaseInput || this.workspaceInput);
                var refineText = trimLine(instruction);
                if (!baseText) {
                    this.focusWorkspace();
                    return;
                }
                this.noticeBaseInput = baseText;
                this.noticeRefinementLabel = trimLine(label);
                this.runAgentPreview([baseText, refineText].filter(Boolean).join('\n'));
            },

            resetNoticeChat: function () {
                this.workspaceInput = '';
                this.noticeBaseInput = '';
                this.noticeRefinementLabel = '';
                this.showIdlePreview();
                this.focusWorkspace();
            },

            copyNoticeDraft: async function () {
                var lines = this.previewResultLines();
                if (!lines.length) {
                    showFeedback('복사할 초안이 없습니다.', 'info');
                    return;
                }
                var text = lines.join('\n');
                try {
                    await navigator.clipboard.writeText(text);
                    showFeedback('초안을 복사했습니다.', 'success');
                } catch (error) {
                    showFeedback('복사하지 못했습니다.', 'error');
                }
            },

            selectAgentMode: function (modeKey) {
                if (this.activeModeKey === 'tts' && modeKey !== 'tts') {
                    this.isTtsReading = false;
                    if ('speechSynthesis' in window) {
                        window.speechSynthesis.cancel();
                    }
                }
                if (this.activeModeKey !== modeKey && (this.activeModeKey === 'message-save' || modeKey === 'message-save')) {
                    this.clearMessageSaveState();
                }
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

            runAgentPreview: async function (overrideText) {
                var text = trimLine(typeof overrideText === 'string' ? overrideText : this.workspaceInput);
                var previewStrategy = String(this.activeMode.preview_strategy || 'llm').toLowerCase();
                if (!text) {
                    this.showIdlePreview();
                    return;
                }
                if (this.activeModeKey === 'notice' && typeof overrideText !== 'string') {
                    this.noticeBaseInput = text;
                    this.noticeRefinementLabel = '';
                }
                if (this.activeModeKey === 'schedule') {
                    this.scheduleEditorOpen = false;
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
                    title: '전송 준비',
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
                    title: '읽기 문구',
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
                    title: '찾은 일정 후보',
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
                    this.playTtsDraft();
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
