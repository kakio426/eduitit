document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector(".home-public-v6-page");
    const primaryLauncherButton = document.querySelector("[data-public-primary-cta='launcher']");
    const magneticButtons = Array.from(
        document.querySelectorAll("[data-magnetic-button='true']")
    );
    const heroRevealItems = Array.from(
        document.querySelectorAll("[data-public-hero-reveal='true']")
    );
    const revealItems = Array.from(
        document.querySelectorAll("[data-public-reveal='true']")
    );
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const supportsFinePointer = window.matchMedia("(pointer: fine)").matches
        && window.matchMedia("(hover: hover)").matches;
    const interactionCleanup = [];

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

    if (page && magneticButtons.length && supportsFinePointer && !prefersReducedMotion) {
        const states = magneticButtons.map((button) => ({
            button,
            blob: button
                .closest("[data-home-public-v6-goo-shell='true']")
                ?.querySelector("[data-magnetic-blob='true']"),
            inner: button.querySelector("[data-magnetic-inner='true']") || button,
            currentX: 0,
            currentY: 0,
            currentInnerX: 0,
            currentInnerY: 0,
            targetX: 0,
            targetY: 0,
            targetInnerX: 0,
            targetInnerY: 0,
        }));
        let frameId = 0;

        const resetState = (state) => {
            state.targetX = 0;
            state.targetY = 0;
            state.targetInnerX = 0;
            state.targetInnerY = 0;
            state.button.classList.remove("is-magnetic-active");
        };

        const handlePointerMove = (event) => {
            states.forEach((state) => {
                const rect = state.button.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                const deltaX = event.clientX - centerX;
                const deltaY = event.clientY - centerY;

                if (Math.abs(deltaX) >= 150 || Math.abs(deltaY) >= 150) {
                    resetState(state);
                    return;
                }

                state.targetX = deltaX * 0.3;
                state.targetY = deltaY * 0.3;
                state.targetInnerX = deltaX * 0.15;
                state.targetInnerY = deltaY * 0.15;
                state.button.classList.add("is-magnetic-active");
            });
        };

        const renderMagnetic = () => {
            states.forEach((state) => {
                state.currentX += (state.targetX - state.currentX) * 0.22;
                state.currentY += (state.targetY - state.currentY) * 0.22;
                state.currentInnerX += (state.targetInnerX - state.currentInnerX) * 0.22;
                state.currentInnerY += (state.targetInnerY - state.currentInnerY) * 0.22;

                const buttonTransform = `translate3d(${state.currentX}px, ${state.currentY}px, 0)`;
                state.button.style.transform = buttonTransform;
                state.inner.style.transform =
                    `translate3d(${state.currentInnerX}px, ${state.currentInnerY}px, 0)`;
                if (state.blob) {
                    state.blob.style.transform = `translate3d(calc(-50% + ${state.currentX}px), calc(-50% + ${state.currentY}px), 0)`;
                }
            });

            frameId = window.requestAnimationFrame(renderMagnetic);
        };

        const handleWindowLeave = (event) => {
            if (event && (event.relatedTarget || event.toElement)) return;
            states.forEach(resetState);
        };

        window.addEventListener("mousemove", handlePointerMove, { passive: true });
        window.addEventListener("mouseout", handleWindowLeave);
        interactionCleanup.push(() => window.removeEventListener("mousemove", handlePointerMove));
        interactionCleanup.push(() => window.removeEventListener("mouseout", handleWindowLeave));

        states.forEach((state) => {
            const handlePointerLeave = () => resetState(state);
            state.button.addEventListener("pointerleave", handlePointerLeave);
            interactionCleanup.push(() => state.button.removeEventListener("pointerleave", handlePointerLeave));
        });

        frameId = window.requestAnimationFrame(renderMagnetic);
        interactionCleanup.push(() => window.cancelAnimationFrame(frameId));
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

    window.addEventListener(
        "pagehide",
        () => {
            interactionCleanup.forEach((cleanup) => cleanup());
        },
        { once: true }
    );

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
