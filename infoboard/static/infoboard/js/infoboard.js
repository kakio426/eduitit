/* ── InfoBoard JS ────────────────────────────────────── */

// ── Search Overlay ──
function ibSetOverlayHidden(overlay, hidden) {
    if (!overlay) return;
    overlay.hidden = hidden;
    overlay.classList.toggle('hidden', hidden);
}

function ibAppendTextElement(parent, tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) {
        element.className = className;
    }
    element.textContent = text || '';
    parent.appendChild(element);
    return element;
}

function ibOpenSearch() {
    const overlay = document.getElementById('ibSearchOverlay');
    if (overlay) {
        ibSetOverlayHidden(overlay, false);
        const input = document.getElementById('ibSearchInput');
        if (input) setTimeout(() => input.focus(), 100);
    }
}

function ibCloseSearch() {
    const overlay = document.getElementById('ibSearchOverlay');
    const input = document.getElementById('ibSearchInput');
    ibSetOverlayHidden(overlay, true);
    if (input) input.blur();
}

function ibStopPropagation(event) {
    if (event) event.stopPropagation();
}

function ibHandleSearchOverlayClick(event) {
    if (event && event.target === event.currentTarget) {
        ibCloseSearch();
    }
}

function ibOpenModal() {
    const overlay = document.getElementById('ibModalOverlay');
    ibSetOverlayHidden(overlay, false);
}

function ibCloseModal() {
    const overlay = document.getElementById('ibModalOverlay');
    const modal = document.getElementById('ibModal');
    if (modal) {
        modal.innerHTML = '';
    }
    ibSetOverlayHidden(overlay, true);
}

function ibOpenSubmitSheet() {
    const overlay = document.getElementById('ibSubmitSheetOverlay');
    const body = document.getElementById('ibSubmitSheetBody');
    if (body && !body.innerHTML.trim()) {
        body.innerHTML = '<div class="p-6 text-sm text-gray-500">제출 폼을 불러오는 중...</div>';
    }
    ibSetOverlayHidden(overlay, false);
}

function ibCloseSubmitSheet() {
    const overlay = document.getElementById('ibSubmitSheetOverlay');
    const body = document.getElementById('ibSubmitSheetBody');
    if (body) {
        body.innerHTML = '';
    }
    ibSetOverlayHidden(overlay, true);
}

function ibHandleSubmitSheetOverlayClick(event) {
    if (event && event.target === event.currentTarget) {
        ibCloseSubmitSheet();
    }
}

let ibConfirmRestoreFocus = null;

function ibEnsureConfirmOverlay() {
    let overlay = document.getElementById('ibConfirmOverlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'ibConfirmOverlay';
    overlay.className = 'ib-modal-overlay hidden';
    overlay.hidden = true;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.addEventListener('click', function(event) {
        if (event.target === overlay) {
            ibCloseConfirm();
        }
    });

    const panel = document.createElement('div');
    panel.className = 'ib-modal p-6 space-y-5';
    panel.addEventListener('click', ibStopPropagation);

    const title = document.createElement('h2');
    title.className = 'text-xl font-black text-gray-900';
    title.textContent = '확인';

    const message = document.createElement('p');
    message.className = 'text-sm font-bold leading-6 text-gray-600';
    message.dataset.ibConfirmMessage = '1';

    const actions = document.createElement('div');
    actions.className = 'flex flex-wrap justify-end gap-2';

    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'ib-inline-button';
    cancel.textContent = '취소';
    cancel.addEventListener('click', ibCloseConfirm);

    const confirm = document.createElement('button');
    confirm.type = 'button';
    confirm.className = 'ib-inline-button danger';
    confirm.textContent = '삭제';
    confirm.dataset.ibConfirmAccept = '1';

    actions.appendChild(cancel);
    actions.appendChild(confirm);
    panel.appendChild(title);
    panel.appendChild(message);
    panel.appendChild(actions);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    return overlay;
}

function ibCloseConfirm() {
    const overlay = document.getElementById('ibConfirmOverlay');
    if (overlay) {
        ibSetOverlayHidden(overlay, true);
        const accept = overlay.querySelector('[data-ib-confirm-accept]');
        if (accept) accept.onclick = null;
    }
    if (ibConfirmRestoreFocus && typeof ibConfirmRestoreFocus.focus === 'function') {
        ibConfirmRestoreFocus.focus({ preventScroll: true });
    }
    ibConfirmRestoreFocus = null;
}

function ibOpenConfirm(message, onConfirm, trigger) {
    const overlay = ibEnsureConfirmOverlay();
    const messageEl = overlay.querySelector('[data-ib-confirm-message]');
    const accept = overlay.querySelector('[data-ib-confirm-accept]');
    if (messageEl) messageEl.textContent = message || '삭제할까요?';
    if (accept) {
        accept.onclick = function() {
            ibCloseConfirm();
            if (typeof onConfirm === 'function') onConfirm();
        };
    }
    ibConfirmRestoreFocus = trigger || document.activeElement;
    ibSetOverlayHidden(overlay, false);
    const cancel = overlay.querySelector('button');
    if (cancel) {
        window.setTimeout(function() {
            cancel.focus();
        }, 0);
    }
}

// Ctrl+K shortcut for InfoBoard search
window.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        const overlay = document.getElementById('ibSearchOverlay');
        if (overlay) {
            e.preventDefault();
            if (overlay.hidden || overlay.classList.contains('hidden')) {
                ibOpenSearch();
            } else {
                ibCloseSearch();
            }
        }
    }
    if (e.key === 'Escape') {
        e.preventDefault();
        ibCloseSearch();
        const modal = document.getElementById('ibModalOverlay');
        if (modal && !(modal.hidden || modal.classList.contains('hidden'))) {
            ibCloseModal();
        }
        const submitSheet = document.getElementById('ibSubmitSheetOverlay');
        if (submitSheet && !(submitSheet.hidden || submitSheet.classList.contains('hidden'))) {
            ibCloseSubmitSheet();
        }
        const confirmOverlay = document.getElementById('ibConfirmOverlay');
        if (confirmOverlay && !(confirmOverlay.hidden || confirmOverlay.classList.contains('hidden'))) {
            ibCloseConfirm();
        }
    }
});

document.addEventListener('click', function(event) {
    const trigger = event.target.closest('[data-ib-confirm]');
    if (!trigger || trigger.dataset.ibConfirmed === '1') {
        return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();

    ibOpenConfirm(trigger.dataset.ibConfirm, function() {
        const form = trigger.form || trigger.closest('form');
        trigger.dataset.ibConfirmed = '1';
        if (form) {
            form.dataset.ibConfirmed = '1';
        }
        if (trigger.type === 'submit' && form && typeof form.requestSubmit === 'function') {
            form.requestSubmit(trigger);
        } else {
            trigger.click();
        }
        window.setTimeout(function() {
            delete trigger.dataset.ibConfirmed;
            if (form) {
                delete form.dataset.ibConfirmed;
            }
        }, 0);
    }, trigger);
}, true);

document.addEventListener('DOMContentLoaded', function() {
    const searchOverlay = document.getElementById('ibSearchOverlay');
    const modalOverlay = document.getElementById('ibModalOverlay');
    const submitSheetOverlay = document.getElementById('ibSubmitSheetOverlay');
    if (searchOverlay) ibSetOverlayHidden(searchOverlay, true);
    if (modalOverlay) ibSetOverlayHidden(modalOverlay, true);
    if (submitSheetOverlay) ibSetOverlayHidden(submitSheetOverlay, true);
});

// ── Tag System ──
function ibAddTag(name) {
    name = (name || '').trim();
    if (!name) return;
    ibAddTagUI(name);
    ibSyncTags();
}

function ibAddTagUI(name) {
    const container = document.getElementById('ibTagContainer');
    if (!container) return;
    // Prevent duplicates
    const existing = container.querySelectorAll('[data-tag-name]');
    for (const el of existing) {
        if (el.dataset.tagName === name) return;
    }
    const chip = document.createElement('span');
    chip.className = 'ib-tag';
    chip.dataset.tagName = name;
    chip.appendChild(document.createTextNode(`#${name} `));
    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'ml-1 text-gray-400 hover:text-red-400';
    removeButton.textContent = '\u00d7';
    removeButton.addEventListener('click', function() {
        ibRemoveTag(chip);
    });
    chip.appendChild(removeButton);
    container.appendChild(chip);
}

function ibRemoveTag(el) {
    el.remove();
    ibSyncTags();
}

function ibSyncTags() {
    const container = document.getElementById('ibTagContainer');
    const hidden = document.getElementById('id_tag_names');
    if (!container || !hidden) return;
    const tags = [];
    container.querySelectorAll('[data-tag-name]').forEach(el => tags.push(el.dataset.tagName));
    hidden.value = tags.join(',');
}

function ibInitTagFields() {
    const container = document.getElementById('ibTagContainer');
    const hidden = document.getElementById('id_tag_names');
    if (!container || !hidden || container.dataset.ibTagsBound === '1') return;

    container.dataset.ibTagsBound = '1';
    if (hidden.value) {
        hidden.value.split(',').forEach(function(name) {
            if (name.trim()) {
                ibAddTagUI(name.trim());
            }
        });
    }
}

// ── Board Form Helpers ──
const IB_ICONS = ['📌', '📚', '📗', '📘', '📙', '📕', '🎓', '🔬', '🎨', '🎵', '⚽', '🌍', '💡', '🔧', '📋', '🗂️', '🏫', '✏️'];

function ibCycleIcon(el) {
    const hidden = document.getElementById('id_icon');
    const current = (hidden && hidden.value) || el.textContent.trim() || IB_ICONS[0];
    const currentIndex = IB_ICONS.indexOf(current);
    const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % IB_ICONS.length : 0;
    const nextIcon = IB_ICONS[nextIndex];
    el.textContent = nextIcon;
    if (hidden) hidden.value = nextIcon;
}

function ibPickColor(btn, color) {
    btn.closest('.flex').querySelectorAll('.ib-color-pick').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const hidden = document.getElementById('id_color_theme');
    if (hidden) hidden.value = color;
}

// ── Card Form Helpers ──
function ibSelectCardType(btn, type) {
    const currentTypeField = document.getElementById('id_card_type');
    const currentType = currentTypeField ? currentTypeField.value : '';
    btn.closest('.flex').querySelectorAll('.ib-type-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const hidden = document.getElementById('id_card_type');
    if (hidden) hidden.value = type;

    // Toggle fields
    const urlField = document.getElementById('ibFieldUrl');
    const fileField = document.getElementById('ibFieldFile');
    const imageField = document.getElementById('ibFieldImage');
    if (urlField) urlField.style.display = type === 'link' ? '' : 'none';
    if (fileField) fileField.style.display = type === 'file' ? '' : 'none';
    if (imageField) imageField.style.display = type === 'image' ? '' : 'none';

    if (type !== 'link') {
        const urlInput = document.getElementById('id_url');
        if (urlInput && currentType !== type) urlInput.value = '';
        const previewEl = document.getElementById('ibOgPreview');
        if (previewEl) previewEl.remove();
    }
    if (type !== 'file') {
        const fileInput = document.getElementById('id_file');
        if (fileInput && currentType !== type) fileInput.value = '';
    }
    if (type !== 'image') {
        const imageInput = document.getElementById('id_image');
        if (imageInput && currentType !== type) imageInput.value = '';
    }
}

function ibPickCardColor(btn, color) {
    btn.closest('.flex').querySelectorAll('.ib-color-pick').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const hidden = document.getElementById('id_color');
    if (hidden) hidden.value = color;
}

// ── Clipboard ──
function ibCopyToClipboard(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    navigator.clipboard.writeText(input.value).then(() => {
        ibToast('링크가 복사되었어요!', 'success');
    }).catch(() => {
        input.select();
        document.execCommand('copy');
        ibToast('링크가 복사되었어요!', 'success');
    });
}

function ibCopyText(text) {
    navigator.clipboard.writeText(text).then(() => {
        ibToast('복사되었어요!', 'success');
    }).catch(() => {
        ibToast('복사에 실패했어요', 'error');
    });
}

// ── QR Fullscreen ──
function ibFullscreenQR() {
    const qrContainer = document.getElementById('ibQrCode');
    if (!qrContainer) return;
    const img = qrContainer.querySelector('img') || qrContainer.querySelector('canvas');
    if (!img) return;

    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:200;background:white;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer';
    overlay.onclick = () => overlay.remove();

    const clone = img.cloneNode(true);
    clone.style.cssText = 'width:min(80vw,400px);height:min(80vw,400px);object-fit:contain';
    overlay.appendChild(clone);

    const hint = document.createElement('p');
    hint.textContent = '화면을 터치하면 닫힙니다';
    hint.style.cssText = 'margin-top:1.5rem;color:#94a3b8;font-weight:700;font-size:1rem';
    overlay.appendChild(hint);

    document.body.appendChild(overlay);
}

// ── Toast ──
function ibToast(message, tag) {
    if (window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent('eduitit:toast', {
            detail: {
                message,
                tag: window.normalizeToastTag ? window.normalizeToastTag(tag) : (tag || 'info'),
            },
        }));
    }
}

// ── OG Meta Auto-Fetch ──
let ibOgTimeout = null;

function ibReadJsonResponse(response) {
    return response.text().then(text => {
        if (!text) return null;
        try {
            return JSON.parse(text);
        } catch (error) {
            return null;
        }
    });
}

function ibFetchOgMeta(url) {
    const setPreviewMessage = function(message, tone) {
        let container = document.getElementById('ibOgPreview');
        if (!container) {
            const urlField = document.getElementById('ibFieldUrl');
            if (!urlField) return;
            container = document.createElement('div');
            container.id = 'ibOgPreview';
            container.className = 'mt-2';
            urlField.appendChild(container);
        }
        const colorClass = tone === 'error' ? 'text-rose-500' : 'text-gray-400';
        container.textContent = '';
        const messageEl = document.createElement('p');
        messageEl.className = `text-xs ${colorClass}`;
        messageEl.textContent = message || '';
        container.appendChild(messageEl);
    };

    setPreviewMessage('메타 확인 중', 'info');

    fetch(`/infoboard/api/og-meta/?url=${encodeURIComponent(url)}`)
        .then(async r => {
            const payload = await ibReadJsonResponse(r);
            if (!r.ok || !payload) {
                throw new Error((payload && payload.error) || '다시 시도');
            }
            return payload;
        })
        .then(meta => {
            const container = document.getElementById('ibOgPreview');
            if (!container) return;

            if (!meta.og_title && !meta.og_image) {
                container.textContent = '';
                return;
            }

            // Auto-fill title if empty
            const titleInput = document.getElementById('id_title');
            if (titleInput && !titleInput.value && meta.og_title) {
                titleInput.value = meta.og_title;
            }

            container.textContent = '';
            const preview = document.createElement('div');
            preview.className = 'ib-og-preview';
            preview.style.cursor = 'default';
            if (meta.og_image) {
                const image = document.createElement('img');
                image.src = meta.og_image;
                image.alt = '';
                image.style.width = '80px';
                image.style.height = '60px';
                image.style.objectFit = 'cover';
                image.style.borderRadius = '0.5rem';
                preview.appendChild(image);
            }
            const textWrap = document.createElement('div');
            textWrap.className = 'ib-og-preview-text';
            if (meta.og_title) ibAppendTextElement(textWrap, 'div', 'ib-og-preview-title', meta.og_title);
            if (meta.og_description) ibAppendTextElement(textWrap, 'div', 'ib-og-preview-desc', meta.og_description);
            if (meta.og_site_name) ibAppendTextElement(textWrap, 'div', 'ib-og-preview-site', meta.og_site_name);
            if (textWrap.childNodes.length) {
                preview.appendChild(textWrap);
            }
            container.appendChild(preview);
        })
        .catch(error => {
            setPreviewMessage(error.message || '다시 시도', 'error');
        });
}

function ibSetupOgFetch() {
    const urlInput = document.getElementById('id_url');
    if (!urlInput || urlInput.dataset.ibOgBound === '1') return;

    urlInput.dataset.ibOgBound = '1';

    urlInput.addEventListener('input', function() {
        clearTimeout(ibOgTimeout);
        const url = this.value.trim();
        if (!url) {
            const previewEl = document.getElementById('ibOgPreview');
            if (previewEl) previewEl.remove();
            return;
        }
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            const previewEl = document.getElementById('ibOgPreview');
            if (previewEl) previewEl.remove();
            return;
        }

        ibOgTimeout = setTimeout(() => ibFetchOgMeta(url), 800);
    });

    // On paste, fetch immediately
    urlInput.addEventListener('paste', function() {
        setTimeout(() => {
            const url = this.value.trim();
            if (url && (url.startsWith('http://') || url.startsWith('https://'))) {
                ibFetchOgMeta(url);
            }
        }, 100);
    });
}

function ibInitInfoboardForms() {
    ibInitTagFields();
    ibSetupOgFetch();
}

document.addEventListener('DOMContentLoaded', function() {
    ibInitInfoboardForms();
});

document.addEventListener('htmx:afterSettle', function() {
    ibInitInfoboardForms();
});

document.addEventListener('infoboard:close-modal', function() {
    ibCloseModal();
});

document.addEventListener('infoboard:close-submit-sheet', function() {
    ibCloseSubmitSheet();
    ibToast('자료가 벽에 올라갔어요!', 'success');
});
