(function () {
  'use strict';

  // ── 활성화 가드 ───────────────────────────────────────────────────────────
  if (!window.__GUIDE_RECORDER_ENABLED) return;

  // ── 상태 ──────────────────────────────────────────────────────────────────
  var state = {
    isRecording: false,
    sessionId: null,
    stepCount: 0,
    pendingCapture: false,
  };

  // ── 설정 ──────────────────────────────────────────────────────────────────
  var CONFIG = {
    apiStartUrl: '/guide-recorder/api/session/start/',
    apiStepUrl: '/guide-recorder/api/session/{id}/step/',
    apiFinishUrl: '/guide-recorder/api/session/{id}/finish/',
    html2canvasCdn: 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js',
  };

  var html2canvasLoaded = false;
  var html2canvasLoading = null; // Promise

  // ── CSRF ──────────────────────────────────────────────────────────────────
  function getCsrfToken() {
    // 1순위: hidden input
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    // 2순위: cookie
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  // ── fetch 헬퍼 ────────────────────────────────────────────────────────────
  function postJson(url, payload) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(payload),
    }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    });
  }

  // ── 인라인 스타일 주입 ────────────────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById('gr-styles')) return;
    var style = document.createElement('style');
    style.id = 'gr-styles';
    style.textContent = [
      '.gr-highlight { outline: 2px solid #3B82F6 !important; outline-offset: 2px !important; cursor: crosshair !important; }',
      '#gr-widget { position: fixed; bottom: 24px; right: 24px; z-index: 150;',
      '  display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }',
      '#gr-btn { display: flex; align-items: center; gap: 8px; padding: 10px 18px;',
      '  border: none; border-radius: 9999px; font-size: 14px; font-weight: 600;',
      '  cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,.25); transition: transform .15s, box-shadow .15s; }',
      '#gr-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,.3); }',
      '#gr-btn:active { transform: translateY(0); }',
      '#gr-btn.idle { background: #1D4ED8; color: #fff; }',
      '#gr-btn.recording { background: #DC2626; color: #fff; animation: gr-pulse 1.5s ease-in-out infinite; }',
      '#gr-badge { background: rgba(0,0,0,.55); color: #fff; font-size: 12px; font-weight: 700;',
      '  padding: 3px 10px; border-radius: 9999px; display: none; }',
      '#gr-toast { background: #1e293b; color: #f8fafc; font-size: 13px; padding: 8px 14px;',
      '  border-radius: 8px; max-width: 240px; text-align: center; opacity: 0;',
      '  transition: opacity .3s; pointer-events: none; }',
      '#gr-toast.show { opacity: 1; }',
      '@keyframes gr-pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(220,38,38,.5); }',
      '  50% { box-shadow: 0 0 0 8px rgba(220,38,38,0); } }',
    ].join('\n');
    document.head.appendChild(style);
  }

  // ── 위젯 DOM 구성 ─────────────────────────────────────────────────────────
  var widget, btn, badge, toast;

  function buildWidget() {
    widget = document.createElement('div');
    widget.id = 'gr-widget';

    toast = document.createElement('div');
    toast.id = 'gr-toast';

    badge = document.createElement('div');
    badge.id = 'gr-badge';

    btn = document.createElement('button');
    btn.id = 'gr-btn';
    btn.className = 'idle';
    btn.type = 'button';
    btn.setAttribute('aria-label', '가이드 녹화');

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (state.isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    });

    widget.appendChild(toast);
    widget.appendChild(badge);
    widget.appendChild(btn);
    document.body.appendChild(widget);
    updateWidgetState();
  }

  function updateWidgetState() {
    if (!btn) return;
    if (state.isRecording) {
      btn.className = 'recording';
      btn.innerHTML = '<i class="fa-solid fa-stop-circle"></i> 녹화 중지';
      badge.style.display = state.stepCount > 0 ? 'block' : 'none';
      badge.textContent = state.stepCount + '단계 기록됨';
    } else {
      btn.className = 'idle';
      btn.innerHTML = '<i class="fa-solid fa-circle"></i> 가이드 녹화';
      badge.style.display = 'none';
    }
  }

  function showToast(msg, duration) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(function () { toast.classList.remove('show'); }, duration || 2500);
  }

  // ── html2canvas 지연 로드 ─────────────────────────────────────────────────
  function loadHtml2Canvas() {
    if (html2canvasLoaded && window.html2canvas) return Promise.resolve();
    if (html2canvasLoading) return html2canvasLoading;
    html2canvasLoading = new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = CONFIG.html2canvasCdn;
      s.onload = function () { html2canvasLoaded = true; resolve(); };
      s.onerror = function () { reject(new Error('html2canvas 로드 실패')); };
      document.head.appendChild(s);
    });
    return html2canvasLoading;
  }

  // ── Highlight (hover) ─────────────────────────────────────────────────────
  var lastHighlighted = null;

  function onMouseOver(e) {
    if (e.target === widget || widget.contains(e.target)) return;
    if (lastHighlighted && lastHighlighted !== e.target) {
      lastHighlighted.classList.remove('gr-highlight');
    }
    e.target.classList.add('gr-highlight');
    lastHighlighted = e.target;
  }

  function onMouseOut(e) {
    e.target.classList.remove('gr-highlight');
    if (lastHighlighted === e.target) lastHighlighted = null;
  }

  // ── 클릭 캡처 ─────────────────────────────────────────────────────────────
  function extractElementMetadata(el) {
    return {
      tag: el.tagName ? el.tagName.toLowerCase() : '',
      text: (el.innerText || el.textContent || '').trim().slice(0, 80),
      id: el.id || '',
      href: el.href || (el.closest('a') ? el.closest('a').href : ''),
      classList: Array.prototype.slice.call(el.classList || []),
    };
  }

  function onDocumentClick(e) {
    // 위젯 내부 클릭은 무시
    if (e.target === widget || widget.contains(e.target)) return;
    if (state.pendingCapture) {
      showToast('캡처 중입니다…');
      return;
    }
    // 기본 동작(링크 이동 등) 차단
    e.preventDefault();
    e.stopPropagation();

    var metadata = extractElementMetadata(e.target);
    if (lastHighlighted) {
      lastHighlighted.classList.remove('gr-highlight');
      lastHighlighted = null;
    }
    captureStep(e.clientX, e.clientY, metadata);
  }

  function captureStep(clientX, clientY, metadata) {
    state.pendingCapture = true;
    btn.disabled = true;

    loadHtml2Canvas()
      .then(function () {
        return window.html2canvas(document.body, {
          scale: 1,
          useCORS: true,
          allowTaint: false,
          logging: false,
          // 위젯 자체는 캡처에서 제외
          ignoreElements: function (el) { return el.id === 'gr-widget'; },
        });
      })
      .then(function (canvas) {
        // 1920px 초과 시 다운스케일
        var finalCanvas = canvas;
        if (canvas.width > 1920) {
          var scale = 1920 / canvas.width;
          var tmp = document.createElement('canvas');
          tmp.width = 1920;
          tmp.height = Math.round(canvas.height * scale);
          tmp.getContext('2d').drawImage(canvas, 0, 0, tmp.width, tmp.height);
          finalCanvas = tmp;
        }

        var b64 = finalCanvas.toDataURL('image/png');
        var scrollX = window.scrollX || window.pageXOffset;
        var scrollY = window.scrollY || window.pageYOffset;

        return postJson(
          CONFIG.apiStepUrl.replace('{id}', state.sessionId),
          {
            screenshot: b64,
            click_x: clientX + scrollX,
            click_y: clientY + scrollY,
            canvas_width: finalCanvas.width,
            canvas_height: finalCanvas.height,
            element_metadata: metadata,
          }
        );
      })
      .then(function (data) {
        if (!data.ok) throw new Error(data.error || 'step 저장 실패');
        state.stepCount += 1;
        updateWidgetState();
        showToast('Step ' + state.stepCount + ' 기록됨 ✓');
      })
      .catch(function (err) {
        console.error('[GuideRecorder] captureStep 오류:', err);
        showToast('캡처 실패: ' + err.message, 3500);
      })
      .finally(function () {
        state.pendingCapture = false;
        btn.disabled = false;
      });
  }

  // ── 세션 생명주기 ─────────────────────────────────────────────────────────
  function startRecording() {
    btn.disabled = true;
    postJson(CONFIG.apiStartUrl, {})
      .then(function (data) {
        if (!data.ok) throw new Error(data.error || 'session 생성 실패');
        state.sessionId = data.session_id;
        state.stepCount = 0;
        state.isRecording = true;
        updateWidgetState();
        showToast('녹화 시작 — 기록할 요소를 클릭하세요');
        // capture phase: 클릭이 요소에 도달하기 전에 가로챔
        document.addEventListener('mouseover', onMouseOver, true);
        document.addEventListener('mouseout', onMouseOut, true);
        document.addEventListener('click', onDocumentClick, true);
      })
      .catch(function (err) {
        console.error('[GuideRecorder] startRecording 오류:', err);
        showToast('녹화 시작 실패: ' + err.message, 3500);
      })
      .finally(function () {
        btn.disabled = false;
      });
  }

  function stopRecording() {
    document.removeEventListener('mouseover', onMouseOver, true);
    document.removeEventListener('mouseout', onMouseOut, true);
    document.removeEventListener('click', onDocumentClick, true);
    if (lastHighlighted) {
      lastHighlighted.classList.remove('gr-highlight');
      lastHighlighted = null;
    }
    state.isRecording = false;
    updateWidgetState();

    if (!state.sessionId) return;
    btn.disabled = true;
    showToast('저장 중…');

    postJson(
      CONFIG.apiFinishUrl.replace('{id}', state.sessionId),
      {}
    )
      .then(function (data) {
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
        }
      })
      .catch(function (err) {
        console.error('[GuideRecorder] stopRecording 오류:', err);
        showToast('저장 실패 — 나중에 다시 시도해 주세요', 4000);
        btn.disabled = false;
      });
  }

  // ── 초기화 ────────────────────────────────────────────────────────────────
  function init() {
    injectStyles();
    buildWidget();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 디버그 핸들 (개발자 콘솔용)
  window.GuideRecorder = { state: state };
})();
