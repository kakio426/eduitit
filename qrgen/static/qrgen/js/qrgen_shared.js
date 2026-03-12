(function () {
    function isPrivateOrLocalHostname(hostname) {
        const normalized = (hostname || "").trim().toLowerCase();
        if (!normalized) {
            return false;
        }
        if (normalized === "localhost" || normalized.endsWith(".local")) {
            return true;
        }
        if (normalized === "::1" || normalized === "[::1]") {
            return true;
        }

        const ipv6 = normalized.replace(/^\[|\]$/g, "");
        if (ipv6.startsWith("fc") || ipv6.startsWith("fd") || ipv6.startsWith("fe80:")) {
            return true;
        }

        const ipv4Match = normalized.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
        if (!ipv4Match) {
            return false;
        }
        const octets = ipv4Match.slice(1).map((value) => parseInt(value, 10));
        if (octets.some((value) => Number.isNaN(value) || value < 0 || value > 255)) {
            return false;
        }
        const [first, second] = octets;
        if (first === 10 || first === 127) {
            return true;
        }
        if (first === 169 && second === 254) {
            return true;
        }
        if (first === 172 && second >= 16 && second <= 31) {
            return true;
        }
        if (first === 192 && second === 168) {
            return true;
        }
        return false;
    }

    function parseUrl(raw) {
        const text = (raw || "").trim();
        if (!text) {
            return { url: "", error: "" };
        }

        const withScheme = /^https?:\/\//i.test(text) ? text : `https://${text}`;
        let parsed;
        try {
            parsed = new URL(withScheme);
        } catch (_error) {
            return { url: "", error: "유효한 링크 형식이 아니에요." };
        }

        if (!["http:", "https:"].includes(parsed.protocol)) {
            return { url: "", error: "http/https 링크만 사용할 수 있어요." };
        }

        if (isPrivateOrLocalHostname(parsed.hostname)) {
            return { url: "", error: "localhost, 사설 IP, 학교 내부망 주소는 QR로 만들 수 없어요." };
        }
        if (!parsed.hostname || parsed.hostname.indexOf(".") === -1) {
            return { url: "", error: "도메인이 포함된 링크를 입력해 주세요." };
        }

        return { url: parsed.toString(), error: "" };
    }

    function renderQrCode(container, text, size, colorDark) {
        if (!container) {
            return;
        }
        container.innerHTML = "";
        if (!text || typeof QRCode === "undefined") {
            return;
        }
        new QRCode(container, {
            text,
            width: size,
            height: size,
            colorDark: colorDark || "#111827",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.M,
        });
    }

    function sanitizeInterval(value) {
        let nextValue = parseInt(value, 10);
        if (Number.isNaN(nextValue)) {
            nextValue = 8;
        }
        if (nextValue < 2) {
            nextValue = 2;
        }
        if (nextValue > 120) {
            nextValue = 120;
        }
        return nextValue;
    }

    function copyToClipboard(text, successMessage) {
        if (!navigator.clipboard || !text) {
            return Promise.reject(new Error("복사에 실패했습니다. 직접 선택해 복사해 주세요."));
        }
        return navigator.clipboard.writeText(text).then(() => {
            if (window.showToast && successMessage) {
                window.showToast(successMessage, "success");
            }
        });
    }

    function createQrgenApp() {
        return {
            items: [],
            nextUid: 1,
            intervalSec: 8,
            cycleMode: false,
            isPlaying: false,
            currentSlide: 0,
            remainingSec: 8,
            autoTimer: null,
            countdownTimer: null,
            renderTimer: null,

            init() {
                this.addItem("링크 1", "");
                this.queueRender();

                document.addEventListener("fullscreenchange", () => {
                    if (!document.fullscreenElement && this.cycleMode) {
                        this.closeCycleMode(true);
                    }
                });
                window.addEventListener("resize", () => {
                    if (this.cycleMode) {
                        this.$nextTick(() => this.renderCycleQr());
                    }
                });
            },

            addItem(defaultTitle, defaultUrl) {
                const item = {
                    uid: this.nextUid++,
                    title: defaultTitle || `${this.items.length + 1}번 링크`,
                    url: defaultUrl || "",
                    normalizedUrl: "",
                    error: "",
                };
                this.items.push(item);
                if (item.url) {
                    this.updateItem(item);
                }
            },

            removeItem(uid) {
                this.items = this.items.filter((item) => item.uid !== uid);
                if (this.items.length === 0) {
                    this.addItem("링크 1", "");
                }
                this.queueRender();
                this.syncCycleAfterDataChange();
            },

            parseUrl,

            updateItem(item) {
                const parsed = parseUrl(item.url);
                item.normalizedUrl = parsed.url;
                item.error = parsed.error;
                this.queueRender();
                this.syncCycleAfterDataChange();
            },

            validItems() {
                return this.items.filter((item) => !!item.normalizedUrl);
            },

            queueRender() {
                if (this.renderTimer) {
                    clearTimeout(this.renderTimer);
                }
                this.renderTimer = setTimeout(() => {
                    this.$nextTick(() => {
                        this.renderAllPreviews();
                        if (this.cycleMode) {
                            this.renderCycleQr();
                        }
                    });
                }, 40);
            },

            renderAllPreviews() {
                this.items.forEach((item) => {
                    renderQrCode(document.getElementById(`preview-qr-${item.uid}`), item.normalizedUrl, 170, "#111827");
                });
            },

            sanitizedInterval() {
                this.intervalSec = sanitizeInterval(this.intervalSec);
                return this.intervalSec;
            },

            onIntervalChange() {
                const interval = this.sanitizedInterval();
                this.remainingSec = interval;
                if (this.cycleMode && this.isPlaying) {
                    this.startTimers();
                }
            },

            activeItem() {
                const valid = this.validItems();
                if (!valid.length) {
                    return null;
                }
                if (this.currentSlide >= valid.length) {
                    this.currentSlide = 0;
                }
                return valid[this.currentSlide];
            },

            activeItemTitle() {
                const item = this.activeItem();
                return item ? (item.title || "링크") : "표시할 QR이 없습니다";
            },

            slideLabel() {
                const total = this.validItems().length;
                if (!total) {
                    return "0 / 0";
                }
                return `${this.currentSlide + 1} / ${total}`;
            },

            startCycleMode() {
                if (!this.validItems().length) {
                    return;
                }
                this.cycleMode = true;
                this.isPlaying = true;
                this.currentSlide = 0;
                this.remainingSec = this.sanitizedInterval();

                this.$nextTick(() => {
                    this.renderCycleQr();
                    this.startTimers();
                    const stage = document.getElementById("cycleStage");
                    if (stage && !document.fullscreenElement && stage.requestFullscreen) {
                        stage.requestFullscreen().catch(() => {});
                    }
                });
            },

            closeCycleMode(skipExit) {
                this.cycleMode = false;
                this.isPlaying = false;
                this.clearTimers();
                if (!skipExit && document.fullscreenElement && document.exitFullscreen) {
                    document.exitFullscreen().catch(() => {});
                }
            },

            syncCycleAfterDataChange() {
                if (!this.cycleMode) {
                    return;
                }
                const valid = this.validItems();
                if (!valid.length) {
                    this.closeCycleMode();
                    return;
                }
                if (this.currentSlide >= valid.length) {
                    this.currentSlide = 0;
                }
                if (this.isPlaying) {
                    this.startTimers();
                } else {
                    this.renderCycleQr();
                }
            },

            clearTimers() {
                if (this.autoTimer) {
                    clearInterval(this.autoTimer);
                    this.autoTimer = null;
                }
                if (this.countdownTimer) {
                    clearInterval(this.countdownTimer);
                    this.countdownTimer = null;
                }
            },

            startTimers() {
                this.clearTimers();
                if (!this.cycleMode || !this.isPlaying) {
                    return;
                }

                const interval = this.sanitizedInterval();
                this.remainingSec = interval;

                this.autoTimer = setInterval(() => {
                    this.nextSlide(false);
                }, interval * 1000);

                this.countdownTimer = setInterval(() => {
                    if (!this.cycleMode || !this.isPlaying) {
                        return;
                    }
                    this.remainingSec -= 1;
                    if (this.remainingSec <= 0) {
                        this.remainingSec = interval;
                    }
                }, 1000);
            },

            togglePlay() {
                if (!this.cycleMode) {
                    return;
                }
                this.isPlaying = !this.isPlaying;
                if (this.isPlaying) {
                    this.startTimers();
                } else {
                    this.clearTimers();
                }
            },

            nextSlide(manual) {
                const valid = this.validItems();
                if (!valid.length) {
                    this.closeCycleMode();
                    return;
                }
                this.currentSlide = (this.currentSlide + 1) % valid.length;
                this.renderCycleQr();
                if (manual && this.isPlaying) {
                    this.startTimers();
                }
            },

            prevSlide() {
                const valid = this.validItems();
                if (!valid.length) {
                    this.closeCycleMode();
                    return;
                }
                this.currentSlide = (this.currentSlide - 1 + valid.length) % valid.length;
                this.renderCycleQr();
                if (this.isPlaying) {
                    this.startTimers();
                }
            },

            renderCycleQr() {
                const item = this.activeItem();
                const side = Math.max(280, Math.min(780, Math.floor(window.innerWidth * 0.76)));
                renderQrCode(document.getElementById("cycleQrCanvas"), item ? item.normalizedUrl : "", side, "#000000");
            },
        };
    }

    function createQrgenSingleLinkMiniApp(options) {
        const settings = options || {};
        return {
            url: settings.initialUrl || "",
            status: "idle",
            message: settings.idleMessage || "수업 링크를 하나 넣으면 QR 미리보기가 바로 나옵니다.",
            errorMessage: "",
            normalizedUrl: "",
            copyValue: "",
            previewDomId: settings.previewDomId || "",

            init() {
                if (this.url) {
                    this.submit();
                }
            },

            submit() {
                const parsed = parseUrl(this.url);
                this.normalizedUrl = parsed.url;
                this.errorMessage = parsed.error;
                this.copyValue = parsed.url;
                if (parsed.error) {
                    this.status = "error";
                    this.message = parsed.error;
                    renderQrCode(document.getElementById(this.previewDomId), "", 0, "#111827");
                    return;
                }
                if (!parsed.url) {
                    this.status = "empty";
                    this.message = settings.emptyMessage || "링크를 입력하면 QR이 여기에 표시됩니다.";
                    renderQrCode(document.getElementById(this.previewDomId), "", 0, "#111827");
                    return;
                }
                this.status = "success";
                this.message = settings.successMessage || "학생에게 바로 보여줄 QR이 준비됐습니다.";
                this.$nextTick(() => {
                    renderQrCode(document.getElementById(this.previewDomId), parsed.url, 152, "#111827");
                });
            },

            reset() {
                this.url = "";
                this.status = "idle";
                this.message = settings.idleMessage || "수업 링크를 하나 넣으면 QR 미리보기가 바로 나옵니다.";
                this.errorMessage = "";
                this.normalizedUrl = "";
                this.copyValue = "";
                renderQrCode(document.getElementById(this.previewDomId), "", 0, "#111827");
            },

            copyLink() {
                if (!this.copyValue) {
                    return;
                }
                copyToClipboard(this.copyValue, "링크를 복사했습니다.").catch(() => {
                    this.status = "error";
                    this.message = "복사에 실패했습니다. 직접 선택해 복사해 주세요.";
                });
            },
        };
    }

    window.qrgenShared = {
        parseUrl,
        renderQrCode,
        sanitizeInterval,
        copyToClipboard,
    };
    window.createQrgenApp = createQrgenApp;
    window.createQrgenSingleLinkMiniApp = createQrgenSingleLinkMiniApp;
})();
