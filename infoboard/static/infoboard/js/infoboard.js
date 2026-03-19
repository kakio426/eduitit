/* InfoBoard interaction helpers */

const IB_ICONS = ["📌", "📚", "📗", "📘", "📙", "📕", "🎓", "🔬", "🎨", "🎵", "⚽", "🌍", "💡", "🔧", "📋", "🗂️", "🏫", "✏️"];
let ibOgTimeout = null;

function ibOpenSearch() {
    const overlay = document.getElementById("ibSearchOverlay");
    if (!overlay) return;
    overlay.classList.remove("hidden");
    const input = document.getElementById("ibSearchInput");
    if (input) {
        window.setTimeout(() => input.focus(), 100);
    }
}

function ibCloseSearch() {
    const overlay = document.getElementById("ibSearchOverlay");
    const input = document.getElementById("ibSearchInput");
    if (overlay) overlay.classList.add("hidden");
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
    const overlay = document.getElementById("ibModalOverlay");
    if (overlay) overlay.classList.remove("hidden");
}

function ibCloseModal() {
    const overlay = document.getElementById("ibModalOverlay");
    const modal = document.getElementById("ibModal");
    if (modal) modal.innerHTML = "";
    if (overlay) overlay.classList.add("hidden");
}

window.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "k") {
        const overlay = document.getElementById("ibSearchOverlay");
        if (!overlay) return;
        event.preventDefault();
        if (overlay.classList.contains("hidden")) {
            ibOpenSearch();
        } else {
            ibCloseSearch();
        }
    }
    if (event.key === "Escape") {
        ibCloseSearch();
        const modal = document.getElementById("ibModalOverlay");
        if (modal && !modal.classList.contains("hidden")) {
            ibCloseModal();
        }
    }
});

function ibAddTag(name) {
    const cleanName = (name || "").trim();
    if (!cleanName) return;
    ibAddTagUI(cleanName);
    ibSyncTags();
}

function ibAddTagUI(name) {
    const container = document.getElementById("ibTagContainer");
    if (!container) return;
    const existing = container.querySelectorAll("[data-tag-name]");
    for (const element of existing) {
        if (element.dataset.tagName === name) return;
    }
    const chip = document.createElement("span");
    chip.className = "ib-tag";
    chip.dataset.tagName = name;
    chip.innerHTML = `#${name} <button type="button" onclick="ibRemoveTag(this.parentElement)" class="ml-1 text-gray-400 hover:text-red-400">&times;</button>`;
    container.appendChild(chip);
}

function ibRemoveTag(element) {
    if (element) element.remove();
    ibSyncTags();
}

function ibSyncTags() {
    const container = document.getElementById("ibTagContainer");
    const hidden = document.getElementById("id_tag_names");
    if (!container || !hidden) return;
    const tags = [];
    container.querySelectorAll("[data-tag-name]").forEach((element) => tags.push(element.dataset.tagName));
    hidden.value = tags.join(",");
}

function ibInitTagFields() {
    const container = document.getElementById("ibTagContainer");
    const hidden = document.getElementById("id_tag_names");
    if (!container || !hidden || container.dataset.ibTagsBound === "1") return;

    container.dataset.ibTagsBound = "1";
    if (hidden.value) {
        hidden.value.split(",").forEach((name) => {
            if (name.trim()) ibAddTagUI(name.trim());
        });
    }
}

function ibRefreshChoiceCards(scope) {
    scope.querySelectorAll(".ib-choice-card, .ib-preset-card").forEach((label) => {
        const input = label.querySelector('input[type="radio"]');
        if (!input) return;
        label.classList.toggle("active", input.checked);
    });
}

function ibSetRadioValue(name, value) {
    document.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
        input.checked = input.value === value;
    });
}

function ibSetBoardColor(color) {
    const hidden = document.getElementById("id_color_theme");
    if (hidden) hidden.value = color;
    document.querySelectorAll(".ib-color-pick[data-color-value]").forEach((button) => {
        button.classList.toggle("active", button.dataset.colorValue === color);
    });
}

function ibApplyPresetCard(label, forceDescription) {
    if (!label) return;
    const picker = document.getElementById("ibIconPicker");
    const iconField = document.getElementById("id_icon");
    const descriptionField = document.getElementById("id_description");
    const publicField = document.getElementById("id_is_public");
    const submitField = document.getElementById("id_allow_student_submit");

    if (picker) picker.textContent = label.dataset.presetIcon || IB_ICONS[0];
    if (iconField) iconField.value = label.dataset.presetIcon || IB_ICONS[0];
    if (descriptionField && (!descriptionField.value || descriptionField.dataset.ibTouched !== "1" || forceDescription)) {
        descriptionField.value = label.dataset.presetDescription || "";
    }
    if (publicField) publicField.checked = label.dataset.presetPublic === "1";
    if (submitField) submitField.checked = label.dataset.presetSubmit === "1";

    ibSetBoardColor(label.dataset.presetColor || "purple");
    ibSetRadioValue("layout", label.dataset.presetLayout || "grid");
    ibSetRadioValue("moderation_mode", label.dataset.presetModeration || "manual");
    ibSetRadioValue("share_mode", label.dataset.presetShare || "private");
    ibRefreshChoiceCards(document);
}

function ibInitChoiceCards() {
    const scope = document;
    scope.querySelectorAll(".ib-choice-card, .ib-preset-card").forEach((label) => {
        if (label.dataset.ibBound === "1") return;
        label.dataset.ibBound = "1";
        label.addEventListener("click", function () {
            const input = label.querySelector('input[type="radio"]');
            if (!input) return;
            input.checked = true;
            input.dispatchEvent(new Event("change", { bubbles: true }));
        });
    });

    scope.querySelectorAll('.ib-choice-card input[type="radio"], .ib-preset-card input[type="radio"]').forEach((input) => {
        if (input.dataset.ibBound === "1") return;
        input.dataset.ibBound = "1";
        input.addEventListener("change", function () {
            ibRefreshChoiceCards(scope);
            const presetLabel = input.closest(".ib-preset-card");
            if (presetLabel && input.checked) {
                ibApplyPresetCard(presetLabel, true);
            }
        });
    });

    ibRefreshChoiceCards(scope);
}

function ibInitBoardPresets() {
    const form = document.querySelector("form[data-board-form-mode]");
    if (!form || form.dataset.ibPresetInit === "1") return;
    form.dataset.ibPresetInit = "1";

    const descriptionField = document.getElementById("id_description");
    if (descriptionField && descriptionField.dataset.ibTouchedBound !== "1") {
        descriptionField.dataset.ibTouchedBound = "1";
        descriptionField.addEventListener("input", function () {
            descriptionField.dataset.ibTouched = descriptionField.value ? "1" : "0";
        });
    }

    const mode = form.dataset.boardFormMode;
    const checked = form.querySelector('.ib-preset-card input[type="radio"]:checked');
    if (checked && mode === "create") {
        ibApplyPresetCard(checked.closest(".ib-preset-card"), false);
    }
}

function ibCycleIcon(element) {
    const hidden = document.getElementById("id_icon");
    const current = (hidden && hidden.value) || element.textContent.trim() || IB_ICONS[0];
    const index = IB_ICONS.indexOf(current);
    const nextIcon = IB_ICONS[index >= 0 ? (index + 1) % IB_ICONS.length : 0];
    if (element) element.textContent = nextIcon;
    if (hidden) hidden.value = nextIcon;
}

function ibPickColor(button, color) {
    const group = button.closest(".flex");
    if (group) {
        group.querySelectorAll(".ib-color-pick").forEach((target) => target.classList.remove("active"));
    }
    button.classList.add("active");
    const hidden = document.getElementById("id_color_theme");
    if (hidden) hidden.value = color;
}

function ibSelectCardType(button, type) {
    const hidden = document.getElementById("id_card_type");
    const currentType = hidden ? hidden.value : "";
    const group = button.closest(".flex");
    if (group) {
        group.querySelectorAll(".ib-type-tab").forEach((target) => target.classList.remove("active"));
    }
    button.classList.add("active");
    if (hidden) hidden.value = type;

    const urlField = document.getElementById("ibFieldUrl");
    const fileField = document.getElementById("ibFieldFile");
    const imageField = document.getElementById("ibFieldImage");
    if (urlField) urlField.style.display = type === "link" ? "" : "none";
    if (fileField) fileField.style.display = type === "file" ? "" : "none";
    if (imageField) imageField.style.display = type === "image" ? "" : "none";

    if (type !== "link") {
        const urlInput = document.getElementById("id_url");
        if (urlInput && currentType !== type) urlInput.value = "";
        const preview = document.getElementById("ibOgPreview");
        if (preview) preview.remove();
    }
    if (type !== "file") {
        const fileInput = document.getElementById("id_file");
        if (fileInput && currentType !== type) fileInput.value = "";
    }
    if (type !== "image") {
        const imageInput = document.getElementById("id_image");
        if (imageInput && currentType !== type) imageInput.value = "";
    }
}

function ibInitCardTypeTabs() {
    const hidden = document.getElementById("id_card_type");
    if (!hidden) return;
    const type = hidden.value || "text";
    const button = document.querySelector(`.ib-type-tab[data-card-type="${type}"]`);
    if (button) ibSelectCardType(button, type);
}

function ibPickCardColor(button, color) {
    const group = button.closest(".flex");
    if (group) {
        group.querySelectorAll(".ib-color-pick").forEach((target) => target.classList.remove("active"));
    }
    button.classList.add("active");
    const hidden = document.getElementById("id_color");
    if (hidden) hidden.value = color;
}

function ibInitCardColorPicker() {
    const hidden = document.getElementById("id_color");
    if (!hidden) return;
    const current = hidden.value || "";
    document.querySelectorAll('.ib-color-pick[data-color-value]').forEach((button) => {
        const isActive = button.dataset.colorValue === current || (!current && button.dataset.colorValue === "");
        button.classList.toggle("active", isActive);
    });
}

function ibCopyToClipboard(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    navigator.clipboard.writeText(input.value).then(() => {
        ibToast("링크가 복사되었어요!", "success");
    }).catch(() => {
        input.select();
        document.execCommand("copy");
        ibToast("링크가 복사되었어요!", "success");
    });
}

function ibCopyText(text) {
    navigator.clipboard.writeText(text).then(() => {
        ibToast("복사되었어요!", "success");
    }).catch(() => {
        ibToast("복사에 실패했어요", "error");
    });
}

function ibFullscreenQR() {
    const qrContainer = document.getElementById("ibQrCode");
    if (!qrContainer) return;
    const image = qrContainer.querySelector("img") || qrContainer.querySelector("canvas");
    if (!image) return;

    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;z-index:200;background:white;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer";
    overlay.onclick = () => overlay.remove();

    const clone = image.cloneNode(true);
    clone.style.cssText = "width:min(80vw,400px);height:min(80vw,400px);object-fit:contain";
    overlay.appendChild(clone);

    const hint = document.createElement("p");
    hint.textContent = "화면을 터치하면 닫힙니다";
    hint.style.cssText = "margin-top:1.5rem;color:#94a3b8;font-weight:700;font-size:1rem";
    overlay.appendChild(hint);

    document.body.appendChild(overlay);
}

function ibToast(message, tag) {
    if (window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent("eduitit:toast", { detail: { message, tag } }));
    }
}

function ibFetchOgMeta(url) {
    const setPreviewMessage = function (message, tone) {
        let container = document.getElementById("ibOgPreview");
        if (!container) {
            const urlField = document.getElementById("ibFieldUrl");
            if (!urlField) return;
            container = document.createElement("div");
            container.id = "ibOgPreview";
            container.className = "mt-2";
            urlField.appendChild(container);
        }
        const colorClass = tone === "error" ? "text-rose-500" : "text-gray-400";
        container.innerHTML = `<p class="text-xs ${colorClass}">${message}</p>`;
    };

    setPreviewMessage("메타 정보를 불러오는 중...", "info");

    fetch(`/infoboard/api/og-meta/?url=${encodeURIComponent(url)}`)
        .then(async function (response) {
            if (!response.ok) {
                let payload = {};
                try {
                    payload = await response.json();
                } catch (error) {
                    payload = {};
                }
                throw new Error(payload.error || "미리보기 정보를 가져오지 못했어요.");
            }
            return response.json();
        })
        .then(function (meta) {
            const container = document.getElementById("ibOgPreview");
            if (!container) return;
            if (!meta.og_title && !meta.og_image) {
                container.innerHTML = "";
                return;
            }

            const titleInput = document.getElementById("id_title");
            if (titleInput && !titleInput.value && meta.og_title) {
                titleInput.value = meta.og_title;
            }

            let html = '<div class="ib-og-preview" style="cursor:default">';
            if (meta.og_image) html += `<img src="${meta.og_image}" alt="" style="width:80px;height:60px;object-fit:cover;border-radius:0.5rem">`;
            html += '<div class="ib-og-preview-text">';
            if (meta.og_title) html += `<div class="ib-og-preview-title">${meta.og_title}</div>`;
            if (meta.og_description) html += `<div class="ib-og-preview-desc">${meta.og_description}</div>`;
            if (meta.og_site_name) html += `<div class="ib-og-preview-site">${meta.og_site_name}</div>`;
            html += "</div></div>";
            container.innerHTML = html;
        })
        .catch(function (error) {
            setPreviewMessage(error.message || "미리보기 정보를 가져오지 못했어요.", "error");
        });
}

function ibSetupOgFetch() {
    const urlInput = document.getElementById("id_url");
    if (!urlInput || urlInput.dataset.ibOgBound === "1") return;
    urlInput.dataset.ibOgBound = "1";

    urlInput.addEventListener("input", function () {
        window.clearTimeout(ibOgTimeout);
        const url = this.value.trim();
        if (!url) {
            const preview = document.getElementById("ibOgPreview");
            if (preview) preview.remove();
            return;
        }
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            const preview = document.getElementById("ibOgPreview");
            if (preview) preview.remove();
            return;
        }
        ibOgTimeout = window.setTimeout(() => ibFetchOgMeta(url), 800);
    });

    urlInput.addEventListener("paste", function () {
        window.setTimeout(() => {
            const url = this.value.trim();
            if (url && (url.startsWith("http://") || url.startsWith("https://"))) {
                ibFetchOgMeta(url);
            }
        }, 100);
    });
}

function ibInitInfoboardForms() {
    ibInitTagFields();
    ibInitChoiceCards();
    ibInitBoardPresets();
    ibInitCardTypeTabs();
    ibInitCardColorPicker();
    ibSetupOgFetch();
}

document.addEventListener("DOMContentLoaded", function () {
    ibInitInfoboardForms();
});

document.addEventListener("htmx:afterSettle", function () {
    ibInitInfoboardForms();
});

document.addEventListener("infoboard:close-modal", function () {
    ibCloseModal();
});
