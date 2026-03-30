document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-tts-page]");
    if (!root) {
        return;
    }

    const templateScript = document.getElementById("tts-template-groups-data");
    const scheduleScript = document.getElementById("tts-schedule-rows-data");
    if (!templateScript || !scheduleScript) {
        return;
    }

    function parseJsonScript(element, fallback) {
        try {
            return JSON.parse(element.textContent || JSON.stringify(fallback));
        } catch (error) {
            console.error("Failed to parse TTS page payload", error);
            return fallback;
        }
    }

    const templateGroups = parseJsonScript(templateScript, []);
    const scheduleRows = parseJsonScript(scheduleScript, []);
    const templateItems = templateGroups.flatMap((group) =>
        (group.items || []).map((item) => ({
            ...item,
            groupTitle: group.title || "빠른 문구",
        })),
    );

    const templateMap = new Map(templateItems.map((item) => [String(item.id), item]));
    const scheduleMap = new Map(scheduleRows.map((row) => [String(row.id), row]));
    const templateCards = Array.from(root.querySelectorAll("[data-tts-template-card]"));
    const scheduleCards = Array.from(root.querySelectorAll("[data-tts-schedule-card]"));
    const preview = root.querySelector("[data-tts-preview]");
    const voiceSelect = root.querySelector("[data-tts-voice]");
    const rateInput = root.querySelector("[data-tts-rate]");
    const pitchInput = root.querySelector("[data-tts-pitch]");
    const status = root.querySelector("[data-tts-status]");
    const selectedSource = root.querySelector("[data-tts-selected-source]");
    const selectedSummary = root.querySelector("[data-tts-selected-summary]");
    const selectedBody = root.querySelector("[data-tts-selected-body]");
    const synth = window.speechSynthesis || null;
    const scheduleLabel = root.dataset.scheduleLabel || "시간표 프리셋";

    let voiceOptions = [];
    let selectedVoiceUri = "";
    let speechSessionId = 0;
    let selectedSourceLabel = selectedSource ? selectedSource.textContent || "빠른 문구" : "빠른 문구";
    let selectedDefaultText = preview ? String(preview.value || "").trim() : "";

    function setStatus(message, tone) {
        if (!status) {
            return;
        }

        status.textContent = message;
        status.classList.remove("text-red-500", "text-emerald-500", "text-amber-500", "text-slate-500");
        if (tone === "error") {
            status.classList.add("text-red-500");
        } else if (tone === "success") {
            status.classList.add("text-emerald-500");
        } else if (tone === "warning") {
            status.classList.add("text-amber-500");
        } else {
            status.classList.add("text-slate-500");
        }
    }

    function setActiveCards(kind, id) {
        templateCards.forEach((element) => {
            element.dataset.active = String(kind === "template" && element.dataset.templateId === String(id));
        });
        scheduleCards.forEach((element) => {
            element.dataset.active = String(kind === "schedule" && element.dataset.rowId === String(id));
        });
    }

    function updateSelectedPanel({ sourceLabel, title, text, defaultText }) {
        selectedSourceLabel = sourceLabel || "빠른 문구";
        selectedDefaultText = String(defaultText || text || "").trim();

        if (selectedSource) {
            selectedSource.textContent = selectedSourceLabel;
        }
        if (selectedSummary) {
            selectedSummary.textContent = title || "방송 문구";
        }
        if (selectedBody) {
            selectedBody.textContent = text || "";
        }
    }

    function fillComposer({ text, sourceLabel, title, defaultText, activeKind, activeId, statusMessage }) {
        if (preview) {
            preview.value = text || "";
        }

        updateSelectedPanel({
            sourceLabel,
            title,
            text: text || "",
            defaultText,
        });
        setActiveCards(activeKind, activeId);

        if (statusMessage) {
            setStatus(statusMessage, "success");
        }
    }

    function selectTemplate(templateId, options = {}) {
        const template = templateMap.get(String(templateId));
        if (!template) {
            return null;
        }

        fillComposer({
            text: template.message || "",
            sourceLabel: template.groupTitle || "빠른 문구",
            title: template.title || "방송 문구",
            defaultText: template.message || "",
            activeKind: "template",
            activeId: template.id,
            statusMessage: options.status === false ? "" : `${template.title} 문구를 가져왔습니다.`,
        });
        return template;
    }

    function selectSchedule(rowId, options = {}) {
        const row = scheduleMap.get(String(rowId));
        if (!row) {
            return null;
        }

        fillComposer({
            text: row.announcement_text || "",
            sourceLabel: scheduleLabel,
            title: `${row.period_label || "교시"} · ${row.subject || "수업"}`,
            defaultText: row.announcement_text || "",
            activeKind: "schedule",
            activeId: row.id,
            statusMessage: options.status === false ? "" : `${row.period_label || "교시"} 안내 문구를 가져왔습니다.`,
        });
        return row;
    }

    function getAvailableVoices() {
        if (!synth) {
            return [];
        }

        const available = synth.getVoices() || [];
        if (!available.length) {
            return [];
        }

        const koreanVoices = available.filter((voice) => String(voice.lang || "").toLowerCase().startsWith("ko"));
        if (koreanVoices.length) {
            return [
                ...koreanVoices,
                ...available.filter((voice) => !String(voice.lang || "").toLowerCase().startsWith("ko")),
            ];
        }
        return available;
    }

    function renderVoiceOptions() {
        if (!voiceSelect) {
            return;
        }

        voiceOptions = getAvailableVoices();
        const previousVoiceUri = selectedVoiceUri || voiceSelect.value || "";
        voiceSelect.innerHTML = "";

        if (!voiceOptions.length) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "기본 목소리";
            voiceSelect.appendChild(option);
            voiceSelect.disabled = true;
            selectedVoiceUri = "";
            return;
        }

        voiceSelect.disabled = false;
        voiceOptions.forEach((voice) => {
            const option = document.createElement("option");
            const uri = voice.voiceURI || voice.name;
            option.value = uri;
            option.textContent = `${voice.name} (${voice.lang || "unknown"})${voice.default ? " · 기본" : ""}`;
            voiceSelect.appendChild(option);
        });

        const preferredVoice =
            voiceOptions.find((voice) => (voice.voiceURI || voice.name) === previousVoiceUri) ||
            voiceOptions.find((voice) => voice.default) ||
            voiceOptions.find((voice) => String(voice.lang || "").toLowerCase().startsWith("ko")) ||
            voiceOptions[0];

        if (preferredVoice) {
            selectedVoiceUri = preferredVoice.voiceURI || preferredVoice.name;
            voiceSelect.value = selectedVoiceUri;
        }
    }

    function getSelectedVoice() {
        if (!voiceOptions.length) {
            return null;
        }

        const uri = selectedVoiceUri || (voiceSelect ? voiceSelect.value : "");
        return voiceOptions.find((voice) => (voice.voiceURI || voice.name) === uri) || null;
    }

    function buildUtterance(text) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "ko-KR";
        utterance.rate = rateInput ? Number(rateInput.value || 0.95) : 0.95;
        utterance.pitch = pitchInput ? Number(pitchInput.value || 1) : 1;
        utterance.volume = 1;

        const voice = getSelectedVoice();
        if (voice) {
            utterance.voice = voice;
        }

        return utterance;
    }

    function stopSpeech(quiet) {
        speechSessionId += 1;
        if (synth) {
            synth.cancel();
        }
        if (!quiet) {
            setStatus("읽기를 멈췄습니다.", "warning");
        }
        return speechSessionId;
    }

    function speakText(text, label) {
        const content = String(text || "").trim();
        if (!content) {
            setStatus("읽을 문구를 먼저 준비해 주세요.", "error");
            return;
        }
        if (!synth) {
            setStatus("이 브라우저는 음성 합성을 지원하지 않습니다.", "error");
            return;
        }

        const sessionId = stopSpeech(true);
        const utterance = buildUtterance(content);
        utterance.onstart = () => {
            setStatus(label ? `${label} 읽는 중` : "읽는 중", "warning");
        };
        utterance.onend = () => {
            if (speechSessionId === sessionId) {
                setStatus("읽기 완료", "success");
            }
        };
        utterance.onerror = () => {
            if (speechSessionId !== sessionId) {
                return;
            }
            setStatus("읽는 중 문제가 생겼습니다.", "error");
        };
        synth.speak(utterance);
    }

    function copyText(text) {
        const content = String(text || "").trim();
        if (!content) {
            setStatus("복사할 문구를 먼저 준비해 주세요.", "error");
            return;
        }

        const finish = () => setStatus("문구를 복사했습니다.", "success");
        const fail = () => setStatus("복사에 실패했습니다. 브라우저 권한을 확인해 주세요.", "error");

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(content).then(finish).catch(fail);
            return;
        }

        try {
            const helper = document.createElement("textarea");
            helper.value = content;
            helper.setAttribute("readonly", "true");
            helper.style.position = "fixed";
            helper.style.left = "-9999px";
            helper.style.opacity = "0";
            document.body.appendChild(helper);
            helper.focus();
            helper.select();
            const success = document.execCommand("copy");
            document.body.removeChild(helper);
            if (success) {
                finish();
            } else {
                fail();
            }
        } catch (error) {
            fail();
        }
    }

    function handleAction(action, templateId, rowId) {
        if (action === "select-template") {
            selectTemplate(templateId);
            return;
        }
        if (action === "read-template") {
            const template = selectTemplate(templateId, { status: false });
            if (template) {
                speakText(template.message, template.title);
            }
            return;
        }
        if (action === "select-schedule") {
            selectSchedule(rowId);
            return;
        }
        if (action === "read-schedule") {
            const row = selectSchedule(rowId, { status: false });
            if (row) {
                speakText(row.announcement_text, `${row.period_label || "교시"} 안내`);
            }
            return;
        }
        if (action === "read-current") {
            speakText(preview ? preview.value : "", selectedSummary ? selectedSummary.textContent : "방송");
            return;
        }
        if (action === "copy-current") {
            copyText(preview ? preview.value : "");
            return;
        }
        if (action === "stop") {
            stopSpeech(false);
        }
    }

    function bootstrapSelection() {
        if (templateItems.length) {
            selectTemplate(templateItems[0].id, { status: false });
            return;
        }
        if (scheduleRows.length) {
            selectSchedule(scheduleRows[0].id, { status: false });
        }
    }

    if (preview) {
        preview.addEventListener("input", () => {
            const currentText = preview.value || "";
            if (selectedBody) {
                selectedBody.textContent = currentText;
            }
            if (!selectedSource) {
                return;
            }

            const changed = String(currentText).trim() !== selectedDefaultText;
            selectedSource.textContent = changed ? `${selectedSourceLabel} · 직접 수정` : selectedSourceLabel;
        });
    }

    if (voiceSelect) {
        voiceSelect.addEventListener("change", () => {
            selectedVoiceUri = voiceSelect.value;
            setStatus("목소리를 바꿨습니다.", "success");
        });
    }

    if (rateInput) {
        rateInput.addEventListener("input", () => {
            setStatus("읽는 속도를 조정했습니다.", "success");
        });
    }

    if (pitchInput) {
        pitchInput.addEventListener("input", () => {
            setStatus("목소리 높이를 조정했습니다.", "success");
        });
    }

    root.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-tts-action]");
        if (!trigger) {
            return;
        }

        event.preventDefault();
        handleAction(trigger.dataset.ttsAction, trigger.dataset.templateId, trigger.dataset.rowId);
    });

    if (synth) {
        renderVoiceOptions();
        if (typeof synth.addEventListener === "function") {
            synth.addEventListener("voiceschanged", renderVoiceOptions);
        }
        synth.onvoiceschanged = renderVoiceOptions;
    } else if (voiceSelect) {
        voiceSelect.innerHTML = '<option value="">기본 목소리</option>';
        voiceSelect.disabled = true;
    }

    bootstrapSelection();
    setStatus("읽기 준비 완료", "success");
});
