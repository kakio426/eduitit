document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-tts-page]");
    const rowsScript = document.getElementById("tts-rows-data");

    if (!root || !rowsScript) {
        return;
    }

    let rows = [];
    try {
        rows = JSON.parse(rowsScript.textContent || "[]");
    } catch (error) {
        console.error("Failed to parse TTS rows", error);
        return;
    }

    const rowMap = new Map(rows.map((row) => [String(row.id), row]));
    const rowElements = Array.from(root.querySelectorAll("[data-tts-row]"));
    const preview = root.querySelector("[data-tts-preview]");
    const voiceSelect = root.querySelector("[data-tts-voice]");
    const rateInput = root.querySelector("[data-tts-rate]");
    const pitchInput = root.querySelector("[data-tts-pitch]");
    const status = root.querySelector("[data-tts-status]");
    const selectedSummary = root.querySelector("[data-tts-selected-summary]");
    const selectedBody = root.querySelector("[data-tts-selected-body]");
    const nextSummary = root.querySelector("[data-tts-next-summary]");
    const nextCountdown = root.querySelector("[data-tts-next-countdown]");
    const clock = root.querySelector("#tts-clock");
    const synth = window.speechSynthesis || null;

    const timeFormatter = new Intl.DateTimeFormat("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });

    let selectedRowId = "";
    let queueActive = false;
    let voiceOptions = [];
    let selectedVoiceUri = "";
    let speechSessionId = 0;

    function getRow(rowId) {
        return rowMap.get(String(rowId));
    }

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

    function setActiveRow(rowId) {
        rowElements.forEach((element) => {
            element.dataset.active = String(element.dataset.rowId === String(rowId));
        });
    }

    function updateSelectionSummary(row) {
        if (!row) {
            return;
        }

        if (selectedSummary) {
            selectedSummary.textContent = row.subject || "문구";
        }
        if (selectedBody) {
            selectedBody.textContent = row.announcement_text || "";
        }
    }

    function selectRow(rowId, options = {}) {
        const row = getRow(rowId);
        if (!row) {
            return;
        }

        selectedRowId = String(row.id);
        if (preview) {
            preview.value = row.announcement_text || "";
        }
        setActiveRow(row.id);
        updateSelectionSummary(row);
        if (options.status !== false) {
            setStatus(`${row.period_label} 문구를 불러왔습니다.`, "success");
        }
        if (options.focusPreview && preview) {
            preview.focus();
        }
    }

    function updateClock() {
        if (clock) {
            clock.textContent = timeFormatter.format(new Date());
        }
    }

    function updateNextSummary() {
        const nextRow = rows.find((row) => row.is_next) || rows[0];
        if (!nextRow) {
            return;
        }

        if (nextSummary) {
            nextSummary.textContent = `${nextRow.subject || "준비 중"} · ${nextRow.announce_time_label || ""}`;
        }
        if (nextCountdown) {
            nextCountdown.textContent = nextRow.countdown_label || "";
        }
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
            return [...koreanVoices, ...available.filter((voice) => !String(voice.lang || "").toLowerCase().startsWith("ko"))];
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

    function startSpeechSession(quiet) {
        speechSessionId += 1;
        queueActive = false;
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
            setStatus("읽을 문구를 먼저 선택해 주세요.", "error");
            return;
        }
        if (!synth) {
            setStatus("이 브라우저는 음성 합성을 지원하지 않습니다.", "error");
            return;
        }

        const sessionId = startSpeechSession(true);
        const utterance = buildUtterance(content);
        utterance.onstart = () => {
            setStatus(label ? `${label} 읽는 중` : "읽는 중", "warning");
        };
        utterance.onend = () => {
            if (speechSessionId === sessionId && !queueActive) {
                setStatus("읽기 완료", "success");
            }
        };
        utterance.onerror = () => {
            if (speechSessionId !== sessionId) {
                return;
            }
            queueActive = false;
            setStatus("읽는 중 문제가 생겼습니다.", "error");
        };
        synth.speak(utterance);
    }

    function readSelected() {
        const row = getRow(selectedRowId) || rows[0];
        if (!row) {
            setStatus("읽을 문구가 없습니다.", "error");
            return;
        }

        const previewText = preview ? String(preview.value || "").trim() : "";
        speakText(previewText || row.announcement_text || "", row.period_label);
    }

    function copyText(text) {
        const content = String(text || "").trim();
        if (!content) {
            setStatus("복사할 문구를 먼저 선택해 주세요.", "error");
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

    function readAll() {
        if (!rows.length) {
            setStatus("읽을 문구가 없습니다.", "error");
            return;
        }
        if (!synth) {
            setStatus("이 브라우저는 음성 합성을 지원하지 않습니다.", "error");
            return;
        }

        const sessionId = startSpeechSession(true);
        queueActive = true;
        let index = 0;

        const speakNext = () => {
            if (!queueActive || speechSessionId !== sessionId) {
                return;
            }
            if (index >= rows.length) {
                if (speechSessionId === sessionId) {
                    queueActive = false;
                    setStatus("전체 읽기 완료", "success");
                }
                return;
            }

            const row = rows[index];
            const utterance = buildUtterance(row.announcement_text || "");
            utterance.onstart = () => {
                if (speechSessionId !== sessionId) {
                    return;
                }
                setStatus(`${row.period_label} 읽는 중`, "warning");
            };
            utterance.onend = () => {
                if (speechSessionId !== sessionId) {
                    return;
                }
                index += 1;
                if (queueActive) {
                    window.setTimeout(speakNext, 220);
                }
            };
            utterance.onerror = () => {
                if (speechSessionId !== sessionId) {
                    return;
                }
                queueActive = false;
                setStatus("전체 읽기 중 오류가 발생했습니다.", "error");
            };
            synth.speak(utterance);
        };

        speakNext();
    }

    function handleAction(action, rowId) {
        const row = rowId ? getRow(rowId) : null;

        if (action === "select-row" && row) {
            selectRow(row.id);
            return;
        }
        if (action === "read-row" && row) {
            selectRow(row.id, { status: false, focusPreview: false });
            speakText(row.announcement_text, row.period_label);
            return;
        }
        if (action === "copy-row" && row) {
            selectRow(row.id, { status: false, focusPreview: false });
            copyText(row.announcement_text);
            return;
        }
        if (action === "read-selected") {
            readSelected();
            return;
        }
        if (action === "copy-selected") {
            const row = getRow(selectedRowId) || rows[0];
            const previewText = preview ? String(preview.value || "").trim() : "";
            copyText(previewText || (row && row.announcement_text) || "");
            return;
        }
        if (action === "read-all") {
            readAll();
            return;
        }
        if (action === "stop") {
            startSpeechSession(false);
        }
    }

    function bootstrap() {
        if (!rows.length) {
            setStatus("오늘 읽을 문구가 없습니다.", "warning");
            return;
        }

        const initialRow = rows.find((row) => row.is_next) || rows[0];
        selectedRowId = String(initialRow.id);

        if (preview) {
            preview.value = initialRow.announcement_text || "";
            preview.addEventListener("input", () => {
                const activeRow = getRow(selectedRowId);
                if (activeRow && selectedBody) {
                    selectedBody.textContent = preview.value || "";
                }
            });
        }

        if (voiceSelect) {
            voiceSelect.addEventListener("change", () => {
                selectedVoiceUri = voiceSelect.value;
            });
        }

        if (rateInput) {
            rateInput.addEventListener("input", () => {
                if (!queueActive) {
                    setStatus("속도를 조정했습니다.", "success");
                }
            });
        }

        if (pitchInput) {
            pitchInput.addEventListener("input", () => {
                if (!queueActive) {
                    setStatus("목소리 높이를 조정했습니다.", "success");
                }
            });
        }

        root.addEventListener("click", (event) => {
            const trigger = event.target.closest("[data-tts-action]");
            if (!trigger) {
                return;
            }

            event.preventDefault();
            handleAction(trigger.dataset.ttsAction, trigger.dataset.rowId);
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

        setActiveRow(selectedRowId);
        updateSelectionSummary(initialRow);
        updateNextSummary();
        updateClock();
        window.setInterval(updateClock, 30000);

        setStatus("읽기 준비 완료", "success");
    }

    bootstrap();
});
