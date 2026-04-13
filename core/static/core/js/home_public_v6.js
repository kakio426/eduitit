document.addEventListener("DOMContentLoaded", () => {
    const primaryLauncherButton = document.querySelector("[data-public-primary-cta='launcher']");
    const heroRevealItems = Array.from(
        document.querySelectorAll("[data-public-hero-reveal='true']")
    );
    const revealItems = Array.from(
        document.querySelectorAll("[data-public-reveal='true']")
    );
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const markVisible = (element) => {
        if (!element) return;
        element.classList.add("is-visible");
    };

    const scrollToFallbackTarget = (targetId) => {
        if (!targetId) return;
        const target = document.getElementById(targetId);
        if (!target) return;
        target.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "start" });
    };

    if (primaryLauncherButton) {
        primaryLauncherButton.addEventListener("click", () => {
            if (typeof window.openServiceLauncher === "function") {
                window.openServiceLauncher();
                return;
            }

            const directHref = primaryLauncherButton.dataset.publicPrimaryHref;
            if (directHref) {
                window.location.assign(directHref);
                return;
            }

            scrollToFallbackTarget(primaryLauncherButton.dataset.publicFallbackTarget);
        });
    }

    if (prefersReducedMotion) {
        heroRevealItems.forEach(markVisible);
        revealItems.forEach(markVisible);
        return;
    }

    heroRevealItems.forEach((item) => {
        const delayMs = Number(item.dataset.publicHeroDelay || "0");
        window.setTimeout(() => {
            markVisible(item);
        }, delayMs);
    });

    if (!revealItems.length) return;

    const revealObserver = new IntersectionObserver(
        (entries, observer) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                markVisible(entry.target);
                observer.unobserve(entry.target);
            });
        },
        {
            threshold: 0.16,
            rootMargin: "0px 0px -10% 0px",
        }
    );

    revealItems.forEach((item) => {
        revealObserver.observe(item);
    });
});
