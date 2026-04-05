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

    function renderAvatarHTML(buddy) {
        var tokens = buddy.palette_tokens || {};
        return '' +
            '<div class="teacher-buddy-avatar is-buddy h-14 w-14 teacher-buddy-profile-avatar" ' +
            'style="--buddy-avatar-start:' + (tokens.bg_start || '#dbeafe') + ';' +
            '--buddy-avatar-end:' + (tokens.bg_end || '#e0e7ff') + ';' +
            '--buddy-avatar-text:' + (tokens.text || '#0f172a') + ';' +
            '--buddy-avatar-accent:' + (tokens.accent || '#4f46e5') + ';">' +
            '<span class="teacher-buddy-avatar-mark">' + (buddy.avatar_mark || '*') + '</span>' +
            '<span class="teacher-buddy-avatar-dot" aria-hidden="true"></span>' +
            '</div>';
    }

    function getSelectionState(root) {
        var profileCard = root.querySelector('[data-buddy-preview-card="profile"]');
        var homeCard = root.querySelector('[data-buddy-preview-card="home"]');
        return {
            mode: root.dataset.selectionMode || 'profile',
            profileKey: profileCard ? (profileCard.getAttribute('data-buddy-preview-buddy-key') || '') : '',
            profileSkinKey: profileCard ? (profileCard.getAttribute('data-buddy-preview-skin-key') || '') : '',
            homeKey: homeCard ? (homeCard.getAttribute('data-buddy-preview-buddy-key') || '') : '',
            homeSkinKey: homeCard ? (homeCard.getAttribute('data-buddy-preview-skin-key') || '') : ''
        };
    }

    function applyPayloadToState(state, payload) {
        if (payload.profile_buddy) {
            state.profileKey = payload.profile_buddy.key || state.profileKey;
            state.profileSkinKey = payload.profile_buddy.selected_skin_key || '';
        }
        if (payload.active_buddy) {
            state.homeKey = payload.active_buddy.key || state.homeKey;
            state.homeSkinKey = payload.active_buddy.selected_skin_key || '';
        }
    }

    function updatePreviewCard(root, type, buddy, captionText, summaryText) {
        if (!buddy) {
            return;
        }
        var card = root.querySelector('[data-buddy-preview-card="' + type + '"]');
        if (!card) {
            return;
        }
        card.setAttribute('data-buddy-preview-buddy-key', buddy.key || '');
        card.setAttribute('data-buddy-preview-skin-key', buddy.selected_skin_key || '');
        if (buddy.palette_tokens && buddy.palette_tokens.gradient) {
            card.style.setProperty('--teacher-buddy-hero-gradient', buddy.palette_tokens.gradient);
        }
        var avatarWrap = root.querySelector('[data-buddy-preview-avatar="' + type + '"]');
        if (avatarWrap && type === 'profile') {
            avatarWrap.innerHTML = renderAvatarHTML(buddy);
        }
        var name = root.querySelector('[data-buddy-preview-name="' + type + '"]');
        var caption = root.querySelector('[data-buddy-preview-caption="' + type + '"]');
        var ascii = root.querySelector('[data-buddy-preview-ascii="' + type + '"]');
        var rarity = root.querySelector('[data-buddy-preview-rarity="' + type + '"]');
        var summary = root.querySelector('[data-buddy-preview-summary="' + type + '"]');
        var style = root.querySelector('[data-buddy-preview-style="' + type + '"]');

        if (name) {
            name.textContent = buddy.name || '';
        }
        if (caption) {
            caption.textContent = captionText || buddy.share_caption || '';
        }
        if (ascii) {
            ascii.textContent = buddy.idle_ascii || '';
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
        var dust = root.querySelector('[data-buddy-settings-dust="true"]');
        var buddySummary = root.querySelector('[data-buddy-settings-buddy-summary="true"]');
        var styleSummary = root.querySelector('[data-buddy-settings-style-summary="true"]');
        if (dust && typeof payload.sticker_dust !== 'undefined') {
            dust.textContent = '스타일 조각 ' + parseInt(payload.sticker_dust || 0, 10) + '개';
        }
        if (buddySummary && payload.buddy_collection_summary_text) {
            buddySummary.textContent = payload.buddy_collection_summary_text;
        }
        if (styleSummary && payload.style_collection_summary_text) {
            styleSummary.textContent = payload.style_collection_summary_text;
        }
    }

    function buildApplyAction(root, mode, buddyKey, skinKey, isSelected) {
        if (isSelected) {
            return '<span class="teacher-buddy-status-chip" data-buddy-style-status="' + mode + '">' + (mode === 'profile' ? 'SNS 대표' : '홈 메이트') + '</span>';
        }
        var action = mode === 'profile' ? root.dataset.selectProfileUrl : root.dataset.selectUrl;
        var buttonLabel = mode === 'profile' ? 'SNS 대표로 적용' : '홈에 적용';
        var buttonClass = mode === 'profile' ? 'teacher-buddy-inline-button' : 'teacher-buddy-inline-button teacher-buddy-inline-button--secondary';
        return '' +
            '<form method="post" action="' + action + '" data-buddy-apply-form="' + mode + '">' +
            '<input type="hidden" name="csrfmiddlewaretoken" value="' + getCsrfToken() + '">' +
            '<input type="hidden" name="buddy_key" value="' + buddyKey + '">' +
            '<input type="hidden" name="skin_key" value="' + skinKey + '">' +
            '<button type="submit" class="' + buttonClass + '">' + buttonLabel + '</button>' +
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
            actions.innerHTML = '' +
                '<form method="post" action="' + root.dataset.unlockSkinUrl + '" data-buddy-unlock-form="true">' +
                '<input type="hidden" name="csrfmiddlewaretoken" value="' + getCsrfToken() + '">' +
                '<input type="hidden" name="buddy_key" value="' + buddyKey + '">' +
                '<input type="hidden" name="skin_key" value="' + skinKey + '">' +
                '<button type="submit" class="teacher-buddy-inline-button">스킨 해금</button>' +
                '</form>';
            return;
        }
        var isProfile = buddyKey === state.profileKey && (skinKey || '') === (state.profileSkinKey || '');
        var isHome = buddyKey === state.homeKey && (skinKey || '') === (state.homeSkinKey || '');
        actions.innerHTML = buildApplyAction(root, state.mode, buddyKey, skinKey, state.mode === 'profile' ? isProfile : isHome);
    }

    function updateSelectionUI(root, state) {
        root.dataset.selectionMode = state.mode;
        var help = root.querySelector('[data-buddy-mode-help="true"]');
        if (help) {
            help.textContent = state.mode === 'profile' ? '현재: SNS 대표 메이트 선택 모드' : '현재: 홈 메이트 선택 모드';
        }
        root.querySelectorAll('[data-buddy-mode-trigger]').forEach(function (button) {
            var selected = button.getAttribute('data-buddy-mode-trigger') === state.mode;
            button.classList.toggle('is-active', selected);
            button.setAttribute('aria-pressed', selected ? 'true' : 'false');
        });

        root.querySelectorAll('[data-buddy-settings-item="true"]').forEach(function (card) {
            var buddyKey = card.getAttribute('data-buddy-key') || '';
            card.classList.toggle('is-profile', buddyKey === state.profileKey);
            card.classList.toggle('is-active', buddyKey === state.homeKey);
        });

        root.querySelectorAll('[data-buddy-style-option="true"]').forEach(function (option) {
            var buddyKey = option.getAttribute('data-buddy-key') || '';
            var skinKey = option.getAttribute('data-skin-key') || '';
            option.classList.toggle('is-profile', buddyKey === state.profileKey && skinKey === (state.profileSkinKey || ''));
            option.classList.toggle('is-active', buddyKey === state.homeKey && skinKey === (state.homeSkinKey || ''));
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
        if (summary && item.style_summary_text) {
            summary.textContent = item.style_summary_text;
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
                copy.textContent = '스타일 조각 ' + parseInt(style.unlock_cost_dust || 0, 10) + '개';
                        }
                    }
                }
            });
        });
        updateSelectionUI(root, state);
    }

    function bindModeButtons(root, state) {
        root.querySelectorAll('[data-buddy-mode-trigger]').forEach(function (button) {
            button.addEventListener('click', function () {
                state.mode = button.getAttribute('data-buddy-mode-trigger') || 'profile';
                updateSelectionUI(root, state);
            });
        });
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
            if (!form.matches('[data-buddy-apply-form], [data-buddy-unlock-form="true"]')) {
                return;
            }
            event.preventDefault();
            try {
                var payload = await submitForm(form);
                applyPayloadToState(state, payload);
                updateSummaries(root, payload);
                if (payload.profile_buddy) {
                    updatePreviewCard(root, 'profile', payload.profile_buddy, payload.profile_buddy.share_caption || '', payload.collection_summary_text || '');
                }
                if (payload.active_buddy) {
                    updatePreviewCard(
                        root,
                        'home',
                        payload.active_buddy,
                        payload.buddy_progress ? payload.buddy_progress.legendary_progress_text : '',
                        payload.buddy_progress ? payload.buddy_progress.home_progress_text : ''
                    );
                }
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

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-teacher-buddy-settings="true"]');
        if (!root) {
            return;
        }
        var state = getSelectionState(root);
        bindModeButtons(root, state);
        bindStyleToggles(root);
        bindForms(root, state);
        bindShareModal(root);
        bindShareActions(root);
        updateSelectionUI(root, state);
    });
})();
