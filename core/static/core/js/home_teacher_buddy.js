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

    function wait(ms) {
        return new Promise(function (resolve) {
            window.setTimeout(resolve, ms);
        });
    }

    function shouldPlayRevealSound() {
        if (!window.AudioContext && !window.webkitAudioContext) {
            return false;
        }
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return false;
        }
        return true;
    }

    function getAudioContext(root) {
        if (!shouldPlayRevealSound()) {
            return null;
        }
        var AudioCtor = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtor) {
            return null;
        }
        if (!root.__buddyAudioContext) {
            root.__buddyAudioContext = new AudioCtor();
        }
        return root.__buddyAudioContext;
    }

    function playTone(context, startAt, frequency, duration, volume, type) {
        var oscillator = context.createOscillator();
        var gain = context.createGain();
        oscillator.type = type || 'sine';
        oscillator.frequency.setValueAtTime(frequency, startAt);
        gain.gain.setValueAtTime(0.0001, startAt);
        gain.gain.exponentialRampToValueAtTime(volume, startAt + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, startAt + duration);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(startAt);
        oscillator.stop(startAt + duration + 0.02);
    }

    function playRevealSound(root, kind) {
        var context = getAudioContext(root);
        if (!context) {
            return;
        }
        if (context.state === 'suspended') {
            context.resume().catch(function () {});
        }
        var startAt = context.currentTime + 0.01;
        var sequences = {
            suspense: [
                [392, 0.08, 0.02, 'triangle'],
                [523, 0.12, 0.025, 'triangle']
            ],
            common: [
                [659, 0.09, 0.03, 'triangle'],
                [880, 0.14, 0.035, 'triangle']
            ],
            rare: [
                [659, 0.08, 0.03, 'triangle'],
                [880, 0.1, 0.04, 'triangle'],
                [988, 0.16, 0.045, 'sine']
            ],
            epic: [
                [659, 0.08, 0.03, 'triangle'],
                [880, 0.1, 0.04, 'triangle'],
                [1174, 0.15, 0.05, 'sine'],
                [1318, 0.22, 0.06, 'sine']
            ],
            legendary: [
                [523, 0.08, 0.035, 'triangle'],
                [784, 0.11, 0.05, 'triangle'],
                [1046, 0.16, 0.06, 'sine'],
                [1568, 0.28, 0.09, 'sine']
            ],
            duplicate: [
                [440, 0.08, 0.02, 'triangle'],
                [392, 0.14, 0.02, 'triangle']
            ]
        };
        var notes = sequences[kind] || sequences.common;
        notes.forEach(function (note) {
            playTone(context, startAt + note[1], note[0], note[2], note[3], note[4]);
        });
    }

    function setProgressSteps(root, pointsToday) {
        root.querySelectorAll('[data-buddy-progress-step]').forEach(function (step) {
            var threshold = parseInt(step.getAttribute('data-buddy-progress-step') || '0', 10);
            step.classList.toggle('is-active', threshold <= pointsToday);
        });
    }

    function setSingleStep(root, selector, active) {
        root.querySelectorAll(selector).forEach(function (step) {
            step.classList.toggle('is-active', Boolean(active));
        });
    }

    function setText(root, selector, value) {
        var node = root.querySelector(selector);
        if (node && typeof value === 'string') {
            node.textContent = value;
        }
    }

    function updateProgress(root, payload, collectionSummaryText) {
        if (!payload) {
            return;
        }
        var pointsToday = parseInt(payload.points_today || 0, 10);
        var tokenCount = parseInt(payload.draw_token_count || 0, 10);
        var tokenReady = Boolean(payload.token_ready);

        setText(root, '[data-buddy-home-progress-text="true"]', payload.home_progress_text || '');
        setText(root, '[data-buddy-home-ticket-condition="true"]', payload.home_ticket_condition_text || '');
        setText(root, '[data-buddy-home-ticket-status="true"]', payload.home_ticket_status_text || '');
        setText(root, '[data-buddy-sns-status="true"]', payload.sns_bonus_text || '');
        setText(root, '[data-buddy-attendance-status="true"]', payload.attendance_text || '');
        setText(root, '[data-buddy-reaction="true"]', payload.reaction_text || '');
        setText(root, '[data-buddy-token-badge="true"]', '토큰 ' + tokenCount);
        if (typeof collectionSummaryText === 'string') {
            setText(root, '[data-buddy-collection-summary="true"]', collectionSummaryText);
        }

        var drawButton = root.querySelector('[data-buddy-draw-button="true"]');
        if (drawButton) {
            drawButton.disabled = !tokenReady;
            drawButton.textContent = '메이트 뽑기';
        }

        var moodCard = root.querySelector('.teacher-buddy-card');
        if (moodCard && payload.mood) {
            moodCard.setAttribute('data-buddy-mood', payload.mood);
        }
        setProgressSteps(root, pointsToday);
        setSingleStep(root, '[data-buddy-sns-step]', !payload.sns_bonus_available);
        setSingleStep(root, '[data-buddy-attendance-step]', payload.attendance_completed);
    }

    function updateActiveBuddy(root, buddy) {
        if (!buddy) {
            return;
        }
        setText(root, '[data-buddy-name="true"]', buddy.name || '');
        setText(root, '[data-buddy-ascii="true"]', buddy.idle_ascii || '');
        var rarity = root.querySelector('[data-buddy-rarity="true"]');
        if (rarity) {
            rarity.textContent = buddy.rarity_label || '';
            rarity.className = 'teacher-buddy-rarity teacher-buddy-rarity--' + (buddy.rarity || 'common');
        }
        var asciiBox = root.querySelector('[data-buddy-ascii-box="true"]');
        if (asciiBox && buddy.palette_tokens && buddy.palette_tokens.gradient) {
            asciiBox.style.setProperty('--teacher-buddy-hero-gradient', buddy.palette_tokens.gradient);
        }
    }

    function setResultStage(root, stage) {
        var modal = root.querySelector('[data-buddy-result-modal="true"]');
        if (!modal) {
            return;
        }
        modal.setAttribute('data-result-stage', stage);
        modal.querySelectorAll('[data-buddy-result-stage]').forEach(function (node) {
            node.hidden = node.getAttribute('data-buddy-result-stage') !== stage;
        });
    }

    function openResultModal(root) {
        var modal = root.querySelector('[data-buddy-result-modal="true"]');
        if (!modal) {
            return;
        }
        root.__buddyLastFocus = document.activeElement;
        root.__buddyResultReady = false;
        setResultStage(root, 'sealed');
        modal.hidden = false;
        modal.classList.add('is-open');
    }

    function populateResult(root, payload) {
        var modal = root.querySelector('[data-buddy-result-modal="true"]');
        var dialog = root.querySelector('[data-buddy-result-dialog="true"]');
        if (!modal || !dialog) {
            return;
        }
        var resultBuddy = payload && (payload.result_buddy || payload.unlocked_buddy) ? (payload.result_buddy || payload.unlocked_buddy) : null;
        dialog.setAttribute('data-result-theme', payload.result_reveal_theme || 'common');
        setText(modal, '[data-buddy-result-theme-title="true"]', payload.result_title || '메이트 결과');
        setText(modal, '[data-buddy-result-name="true"]', resultBuddy ? resultBuddy.name : '교실 메이트');
        setText(modal, '[data-buddy-result-ascii="true"]', resultBuddy ? (resultBuddy.unlock_ascii || resultBuddy.idle_ascii || '') : '');
        setText(modal, '[data-buddy-result-message="true"]', payload.message || '메이트 결과를 확인했어요.');
    }

    function revealResult(root) {
        var modal = root.querySelector('[data-buddy-result-modal="true"]');
        if (!modal) {
            return;
        }
        var dialog = root.querySelector('[data-buddy-result-dialog="true"]');
        setResultStage(root, 'reveal');
        root.__buddyResultReady = true;
        playRevealSound(root, dialog ? (dialog.getAttribute('data-result-theme') || 'common') : 'common');
        var closeButton = modal.querySelector('[data-buddy-result-close="true"]');
        if (closeButton) {
            closeButton.focus();
        }
    }

    function closeResultModal(root) {
        if (!root.__buddyResultReady) {
            return;
        }
        var modal = root.querySelector('[data-buddy-result-modal="true"]');
        if (!modal) {
            return;
        }
        modal.classList.remove('is-open');
        modal.hidden = true;
        if (root.__buddyLastFocus && typeof root.__buddyLastFocus.focus === 'function') {
            root.__buddyLastFocus.focus();
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

    async function runRevealSequence(root, payloadPromise) {
        openResultModal(root);
        await wait(600);
        setResultStage(root, 'suspense');
        playRevealSound(root, 'suspense');
        var payload = null;
        try {
            payload = await Promise.all([payloadPromise, wait(850)]).then(function (values) {
                return values[0];
            });
        } catch (error) {
            var modal = root.querySelector('[data-buddy-result-modal="true"]');
            if (modal) {
                modal.classList.remove('is-open');
                modal.hidden = true;
            }
            root.__buddyResultReady = true;
            throw error;
        }
        if (payload.active_buddy) {
            updateActiveBuddy(root, payload.active_buddy);
        }
        updateProgress(root, payload.buddy_progress || null, payload.collection_summary_text || '');
        populateResult(root, payload);
        revealResult(root);
        return payload;
    }

    function bindPanel(root) {
        root.querySelectorAll('[data-buddy-draw-form="true"]').forEach(function (form) {
            form.addEventListener('submit', async function (event) {
                event.preventDefault();
                var drawButton = form.querySelector('[data-buddy-draw-button="true"]');
                if (drawButton) {
                    drawButton.disabled = true;
                    drawButton.textContent = '봉투 여는 중...';
                }
                try {
                    await runRevealSequence(root, submitForm(form));
                } catch (error) {
                    showFeedback(error.message || '메이트를 뽑지 못했습니다.', 'error');
                    if (drawButton) {
                        drawButton.disabled = false;
                        drawButton.textContent = '메이트 뽑기';
                    }
                }
            });
        });

        root.querySelectorAll('[data-buddy-result-close="true"]').forEach(function (button) {
            button.addEventListener('click', function () {
                closeResultModal(root);
            });
        });
    }

    function initTeacherBuddyPanels() {
        var panels = Array.prototype.slice.call(document.querySelectorAll('[data-teacher-buddy-panel="true"]'));
        if (!panels.length) {
            return;
        }
        panels.forEach(bindPanel);

        document.addEventListener('teacherBuddy:progress', function (event) {
            panels.forEach(function (panel) {
                updateProgress(panel, event.detail || null);
            });
        });

        document.body.addEventListener('teacherBuddy:snsReward', function (event) {
            var detail = event.detail || {};
            panels.forEach(function (panel) {
                updateProgress(panel, detail.buddy_progress || null);
            });
            if (detail.message) {
                showFeedback(detail.message, detail.reward_granted ? 'success' : 'info');
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key !== 'Escape') {
                return;
            }
            panels.forEach(function (panel) {
                closeResultModal(panel);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', initTeacherBuddyPanels);
})();
