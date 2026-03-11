(function () {
    function readJsonScript(scriptId) {
        const element = document.getElementById(scriptId);
        if (!element) {
            return {};
        }
        try {
            return JSON.parse(element.textContent || "{}");
        } catch (_error) {
            return {};
        }
    }

    function highlightCode(code) {
        return String(code || "")
            .replace(/(# [^\n]+)/g, '<span class="text-purple-600 font-bold">$1</span>')
            .replace(/(\[.*?\])/g, '<span class="text-blue-500 font-bold">$1</span>')
            .replace(/(\*\*(.*?)\*\*)/g, '<strong class="text-gray-800">$1</strong>');
    }

    function safeCopyText(text, successMessage) {
        if (!navigator.clipboard || !text) {
            return Promise.reject(new Error("복사에 실패했습니다. 직접 선택해 복사해 주세요."));
        }
        return navigator.clipboard.writeText(text).then(() => {
            if (window.showToast && successMessage) {
                window.showToast(successMessage, "success");
            }
        });
    }

    function setScrollLock(locked) {
        const root = document.documentElement;
        if (locked) {
            document.body.style.overflow = "hidden";
            root.style.overflow = "hidden";
            return;
        }
        document.body.style.overflow = "";
        root.style.overflow = "";
    }

    function createHomePromptLabMiniApp(scriptId) {
        return {
            catalog: {},
            categories: [],
            activeKey: "",
            recommendations: [],
            copyValue: "",
            state: {
                status: "idle",
                message: "카테고리를 고르면 추천 프롬프트를 바로 복사할 수 있습니다.",
            },

            init() {
                const catalog = readJsonScript(scriptId);
                this.catalog = catalog;
                this.categories = Object.keys(catalog).map((key) => {
                    const item = catalog[key] || {};
                    return {
                        key,
                        title: item.mini_title || item.title || key,
                    };
                });
            },

            selectCategory(key) {
                this.activeKey = key;
                const category = this.catalog[key];
                if (!category || !Array.isArray(category.items) || !category.items.length) {
                    this.recommendations = [];
                    this.copyValue = "";
                    this.state = {
                        status: "empty",
                        message: "이 카테고리에는 아직 추천 프롬프트가 없습니다.",
                    };
                    return;
                }
                this.recommendations = category.items.slice(0, 2);
                this.copyValue = this.recommendations[0].code || "";
                this.state = {
                    status: "success",
                    message: "추천 프롬프트를 바로 복사하거나 전체 페이지에서 더 자세히 볼 수 있습니다.",
                };
            },

            copyPrimary() {
                if (!this.copyValue) {
                    this.state = {
                        status: "error",
                        message: "먼저 카테고리를 골라 주세요.",
                    };
                    return;
                }
                safeCopyText(this.copyValue, "추천 프롬프트를 복사했습니다.")
                    .then(() => {
                        this.state = {
                            status: "success",
                            message: "추천 프롬프트를 복사했습니다.",
                        };
                    })
                    .catch((error) => {
                        this.state = {
                            status: "error",
                            message: error.message || "복사에 실패했습니다. 직접 선택해 복사해 주세요.",
                        };
                    });
            },

            copyPrompt(code, title) {
                safeCopyText(code, `${title} 프롬프트를 복사했습니다.`)
                    .then(() => {
                        this.copyValue = code;
                        this.state = {
                            status: "success",
                            message: `${title} 프롬프트를 복사했습니다.`,
                        };
                    })
                    .catch((error) => {
                        this.state = {
                            status: "error",
                            message: error.message || "복사에 실패했습니다. 직접 선택해 복사해 주세요.",
                        };
                    });
            },

            reset() {
                this.activeKey = "";
                this.recommendations = [];
                this.copyValue = "";
                this.state = {
                    status: "idle",
                    message: "카테고리를 고르면 추천 프롬프트를 바로 복사할 수 있습니다.",
                };
            },
        };
    }

    function initPromptLabPage(options) {
        const settings = options || {};
        const promptData = readJsonScript(settings.catalogScriptId || "prompt-lab-catalog");
        const overlay = document.getElementById("modal-overlay");
        const modal = document.getElementById("modal-content");
        const modalTitle = document.getElementById("modal-title");
        const modalBody = document.getElementById("modal-body-content");
        const cards = document.querySelectorAll(".prompt-card");

        if (!overlay || !modal || !modalTitle || !modalBody || !cards.length) {
            return;
        }

        function openModal(category) {
            const data = promptData[category];
            if (!data) {
                return;
            }

            modalTitle.innerText = data.title;
            let htmlContent = '<div class="space-y-6 md:space-y-8">';
            data.items.forEach((item, index) => {
                htmlContent += `
                    <div class="clay-card shadow-clay p-4 sm:p-6 md:p-8 rounded-clay bg-[#E0E5EC] overflow-hidden max-w-full">
                        <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 md:mb-6 gap-4">
                            <div class="min-w-0 w-full">
                                <h3 class="text-lg sm:text-xl md:text-3xl font-bold text-gray-700 flex items-start gap-3 leading-snug break-words">
                                    <span class="w-8 h-8 md:w-10 md:h-10 rounded-full shadow-clay-inner shrink-0 flex items-center justify-center text-sm md:text-lg font-bold text-purple-500">${index + 1}</span>
                                    ${item.title}
                                </h3>
                                <div class="flex flex-wrap gap-2 mt-3 md:ml-12">
                                    ${(item.tags || []).map((tag) => `<span class="px-3 py-1.5 rounded-full shadow-clay text-xs sm:text-sm md:text-base text-gray-500 bg-[#E0E5EC]">#${tag}</span>`).join("")}
                                </div>
                            </div>
                            <button onclick="copyCode(this)" class="clay-btn shadow-clay px-6 md:px-8 py-3.5 rounded-clay text-purple-600 font-bold hover:shadow-clay-hover hover:text-purple-700 active:shadow-clay-pressed active:scale-95 transition-all text-base md:text-xl flex items-center justify-center gap-2 w-full md:w-auto">
                                <i class="fa-regular fa-copy"></i> 복사하기
                            </button>
                        </div>
                        <p class="text-gray-600 mb-4 md:mb-6 text-base sm:text-lg md:text-2xl md:pl-12 break-words">
                            💡 ${item.desc}
                        </p>
                        <div class="relative md:ml-12 min-w-0">
                            <pre class="shadow-clay-inner rounded-xl p-4 md:p-6 bg-gray-100 text-sm sm:text-base md:text-lg overflow-x-auto text-gray-700 font-mono leading-relaxed whitespace-pre-wrap border border-gray-200">${highlightCode(item.code)}</pre>
                        </div>
                    </div>
                `;
            });
            htmlContent += "</div>";
            modalBody.innerHTML = htmlContent;

            overlay.classList.remove("hidden");
            modal.classList.remove("hidden");
            setTimeout(() => {
                overlay.classList.remove("opacity-0");
                modal.classList.remove("opacity-0", "scale-95");
                modal.classList.add("scale-100");
            }, 10);
            setScrollLock(true);
        }

        function closeModal() {
            overlay.classList.add("opacity-0");
            modal.classList.remove("scale-100");
            modal.classList.add("opacity-0", "scale-95");
            setTimeout(() => {
                overlay.classList.add("hidden");
                modal.classList.add("hidden");
                setScrollLock(false);
            }, 300);
        }

        function copyCode(button) {
            const cardContainer = button.closest(".clay-card");
            const codeBlock = cardContainer ? cardContainer.querySelector("pre") : null;
            const text = codeBlock ? codeBlock.innerText : "";
            const originalContent = button.innerHTML;

            safeCopyText(text, "")
                .then(() => {
                    button.innerHTML = '<i class="fa-solid fa-check"></i> 완료!';
                    button.classList.remove("text-purple-600");
                    button.classList.add("text-green-500");
                    setTimeout(() => {
                        button.innerHTML = originalContent;
                        button.classList.add("text-purple-600");
                        button.classList.remove("text-green-500");
                    }, 2000);
                })
                .catch(() => {
                    if (window.showToast) {
                        window.showToast("복사에 실패했습니다. 직접 선택해 복사해 주세요.", "error");
                    }
                });
        }

        cards.forEach((card) => {
            card.setAttribute("role", "button");
            card.setAttribute("tabindex", "0");
            card.addEventListener("click", () => openModal(card.dataset.category));
            card.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openModal(card.dataset.category);
                }
            });
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !modal.classList.contains("hidden")) {
                closeModal();
            }
        });

        window.copyCode = copyCode;
        window.closeModal = closeModal;
        window.openPromptLabModal = openModal;
    }

    window.createHomePromptLabMiniApp = createHomePromptLabMiniApp;
    window.initPromptLabPage = initPromptLabPage;
})();
