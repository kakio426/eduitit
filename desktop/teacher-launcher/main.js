const fs = require("fs");
const http = require("http");
const https = require("https");
const path = require("path");
const { app, BrowserWindow, dialog, screen } = require("electron");
const { NsisUpdater } = require("electron-updater");

const PROTOCOL = "eduitit-launcher";
const MIN_VIDEO_WIDTH = 640;
const MIN_DASHBOARD_WIDTH = 560;
const DEFAULT_LEFT_RATIO = 0.62;
const TV_MODE_LEFT_RATIO = 0.5;
const SPLIT_GAP = 0;
const ALWAYS_ON_TOP_LEVEL = "screen-saver";
const WATCHDOG_INTERVAL_MS = 1400;
const WATCHDOG_RECOVER_COOLDOWN_MS = 4000;
const WATCHDOG_MAX_RECOVERY_PER_MIN = 3;
const SPLIT_RATIO_MIN = 0.45;
const SPLIT_RATIO_MAX = 0.72;
const SPLIT_RATIO_STEP = 0.03;
const AUTO_UPDATE_CACHE_FILENAME = "launcher-release-config.json";
const AUTO_UPDATE_CHECK_MIN_INTERVAL_MS = 30 * 60 * 1000;

let videoWindow = null;
let dashboardWindow = null;
let infoWindow = null;
let blackoutWindow = null;
let watchdogTimer = null;
let lastLaunchPayload = null;
let isRestoringSplit = false;
let displayHandlersBound = false;
let splitCreateLock = false;
let lastRecoveryAt = 0;
let recoveryAttemptTimestamps = [];
let watchdogCircuitOpen = false;
let splitRatioOverride = null;
let appTerminating = false;
let splitDisplayId = null;
let autoUpdater = null;
let updateCheckPromise = null;
let downloadedUpdateInfo = null;
let downloadedUpdatePromptOpen = false;
let cachedLauncherReleaseConfig = {
  configUrl: "",
  updateBaseUrl: "",
  downloadUrl: "",
  bridgeNotice: "",
  bridgeVersion: "",
  lastCheckedAt: 0,
};

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

function extractYouTubeVideoId(rawUrl) {
  if (typeof rawUrl !== "string" || !rawUrl.trim()) return "";

  try {
    const parsed = new URL(rawUrl);
    const host = String(parsed.hostname || "").toLowerCase().replace(/^www\./, "");

    if (host === "youtu.be") {
      return parsed.pathname.split("/").filter(Boolean)[0] || "";
    }

    if (host.endsWith("youtube.com")) {
      if (parsed.pathname === "/watch") {
        return parsed.searchParams.get("v") || "";
      }

      const pathParts = parsed.pathname.split("/").filter(Boolean);
      if (pathParts.length > 1 && ["embed", "shorts", "live"].includes(pathParts[0])) {
        return pathParts[1];
      }
    }
  } catch (_) {
    // Fall through to regex extraction.
  }

  const matched = String(rawUrl).match(/(?:v=|youtu\.be\/|shorts\/|embed\/|live\/)([A-Za-z0-9_-]{6,})/);
  return matched ? matched[1] : "";
}

function buildYouTubeWatchUrl(videoId, { autoplay = true } = {}) {
  if (!videoId) return "";

  const url = new URL("https://www.youtube.com/watch");
  url.searchParams.set("v", videoId);
  if (autoplay) {
    url.searchParams.set("autoplay", "1");
  }
  return url.toString();
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
    const updateConfigUrl = normalizeHttpUrl(payload.updateConfigUrl);
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
      updateConfigUrl: updateConfigUrl || "",
    };
  } catch (err) {
    return { error: err instanceof Error ? err.message : "invalid_payload" };
  }
}

function showErrorBox(message) {
  dialog.showErrorBox("Eduitit Teacher Launcher", message);
}

function normalizeUpdateBaseUrl(rawUrl) {
  const normalized = normalizeHttpUrl(rawUrl);
  if (!normalized) return "";
  return normalized.endsWith("/") ? normalized : `${normalized}/`;
}

function normalizeTimestamp(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return 0;
  return Math.trunc(parsed);
}

function normalizeShortText(value, maxLength = 500) {
  if (typeof value !== "string") return "";
  return value.trim().slice(0, maxLength);
}

function normalizeLauncherReleaseConfig(raw, fallback = {}) {
  const source = raw && typeof raw === "object" ? raw : {};
  const previous = fallback && typeof fallback === "object" ? fallback : {};
  return {
    configUrl: normalizeHttpUrl(source.configUrl) || normalizeHttpUrl(previous.configUrl) || "",
    updateBaseUrl: normalizeUpdateBaseUrl(source.updateBaseUrl) || normalizeUpdateBaseUrl(previous.updateBaseUrl) || "",
    downloadUrl: normalizeHttpUrl(source.downloadUrl) || normalizeHttpUrl(previous.downloadUrl) || "",
    bridgeNotice: normalizeShortText(source.bridgeNotice || previous.bridgeNotice, 500),
    bridgeVersion: normalizeShortText(source.bridgeVersion || previous.bridgeVersion, 50),
    lastCheckedAt: normalizeTimestamp(source.lastCheckedAt || previous.lastCheckedAt),
  };
}

function getLauncherReleaseConfigStatePath() {
  try {
    return path.join(app.getPath("userData"), AUTO_UPDATE_CACHE_FILENAME);
  } catch (_) {
    return "";
  }
}

function loadLauncherReleaseConfigState() {
  const statePath = getLauncherReleaseConfigStatePath();
  if (!statePath || !fs.existsSync(statePath)) {
    return cachedLauncherReleaseConfig;
  }

  try {
    const raw = JSON.parse(fs.readFileSync(statePath, "utf8"));
    cachedLauncherReleaseConfig = normalizeLauncherReleaseConfig(raw, cachedLauncherReleaseConfig);
  } catch (err) {
    console.error("[launcher-update] failed to read cached config:", err);
  }

  return cachedLauncherReleaseConfig;
}

function saveLauncherReleaseConfigState(patch = {}) {
  cachedLauncherReleaseConfig = normalizeLauncherReleaseConfig(
    { ...cachedLauncherReleaseConfig, ...patch },
    cachedLauncherReleaseConfig
  );

  const statePath = getLauncherReleaseConfigStatePath();
  if (!statePath) {
    return cachedLauncherReleaseConfig;
  }

  try {
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.writeFileSync(statePath, JSON.stringify(cachedLauncherReleaseConfig, null, 2), "utf8");
  } catch (err) {
    console.error("[launcher-update] failed to persist config:", err);
  }

  return cachedLauncherReleaseConfig;
}

function fetchJson(rawUrl) {
  return new Promise((resolve, reject) => {
    const normalizedUrl = normalizeHttpUrl(rawUrl);
    if (!normalizedUrl) {
      reject(new Error("invalid_url"));
      return;
    }

    const target = new URL(normalizedUrl);
    const client = target.protocol === "https:" ? https : http;
    const request = client.request(
      target,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
          "User-Agent": `EduititTeacherLauncher/${app.getVersion() || "0.2.0"}`,
        },
      },
      (response) => {
        const statusCode = Number(response.statusCode || 0);
        if (statusCode >= 400) {
          response.resume();
          reject(new Error(`http_${statusCode}`));
          return;
        }

        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", () => {
          try {
            resolve(JSON.parse(body || "{}"));
          } catch (_) {
            reject(new Error("invalid_json"));
          }
        });
      }
    );

    request.on("error", reject);
    request.setTimeout(5000, () => {
      request.destroy(new Error("timeout"));
    });
    request.end();
  });
}

function hasActiveSplitSession() {
  return (
    (videoWindow && !videoWindow.isDestroyed()) ||
    (dashboardWindow && !dashboardWindow.isDestroyed()) ||
    (blackoutWindow && !blackoutWindow.isDestroyed())
  );
}

async function promptForDownloadedUpdate(info) {
  if (!info || downloadedUpdatePromptOpen) return;

  downloadedUpdatePromptOpen = true;
  downloadedUpdateInfo = info;

  try {
    const ownerWindow = infoWindow && !infoWindow.isDestroyed() ? infoWindow : undefined;
    const versionLabel = normalizeShortText(info.version, 40) || "새 버전";
    const dialogOptions = {
      type: "info",
      buttons: ["지금 재시작", "나중에"],
      defaultId: 0,
      cancelId: 1,
      noLink: true,
      title: "Eduitit Teacher Launcher",
      message: `런처 업데이트 ${versionLabel} 다운로드가 끝났습니다.`,
      detail: "지금 재시작하면 바로 업데이트됩니다. 나중에를 누르면 다음 종료 때 자동으로 설치됩니다.",
    };
    const result = ownerWindow
      ? await dialog.showMessageBox(ownerWindow, dialogOptions)
      : await dialog.showMessageBox(dialogOptions);

    if (result.response === 0) {
      const updater = ensureAutoUpdater();
      if (updater) {
        updater.quitAndInstall();
        return;
      }
    }
  } catch (err) {
    console.error("[launcher-update] failed to show restart prompt:", err);
  } finally {
    downloadedUpdatePromptOpen = false;
    downloadedUpdateInfo = null;
  }
}

function maybePromptForDownloadedUpdate() {
  if (!downloadedUpdateInfo || hasActiveSplitSession()) return;
  void promptForDownloadedUpdate(downloadedUpdateInfo);
}

function ensureAutoUpdater() {
  if (!app.isPackaged) return null;
  if (autoUpdater) return autoUpdater;

  autoUpdater = new NsisUpdater();
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.logger = console;
  autoUpdater.on("error", (err) => {
    console.error("[launcher-update] updater error:", err);
  });
  autoUpdater.on("update-downloaded", (info) => {
    downloadedUpdateInfo = info || { version: "" };
    if (hasActiveSplitSession()) return;
    maybePromptForDownloadedUpdate();
  });
  return autoUpdater;
}

async function checkForLauncherUpdates({ force = false } = {}) {
  const state = loadLauncherReleaseConfigState();
  if (!state.updateBaseUrl) return null;

  if (!app.isPackaged) {
    saveLauncherReleaseConfigState({ lastCheckedAt: Date.now() });
    return null;
  }

  if (updateCheckPromise) {
    return updateCheckPromise;
  }

  const now = Date.now();
  if (!force && state.lastCheckedAt && now - state.lastCheckedAt < AUTO_UPDATE_CHECK_MIN_INTERVAL_MS) {
    return null;
  }

  const updater = ensureAutoUpdater();
  if (!updater) return null;

  updater.setFeedURL({
    provider: "generic",
    url: state.updateBaseUrl,
  });
  saveLauncherReleaseConfigState({ lastCheckedAt: now });
  updateCheckPromise = updater
    .checkForUpdates()
    .catch((err) => {
      console.error("[launcher-update] check failed:", err);
      return null;
    })
    .finally(() => {
      updateCheckPromise = null;
    });
  return updateCheckPromise;
}

async function syncLauncherReleaseConfig(rawConfigUrl, { checkImmediately = false, force = false } = {}) {
  const configUrl = normalizeHttpUrl(rawConfigUrl);
  if (!configUrl) {
    return loadLauncherReleaseConfigState();
  }

  saveLauncherReleaseConfigState({ configUrl });

  try {
    const payload = await fetchJson(configUrl);
    const nextState = saveLauncherReleaseConfigState({
      configUrl,
      downloadUrl: payload.downloadUrl,
      updateBaseUrl: payload.updateBaseUrl,
      bridgeNotice: payload.bridgeNotice,
      bridgeVersion: payload.bridgeVersion,
    });
    if (nextState.updateBaseUrl && (checkImmediately || force)) {
      await checkForLauncherUpdates({ force });
    }
    return nextState;
  } catch (err) {
    console.error("[launcher-update] failed to refresh config:", err);
    return loadLauncherReleaseConfigState();
  }
}

function bootstrapLauncherAutoUpdate() {
  const state = loadLauncherReleaseConfigState();
  if (state.configUrl) {
    void syncLauncherReleaseConfig(state.configUrl, { checkImmediately: true });
    return;
  }
  if (state.updateBaseUrl) {
    void checkForLauncherUpdates();
  }
}

function closeSplitWindows() {
  if (videoWindow && !videoWindow.isDestroyed()) {
    videoWindow.__eduititInternalClose = true;
    videoWindow.close();
  }
  if (dashboardWindow && !dashboardWindow.isDestroyed()) {
    dashboardWindow.__eduititInternalClose = true;
    dashboardWindow.close();
  }
  if (blackoutWindow && !blackoutWindow.isDestroyed()) blackoutWindow.close();
  BrowserWindow.getAllWindows()
    .filter((win) => win && win.__eduititSplitWindow === true && !win.isDestroyed())
    .forEach((win) => {
      try {
        win.__eduititInternalClose = true;
        win.close();
      } catch (_) {
        // no-op
      }
    });
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

function emergencyQuit() {
  if (appTerminating) return;
  appTerminating = true;
  watchdogCircuitOpen = true;
  stopWatchdog();
  lastLaunchPayload = null;
  splitCreateLock = false;
  isRestoringSplit = false;
  closeSplitWindows();
  if (app.isReady()) {
    app.quit();
    return;
  }
  app.exit(0);
}

function handleUserWindowClose() {
  if (appTerminating) return;
  emergencyQuit();
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

function findDisplayById(displayId) {
  if (displayId === null || displayId === undefined) return null;
  return screen.getAllDisplays().find((display) => display.id === displayId) || null;
}

function lockDisplayToCurrentPointer() {
  const cursorPoint = screen.getCursorScreenPoint();
  const display = screen.getDisplayNearestPoint(cursorPoint) || screen.getPrimaryDisplay();
  splitDisplayId = display.id;
  return display;
}

function cycleSplitDisplay() {
  const displays = screen
    .getAllDisplays()
    .slice()
    .sort((a, b) => (a.bounds.x - b.bounds.x) || (a.bounds.y - b.bounds.y));
  if (displays.length <= 1) return;

  const currentIndex = displays.findIndex((display) => display.id === splitDisplayId);
  const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % displays.length : 0;
  splitDisplayId = displays[nextIndex].id;
  relayoutSplitWindows();
}

function parseLauncherAction(rawUrl) {
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== `${PROTOCOL}:`) return null;

    const host = String(parsed.hostname || "").toLowerCase();
    if (host === "quit") {
      return { type: "quit" };
    }
    if (host === "action") {
      const name = String(parsed.searchParams.get("name") || "").toLowerCase();
      if (name) return { type: "action", name };
    }
    return null;
  } catch (_) {
    return null;
  }
}

function executeLauncherAction(action) {
  if (!action) return false;

  if (action.type === "quit") {
    emergencyQuit();
    return true;
  }
  if (action.type !== "action") return false;

  if (action.name === "ratio_up") {
    adjustSplitRatio(SPLIT_RATIO_STEP);
    return true;
  }
  if (action.name === "ratio_down") {
    adjustSplitRatio(-SPLIT_RATIO_STEP);
    return true;
  }
  if (action.name === "ratio_reset") {
    resetSplitRatio();
    return true;
  }
  if (action.name === "tv_mode") {
    enableTvModeSplit();
    return true;
  }
  if (action.name === "move_display") {
    cycleSplitDisplay();
    return true;
  }
  return false;
}

function installWindowGuards(win, payload, role) {
  if (!isSplitWindowAlive(win)) return;

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (String(url || "").startsWith(`${PROTOCOL}://`)) {
      handleLaunchUrl(url);
      return { action: "deny" };
    }
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, targetUrl) => {
    if (String(targetUrl || "").startsWith(`${PROTOCOL}://`)) {
      event.preventDefault();
      handleLaunchUrl(targetUrl);
      return;
    }
    if (isAllowedNavigation(targetUrl, payload, role)) return;
    event.preventDefault();
  });
  win.webContents.on("context-menu", (event) => {
    event.preventDefault();
  });

  win.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    const key = String(input.key || "").toLowerCase();
    const emergencyQuitHotkey = input.shift && input.alt && (input.control || input.meta) && key === "q";
    if (emergencyQuitHotkey) {
      event.preventDefault();
      emergencyQuit();
      return;
    }
    if (key === "b" && !input.control && !input.meta && !input.alt) {
      event.preventDefault();
      toggleBlackout();
      return;
    }
    const ratioAdjustHotkey = input.alt && (input.control || input.meta);
    if (ratioAdjustHotkey && key === "arrowright") {
      event.preventDefault();
      adjustSplitRatio(SPLIT_RATIO_STEP);
      return;
    }
    if (ratioAdjustHotkey && key === "arrowleft") {
      event.preventDefault();
      adjustSplitRatio(-SPLIT_RATIO_STEP);
      return;
    }
    if (ratioAdjustHotkey && key === "0") {
      event.preventDefault();
      resetSplitRatio();
      return;
    }
    if (key === "escape" && blackoutWindow && !blackoutWindow.isDestroyed()) {
      event.preventDefault();
      closeBlackoutWindow();
    }
  });
}

function getTargetDisplay() {
  const lockedDisplay = findDisplayById(splitDisplayId);
  if (lockedDisplay) return lockedDisplay;

  const cursorPoint = screen.getCursorScreenPoint();
  const fallback = screen.getDisplayNearestPoint(cursorPoint) || screen.getPrimaryDisplay();
  splitDisplayId = fallback.id;
  return fallback;
}

function getSplitArea(display) {
  const workArea = display.workArea || display.bounds;
  return {
    x: workArea.x,
    y: workArea.y,
    width: workArea.width,
    height: workArea.height,
  };
}

function pickLeftRatio(totalWidth) {
  return DEFAULT_LEFT_RATIO;
}

function clampSplitRatio(value) {
  return Math.min(SPLIT_RATIO_MAX, Math.max(SPLIT_RATIO_MIN, value));
}

function getEffectiveLeftRatio(totalWidth) {
  if (typeof splitRatioOverride === "number") {
    return clampSplitRatio(splitRatioOverride);
  }
  return pickLeftRatio(totalWidth);
}

function adjustSplitRatio(delta) {
  const currentWidth = Math.max(1, getSplitArea(getTargetDisplay()).width - SPLIT_GAP);
  const baseRatio =
    typeof splitRatioOverride === "number" ? splitRatioOverride : pickLeftRatio(currentWidth);
  splitRatioOverride = clampSplitRatio(baseRatio + delta);
  relayoutSplitWindows();
}

function resetSplitRatio() {
  splitRatioOverride = null;
  relayoutSplitWindows();
}

function enableTvModeSplit() {
  splitRatioOverride = clampSplitRatio(TV_MODE_LEFT_RATIO);
  relayoutSplitWindows();
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
    "<p style='line-height:1.6;color:#94a3b8;'>기본은 영상이 더 넓은 62:38으로 시작하고, 수업 화면의 <strong>TV 모드</strong> 버튼으로 50:50으로 바꿀 수 있습니다.</p>",
    "<p style='line-height:1.6;color:#94a3b8;'>이 창은 대기 화면입니다. 수업 시작 버튼으로 런처를 호출해 주세요.</p>",
    "</body></html>",
  ].join("");

  infoWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
  infoWindow.webContents.once("did-finish-load", () => {
    maybePromptForDownloadedUpdate();
  });
  infoWindow.on("closed", () => {
    infoWindow = null;
  });
}

function computeSplitBounds() {
  const display = getTargetDisplay();
  // Use workArea to avoid clipping under OS taskbar/docks.
  const area = getSplitArea(display);
  const totalWidth = Math.max(1, area.width - SPLIT_GAP);
  const leftRatio = getEffectiveLeftRatio(totalWidth);

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

function resetRecoveryWindow(now) {
  recoveryAttemptTimestamps = recoveryAttemptTimestamps.filter((ts) => now - ts < 60_000);
}

function canRecoverNow(now) {
  resetRecoveryWindow(now);
  if (now - lastRecoveryAt < WATCHDOG_RECOVER_COOLDOWN_MS) {
    return false;
  }
  if (recoveryAttemptTimestamps.length >= WATCHDOG_MAX_RECOVERY_PER_MIN) {
    return false;
  }
  return true;
}

function ensureSplitHealthy() {
  if (!lastLaunchPayload) return;
  if (splitCreateLock) return;
  if (watchdogCircuitOpen) return;

  const videoAlive = isSplitWindowAlive(videoWindow);
  const dashboardAlive = isSplitWindowAlive(dashboardWindow);
  if (!videoAlive || !dashboardAlive) {
    const now = Date.now();
    if (!canRecoverNow(now)) {
      resetRecoveryWindow(now);
      if (recoveryAttemptTimestamps.length >= WATCHDOG_MAX_RECOVERY_PER_MIN) {
        watchdogCircuitOpen = true;
        stopWatchdog();
        showErrorBox("자동 복구를 잠시 중지했습니다. 런처를 다시 실행해 주세요.");
      }
      return;
    }
    if (isRestoringSplit) return;
    lastRecoveryAt = now;
    recoveryAttemptTimestamps.push(now);
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
  isRestoringSplit = false;
}

function bindDisplayEventHandlers() {
  if (displayHandlersBound) return;
  if (!app.isReady()) return;

  displayHandlersBound = true;
  screen.on("display-metrics-changed", () => {
    relayoutSplitWindows();
  });

  screen.on("display-added", () => {
    relayoutSplitWindows();
  });

  screen.on("display-removed", () => {
    relayoutSplitWindows();
  });
}

function installYouTubeFocusMode(targetWindow, targetVideoUrl) {
  if (!targetWindow || targetWindow.isDestroyed()) return;
  const targetVideoId = extractYouTubeVideoId(targetVideoUrl);
  const replayUrl = buildYouTubeWatchUrl(targetVideoId, { autoplay: true }) || normalizeHttpUrl(targetVideoUrl) || "";

  const applyScript = () => {
    const js = `
      (() => {
        const targetVideoId = ${JSON.stringify(targetVideoId)};
        const replayUrl = ${JSON.stringify(replayUrl)};
        const replayCooldownMs = 2500;
        const href = window.location.href || "";
        if (!href.includes("youtube.com/watch")) return;

        function extractVideoId(rawUrl) {
          if (!rawUrl) return "";
          const matched = String(rawUrl).match(/(?:v=|youtu\\.be\\/|shorts\\/|embed\\/|live\\/)([A-Za-z0-9_-]{6,})/);
          return matched ? matched[1] : "";
        }

        function getPlayerApi() {
          return document.getElementById("movie_player") || null;
        }

        function isAdShowing() {
          const playerElement = document.querySelector(".html5-video-player") || document.getElementById("movie_player");
          if (playerElement && (playerElement.classList.contains("ad-showing") || playerElement.classList.contains("ad-interrupting"))) {
            return true;
          }
          return Boolean(
            document.querySelector(".ytp-ad-player-overlay, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .video-ads")
          );
        }

        function getActiveVideoId() {
          const playerApi = getPlayerApi();
          try {
            if (playerApi && typeof playerApi.getVideoData === "function") {
              const data = playerApi.getVideoData();
              if (data && data.video_id) {
                return String(data.video_id);
              }
            }
          } catch (_) {}

          try {
            if (playerApi && typeof playerApi.getVideoUrl === "function") {
              const playerUrl = playerApi.getVideoUrl();
              const playerVideoId = extractVideoId(playerUrl);
              if (playerVideoId) {
                return playerVideoId;
              }
            }
          } catch (_) {}

          return extractVideoId(window.location.href);
        }

        function getPageVideoId() {
          return extractVideoId(window.location.href);
        }

        function getPlayerState() {
          const playerApi = getPlayerApi();
          try {
            if (playerApi && typeof playerApi.getPlayerState === "function") {
              return playerApi.getPlayerState();
            }
          } catch (_) {}
          return null;
        }

        function replayMainVideo() {
          const playerApi = getPlayerApi();

          try {
            if (playerApi && typeof playerApi.seekTo === "function") {
              playerApi.seekTo(0, true);
            }
            if (playerApi && typeof playerApi.playVideo === "function") {
              playerApi.playVideo();
              return true;
            }
          } catch (_) {}

          const replayButton = document.querySelector(".ytp-replay-button");
          if (replayButton) {
            replayButton.click();
            return true;
          }

          const video = document.querySelector("video");
          if (video) {
            try {
              video.currentTime = 0;
              video.play().catch(() => {});
              return true;
            } catch (_) {}
          }

          if (replayUrl) {
            if (window.location.href !== replayUrl) {
              window.location.replace(replayUrl);
            } else {
              window.location.reload();
            }
            return true;
          }

          return false;
        }

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
              overflow: auto !important;
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
            .html5-video-player,
            .html5-video-container,
            video.video-stream.html5-main-video {
              width: 100% !important;
              height: 100% !important;
              max-height: calc(100vh - 4px) !important;
            }

            video.video-stream.html5-main-video {
              object-fit: contain !important;
            }
          \`;
          document.head.appendChild(style);
        }

        const sizeButton = document.querySelector(".ytp-size-button");
        if (sizeButton && sizeButton.getAttribute("aria-pressed") !== "true") {
          sizeButton.click();
        }

        if (!window.__eduititRepeatEnforcer) {
          const confirmedPlaybackThresholdSec = 3;
          const repeatState = window.__eduititRepeatState || {
            lastReplayAt: 0,
            lastRecoveryAt: 0,
            lastAdSeenAt: 0,
            sawTargetPlayback: false,
          };
          window.__eduititRepeatState = repeatState;
          window.__eduititRepeatEnforcer = window.setInterval(() => {
            const now = Date.now();
            const video = document.querySelector("video");
            if (video) {
              video.loop = false;
              video.removeAttribute("loop");
            }

            if (isAdShowing()) {
              repeatState.lastAdSeenAt = now;
              return;
            }

            if (repeatState.lastAdSeenAt && now - repeatState.lastAdSeenAt < 4000) {
              return;
            }

            const pageVideoId = getPageVideoId();
            const activeVideoId = getActiveVideoId();
            const playerState = getPlayerState();
            const confirmedTargetPlayback =
              !targetVideoId ||
              (pageVideoId === targetVideoId &&
                (!activeVideoId || activeVideoId === targetVideoId || activeVideoId === pageVideoId) &&
                Boolean(
                  video &&
                    !video.ended &&
                    video.currentTime >= confirmedPlaybackThresholdSec &&
                    (playerState === null || playerState === 1 || playerState === 2 || playerState === 3)
                ));

            if (confirmedTargetPlayback) {
              repeatState.sawTargetPlayback = true;
            }

            // Recover only when the watch page itself drifts away. Ads can expose
            // a temporary internal video id that should not trigger a reload.
            if (targetVideoId && repeatState.sawTargetPlayback && pageVideoId && pageVideoId !== targetVideoId) {
              if (replayUrl && now - repeatState.lastRecoveryAt >= replayCooldownMs) {
                repeatState.lastRecoveryAt = now;
                repeatState.sawTargetPlayback = false;
                window.location.replace(replayUrl);
              }
              return;
            }

            if (!confirmedTargetPlayback && targetVideoId && activeVideoId && activeVideoId !== targetVideoId) {
              return;
            }

            const hasEnded = playerState === 0 || Boolean(video && video.ended);
            if (!hasEnded) return;
            if (targetVideoId && !repeatState.sawTargetPlayback) return;
            if (now - repeatState.lastReplayAt < replayCooldownMs) return;

            repeatState.lastReplayAt = now;
            replayMainVideo();
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
  if (splitCreateLock) return;
  splitCreateLock = true;

  try {
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
  videoWindow.__eduititSplitWindow = true;
  applyTeachingWindowBehavior(videoWindow);
  installWindowGuards(videoWindow, payload, "video");
  videoWindow.loadURL(payload.youtubeUrl);
  installYouTubeFocusMode(videoWindow, payload.youtubeUrl);

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
  dashboardWindow.__eduititSplitWindow = true;
  applyTeachingWindowBehavior(dashboardWindow);
  installWindowGuards(dashboardWindow, payload, "dashboard");
  dashboardWindow.loadURL(payload.dashboardUrl);

  videoWindow.webContents.once("did-finish-load", () => {
    // Keep the player section visible at top after launch.
    videoWindow.webContents.executeJavaScript("window.scrollTo(0, 0)").catch(() => {});
  });

  const videoRef = videoWindow;
  const dashboardRef = dashboardWindow;

  videoRef.on("close", () => {
    if (!videoRef.__eduititInternalClose) {
      handleUserWindowClose();
    }
  });
  dashboardRef.on("close", () => {
    if (!dashboardRef.__eduititInternalClose) {
      handleUserWindowClose();
    }
  });

  videoRef.on("closed", () => {
    if (videoWindow === videoRef) {
      videoWindow = null;
    }
  });
  dashboardRef.on("closed", () => {
    if (dashboardWindow === dashboardRef) {
      dashboardWindow = null;
    }
  });

  startWatchdog();
  } finally {
    splitCreateLock = false;
  }
}

function handleLaunchUrl(rawUrl) {
  const launcherAction = parseLauncherAction(rawUrl);
  if (launcherAction && executeLauncherAction(launcherAction)) {
    return;
  }

  const parsed = parseLaunchUrl(rawUrl);
  if (parsed.error) {
    showErrorBox(`런처 payload를 읽지 못했습니다: ${parsed.error}`);
    return;
  }
  watchdogCircuitOpen = false;
  recoveryAttemptTimestamps = [];
  lastRecoveryAt = 0;
  lockDisplayToCurrentPointer();
  lastLaunchPayload = parsed;
  if (parsed.updateConfigUrl) {
    void syncLauncherReleaseConfig(parsed.updateConfigUrl, { checkImmediately: true });
  }
  createSplitWindows(parsed);
}

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", (_, argv) => {
    const run = () => {
      const launchUrl = extractLaunchUrlFromArgv(argv);
      if (launchUrl) {
        handleLaunchUrl(launchUrl);
        return;
      }
      if (dashboardWindow && !dashboardWindow.isDestroyed()) dashboardWindow.focus();
      else if (videoWindow && !videoWindow.isDestroyed()) videoWindow.focus();
      else createInfoWindow();
    };
    if (app.isReady()) {
      run();
      return;
    }
    app.whenReady().then(run);
  });

  if (process.defaultApp) {
    app.setAsDefaultProtocolClient(PROTOCOL, process.execPath, [path.resolve(process.argv[1])]);
  } else {
    app.setAsDefaultProtocolClient(PROTOCOL);
  }

  app.whenReady().then(() => {
    bindDisplayEventHandlers();
    bootstrapLauncherAutoUpdate();
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

app.on("before-quit", () => {
  stopWatchdog();
});
