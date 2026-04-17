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

    function buildSocketUrl(path) {
        var rawPath = String(path || '').trim();
        if (!rawPath) {
            return '';
        }
        if (rawPath.indexOf('ws://') === 0 || rawPath.indexOf('wss://') === 0) {
            return rawPath;
        }
        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return protocol + '//' + window.location.host + '/' + rawPath.replace(/^\/+/, '');
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

    function normalizeBrowserFiles(fileList) {
        return Array.prototype.slice.call(fileList || []).filter(Boolean);
    }

    function escapeRegExp(value) {
        return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
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
        var activePanelPositionFrame = 0;

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

        function cancelPendingClose() {
            if (!closeDelayTimer) {
                return;
            }
            window.clearTimeout(closeDelayTimer);
            closeDelayTimer = 0;
        }

        function cancelScheduledPanelPosition() {
            if (!activePanelPositionFrame) {
                return;
            }
            window.cancelAnimationFrame(activePanelPositionFrame);
            activePanelPositionFrame = 0;
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
            cancelScheduledPanelPosition();
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

        function positionActivePanels() {
            if (!activeGroup || !activeSectionKey) {
                return;
            }
            positionPanel(activeGroup, getGroupPanel(activeGroup, 'flyout'));
            positionPanel(activeGroup, getGroupPanel(activeGroup, 'tooltip'));
        }

        function scheduleActivePanelPosition() {
            if (!activeGroup || !activeSectionKey) {
                return;
            }
            cancelScheduledPanelPosition();
            activePanelPositionFrame = window.requestAnimationFrame(function () {
                activePanelPositionFrame = 0;
                positionActivePanels();
            });
        }

        syncRailState('');

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

        window.addEventListener('resize', scheduleActivePanelPosition);
        window.addEventListener('scroll', scheduleActivePanelPosition, true);

        document.addEventListener('click', function (event) {
            if (!rail.contains(event.target)) {
                cancelPendingClose();
                cancelScheduledPanelPosition();
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
            quickdropDragDepth: 0,
            isQuickdropDragActive: false,
            isTtsReading: false,
            workspaceInput: '',
            agentModeMenuOpen: false,
            railSearchText: '',
            activeModeKey: workspaceConfig.initial_mode || '',
            activeRailKey: workspaceConfig.initial_rail_key || '',
            activeConversationKey: '',
            agentModes: Array.isArray(workspaceConfig.modes) ? workspaceConfig.modes : [],
            agentRailSections: Array.isArray(workspaceConfig.rail_sections) ? workspaceConfig.rail_sections : [],
            agentConversationRail: workspaceConfig.conversations && typeof workspaceConfig.conversations === 'object'
                ? workspaceConfig.conversations
                : {},
            activeRoomSnapshot: null,
            isHumanChatLoading: false,
            isHumanChatSending: false,
            humanChatDraftText: '',
            humanChatErrorText: '',
            humanChatReplyTo: null,
            humanChatQueuedFiles: [],
            humanChatDragDepth: 0,
            isHumanChatDragActive: false,
            humanChatSelectedMessageIds: [],
            humanChatSelectedAssetIds: [],
            humanChatUtilityPanel: '',
            humanChatInviteEmail: '',
            humanChatInviteRole: '',
            humanChatLatestInviteUrl: '',
            humanChatInviteErrorText: '',
            isHumanChatCreatingInvite: false,
            humanChatDmMemberIds: [],
            humanChatDmRoomName: '',
            humanChatDmErrorText: '',
            isHumanChatCreatingDm: false,
            humanChatApplyingSuggestionIds: [],
            agentConversationContext: null,
            isSharingAgentPreviewToRoom: false,
            homeConversationSocket: null,
            homeActiveRoomSocket: null,
            homeActiveRoomSocketId: '',
            homeConversationRefreshTimer: 0,
            homeRoomRefreshTimer: 0,
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
                this.agentRailSections = Array.isArray(workspaceConfig.rail_sections) ? workspaceConfig.rail_sections : this.agentRailSections;
                this.agentConversationRail = workspaceConfig.conversations && typeof workspaceConfig.conversations === 'object'
                    ? workspaceConfig.conversations
                    : this.agentConversationRail;
                this.favoriteIds = normalizeIdList(frontendConfig.favoriteProductIds || parseJsonScript('home-favorite-ids-data', []));
                if (!this.activeModeKey && this.agentModes.length) {
                    this.activeModeKey = this.agentModes[0].key;
                }
                if (!this.activeRailKey) {
                    this.activeRailKey = 'service:' + String(this.activeModeKey || '');
                }
                this.showIdlePreview();
                this.connectHomeConversationSocket();
                var self = this;
                window.addEventListener('home-v6:favorites-updated', function (event) {
                    self.favoriteIds = normalizeIdList(event && event.detail ? event.detail.productIds : []);
                });
                window.addEventListener('beforeunload', function () {
                    self.disconnectHomeConversationSocket();
                    self.disconnectActiveRoomSocket();
                });
            },

            get activeMode() {
                return this.agentModes.find(function (mode) {
                    return mode.key === this.activeModeKey;
                }, this) || this.agentModes[0] || {};
            },

            get activeRendererKey() {
                if (this.activeRailItem && this.activeRailItem.kind === 'room') {
                    return trimLine(this.activeRailItem.renderer_key || 'human-chat');
                }
                return trimLine(this.activeMode.renderer_key || this.activeMode.key || '');
            },

            modeByKey: function (modeKey) {
                var targetKey = trimLine(modeKey);
                return this.agentModes.find(function (mode) {
                    return trimLine(mode && mode.key) === targetKey;
                }) || {};
            },

            modeHasCapability: function (mode, capabilityKey) {
                var capabilities = mode && typeof mode.capabilities === 'object' ? mode.capabilities : {};
                return Boolean(capabilities && capabilities[capabilityKey]);
            },

            activeModeStarterItems: function () {
                return Array.isArray(this.activeMode.starter_items) ? this.activeMode.starter_items : [];
            },

            activeModeRefinementActions: function () {
                return Array.isArray(this.activeMode.refinement_actions) ? this.activeMode.refinement_actions : [];
            },

            railSections: function () {
                return Array.isArray(this.agentRailSections) ? this.agentRailSections : [];
            },

            allRailItems: function () {
                return this.railSections().reduce(function (items, section) {
                    var sectionItems = Array.isArray(section && section.items) ? section.items : [];
                    return items.concat(sectionItems);
                }, []);
            },

            railItemByKey: function (itemKey) {
                var targetKey = trimLine(itemKey);
                return this.allRailItems().find(function (item) {
                    return trimLine(item && item.key) === targetKey;
                }) || null;
            },

            get activeRailItem() {
                return this.railItemByKey(this.activeRailKey);
            },

            get activeConversationItem() {
                var item = this.activeRailItem;
                return item && item.kind === 'room' ? item : null;
            },

            activeConversationItems: function () {
                var rail = this.agentConversationRail && typeof this.agentConversationRail === 'object'
                    ? this.agentConversationRail
                    : {};
                return Array.isArray(rail.items) ? rail.items : [];
            },

            railSearchQuery: function () {
                return trimLine(this.railSearchText).toLowerCase();
            },

            filteredAgentModes: function () {
                var query = this.railSearchQuery();
                if (!query) {
                    return this.agentModes;
                }
                return this.agentModes.filter(function (mode) {
                    var label = trimLine(mode && mode.label).toLowerCase();
                    var aliases = Array.isArray(mode && mode.aliases) ? mode.aliases : [];
                    return label.indexOf(query) !== -1 || aliases.some(function (alias) {
                        return trimLine(alias).toLowerCase().indexOf(query) !== -1;
                    });
                });
            },

            filteredAgentConversations: function () {
                var query = this.railSearchQuery();
                var items = this.activeConversationItems();
                if (!query) {
                    return items;
                }
                return items.filter(function (item) {
                    return trimLine(item && item.label).toLowerCase().indexOf(query) !== -1
                        || trimLine(item && item.summary).toLowerCase().indexOf(query) !== -1
                        || trimLine(item && item.meta).toLowerCase().indexOf(query) !== -1;
                });
            },

            filteredAgentRailSections: function () {
                var query = this.railSearchQuery();
                return this.railSections().map(function (section) {
                    var items = Array.isArray(section && section.items) ? section.items : [];
                    var filteredItems = !query
                        ? items
                        : items.filter(function (item) {
                            return trimLine(item && item.title).toLowerCase().indexOf(query) !== -1
                                || trimLine(item && item.summary).toLowerCase().indexOf(query) !== -1
                                || trimLine(item && item.meta).toLowerCase().indexOf(query) !== -1;
                        });
                    return {
                        key: trimLine(section && section.key),
                        label: trimLine(section && section.label),
                        items: filteredItems,
                    };
                }).filter(function (section) {
                    return section.items.length;
                });
            },

            railCountByKind: function (kind) {
                var targetKind = trimLine(kind);
                return this.allRailItems().filter(function (item) {
                    return trimLine(item && item.kind) === targetKind;
                }).length;
            },

            firstRailItemKeyByKind: function (kind) {
                var targetKind = trimLine(kind);
                var item = this.allRailItems().find(function (entry) {
                    return trimLine(entry && entry.kind) === targetKind;
                });
                return trimLine(item && item.key);
            },

            selectRailItem: async function (itemKey) {
                var item = this.railItemByKey(itemKey);
                if (!item) {
                    return;
                }
                if (item.kind === 'room') {
                    await this.selectHumanConversation(item.key);
                    return;
                }
                this.disconnectActiveRoomSocket();
                this.clearAgentConversationContext();
                this.selectAgentMode(item.mode_key || item.entity_key || '');
            },

            updateRailItem: function (itemKey, updater) {
                var targetKey = trimLine(itemKey);
                this.agentRailSections = this.railSections().map(function (section) {
                    return Object.assign({}, section, {
                        items: (Array.isArray(section.items) ? section.items : []).map(function (item) {
                            if (trimLine(item && item.key) !== targetKey) {
                                return item;
                            }
                            return updater(Object.assign({}, item)) || item;
                        }),
                    });
                });
            },

            activeHeaderTitle: function () {
                var room = this.activeRoomSnapshot && this.activeRoomSnapshot.room ? this.activeRoomSnapshot.room : null;
                if (this.activeConversationItem) {
                    return trimLine(room && room.name) || trimLine(this.activeConversationItem.title) || '끼리끼리 채팅방';
                }
                return trimLine(this.activeMode.label) || 'AI 교무비서';
            },

            activeHeaderMeta: function () {
                var room = this.activeRoomSnapshot && this.activeRoomSnapshot.room ? this.activeRoomSnapshot.room : null;
                if (this.activeConversationItem) {
                    return trimLine(room && room.room_kind_label) || trimLine(this.activeConversationItem.meta) || '대화';
                }
                return trimLine(this.activeMode.helper);
            },

            activeHeaderBadge: function () {
                return this.activeConversationItem ? '대화' : 'AI';
            },

            activeHeaderPrimaryHref: function () {
                var room = this.activeRoomSnapshot && this.activeRoomSnapshot.room ? this.activeRoomSnapshot.room : null;
                if (this.activeConversationItem) {
                    return trimLine(room && room.open_url) || trimLine(this.activeConversationItem.open_url);
                }
                return trimLine(this.activeMode.service_href);
            },

            activeHeaderPrimaryLabel: function () {
                if (this.activeConversationItem) {
                    return '채팅방 열기';
                }
                return trimLine(this.activeMode.service_label);
            },

            activeHeaderSecondaryHref: function () {
                return this.activeConversationItem ? '' : trimLine(this.activeMode.secondary_link_href);
            },

            activeHeaderSecondaryLabel: function () {
                return this.activeConversationItem ? '' : trimLine(this.activeMode.secondary_link_label);
            },

            humanChatSnapshotRoom: function () {
                return this.activeRoomSnapshot && this.activeRoomSnapshot.room ? this.activeRoomSnapshot.room : {};
            },

            humanChatComposerCapabilities: function () {
                return this.activeRoomSnapshot && typeof this.activeRoomSnapshot.composer_capabilities === 'object'
                    ? this.activeRoomSnapshot.composer_capabilities
                    : {};
            },

            humanChatSupportsReply: function () {
                return Boolean(this.humanChatComposerCapabilities().reply);
            },

            humanChatCanAttachFiles: function () {
                return Boolean(this.humanChatComposerCapabilities().file_attach);
            },

            humanChatSupportsReactions: function () {
                return Boolean(this.humanChatComposerCapabilities().reactions);
            },

            humanChatContextActions: function () {
                return Array.isArray(this.activeRoomSnapshot && this.activeRoomSnapshot.context_actions)
                    ? this.activeRoomSnapshot.context_actions
                    : [];
            },

            humanChatAssetsPanel: function () {
                return this.activeRoomSnapshot && typeof this.activeRoomSnapshot.assets_panel === 'object'
                    ? this.activeRoomSnapshot.assets_panel
                    : {};
            },

            humanChatHasAssetsPanel: function () {
                var panel = this.humanChatAssetsPanel();
                return Boolean(panel && panel.has_assets);
            },

            humanChatAssetSections: function () {
                var panel = this.humanChatAssetsPanel();
                return Array.isArray(panel.sections) ? panel.sections : [];
            },

            humanChatAssetsTotalCount: function () {
                var panel = this.humanChatAssetsPanel();
                return Number(panel.total_asset_count || 0);
            },

            humanChatCalendarSuggestions: function () {
                return Array.isArray(this.activeRoomSnapshot && this.activeRoomSnapshot.calendar_suggestions)
                    ? this.activeRoomSnapshot.calendar_suggestions
                    : [];
            },

            humanChatInviteConfig: function () {
                return this.activeRoomSnapshot && typeof this.activeRoomSnapshot.invite_actions === 'object'
                    ? this.activeRoomSnapshot.invite_actions
                    : {};
            },

            humanChatInviteRoles: function () {
                var config = this.humanChatInviteConfig();
                return Array.isArray(config.roles) ? config.roles : [];
            },

            humanChatCanCreateInvite: function () {
                var config = this.humanChatInviteConfig();
                return Boolean(config.can_create && trimLine(config.create_url));
            },

            humanChatDmConfig: function () {
                return this.activeRoomSnapshot && typeof this.activeRoomSnapshot.dm_actions === 'object'
                    ? this.activeRoomSnapshot.dm_actions
                    : {};
            },

            humanChatDmMembers: function () {
                var config = this.humanChatDmConfig();
                return Array.isArray(config.members) ? config.members : [];
            },

            humanChatCanCreateDm: function () {
                var config = this.humanChatDmConfig();
                return Boolean(trimLine(config.create_url));
            },

            humanChatAllAssets: function () {
                return this.humanChatMessages().reduce(function (items, message) {
                    var assets = Array.isArray(message && message.assets) ? message.assets : [];
                    assets.forEach(function (asset) {
                        items.push(Object.assign({}, asset, {
                            message_id: trimLine(message && message.id),
                            message_body: trimLine(message && message.body),
                            sender_name: trimLine(message && message.sender_name),
                        }));
                    });
                    return items;
                }, []);
            },

            humanChatMessageById: function (messageId) {
                var targetId = trimLine(messageId);
                if (!targetId) {
                    return null;
                }
                return this.humanChatMessages().find(function (message) {
                    return trimLine(message && message.id) === targetId;
                }) || null;
            },

            humanChatSelectedMessages: function () {
                return (Array.isArray(this.humanChatSelectedMessageIds) ? this.humanChatSelectedMessageIds : [])
                    .map(function (messageId) {
                        return this.humanChatMessageById(messageId);
                    }, this)
                    .filter(Boolean);
            },

            humanChatSelectedAssets: function () {
                var selectedIds = Array.isArray(this.humanChatSelectedAssetIds) ? this.humanChatSelectedAssetIds : [];
                var assets = this.humanChatAllAssets();
                return selectedIds.map(function (assetId) {
                    return assets.find(function (asset) {
                        return trimLine(asset && asset.id) === trimLine(assetId);
                    }) || null;
                }).filter(Boolean);
            },

            humanChatIsMessageSelected: function (messageId) {
                var targetId = trimLine(messageId);
                return Boolean(targetId && Array.isArray(this.humanChatSelectedMessageIds) && this.humanChatSelectedMessageIds.indexOf(targetId) !== -1);
            },

            humanChatIsAssetSelected: function (assetId) {
                var targetId = trimLine(assetId);
                return Boolean(targetId && Array.isArray(this.humanChatSelectedAssetIds) && this.humanChatSelectedAssetIds.indexOf(targetId) !== -1);
            },

            toggleHumanChatMessageSelection: function (message) {
                var messageId = trimLine(message && message.id);
                if (!messageId) {
                    return;
                }
                var selected = Array.isArray(this.humanChatSelectedMessageIds) ? this.humanChatSelectedMessageIds.slice() : [];
                if (selected.indexOf(messageId) !== -1) {
                    this.humanChatSelectedMessageIds = selected.filter(function (value) {
                        return value !== messageId;
                    });
                    return;
                }
                selected.push(messageId);
                this.humanChatSelectedMessageIds = selected.slice(0, 6);
            },

            toggleHumanChatAssetSelection: function (asset) {
                var assetId = trimLine(asset && asset.id);
                if (!assetId) {
                    return;
                }
                var selected = Array.isArray(this.humanChatSelectedAssetIds) ? this.humanChatSelectedAssetIds.slice() : [];
                if (selected.indexOf(assetId) !== -1) {
                    this.humanChatSelectedAssetIds = selected.filter(function (value) {
                        return value !== assetId;
                    });
                    return;
                }
                selected.push(assetId);
                this.humanChatSelectedAssetIds = selected.slice(0, 6);
            },

            humanChatHasSelection: function () {
                return Boolean(
                    (Array.isArray(this.humanChatSelectedMessageIds) && this.humanChatSelectedMessageIds.length)
                    || (Array.isArray(this.humanChatSelectedAssetIds) && this.humanChatSelectedAssetIds.length)
                );
            },

            clearHumanChatSelection: function () {
                this.humanChatSelectedMessageIds = [];
                this.humanChatSelectedAssetIds = [];
            },

            syncHumanChatSelection: function () {
                var availableMessageIds = this.humanChatMessages().map(function (message) {
                    return trimLine(message && message.id);
                }).filter(Boolean);
                var availableAssetIds = this.humanChatAllAssets().map(function (asset) {
                    return trimLine(asset && asset.id);
                }).filter(Boolean);
                this.humanChatSelectedMessageIds = (Array.isArray(this.humanChatSelectedMessageIds) ? this.humanChatSelectedMessageIds : []).filter(function (messageId) {
                    return availableMessageIds.indexOf(trimLine(messageId)) !== -1;
                });
                this.humanChatSelectedAssetIds = (Array.isArray(this.humanChatSelectedAssetIds) ? this.humanChatSelectedAssetIds : []).filter(function (assetId) {
                    return availableAssetIds.indexOf(trimLine(assetId)) !== -1;
                });
            },

            humanChatSelectionSummary: function () {
                var messageCount = (Array.isArray(this.humanChatSelectedMessageIds) ? this.humanChatSelectedMessageIds.length : 0);
                var assetCount = (Array.isArray(this.humanChatSelectedAssetIds) ? this.humanChatSelectedAssetIds.length : 0);
                var parts = [];
                if (messageCount) {
                    parts.push('메시지 ' + messageCount);
                }
                if (assetCount) {
                    parts.push('자료 ' + assetCount);
                }
                return parts.join(' · ');
            },

            toggleHumanChatUtilityPanel: function (panelKey) {
                var nextKey = trimLine(panelKey);
                this.humanChatUtilityPanel = this.humanChatUtilityPanel === nextKey ? '' : nextKey;
                this.humanChatInviteErrorText = '';
                this.humanChatDmErrorText = '';
                if (!this.humanChatInviteRole) {
                    this.humanChatInviteRole = trimLine(this.humanChatInviteConfig().default_role) || 'member';
                }
            },

            closeHumanChatUtilityPanel: function () {
                this.humanChatUtilityPanel = '';
                this.humanChatInviteErrorText = '';
                this.humanChatDmErrorText = '';
            },

            humanChatIsDmMemberSelected: function (userId) {
                return Boolean(Array.isArray(this.humanChatDmMemberIds) && this.humanChatDmMemberIds.indexOf(trimLine(userId)) !== -1);
            },

            toggleHumanChatDmMember: function (userId) {
                var memberId = trimLine(userId);
                var maxMembers = Number(this.humanChatDmConfig().max_members || 4);
                var selected = Array.isArray(this.humanChatDmMemberIds) ? this.humanChatDmMemberIds.slice() : [];
                if (!memberId) {
                    return;
                }
                if (selected.indexOf(memberId) !== -1) {
                    this.humanChatDmMemberIds = selected.filter(function (value) {
                        return value !== memberId;
                    });
                    return;
                }
                if (selected.length >= maxMembers) {
                    this.humanChatDmErrorText = '최대 ' + maxMembers + '명까지 선택할 수 있습니다.';
                    return;
                }
                selected.push(memberId);
                this.humanChatDmErrorText = '';
                this.humanChatDmMemberIds = selected;
            },

            buildHumanChatContextText: function () {
                var lines = [];
                var selectedMessages = this.humanChatSelectedMessages();
                var selectedAssets = this.humanChatSelectedAssets();
                var room = this.humanChatSnapshotRoom();

                selectedMessages.forEach(function (message) {
                    var body = trimLine(message && (message.body || message.parent_preview));
                    if (!body) {
                        return;
                    }
                    var prefix = trimLine(message && message.sender_name);
                    lines.push(prefix ? prefix + ': ' + body : body);
                });

                selectedAssets.forEach(function (asset) {
                    var name = trimLine(asset && asset.original_name);
                    if (name) {
                        lines.push('첨부: ' + name);
                    }
                });

                if (!lines.length) {
                    this.humanChatMessages().slice(-3).forEach(function (message) {
                        var body = trimLine(message && message.body);
                        if (!body) {
                            return;
                        }
                        var prefix = trimLine(message && message.sender_name);
                        lines.push(prefix ? prefix + ': ' + body : body);
                    });
                }

                if (!lines.length) {
                    var summary = trimLine(this.activeConversationItem && this.activeConversationItem.summary);
                    if (summary) {
                        lines.push(summary);
                    }
                }

                if (!lines.length) {
                    var title = trimLine(room && room.name);
                    if (title) {
                        lines.push(title);
                    }
                }

                return lines.filter(Boolean).join('\n');
            },

            setAgentConversationContext: function () {
                var room = this.humanChatSnapshotRoom();
                var item = this.activeConversationItem;
                this.agentConversationContext = {
                    conversation_key: trimLine(item && item.key),
                    room_id: trimLine(room && room.id),
                    room_title: trimLine(room && room.name),
                    room_kind: trimLine(room && room.room_kind),
                    can_post_top_level: Boolean(room && room.can_post_top_level),
                    selected_message_ids: (Array.isArray(this.humanChatSelectedMessageIds) ? this.humanChatSelectedMessageIds : []).slice(),
                    selected_asset_ids: (Array.isArray(this.humanChatSelectedAssetIds) ? this.humanChatSelectedAssetIds : []).slice(),
                    selected_message_texts: this.humanChatSelectedMessages().map(function (message) {
                        return trimLine(message && (message.body || message.parent_preview));
                    }).filter(Boolean).slice(0, 4),
                    selected_asset_names: this.humanChatSelectedAssets().map(function (asset) {
                        return trimLine(asset && asset.original_name);
                    }).filter(Boolean).slice(0, 4),
                };
            },

            clearAgentConversationContext: function () {
                this.agentConversationContext = null;
                this.isSharingAgentPreviewToRoom = false;
            },

            hasAgentConversationContext: function () {
                return Boolean(this.agentConversationContext && trimLine(this.agentConversationContext.conversation_key));
            },

            agentConversationContextItem: function () {
                return this.hasAgentConversationContext()
                    ? this.railItemByKey(this.agentConversationContext.conversation_key)
                    : null;
            },

            agentConversationContextTitle: function () {
                var item = this.agentConversationContextItem();
                var context = this.agentConversationContext || {};
                return trimLine(item && item.title) || trimLine(context.room_title) || '대화';
            },

            launchHumanChatContextAction: function (action) {
                var modeKey = trimLine(action && action.mode_key);
                if (!modeKey) {
                    return;
                }
                this.setAgentConversationContext();
                this.workspaceInput = this.buildHumanChatContextText();
                this.humanChatUtilityPanel = '';
                this.selectAgentMode(modeKey);
            },

            returnToAgentConversationContext: async function () {
                var item = this.agentConversationContextItem();
                var itemKey = trimLine(item && item.key);
                this.clearAgentConversationContext();
                if (itemKey) {
                    await this.selectHumanConversation(itemKey);
                }
            },

            buildShareableAgentPreviewText: function () {
                var lines = this.previewResultLines().slice();
                if (this.activeRendererKey === 'schedule' && this.scheduleHasExecution()) {
                    lines = [
                        trimLine(this.agentExecutionDraft && this.agentExecutionDraft.title),
                        trimLine(this.scheduleDraftDateLabel()),
                        trimLine(this.scheduleDraftTimeLabel()),
                    ].filter(Boolean);
                }
                if (this.activeRendererKey === 'reservation' && this.reservationHasExecution()) {
                    lines = [
                        trimLine(this.reservationRoomLabel()),
                        trimLine(this.reservationDateLabel()),
                        trimLine(this.reservationTimeLabel()),
                        trimLine(this.reservationPartyLabel()),
                    ].filter(Boolean);
                }
                return lines.filter(Boolean).join('\n');
            },

            canSharePreviewToContextConversation: function () {
                var item = this.agentConversationContextItem();
                var context = this.agentConversationContext || {};
                if (!item || !trimLine(item.send_url)) {
                    return false;
                }
                if (String(context.room_kind || '') === 'notice' && !context.can_post_top_level) {
                    return false;
                }
                return Boolean(trimLine(this.buildShareableAgentPreviewText()));
            },

            shareAgentPreviewToContextConversation: async function () {
                var item = this.agentConversationContextItem();
                var csrfToken = getCsrfToken();
                var text = trimLine(this.buildShareableAgentPreviewText());
                if (!item || !trimLine(item.send_url) || !text) {
                    showFeedback('공유할 내용을 아직 만들지 못했습니다.', 'info');
                    return;
                }
                if (!csrfToken) {
                    showFeedback('보안 토큰을 확인할 수 없습니다.', 'error');
                    return;
                }
                this.isSharingAgentPreviewToRoom = true;
                try {
                    var formData = new FormData();
                    formData.append('text', text);
                    var response = await fetch(item.send_url, {
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
                    if (!response.ok || payload.status !== 'success') {
                        throw new Error(payload.error || '대화방에 공유하지 못했습니다.');
                    }
                    showFeedback('대화방에 공유했습니다.', 'success');
                    await this.refreshConversationRail();
                    await this.returnToAgentConversationContext();
                } catch (error) {
                    showFeedback(error && error.message ? error.message : '대화방에 공유하지 못했습니다.', 'error');
                } finally {
                    this.isSharingAgentPreviewToRoom = false;
                }
            },

            applyConversationPayload: function (conversations) {
                var payload = conversations && typeof conversations === 'object' ? conversations : {};
                var roomItems = Array.isArray(payload.items) ? payload.items : [];
                this.agentConversationRail = payload;
                this.agentRailSections = this.railSections().map(function (section) {
                    if (trimLine(section && section.key) !== 'rooms') {
                        return section;
                    }
                    return Object.assign({}, section, {
                        label: trimLine(payload.title) || trimLine(section && section.label) || '끼리끼리 채팅방',
                        items: roomItems,
                    });
                });
                if (this.activeConversationItem && !roomItems.some(function (item) {
                    return trimLine(item && item.key) === trimLine(this.activeRailKey);
                }, this)) {
                    this.disconnectActiveRoomSocket();
                    this.activeRoomSnapshot = null;
                    this.activeConversationKey = '';
                    this.activeRailKey = 'service:' + trimLine(this.activeModeKey || 'notice');
                }
            },

            refreshConversationRail: async function () {
                var refreshUrl = trimLine(
                    (this.agentConversationRail && this.agentConversationRail.refresh_url)
                    || (workspaceConfig.conversations && workspaceConfig.conversations.refresh_url)
                );
                if (!refreshUrl) {
                    return;
                }
                var response = await fetch(refreshUrl, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });
                var payload = {};
                try {
                    payload = await response.json();
                } catch (jsonError) {
                    payload = {};
                }
                if (!response.ok || payload.status !== 'ok') {
                    throw new Error(payload.error || '대화 목록을 불러오지 못했습니다.');
                }
                this.applyConversationPayload(payload.conversations);
            },

            scheduleConversationRailRefresh: function () {
                if (this.homeConversationRefreshTimer) {
                    window.clearTimeout(this.homeConversationRefreshTimer);
                }
                this.homeConversationRefreshTimer = window.setTimeout(function () {
                    this.refreshConversationRail().catch(function (error) {
                        console.warn('[home-v6] failed to refresh conversations', error);
                    });
                }.bind(this), 160);
            },

            scheduleHumanRoomRefresh: function () {
                if (this.homeRoomRefreshTimer) {
                    window.clearTimeout(this.homeRoomRefreshTimer);
                }
                this.homeRoomRefreshTimer = window.setTimeout(function () {
                    if (!this.activeConversationItem) {
                        return;
                    }
                    this.refreshHumanConversation({ preserveReply: true }).catch(function (error) {
                        console.warn('[home-v6] failed to refresh active room', error);
                    });
                    this.scheduleConversationRailRefresh();
                }.bind(this), 160);
            },

            disconnectHomeConversationSocket: function () {
                if (this.homeConversationSocket && typeof this.homeConversationSocket.close === 'function') {
                    try {
                        this.homeConversationSocket.onclose = null;
                        this.homeConversationSocket.close();
                    } catch (error) {
                        // Ignore close errors.
                    }
                }
                this.homeConversationSocket = null;
            },

            connectHomeConversationSocket: function () {
                var socketUrl = buildSocketUrl(
                    trimLine(
                        (this.agentConversationRail && this.agentConversationRail.user_ws_url)
                        || (workspaceConfig.conversations && workspaceConfig.conversations.user_ws_url)
                    )
                );
                if (!socketUrl || typeof window.WebSocket !== 'function') {
                    return;
                }
                this.disconnectHomeConversationSocket();
                var self = this;
                var socket = new window.WebSocket(socketUrl);
                this.homeConversationSocket = socket;
                socket.onmessage = function (event) {
                    try {
                        var data = JSON.parse(event.data || '{}');
                        if (data.type === 'notification.summary') {
                            self.scheduleConversationRailRefresh();
                        }
                    } catch (error) {
                        console.warn('[home-v6] failed to parse conversation socket payload', error);
                    }
                };
                socket.onclose = function () {
                    if (self.homeConversationSocket === socket) {
                        self.homeConversationSocket = null;
                        window.setTimeout(function () {
                            self.connectHomeConversationSocket();
                        }, 1200);
                    }
                };
            },

            disconnectActiveRoomSocket: function () {
                if (this.homeActiveRoomSocket && typeof this.homeActiveRoomSocket.close === 'function') {
                    try {
                        this.homeActiveRoomSocket.onclose = null;
                        this.homeActiveRoomSocket.close();
                    } catch (error) {
                        // Ignore close errors.
                    }
                }
                this.homeActiveRoomSocket = null;
                this.homeActiveRoomSocketId = '';
            },

            connectActiveRoomSocket: function () {
                var room = this.humanChatSnapshotRoom();
                var roomId = trimLine(room && room.id);
                var socketUrl = buildSocketUrl(trimLine(room && room.room_ws_url));
                if (!roomId || !socketUrl || typeof window.WebSocket !== 'function') {
                    this.disconnectActiveRoomSocket();
                    return;
                }
                if (this.homeActiveRoomSocket && this.homeActiveRoomSocketId === roomId) {
                    return;
                }
                this.disconnectActiveRoomSocket();
                var self = this;
                var socket = new window.WebSocket(socketUrl);
                this.homeActiveRoomSocket = socket;
                this.homeActiveRoomSocketId = roomId;
                socket.onmessage = function (event) {
                    try {
                        var data = JSON.parse(event.data || '{}');
                        if (!data.type || data.type === 'room.snapshot') {
                            return;
                        }
                        self.scheduleHumanRoomRefresh();
                    } catch (error) {
                        console.warn('[home-v6] failed to parse room socket payload', error);
                    }
                };
                socket.onclose = function () {
                    if (self.homeActiveRoomSocket === socket && self.homeActiveRoomSocketId === roomId) {
                        self.homeActiveRoomSocket = null;
                        window.setTimeout(function () {
                            if (self.activeConversationItem && trimLine(self.humanChatSnapshotRoom().id) === roomId) {
                                self.connectActiveRoomSocket();
                            }
                        }, 1200);
                    }
                };
            },

            isHumanChatSuggestionApplying: function (suggestionId) {
                return Array.isArray(this.humanChatApplyingSuggestionIds)
                    && this.humanChatApplyingSuggestionIds.indexOf(trimLine(suggestionId)) !== -1;
            },

            applyHumanChatCalendarSuggestion: async function (suggestion) {
                var applyUrl = trimLine(suggestion && suggestion.apply_url);
                var suggestionId = trimLine(suggestion && suggestion.id);
                var csrfToken = getCsrfToken();
                if (!applyUrl || !suggestionId || !csrfToken) {
                    showFeedback('일정을 넣지 못했습니다.', 'error');
                    return;
                }
                this.humanChatApplyingSuggestionIds = (Array.isArray(this.humanChatApplyingSuggestionIds) ? this.humanChatApplyingSuggestionIds : []).concat([suggestionId]);
                try {
                    var response = await fetch(applyUrl, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    var payload = {};
                    try {
                        payload = await response.json();
                    } catch (jsonError) {
                        payload = {};
                    }
                    if (!response.ok || payload.status !== 'success') {
                        throw new Error(payload.error || '일정을 넣지 못했습니다.');
                    }
                    showFeedback(payload.message || '캘린더에 넣었습니다.', 'success');
                    await this.refreshHumanConversation({ preserveReply: true });
                    await this.refreshConversationRail();
                } catch (error) {
                    showFeedback(error && error.message ? error.message : '일정을 넣지 못했습니다.', 'error');
                } finally {
                    this.humanChatApplyingSuggestionIds = (Array.isArray(this.humanChatApplyingSuggestionIds) ? this.humanChatApplyingSuggestionIds : []).filter(function (value) {
                        return value !== suggestionId;
                    });
                }
            },

            copyHumanChatInviteUrl: async function () {
                var inviteUrl = trimLine(this.humanChatLatestInviteUrl);
                if (!inviteUrl) {
                    return;
                }
                try {
                    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
                        await navigator.clipboard.writeText(inviteUrl);
                    }
                    showFeedback('초대 링크를 복사했습니다.', 'success');
                } catch (error) {
                    showFeedback('초대 링크를 복사하지 못했습니다.', 'error');
                }
            },

            submitHumanChatInvite: async function () {
                var config = this.humanChatInviteConfig();
                var createUrl = trimLine(config.create_url);
                var csrfToken = getCsrfToken();
                if (!createUrl || !csrfToken) {
                    this.humanChatInviteErrorText = '초대 링크를 만들 수 없습니다.';
                    return;
                }
                this.isHumanChatCreatingInvite = true;
                this.humanChatInviteErrorText = '';
                this.humanChatLatestInviteUrl = '';
                try {
                    var formData = new FormData();
                    if (trimLine(this.humanChatInviteEmail)) {
                        formData.append('email', trimLine(this.humanChatInviteEmail));
                    }
                    formData.append('role', trimLine(this.humanChatInviteRole || config.default_role || 'member'));
                    var response = await fetch(createUrl, {
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
                    if (!response.ok || payload.status !== 'success') {
                        throw new Error(payload.error || '초대 링크를 만들지 못했습니다.');
                    }
                    this.humanChatLatestInviteUrl = trimLine(payload.invite && payload.invite.url);
                    this.humanChatInviteEmail = '';
                    showFeedback('초대 링크를 만들었습니다.', 'success');
                } catch (error) {
                    this.humanChatInviteErrorText = error && error.message ? error.message : '초대 링크를 만들지 못했습니다.';
                    showFeedback(this.humanChatInviteErrorText, 'error');
                } finally {
                    this.isHumanChatCreatingInvite = false;
                }
            },

            submitHumanChatDm: async function () {
                var config = this.humanChatDmConfig();
                var createUrl = trimLine(config.create_url);
                var csrfToken = getCsrfToken();
                if (!createUrl || !csrfToken) {
                    this.humanChatDmErrorText = '대화를 만들 수 없습니다.';
                    return;
                }
                if (!Array.isArray(this.humanChatDmMemberIds) || !this.humanChatDmMemberIds.length) {
                    this.humanChatDmErrorText = '상대를 선택해 주세요.';
                    return;
                }
                this.isHumanChatCreatingDm = true;
                this.humanChatDmErrorText = '';
                try {
                    var formData = new FormData();
                    this.humanChatDmMemberIds.forEach(function (memberId) {
                        formData.append('user_ids', memberId);
                    });
                    if (trimLine(this.humanChatDmRoomName)) {
                        formData.append('name', trimLine(this.humanChatDmRoomName));
                    }
                    var response = await fetch(createUrl, {
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
                    if (!response.ok || payload.status !== 'success') {
                        throw new Error(payload.error || '대화를 만들지 못했습니다.');
                    }
                    this.humanChatDmMemberIds = [];
                    this.humanChatDmRoomName = '';
                    this.closeHumanChatUtilityPanel();
                    await this.refreshConversationRail();
                    if (payload.room && payload.room.id) {
                        await this.selectHumanConversation('room:' + String(payload.room.id));
                    }
                    showFeedback('새 대화를 시작했습니다.', 'success');
                } catch (error) {
                    this.humanChatDmErrorText = error && error.message ? error.message : '대화를 만들지 못했습니다.';
                    showFeedback(this.humanChatDmErrorText, 'error');
                } finally {
                    this.isHumanChatCreatingDm = false;
                }
            },

            quickdropDataTransferHasFiles: function (event) {
                var transfer = event && event.dataTransfer ? event.dataTransfer : null;
                var types = transfer && transfer.types ? Array.prototype.slice.call(transfer.types) : [];
                return types.indexOf('Files') !== -1;
            },

            resetQuickdropDragState: function () {
                this.quickdropDragDepth = 0;
                this.isQuickdropDragActive = false;
            },

            handleQuickdropDragEnter: function (event) {
                if (!this.quickdropDataTransferHasFiles(event)) {
                    return;
                }
                event.preventDefault();
                this.quickdropDragDepth += 1;
                this.isQuickdropDragActive = true;
            },

            handleQuickdropDragOver: function (event) {
                if (!this.quickdropDataTransferHasFiles(event)) {
                    return;
                }
                event.preventDefault();
                this.isQuickdropDragActive = true;
            },

            handleQuickdropDragLeave: function (event) {
                if (!this.quickdropDataTransferHasFiles(event)) {
                    return;
                }
                event.preventDefault();
                this.quickdropDragDepth = Math.max(0, this.quickdropDragDepth - 1);
                if (!this.quickdropDragDepth) {
                    this.isQuickdropDragActive = false;
                }
            },

            handleQuickdropDrop: function (event) {
                var transfer = event && event.dataTransfer ? event.dataTransfer : null;
                var files = normalizeBrowserFiles(transfer && transfer.files);
                var file = files[0] || null;
                this.resetQuickdropDragState();
                if (!file) {
                    return;
                }
                event.preventDefault();
                this.queueQuickdropFile(file, trimLine(file.name || ''));
                showFeedback('파일을 담았어요.', 'success');
            },

            clearHumanChatComposer: function () {
                this.humanChatDraftText = '';
                this.humanChatErrorText = '';
                this.humanChatReplyTo = null;
                this.humanChatQueuedFiles = [];
                this.humanChatDragDepth = 0;
                this.isHumanChatDragActive = false;
                this.humanChatUtilityPanel = '';
                this.humanChatInviteErrorText = '';
                this.humanChatDmErrorText = '';
                this.humanChatLatestInviteUrl = '';
                this.humanChatInviteEmail = '';
                this.humanChatDmMemberIds = [];
                this.humanChatDmRoomName = '';
                this.humanChatApplyingSuggestionIds = [];
                this.clearHumanChatSelection();
            },

            humanChatFileInput: function () {
                return document.querySelector('[data-home-v6-human-chat-file-input="true"]');
            },

            openHumanChatFilePicker: function () {
                var input = this.humanChatFileInput();
                if (input && typeof input.click === 'function') {
                    input.click();
                }
            },

            appendHumanChatFiles: function (files, options) {
                var sourceFiles = Array.isArray(files) ? files.filter(Boolean) : [];
                var nextFiles = Array.isArray(this.humanChatQueuedFiles) ? this.humanChatQueuedFiles.slice() : [];
                sourceFiles.forEach(function (file, index) {
                    var fallbackName = options && options.fromClipboard
                        ? inferQuickdropClipboardFilename(file)
                        : trimLine(file && file.name);
                    var displayName = trimLine(file && file.name) || fallbackName || ('file-' + Date.now());
                    nextFiles.push({
                        id: ['human-file', Date.now(), nextFiles.length, index].join(':'),
                        file: file,
                        name: displayName,
                        kind: String(file && file.type ? file.type : '').indexOf('image/') === 0 ? 'image' : 'file',
                    });
                });
                this.humanChatQueuedFiles = nextFiles.slice(0, 8);
                this.humanChatErrorText = '';
            },

            queueHumanChatFilesFromInput: function (event) {
                var input = event && event.target ? event.target : null;
                this.appendHumanChatFiles(normalizeBrowserFiles(input && input.files));
                if (input) {
                    input.value = '';
                }
            },

            removeHumanChatQueuedFile: function (fileId) {
                var targetId = trimLine(fileId);
                this.humanChatQueuedFiles = (Array.isArray(this.humanChatQueuedFiles) ? this.humanChatQueuedFiles : []).filter(function (item) {
                    return trimLine(item && item.id) !== targetId;
                });
            },

            humanChatHasFilesQueued: function () {
                return Array.isArray(this.humanChatQueuedFiles) && this.humanChatQueuedFiles.length > 0;
            },

            humanChatCanPostTopLevel: function () {
                var snapshot = this.activeRoomSnapshot && typeof this.activeRoomSnapshot === 'object' ? this.activeRoomSnapshot : {};
                var room = snapshot.room && typeof snapshot.room === 'object' ? snapshot.room : {};
                return Boolean(room.can_post_top_level);
            },

            humanChatCanSend: function () {
                var hasContent = trimLine(this.humanChatDraftText) || this.humanChatHasFilesQueued();
                return Boolean(hasContent && (this.humanChatCanPostTopLevel() || this.humanChatReplyTo));
            },

            handleHumanChatDragEnter: function (event) {
                if (!this.quickdropDataTransferHasFiles(event)) {
                    return;
                }
                event.preventDefault();
                this.humanChatDragDepth += 1;
                this.isHumanChatDragActive = true;
            },

            handleHumanChatDragOver: function (event) {
                if (!this.quickdropDataTransferHasFiles(event)) {
                    return;
                }
                event.preventDefault();
                this.isHumanChatDragActive = true;
            },

            handleHumanChatDragLeave: function (event) {
                if (!this.quickdropDataTransferHasFiles(event)) {
                    return;
                }
                event.preventDefault();
                this.humanChatDragDepth = Math.max(0, this.humanChatDragDepth - 1);
                if (!this.humanChatDragDepth) {
                    this.isHumanChatDragActive = false;
                }
            },

            handleHumanChatDrop: function (event) {
                var transfer = event && event.dataTransfer ? event.dataTransfer : null;
                var files = normalizeBrowserFiles(transfer && transfer.files);
                this.humanChatDragDepth = 0;
                this.isHumanChatDragActive = false;
                if (!files.length) {
                    return;
                }
                event.preventDefault();
                this.appendHumanChatFiles(files);
                showFeedback('파일을 담았어요.', 'success');
            },

            captureHumanChatPaste: function (event) {
                var clipboard = event && event.clipboardData ? event.clipboardData : null;
                var items = clipboard && clipboard.items ? Array.prototype.slice.call(clipboard.items) : [];
                var files = items.map(function (item) {
                    return item && item.kind === 'file' && typeof item.getAsFile === 'function' ? item.getAsFile() : null;
                }).filter(Boolean);
                if (!files.length) {
                    return;
                }
                event.preventDefault();
                this.appendHumanChatFiles(files, { fromClipboard: true });
                showFeedback('파일을 담았어요.', 'success');
            },

            humanChatMessages: function () {
                var snapshot = this.activeRoomSnapshot && typeof this.activeRoomSnapshot === 'object' ? this.activeRoomSnapshot : {};
                return Array.isArray(snapshot.messages) ? snapshot.messages : [];
            },

            humanChatComposerPlaceholder: function () {
                var room = this.activeRoomSnapshot && this.activeRoomSnapshot.room ? this.activeRoomSnapshot.room : {};
                return trimLine(room && room.composer_placeholder) || '메시지 입력';
            },

            humanChatReplyTargetId: function (message) {
                if (!message || typeof message !== 'object') {
                    return '';
                }
                return trimLine(message.parent_message_id || message.id);
            },

            setHumanChatReply: function (message) {
                if (!message || typeof message !== 'object') {
                    return;
                }
                this.humanChatReplyTo = {
                    id: this.humanChatReplyTargetId(message),
                    sender_name: trimLine(message.sender_name),
                    body: trimLine(message.body || message.parent_preview),
                };
                this.humanChatErrorText = '';
            },

            clearHumanChatReply: function () {
                this.humanChatReplyTo = null;
            },

            refreshHumanConversation: async function (options) {
                var item = this.activeConversationItem;
                var snapshotUrl = trimLine(item && item.snapshot_url);
                if (!item || !snapshotUrl) {
                    this.activeRoomSnapshot = null;
                    this.disconnectActiveRoomSocket();
                    return;
                }
                this.isHumanChatLoading = true;
                try {
                    var response = await fetch(snapshotUrl, {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    var payload = {};
                    try {
                        payload = await response.json();
                    } catch (jsonError) {
                        payload = {};
                    }
                    if (!response.ok || payload.status !== 'success') {
                        throw new Error(payload.error || '대화를 불러오지 못했습니다.');
                    }
                    this.activeRoomSnapshot = payload;
                    if (!this.humanChatInviteRole) {
                        this.humanChatInviteRole = trimLine(payload && payload.invite_actions && payload.invite_actions.default_role) || 'member';
                    }
                    this.syncHumanChatSelection();
                    this.connectActiveRoomSocket();
                    this.humanChatErrorText = '';
                    this.updateRailItem(item.key, function (current) {
                        var messages = Array.isArray(payload.messages) ? payload.messages : [];
                        var latestMessage = messages.length ? messages[messages.length - 1] : null;
                        return Object.assign({}, current, {
                            summary: trimLine(latestMessage && latestMessage.body) || current.summary || '',
                            unread_count: 0,
                            badge: '',
                        });
                    });
                    if (!(options && options.preserveReply)) {
                        this.humanChatReplyTo = null;
                    }
                } catch (error) {
                    this.humanChatErrorText = error && error.message ? error.message : '대화를 불러오지 못했습니다.';
                    showFeedback(this.humanChatErrorText, 'error');
                } finally {
                    this.isHumanChatLoading = false;
                }
            },

            selectHumanConversation: async function (itemKey) {
                var item = this.railItemByKey(itemKey);
                if (!item || item.kind !== 'room') {
                    return;
                }
                this.clearAgentConversationContext();
                if (this.activeMode && this.modeHasCapability(this.activeMode, 'tts_read')) {
                    this.isTtsReading = false;
                    if ('speechSynthesis' in window) {
                        window.speechSynthesis.cancel();
                    }
                }
                this.activeRailKey = item.key;
                this.activeConversationKey = item.key;
                this.agentModeMenuOpen = false;
                this.clearHumanChatComposer();
                await this.refreshHumanConversation();
            },

            sendHumanChat: async function () {
                var item = this.activeConversationItem;
                var sendUrl = trimLine(item && item.send_url);
                var csrfToken = getCsrfToken();
                if (!sendUrl) {
                    this.humanChatErrorText = '전송 경로를 찾지 못했습니다.';
                    showFeedback(this.humanChatErrorText, 'error');
                    return;
                }
                if (!csrfToken) {
                    this.humanChatErrorText = '보안 토큰을 확인할 수 없습니다.';
                    showFeedback(this.humanChatErrorText, 'error');
                    return;
                }
                if (!this.humanChatCanSend()) {
                    this.humanChatErrorText = '보낼 내용을 넣어 주세요.';
                    showFeedback(this.humanChatErrorText, 'info');
                    return;
                }

                this.isHumanChatSending = true;
                this.humanChatErrorText = '';
                try {
                    var formData = new FormData();
                    var draftText = trimLine(this.humanChatDraftText);
                    if (draftText) {
                        formData.append('text', draftText);
                    }
                    if (this.humanChatReplyTo && trimLine(this.humanChatReplyTo.id)) {
                        formData.append('parent_message_id', trimLine(this.humanChatReplyTo.id));
                    }
                    (Array.isArray(this.humanChatQueuedFiles) ? this.humanChatQueuedFiles : []).forEach(function (entry) {
                        if (entry && entry.file) {
                            formData.append('files', entry.file, entry.name || entry.file.name || 'upload');
                        }
                    });
                    var response = await fetch(sendUrl, {
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
                    if (!response.ok || payload.status !== 'success') {
                        throw new Error(payload.error || '전송하지 못했습니다.');
                    }
                    this.humanChatDraftText = '';
                    this.humanChatReplyTo = null;
                    this.humanChatQueuedFiles = [];
                    await this.refreshHumanConversation({ preserveReply: false });
                } catch (error) {
                    this.humanChatErrorText = error && error.message ? error.message : '전송하지 못했습니다.';
                    showFeedback(this.humanChatErrorText, 'error');
                } finally {
                    this.isHumanChatSending = false;
                }
            },

            toggleHumanChatReaction: async function (message) {
                var reactionUrl = trimLine(message && message.reaction_url);
                var csrfToken = getCsrfToken();
                if (!reactionUrl || !csrfToken) {
                    showFeedback('반응을 남기지 못했습니다.', 'error');
                    return;
                }
                try {
                    var response = await fetch(reactionUrl, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    var payload = {};
                    try {
                        payload = await response.json();
                    } catch (jsonError) {
                        payload = {};
                    }
                    if (!response.ok || payload.status !== 'success') {
                        throw new Error(payload.error || '반응을 남기지 못했습니다.');
                    }
                    await this.refreshHumanConversation({ preserveReply: true });
                } catch (error) {
                    showFeedback(error && error.message ? error.message : '반응을 남기지 못했습니다.', 'error');
                }
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

            resolveContinueQueryValue: function (source) {
                var payload = source && typeof source === 'object' ? source : {};
                var sourceType = trimLine(payload.source);
                var transform = trimLine(payload.transform);
                var value = '';
                if (sourceType === 'workspace_input') {
                    value = trimLine(this.workspaceInput);
                } else if (sourceType === 'execution_field') {
                    value = trimLine(this.agentExecutionDraft && this.agentExecutionDraft[payload.field]);
                }
                if (!value) {
                    return '';
                }
                if (transform === 'date') {
                    return String(value).slice(0, 10);
                }
                return value;
            },

            buildModeContinueHref: function (mode) {
                var targetMode = mode || this.activeMode || {};
                var href = trimLine(targetMode.after_action_href || targetMode.service_href || '');
                var queryFields = Array.isArray(targetMode.continue_query_fields) ? targetMode.continue_query_fields : [];
                var query = {};
                if (!href) {
                    return '';
                }
                queryFields.forEach(function (field) {
                    var param = trimLine(field && field.param);
                    var value = this.resolveContinueQueryValue(field);
                    if (param && value) {
                        query[param] = value;
                    }
                }, this);
                if (Object.keys(query).length) {
                    return appendQueryParams(href, query);
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
                return lines.slice(0, Number(this.activeMode.preview_line_limit || 8));
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
                    if (this.modeHasCapability(this.activeMode, 'schedule_editor')) {
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
                        if (this.modeHasCapability(this.activeMode, 'schedule_editor')) {
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
                if (this.modeHasCapability(this.activeMode, 'notice_refinement') || !trimLine(this.workspaceInput)) {
                    this.noticeRefinementLabel = '';
                    if (!trimLine(this.workspaceInput)) {
                        this.noticeBaseInput = '';
                    }
                }
            },

            quickdropQuickExamples: function () {
                return this.activeModeStarterItems();
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
                this.resetQuickdropDragState();
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
                this.resetQuickdropDragState();
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
                return this.activeModeStarterItems();
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
                return this.activeModeStarterItems();
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
                return this.activeModeStarterItems();
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
                return this.activeModeStarterItems();
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
                return this.activeModeStarterItems();
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

            reservationKnownRoomNames: function () {
                var uiOptions = this.activeMode && typeof this.activeMode.ui_options === 'object'
                    ? this.activeMode.ui_options
                    : {};
                return (Array.isArray(uiOptions.room_names) ? uiOptions.room_names : []).map(function (name) {
                    return trimLine(name);
                }).filter(Boolean);
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

            noticeRefinementActions: function () {
                return this.activeModeRefinementActions();
            },

            teacherLawQuickExamples: function () {
                return this.activeModeStarterItems();
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
                return this.activeModeStarterItems();
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
                var currentMode = this.activeMode;
                var nextMode = this.modeByKey(modeKey);
                this.activeConversationKey = '';
                if (this.modeHasCapability(currentMode, 'tts_read') && !this.modeHasCapability(nextMode, 'tts_read')) {
                    this.isTtsReading = false;
                    if ('speechSynthesis' in window) {
                        window.speechSynthesis.cancel();
                    }
                }
                if (
                    this.activeModeKey !== modeKey
                    && (this.modeHasCapability(currentMode, 'message_pipeline') || this.modeHasCapability(nextMode, 'message_pipeline'))
                ) {
                    this.clearMessageSaveState();
                }
                if (this.modeHasCapability(currentMode, 'file_attach') && !this.modeHasCapability(nextMode, 'file_attach')) {
                    this.resetQuickdropDragState();
                }
                this.activeModeKey = modeKey;
                this.activeRailKey = 'service:' + String(modeKey || '');
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
                var context = this.agentConversationContext && typeof this.agentConversationContext === 'object'
                    ? this.agentConversationContext
                    : {};
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
                        conversation_key: trimLine(context.conversation_key),
                        room_id: trimLine(context.room_id),
                        room_title: trimLine(context.room_title),
                        room_kind: trimLine(context.room_kind),
                        selected_message_ids: Array.isArray(context.selected_message_ids) ? context.selected_message_ids : [],
                        selected_asset_ids: Array.isArray(context.selected_asset_ids) ? context.selected_asset_ids : [],
                        selected_message_texts: Array.isArray(context.selected_message_texts) ? context.selected_message_texts : [],
                        selected_asset_names: Array.isArray(context.selected_asset_names) ? context.selected_asset_names : [],
                    },
                };
            },

            buildLocalPreview: function (text) {
                var builderMap = {
                    'notice': 'buildNoticePreview',
                    'schedule': 'buildSchedulePreview',
                    'teacher-law': 'buildTeacherLawPreview',
                    'reservation': 'buildReservationPreview',
                    'quickdrop': 'buildQuickdropPreview',
                    'pdf': 'buildPdfPreview',
                    'tts': 'buildTtsPreview',
                    'message-save': 'buildMessageSavePreview',
                };
                var methodName = builderMap[this.activeRendererKey] || 'buildNoticePreview';
                var builder = typeof this[methodName] === 'function' ? this[methodName] : this.buildNoticePreview;
                return builder.call(this, text);
            },

            runAgentPreview: async function (overrideText) {
                var text = trimLine(typeof overrideText === 'string' ? overrideText : this.workspaceInput);
                var previewStrategy = String(this.activeMode.preview_strategy || 'llm').toLowerCase();
                if (!text) {
                    this.showIdlePreview();
                    return;
                }
                if (this.modeHasCapability(this.activeMode, 'notice_refinement') && typeof overrideText !== 'string') {
                    this.noticeBaseInput = text;
                    this.noticeRefinementLabel = '';
                }
                if (this.modeHasCapability(this.activeMode, 'schedule_editor')) {
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
                var roomNames = this.reservationKnownRoomNames();
                var roomPattern = roomNames.length
                    ? new RegExp(roomNames.slice().sort(function (left, right) {
                        return right.length - left.length;
                    }).map(escapeRegExp).join('|'))
                    : null;
                var roomHint = roomPattern ? firstMatch(text, roomPattern) : '';
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
