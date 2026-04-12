const fs = require("fs");
const http = require("http");
const https = require("https");
const path = require("path");
const { app, BrowserWindow, dialog, screen, shell } = require("electron");
const { NsisUpdater } = require("electron-updater");

const PROTOCOL = "eduitit-launcher";
const MIN_VIDEO_WIDTH = 640;
const MIN_DASHBOARD_WIDTH = 560;
const DEFAULT_LEFT_RATIO = 0.62;
const TV_MODE_LEFT_RATIO = 0.5;
const SPLIT_GAP = 0;
const ALWAYS_ON_TOP_LEVEL = "screen-saver";
const VIDEO_CONTROL_BAR_HEIGHT = 96;
const MIN_VIDEO_CONTENT_HEIGHT = 260;
const WATCHDOG_INTERVAL_MS = 1400;
const WATCHDOG_RECOVER_COOLDOWN_MS = 4000;
const WATCHDOG_MAX_RECOVERY_PER_MIN = 3;
const SPLIT_RATIO_MIN = 0.45;
const SPLIT_RATIO_MAX = 0.72;
const SPLIT_RATIO_STEP = 0.03;
const AUTO_UPDATE_CACHE_FILENAME = "launcher-release-config.json";
const PENDING_LAUNCH_FILENAME = "launcher-pending-session.json";
const AUTO_UPDATE_CHECK_MIN_INTERVAL_MS = 30 * 60 * 1000;
const PENDING_LAUNCH_MAX_AGE_MS = 30 * 60 * 1000;

let videoWindow = null;
let videoControlWindow = null;
let dashboardWindow = null;
let infoWindow = null;
let blackoutWindow = null;
let videoCurtainWindow = null;
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
let requiredUpdateContext = null;
let infoWindowReady = false;
let pendingInfoWindowState = null;
let cachedLauncherReleaseConfig = {
  configUrl: "",
  updateBaseUrl: "",
  downloadUrl: "",
  bridgeNotice: "",
  bridgeVersion: "",
  latestVersion: "",
  minimumRequiredVersion: "",
  lastCheckedAt: 0,
};

function extractLaunchUrlFromArgv(argv) {
  if (!Array.isArray(argv)) return null;
  return argv.find((value) => isLauncherProtocolUrl(value)) || null;
}

function isLauncherProtocolUrl(rawUrl) {
  return typeof rawUrl === "string" && rawUrl.startsWith(`${PROTOCOL}:`);
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
    const videoUrl = normalizeHttpUrl(payload.videoUrl || payload.youtubeUrl);
    const dashboardUrl = normalizeHttpUrl(payload.dashboardUrl);
    const updateConfigUrl = normalizeHttpUrl(payload.updateConfigUrl);
    if (!videoUrl || !dashboardUrl) {
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
      videoUrl,
      youtubeUrl: videoUrl,
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

function getDefaultInfoWindowState() {
  return {
    badge: "런처 준비됨",
    title: "Eduitit Teacher Launcher",
    message: "브라우저에서 런처로 수업 시작을 누르면 왼쪽 영상과 오른쪽 대시보드가 함께 열립니다.",
    detail: "업데이트가 필요하면 이 창에서 진행 상태를 바로 보여 줍니다.",
    progress: null,
    tone: "idle",
  };
}

function normalizeInfoWindowState(rawState = {}) {
  const base = getDefaultInfoWindowState();
  const state = rawState && typeof rawState === "object" ? rawState : {};
  const normalizedProgress = Number.isFinite(Number(state.progress))
    ? Math.max(0, Math.min(100, Math.round(Number(state.progress))))
    : null;

  return {
    badge: normalizeShortText(state.badge || base.badge, 40) || base.badge,
    title: normalizeShortText(state.title || base.title, 120) || base.title,
    message: normalizeShortText(state.message || base.message, 240) || base.message,
    detail: normalizeShortText(state.detail || base.detail, 360) || "",
    progress: normalizedProgress,
    tone: ["idle", "info", "success", "warning", "error"].includes(state.tone) ? state.tone : base.tone,
  };
}

function buildInfoWindowHtml() {
  return `
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          :root {
            color-scheme: dark;
          }

          * {
            box-sizing: border-box;
          }

          body {
            margin: 0;
            min-height: 100vh;
            font-family: "Segoe UI", Arial, sans-serif;
            background:
              radial-gradient(circle at top left, rgba(16, 185, 129, 0.18), transparent 34%),
              linear-gradient(180deg, #111827 0%, #0f172a 100%);
            color: #e2e8f0;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
          }

          .panel {
            width: 100%;
            max-width: 560px;
            border-radius: 24px;
            padding: 28px;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(148, 163, 184, 0.14);
            box-shadow: 0 28px 60px rgba(15, 23, 42, 0.45);
          }

          .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: -0.01em;
            background: rgba(148, 163, 184, 0.16);
            color: #dbeafe;
          }

          body[data-tone="info"] .badge {
            background: rgba(59, 130, 246, 0.2);
            color: #bfdbfe;
          }

          body[data-tone="success"] .badge {
            background: rgba(16, 185, 129, 0.22);
            color: #bbf7d0;
          }

          body[data-tone="warning"] .badge {
            background: rgba(245, 158, 11, 0.2);
            color: #fde68a;
          }

          body[data-tone="error"] .badge {
            background: rgba(244, 63, 94, 0.18);
            color: #fecdd3;
          }

          h1 {
            margin: 16px 0 10px;
            font-size: 31px;
            line-height: 1.18;
            letter-spacing: -0.04em;
          }

          .message {
            margin: 0;
            font-size: 17px;
            font-weight: 700;
            line-height: 1.55;
            color: #f8fafc;
          }

          .detail {
            margin: 12px 0 0;
            font-size: 14px;
            line-height: 1.6;
            color: #cbd5e1;
          }

          .progress-wrap {
            margin-top: 22px;
            display: none;
          }

          .progress-wrap.visible {
            display: block;
          }

          .progress-track {
            width: 100%;
            height: 12px;
            border-radius: 999px;
            background: rgba(148, 163, 184, 0.16);
            overflow: hidden;
          }

          .progress-bar {
            width: 0%;
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #34d399 0%, #60a5fa 100%);
            transition: width 180ms ease;
          }

          .progress-text {
            margin-top: 10px;
            font-size: 13px;
            font-weight: 700;
            color: #bfdbfe;
          }
        </style>
      </head>
      <body data-tone="idle">
        <div class="panel">
          <div id="statusBadge" class="badge">런처 준비됨</div>
          <h1 id="statusTitle">Eduitit Teacher Launcher</h1>
          <p id="statusMessage" class="message">브라우저에서 런처로 수업 시작을 누르면 왼쪽 영상과 오른쪽 대시보드가 함께 열립니다.</p>
          <p id="statusDetail" class="detail">업데이트가 필요하면 이 창에서 진행 상태를 바로 보여 줍니다.</p>
          <div id="progressWrap" class="progress-wrap">
            <div class="progress-track"><div id="progressBar" class="progress-bar"></div></div>
            <div id="progressText" class="progress-text"></div>
          </div>
        </div>
        <script>
          window.__applyLauncherStatus = (nextState = {}) => {
            const state = nextState && typeof nextState === "object" ? nextState : {};
            document.body.dataset.tone = state.tone || "idle";
            document.getElementById("statusBadge").textContent = state.badge || "";
            document.getElementById("statusTitle").textContent = state.title || "";
            document.getElementById("statusMessage").textContent = state.message || "";
            document.getElementById("statusDetail").textContent = state.detail || "";

            const progressWrap = document.getElementById("progressWrap");
            const progressBar = document.getElementById("progressBar");
            const progressText = document.getElementById("progressText");
            if (Number.isFinite(state.progress)) {
              progressWrap.classList.add("visible");
              progressBar.style.width = state.progress + "%";
              progressText.textContent = "진행률 " + state.progress + "%";
            } else {
              progressWrap.classList.remove("visible");
              progressBar.style.width = "0%";
              progressText.textContent = "";
            }
          };
        </script>
      </body>
    </html>
  `;
}

function applyInfoWindowState(state) {
  if (!infoWindow || infoWindow.isDestroyed() || !infoWindowReady) return;
  const payload = JSON.stringify(normalizeInfoWindowState(state));
  infoWindow.webContents
    .executeJavaScript(`window.__applyLauncherStatus(${payload});`, true)
    .catch((err) => {
      console.error("[launcher-ui] failed to apply info window state:", err);
    });
}

function setInfoWindowState(rawState, { reveal = true, focus = false } = {}) {
  pendingInfoWindowState = normalizeInfoWindowState(rawState);
  createInfoWindow({ focus: reveal || focus });
  if (reveal && infoWindow && !infoWindow.isDestroyed()) {
    if (!infoWindow.isVisible()) infoWindow.show();
    if (focus) infoWindow.focus();
  }
  if (infoWindowReady) {
    applyInfoWindowState(pendingInfoWindowState);
  }
}

function setUpdateWindowState({ badge, title, message, detail, progress = null, tone = "info" }) {
  setInfoWindowState(
    {
      badge,
      title,
      message,
      detail,
      progress,
      tone,
    },
    { reveal: true, focus: false }
  );
}

function normalizeVersionString(value) {
  if (typeof value !== "string") return "";
  const cleaned = value.trim();
  return /^\d+(?:\.\d+){0,3}$/.test(cleaned) ? cleaned : "";
}

function compareVersionStrings(left, right) {
  const leftParts = normalizeVersionString(left)
    .split(".")
    .filter(Boolean)
    .map((part) => Number.parseInt(part, 10));
  const rightParts = normalizeVersionString(right)
    .split(".")
    .filter(Boolean)
    .map((part) => Number.parseInt(part, 10));
  const maxLength = Math.max(leftParts.length, rightParts.length);

  for (let index = 0; index < maxLength; index += 1) {
    const leftValue = Number.isFinite(leftParts[index]) ? leftParts[index] : 0;
    const rightValue = Number.isFinite(rightParts[index]) ? rightParts[index] : 0;
    if (leftValue > rightValue) return 1;
    if (leftValue < rightValue) return -1;
  }

  return 0;
}

function isVersionAtLeast(currentVersion, minimumVersion) {
  const normalizedMinimum = normalizeVersionString(minimumVersion);
  if (!normalizedMinimum) return true;
  const normalizedCurrent = normalizeVersionString(currentVersion);
  if (!normalizedCurrent) return false;
  return compareVersionStrings(normalizedCurrent, normalizedMinimum) >= 0;
}

function getCurrentLauncherVersion() {
  return normalizeVersionString(app.getVersion() || "") || "0.0.0";
}

function normalizeLaunchPayload(rawPayload) {
  const source = rawPayload && typeof rawPayload === "object" ? rawPayload : {};
  const videoUrl = normalizeHttpUrl(source.videoUrl || source.youtubeUrl);
  const dashboardUrl = normalizeHttpUrl(source.dashboardUrl);

  if (!videoUrl || !dashboardUrl) {
    return null;
  }

  return {
    classId: source.classId,
    title: normalizeShortText(source.title || "Eduitit ArtClass", 120) || "Eduitit ArtClass",
    videoUrl,
    youtubeUrl: videoUrl,
    dashboardUrl,
    updateConfigUrl: normalizeHttpUrl(source.updateConfigUrl) || "",
  };
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
    latestVersion: normalizeVersionString(source.latestVersion) || normalizeVersionString(previous.latestVersion) || "",
    minimumRequiredVersion:
      normalizeVersionString(source.minimumRequiredVersion) ||
      normalizeVersionString(previous.minimumRequiredVersion) ||
      "",
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

function getPendingLaunchStatePath() {
  try {
    return path.join(app.getPath("userData"), PENDING_LAUNCH_FILENAME);
  } catch (_) {
    return "";
  }
}

function loadPendingLaunchState() {
  const statePath = getPendingLaunchStatePath();
  if (!statePath || !fs.existsSync(statePath)) {
    return null;
  }

  try {
    const raw = JSON.parse(fs.readFileSync(statePath, "utf8"));
    const savedAt = normalizeTimestamp(raw.savedAt);
    if (!savedAt || Date.now() - savedAt > PENDING_LAUNCH_MAX_AGE_MS) {
      fs.unlinkSync(statePath);
      return null;
    }

    const payload = normalizeLaunchPayload(raw.payload);
    if (!payload) {
      fs.unlinkSync(statePath);
      return null;
    }

    return {
      payload,
      requiredVersion: normalizeVersionString(raw.requiredVersion),
      savedAt,
    };
  } catch (err) {
    console.error("[launcher-update] failed to read pending launch state:", err);
    return null;
  }
}

function savePendingLaunchState(payload, { requiredVersion = "" } = {}) {
  const normalizedPayload = normalizeLaunchPayload(payload);
  if (!normalizedPayload) return null;

  const statePath = getPendingLaunchStatePath();
  if (!statePath) return null;

  const nextState = {
    payload: normalizedPayload,
    requiredVersion: normalizeVersionString(requiredVersion),
    savedAt: Date.now(),
  };

  try {
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.writeFileSync(statePath, JSON.stringify(nextState, null, 2), "utf8");
    return nextState;
  } catch (err) {
    console.error("[launcher-update] failed to persist pending launch state:", err);
    return null;
  }
}

function clearPendingLaunchState() {
  const statePath = getPendingLaunchStatePath();
  if (!statePath || !fs.existsSync(statePath)) return;

  try {
    fs.unlinkSync(statePath);
  } catch (err) {
    console.error("[launcher-update] failed to clear pending launch state:", err);
  }
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
          "User-Agent": `EduititTeacherLauncher/${app.getVersion() || "0.2.10"}`,
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
    (blackoutWindow && !blackoutWindow.isDestroyed()) ||
    (videoCurtainWindow && !videoCurtainWindow.isDestroyed())
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

async function tryUpdateFromMissingPayload() {
  if (!app.isPackaged) {
    return false;
  }

  let state = loadLauncherReleaseConfigState();
  if (!state.configUrl && !state.updateBaseUrl && !state.downloadUrl) {
    return false;
  }

  try {
    setUpdateWindowState({
      badge: "업데이트 확인 중",
      title: "런처를 최신 상태로 맞추는 중입니다.",
      message: "잠시만 기다려 주세요.",
      detail: "오래된 런처가 감지되어 새 버전을 확인하고 있습니다.",
    });
    if (state.configUrl) {
      state = await syncLauncherReleaseConfig(state.configUrl, { checkImmediately: true, force: true });
    } else {
      const updateResult = await checkForLauncherUpdates({ force: true });
      if (updateResult && updateResult.downloadPromise) {
        await updateResult.downloadPromise.catch((err) => {
          console.error("[launcher-update] missing_payload download failed:", err);
          return null;
        });
      }
      state = loadLauncherReleaseConfigState();
    }
  } catch (err) {
    console.error("[launcher-update] missing_payload recovery failed:", err);
    state = loadLauncherReleaseConfigState();
  }

  const requiredVersion = normalizeVersionString(
    state.minimumRequiredVersion || state.latestVersion || state.bridgeVersion
  );
  if (!requiredVersion || isVersionAtLeast(getCurrentLauncherVersion(), requiredVersion)) {
    return false;
  }

  if (downloadedUpdateInfo && isVersionAtLeast(downloadedUpdateInfo.version, requiredVersion)) {
    setUpdateWindowState({
      badge: "업데이트 준비 완료",
      title: "새 버전 설치를 시작합니다.",
      message: "잠시만 기다려 주세요.",
      detail: "업데이트 후 같은 수업을 다시 열 수 있게 준비하고 있습니다.",
      progress: 100,
      tone: "success",
    });
    await promptForDownloadedUpdate(downloadedUpdateInfo);
    return true;
  }

  const fallbackDownloadUrl = normalizeHttpUrl(state.downloadUrl);
  if (fallbackDownloadUrl) {
    shell.openExternal(fallbackDownloadUrl).catch((err) => {
      console.error("[launcher-update] failed to open fallback download url from missing_payload:", err);
    });
  }

  setUpdateWindowState({
    badge: "수동 설치 필요",
    title: "설치 파일을 열었습니다.",
    message: "새 버전을 설치한 뒤 다시 눌러 주세요.",
    detail: "자동 업데이트를 바로 적용하지 못해 설치 파일을 먼저 열었습니다.",
    tone: "warning",
  });
  showErrorBox("현재 런처가 오래되어 이 버튼을 처리하지 못합니다. 업데이트 설치 화면을 열었습니다. 업데이트 후 다시 시도해 주세요.");
  return true;
}

function installRequiredUpdateNow() {
  if (!requiredUpdateContext) return false;

  const updater = ensureAutoUpdater();
  if (!updater) return false;

  const pendingState = savePendingLaunchState(requiredUpdateContext.payload, {
    requiredVersion: requiredUpdateContext.requiredVersion,
  });
  if (!pendingState) {
    showErrorBox("업데이트 후 다시 열 수업 정보를 저장하지 못했습니다. 다시 시도해 주세요.");
    return false;
  }

  try {
    setUpdateWindowState({
      badge: "재시작 중",
      title: "업데이트 설치를 시작합니다.",
      message: "런처가 잠시 닫혔다가 다시 열립니다.",
      detail: "설치가 끝나면 같은 수업을 자동으로 다시 엽니다.",
      progress: 100,
      tone: "success",
    });
    updater.quitAndInstall();
    return true;
  } catch (err) {
    console.error("[launcher-update] forced install failed:", err);
    showErrorBox("런처 업데이트를 자동으로 설치하지 못했습니다. 설치 파일을 다시 열어 주세요.");
    return false;
  }
}

function ensureAutoUpdater() {
  if (!app.isPackaged) return null;
  if (autoUpdater) return autoUpdater;

  autoUpdater = new NsisUpdater();
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.logger = console;
  autoUpdater.on("checking-for-update", () => {
    setUpdateWindowState({
      badge: "업데이트 확인 중",
      title: "런처를 최신 상태로 확인하고 있습니다.",
      message: "잠시만 기다려 주세요.",
      detail: "새 버전이 있으면 자동으로 내려받고, 끝나면 같은 수업을 다시 엽니다.",
    });
  });
  autoUpdater.on("update-available", (info) => {
    const versionLabel = normalizeShortText(info && info.version, 40) || "새 버전";
    setUpdateWindowState({
      badge: "업데이트 다운로드 중",
      title: `${versionLabel}을 내려받는 중입니다.`,
      message: "조금만 기다려 주세요.",
      detail: "다운로드가 끝나면 자동으로 설치 준비를 이어갑니다.",
      progress: 0,
    });
  });
  autoUpdater.on("download-progress", (progressInfo) => {
    const percent = Number(progressInfo && progressInfo.percent);
    setUpdateWindowState({
      badge: "업데이트 다운로드 중",
      title: "새 버전을 내려받고 있습니다.",
      message: "런처를 닫지 말고 잠시만 기다려 주세요.",
      detail: "다운로드가 끝나면 자동으로 설치 준비를 이어갑니다.",
      progress: Number.isFinite(percent) ? percent : null,
    });
  });
  autoUpdater.on("update-not-available", () => {
    if (requiredUpdateContext) return;
    pendingInfoWindowState = getDefaultInfoWindowState();
    applyInfoWindowState(pendingInfoWindowState);
  });
  autoUpdater.on("error", (err) => {
    console.error("[launcher-update] updater error:", err);
    setUpdateWindowState({
      badge: "업데이트 확인 실패",
      title: "업데이트 상태를 바로 확인하지 못했습니다.",
      message: "인터넷 연결을 확인한 뒤 다시 시도해 주세요.",
      detail: "잠시 후 다시 실행하거나 설치 파일로 업데이트할 수 있습니다.",
      tone: "warning",
    });
  });
  autoUpdater.on("update-downloaded", (info) => {
    downloadedUpdateInfo = info || { version: "" };
    setUpdateWindowState({
      badge: "업데이트 준비 완료",
      title: "새 버전 다운로드가 끝났습니다.",
      message: requiredUpdateContext
        ? "잠시 뒤 자동으로 다시 시작합니다."
        : "재시작하면 바로 업데이트됩니다.",
      detail: requiredUpdateContext
        ? "업데이트 후 같은 수업을 다시 엽니다."
        : "지금 재시작하거나 다음 종료 때 자동으로 설치할 수 있습니다.",
      progress: 100,
      tone: "success",
    });
    if (
      requiredUpdateContext &&
      isVersionAtLeast(downloadedUpdateInfo.version, requiredUpdateContext.requiredVersion)
    ) {
      installRequiredUpdateNow();
      return;
    }
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
      latestVersion: payload.latestVersion,
      minimumRequiredVersion: payload.minimumRequiredVersion,
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

async function ensureLauncherVersionReadyForLaunch(payload) {
  if (!app.isPackaged) {
    return true;
  }

  const state = payload.updateConfigUrl
    ? await syncLauncherReleaseConfig(payload.updateConfigUrl, { force: true })
    : loadLauncherReleaseConfigState();
  const requiredVersion = normalizeVersionString(
    state.minimumRequiredVersion || state.latestVersion || state.bridgeVersion
  );

  if (!requiredVersion || isVersionAtLeast(getCurrentLauncherVersion(), requiredVersion)) {
    requiredUpdateContext = null;
    return true;
  }

  requiredUpdateContext = {
    payload,
    requiredVersion,
    downloadUrl: state.downloadUrl,
  };
  savePendingLaunchState(payload, { requiredVersion });
  setUpdateWindowState({
    badge: "업데이트 필요",
    title: "런처를 먼저 업데이트합니다.",
    message: "잠시만 기다려 주세요.",
    detail: "최신 버전 설치가 끝나면 같은 수업을 자동으로 다시 엽니다.",
    tone: "warning",
  });

  if (
    downloadedUpdateInfo &&
    isVersionAtLeast(downloadedUpdateInfo.version, requiredVersion) &&
    installRequiredUpdateNow()
  ) {
    return false;
  }

  try {
    const updateResult = await checkForLauncherUpdates({ force: true });
    if (updateResult && updateResult.downloadPromise) {
      await updateResult.downloadPromise.catch((err) => {
        console.error("[launcher-update] forced download failed:", err);
        return null;
      });
    }
  } catch (err) {
    console.error("[launcher-update] forced update check failed:", err);
  }

  if (
    downloadedUpdateInfo &&
    isVersionAtLeast(downloadedUpdateInfo.version, requiredVersion) &&
    installRequiredUpdateNow()
  ) {
    return false;
  }

  const fallbackDownloadUrl = normalizeHttpUrl(state.downloadUrl);
  if (fallbackDownloadUrl) {
    shell.openExternal(fallbackDownloadUrl).catch((err) => {
      console.error("[launcher-update] failed to open fallback download url:", err);
    });
  }
  showErrorBox("런처를 최신 버전으로 업데이트한 뒤 자동으로 이 수업을 다시 엽니다. 설치 화면이 열리면 업데이트를 진행해 주세요.");
  return false;
}

async function resumePendingLaunchIfNeeded() {
  const pendingState = loadPendingLaunchState();
  if (!pendingState) {
    return false;
  }

  await launchSplitSession(pendingState.payload);
  return true;
}

function closeSplitWindows() {
  if (videoWindow && !videoWindow.isDestroyed()) {
    videoWindow.__eduititInternalClose = true;
    videoWindow.close();
  }
  if (videoControlWindow && !videoControlWindow.isDestroyed()) {
    videoControlWindow.__eduititInternalClose = true;
    videoControlWindow.close();
  }
  if (dashboardWindow && !dashboardWindow.isDestroyed()) {
    dashboardWindow.__eduititInternalClose = true;
    dashboardWindow.close();
  }
  if (blackoutWindow && !blackoutWindow.isDestroyed()) blackoutWindow.close();
  if (videoCurtainWindow && !videoCurtainWindow.isDestroyed()) videoCurtainWindow.close();
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
  videoControlWindow = null;
  dashboardWindow = null;
  blackoutWindow = null;
  videoCurtainWindow = null;
}

function closeBlackoutWindow() {
  if (blackoutWindow && !blackoutWindow.isDestroyed()) {
    blackoutWindow.close();
  }
  blackoutWindow = null;
}

function getVideoCurtainBounds() {
  const bounds = computeSplitBounds();
  return {
    x: bounds.x,
    y: bounds.y,
    width: bounds.leftWidth,
    height: bounds.videoHeight,
  };
}

function syncVideoCurtainBounds() {
  if (!videoCurtainWindow || videoCurtainWindow.isDestroyed()) return;
  videoCurtainWindow.setBounds(getVideoCurtainBounds());
}

function closeVideoCurtainWindow() {
  if (videoCurtainWindow && !videoCurtainWindow.isDestroyed()) {
    videoCurtainWindow.close();
  }
  videoCurtainWindow = null;
}

function createVideoCurtainWindow() {
  if (videoCurtainWindow && !videoCurtainWindow.isDestroyed()) {
    syncVideoCurtainBounds();
    videoCurtainWindow.showInactive();
    return;
  }

  const bounds = getVideoCurtainBounds();
  videoCurtainWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    frame: false,
    backgroundColor: "#050816",
    autoHideMenuBar: true,
    skipTaskbar: true,
    alwaysOnTop: true,
    focusable: false,
    fullscreenable: false,
    transparent: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  videoCurtainWindow.setAlwaysOnTop(true, ALWAYS_ON_TOP_LEVEL);
  videoCurtainWindow.setIgnoreMouseEvents(true);
  videoCurtainWindow.setMenuBarVisibility(false);
  videoCurtainWindow.loadURL(
    "data:text/html;charset=utf-8," +
      encodeURIComponent(`
        <html>
          <body style="margin:0;background:#050816;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;display:flex;align-items:center;justify-content:center;">
            <div style="text-align:center;padding:32px;">
              <div style="font-size:20px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#86efac;">EDUITIT</div>
              <div style="margin-top:14px;font-size:34px;font-weight:900;">영상이 가려져 있습니다</div>
              <div style="margin-top:14px;font-size:16px;font-weight:700;color:#cbd5e1;">왼쪽 아래 제어 바에서 다시 재생하거나 수업을 종료해 주세요.</div>
            </div>
          </body>
        </html>
      `)
  );
  videoCurtainWindow.on("closed", () => {
    videoCurtainWindow = null;
  });
}

function toggleVideoCurtain() {
  if (videoCurtainWindow && !videoCurtainWindow.isDestroyed()) {
    closeVideoCurtainWindow();
    return;
  }
  createVideoCurtainWindow();
}

function replayCurrentVideo() {
  if (!lastLaunchPayload) return false;

  closeVideoCurtainWindow();
  const expectedUrl = getPayloadVideoUrl(lastLaunchPayload);
  if (!expectedUrl) return false;

  if (!isSplitWindowAlive(videoWindow) || !isSplitWindowAlive(videoControlWindow) || !isSplitWindowAlive(dashboardWindow)) {
    createSplitWindows(lastLaunchPayload);
    return true;
  }

  videoWindow.webContents.loadURL(expectedUrl).catch((err) => {
    console.error("[launcher-video] failed to replay original video url:", err);
  });
  enforceWindowVisible(videoWindow);
  enforceWindowVisible(videoControlWindow);
  enforceWindowVisible(dashboardWindow);
  return true;
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

function getPayloadVideoUrl(payload) {
  return normalizeHttpUrl(payload && (payload.videoUrl || payload.youtubeUrl));
}

function normalizeHostname(hostname) {
  return String(hostname || "").toLowerCase().replace(/^www\./, "");
}

function isAllowedVideoHost(hostname) {
  const host = normalizeHostname(hostname);
  return (
    host === "youtube.com" ||
    host.endsWith(".youtube.com") ||
    host === "youtu.be" ||
    host.endsWith(".googlevideo.com") ||
    host.endsWith(".ytimg.com") ||
    host.endsWith(".ggpht.com")
  );
}

function getRegistrableHost(hostname) {
  const host = normalizeHostname(hostname);
  if (!host || host.includes(":")) return host;
  const parts = host.split(".").filter(Boolean);
  if (parts.length <= 2) return host;
  return parts.slice(-2).join(".");
}

function extractSupplementalVideoHosts(rawUrl) {
  const hosts = new Set();
  try {
    const parsed = new URL(rawUrl);
    for (const value of parsed.searchParams.values()) {
      String(value || "")
        .split(/[;,]+/)
        .map((token) => token.trim())
        .filter(Boolean)
        .forEach((token) => {
          const normalizedToken = token.replace(/^https?:\/\//i, "").replace(/\/.*$/, "");
          if (!/[.]/.test(normalizedToken)) return;
          hosts.add(normalizeHostname(normalizedToken));
        });
    }
  } catch (_) {
    return hosts;
  }
  return hosts;
}

function isAllowedExternalVideoHost(hostname, payload) {
  const expectedUrl = getPayloadVideoUrl(payload);
  if (!expectedUrl) return false;

  const targetHost = normalizeHostname(hostname);
  if (!targetHost) return false;

  try {
    const expectedHost = normalizeHostname(new URL(expectedUrl).hostname);
    if (targetHost === expectedHost) return true;

    const expectedSite = getRegistrableHost(expectedHost);
    if (expectedSite && (targetHost === expectedSite || targetHost.endsWith(`.${expectedSite}`))) {
      return true;
    }

    for (const extraHost of extractSupplementalVideoHosts(expectedUrl)) {
      if (targetHost === extraHost || targetHost.endsWith(`.${extraHost}`)) {
        return true;
      }
    }
  } catch (_) {
    return false;
  }

  return false;
}

function isUnexpectedVideoNavigation(targetUrl, payload) {
  const expectedVideoId = extractYouTubeVideoId(getPayloadVideoUrl(payload));
  if (!expectedVideoId) return false;

  const navigatedVideoId = extractYouTubeVideoId(targetUrl);
  return Boolean(navigatedVideoId && navigatedVideoId !== expectedVideoId);
}

function restoreOriginalVideoWindowUrl(win, payload) {
  if (!isSplitWindowAlive(win)) return;
  const expectedUrl = getPayloadVideoUrl(payload);
  if (!expectedUrl) return;

  const currentUrl = normalizeHttpUrl(win.webContents.getURL());
  if (currentUrl === expectedUrl) return;

  win.webContents.loadURL(expectedUrl).catch((err) => {
    console.error("[launcher-video] failed to restore original video url:", err);
  });
}

function isAllowedNavigation(targetUrl, payload, role) {
  try {
    const parsed = new URL(targetUrl);
    if (role === "video") {
      if (isUnexpectedVideoNavigation(targetUrl, payload)) {
        return false;
      }
      const expectedUrl = getPayloadVideoUrl(payload);
      if (extractYouTubeVideoId(expectedUrl)) {
        return isAllowedVideoHost(parsed.hostname);
      }
      return isAllowedExternalVideoHost(parsed.hostname, payload);
    }
    if (role === "control") {
      return parsed.protocol === "data:";
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

    const target = String(parsed.hostname || parsed.pathname || "")
      .replace(/^\/+/, "")
      .toLowerCase();

    if (target === "quit") {
      return { type: "quit" };
    }
    if (target === "action") {
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
  if (action.name === "replay_video") {
    return replayCurrentVideo();
  }
  if (action.name === "toggle_video_curtain") {
    toggleVideoCurtain();
    return true;
  }
  return false;
}

function installWindowGuards(win, payload, role) {
  if (!isSplitWindowAlive(win)) return;

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isLauncherProtocolUrl(url)) {
      handleLaunchUrl(url);
      return { action: "deny" };
    }
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, targetUrl) => {
    if (isLauncherProtocolUrl(targetUrl)) {
      event.preventDefault();
      handleLaunchUrl(targetUrl);
      return;
    }
    if (role === "video" && isUnexpectedVideoNavigation(targetUrl, payload)) {
      event.preventDefault();
      restoreOriginalVideoWindowUrl(win, payload);
      return;
    }
    if (isAllowedNavigation(targetUrl, payload, role)) return;
    event.preventDefault();
  });
  if (role === "video") {
    const syncVideoNavigation = (_, targetUrl) => {
      if (!isUnexpectedVideoNavigation(targetUrl, payload)) return;
      restoreOriginalVideoWindowUrl(win, payload);
    };
    win.webContents.on("did-navigate", syncVideoNavigation);
    win.webContents.on("did-navigate-in-page", syncVideoNavigation);
  }
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

function createInfoWindow({ focus = true } = {}) {
  if (infoWindow && !infoWindow.isDestroyed()) {
    if (focus) infoWindow.focus();
    return;
  }

  infoWindowReady = false;
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
  infoWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(buildInfoWindowHtml())}`);
  infoWindow.webContents.once("did-finish-load", () => {
    infoWindowReady = true;
    applyInfoWindowState(pendingInfoWindowState || getDefaultInfoWindowState());
    maybePromptForDownloadedUpdate();
  });
  infoWindow.on("closed", () => {
    infoWindow = null;
    infoWindowReady = false;
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

  const controlHeight = Math.max(
    72,
    Math.min(VIDEO_CONTROL_BAR_HEIGHT, Math.max(72, area.height - MIN_VIDEO_CONTENT_HEIGHT))
  );
  const videoHeight = Math.max(MIN_VIDEO_CONTENT_HEIGHT, area.height - controlHeight);
  const videoControlY = area.y + videoHeight;

  return {
    x: area.x,
    y: area.y,
    width: area.width,
    height: area.height,
    leftWidth,
    videoHeight,
    videoControlY,
    videoControlHeight: controlHeight,
    rightX: area.x + leftWidth + SPLIT_GAP,
    rightWidth,
  };
}

function buildVideoControlWindowHtml() {
  return `
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          :root {
            color-scheme: dark;
          }

          * {
            box-sizing: border-box;
          }

          body {
            margin: 0;
            height: 100vh;
            background:
              radial-gradient(circle at top left, rgba(16, 185, 129, 0.18), transparent 34%),
              linear-gradient(180deg, #131d34 0%, #0f172a 100%);
            color: #e2e8f0;
            font-family: "Segoe UI", Arial, sans-serif;
            overflow: hidden;
          }

          .shell {
            height: 100%;
            padding: 10px 12px;
            display: grid;
            grid-template-rows: 44px 1fr;
            gap: 8px;
          }

          .primary-actions {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
          }

          .primary-action {
            border: 0;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            color: #ffffff;
            font-size: 19px;
            font-weight: 900;
            letter-spacing: -0.02em;
            box-shadow: 0 12px 24px rgba(15, 23, 42, 0.24);
          }

          .primary-action.replay {
            background: linear-gradient(135deg, #10b981, #34d399);
          }

          .primary-action.quit {
            background: linear-gradient(135deg, #f43f5e, #fb7185);
          }

          .secondary-default,
          .secondary-expanded {
            min-height: 0;
          }

          .secondary-default {
            display: flex;
            align-items: center;
            gap: 10px;
          }

          .secondary-default.hidden,
          .secondary-expanded.hidden {
            display: none;
          }

          .toggle-button {
            border: 0;
            border-radius: 999px;
            padding: 7px 12px;
            background: rgba(148, 163, 184, 0.18);
            color: #f8fafc;
            font-size: 12px;
            font-weight: 800;
            cursor: pointer;
            white-space: nowrap;
          }

          .hint {
            min-width: 0;
            color: #cbd5e1;
            font-size: 11px;
            font-weight: 700;
            line-height: 1.3;
            white-space: normal;
            overflow: visible;
          }

          .secondary-expanded {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 8px;
          }

          .secondary-chip {
            border-radius: 11px;
            border: 1px solid rgba(148, 163, 184, 0.18);
            background: rgba(255, 255, 255, 0.07);
            color: #f8fafc;
            text-decoration: none;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 11px;
            font-weight: 800;
            line-height: 1.1;
            padding: 6px 8px;
          }

          .secondary-chip.back {
            background: rgba(99, 102, 241, 0.22);
            border-color: rgba(129, 140, 248, 0.34);
          }
        </style>
      </head>
      <body>
        <div class="shell">
          <div class="primary-actions">
            <a class="primary-action replay" href="${PROTOCOL}://action?name=replay_video">영상 다시 재생</a>
            <a class="primary-action quit" href="${PROTOCOL}://quit">수업 종료</a>
          </div>
          <div id="secondaryDefault" class="secondary-default">
            <button id="toggleAdvanced" class="toggle-button" type="button">세부 조정</button>
            <div class="hint">영상에서 오른쪽 클릭 후 연속 재생을 누르면 영상이 자동 반복됩니다.</div>
          </div>
          <div id="secondaryExpanded" class="secondary-expanded hidden">
            <button id="collapseAdvanced" class="secondary-chip back" type="button">기본 화면</button>
            <a class="secondary-chip" href="${PROTOCOL}://action?name=tv_mode">TV 모드</a>
            <a class="secondary-chip" href="${PROTOCOL}://action?name=ratio_reset">기본 비율</a>
            <a class="secondary-chip" href="${PROTOCOL}://action?name=ratio_up">영상 더 크게</a>
            <a class="secondary-chip" href="${PROTOCOL}://action?name=move_display">화면 위치 변경</a>
          </div>
        </div>
        <script>
          (() => {
            const defaultRow = document.getElementById("secondaryDefault");
            const expandedRow = document.getElementById("secondaryExpanded");
            const toggleAdvanced = document.getElementById("toggleAdvanced");
            const collapseAdvanced = document.getElementById("collapseAdvanced");

            function setExpanded(next) {
              const expanded = !!next;
              defaultRow.classList.toggle("hidden", expanded);
              expandedRow.classList.toggle("hidden", !expanded);
            }

            toggleAdvanced.addEventListener("click", () => setExpanded(true));
            collapseAdvanced.addEventListener("click", () => setExpanded(false));
            setExpanded(false);
          })();
        </script>
      </body>
    </html>
  `;
}

function createVideoControlWindow(payload) {
  const bounds = computeSplitBounds();
  const controlBounds = {
    x: bounds.x,
    y: bounds.videoControlY,
    width: bounds.leftWidth,
    height: bounds.videoControlHeight,
  };

  videoControlWindow = new BrowserWindow({
    x: controlBounds.x,
    y: controlBounds.y,
    width: controlBounds.width,
    height: controlBounds.height,
    frame: false,
    backgroundColor: "#0f172a",
    autoHideMenuBar: true,
    skipTaskbar: true,
    alwaysOnTop: true,
    title: `${payload.title} - Controls`,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  videoControlWindow.__eduititSplitWindow = true;
  applyTeachingWindowBehavior(videoControlWindow);
  installWindowGuards(videoControlWindow, payload, "control");
  videoControlWindow.loadURL(
    "data:text/html;charset=utf-8," + encodeURIComponent(buildVideoControlWindowHtml())
  );
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
  if (!videoControlWindow || videoControlWindow.isDestroyed()) return;
  if (!dashboardWindow || dashboardWindow.isDestroyed()) return;

  const bounds = computeSplitBounds();
  videoWindow.setBounds({
    x: bounds.x,
    y: bounds.y,
    width: bounds.leftWidth,
    height: bounds.videoHeight,
  });
  videoControlWindow.setBounds({
    x: bounds.x,
    y: bounds.videoControlY,
    width: bounds.leftWidth,
    height: bounds.videoControlHeight,
  });
  dashboardWindow.setBounds({
    x: bounds.rightX,
    y: bounds.y,
    width: bounds.rightWidth,
    height: bounds.height,
  });
  syncBlackoutBounds();
  syncVideoCurtainBounds();
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
  const videoControlAlive = isSplitWindowAlive(videoControlWindow);
  const dashboardAlive = isSplitWindowAlive(dashboardWindow);
  if (!videoAlive || !videoControlAlive || !dashboardAlive) {
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
  enforceWindowVisible(videoControlWindow);
  enforceWindowVisible(dashboardWindow);
  applyTeachingWindowBehavior(videoWindow);
  applyTeachingWindowBehavior(videoControlWindow);
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

        const currentPageVideoId = getPageVideoId();
        if (targetVideoId && currentPageVideoId && currentPageVideoId !== targetVideoId && replayUrl) {
          window.location.replace(replayUrl);
          return;
        }

        if (window.__eduititVideoGuard) {
          window.clearInterval(window.__eduititVideoGuard);
        }
        const driftState = window.__eduititDriftState || {
          lastRecoveryAt: 0,
          activeMismatchSince: 0,
          activeMismatchVideoId: "",
        };
        window.__eduititDriftState = driftState;
        window.__eduititVideoGuard = window.setInterval(() => {
          const now = Date.now();

          if (isAdShowing()) {
            driftState.activeMismatchSince = 0;
            driftState.activeMismatchVideoId = "";
            return;
          }

          const pageVideoId = getPageVideoId();
          const activeVideoId = getActiveVideoId();
          const playerState = getPlayerState();
          const video = document.querySelector("video");

          if (targetVideoId && pageVideoId && pageVideoId !== targetVideoId) {
            if (replayUrl && now - driftState.lastRecoveryAt >= replayCooldownMs) {
              driftState.lastRecoveryAt = now;
              window.location.replace(replayUrl);
            }
            return;
          }

          if (!activeVideoId || activeVideoId === targetVideoId) {
            driftState.activeMismatchSince = 0;
            driftState.activeMismatchVideoId = "";
            return;
          }

          if (driftState.activeMismatchVideoId !== activeVideoId) {
            driftState.activeMismatchVideoId = activeVideoId;
            driftState.activeMismatchSince = now;
          }

          const mismatchDurationMs = driftState.activeMismatchSince ? now - driftState.activeMismatchSince : 0;
          const isPlayingAnotherVideo = Boolean(
            video &&
              video.currentTime >= 1 &&
              (playerState === null || playerState === 1 || playerState === 2 || playerState === 3)
          );

          if (
            isPlayingAnotherVideo &&
            mismatchDurationMs >= 1500 &&
            replayUrl &&
            now - driftState.lastRecoveryAt >= replayCooldownMs
          ) {
            driftState.lastRecoveryAt = now;
            window.location.replace(replayUrl);
          }
        }, 1200);

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
    height: bounds.videoHeight,
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
  videoWindow.loadURL(getPayloadVideoUrl(payload));
  if (extractYouTubeVideoId(getPayloadVideoUrl(payload))) {
    installYouTubeFocusMode(videoWindow, getPayloadVideoUrl(payload));
  }

  createVideoControlWindow(payload);

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
  const videoControlRef = videoControlWindow;
  const dashboardRef = dashboardWindow;

  videoRef.on("close", () => {
    if (!videoRef.__eduititInternalClose) {
      handleUserWindowClose();
    }
  });
  videoControlRef.on("close", () => {
    if (!videoControlRef.__eduititInternalClose) {
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
  videoControlRef.on("closed", () => {
    if (videoControlWindow === videoControlRef) {
      videoControlWindow = null;
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

async function launchSplitSession(payload) {
  const normalizedPayload = normalizeLaunchPayload(payload);
  if (!normalizedPayload) {
    showErrorBox("런처 수업 정보를 다시 확인해 주세요.");
    return;
  }

  const versionReady = await ensureLauncherVersionReadyForLaunch(normalizedPayload);
  if (!versionReady) {
    return;
  }

  watchdogCircuitOpen = false;
  recoveryAttemptTimestamps = [];
  lastRecoveryAt = 0;
  clearPendingLaunchState();
  lockDisplayToCurrentPointer();
  lastLaunchPayload = normalizedPayload;
  if (normalizedPayload.updateConfigUrl) {
    void syncLauncherReleaseConfig(normalizedPayload.updateConfigUrl, { checkImmediately: true });
  }
  createSplitWindows(normalizedPayload);
}

async function handleLaunchUrl(rawUrl) {
  const launcherAction = parseLauncherAction(rawUrl);
  if (launcherAction && executeLauncherAction(launcherAction)) {
    return;
  }

  const parsed = parseLaunchUrl(rawUrl);
  if (parsed.error) {
    if (parsed.error === "missing_payload") {
      const handledByUpdate = await tryUpdateFromMissingPayload();
      if (handledByUpdate) {
        return;
      }
    }
    showErrorBox(`런처 payload를 읽지 못했습니다: ${parsed.error}`);
    return;
  }
  await launchSplitSession(parsed);
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

  app.whenReady().then(async () => {
    bindDisplayEventHandlers();
    bootstrapLauncherAutoUpdate();
    const launchUrl = extractLaunchUrlFromArgv(process.argv);
    if (launchUrl) {
      handleLaunchUrl(launchUrl);
      return;
    }
    if (await resumePendingLaunchIfNeeded()) {
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
