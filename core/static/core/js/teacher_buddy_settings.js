(function () {
    function getCsrfToken() {
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        if (field && field.value) {
            return field.value;
        }
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function showFeedback(message, type) {
        if (window.showToast) {
            window.showToast(message, type || 'info');
            return;
        }
        if ((type || 'info') === 'error') {
            alert(message);
        }
    }

    function setHidden(node, hidden) {
        if (!node) {
            return;
        }
        if (hidden) {
            node.setAttribute('hidden', 'hidden');
        } else {
            node.removeAttribute('hidden');
        }
    }

    async function submitForm(form) {
        var response = await fetch(form.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: new FormData(form)
        });
        var payload = {};
        try {
            payload = await response.json();
        } catch (error) {
            payload = {};
        }
        if (!response.ok) {
            throw new Error(payload.error || '요청을 처리하지 못했습니다.');
        }
        return payload;
    }

    async function copyText(value, successMessage) {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(value);
            } else {
                var textarea = document.createElement('textarea');
                textarea.value = value;
                textarea.setAttribute('readonly', 'readonly');
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.focus();
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
            }
            showFeedback(successMessage, 'success');
        } catch (error) {
            showFeedback('클립보드 복사에 실패했습니다.', 'error');
        }
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function renderAscii(node, value) {
        if (!node) {
            return;
        }
        node.innerHTML = '';
        String(value || '').split(/\r?\n/).forEach(function (line) {
            var row = document.createElement('span');
            row.className = 'teacher-buddy-ascii-line';
            row.textContent = String(line || '').trim();
            node.appendChild(row);
        });
    }

    function setAsciiTone(node, asciiTokens, paletteTokens) {
        if (!node) {
            return;
        }
        var tokens = asciiTokens && typeof asciiTokens === 'object' ? asciiTokens : null;
        var palette = paletteTokens && typeof paletteTokens === 'object' ? paletteTokens : null;
        node.style.setProperty('--teacher-buddy-ascii-start', (tokens && tokens.start) || (palette && palette.text) || '#111827');
        node.style.setProperty('--teacher-buddy-ascii-end', (tokens && tokens.end) || (palette && palette.accent) || (palette && palette.text) || '#111827');
    }

    function renderAvatarHTML(buddy) {
        var tokens = buddy.palette_tokens || {};
        return '' +
            '<div class="teacher-buddy-avatar teacher-buddy-avatar--hero is-buddy h-16 w-16 teacher-buddy-profile-avatar" ' +
            'style="--buddy-avatar-start:' + (tokens.bg_start || '#dbeafe') + ';' +
            '--buddy-avatar-end:' + (tokens.bg_end || '#e0e7ff') + ';' +
            '--buddy-avatar-text:' + (tokens.text || '#0f172a') + ';' +
            '--buddy-avatar-accent:' + (tokens.accent || '#4f46e5') + ';">' +
            '<pre class="teacher-buddy-avatar-ascii" data-buddy-avatar-ascii="true">' + escapeHtml(buddy.avatar_ascii || '') + '</pre>' +
            '<span class="teacher-buddy-avatar-dot" aria-hidden="true"></span>' +
            '</div>';
    }

    function getSelectionState(root) {
        var representativeCard = root.querySelector('[data-buddy-preview-card="representative"]');
        return {
            representativeKey: representativeCard ? (representativeCard.getAttribute('data-buddy-preview-buddy-key') || '') : '',
            representativeSkinKey: representativeCard ? (representativeCard.getAttribute('data-buddy-preview-skin-key') || '') : ''
        };
    }

    function applyPayloadToState(state, payload) {
        var representative = payload.profile_buddy || payload.active_buddy;
        if (!representative) {
            return;
        }
        state.representativeKey = representative.key || state.representativeKey;
        state.representativeSkinKey = representative.selected_skin_key || '';
    }

    function updatePreviewCard(root, buddy, captionText, summaryText) {
        if (!buddy) {
            return;
        }
        var card = root.querySelector('[data-buddy-preview-card="representative"]');
        if (!card) {
            return;
        }
        card.setAttribute('data-buddy-preview-buddy-key', buddy.key || '');
        card.setAttribute('data-buddy-preview-skin-key', buddy.selected_skin_key || '');
        if (buddy.palette_tokens && buddy.palette_tokens.gradient) {
            card.style.setProperty('--teacher-buddy-hero-gradient', buddy.palette_tokens.gradient);
        }
        var avatarWrap = root.querySelector('[data-buddy-preview-avatar="representative"]');
        if (avatarWrap) {
            avatarWrap.innerHTML = renderAvatarHTML(buddy);
        }
        var name = root.querySelector('[data-buddy-preview-name="representative"]');
        var caption = root.querySelector('[data-buddy-preview-caption="representative"]');
        var ascii = root.querySelector('[data-buddy-preview-ascii="representative"]');
        var rarity = root.querySelector('[data-buddy-preview-rarity="representative"]');
        var summary = root.querySelector('[data-buddy-preview-summary="representative"]');
        var style = root.querySelector('[data-buddy-preview-style="representative"]');

        if (name) {
            name.textContent = buddy.name || '';
        }
        if (caption) {
            caption.textContent = captionText || buddy.share_caption || '';
        }
        if (ascii) {
            renderAscii(ascii, buddy.idle_ascii || '');
            setAsciiTone(ascii, buddy.ascii_tokens, buddy.palette_tokens || {});
        }
        if (rarity) {
            rarity.textContent = buddy.rarity_label || '';
            rarity.className = 'teacher-buddy-rarity teacher-buddy-rarity--' + (buddy.rarity || 'common');
        }
        if (summary && typeof summaryText === 'string') {
            summary.textContent = summaryText;
        }
        if (style) {
            style.textContent = buddy.selected_skin_label || '기본 스타일';
        }
    }

    function updateSummaries(root, payload) {
        var buddySummary = root.querySelector('[data-buddy-settings-buddy-summary="true"]');
        var styleSummary = root.querySelector('[data-buddy-settings-style-summary="true"]');
        if (buddySummary && payload.buddy_collection_summary_text) {
            buddySummary.textContent = payload.buddy_collection_summary_text;
        }
        if (styleSummary && payload.style_collection_summary_text) {
            styleSummary.textContent = payload.style_collection_summary_text;
        }
    }

    function updateTokenBadge(root, count) {
        var badge = root.querySelector('[data-buddy-settings-token="true"]');
        if (!badge) {
            return;
        }
        badge.textContent = '보유 뽑기권 ' + parseInt(count || 0, 10) + '장';
    }

    function buildApplyAction(root, buddyKey, skinKey, isSelected) {
        if (isSelected) {
            return '<span class="teacher-buddy-status-chip" data-buddy-style-status="representative">현재 대표</span>';
        }
        var action = root.dataset.selectUrl;
        return '' +
            '<form method="post" action="' + action + '" data-buddy-apply-form="representative">' +
            '<input type="hidden" name="csrfmiddlewaretoken" value="' + getCsrfToken() + '">' +
            '<input type="hidden" name="buddy_key" value="' + buddyKey + '">' +
            '<input type="hidden" name="skin_key" value="' + skinKey + '">' +
            '<button type="submit" class="teacher-buddy-inline-button">대표로 적용</button>' +
            '</form>';
    }

    function buildBuddyApplyAction(root, buddyKey, hasExtraStyles, isSelected) {
        if (isSelected) {
            return '<span class="teacher-buddy-status-chip" data-buddy-card-status="true">현재 대표</span>';
        }
        var action = root.dataset.selectUrl;
        return '' +
            '<form method="post" action="' + action + '" data-buddy-apply-form="representative" data-buddy-card-form="true">' +
            '<input type="hidden" name="csrfmiddlewaretoken" value="' + getCsrfToken() + '">' +
            '<input type="hidden" name="buddy_key" value="' + buddyKey + '">' +
            '<input type="hidden" name="skin_key" value="">' +
            '<button type="submit" class="teacher-buddy-inline-button">' + (hasExtraStyles ? '기본으로 적용' : '대표로 적용') + '</button>' +
            '</form>';
    }

    function renderStyleActions(root, option, state) {
        var actions = option.querySelector('[data-buddy-style-actions="true"]');
        if (!actions) {
            return;
        }
        var unlocked = option.getAttribute('data-style-unlocked') === 'true';
        var buddyKey = option.getAttribute('data-buddy-key') || '';
        var skinKey = option.getAttribute('data-skin-key') || '';
        var styleDefault = option.getAttribute('data-style-default') === 'true';
        if (!unlocked && !styleDefault) {
            actions.innerHTML = '<span class="teacher-buddy-status-chip teacher-buddy-status-chip--soft">메이트 뽑기에서 등장</span>';
            return;
        }
        var isSelected = buddyKey === state.representativeKey && (skinKey || '') === (state.representativeSkinKey || '');
        actions.innerHTML = buildApplyAction(root, buddyKey, skinKey, isSelected);
    }

    function renderBuddyActions(root, card, state) {
        var actions = card.querySelector('[data-buddy-card-actions="true"]');
        if (!actions) {
            return;
        }
        var buddyKey = card.getAttribute('data-buddy-key') || '';
        var isLocked = card.getAttribute('data-buddy-locked') === 'true';
        if (isLocked || !buddyKey) {
            actions.innerHTML = '';
            return;
        }
        var styleTotal = parseInt(card.getAttribute('data-buddy-style-total') || '1', 10);
        var hasExtraStyles = !Number.isNaN(styleTotal) && styleTotal > 1;
        var isSelected = buddyKey === state.representativeKey;
        actions.innerHTML = buildBuddyApplyAction(root, buddyKey, hasExtraStyles, isSelected);
    }

    function updateSelectionUI(root, state) {
        root.querySelectorAll('[data-buddy-settings-item="true"]').forEach(function (card) {
            var buddyKey = card.getAttribute('data-buddy-key') || '';
            var isSelected = buddyKey === state.representativeKey;
            card.classList.toggle('is-profile', isSelected);
            card.classList.toggle('is-active', isSelected);
            renderBuddyActions(root, card, state);
        });

        root.querySelectorAll('[data-buddy-style-option="true"]').forEach(function (option) {
            var buddyKey = option.getAttribute('data-buddy-key') || '';
            var skinKey = option.getAttribute('data-skin-key') || '';
            var isSelected = buddyKey === state.representativeKey && skinKey === (state.representativeSkinKey || '');
            option.classList.toggle('is-profile', isSelected);
            option.classList.toggle('is-active', isSelected);
            renderStyleActions(root, option, state);
        });
    }

    function updateCollectionItem(root, item, state) {
        if (!item || !item.key) {
            return;
        }
        var card = null;
        root.querySelectorAll('[data-buddy-settings-item="true"]').forEach(function (candidate) {
            if (!card && candidate.getAttribute('data-buddy-key') === item.key) {
                card = candidate;
            }
        });
        if (!card) {
            return;
        }
        var summary = card.querySelector('[data-buddy-style-summary="true"]');
        var ascii = card.querySelector('.teacher-buddy-collection-ascii');
        if (summary && item.style_summary_text) {
            summary.textContent = item.style_summary_text;
        }
        if (ascii) {
            renderAscii(ascii, item.idle_ascii || '');
            setAsciiTone(ascii, item.ascii_tokens, item.palette_tokens || {});
        }
        (item.style_options || []).forEach(function (style) {
            card.querySelectorAll('[data-buddy-style-option="true"]').forEach(function (option) {
                if (option.getAttribute('data-skin-key') === (style.skin_key || '')) {
                    option.setAttribute('data-style-unlocked', style.is_unlocked ? 'true' : 'false');
                    var copy = option.querySelector('.teacher-buddy-style-copy');
                    if (copy) {
                        if (style.is_default) {
                            copy.textContent = '기본 스타일';
                        } else if (style.is_unlocked) {
                            copy.textContent = '해금 완료';
                        } else {
                            copy.textContent = '뽑기로 만나기';
                        }
                    }
                }
            });
        });
        updateSelectionUI(root, state);
    }

    function bindStyleToggles(root) {
        root.querySelectorAll('[data-buddy-style-toggle="true"]').forEach(function (button) {
            button.addEventListener('click', function () {
                var card = button.closest('[data-buddy-settings-item="true"]');
                var drawer = card ? card.querySelector('[data-buddy-style-drawer="true"]') : null;
                if (!drawer) {
                    return;
                }
                var nextHidden = !drawer.hasAttribute('hidden');
                setHidden(drawer, nextHidden);
                button.setAttribute('aria-expanded', nextHidden ? 'false' : 'true');
            });
        });
    }

    function bindForms(root, state) {
        root.addEventListener('submit', async function (event) {
            var form = event.target;
            if (!form.matches('[data-buddy-apply-form]')) {
                return;
            }
            event.preventDefault();
            try {
                var payload = await submitForm(form);
                applyPayloadToState(state, payload);
                updateSummaries(root, payload);
                updatePreviewCard(
                    root,
                    payload.profile_buddy || payload.active_buddy,
                    payload.profile_buddy ? (payload.profile_buddy.share_caption || '') : '',
                    root.dataset.sharedSelectionCopy || '대표를 고르면 홈과 SNS에 함께 반영돼요.'
                );
                if (payload.collection_item) {
                    updateCollectionItem(root, payload.collection_item, state);
                } else {
                    updateSelectionUI(root, state);
                }
                showFeedback(payload.message || '메이트를 변경했어요.', 'success');
            } catch (error) {
                showFeedback(error.message || '메이트를 변경하지 못했습니다.', 'error');
            }
        });
    }

    function bindShareModal(root) {
        var modal = root.querySelector('[data-buddy-share-modal="true"]');
        if (!modal) {
            return;
        }
        function openModal() {
            root.__buddyShareLastFocus = document.activeElement;
            modal.hidden = false;
            modal.classList.add('is-open');
            var firstButton = modal.querySelector('[data-buddy-community-share="true"]');
            if (firstButton) {
                firstButton.focus();
            }
        }
        function closeModal() {
            modal.classList.remove('is-open');
            modal.hidden = true;
            if (root.__buddyShareLastFocus && typeof root.__buddyShareLastFocus.focus === 'function') {
                root.__buddyShareLastFocus.focus();
            }
        }
        root.querySelectorAll('[data-buddy-share-open="true"]').forEach(function (button) {
            button.addEventListener('click', openModal);
        });
        root.querySelectorAll('[data-buddy-share-close="true"]').forEach(function (button) {
            button.addEventListener('click', closeModal);
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
    }

    function bindShareActions(root) {
        var shareData = root.querySelector('.teacher-buddy-share-data');
        if (!shareData) {
            return;
        }
        var shareUrl = shareData.dataset.shareUrl || '';
        var shareImageUrl = shareData.dataset.shareImageUrl || '';
        var shareFilename = shareData.dataset.shareFilename || 'teacher-buddy.svg';
        var shareTitle = shareData.dataset.shareTitle || '교실 메이트';
        var shareDescription = shareData.dataset.shareDescription || '';
        var indischoolCopy = shareData.dataset.shareIndischool || shareDescription;
        var instagramCopy = shareData.dataset.shareInstagram || shareDescription;
        var kakaoJsKey = shareData.dataset.kakaoJsKey || '';

        var kakaoButton = root.querySelector('[data-buddy-share-kakao="true"]');
        if (kakaoButton) {
            kakaoButton.addEventListener('click', async function () {
                if (!(window.Kakao && kakaoJsKey)) {
                    await copyText(shareUrl, '카카오 SDK가 없어 링크를 복사해 드렸어요.');
                    return;
                }
                if (!window.Kakao.isInitialized()) {
                    window.Kakao.init(kakaoJsKey);
                }
                window.Kakao.Share.sendDefault({
                    objectType: 'feed',
                    content: {
                        title: shareTitle,
                        description: shareDescription,
                        imageUrl: shareImageUrl,
                        link: {
                            mobileWebUrl: shareUrl,
                            webUrl: shareUrl
                        }
                    },
                    buttons: [
                        {
                            title: '메이트 보기',
                            link: {
                                mobileWebUrl: shareUrl,
                                webUrl: shareUrl
                            }
                        }
                    ]
                });
            });
        }

        var copyLinkButton = root.querySelector('[data-buddy-copy-link="true"]');
        if (copyLinkButton) {
            copyLinkButton.addEventListener('click', function () {
                copyText(shareUrl, '공유 링크를 복사했어요.');
            });
        }

        var indischoolButton = root.querySelector('[data-buddy-copy-indischool="true"]');
        if (indischoolButton) {
            indischoolButton.addEventListener('click', function () {
                copyText(indischoolCopy, '인디스쿨용 문구를 복사했어요.');
            });
        }

        var instagramButton = root.querySelector('[data-buddy-copy-instagram="true"]');
        if (instagramButton) {
            instagramButton.addEventListener('click', function () {
                copyText(instagramCopy, '인스타그램용 문구를 복사했어요.');
            });
        }

        var downloadButton = root.querySelector('[data-buddy-download-image="true"]');
        if (downloadButton) {
            downloadButton.addEventListener('click', function () {
                var link = document.createElement('a');
                link.href = shareImageUrl;
                link.download = shareFilename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                showFeedback('공유 이미지를 저장했어요.', 'success');
            });
        }
    }

    function bindCouponForm(root) {
        var form = root.querySelector('[data-buddy-coupon-form="true"]');
        if (!form) {
            return;
        }
        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            var input = form.querySelector('[data-buddy-coupon-input="true"]');
            var submitButton = form.querySelector('[data-buddy-coupon-submit="true"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = '등록 중...';
            }
            try {
                var payload = await submitForm(form);
                updateTokenBadge(root, payload.draw_token_count || 0);
                if (input) {
                    input.value = '';
                }
                showFeedback(payload.message || '쿠폰을 등록했어요.', 'success');
            } catch (error) {
                showFeedback(error.message || '쿠폰을 등록하지 못했습니다.', 'error');
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = '쿠폰 등록';
                }
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-teacher-buddy-settings="true"]');
        if (!root) {
            return;
        }
        var state = getSelectionState(root);
        bindStyleToggles(root);
        bindForms(root, state);
        bindShareModal(root);
        bindShareActions(root);
        bindCouponForm(root);
        updateSelectionUI(root, state);
    });
})();
