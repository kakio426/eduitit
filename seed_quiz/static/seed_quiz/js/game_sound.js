(function () {
    const STORAGE_KEY = 'seed_quiz_game_sound_enabled';
    const SELECTOR = '[data-sqg-sound-toggle]';
    let audioContext = null;
    let storedPreference = window.localStorage.getItem(STORAGE_KEY);
    let enabled = storedPreference === null
        ? document.documentElement.dataset.sqgRoomSoundDefault === '1'
        : storedPreference === '1';

    function applyRoomDefault(root) {
        const source = root && root.querySelector
            ? root.querySelector('[data-sqg-room-sound-default]')
            : null;
        if (!source || window.localStorage.getItem(STORAGE_KEY) !== null) return;
        enabled = source.dataset.sqgRoomSoundDefault === '1';
        syncToggles();
    }

    function getContext() {
        if (!audioContext) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return null;
            audioContext = new AudioContext();
        }
        if (audioContext.state === 'suspended') {
            audioContext.resume().catch(function (error) {
                if (window.console && window.console.debug) {
                    window.console.debug('Seed quiz audio resume failed', error);
                }
            });
        }
        return audioContext;
    }

    function tone(frequency, start, duration, gainValue) {
        const context = getContext();
        if (!context) return;
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(frequency, context.currentTime + start);
        gain.gain.setValueAtTime(0.0001, context.currentTime + start);
        gain.gain.exponentialRampToValueAtTime(gainValue, context.currentTime + start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + start + duration);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(context.currentTime + start);
        oscillator.stop(context.currentTime + start + duration + 0.02);
    }

    function play(kind) {
        if (!enabled) return;
        if (kind === 'correct') {
            tone(660, 0, 0.12, 0.04);
            tone(880, 0.1, 0.14, 0.035);
            return;
        }
        if (kind === 'wrong') {
            tone(220, 0, 0.16, 0.035);
            return;
        }
        if (kind === 'tick') {
            tone(520, 0, 0.06, 0.025);
            return;
        }
        if (kind === 'podium') {
            tone(523, 0, 0.1, 0.035);
            tone(659, 0.1, 0.1, 0.035);
            tone(784, 0.2, 0.18, 0.04);
        }
    }

    function updateToggle(button) {
        button.setAttribute('aria-pressed', enabled ? 'true' : 'false');
        button.textContent = enabled ? '소리 켬' : '소리 끔';
        button.classList.toggle('bg-slate-900', enabled);
        button.classList.toggle('text-white', enabled);
        button.classList.toggle('bg-white/80', !enabled);
        button.classList.toggle('text-slate-700', !enabled);
    }

    function syncToggles() {
        document.querySelectorAll(SELECTOR).forEach(updateToggle);
    }

    document.addEventListener('click', function (event) {
        const button = event.target.closest(SELECTOR);
        if (!button) return;
        enabled = !enabled;
        window.localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
        if (enabled) getContext();
        syncToggles();
    });

    document.body.addEventListener('htmx:afterSwap', function (event) {
        const target = event.detail && event.detail.target;
        if (!target) return;
        applyRoomDefault(target);
        const soundTarget = target.querySelector('[data-sqg-sound-event]');
        if (soundTarget) play(soundTarget.dataset.sqgSoundEvent);
    });

    window.sqgPlaySound = play;
    window.sqgSyncSoundToggles = syncToggles;
    document.addEventListener('DOMContentLoaded', function () {
        applyRoomDefault(document);
        syncToggles();
    });
})();
