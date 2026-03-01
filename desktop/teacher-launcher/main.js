const path = require("path");
const { app, BrowserWindow, dialog, screen } = require("electron");

const PROTOCOL = "eduitit-launcher";
const MIN_VIDEO_WIDTH = 640;
const MIN_DASHBOARD_WIDTH = 560;
const DEFAULT_LEFT_RATIO = 0.54;
const SPLIT_GAP = 0;
const ALWAYS_ON_TOP_LEVEL = "screen-saver";
const WATCHDOG_INTERVAL_MS = 1400;

let videoWindow = null;
let dashboardWindow = null;
let infoWindow = null;
let blackoutWindow = null;
let watchdogTimer = null;
let lastLaunchPayload = null;
let isRestoringSplit = false;

function extractLaunchUrlFromArgv(argv) {
  if (!Array.isArray(argv)) return null;
  return argv.find((value) => typeof value === "string" && value.startsWith(`${PROTOCOL}://`)) || null;
}

function normalizeHttpUrl(raw) {
  if (typeof raw !== "string" || !raw.trim()) return null;
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    return parsed.toString();
  } catch (_) {
    return null;
  }
}

function decodePayload(rawPayload) {
  if (!rawPayload) return null;
  const padded = rawPayload + "=".repeat((4 - (rawPayload.length % 4)) % 4);
  const base64 = padded.replace(/-/g, "+").replace(/_/g, "/");
  const decoded = Buffer.from(base64, "base64").toString("utf-8");
  return JSON.parse(decoded);
}

function parseLaunchUrl(rawUrl) {
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== `${PROTOCOL}:`) {
      throw new Error("unsupported_protocol");
    }

    const encodedPayload = parsed.searchParams.get("payload");
    if (!encodedPayload) {
      throw new Error("missing_payload");
    }

    const payload = decodePayload(encodedPayload);
    const youtubeUrl = normalizeHttpUrl(payload.youtubeUrl);
    const dashboardUrl = normalizeHttpUrl(payload.dashboardUrl);
    if (!youtubeUrl || !dashboardUrl) {
      throw new Error("invalid_urls");
    }

    if (typeof payload.expiresAt === "number") {
      const now = Math.floor(Date.now() / 1000);
      if (now > payload.expiresAt) {
        throw new Error("expired_payload");
      }
    }

    return {
      classId: payload.classId,
      title: payload.title || "Eduitit ArtClass",
      youtubeUrl,
      dashboardUrl,
    };
  } catch (err) {
    return { error: err instanceof Error ? err.message : "invalid_payload" };
  }
}

function showErrorBox(message) {
  dialog.showErrorBox("Eduitit Teacher Launcher", message);
}

function closeSplitWindows() {
  if (videoWindow && !videoWindow.isDestroyed()) videoWindow.close();
  if (dashboardWindow && !dashboardWindow.isDestroyed()) dashboardWindow.close();
  if (blackoutWindow && !blackoutWindow.isDestroyed()) blackoutWindow.close();
  videoWindow = null;
  dashboardWindow = null;
  blackoutWindow = null;
}

function closeBlackoutWindow() {
  if (blackoutWindow && !blackoutWindow.isDestroyed()) {
    blackoutWindow.close();
  }
  blackoutWindow = null;
}

function isSplitWindowAlive(win) {
  return Boolean(win && !win.isDestroyed());
}

function enforceWindowVisible(win) {
  if (!isSplitWindowAlive(win)) return;
  if (win.isMinimized()) win.restore();
  if (!win.isVisible()) win.show();
}

function isAllowedVideoHost(hostname) {
  const host = String(hostname || "").replace(/^www\./, "");
  return (
    host === "youtube.com" ||
    host.endsWith(".youtube.com") ||
    host === "youtu.be" ||
    host.endsWith(".googlevideo.com") ||
    host.endsWith(".ytimg.com") ||
    host.endsWith(".ggpht.com")
  );
}

function isAllowedNavigation(targetUrl, payload, role) {
  try {
    const parsed = new URL(targetUrl);
    if (role === "video") {
      return isAllowedVideoHost(parsed.hostname);
    }
    const dashboardOrigin = new URL(payload.dashboardUrl).origin;
    return parsed.origin === dashboardOrigin;
  } catch (_) {
    return false;
  }
}

function installWindowGuards(win, payload, role) {
  if (!isSplitWindowAlive(win)) return;

  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event, targetUrl) => {
    if (isAllowedNavigation(targetUrl, payload, role)) return;
    event.preventDefault();
  });
  win.webContents.on("context-menu", (event) => {
    event.preventDefault();
  });

  win.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    const key = String(input.key || "").toLowerCase();
    if (key === "b" && !input.control && !input.meta && !input.alt) {
      event.preventDefault();
      toggleBlackout();
      return;
    }
    if (key === "escape" && blackoutWindow && !blackoutWindow.isDestroyed()) {
      event.preventDefault();
      closeBlackoutWindow();
    }
  });
}

function getTargetDisplay() {
  const cursorPoint = screen.getCursorScreenPoint();
  return screen.getDisplayNearestPoint(cursorPoint) || screen.getPrimaryDisplay();
}

function pickLeftRatio(totalWidth) {
  if (totalWidth <= 1366) return 0.5;
  if (totalWidth <= 1600) return 0.52;
  if (totalWidth <= 1920) return 0.53;
  return DEFAULT_LEFT_RATIO;
}

function createInfoWindow() {
  if (infoWindow && !infoWindow.isDestroyed()) {
    infoWindow.focus();
    return;
  }

  infoWindow = new BrowserWindow({
    width: 560,
    height: 420,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  infoWindow.setMenuBarVisibility(false);

  const html = [
    "<html><head><meta charset='utf-8'><title>Eduitit Launcher</title></head>",
    "<body style='font-family:Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:28px;'>",
    "<h2 style='margin-top:0;'>Eduitit Teacher Launcher</h2>",
    "<p style='line-height:1.6;'>브라우저에서 <strong>런처로 수업 시작</strong> 버튼을 누르면",
    " 왼쪽(유튜브) + 오른쪽(대시보드) 분할 창이 자동으로 열립니다.</p>",
    "<p style='line-height:1.6;color:#94a3b8;'>이 창은 대기 화면입니다. 수업 시작 버튼으로 런처를 호출해 주세요.</p>",
    "</body></html>",
  ].join("");

  infoWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
  infoWindow.on("closed", () => {
    infoWindow = null;
  });
}

function computeSplitBounds() {
  const display = getTargetDisplay();
  // Use full display bounds so split windows can cover taskbar area.
  const area = display.bounds;
  const totalWidth = Math.max(1, area.width - SPLIT_GAP);
  const leftRatio = pickLeftRatio(totalWidth);

  let leftWidth = Math.floor(totalWidth * leftRatio);
  leftWidth = Math.max(MIN_VIDEO_WIDTH, leftWidth);
  leftWidth = Math.min(totalWidth - MIN_DASHBOARD_WIDTH, leftWidth);

  let rightWidth = totalWidth - leftWidth;
  if (rightWidth < MIN_DASHBOARD_WIDTH) {
    rightWidth = MIN_DASHBOARD_WIDTH;
    leftWidth = totalWidth - rightWidth;
  }
  if (leftWidth < MIN_VIDEO_WIDTH) {
    leftWidth = MIN_VIDEO_WIDTH;
    rightWidth = totalWidth - leftWidth;
  }

  return {
    x: area.x,
    y: area.y,
    width: area.width,
    height: area.height,
    leftWidth,
    rightX: area.x + leftWidth + SPLIT_GAP,
    rightWidth,
  };
}

function getBlackoutBounds() {
  const bounds = computeSplitBounds();
  return {
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
  };
}

function syncBlackoutBounds() {
  if (!blackoutWindow || blackoutWindow.isDestroyed()) return;
  blackoutWindow.setBounds(getBlackoutBounds());
}

function createBlackoutWindow() {
  if (blackoutWindow && !blackoutWindow.isDestroyed()) {
    syncBlackoutBounds();
    blackoutWindow.showInactive();
    return;
  }

  const bounds = getBlackoutBounds();
  blackoutWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    frame: false,
    backgroundColor: "#000000",
    autoHideMenuBar: true,
    skipTaskbar: true,
    alwaysOnTop: true,
    focusable: false,
    fullscreenable: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  blackoutWindow.setAlwaysOnTop(true, ALWAYS_ON_TOP_LEVEL);
  blackoutWindow.setIgnoreMouseEvents(true);
  blackoutWindow.setMenuBarVisibility(false);
  blackoutWindow.loadURL("data:text/html;charset=utf-8,<html><body style='margin:0;background:#000;'></body></html>");
  blackoutWindow.on("closed", () => {
    blackoutWindow = null;
  });
}

function toggleBlackout() {
  if (blackoutWindow && !blackoutWindow.isDestroyed()) {
    closeBlackoutWindow();
    return;
  }
  createBlackoutWindow();
}

function applyTeachingWindowBehavior(win) {
  if (!win || win.isDestroyed()) return;
  win.setMenuBarVisibility(false);
  // Keep split windows above taskbar/other windows during class mode.
  win.setAlwaysOnTop(true, ALWAYS_ON_TOP_LEVEL);
}

function relayoutSplitWindows() {
  if (!videoWindow || videoWindow.isDestroyed()) return;
  if (!dashboardWindow || dashboardWindow.isDestroyed()) return;

  const bounds = computeSplitBounds();
  videoWindow.setBounds({
    x: bounds.x,
    y: bounds.y,
    width: bounds.leftWidth,
    height: bounds.height,
  });
  dashboardWindow.setBounds({
    x: bounds.rightX,
    y: bounds.y,
    width: bounds.rightWidth,
    height: bounds.height,
  });
  syncBlackoutBounds();
}

function ensureSplitHealthy() {
  if (!lastLaunchPayload) return;

  const videoAlive = isSplitWindowAlive(videoWindow);
  const dashboardAlive = isSplitWindowAlive(dashboardWindow);
  if (!videoAlive || !dashboardAlive) {
    if (isRestoringSplit) return;
    isRestoringSplit = true;
    try {
      createSplitWindows(lastLaunchPayload);
    } finally {
      isRestoringSplit = false;
    }
    return;
  }

  enforceWindowVisible(videoWindow);
  enforceWindowVisible(dashboardWindow);
  applyTeachingWindowBehavior(videoWindow);
  applyTeachingWindowBehavior(dashboardWindow);
  relayoutSplitWindows();
}

function startWatchdog() {
  if (watchdogTimer) return;
  watchdogTimer = setInterval(() => {
    ensureSplitHealthy();
  }, WATCHDOG_INTERVAL_MS);
}

function stopWatchdog() {
  if (!watchdogTimer) return;
  clearInterval(watchdogTimer);
  watchdogTimer = null;
}

function installYouTubeFocusMode(targetWindow) {
  if (!targetWindow || targetWindow.isDestroyed()) return;

  const applyScript = () => {
    const js = `
      (() => {
        const href = window.location.href || "";
        if (!href.includes("youtube.com/watch")) return;

        const styleId = "eduitit-youtube-focus-style";
        if (!document.getElementById(styleId)) {
          const style = document.createElement("style");
          style.id = styleId;
          style.textContent = \`
            #masthead-container,
            #secondary,
            #below,
            ytd-comments,
            ytd-watch-next-secondary-results-renderer,
            ytd-merch-shelf-renderer,
            #chat,
            #panels,
            #meta,
            #top-row,
            #related {
              display: none !important;
            }

            html, body, ytd-app, ytd-page-manager, ytd-watch-flexy {
              background: #000 !important;
              margin: 0 !important;
              padding: 0 !important;
              overflow: hidden !important;
            }

            ytd-watch-flexy #columns,
            ytd-watch-flexy #primary,
            ytd-watch-flexy #primary-inner {
              margin: 0 !important;
              padding: 0 !important;
              max-width: none !important;
              width: 100vw !important;
            }

            ytd-watch-flexy #player,
            ytd-watch-flexy #player-container,
            .html5-video-player {
              width: 100vw !important;
              height: 100vh !important;
              max-height: 100vh !important;
            }
          \`;
          document.head.appendChild(style);
        }

        const sizeButton = document.querySelector(".ytp-size-button");
        if (sizeButton && sizeButton.getAttribute("aria-pressed") !== "true") {
          sizeButton.click();
        }

        if (!window.__eduititRepeatEnforcer) {
          window.__eduititRepeatEnforcer = window.setInterval(() => {
            const video = document.querySelector("video");
            if (!video) return;

            video.loop = true;
            video.setAttribute("loop", "loop");

            if (!video.dataset.eduititLoopBound) {
              video.dataset.eduititLoopBound = "1";
              video.addEventListener("ended", () => {
                const replayButton = document.querySelector(".ytp-replay-button");
                if (replayButton) {
                  replayButton.click();
                  return;
                }
                video.currentTime = 0;
                video.play().catch(() => {});
              });
            }
          }, 1200);
        }

        window.scrollTo(0, 0);
      })();
    `;
    targetWindow.webContents.executeJavaScript(js).catch(() => {});
  };

  targetWindow.webContents.on("did-finish-load", applyScript);
  targetWindow.webContents.on("did-navigate-in-page", applyScript);
}

function createSplitWindows(payload) {
  closeSplitWindows();
  if (infoWindow && !infoWindow.isDestroyed()) {
    infoWindow.close();
  }

  const bounds = computeSplitBounds();

  videoWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.leftWidth,
    height: bounds.height,
    autoHideMenuBar: true,
    title: `${payload.title} - Video`,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  applyTeachingWindowBehavior(videoWindow);
  installWindowGuards(videoWindow, payload, "video");
  videoWindow.loadURL(payload.youtubeUrl);
  installYouTubeFocusMode(videoWindow);

  dashboardWindow = new BrowserWindow({
    x: bounds.rightX,
    y: bounds.y,
    width: bounds.rightWidth,
    height: bounds.height,
    autoHideMenuBar: true,
    title: `${payload.title} - Dashboard`,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  applyTeachingWindowBehavior(dashboardWindow);
  installWindowGuards(dashboardWindow, payload, "dashboard");
  dashboardWindow.loadURL(payload.dashboardUrl);

  videoWindow.webContents.once("did-finish-load", () => {
    // Keep the player section visible at top after launch.
    videoWindow.webContents.executeJavaScript("window.scrollTo(0, 0)").catch(() => {});
  });

  videoWindow.on("closed", () => {
    videoWindow = null;
  });
  dashboardWindow.on("closed", () => {
    dashboardWindow = null;
  });

  startWatchdog();
}

function handleLaunchUrl(rawUrl) {
  const parsed = parseLaunchUrl(rawUrl);
  if (parsed.error) {
    showErrorBox(`런처 payload를 읽지 못했습니다: ${parsed.error}`);
    return;
  }
  lastLaunchPayload = parsed;
  createSplitWindows(parsed);
}

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", (_, argv) => {
    const launchUrl = extractLaunchUrlFromArgv(argv);
    if (launchUrl) {
      handleLaunchUrl(launchUrl);
      return;
    }
    if (dashboardWindow && !dashboardWindow.isDestroyed()) dashboardWindow.focus();
    else if (videoWindow && !videoWindow.isDestroyed()) videoWindow.focus();
    else createInfoWindow();
  });

  if (process.defaultApp) {
    app.setAsDefaultProtocolClient(PROTOCOL, process.execPath, [path.resolve(process.argv[1])]);
  } else {
    app.setAsDefaultProtocolClient(PROTOCOL);
  }

  app.whenReady().then(() => {
    const launchUrl = extractLaunchUrlFromArgv(process.argv);
    if (launchUrl) {
      handleLaunchUrl(launchUrl);
      return;
    }
    createInfoWindow();
  });
}

app.on("open-url", (event, rawUrl) => {
  event.preventDefault();
  if (app.isReady()) {
    handleLaunchUrl(rawUrl);
    return;
  }
  app.whenReady().then(() => handleLaunchUrl(rawUrl));
});

app.on("window-all-closed", () => {
  stopWatchdog();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (!videoWindow && !dashboardWindow) {
    createInfoWindow();
  }
});

screen.on("display-metrics-changed", () => {
  relayoutSplitWindows();
});

screen.on("display-added", () => {
  relayoutSplitWindows();
});

screen.on("display-removed", () => {
  relayoutSplitWindows();
});

app.on("before-quit", () => {
  stopWatchdog();
});
