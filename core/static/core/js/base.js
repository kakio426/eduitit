(function () {
    function getCsrfToken() {
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        if (field && field.value) {
            return field.value;
        }
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

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

    function normalizeToastTag(tag) {
        var normalized = typeof tag === 'string' ? tag.trim().toLowerCase() : '';
        if (!normalized) {
            return 'info';
        }
        if (normalized === 'error') {
            return 'danger';
        }
        if (normalized === 'danger' || normalized === 'success' || normalized === 'warning' || normalized === 'info') {
            return normalized;
        }
        return 'info';
    }

    function parseInlineJson(value, fallback) {
        if (typeof value !== 'string' || !value.trim()) {
            return fallback;
        }
        try {
            return JSON.parse(value);
        } catch (error) {
            return fallback;
        }
    }

    document.addEventListener('htmx:configRequest', function (event) {
        var token = getCsrfToken();
        if (token) {
            event.detail.headers['X-CSRFToken'] = token;
        }
    });

    window.normalizeToastTag = normalizeToastTag;
    window.showToast = function (message, tag) {
        window.dispatchEvent(new CustomEvent('eduitit:toast', {
            detail: {
                message: message || '',
                tag: normalizeToastTag(tag),
            },
        }));
    };

    window.toggleDesktopMenu = function () {
        var menu = document.getElementById('desktopDropdownMenu');
        if (!menu) {
            return;
        }
        var isHidden = menu.style.display === 'none' || !menu.style.display;
        menu.style.display = isHidden ? 'block' : 'none';
        menu.removeAttribute('x-cloak');
    };
    function initNavbarClock() {
        var clock = document.getElementById('navbarClock');
        if (!clock) {
            return;
        }

        function renderClock() {
            var now = new Date();
            clock.textContent = now.toLocaleTimeString('ko-KR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false,
            });
        }

        renderClock();
        setInterval(renderClock, 1000);
    }

    var classroomPickerState = {
        currentId: '',
        currentName: '',
        defaultId: '',
    };

    function getDesktopClassroomElements() {
        return {
            root: document.getElementById('desktopClassroomPicker'),
            button: document.getElementById('classroomMenuBtn'),
            menu: document.getElementById('desktopClassroomMenu'),
            icon: document.querySelector('[data-classroom-menu-icon]'),
            label: document.getElementById('desktopClassroomCurrentLabel'),
        };
    }

    function getClassroomStateRoot() {
        return document.getElementById('desktopClassroomPicker') || document.getElementById('mobileClassroomPicker');
    }

    function writeClassroomPickerState() {
        var currentId = classroomPickerState.currentId || '';
        var currentName = classroomPickerState.currentName || '';
        var defaultId = classroomPickerState.defaultId || '';
        document.querySelectorAll('[data-classroom-picker-root]').forEach(function (root) {
            root.setAttribute('data-current-classroom-id', currentId);
            root.setAttribute('data-current-classroom-name', currentName);
            root.setAttribute('data-default-classroom-id', defaultId);
        });
    }

    function readClassroomPickerState() {
        var root = getClassroomStateRoot();
        if (!root) {
            return false;
        }
        classroomPickerState.currentId = root.getAttribute('data-current-classroom-id') || '';
        classroomPickerState.currentName = root.getAttribute('data-current-classroom-name') || '';
        classroomPickerState.defaultId = root.getAttribute('data-default-classroom-id') || '';
        return true;
    }

    function setDesktopClassroomMenuOpen(isOpen) {
        var elements = getDesktopClassroomElements();
        if (!elements.menu || !elements.button) {
            return;
        }
        elements.menu.classList.toggle('hidden', !isOpen);
        elements.button.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        if (elements.icon) {
            elements.icon.classList.toggle('rotate-180', isOpen);
        }
    }

    function syncClassroomPickerUi() {
        var currentId = classroomPickerState.currentId || '';
        var currentName = classroomPickerState.currentName || '';
        var defaultId = classroomPickerState.defaultId || '';
        var elements = getDesktopClassroomElements();

        if (elements.label) {
            elements.label.textContent = currentName || '학급 선택';
        }
        if (elements.button) {
            elements.button.title = currentName
                ? '현재 학급: ' + currentName + ' (로그인 시 자동 선택)'
                : '기본 학급을 선택하면 로그인 직후 자동으로 적용됩니다.';
        }

        document.querySelectorAll('[data-classroom-select="true"]').forEach(function (button) {
            var classroomId = button.getAttribute('data-classroom-id') || '';
            var classroomName = button.getAttribute('data-classroom-name') || '';
            var isCurrent = currentId ? classroomId === currentId : (!!currentName && classroomName === currentName);
            var isDefault = !!defaultId && classroomId === defaultId;
            var isDesktopButton = !!button.closest('#desktopClassroomMenu');
            var defaultBadge = button.querySelector('[data-classroom-default-badge]');
            var checkIcon = button.querySelector('[data-classroom-check]');

            if (isDesktopButton) {
                button.classList.toggle('bg-purple-50', isCurrent);
                button.classList.toggle('text-purple-600', isCurrent);
                button.classList.toggle('font-bold', isCurrent);
                button.classList.toggle('text-gray-600', !isCurrent);
            } else {
                button.classList.toggle('bg-purple-100', isCurrent);
                button.classList.toggle('text-purple-600', isCurrent);
                button.classList.toggle('font-bold', isCurrent);
                button.classList.toggle('text-gray-600', !isCurrent);
                button.classList.toggle('hover:bg-purple-50', !isCurrent);
            }

            button.setAttribute('aria-pressed', isCurrent ? 'true' : 'false');
            if (defaultBadge) {
                defaultBadge.classList.toggle('hidden', !isDefault);
            }
            if (checkIcon) {
                checkIcon.classList.toggle('hidden', !isCurrent);
            }
        });

        document.querySelectorAll('[data-classroom-clear-conditional="true"]').forEach(function (button) {
            button.classList.toggle('hidden', !currentId && !currentName);
        });
    }

    function postClassroomSelection(payload) {
        return fetch('/api/set-classroom/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(payload),
        }).then(function (response) {
            if (!response.ok) {
                throw new Error('classroom update failed');
            }
            return response.json();
        });
    }

    function bindClassroomPicker() {
        var hasPicker = readClassroomPickerState();
        var button = document.getElementById('classroomMenuBtn');
        if (!hasPicker && !button) {
            return;
        }

        syncClassroomPickerUi();

        if (button) {
            button.addEventListener('click', function (event) {
                var menu = document.getElementById('desktopClassroomMenu');
                event.preventDefault();
                event.stopPropagation();
                if (!menu) {
                    return;
                }
                setDesktopClassroomMenuOpen(menu.classList.contains('hidden'));
            });
        }

        document.querySelectorAll('[data-classroom-select="true"]').forEach(function (optionButton) {
            optionButton.addEventListener('click', function (event) {
                var classroomId = optionButton.getAttribute('data-classroom-id') || '';
                var classroomName = optionButton.getAttribute('data-classroom-name') || '';
                event.preventDefault();
                event.stopPropagation();
                if (!classroomId) {
                    return;
                }
                postClassroomSelection({
                    source: 'hs',
                    classroom_id: classroomId,
                    persist_default: true,
                }).then(function (payload) {
                    if (payload.status !== 'ok') {
                        throw new Error('classroom update failed');
                    }
                    classroomPickerState.currentId = classroomId;
                    classroomPickerState.currentName = payload.name || classroomName;
                    classroomPickerState.defaultId = classroomId;
                    writeClassroomPickerState();
                    syncClassroomPickerUi();
                    setDesktopClassroomMenuOpen(false);
                }).catch(function () {
                    alert('학급 선택 저장에 실패했습니다. 잠시 후 다시 시도해 주세요.');
                });
            });
        });

        document.querySelectorAll('[data-classroom-clear="true"]').forEach(function (clearButton) {
            clearButton.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                postClassroomSelection({
                    classroom_id: '',
                    persist_default: true,
                }).then(function (payload) {
                    if (payload.status !== 'cleared') {
                        throw new Error('classroom clear failed');
                    }
                    classroomPickerState.currentId = '';
                    classroomPickerState.currentName = '';
                    classroomPickerState.defaultId = '';
                    writeClassroomPickerState();
                    syncClassroomPickerUi();
                    setDesktopClassroomMenuOpen(false);
                }).catch(function () {
                    alert('학급 선택 해제에 실패했습니다. 잠시 후 다시 시도해 주세요.');
                });
            });
        });
    }

    window.toggleMobileMenu = function () {
        var menu = document.getElementById('mobileMenu');
        var btn = document.getElementById('mobileMenuBtn');
        var icon = document.getElementById('menuIcon');
        if (!menu || !btn || !icon) {
            return;
        }
        var isOpen = menu.classList.contains('translate-y-0');

        if (isOpen) {
            menu.classList.remove('translate-y-0', 'opacity-100', 'pointer-events-auto');
            menu.classList.add('-translate-y-full', 'opacity-0', 'pointer-events-none');
            menu.setAttribute('aria-hidden', 'true');
            btn.setAttribute('aria-expanded', 'false');
            btn.setAttribute('aria-label', '메뉴 열기');
            icon.classList.remove('fa-xmark');
            icon.classList.add('fa-bars');
            document.body.style.overflow = 'auto';
            return;
        }

        menu.classList.remove('-translate-y-full', 'opacity-0', 'pointer-events-none');
        menu.classList.add('translate-y-0', 'opacity-100', 'pointer-events-auto');
        menu.setAttribute('aria-hidden', 'false');
        btn.setAttribute('aria-expanded', 'true');
        btn.setAttribute('aria-label', '메뉴 닫기');
        icon.classList.remove('fa-bars');
        icon.classList.add('fa-xmark');
        document.body.style.overflow = 'hidden';
    };

    document.addEventListener('click', function (event) {
        if (!window.Alpine) {
            var menu = document.getElementById('desktopDropdownMenu');
            var button = document.getElementById('userMenuBtn');
            if (menu && button && !button.contains(event.target) && !menu.contains(event.target)) {
                menu.style.display = 'none';
            }
        }

        var classroomRoot = document.getElementById('desktopClassroomPicker');
        if (classroomRoot && !classroomRoot.contains(event.target)) {
            setDesktopClassroomMenuOpen(false);
        }

        var mobileMenu = document.getElementById('mobileMenu');
        var mobileButton = document.getElementById('mobileMenuBtn');
        if (mobileMenu && mobileButton && !mobileMenu.contains(event.target) && !mobileButton.contains(event.target)) {
            if (mobileMenu.classList.contains('translate-y-0')) {
                window.toggleMobileMenu();
            }
        }
    });

    window.addEventListener('resize', function () {
        var menu = document.getElementById('mobileMenu');
        if (window.innerWidth >= 768 && menu && menu.classList.contains('translate-y-0')) {
            window.toggleMobileMenu();
        }
    });

    var unifiedModalPrevBodyOverflow = '';

    function setUnifiedModalTitle(title) {
        var heading = document.getElementById('unifiedModalTitle');
        if (heading) {
            heading.textContent = title || '정보';
        }
    }

    function renderRemoteModalError(content, loading, retryCallback) {
        content.innerHTML = ''
            + '<div class="flex flex-col items-center justify-center py-20 text-center space-y-6">'
            + '<i class="fa-solid fa-triangle-exclamation text-7xl text-gray-200"></i>'
            + '<h3 class="text-3xl font-bold text-gray-700">정보를 불러오지 못했습니다</h3>'
            + '<p class="text-xl text-gray-400 font-hand">잠시 후 다시 시도해 주세요.</p>'
            + '<button type="button" class="rounded-full bg-slate-900 px-8 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-slate-700" data-remote-modal-retry="true">다시 시도</button>'
            + '</div>';
        loading.classList.add('hidden');
        var retryButton = content.querySelector('[data-remote-modal-retry]');
        if (retryButton && typeof retryCallback === 'function') {
            retryButton.addEventListener('click', retryCallback);
        }
    }

    function loadRemoteModal(url, modalTitle, retryCallback) {
        window.openUnifiedModal();
        var content = document.getElementById('modalContent');
        var loading = document.getElementById('modalLoading');
        if (!content || !loading || !url) {
            return;
        }
        setUnifiedModalTitle(modalTitle);
        loading.classList.remove('hidden');
        content.innerHTML = '';

        fetch(url)
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.text();
            })
            .then(function (html) {
                content.innerHTML = html;
                loading.classList.add('hidden');
            })
            .catch(function () {
                renderRemoteModalError(content, loading, retryCallback);
            });
    }

    function resetUnifiedModalState() {
        var modal = document.getElementById('unifiedModal');
        var backdrop = document.getElementById('modalBackdrop');
        var panel = document.getElementById('modalPanel');
        var loading = document.getElementById('modalLoading');
        var content = document.getElementById('modalContent');
        if (!modal || !backdrop || !panel) {
            return;
        }

        modal.classList.add('hidden');
        backdrop.classList.add('opacity-0');
        panel.classList.remove('scale-100', 'opacity-100');
        panel.classList.add('scale-95', 'opacity-0');
        document.body.style.overflow = unifiedModalPrevBodyOverflow;
        unifiedModalPrevBodyOverflow = '';
        if (loading) {
            loading.classList.add('hidden');
        }
        if (content) {
            content.innerHTML = '';
        }
    }

    window.openUnifiedModal = function () {
        var modal = document.getElementById('unifiedModal');
        var backdrop = document.getElementById('modalBackdrop');
        var panel = document.getElementById('modalPanel');
        var body = document.body;
        if (!modal || !backdrop || !panel || !body || !modal.classList.contains('hidden')) {
            return;
        }

        modal.classList.remove('hidden');
        unifiedModalPrevBodyOverflow = body.style.overflow || '';
        body.style.overflow = 'hidden';
        panel.classList.add('scale-95', 'opacity-0');

        requestAnimationFrame(function () {
            backdrop.classList.remove('opacity-0');
            panel.classList.remove('scale-95', 'opacity-0');
            panel.classList.add('scale-100', 'opacity-100');
        });
    };

    window.openModal = function (productId) {
        var url = '/products/preview/' + productId + '/?t=' + Date.now();
        loadRemoteModal(url, '서비스 미리보기', function () {
            window.openModal(productId);
        });
    };

    window.openRemoteModal = function (url, modalTitle) {
        loadRemoteModal(url, modalTitle || '정보', function () {
            window.openRemoteModal(url, modalTitle || '정보');
        });
    };

    window.closeModal = function () {
        var modal = document.getElementById('unifiedModal');
        var backdrop = document.getElementById('modalBackdrop');
        var panel = document.getElementById('modalPanel');
        var body = document.body;
        if (!modal || !backdrop || !panel || !body || modal.classList.contains('hidden')) {
            return;
        }

        backdrop.classList.add('opacity-0');
        panel.classList.remove('scale-100', 'opacity-100');
        panel.classList.add('scale-95', 'opacity-0');

        setTimeout(function () {
            modal.classList.add('hidden');
            body.style.overflow = unifiedModalPrevBodyOverflow;
            unifiedModalPrevBodyOverflow = '';
        }, 300);
    };

    window.syncGlobalBannerOffset = function () {
        var banner = document.getElementById('globalBanner');
        var height = 0;
        if (banner && window.getComputedStyle(banner).display !== 'none') {
            height = Math.ceil(banner.getBoundingClientRect().height);
        }
        document.documentElement.style.setProperty('--global-banner-height', height + 'px');
        if (window.syncMobileMenuOffset) {
            window.syncMobileMenuOffset();
        }
    };

    window.syncMobileMenuOffset = function () {
        var nav = document.getElementById('mainNav');
        var top = 88;
        var navHeight = 88;
        if (nav) {
            navHeight = Math.max(0, Math.ceil(nav.getBoundingClientRect().height));
            top = Math.max(0, Math.ceil(nav.getBoundingClientRect().bottom));
        }
        document.documentElement.style.setProperty('--main-nav-height', navHeight + 'px');
        document.documentElement.style.setProperty('--mobile-menu-top', top + 'px');
    };

    function initAutoLogout() {
        var modal = document.getElementById('autoLogoutModal');
        if (!modal) {
            return;
        }

        var timeoutMinutes = 360;
        var warningMinutes = 359;
        var logoutTimer;
        var warningTimer;
        var countdownInterval;
        var secondsLeft = 60;
        var logoutUrl = modal.dataset.logoutUrl || '';

        function updateCountdown() {
            var timerEl = document.getElementById('logoutTimer');
            if (!timerEl) {
                return;
            }
            timerEl.textContent = secondsLeft;
            if (secondsLeft <= 0) {
                clearInterval(countdownInterval);
            }
            secondsLeft -= 1;
        }

        function showWarning() {
            modal.classList.remove('hidden');
            secondsLeft = 60;
            updateCountdown();
            countdownInterval = setInterval(updateCountdown, 1000);
        }

        function autoLogout() {
            if (!logoutUrl) {
                return;
            }
            var form = document.createElement('form');
            form.method = 'POST';
            form.action = logoutUrl;
            var csrf = document.createElement('input');
            csrf.type = 'hidden';
            csrf.name = 'csrfmiddlewaretoken';
            csrf.value = getCsrfToken();
            form.appendChild(csrf);
            document.body.appendChild(form);
            form.submit();
        }

        function startTimers() {
            clearTimeout(logoutTimer);
            clearTimeout(warningTimer);
            clearInterval(countdownInterval);
            modal.classList.add('hidden');
            warningTimer = setTimeout(showWarning, warningMinutes * 60 * 1000);
            logoutTimer = setTimeout(autoLogout, timeoutMinutes * 60 * 1000);
        }

        window.extendSession = function () {
            fetch(window.location.href, { method: 'HEAD' })
                .then(function () {
                    startTimers();
                })
                .catch(function () {});
        };

        var activities = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
        var throttleTimer = null;

        function handleActivity() {
            if (throttleTimer) {
                return;
            }
            throttleTimer = setTimeout(function () {
                if (modal.classList.contains('hidden')) {
                    startTimers();
                }
                throttleTimer = null;
            }, 10000);
        }

        activities.forEach(function (activity) {
            window.addEventListener(activity, handleActivity, true);
        });
        startTimers();
    }

    function initServiceLauncher() {
        var launcherItems = parseJsonScript('service-launcher-items-data', []);
        var modal = document.getElementById('serviceLauncherModal');
        var input = document.getElementById('serviceLauncherInput');
        var backdrop = document.getElementById('serviceLauncherBackdrop');
        var results = document.getElementById('serviceLauncherResults');
        if (!modal || !input || !backdrop || !results || !Array.isArray(launcherItems) || !launcherItems.length) {
            return;
        }

        var activeIdx = -1;
        var visibleItems = [];
        var recentKey = 'eduitit_recent_launcher_items';
        var maxRecent = 5;
        var prevBodyOverflow = null;
        var trackUsageUrl = '/api/track-usage/';
        var typeColors = {
            collect_sign: 'text-blue-500',
            classroom: 'text-blue-500',
            work: 'text-emerald-500',
            game: 'text-red-500',
            counsel: 'text-violet-500',
            edutech: 'text-cyan-500',
            etc: 'text-slate-500',
        };

        function escapeHtml(text) {
            return String(text || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function isLauncherOpen() {
            return !modal.classList.contains('hidden');
        }

        function isUnifiedModalOpen() {
            var unifiedModal = document.getElementById('unifiedModal');
            return unifiedModal && !unifiedModal.classList.contains('hidden');
        }

        function getRecentIds() {
            try {
                return JSON.parse(localStorage.getItem(recentKey) || '[]');
            } catch (error) {
                return [];
            }
        }

        function addRecent(id) {
            var list = getRecentIds().filter(function (savedId) { return savedId !== id; });
            list.unshift(id);
            if (list.length > maxRecent) {
                list = list.slice(0, maxRecent);
            }
            localStorage.setItem(recentKey, JSON.stringify(list));
        }

        function getRecentItems() {
            return getRecentIds()
                .map(function (id) {
                    return launcherItems.find(function (item) { return item.id === id; });
                })
                .filter(Boolean);
        }

        function buildIconHtml(item) {
            if (item.icon && item.icon.indexOf('fa-') !== -1) {
                return '<i class="' + item.icon + ' ' + (typeColors[item.service_type] || 'text-slate-500') + '"></i>';
            }
            return '<span>' + escapeHtml(item.icon || '📦') + '</span>';
        }

        function buildItemHtml(item, index) {
            var summary = item.summary ? '<p class="mt-1 text-xs text-slate-500 line-clamp-1">' + escapeHtml(item.summary) + '</p>' : '';
            var externalBadge = item.is_external
                ? '<span class="ml-2 inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">외부</span>'
                : '';
            return ''
                + '<button type="button" class="service-launcher-item flex w-full items-start gap-3 rounded-2xl px-4 py-3 text-left transition hover:bg-indigo-50" data-idx="' + index + '">'
                + '<span class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl bg-slate-50 text-lg">'
                + buildIconHtml(item)
                + '</span>'
                + '<span class="min-w-0 flex-1">'
                + '<span class="flex items-center text-sm font-black text-slate-900">'
                + '<span class="truncate">' + escapeHtml(item.title) + '</span>'
                + externalBadge
                + '</span>'
                + summary
                + '</span>'
                + '<span class="pt-1 text-slate-300"><i class="fa-solid fa-arrow-up-right-from-square text-xs"></i></span>'
                + '</button>';
        }

        function renderEmptyState(message) {
            visibleItems = [];
            activeIdx = -1;
            results.innerHTML = '<div class="px-4 py-10 text-center text-sm font-semibold text-slate-400">' + escapeHtml(message) + '</div>';
        }

        function bindRenderedItems() {
            results.querySelectorAll('.service-launcher-item').forEach(function (element) {
                element.addEventListener('click', function () {
                    launchItem(parseInt(this.dataset.idx || '-1', 10));
                });
            });
        }

        function renderSections(sections) {
            var html = '';
            var nextItems = [];
            var itemIndex = 0;
            sections.forEach(function (section) {
                if (!section.items || !section.items.length) {
                    return;
                }
                html += '<section class="pb-2">';
                html += '<div class="px-4 pb-1 pt-3 text-[11px] font-extrabold uppercase tracking-[0.08em] text-slate-400">' + escapeHtml(section.label) + '</div>';
                section.items.forEach(function (item) {
                    nextItems.push(item);
                    html += buildItemHtml(item, itemIndex);
                    itemIndex += 1;
                });
                html += '</section>';
            });

            if (!nextItems.length) {
                renderEmptyState('검색 결과가 없습니다.');
                return;
            }

            visibleItems = nextItems;
            activeIdx = -1;
            results.innerHTML = html;
            bindRenderedItems();
        }

        function buildGroupedSections(items) {
            var groups = {};
            items.forEach(function (item) {
                if (!groups[item.group_key]) {
                    groups[item.group_key] = {
                        order: item.group_order || 999,
                        label: item.group_title || '기타 서비스',
                        items: [],
                    };
                }
                groups[item.group_key].items.push(item);
            });
            return Object.keys(groups)
                .map(function (key) { return groups[key]; })
                .sort(function (left, right) { return left.order - right.order; });
        }

        function renderDefaultSections() {
            var sections = [];
            var recentItems = getRecentItems();
            if (recentItems.length) {
                sections.push({ label: '최근 연 서비스', items: recentItems });
            }
            buildGroupedSections(launcherItems).forEach(function (group) {
                sections.push({ label: group.label, items: group.items });
            });
            renderSections(sections);
        }

        function renderSearchResults(query) {
            var normalized = query.trim().toLowerCase();
            if (!normalized) {
                renderDefaultSections();
                return;
            }
            var filtered = launcherItems.filter(function (item) {
                return (item.searchable_text || '').indexOf(normalized) !== -1;
            });
            renderSections([{ label: '검색 결과', items: filtered }]);
        }

        function highlightActive() {
            results.querySelectorAll('.service-launcher-item').forEach(function (element, index) {
                if (index === activeIdx) {
                    element.classList.add('bg-indigo-50');
                    element.scrollIntoView({ block: 'nearest' });
                    return;
                }
                element.classList.remove('bg-indigo-50');
            });
        }

        function launchItem(index) {
            if (index < 0 || index >= visibleItems.length) {
                return;
            }
            var item = visibleItems[index];
            addRecent(item.id);
            if (item && item.id) {
                fetch(trackUsageUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify({
                        product_id: parseInt(item.id, 10),
                        action: 'launch',
                        source: 'other',
                    }),
                    keepalive: true,
                }).catch(function () {
                    return null;
                });
            }
            window.closeServiceLauncher();
            if (item.is_external) {
                window.open(item.href, '_blank', 'noopener');
                return;
            }
            window.location.href = item.href;
        }

        window.openServiceLauncher = function () {
            if (isLauncherOpen() || isUnifiedModalOpen()) {
                return;
            }
            prevBodyOverflow = document.body.style.overflow;
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
            input.value = '';
            renderDefaultSections();
            setTimeout(function () { input.focus(); }, 50);
        };

        window.closeServiceLauncher = function () {
            if (!isLauncherOpen()) {
                return;
            }
            modal.classList.add('hidden');
            document.body.style.overflow = prevBodyOverflow || '';
            prevBodyOverflow = null;
        };

        backdrop.addEventListener('click', function () {
            window.closeServiceLauncher();
        });

        modal.addEventListener('click', function (event) {
            if (event.target === modal || event.target === backdrop) {
                window.closeServiceLauncher();
            }
        });

        input.addEventListener('input', function () {
            renderSearchResults(this.value);
        });

        input.addEventListener('keydown', function (event) {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                if (visibleItems.length) {
                    activeIdx = (activeIdx + 1) % visibleItems.length;
                    highlightActive();
                }
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                if (visibleItems.length) {
                    activeIdx = activeIdx <= 0 ? visibleItems.length - 1 : activeIdx - 1;
                    highlightActive();
                }
            } else if (event.key === 'Enter') {
                event.preventDefault();
                if (activeIdx >= 0) {
                    launchItem(activeIdx);
                } else if (visibleItems.length === 1) {
                    launchItem(0);
                }
            } else if (event.key === 'Escape' && isLauncherOpen()) {
                event.preventDefault();
                window.closeServiceLauncher();
            }
        });

        document.addEventListener('keydown', function (event) {
            if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
                event.preventDefault();
                if (isUnifiedModalOpen()) {
                    return;
                }
                if (isLauncherOpen()) {
                    window.closeServiceLauncher();
                    return;
                }
                window.openServiceLauncher();
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && isLauncherOpen()) {
                event.preventDefault();
                window.closeServiceLauncher();
            }
        }, true);
    }

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            setDesktopClassroomMenuOpen(false);
        }
    });

    document.addEventListener('keydown', function (event) {
        var unifiedModal = document.getElementById('unifiedModal');
        if (event.key === 'Escape' && unifiedModal && !unifiedModal.classList.contains('hidden')) {
            window.closeModal();
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        var panel = document.getElementById('modalPanel');
        if (panel) {
            panel.addEventListener('click', function (event) {
                event.stopPropagation();
            });
        }

        var content = document.getElementById('modalContent');
        if (content) {
            content.addEventListener('click', function (event) {
                var anchor = event.target.closest('a[href]');
                if (anchor) {
                    window.closeModal();
                }
            });
        }

        document.addEventListener('click', function (event) {
            var trigger = event.target.closest('[data-buddy-profile-trigger]');
            if (!trigger) {
                return;
            }
            var profileUrl = trigger.getAttribute('data-buddy-profile-url');
            if (!profileUrl || !window.openRemoteModal) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            window.openRemoteModal(
                profileUrl,
                trigger.getAttribute('data-buddy-profile-title') || '메이트 프로필'
            );
        });

        window.syncGlobalBannerOffset();
        window.syncMobileMenuOffset();
        bindClassroomPicker();
        initNavbarClock();

        var banner = document.getElementById('globalBanner');
        if (banner && typeof ResizeObserver !== 'undefined') {
            var resizeObserver = new ResizeObserver(function () { window.syncGlobalBannerOffset(); });
            resizeObserver.observe(banner);
            var mutationObserver = new MutationObserver(function () { window.syncGlobalBannerOffset(); });
            mutationObserver.observe(banner, { attributes: true, attributeFilter: ['style', 'class'] });
        }

        initAutoLogout();
        initServiceLauncher();

        if (window.AOS) {
            window.AOS.init({
                once: true,
                offset: 20,
                duration: 800,
                easing: 'ease-out-cubic',
            });
        }
    });

    window.addEventListener('pageshow', resetUnifiedModalState);
    window.addEventListener('resize', function () {
        window.syncGlobalBannerOffset();
        window.syncMobileMenuOffset();
        if (window.AOS) {
            window.AOS.refresh();
        }
    });
    window.addEventListener('load', function () {
        window.syncMobileMenuOffset();
        if (window.AOS) {
            window.AOS.refresh();
        }
    });
})();
