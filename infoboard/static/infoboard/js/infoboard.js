/* ── InfoBoard JS ────────────────────────────────────── */

// ── Search Overlay ──
function ibOpenSearch() {
    const overlay = document.getElementById('ibSearchOverlay');
    if (overlay) {
        overlay.classList.remove('hidden');
        const input = document.getElementById('ibSearchInput');
        if (input) setTimeout(() => input.focus(), 100);
    }
}

function ibCloseSearch() {
    const overlay = document.getElementById('ibSearchOverlay');
    const input = document.getElementById('ibSearchInput');
    if (overlay) overlay.classList.add('hidden');
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

// Ctrl+K shortcut for InfoBoard search
window.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        const overlay = document.getElementById('ibSearchOverlay');
        if (overlay) {
            e.preventDefault();
            if (overlay.classList.contains('hidden')) {
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
        if (modal && !modal.classList.contains('hidden')) {
            modal.classList.add('hidden');
        }
    }
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
    chip.innerHTML = `#${name} <button type="button" onclick="ibRemoveTag(this.parentElement)" class="ml-1 text-gray-400 hover:text-red-400">&times;</button>`;
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

// ── Board Form Helpers ──
const IB_ICONS = ['📌', '📚', '📗', '📘', '📙', '📕', '🎓', '🔬', '🎨', '🎵', '⚽', '🌍', '💡', '🔧', '📋', '🗂️', '🏫', '✏️'];
let ibIconIndex = 0;

function ibCycleIcon(el) {
    ibIconIndex = (ibIconIndex + 1) % IB_ICONS.length;
    el.textContent = IB_ICONS[ibIconIndex];
    const hidden = document.getElementById('id_icon');
    if (hidden) hidden.value = IB_ICONS[ibIconIndex];
}

function ibPickColor(btn, color) {
    btn.closest('.flex').querySelectorAll('.ib-color-pick').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const hidden = document.getElementById('id_color_theme');
    if (hidden) hidden.value = color;
}

// ── Card Form Helpers ──
function ibSelectCardType(btn, type) {
    btn.closest('.flex').querySelectorAll('.ib-type-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const hidden = document.getElementById('id_card_type');
    if (hidden) hidden.value = type;

    // Toggle fields
    const fields = { url: 'ibFieldUrl', file: 'ibFieldFile', image: 'ibFieldImage', content: 'ibFieldContent' };
    document.getElementById('ibFieldUrl').style.display = type === 'link' ? '' : 'none';
    document.getElementById('ibFieldFile').style.display = type === 'file' ? '' : 'none';
    document.getElementById('ibFieldImage').style.display = type === 'image' ? '' : 'none';
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
        window.dispatchEvent(new CustomEvent('eduitit:toast', { detail: { message, tag } }));
    }
}

// ── OG Meta Auto-Fetch ──
let ibOgTimeout = null;

function ibSetupOgFetch() {
    const urlInput = document.getElementById('id_url');
    if (!urlInput) return;

    urlInput.addEventListener('input', function() {
        clearTimeout(ibOgTimeout);
        const url = this.value.trim();
        if (!url || !url.startsWith('http')) return;

        ibOgTimeout = setTimeout(() => ibFetchOgMeta(url), 800);
    });

    // On paste, fetch immediately
    urlInput.addEventListener('paste', function() {
        setTimeout(() => {
            const url = this.value.trim();
            if (url && url.startsWith('http')) ibFetchOgMeta(url);
        }, 100);
    });
}

function ibFetchOgMeta(url) {
    const previewEl = document.getElementById('ibOgPreview');
    if (previewEl) previewEl.innerHTML = '<p class="text-xs text-gray-400 animate-pulse">🔍 메타 정보 가져오는 중...</p>';
    else {
        // Create preview container if not exists
        const urlField = document.getElementById('ibFieldUrl');
        if (urlField) {
            const div = document.createElement('div');
            div.id = 'ibOgPreview';
            div.className = 'mt-2';
            div.innerHTML = '<p class="text-xs text-gray-400 animate-pulse">🔍 메타 정보 가져오는 중...</p>';
            urlField.appendChild(div);
        }
    }

    fetch(`/infoboard/api/og-meta/?url=${encodeURIComponent(url)}`)
        .then(r => {
            if (!r.ok) throw new Error('Failed');
            return r.json();
        })
        .then(meta => {
            const container = document.getElementById('ibOgPreview');
            if (!container) return;

            if (!meta.og_title && !meta.og_image) {
                container.innerHTML = '';
                return;
            }

            // Auto-fill title if empty
            const titleInput = document.getElementById('id_title');
            if (titleInput && !titleInput.value && meta.og_title) {
                titleInput.value = meta.og_title;
            }

            // Show preview
            let html = '<div class="ib-og-preview" style="cursor:default">';
            if (meta.og_image) html += `<img src="${meta.og_image}" alt="" style="width:80px;height:60px;object-fit:cover;border-radius:0.5rem">`;
            html += '<div class="ib-og-preview-text">';
            if (meta.og_title) html += `<div class="ib-og-preview-title">${meta.og_title}</div>`;
            if (meta.og_description) html += `<div class="ib-og-preview-desc">${meta.og_description}</div>`;
            if (meta.og_site_name) html += `<div class="ib-og-preview-site">${meta.og_site_name}</div>`;
            html += '</div></div>';
            container.innerHTML = html;
        })
        .catch(() => {
            const container = document.getElementById('ibOgPreview');
            if (container) container.innerHTML = '';
        });
}

// Setup OG fetch when card form is loaded via HTMX
document.addEventListener('htmx:afterSettle', function() {
    ibSetupOgFetch();
});
