(function () {
  if (window.__eduMaterialsFrameHostInstalled) {
    return;
  }
  window.__eduMaterialsFrameHostInstalled = true;

  var frames = [];

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

  function describeError(data) {
    var message = text(data.message);
    var detail = text(data.detail);
    var url = text(data.url);

    if (data.kind === "resource") {
      var host = url;
      try {
        host = new URL(url).host || url;
      } catch (error) {}
      return "외부 파일을 불러오지 못했습니다. " + (host || "자료 안의 스크립트/스타일 주소") + " 연결을 확인해 주세요.";
    }

    if (data.kind === "timeout") {
      return "페이지는 열렸지만 로딩 화면이 계속 남아 있습니다. 시작 스크립트가 중간에 멈췄을 수 있습니다.";
    }

    if (message.indexOf("THREE") !== -1) {
      return "Three.js 초기화가 끝나지 않았습니다. 3D 자료가 필요한 외부 스크립트를 먼저 확인해 주세요.";
    }

    if (message.indexOf("WebGL") !== -1) {
      return "브라우저의 WebGL 초기화가 실패했습니다. 다른 브라우저나 기기에서 다시 열어 보세요.";
    }

    return detail || message || "자료 안의 스크립트가 실행 도중 멈췄습니다.";
  }

  function initFrame(shell) {
    var iframe = shell.querySelector("[data-material-iframe]");
    var status = shell.querySelector("[data-frame-status]");
    if (!iframe || !status) {
      return null;
    }

    var card = status.querySelector("[data-frame-status-card]");
    var title = status.querySelector("[data-frame-status-title]");
    var body = status.querySelector("[data-frame-status-body]");
    var reload = status.querySelector("[data-frame-status-reload]");
    var frameState = {
      iframe: iframe,
      status: status,
      card: card,
      title: title,
      body: body,
      reload: reload,
      ready: false,
      hasError: false,
    };

    frameState.show = function (titleText, bodyText, tone) {
      frameState.status.hidden = false;
      frameState.status.setAttribute("data-tone", tone || "notice");
      frameState.title.textContent = titleText;
      frameState.body.textContent = bodyText;
      if (frameState.card) {
        if (bodyText) {
          frameState.card.setAttribute("title", bodyText);
          frameState.card.setAttribute("aria-label", titleText + ". " + bodyText);
        } else {
          frameState.card.removeAttribute("title");
          frameState.card.setAttribute("aria-label", titleText);
        }
      }
    };

    frameState.hide = function () {
      frameState.status.hidden = true;
    };

    if (reload) {
      reload.addEventListener("click", function () {
        frameState.ready = false;
        frameState.hasError = false;
        frameState.hide();
        iframe.src = iframe.src;
      });
    }
    return frameState;
  }

  function findFrameBySource(source) {
    for (var index = 0; index < frames.length; index += 1) {
      if (frames[index].iframe.contentWindow === source) {
        return frames[index];
      }
    }
    return null;
  }

  function boot() {
    var shells = document.querySelectorAll("[data-material-frame-shell]");
    for (var index = 0; index < shells.length; index += 1) {
      var frameState = initFrame(shells[index]);
      if (frameState) {
        frames.push(frameState);
      }
    }
  }

  window.addEventListener("message", function (event) {
    var frameState = findFrameBySource(event.source);
    if (!frameState) {
      return;
    }

    var data = event.data || {};
    if (!data.type || data.type.indexOf("edu-materials:") !== 0) {
      return;
    }

    if (data.type === "edu-materials:runtime-ready") {
      frameState.ready = true;
      frameState.hasError = false;
      frameState.hide();
      return;
    }

    if (data.type === "edu-materials:runtime-error") {
      frameState.ready = false;
      frameState.hasError = true;
      frameState.show("오류 있음", describeError(data), "error");
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
