(function () {
    if (window.__snsPinnedNoticeScriptLoaded) {
        return;
    }
    window.__snsPinnedNoticeScriptLoaded = true;

    var STORAGE_PREFIX = 'core:sns:pinned-notice:dismissed:';
    var storageAvailable = true;

    try {
        var probeKey = STORAGE_PREFIX + 'probe';
        window.localStorage.setItem(probeKey, '1');
        window.localStorage.removeItem(probeKey);
    } catch (error) {
        storageAvailable = false;
    }

    function collect(scope, selector) {
        var elements = [];
        if (!scope) {
            return elements;
        }
        if (scope.matches && scope.matches(selector)) {
            elements.push(scope);
        }
        if (scope.querySelectorAll) {
            elements = elements.concat(Array.prototype.slice.call(scope.querySelectorAll(selector)));
        }
        return elements;
    }

    function storageKey(key) {
        return STORAGE_PREFIX + key;
    }

    function isDismissed(key) {
        if (!storageAvailable || !key) {
            return false;
        }
        try {
            return window.localStorage.getItem(storageKey(key)) === '1';
        } catch (error) {
            return false;
        }
    }

    function markDismissed(key) {
        if (!storageAvailable || !key) {
            return;
        }
        try {
            window.localStorage.setItem(storageKey(key), '1');
        } catch (error) {
            storageAvailable = false;
        }
    }

    function setCardVisibility(card, visible) {
        if (!card) {
            return;
        }
        card.hidden = !visible;
        card.classList.toggle('hidden', !visible);
    }

    function updatePinnedNoticeSection(section) {
        if (!section) {
            return;
        }
        var visibleCards = collect(section, '[data-pinned-notice-card]').filter(function (card) {
            return !card.hidden;
        });
        section.hidden = visibleCards.length === 0;
        section.classList.toggle('hidden', visibleCards.length === 0);
    }

    function applyPinnedNoticeDismissState(scope) {
        collect(scope || document, '[data-pinned-notice-card]').forEach(function (card) {
            var key = card.getAttribute('data-pinned-notice-key');
            setCardVisibility(card, !isDismissed(key));
        });

        collect(scope || document, '[data-pinned-notice-section]').forEach(function (section) {
            updatePinnedNoticeSection(section);
        });
    }

    function syncPinnedNoticeComposerState(scope) {
        collect(scope || document, 'form').forEach(function (form) {
            var pinInput = form.querySelector('[data-pin-notice-input]');
            var dismissInput = form.querySelector('[data-allow-dismiss-input]');
            if (!pinInput || !dismissInput) {
                return;
            }

            var enabled = !!pinInput.checked;
            dismissInput.disabled = !enabled;
            if (!enabled) {
                dismissInput.checked = false;
            }

            var dismissLabel = dismissInput.closest('label');
            if (dismissLabel) {
                dismissLabel.classList.toggle('opacity-50', !enabled);
            }
        });
    }

    window.dismissPinnedNotice = function (key, trigger) {
        markDismissed(key);

        var card = trigger && trigger.closest ? trigger.closest('[data-pinned-notice-card]') : null;
        if (!card) {
            applyPinnedNoticeDismissState(document);
            return;
        }

        setCardVisibility(card, false);
        updatePinnedNoticeSection(card.closest('[data-pinned-notice-section]'));
    };

    window.applyPinnedNoticeDismissState = applyPinnedNoticeDismissState;
    window.syncPinnedNoticeComposerState = syncPinnedNoticeComposerState;

    document.addEventListener('DOMContentLoaded', function () {
        applyPinnedNoticeDismissState(document);
        syncPinnedNoticeComposerState(document);
    });

    document.addEventListener('change', function (event) {
        if (!event.target.matches('[data-pin-notice-input], [data-allow-dismiss-input]')) {
            return;
        }
        syncPinnedNoticeComposerState(event.target.closest('form'));
    });

    document.addEventListener('htmx:afterSwap', function (event) {
        applyPinnedNoticeDismissState(event.target);
        syncPinnedNoticeComposerState(event.target);
    });

    applyPinnedNoticeDismissState(document);
    syncPinnedNoticeComposerState(document);
})();
