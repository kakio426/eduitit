(function () {
    const PLAYER_PREFIX = 'seed_quiz_live_players:';
    const RANK_PREFIX = 'seed_quiz_live_ranks:';
    const STAGE_PREFIX = 'seed_quiz_live_stage:';

    function readJson(key) {
        try {
            return JSON.parse(window.sessionStorage.getItem(key) || '{}') || {};
        } catch (error) {
            return {};
        }
    }

    function writeJson(key, value) {
        try {
            window.sessionStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            if (window.console && window.console.debug) {
                window.console.debug('Seed quiz live state skipped', error);
            }
        }
    }

    function toast(scope, message) {
        const target = scope.querySelector('[data-sqg-live-toast]');
        if (!target || !message) return;
        target.textContent = message;
        target.classList.remove('sqg-toast-pop');
        window.requestAnimationFrame(function () {
            target.classList.add('sqg-toast-pop');
        });
    }

    function popClass(target, className) {
        if (!target) return;
        target.classList.remove(className);
        window.requestAnimationFrame(function () {
            target.classList.add(className);
        });
    }

    function spotlightPlayer(scope, playerId) {
        if (!scope || !playerId) return;
        scope.querySelectorAll('[data-sqg-spotlight-player]').forEach(function (target) {
            if (target.dataset.sqgSpotlightPlayer === playerId) {
                popClass(target, 'sqg-spotlight-pop');
            }
        });
    }

    function enhancePlayers(root) {
        root.querySelectorAll('[data-sqg-live-scope]').forEach(function (scope) {
            const scopeId = scope.dataset.sqgLiveScope;
            if (!scopeId) return;
            const key = PLAYER_PREFIX + scopeId;
            const previous = readJson(key);
            const current = {};
            let toastMessage = '';

            scope.querySelectorAll('[data-sqg-live-player]').forEach(function (row) {
                const id = row.dataset.sqgLivePlayer;
                if (!id) return;
                const state = {
                    name: row.dataset.sqgLiveName || '',
                    ready: row.dataset.sqgReadyState || '',
                    connected: row.dataset.sqgConnected || '0',
                };
                current[id] = state;
                const before = previous[id];
                if (!before && Object.keys(previous).length > 0) {
                    row.classList.add('sqg-live-enter');
                    spotlightPlayer(scope, id);
                    toastMessage = state.name ? state.name + ' 입장' : '새 참가자 입장';
                    return;
                }
                if (!before) return;
                if (before.ready !== 'done' && state.ready === 'done') {
                    row.classList.add('sqg-live-done');
                    spotlightPlayer(scope, id);
                    toastMessage = state.name ? state.name + ' 완료' : '완료';
                } else if (before.connected !== state.connected) {
                    spotlightPlayer(scope, id);
                    toastMessage = state.name
                        ? state.name + (state.connected === '1' ? ' 접속' : ' 잠시 이탈')
                        : '';
                }
            });

            if (toastMessage) toast(scope, toastMessage);
            writeJson(key, current);
        });
    }

    function rankLabel(delta) {
        if (delta > 0) return '↑' + delta;
        if (delta < 0) return '↓' + Math.abs(delta);
        return '유지';
    }

    function rankClass(delta) {
        if (delta > 0) return 'sqg-rank-up';
        if (delta < 0) return 'sqg-rank-down';
        return 'sqg-rank-same';
    }

    function enhanceRanks(root) {
        root.querySelectorAll('[data-sqg-rank-scope]').forEach(function (scope) {
            const scopeId = scope.dataset.sqgRankScope;
            if (!scopeId) return;
            const key = RANK_PREFIX + scopeId;
            const previous = readJson(key);
            const current = {};

            scope.querySelectorAll('[data-sqg-rank-row]').forEach(function (row) {
                const id = row.dataset.sqgRankPlayerId;
                const rank = Number(row.dataset.sqgRank || 0);
                if (!id || !rank) return;
                const oldRank = Number(previous[id] || rank);
                const delta = oldRank - rank;
                current[id] = rank;
                const badge = row.querySelector('[data-sqg-rank-delta]');
                if (!badge) return;
                badge.textContent = rankLabel(delta);
                badge.classList.remove('sqg-rank-up', 'sqg-rank-down', 'sqg-rank-same');
                badge.classList.add(rankClass(delta));
                if (delta !== 0) row.classList.add('sqg-rank-shift');
            });

            writeJson(key, current);
        });
    }

    function enhanceStage(root) {
        root.querySelectorAll('[data-sqg-stage-scope]').forEach(function (scope) {
            const scopeId = scope.dataset.sqgStageScope;
            if (!scopeId) return;
            const key = STAGE_PREFIX + scopeId;
            const previous = readJson(key);
            const current = {
                event: scope.dataset.sqgStageEvent || '',
            };
            if (previous.event && previous.event !== current.event) {
                popClass(scope, 'sqg-stage-event-pop');
            }
            writeJson(key, current);
        });
    }

    function enhance(root) {
        if (!root || !root.querySelectorAll) return;
        enhanceStage(root);
        enhancePlayers(root);
        enhanceRanks(root);
    }

    document.addEventListener('DOMContentLoaded', function () {
        enhance(document);
    });
    document.body.addEventListener('htmx:afterSwap', function (event) {
        enhance(event.detail && event.detail.target ? event.detail.target : document);
    });
})();
