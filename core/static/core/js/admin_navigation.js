'use strict';

{
    const navSidebar = document.getElementById('nav-sidebar');
    if (!navSidebar) {
        return;
    }

    const navFilter = document.getElementById('nav-filter');
    const groups = Array.from(navSidebar.querySelectorAll('.admin-nav-group'));
    const defaultGroupState = {};
    const scrollStorageKey = 'eduitit.admin.navSidebarScrollTop';
    const groupStorageKey = 'eduitit.admin.navGroupState';
    let isRestoringGroups = false;

    groups.forEach((group) => {
        defaultGroupState[group.dataset.adminGroup] = group.open;
    });

    function readStoredGroupState() {
        try {
            return JSON.parse(localStorage.getItem(groupStorageKey) || '{}');
        } catch (error) {
            return {};
        }
    }

    function writeStoredGroupState() {
        const state = {};
        groups.forEach((group) => {
            state[group.dataset.adminGroup] = group.open;
        });
        localStorage.setItem(groupStorageKey, JSON.stringify(state));
    }

    function restoreGroupState() {
        const stored = readStoredGroupState();
        isRestoringGroups = true;
        groups.forEach((group) => {
            const key = group.dataset.adminGroup;
            if (Object.prototype.hasOwnProperty.call(stored, key)) {
                group.open = !!stored[key];
                return;
            }
            group.open = !!defaultGroupState[key];
        });
        isRestoringGroups = false;
    }

    function normalize(value) {
        return String(value || '').trim().toLowerCase();
    }

    function saveSidebarScroll() {
        localStorage.setItem(scrollStorageKey, String(navSidebar.scrollTop));
    }

    function restoreSidebarScroll() {
        const storedScroll = localStorage.getItem(scrollStorageKey);
        if (storedScroll !== null) {
            navSidebar.scrollTop = Number(storedScroll) || 0;
            return;
        }

        const currentLink = navSidebar.querySelector(
            '.current-model a[aria-current="page"], .current-model a, .current-app caption .section'
        );
        if (currentLink) {
            currentLink.scrollIntoView({block: 'nearest'});
        }
    }

    function syncVisibleApps(query) {
        let hasResults = false;

        groups.forEach((group) => {
            let groupVisible = false;
            const modules = Array.from(group.querySelectorAll('.module'));

            modules.forEach((module) => {
                const appLink = module.querySelector('caption .section');
                const appText = normalize(
                    [
                        appLink ? appLink.textContent : '',
                        module.className,
                    ].join(' ')
                );
                const appMatches = Boolean(query) && appText.includes(query);
                const rows = Array.from(module.querySelectorAll('tbody tr'));
                let visibleRows = 0;

                rows.forEach((row) => {
                    const modelText = normalize(row.querySelector('th[scope="row"]')?.textContent);
                    const matches = !query || appMatches || modelText.includes(query);
                    row.style.display = matches ? '' : 'none';
                    if (matches) {
                        visibleRows += 1;
                    }
                });

                const moduleVisible = visibleRows > 0 || (!rows.length && (!query || appMatches));
                module.style.display = moduleVisible ? '' : 'none';
                if (moduleVisible) {
                    groupVisible = true;
                    hasResults = true;
                }
            });

            group.hidden = !groupVisible;
            if (query) {
                group.open = groupVisible;
            }
        });

        if (!query) {
            restoreGroupState();
        }

        navFilter.classList.toggle('no-results', Boolean(query) && !hasResults);
    }

    restoreGroupState();

    groups.forEach((group) => {
        group.addEventListener('toggle', () => {
            if (isRestoringGroups || normalize(navFilter?.value)) {
                return;
            }
            writeStoredGroupState();
        });
    });

    if (navFilter) {
        const applyFilter = () => {
            syncVisibleApps(normalize(navFilter.value));
        };

        navFilter.addEventListener('input', applyFilter);
        navFilter.addEventListener('change', applyFilter);
        navFilter.addEventListener('keyup', (event) => {
            if (event.key === 'Escape') {
                navFilter.value = '';
                applyFilter();
            }
        });

        applyFilter();
    }

    navSidebar.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', saveSidebarScroll);
    });
    window.addEventListener('beforeunload', saveSidebarScroll);

    requestAnimationFrame(restoreSidebarScroll);
}
