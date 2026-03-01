const path = require("path");
const { app, BrowserWindow, dialog, screen } = require("electron");

const PROTOCOL = "eduitit-launcher";
const MIN_VIDEO_WIDTH = 640;
const MIN_DASHBOARD_WIDTH = 420;
const DEFAULT_LEFT_RATIO = 0.6;

let videoWindow = null;
let dashboardWindow = null;
let infoWindow = null;

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
  videoWindow = null;
  dashboardWindow = null;
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
  const display = screen.getPrimaryDisplay();
  const area = display.workArea;

  let leftWidth = Math.floor(area.width * DEFAULT_LEFT_RATIO);
  leftWidth = Math.max(MIN_VIDEO_WIDTH, leftWidth);
  leftWidth = Math.min(area.width - MIN_DASHBOARD_WIDTH, leftWidth);

  let rightWidth = area.width - leftWidth;
  if (rightWidth < MIN_DASHBOARD_WIDTH) {
    rightWidth = MIN_DASHBOARD_WIDTH;
    leftWidth = area.width - rightWidth;
  }

  return {
    x: area.x,
    y: area.y,
    height: area.height,
    leftWidth,
    rightWidth,
  };
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
  videoWindow.setMenuBarVisibility(false);
  videoWindow.loadURL(payload.youtubeUrl);

  dashboardWindow = new BrowserWindow({
    x: bounds.x + bounds.leftWidth,
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
  dashboardWindow.setMenuBarVisibility(false);
  dashboardWindow.loadURL(payload.dashboardUrl);

  videoWindow.on("closed", () => {
    videoWindow = null;
  });
  dashboardWindow.on("closed", () => {
    dashboardWindow = null;
  });
}

function handleLaunchUrl(rawUrl) {
  const parsed = parseLaunchUrl(rawUrl);
  if (parsed.error) {
    showErrorBox(`런처 payload를 읽지 못했습니다: ${parsed.error}`);
    return;
  }
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
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (!videoWindow && !dashboardWindow) {
    createInfoWindow();
  }
});
