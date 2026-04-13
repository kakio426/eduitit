document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector(".home-public-v6-page");
    const primaryLauncherButton = document.querySelector("[data-public-primary-cta='launcher']");
    const heroRevealItems = Array.from(
        document.querySelectorAll("[data-public-hero-reveal='true']")
    );
    const revealItems = Array.from(
        document.querySelectorAll("[data-public-reveal='true']")
    );
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const supportsFinePointer = window.matchMedia("(pointer: fine)").matches
        && window.matchMedia("(hover: hover)").matches;
    const cursorCloud = document.querySelector("[data-public-cursor-cloud='true']");
    const cursorDot = document.querySelector("[data-public-cursor-dot='true']");
    const cursorFollower = document.querySelector("[data-public-cursor-follower='true']");
    const cursorAura = document.querySelector("[data-public-cursor-aura='true']");
    const cursorLabel = document.querySelector("[data-public-cursor-label='true']");
    const pointerCleanup = [];

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

    if (page && supportsFinePointer && !prefersReducedMotion && cursorCloud && cursorDot && cursorFollower && cursorAura) {
        document.documentElement.setAttribute("data-home-public-v6-pointer", "true");

        let mouseX = window.innerWidth * 0.5;
        let mouseY = window.innerHeight * 0.5;
        let followerX = mouseX;
        let followerY = mouseY;
        let auraX = mouseX;
        let auraY = mouseY;
        let cloudX = 0;
        let cloudY = 0;
        let frameId = 0;
        let activePointerTarget = null;

        page.dataset.pointerVisible = "false";
        page.dataset.pointerHover = "false";
        page.dataset.pointerTone = "violet";
        page.dataset.pointerMode = "idle";

        const interactiveTargets = Array.from(page.querySelectorAll("a, button"));
        const denseInteractiveSelector = [
            ".home-public-v6-preview-item",
            ".home-public-v6-bento-card",
            ".home-public-v6-group-item",
        ].join(", ");

        const clearPointerFocus = () => {
            if (!activePointerTarget) return;
            activePointerTarget.removeAttribute("data-pointer-focus");
            activePointerTarget = null;
        };

        const resolvePointerLabel = (target) => {
            if (!target) return "OPEN";
            if (target.matches(".home-public-v6-brand")) return "HOME";
            if (target.matches(".home-public-v6-primary-link, .home-public-v6-login-link")) return "START";
            if (target.matches(".home-public-v6-secondary-link, .home-public-v6-header-link")) return "VIEW";
            if (target.matches(".home-public-v6-preview-login")) return "LOGIN";
            return "OPEN";
        };

        const resolvePointerTone = (target) => {
            if (!target) return "violet";
            if (target.matches(".home-public-v6-secondary-link, .home-public-v6-header-link")) return "lilac";
            if (target.matches(".home-public-v6-preview-login")) return "ink";
            if (target.matches(".home-public-v6-preview-item, .home-public-v6-bento-card, .home-public-v6-group-item")) return "plum";
            if (target.matches(".home-public-v6-brand, .home-public-v6-login-link")) return "ink";
            return "violet";
        };

        const resolvePointerMode = (target) => {
            if (!target) return "idle";
            if (target.matches(denseInteractiveSelector)) return "text";
            return "label";
        };

        const handleMouseMove = (event) => {
            mouseX = event.clientX;
            mouseY = event.clientY;
            page.dataset.pointerVisible = "true";
            cursorDot.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0)`;
        };

        const handleMouseEnter = () => {
            page.dataset.pointerVisible = "true";
        };

        const handleMouseLeave = () => {
            page.dataset.pointerVisible = "false";
            page.dataset.pointerHover = "false";
            page.dataset.pointerTone = "violet";
            page.dataset.pointerMode = "idle";
            clearPointerFocus();
            if (cursorLabel) {
                cursorLabel.textContent = "OPEN";
            }
        };

        const handlePointerHoverOn = (event) => {
            const target = event.currentTarget;
            page.dataset.pointerHover = "true";
            page.dataset.pointerTone = resolvePointerTone(target);
            page.dataset.pointerMode = resolvePointerMode(target);
            clearPointerFocus();
            activePointerTarget = target;
            activePointerTarget.setAttribute("data-pointer-focus", "true");
            if (cursorLabel) {
                cursorLabel.textContent = resolvePointerLabel(target);
            }
        };

        const handlePointerHoverOff = (event) => {
            if (activePointerTarget === event.currentTarget) {
                clearPointerFocus();
            }
            page.dataset.pointerHover = "false";
            page.dataset.pointerTone = "violet";
            page.dataset.pointerMode = "idle";
            if (cursorLabel) {
                cursorLabel.textContent = "OPEN";
            }
        };

        const renderPointer = () => {
            followerX += (mouseX - followerX) * 0.18;
            followerY += (mouseY - followerY) * 0.18;
            auraX += (mouseX - auraX) * 0.08;
            auraY += (mouseY - auraY) * 0.08;
            cloudX += ((mouseX - window.innerWidth * 0.5) - cloudX) * 0.14;
            cloudY += ((mouseY - window.innerHeight * 0.5) - cloudY) * 0.14;

            const isVisible = page.dataset.pointerVisible === "true";
            const isHoveringInteractive = page.dataset.pointerHover === "true";
            const pointerMode = page.dataset.pointerMode || "idle";
            const followerScale = isHoveringInteractive && pointerMode === "label" ? 1.04 : 1;
            const auraScale = isHoveringInteractive
                ? (pointerMode === "text" ? 1.14 : 1.06)
                : 0.92;
            const cloudScale = isHoveringInteractive
                ? (pointerMode === "text" ? 1.02 : 1.04)
                : 0.94;
            const cloudOpacity = !isVisible
                ? "0"
                : (isHoveringInteractive
                    ? (pointerMode === "text" ? "0.66" : "0.78")
                    : "0.34");
            const followerOpacity = isVisible && isHoveringInteractive && pointerMode === "label"
                ? "1"
                : "0";
            const auraOpacity = !isVisible
                ? "0"
                : (isHoveringInteractive
                    ? (pointerMode === "text" ? "0.54" : "0.42")
                    : "0.22");

            cursorCloud.style.transform = `translate3d(${cloudX}px, ${cloudY}px, 0) scale(${cloudScale})`;
            cursorCloud.style.opacity = cloudOpacity;
            cursorFollower.style.transform = `translate3d(${followerX}px, ${followerY}px, 0) scale(${followerScale})`;
            cursorFollower.style.opacity = followerOpacity;
            cursorAura.style.transform = `translate3d(${auraX}px, ${auraY}px, 0) scale(${auraScale})`;
            cursorAura.style.opacity = auraOpacity;
            cursorDot.style.opacity = isVisible ? "1" : "0";

            frameId = window.requestAnimationFrame(renderPointer);
        };

        window.addEventListener("mousemove", handleMouseMove, { passive: true });
        page.addEventListener("mouseenter", handleMouseEnter);
        page.addEventListener("mouseleave", handleMouseLeave);
        pointerCleanup.push(() => window.removeEventListener("mousemove", handleMouseMove));
        pointerCleanup.push(() => page.removeEventListener("mouseenter", handleMouseEnter));
        pointerCleanup.push(() => page.removeEventListener("mouseleave", handleMouseLeave));

        interactiveTargets.forEach((target) => {
            target.addEventListener("pointerenter", handlePointerHoverOn);
            target.addEventListener("pointerleave", handlePointerHoverOff);
            pointerCleanup.push(() => target.removeEventListener("pointerenter", handlePointerHoverOn));
            pointerCleanup.push(() => target.removeEventListener("pointerleave", handlePointerHoverOff));
        });

        frameId = window.requestAnimationFrame(renderPointer);
        pointerCleanup.push(() => window.cancelAnimationFrame(frameId));
        pointerCleanup.push(() => clearPointerFocus());
        pointerCleanup.push(() => document.documentElement.removeAttribute("data-home-public-v6-pointer"));
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
            pointerCleanup.forEach((cleanup) => cleanup());
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
