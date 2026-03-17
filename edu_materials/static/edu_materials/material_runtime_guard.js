(function () {
  if (window.__eduMaterialsRuntimeGuardInstalled) {
    return;
  }
  window.__eduMaterialsRuntimeGuardInstalled = true;

  var readyReported = false;
  var issueReported = false;
  var pendingIssue = null;
  var overlayId = "__edu_materials_runtime_guard__";
  var READY_CHECK_INTERVAL_MS = 400;

  function text(value) {
    if (value === null || value === undefined) {
      return "";
    }
    try {
      return String(value);
    } catch (error) {
      return "";
    }
  }

  function post(type, payload) {
    try {
      var message = payload || {};
      message.type = type;
      if (window.parent && window.parent !== window) {
        window.parent.postMessage(message, "*");
      }
    } catch (error) {}
  }

  function isVisible(element) {
    if (!element || !element.getBoundingClientRect || !window.getComputedStyle) {
      return false;
    }
    var style = window.getComputedStyle(element);
    if (!style || style.display === "none" || style.visibility === "hidden") {
      return false;
    }
    if (parseFloat(style.opacity || "1") <= 0.05) {
      return false;
    }
    var rect = element.getBoundingClientRect();
    return rect.width >= Math.max(window.innerWidth * 0.55, 220) &&
      rect.height >= Math.max(window.innerHeight * 0.35, 140);
  }

  function pushUnique(list, elements) {
    for (var index = 0; index < elements.length; index += 1) {
      if (list.indexOf(elements[index]) === -1) {
        list.push(elements[index]);
      }
    }
  }

  function findBlockingOverlay() {
    if (!document.querySelectorAll) {
      return null;
    }

    var candidates = [];
    pushUnique(
      candidates,
      document.querySelectorAll(
        "#loading, #loader, #app-loading, #splash, #splash-screen, [data-loading], [data-loader]"
      )
    );
    pushUnique(
      candidates,
      document.querySelectorAll(
        "[id*='load'], [class*='load'], [id*='spinner'], [class*='spinner'], [id*='splash'], [class*='splash']"
      )
    );

    for (var index = 0; index < candidates.length; index += 1) {
      if (isVisible(candidates[index])) {
        return candidates[index];
      }
    }
    return null;
  }

  function describeIssue(payload) {
    var message = text(payload.message);
    var url = text(payload.url);

    if (payload.kind === "resource" && url) {
      return {
        title: "외부 파일을 불러오지 못했습니다.",
        body: "자료가 사용하는 스크립트나 스타일 주소가 응답하지 않았습니다. " + url,
      };
    }

    if (message.indexOf("THREE") !== -1) {
      return {
        title: "3D 라이브러리 초기화가 멈췄습니다.",
        body: "Three.js 또는 관련 보조 스크립트가 준비되지 않아 3D 화면이 시작되지 않았습니다.",
      };
    }

    if (message.indexOf("WebGL") !== -1) {
      return {
        title: "브라우저 3D 실행이 실패했습니다.",
        body: "이 기기나 브라우저에서 WebGL 초기화가 실패해 3D 자료를 띄우지 못했습니다.",
      };
    }

    if (payload.kind === "timeout") {
      return {
        title: "로딩 화면에서 멈췄습니다.",
        body: "페이지는 열렸지만 시작 스크립트가 끝까지 실행되지 않아 로딩 화면이 계속 남아 있습니다.",
      };
    }

    if (payload.kind === "promise") {
      return {
        title: "비동기 작업 중 오류가 났습니다.",
        body: message || "자료 안의 비동기 초기화 작업이 끝나기 전에 오류가 발생했습니다.",
      };
    }

    return {
      title: "자료 실행 중 오류가 났습니다.",
      body: message || "페이지를 여는 도중 스크립트가 중간에 멈췄습니다.",
    };
  }

  function ensurePanel(description) {
    var panel = document.getElementById(overlayId);
    if (!panel) {
      panel = document.createElement("div");
      panel.id = overlayId;
      panel.setAttribute("role", "alert");
      panel.style.cssText =
        "box-sizing:border-box;max-width:560px;width:min(92vw,560px);padding:24px;border-radius:24px;border:1px solid rgba(248,113,113,.45);background:rgba(15,23,42,.96);color:#f8fafc;box-shadow:0 20px 60px rgba(2,6,23,.45);font-family:'Noto Sans KR',sans-serif;";
      panel.innerHTML =
        '<div style="font-size:20px;font-weight:800;line-height:1.4;" data-edu-runtime-title></div>' +
        '<p style="margin:12px 0 0;font-size:14px;line-height:1.7;color:#cbd5e1;" data-edu-runtime-body></p>' +
        '<p style="margin:12px 0 0;font-size:12px;line-height:1.6;color:#94a3b8;">교육자료실은 저장된 HTML 자체는 유지하고, 실행 오류만 화면에 드러나게 합니다.</p>';
    }

    panel.querySelector("[data-edu-runtime-title]").textContent = description.title;
    panel.querySelector("[data-edu-runtime-body]").textContent = description.body;
    return panel;
  }

  function mountPanel(payload) {
    var description = describeIssue(payload);
    post("edu-materials:runtime-error", {
      kind: payload.kind || "runtime",
      message: text(payload.message),
      url: text(payload.url),
      detail: description.body,
    });

    if (!document.body) {
      pendingIssue = payload;
      return;
    }

    var panel = ensurePanel(description);
    var overlay = findBlockingOverlay();

    if (overlay && overlay !== panel) {
      overlay.innerHTML = "";
      overlay.appendChild(panel);
      overlay.style.display = "flex";
      overlay.style.alignItems = "center";
      overlay.style.justifyContent = "center";
      overlay.style.position = "fixed";
      overlay.style.inset = "0";
      overlay.style.padding = "24px";
      overlay.style.background = "rgba(2,6,23,.96)";
      overlay.style.opacity = "1";
      overlay.style.visibility = "visible";
      overlay.style.zIndex = "2147483647";
      return;
    }

    panel.style.position = "fixed";
    panel.style.inset = "auto 24px 24px auto";
    panel.style.zIndex = "2147483647";
    document.body.appendChild(panel);
  }

  function reportIssue(payload) {
    if (issueReported) {
      return;
    }
    issueReported = true;
    mountPanel(payload || { kind: "runtime", message: "" });
  }

  window.addEventListener(
    "error",
    function (event) {
      var target = event.target || event.srcElement;
      if (target && target !== window) {
        var tagName = text(target.tagName).toUpperCase();
        if (tagName === "SCRIPT" || tagName === "LINK") {
          reportIssue({
            kind: "resource",
            message: tagName + " load failed",
            url: target.src || target.href || "",
          });
          return;
        }
      }

      reportIssue({
        kind: "runtime",
        message: event.message || "스크립트 오류가 발생했습니다.",
        url: event.filename || "",
      });
    },
    true
  );

  window.addEventListener("unhandledrejection", function (event) {
    var reason = event.reason;
    var message = "";

    if (reason && typeof reason === "object") {
      message = text(reason.message || reason.stack || reason.name);
    }
    if (!message) {
      message = text(reason) || "처리되지 않은 비동기 오류가 발생했습니다.";
    }

    reportIssue({
      kind: "promise",
      message: message,
    });
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (pendingIssue) {
      mountPanel(pendingIssue);
      pendingIssue = null;
    }
  });

  function maybeReportReady() {
    if (readyReported || issueReported) {
      return;
    }

    function checkRuntimeState() {
      if (readyReported || issueReported) {
        return;
      }

      if (!findBlockingOverlay()) {
        readyReported = true;
        post("edu-materials:runtime-ready", {});
        return;
      }

      window.setTimeout(checkRuntimeState, READY_CHECK_INTERVAL_MS);
    }

    window.setTimeout(checkRuntimeState, READY_CHECK_INTERVAL_MS);
  }

  if (document.readyState === "complete") {
    maybeReportReady();
  } else {
    window.addEventListener("load", maybeReportReady);
  }
})();
