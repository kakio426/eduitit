/**
 * DutyTicker Logic Manager (Vanilla JS Port)
 */
class DutyTickerManager {
    constructor() {
        // State
        this.roles = [];
        this.students = [];
        this.todaySchedule = [];
        this.isBroadcasting = false;
        this.broadcastMessage = '';
        this.isSoundEnabled = localStorage.getItem('dt-broadcast-sound') !== 'false';
        this.currentAlert = null;
        this.selectedRoleId = null;

        // Timer State
        this.timerSeconds = 300;
        this.timerMaxSeconds = 300;
        this.isTimerRunning = false;
        this.timerInterval = null;

        // Sound Context (Lazy initialized)
        this.audioCtx = null;
        this.broadcastInterval = null;
    }

    init() {
        console.log("DutyTicker Manager Initializing...");
        this.loadData();
        this.initUI();
        this.setupEventListeners();
        this.startBackgroundProcesses();
        this.renderAll();
    }

    loadData() {
        // Roles
        const savedRoles = localStorage.getItem('dt-roles');
        this.roles = savedRoles ? JSON.parse(savedRoles) : [...mockRoles];

        // Students
        this.students = [...mockStudents];

        // Schedule
        const todayIdx = new Date().getDay();
        const displayDay = (todayIdx === 0 || todayIdx === 6) ? 1 : todayIdx;
        this.todaySchedule = mockWeeklySchedule[displayDay] || [];
    }

    saveRoles() {
        localStorage.setItem('dt-roles', JSON.stringify(this.roles));
    }

    initUI() {
        // Init Sound Switch UI
        const soundBtn = document.getElementById('toggleSoundBtn');
        if (soundBtn) {
            this.updateSoundUI();
        }
    }

    setupEventListeners() {
        // Broadcast
        document.getElementById('broadcastBtn').onclick = () => this.openBroadcastModal();
        document.getElementById('sendBroadcastBtn').onclick = () => this.handleStartBroadcast();
        document.getElementById('toggleSoundBtn').onclick = () => this.toggleBroadcastSound();

        // Alert
        document.getElementById('alertDismissBtn').onclick = () => this.dismissAlert();

        // Timer
        document.getElementById('timerToggle').onclick = () => this.toggleTimer();
        document.getElementById('timerReset').onclick = () => this.resetTimer();

        const timerModes = document.querySelectorAll('.timer-mode'); // Note: added class in main.html implicitly or here
        // If I haven't added classes, I'll use index or text for now
        const modeButtons = document.querySelectorAll('#timerCardRoot button'); // More specific selector needed
    }

    startBackgroundProcesses() {
        // Schedule Checker
        setInterval(() => this.checkScheduleAlerts(), 1000);

        // Clock is already handled in main.html script block
    }

    // --- Role Management ---
    renderCurrentRole() {
        const role = this.roles.find(r => r.status === 'pending') || null;
        const roleState = document.getElementById('roleState');
        const broadcastState = document.getElementById('broadcastState');
        const emptyState = document.getElementById('emptyState');

        // Reset display
        [roleState, broadcastState, emptyState].forEach(el => el.classList.add('hidden'));

        if (this.isBroadcasting) {
            broadcastState.classList.remove('hidden');
            document.getElementById('broadcastMessageDisplay').textContent = this.broadcastMessage;
            return;
        }

        if (!role) {
            emptyState.classList.remove('hidden');
            return;
        }

        roleState.classList.remove('hidden');
        document.getElementById('roleTimeSlot').textContent = role.timeSlot;
        document.getElementById('roleNameDisplay').textContent = role.name;
        document.getElementById('roleAssigneeName').textContent = role.assignee;

        const descText = document.getElementById('roleDescriptionText');
        if (role.description) {
            document.getElementById('roleDescriptionContainer').classList.remove('hidden');
            descText.textContent = role.description;
        } else {
            document.getElementById('roleDescriptionContainer').classList.add('hidden');
        }

        roleState.onclick = () => this.openStudentModal(role.id);
    }

    renderTimeline() {
        const ticker = document.getElementById('timelineTicker');
        if (!ticker) return;

        // Duplicate roles for seamless scrolling if many
        const displayRoles = this.roles.length > 4 ? [...this.roles, ...this.roles] : this.roles;

        ticker.innerHTML = displayRoles.map((role, idx) => `
            <div class="p-6 rounded-[1.5rem] flex justify-between items-center transition-all border border-[var(--border)] cursor-pointer shadow-lg ${role.status === 'completed' ? 'opacity-40 grayscale-[0.5]' : 'bg-[var(--bg-card)]'}"
                 onclick="window.dtApp.openStudentModal('${role.id}')">
                <div class="flex-1">
                    <div class="flex items-center gap-3">
                        <span class="text-xs font-black px-3 py-1 rounded-full uppercase tracking-widest ${role.status === 'completed' ? 'bg-[var(--bg-accent)] text-[var(--text-muted)]' : 'bg-[var(--accent)]/20 text-[var(--accent)] border border-[var(--accent)]/20'}">
                            ${role.timeSlot}
                        </span>
                    </div>
                    <p class="font-black text-2xl mt-2 tracking-tight ${role.status === 'completed' ? 'line-through decoration-[var(--text-muted)] text-[var(--text-muted)]' : 'text-[var(--text-main)]'}">
                        ${role.name}
                    </p>
                    <p class="text-[var(--accent)] font-bold text-lg mt-1">${role.assignee}</p>
                </div>
                <div class="ml-4" onclick="event.stopPropagation(); window.dtApp.toggleRoleStatus('${role.id}')">
                    ${role.status === 'completed' ?
                '<div class="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center border border-green-500/20"><span class="text-green-500 text-2xl font-bold">✓</span></div>' :
                '<div class="w-10 h-10 rounded-full bg-[var(--bg-accent)] flex items-center justify-center border border-[var(--border)] group"><div class="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse"></div></div>'
            }
                </div>
            </div>
        `).join('');

        // Apply scrolling animation
        if (this.roles.length > 4) {
            ticker.classList.add('ticker-active');
            document.querySelector('.status-dot').classList.add('status-dot-active');
            document.querySelector('.indicator-text').textContent = "Scrolling";
        } else {
            ticker.classList.remove('ticker-active');
            document.querySelector('.status-dot').classList.remove('status-dot-active');
            document.querySelector('.indicator-text').textContent = "Fixed";
        }
    }

    renderAll() {
        this.renderCurrentRole();
        this.renderTimeline();
    }

    toggleRoleStatus(roleId) {
        this.roles = this.roles.map(r => r.id === roleId ?
            { ...r, status: r.status === 'completed' ? 'pending' : 'completed' } : r
        );
        this.saveRoles();
        this.renderAll();
    }

    updateRoleAssignee(roleId, attendee) {
        this.roles = this.roles.map(r => r.id === roleId ? { ...r, assignee: attendee } : r);
        this.saveRoles();
        this.renderAll();
    }

    // --- Modals ---
    openBroadcastModal() {
        const modal = document.getElementById('broadcastModal');
        modal.classList.remove('hidden');
        setTimeout(() => modal.classList.remove('opacity-0'), 10);
        document.getElementById('broadcastInput').focus();
    }

    handleStartBroadcast() {
        const msg = document.getElementById('broadcastInput').value;
        if (!msg.trim()) return;

        this.broadcastMessage = msg;
        this.isBroadcasting = true;
        closeBroadcastModal();
        this.updateBroadcastBtnUI();
        this.renderCurrentRole();
        this.startBroadcastSoundLoop();
    }

    stopBroadcast() {
        this.isBroadcasting = false;
        this.broadcastMessage = '';
        this.updateBroadcastBtnUI();
        this.renderCurrentRole();
        this.stopBroadcastSoundLoop();
    }

    updateBroadcastBtnUI() {
        const btn = document.getElementById('broadcastBtn');
        const icon = document.getElementById('broadcastIcon');
        const spin = document.getElementById('broadcastBtnSpin');

        if (this.isBroadcasting) {
            btn.classList.replace('bg-[var(--accent)]', 'bg-red-500');
            icon.classList.replace('fa-bullhorn', 'fa-xmark');
            spin.classList.remove('hidden');
            btn.onclick = () => this.stopBroadcast();
        } else {
            btn.classList.replace('bg-red-500', 'bg-[var(--accent)]');
            icon.classList.replace('fa-xmark', 'fa-bullhorn');
            spin.classList.add('hidden');
            btn.onclick = () => this.openBroadcastModal();
        }
    }

    toggleBroadcastSound() {
        this.isSoundEnabled = !this.isSoundEnabled;
        localStorage.setItem('dt-broadcast-sound', this.isSoundEnabled);
        this.updateSoundUI();
    }

    updateSoundUI() {
        const btn = document.getElementById('toggleSoundBtn');
        const dot = btn.querySelector('div');
        if (this.isSoundEnabled) {
            btn.classList.replace('bg-gray-400', 'bg-[var(--accent)]');
            dot.classList.replace('left-1', 'left-7');
        } else {
            btn.classList.add('bg-gray-400');
            btn.classList.remove('bg-[var(--accent)]');
            dot.classList.replace('left-7', 'left-1');
        }
    }

    openStudentModal(roleId) {
        this.selectedRoleId = roleId;
        const role = this.roles.find(r => r.id === roleId);
        document.getElementById('studentModalTitle').textContent = role.name;

        const grid = document.getElementById('studentListGrid');
        grid.innerHTML = this.students.map(s => `
            <button onclick="window.dtApp.handleStudentSelect('${s}')" 
                    class="py-3 px-2 bg-[var(--bg-accent)] border border-[var(--border)] rounded-xl font-bold text-lg hover:bg-[var(--accent)] hover:text-white transition-all">
                ${s}
            </button>
        `).join('');

        const modal = document.getElementById('studentModal');
        modal.classList.remove('hidden');
        setTimeout(() => modal.classList.remove('opacity-0'), 10);

        // Setup toggle button in modal
        document.getElementById('toggleRoleStatusBtn').onclick = () => {
            this.toggleRoleStatus(roleId);
            closeStudentModal();
        };
    }

    handleStudentSelect(name) {
        if (this.selectedRoleId) {
            this.updateRoleAssignee(this.selectedRoleId, name);
            closeStudentModal();
        }
    }

    // --- Alerts ---
    checkScheduleAlerts() {
        const now = new Date();
        const mins = now.getHours() * 60 + now.getMinutes();

        const upcoming = this.todaySchedule.find(session => {
            const [h, m] = session.startTime.split(':').map(Number);
            return (h * 60 + m) - mins === 5;
        });

        if (upcoming && (!this.currentAlert || this.currentAlert.id !== upcoming.id)) {
            this.showAlert(`${upcoming.name} 시작 5분 전입니다!`, upcoming.id);
        }
    }

    showAlert(msg, id) {
        this.currentAlert = { message: msg, id: id };
        document.getElementById('alertMessage').textContent = msg;
        const overlay = document.getElementById('alertOverlay');
        overlay.classList.remove('hidden');
        setTimeout(() => overlay.classList.replace('opacity-0', 'opacity-100'), 10);
        this.playDing();
    }

    dismissAlert() {
        const overlay = document.getElementById('alertOverlay');
        overlay.classList.replace('opacity-100', 'opacity-0');
        setTimeout(() => {
            overlay.classList.add('hidden');
            this.currentAlert = null;
        }, 300);
    }

    // --- Timer ---
    toggleTimer() {
        if (this.isTimerRunning) {
            this.pauseTimer();
        } else {
            this.startTimer();
        }
    }

    startTimer() {
        this.isTimerRunning = true;
        document.getElementById('timerToggle').innerHTML = '<i class="fa-solid fa-pause"></i>';
        this.timerInterval = setInterval(() => {
            this.timerSeconds--;
            if (this.timerSeconds <= 0) {
                this.timerSeconds = 0;
                this.pauseTimer();
                this.playAlert(); // Timer end sound
            }
            this.updateTimerDisplay();
        }, 1000);
    }

    pauseTimer() {
        this.isTimerRunning = false;
        document.getElementById('timerToggle').innerHTML = '<i class="fa-solid fa-play"></i>';
        clearInterval(this.timerInterval);
    }

    resetTimer() {
        this.pauseTimer();
        this.timerSeconds = this.timerMaxSeconds;
        this.updateTimerDisplay();
    }

    updateTimerDisplay() {
        const m = Math.floor(this.timerSeconds / 60);
        const s = this.timerSeconds % 60;
        document.getElementById('timerDisplay').textContent =
            `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }

    setTimerMode(seconds) {
        this.pauseTimer();
        this.timerMaxSeconds = seconds;
        this.timerSeconds = seconds;
        this.updateTimerDisplay();
    }

    // --- Sound ---
    getAudioCtx() {
        if (!this.audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            this.audioCtx = new AudioContextClass();
        }
        return this.audioCtx;
    }

    playNote(freq, startTime, duration, vol = 0.3) {
        const ctx = this.getAudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, startTime);
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(vol, startTime + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
        osc.start(startTime);
        osc.stop(startTime + duration + 0.1);
    }

    playAlert() {
        try {
            const ctx = this.getAudioCtx();
            const now = ctx.currentTime;
            this.playNote(392.00, now, 0.8, 0.3);        // G4
            this.playNote(493.88, now + 0.15, 0.8, 0.3); // B4
            this.playNote(587.33, now + 0.3, 0.8, 0.3);  // D5
            this.playNote(783.99, now + 0.45, 1.2, 0.2); // G5
        } catch (e) { }
    }

    playDing() {
        try {
            const ctx = this.getAudioCtx();
            const now = ctx.currentTime;
            this.playNote(523.25, now, 0.5, 0.1); // C5
        } catch (e) { }
    }

    startBroadcastSoundLoop() {
        if (!this.isSoundEnabled) return;
        this.playAlert();
        this.broadcastInterval = setInterval(() => this.playAlert(), 3500);
    }

    stopBroadcastSoundLoop() {
        if (this.broadcastInterval) {
            clearInterval(this.broadcastInterval);
            this.broadcastInterval = null;
        }
    }
}

// Global modal helpers
function closeBroadcastModal() {
    const modal = document.getElementById('broadcastModal');
    modal.classList.add('opacity-0');
    setTimeout(() => modal.classList.add('hidden'), 300);
}

function closeStudentModal() {
    const modal = document.getElementById('studentModal');
    modal.classList.add('opacity-0');
    setTimeout(() => modal.classList.add('hidden'), 300);
}
