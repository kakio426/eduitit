(function () {
  const editorRoot = document.getElementById("timetable-editor-root");
  if (!editorRoot) {
    return;
  }

  const readJsonScript = (id, fallback) => {
    const node = document.getElementById(id);
    if (!node) {
      return fallback;
    }
    try {
      return JSON.parse(node.textContent || "");
    } catch (_error) {
      return fallback;
    }
  };

  const bootstrap = readJsonScript("timetable-editor-bootstrap", {});
  const state = {
    sheetData: readJsonScript("timetable-sheet-data", []),
    validation: readJsonScript("timetable-validation-data", { conflicts: [], warnings: [], cell_messages: {}, summary: {} }),
    teacherStats: readJsonScript("timetable-teacher-stats-data", []),
    effectiveEvents: readJsonScript("timetable-effective-events-data", []),
    selectedSheetId: null,
    selection: null,
    autosaveTimer: null,
    workbookApi: null,
    saveInFlight: false,
    editingEventId: null,
    eventSlotMap: {},
  };

  const classroomMap = {};
  (bootstrap.classrooms || []).forEach((item) => {
    classroomMap[String(item.id)] = item.label;
  });
  const dayIndexMap = {};
  (bootstrap.days || []).forEach((item, index) => {
    dayIndexMap[item] = index + 1;
  });

  const statusNode = document.getElementById("timetable-save-status");
  const conflictList = document.getElementById("conflict-list");
  const teacherStatsList = document.getElementById("teacher-stats-list");
  const summaryConflicts = document.getElementById("summary-conflicts");
  const summaryWarnings = document.getElementById("summary-warnings");
  const summaryIncomplete = document.getElementById("summary-incomplete");
  const shareLinksList = document.getElementById("share-links-list");
  const snapshotList = document.getElementById("snapshot-list");
  const sharedEventsList = document.getElementById("shared-events-list");
  const sharedEventsCount = document.getElementById("shared-events-count");
  const sharedEventsStatus = document.getElementById("shared-events-status");
  const publishStageMessage = document.getElementById("publish-stage-message");
  const publishReadinessBadge = document.getElementById("publish-readiness-badge");
  const publishBlockerList = document.getElementById("publish-blocker-list");
  const progressReviewComplete = document.getElementById("progress-review-complete");
  const progressReviewRequired = document.getElementById("progress-review-required");
  const recentActivityList = document.getElementById("recent-activity-list");
  const classInputStatusList = document.getElementById("class-input-status-list");
  const classInputSearch = document.getElementById("class-input-search");
  const sharedEventScope = document.getElementById("shared-event-scope");
  const sharedEventTitle = document.getElementById("shared-event-title");
  const sharedEventDay = document.getElementById("shared-event-day");
  const sharedEventStart = document.getElementById("shared-event-start");
  const sharedEventEnd = document.getElementById("shared-event-end");
  const sharedEventNote = document.getElementById("shared-event-note");
  const saveSharedEventButton = document.getElementById("save-shared-event-button");
  const cancelSharedEventButton = document.getElementById("cancel-shared-event-button");
  const selectionStateBadge = document.getElementById("selection-state-badge");
  const selectionSheetLabel = document.getElementById("selection-sheet-label");
  const selectionSlotLabel = document.getElementById("selection-slot-label");
  const selectionRangeLabel = document.getElementById("selection-range-label");
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const buildEventSummary = (events) =>
    (events || []).map((event) => `${event.scope_label} 행사 '${event.title}'`).join(", ");

  const refreshEventSlotMap = () => {
    const slotMap = {};
    (state.effectiveEvents || []).forEach((event) => {
      (event.slot_keys || []).forEach((slotKey) => {
        slotMap[slotKey] = slotMap[slotKey] || [];
        slotMap[slotKey].push(event);
      });
    });
    state.eventSlotMap = slotMap;
  };

  const buildEventDetailUrl = (eventId) =>
    String(bootstrap.event_detail_url_template || "").replace("__EVENT_ID__", String(eventId));

  const setEventStatus = (text, tone) => {
    if (!sharedEventsStatus) {
      return;
    }
    sharedEventsStatus.textContent = text;
    sharedEventsStatus.className = "mt-3 rounded-2xl px-4 py-3 text-sm font-semibold ";
    if (tone === "error") {
      sharedEventsStatus.className += "bg-rose-50 text-rose-700";
    } else if (tone === "success") {
      sharedEventsStatus.className += "bg-emerald-50 text-emerald-700";
    } else {
      sharedEventsStatus.className += "bg-slate-50 text-slate-600";
    }
  };

  const resetEventForm = () => {
    state.editingEventId = null;
    if (sharedEventScope) {
      sharedEventScope.value = "school";
    }
    if (sharedEventTitle) {
      sharedEventTitle.value = "";
    }
    if (sharedEventDay) {
      sharedEventDay.selectedIndex = 0;
    }
    if (sharedEventStart) {
      sharedEventStart.selectedIndex = 0;
    }
    if (sharedEventEnd) {
      sharedEventEnd.selectedIndex = 0;
    }
    if (sharedEventNote) {
      sharedEventNote.value = "";
    }
    if (saveSharedEventButton) {
      saveSharedEventButton.textContent = "행사 저장";
    }
    cancelSharedEventButton?.classList.add("hidden");
    setEventStatus("행사를 저장하면 해당 시간대가 모든 반에 함께 표시됩니다.", "idle");
  };

  const fillEventForm = (event) => {
    state.editingEventId = event.id;
    if (sharedEventScope) {
      sharedEventScope.value = event.scope_type || "school";
    }
    if (sharedEventTitle) {
      sharedEventTitle.value = event.title || "";
    }
    if (sharedEventDay) {
      sharedEventDay.value = event.day_key || bootstrap.days?.[0] || "";
    }
    if (sharedEventStart) {
      sharedEventStart.value = String(event.period_start || 1);
    }
    if (sharedEventEnd) {
      sharedEventEnd.value = String(event.period_end || event.period_start || 1);
    }
    if (sharedEventNote) {
      sharedEventNote.value = event.note || "";
    }
    if (saveSharedEventButton) {
      saveSharedEventButton.textContent = "행사 수정 저장";
    }
    cancelSharedEventButton?.classList.remove("hidden");
    setEventStatus("수정할 행사 내용을 바꾼 뒤 저장하세요.", "idle");
  };

  const renderSharedEvents = () => {
    if (!sharedEventsList) {
      return;
    }
    const events = state.effectiveEvents || [];
    if (sharedEventsCount) {
      sharedEventsCount.textContent = `${events.length}개`;
    }
    if (!events.length) {
      sharedEventsList.innerHTML = '<div class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">아직 적용된 공통 행사가 없습니다.</div>';
      return;
    }
    sharedEventsList.innerHTML = events
      .map(
        (event) => `
          <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="text-sm font-bold text-slate-900">${escapeHtml(event.title)}</p>
                <p class="mt-1 text-xs font-semibold text-slate-500">${escapeHtml(event.scope_label)} · ${escapeHtml(event.slot_label)}</p>
                ${
                  event.note
                    ? `<p class="mt-2 text-xs leading-5 text-slate-600">${escapeHtml(event.note)}</p>`
                    : ""
                }
              </div>
              <div class="flex flex-wrap gap-2">
                <button type="button" class="shared-event-edit inline-flex items-center justify-center rounded-xl bg-white px-3 py-2 text-xs font-bold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100" data-event-id="${event.id}">
                  수정
                </button>
                <button type="button" class="shared-event-delete inline-flex items-center justify-center rounded-xl bg-rose-50 px-3 py-2 text-xs font-bold text-rose-700 ring-1 ring-rose-200 hover:bg-rose-100" data-event-id="${event.id}">
                  삭제
                </button>
              </div>
            </div>
          </div>
        `
      )
      .join("");
  };

  const parseDisplayText = (value) => {
    const text = String(value || "").trim();
    if (!text) {
      return { subjectName: "", teacherName: "", roomName: "", issues: [] };
    }
    const match = text.match(/^\s*([^(@]+?)(?:\(([^)]+)\))?(?:\s*@\s*(.+))?\s*$/);
    if (!match) {
      return {
        subjectName: text,
        teacherName: "",
        roomName: "",
        issues: ["형식이 올바르지 않습니다."],
      };
    }
    return {
      subjectName: (match[1] || "").trim(),
      teacherName: (match[2] || "").trim(),
      roomName: (match[3] || "").trim(),
      issues: [],
    };
  };

  const extractCellText = (cell) => {
    if (!cell) {
      return "";
    }
    if (typeof cell === "object") {
      return String(cell.m || cell.v || "").trim();
    }
    return String(cell || "").trim();
  };

  const resolveSelectionRange = () => {
    if (!state.selection || !state.selectedSheetId) {
      return null;
    }
    const row = state.selection.row || [];
    const column = state.selection.column || [];
    if (row.length < 2 || column.length < 2) {
      return null;
    }
    return {
      sheetId: state.selectedSheetId,
      startRow: Math.max(1, Math.min(row[0], row[1])),
      endRow: Math.max(1, Math.max(row[0], row[1])),
      startColumn: Math.max(1, Math.min(column[0], column[1])),
      endColumn: Math.max(1, Math.max(column[0], column[1])),
    };
  };

  const buildComposerText = () => {
    const freeText = document.getElementById("composer-free-text").value.trim();
    if (freeText) {
      return freeText;
    }
    const subject = document.getElementById("composer-subject").value.trim();
    const teacher = document.getElementById("composer-teacher").value.trim();
    const room = document.getElementById("composer-room").value.trim();
    let text = subject;
    if (teacher) {
      text = text ? `${text}(${teacher})` : `(${teacher})`;
    }
    if (room) {
      text = text ? `${text} @ ${room}` : `@ ${room}`;
    }
    return text.trim();
  };

  const setSaveStatus = (text, tone) => {
    statusNode.textContent = text;
    statusNode.className = "rounded-full px-4 py-2 text-sm font-bold ";
    if (tone === "error") {
      statusNode.className += "bg-rose-100 text-rose-700";
    } else if (tone === "success") {
      statusNode.className += "bg-emerald-100 text-emerald-700";
    } else {
      statusNode.className += "bg-slate-100 text-slate-600";
    }
  };

  const renderTeacherStats = (rows) => {
    teacherStatsList.innerHTML = "";
    (rows || []).forEach((row) => {
      const wrapper = document.createElement("div");
      wrapper.className = "rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3";
      const percent = row.target_hours ? Math.min(100, Math.round((row.assigned_hours / row.target_hours) * 100)) : 0;
      wrapper.innerHTML = `
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="text-sm font-bold text-slate-900">${row.teacher_name}</p>
            <p class="mt-1 text-xs text-slate-500">${row.assigned_hours} / ${row.target_hours || 0}시간</p>
          </div>
          <span class="rounded-full px-3 py-1 text-xs font-bold ${row.is_over ? "bg-rose-100 text-rose-700" : "bg-sky-100 text-sky-700"}">
            ${row.is_over ? "초과" : "진행"}
          </span>
        </div>
        <div class="teacher-stat-bar mt-3"><span style="width: ${percent}%"></span></div>
      `;
      teacherStatsList.appendChild(wrapper);
    });
  };

  const renderValidation = (validation) => {
    state.validation = validation || { conflicts: [], warnings: [], cell_messages: {}, summary: {} };
    const conflicts = state.validation.conflicts || [];
    const warnings = state.validation.warnings || [];
    const summary = state.validation.summary || {};
    summaryConflicts.textContent = summary.conflict_count || conflicts.length || 0;
    summaryWarnings.textContent = summary.warning_count || warnings.length || 0;
    summaryIncomplete.textContent = summary.incomplete_count || 0;
    conflictList.innerHTML = "";

    if (!conflicts.length && !warnings.length) {
      const empty = document.createElement("li");
      empty.className = "rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700";
      empty.textContent = "현재 확인된 큰 겹침은 없습니다.";
      conflictList.appendChild(empty);
      return;
    }

    [...conflicts, ...warnings].slice(0, 3).forEach((message, index) => {
      const item = document.createElement("li");
      const isConflict = index < conflicts.length;
      item.className = isConflict
        ? "rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
        : "rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800";
      item.textContent = message;
      conflictList.appendChild(item);
    });
  };

  const renderPublishReadiness = (publishReadiness, progressSummary) => {
    if (publishReadinessBadge) {
      publishReadinessBadge.textContent = publishReadiness?.workflow_label || "초안";
      publishReadinessBadge.className = `rounded-full px-3 py-1 text-xs font-bold ${
        publishReadiness?.can_publish ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
      }`;
    }
    if (publishStageMessage) {
      publishStageMessage.textContent = publishReadiness?.stage_message || "현재 상태를 확인하는 중입니다.";
      publishStageMessage.className = `mt-4 rounded-2xl border px-4 py-3 text-sm font-semibold ${
        publishReadiness?.can_publish
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-amber-200 bg-amber-50 text-amber-800"
      }`;
    }
    if (progressReviewComplete && progressSummary) {
      progressReviewComplete.textContent = `${progressSummary.review_complete_count || 0} / ${progressSummary.total_classes || 0}`;
    }
    if (progressReviewRequired && progressSummary) {
      progressReviewRequired.textContent = progressSummary.review_required_count || 0;
    }
    if (publishBlockerList) {
      const blockers = publishReadiness?.blockers || [];
      if (!blockers.length) {
        publishBlockerList.innerHTML = '<li class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">현재 큰 차단 사유 없이 확정 가능한 상태입니다.</li>';
      } else {
        publishBlockerList.innerHTML = blockers
          .slice(0, 4)
          .map(
            (message) =>
              `<li class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">${escapeHtml(message)}</li>`
          )
          .join("");
      }
    }
  };

  const renderRecentActivity = (items) => {
    if (!recentActivityList) {
      return;
    }
    if (!(items || []).length) {
      recentActivityList.innerHTML = '<div class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">아직 기록된 주요 활동이 없습니다.</div>';
      return;
    }
    recentActivityList.innerHTML = (items || [])
      .map((item) => {
        const toneClass =
          item.tone === "emerald"
            ? "border-emerald-200 bg-emerald-50"
            : item.tone === "amber"
              ? "border-amber-200 bg-amber-50"
              : item.tone === "sky"
                ? "border-sky-200 bg-sky-50"
                : item.tone === "rose"
                  ? "border-rose-200 bg-rose-50"
                  : "border-slate-200 bg-slate-50";
        return `<article class="rounded-2xl border px-4 py-3 ${toneClass}">
          <p class="text-sm font-bold text-slate-900">${escapeHtml(item.message || "")}</p>
          <p class="mt-1 text-xs font-semibold text-slate-500">${escapeHtml(item.actor_label || "")} · ${escapeHtml(item.created_at_label || "")}</p>
        </article>`;
      })
      .join("");
  };

  const updateSelectionState = () => {
    if (!selectionStateBadge || !selectionSheetLabel || !selectionSlotLabel || !selectionRangeLabel) {
      return;
    }
    const range = resolveSelectionRange();
    if (!range) {
      selectionStateBadge.textContent = "선택 전";
      selectionStateBadge.className = "rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600";
      selectionSheetLabel.textContent = "먼저 칸을 선택해 주세요";
      selectionSlotLabel.textContent = "선택된 시간 없음";
      selectionRangeLabel.textContent = "한 칸 또는 여러 칸을 선택할 수 있습니다.";
      return;
    }

    const sheet = state.sheetData.find((item) => String(item.id) === String(range.sheetId)) || state.sheetData[0] || {};
    const firstDay = (bootstrap.days || [])[range.startColumn - 1] || "";
    const lastDay = (bootstrap.days || [])[range.endColumn - 1] || firstDay;
    const firstPeriod = (bootstrap.period_labels || [])[range.startRow - 1] || `${range.startRow}교시`;
    const lastPeriod = (bootstrap.period_labels || [])[range.endRow - 1] || `${range.endRow}교시`;
    const cellCount = (range.endRow - range.startRow + 1) * (range.endColumn - range.startColumn + 1);

    selectionStateBadge.textContent = cellCount > 1 ? `${cellCount}칸 선택` : "한 칸 선택";
    selectionStateBadge.className = "rounded-full bg-sky-100 px-3 py-1 text-xs font-bold text-sky-700";
    selectionSheetLabel.textContent = sheet.name || "선택된 반";
    selectionSlotLabel.textContent =
      range.startRow === range.endRow && range.startColumn === range.endColumn
        ? `${firstDay} ${firstPeriod}`
        : `${firstDay} ${firstPeriod} ~ ${lastDay} ${lastPeriod}`;
    selectionRangeLabel.textContent =
      cellCount > 1 ? `${cellCount}칸에 같은 배정을 한 번에 넣습니다.` : "이 칸에만 배정이 들어갑니다.";
  };

  const syncValidationUI = (payload) => {
    if (payload?.effective_events) {
      state.effectiveEvents = payload.effective_events;
      refreshEventSlotMap();
      renderSharedEvents();
    }
    if (payload?.validation) {
      renderValidation(payload.validation);
      applyConflictHighlights();
    }
    if (payload?.teacher_stats) {
      renderTeacherStats(payload.teacher_stats);
    }
    if (payload?.publish_readiness || payload?.progress_summary) {
      renderPublishReadiness(payload.publish_readiness || {}, payload.progress_summary || {});
    }
    if (payload?.recent_activity) {
      renderRecentActivity(payload.recent_activity);
    }
  };

  const resolveSheetForCellKey = (key) => {
    const [classToken, dayKey, periodNoRaw] = String(key || "").split(":");
    const sheetName = classroomMap[classToken] || classToken;
    const periodNo = Number(periodNoRaw);
    const columnIndex = dayIndexMap[dayKey];
    return {
      sheet: state.sheetData.find((item) => item.name === sheetName),
      rowIndex: Number.isFinite(periodNo) ? periodNo : 0,
      columnIndex: columnIndex || 0,
    };
  };

  const applyConflictHighlights = () => {
    if (!state.workbookApi || !state.sheetData.length) {
      return;
    }

    state.sheetData.forEach((sheet) => {
      const rowCount = (bootstrap.period_labels || []).length;
      const colCount = (bootstrap.days || []).length;
      for (let row = 1; row <= rowCount; row += 1) {
        for (let col = 1; col <= colCount; col += 1) {
          state.workbookApi.setCellFormat(row, col, "bg", "#ffffff", { id: sheet.id });
        }
      }
    });

    state.sheetData.forEach((sheet) => {
      Object.keys(state.eventSlotMap || {}).forEach((slotKey) => {
        const [dayKey, periodNoRaw] = String(slotKey).split(":");
        const rowIndex = Number(periodNoRaw);
        const columnIndex = dayIndexMap[dayKey];
        if (!rowIndex || !columnIndex) {
          return;
        }
        state.workbookApi.setCellFormat(rowIndex, columnIndex, "bg", "#fef3c7", { id: sheet.id });
      });
    });

    Object.keys(state.validation.cell_messages || {}).forEach((cellKey) => {
      const payload = resolveSheetForCellKey(cellKey);
      if (!payload.sheet || !payload.rowIndex || !payload.columnIndex) {
        return;
      }
      if (!(state.validation.cell_messages[cellKey] || []).length) {
        return;
      }
      state.workbookApi.setCellFormat(payload.rowIndex, payload.columnIndex, "bg", "#fecaca", { id: payload.sheet.id });
    });
  };

  const buildLocalValidation = () => {
    const cellMessages = {};
    const teacherSlots = {};
    state.sheetData.forEach((sheet) => {
      (bootstrap.period_labels || []).forEach((_periodLabel, periodOffset) => {
        const periodNo = periodOffset + 1;
        (bootstrap.days || []).forEach((dayKey, dayOffset) => {
          const text = extractCellText((sheet.data?.[periodNo] || [])[dayOffset + 1]);
          if (!text) {
            return;
          }
          const cellKey = `${sheet.name}:${dayKey}:${periodNo}`;
          const parsed = parseDisplayText(text);
          if (parsed.issues.length) {
            cellMessages[cellKey] = [...parsed.issues];
          }
          const slotEvents = state.eventSlotMap[`${dayKey}:${periodNo}`] || [];
          if (slotEvents.length) {
            cellMessages[cellKey] = cellMessages[cellKey] || [];
            cellMessages[cellKey].push(`${dayKey} ${periodNo}교시는 ${buildEventSummary(slotEvents)} 시간입니다.`);
          }
          if (parsed.teacherName) {
            const teacherKey = `${parsed.teacherName}:${dayKey}:${periodNo}`;
            teacherSlots[teacherKey] = teacherSlots[teacherKey] || [];
            teacherSlots[teacherKey].push(cellKey);
          }
        });
      });
    });

    Object.keys(teacherSlots).forEach((teacherKey) => {
      if ((teacherSlots[teacherKey] || []).length < 2) {
        return;
      }
      teacherSlots[teacherKey].forEach((cellKey) => {
        cellMessages[cellKey] = cellMessages[cellKey] || [];
        cellMessages[cellKey].push("같은 시간에 같은 교사가 여러 반에 배정되었습니다.");
      });
    });

    return { cell_messages: cellMessages };
  };

  const scheduleAutosave = () => {
    window.clearTimeout(state.autosaveTimer);
    setSaveStatus("저장 대기 중...", "idle");
    state.autosaveTimer = window.setTimeout(async () => {
      if (state.saveInFlight) {
        scheduleAutosave();
        return;
      }
      state.saveInFlight = true;
      setSaveStatus("저장 중...", "idle");
      try {
        const response = await fetch(bootstrap.autosave_url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({ sheet_data: state.sheetData }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.message || "자동 저장에 실패했습니다.");
        }
        renderValidation(payload.validation);
        renderTeacherStats(payload.teacher_stats);
        applyConflictHighlights();
        setSaveStatus("자동 저장됨", "success");
      } catch (error) {
        setSaveStatus(error.message, "error");
      } finally {
        state.saveInFlight = false;
      }
    }, 450);
  };

  const saveSnapshot = async () => {
    const name = window.prompt("스냅샷 이름을 입력해 주세요.", "");
    if (name === null) {
      return;
    }
    setSaveStatus("스냅샷 저장 중...", "idle");
    const response = await fetch(bootstrap.snapshots_url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({ name }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || "스냅샷 저장에 실패했습니다.");
    }
    setSaveStatus(`스냅샷 저장: ${payload.snapshot.name}`, "success");
    window.location.reload();
  };

  const renderShareLinks = (links, portalUrl) => {
    const grouped = { classLinks: [], teacherLinks: [] };
    (links || []).forEach((link) => {
      if (link.audience_type === "class") {
        grouped.classLinks.push(link);
      } else {
        grouped.teacherLinks.push(link);
      }
    });

    const renderGroup = (title, emptyText, items) => {
      if (!items.length) {
        return `
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p class="text-xs font-black uppercase tracking-[0.2em] text-slate-400">${escapeHtml(title)}</p>
            <div class="mt-3 rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm text-slate-500">${escapeHtml(emptyText)}</div>
          </div>
        `;
      }
      return `
        <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <p class="text-xs font-black uppercase tracking-[0.2em] text-slate-400">${escapeHtml(title)}</p>
          <div class="mt-3 space-y-2">
            ${items
              .map(
                (link) => `
                  <div class="rounded-2xl bg-white px-3 py-3 ring-1 ring-slate-200">
                    <p class="text-sm font-bold text-slate-900">${escapeHtml(link.audience_label)}</p>
                    <p class="share-link-url mt-1 break-all text-xs text-slate-500" data-share-primary-url="true">${escapeHtml(link.url)}</p>
                  </div>
                `
              )
              .join("")}
          </div>
        </div>
      `;
    };

    if ((!links || !links.length) && !portalUrl) {
      shareLinksList.innerHTML = '<div class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">확정 후 읽기 전용 링크가 생성됩니다.</div>';
      return;
    }

    shareLinksList.innerHTML = `
      ${renderGroup("반별 바로보기", "아직 반별 링크가 없습니다.", grouped.classLinks)}
      ${renderGroup("전담·강사 바로보기", "아직 전담·강사 링크가 없습니다.", grouped.teacherLinks)}
      ${
        portalUrl
          ? `<div class="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4">
              <p class="text-xs font-black uppercase tracking-[0.2em] text-sky-600">교사용 모아보기</p>
              <p class="mt-2 text-sm font-bold text-sky-950">교사용 모아보기</p>
              <p class="mt-1 break-all text-xs text-sky-700">${escapeHtml(portalUrl)}</p>
            </div>`
          : ""
      }
    `;
  };

  const publishWorkspace = async () => {
    if (!window.confirm("현재 시간표를 확정하고 읽기 전용 링크를 만들까요?")) {
      return;
    }
    const name = window.prompt("확정본 이름", "");
    setSaveStatus("확정본 생성 중...", "idle");
    const response = await fetch(bootstrap.publish_url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({ name, sheet_data: state.sheetData }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      syncValidationUI(payload);
      throw new Error(payload.message || "확정에 실패했습니다.");
    }
    renderShareLinks(payload.share_links || [], payload.portal_url || "");
    const publishConflicts = payload.publish_result?.conflicts || [];
    const publishWarnings = payload.publish_result?.warnings || [];
    if (publishConflicts.length || publishWarnings.length) {
      setSaveStatus("확정은 완료했고, 일부 예약 반영 안내가 있습니다. 화면을 새로고침합니다.", "success");
    } else {
      setSaveStatus("확정과 링크 생성이 완료되었습니다. 화면을 새로고침합니다.", "success");
    }
    window.setTimeout(() => window.location.reload(), 500);
  };

  const restoreSnapshot = async (button) => {
    const snapshotName = button.dataset.snapshotName || "선택한 스냅샷";
    if (!window.confirm(`'${snapshotName}' 상태로 현재 초안을 되돌릴까요?`)) {
      return;
    }
    setSaveStatus("스냅샷 복원 중...", "idle");
    const response = await fetch(button.dataset.restoreUrl, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
      },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      syncValidationUI(payload);
      throw new Error(payload.message || "스냅샷 복원에 실패했습니다.");
    }
    syncValidationUI(payload);
    setSaveStatus(`스냅샷 복원: ${payload.snapshot.name}`, "success");
    window.setTimeout(() => {
      window.location.href = payload.redirect_url || window.location.href;
    }, 350);
  };

  const applySelectionValue = (value) => {
    const range = resolveSelectionRange();
    if (!range || !state.workbookApi) {
      setSaveStatus("먼저 시트에서 칸을 선택해 주세요.", "error");
      return;
    }
    for (let row = range.startRow; row <= range.endRow; row += 1) {
      for (let column = range.startColumn; column <= range.endColumn; column += 1) {
        state.workbookApi.setCellValue(row, column, value, { id: range.sheetId });
      }
    }
  };

  const mountWorkbook = () => {
    const Workbook = window.react?.Workbook;
    if (!Workbook || !window.React || !window.ReactDOM) {
      setSaveStatus("시간표 편집기를 불러오지 못했습니다.", "error");
      return;
    }

    const ref = window.React.createRef();
    const props = {
      data: state.sheetData,
      showToolbar: true,
      showFormulaBar: false,
      showSheetTabs: true,
      allowEdit: true,
      hooks: {
        afterSelectionChange(sheetId, selection) {
          state.selectedSheetId = sheetId;
          state.selection = selection;
          updateSelectionState();
        },
        beforeAddSheet() {
          return false;
        },
        beforeDeleteSheet() {
          return false;
        },
        beforeUpdateSheetName() {
          return false;
        },
      },
      onChange(data) {
        state.sheetData = data || [];
        const localValidation = buildLocalValidation();
        renderValidation({
          conflicts: state.validation.conflicts || [],
          warnings: state.validation.warnings || [],
          cell_messages: localValidation.cell_messages,
          summary: state.validation.summary || {},
        });
        applyConflictHighlights();
        scheduleAutosave();
      },
      ref,
    };

    const renderApp = window.React.createElement(Workbook, props);
    if (typeof window.ReactDOM.createRoot === "function") {
      const root = window.ReactDOM.createRoot(editorRoot);
      root.render(renderApp);
    } else {
      window.ReactDOM.render(renderApp, editorRoot);
    }

    window.setTimeout(() => {
      state.workbookApi = ref.current;
      state.selectedSheetId = (state.sheetData[0] || {}).id || null;
      refreshEventSlotMap();
      renderSharedEvents();
      renderValidation(state.validation);
      renderTeacherStats(state.teacherStats);
      applyConflictHighlights();
      updateSelectionState();
    }, 150);
  };

  const saveSharedEvent = async () => {
    if (!bootstrap.events_url) {
      throw new Error("행사 저장 경로를 찾지 못했습니다.");
    }
    const isEditing = Boolean(state.editingEventId);
    const payload = {
      scope_type: sharedEventScope?.value || "school",
      title: sharedEventTitle?.value?.trim() || "",
      day_key: sharedEventDay?.value || "",
      period_start: Number(sharedEventStart?.value || 1),
      period_end: Number(sharedEventEnd?.value || 1),
      note: sharedEventNote?.value?.trim() || "",
    };
    const url = state.editingEventId ? buildEventDetailUrl(state.editingEventId) : bootstrap.events_url;
    const method = state.editingEventId ? "PATCH" : "POST";
    setEventStatus(isEditing ? "행사 수정 중..." : "행사 저장 중...", "idle");
    const response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.message || "행사 저장에 실패했습니다.");
    }
    syncValidationUI(result);
    resetEventForm();
    setEventStatus(isEditing ? "행사를 수정했습니다." : "행사를 저장했습니다.", "success");
    setSaveStatus("공통 행사 반영 완료", "success");
  };

  const deleteSharedEvent = async (eventId) => {
    if (!window.confirm("이 공통 행사를 삭제할까요?")) {
      return;
    }
    setEventStatus("행사 삭제 중...", "idle");
    const response = await fetch(buildEventDetailUrl(eventId), {
      method: "DELETE",
      headers: {
        "X-CSRFToken": csrfToken,
      },
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.message || "행사 삭제에 실패했습니다.");
    }
    if (state.editingEventId === eventId) {
      resetEventForm();
    }
    syncValidationUI(result);
    setEventStatus("행사를 삭제했습니다.", "success");
    setSaveStatus("공통 행사 삭제 완료", "success");
  };

  const postJson = async (url, payload) => {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify(payload || {}),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.message || "작업을 처리하지 못했습니다.");
    }
    return result;
  };

  document.getElementById("apply-selection-button")?.addEventListener("click", () => {
    const text = buildComposerText();
    if (!text) {
      setSaveStatus("과목 또는 교사 정보를 먼저 입력해 주세요.", "error");
      return;
    }
    applySelectionValue(text);
  });

  document.getElementById("clear-selection-button")?.addEventListener("click", () => {
    applySelectionValue("");
  });

  document.getElementById("save-snapshot-button")?.addEventListener("click", () => {
    saveSnapshot().catch((error) => setSaveStatus(error.message, "error"));
  });

  document.getElementById("publish-workspace-button")?.addEventListener("click", () => {
    publishWorkspace().catch((error) => setSaveStatus(error.message, "error"));
  });

  snapshotList?.addEventListener("click", (event) => {
    const button = event.target.closest(".snapshot-restore-button");
    if (!button) {
      return;
    }
    restoreSnapshot(button).catch((error) => setSaveStatus(error.message, "error"));
  });

  document.getElementById("copy-first-share-link")?.addEventListener("click", async () => {
    const firstLink = shareLinksList.querySelector("[data-share-primary-url='true']");
    if (!firstLink) {
      setSaveStatus("아직 복사할 바로보기 링크가 없습니다.", "error");
      return;
    }
    try {
      await navigator.clipboard.writeText(firstLink.textContent.trim());
      setSaveStatus("첫 링크를 복사했습니다.", "success");
    } catch (_error) {
      setSaveStatus("클립보드 복사에 실패했습니다.", "error");
    }
  });

  saveSharedEventButton?.addEventListener("click", () => {
    saveSharedEvent()
      .catch((error) => setEventStatus(error.message, "error"));
  });

  cancelSharedEventButton?.addEventListener("click", () => {
    resetEventForm();
  });

  sharedEventsList?.addEventListener("click", (event) => {
    const editButton = event.target.closest(".shared-event-edit");
    if (editButton) {
      const selectedEvent = (state.effectiveEvents || []).find((item) => String(item.id) === String(editButton.dataset.eventId));
      if (selectedEvent) {
        fillEventForm(selectedEvent);
      }
      return;
    }
    const deleteButton = event.target.closest(".shared-event-delete");
    if (!deleteButton) {
      return;
    }
    deleteSharedEvent(Number(deleteButton.dataset.eventId)).catch((error) => setEventStatus(error.message, "error"));
  });

  classInputStatusList?.addEventListener("click", async (event) => {
    const copyButton = event.target.closest(".class-input-copy");
    if (copyButton) {
      try {
        await navigator.clipboard.writeText(copyButton.dataset.linkUrl || "");
        setSaveStatus("반별 입력 링크를 복사했습니다.", "success");
      } catch (_error) {
        setSaveStatus("클립보드 복사에 실패했습니다.", "error");
      }
      return;
    }

    const issueButton = event.target.closest(".class-link-issue-button");
    if (issueButton) {
      try {
        setSaveStatus("입력 링크를 준비 중...", "idle");
        await postJson(issueButton.dataset.issueUrl, {
          classroom_id: Number(issueButton.dataset.classroomId),
        });
        window.location.reload();
      } catch (error) {
        setSaveStatus(error.message, "error");
      }
      return;
    }

    const revokeButton = event.target.closest(".class-link-revoke-button");
    if (revokeButton) {
      if (revokeButton.disabled) {
        return;
      }
      if (!window.confirm("이 반 입력 링크를 끊을까요?")) {
        return;
      }
      try {
        setSaveStatus("입력 링크를 끊는 중...", "idle");
        await postJson(revokeButton.dataset.revokeUrl, {});
        window.location.reload();
      } catch (error) {
        setSaveStatus(error.message, "error");
      }
      return;
    }

    const reviewButton = event.target.closest(".class-status-review-button");
    if (!reviewButton) {
      return;
    }
    const reviewNote = window.prompt("검토 메모가 있으면 남겨 주세요.", "") ?? "";
    try {
      setSaveStatus("검토 상태를 저장하는 중...", "idle");
      await postJson(reviewButton.dataset.reviewUrl, {
        review_note: reviewNote.trim(),
      });
      window.location.reload();
    } catch (error) {
      setSaveStatus(error.message, "error");
    }
  });

  classInputSearch?.addEventListener("input", () => {
    const keyword = classInputSearch.value.trim().toLowerCase();
    classInputStatusList?.querySelectorAll(".class-input-row").forEach((row) => {
      const text = row.dataset.search || "";
      row.classList.toggle("hidden", Boolean(keyword) && !text.includes(keyword));
    });
  });

  resetEventForm();
  mountWorkbook();
})();
