document.addEventListener("DOMContentLoaded", () => {
    const showcaseRoot = document.querySelector("[data-public-platform-showcase='true']");
    const primaryLauncherButton = document.querySelector("[data-public-primary-cta='launcher']");

    const scrollToFallbackTarget = (targetId) => {
        const target = document.getElementById(targetId);
        if (!target) return;
        target.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    if (primaryLauncherButton) {
        primaryLauncherButton.addEventListener("click", () => {
            if (typeof window.openServiceLauncher === "function") {
                window.openServiceLauncher();
                return;
            }

            const fallbackTarget = primaryLauncherButton.dataset.publicFallbackTarget;
            if (fallbackTarget) {
                scrollToFallbackTarget(fallbackTarget);
            }
        });
    }

    if (!showcaseRoot) return;

    const triggers = Array.from(
        showcaseRoot.querySelectorAll("[data-platform-showcase-trigger]")
    );
    const panels = Array.from(
        showcaseRoot.querySelectorAll("[data-platform-showcase-panel]")
    );

    if (!triggers.length || !panels.length) return;

    const activate = (index) => {
        triggers.forEach((trigger, triggerIndex) => {
            const isActive = triggerIndex === index;
            trigger.setAttribute("aria-selected", isActive ? "true" : "false");
            trigger.setAttribute("tabindex", isActive ? "0" : "-1");
            trigger.dataset.platformShowcaseActive = isActive ? "true" : "false";
        });

        panels.forEach((panel, panelIndex) => {
            const isActive = panelIndex === index;
            panel.hidden = !isActive;
            panel.dataset.platformShowcaseActive = isActive ? "true" : "false";
        });
    };

    triggers.forEach((trigger, index) => {
        trigger.addEventListener("click", () => {
            activate(index);
        });

        trigger.addEventListener("focus", () => {
            activate(index);
        });

        trigger.addEventListener("keydown", (event) => {
            let nextIndex = null;

            if (event.key === "ArrowRight" || event.key === "ArrowDown") {
                nextIndex = (index + 1) % triggers.length;
            } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
                nextIndex = (index - 1 + triggers.length) % triggers.length;
            } else if (event.key === "Home") {
                nextIndex = 0;
            } else if (event.key === "End") {
                nextIndex = triggers.length - 1;
            }

            if (nextIndex === null) return;

            event.preventDefault();
            activate(nextIndex);
            triggers[nextIndex].focus();
        });
    });

    const initialIndex = Math.max(
        0,
        triggers.findIndex(
            (trigger) => trigger.getAttribute("aria-selected") === "true"
        )
    );
    activate(initialIndex);
});
