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

    if (page && supportsFinePointer && !prefersReducedMotion && cursorDot && cursorFollower && cursorAura) {
        document.documentElement.setAttribute("data-home-public-v6-pointer", "true");

        let mouseX = window.innerWidth * 0.5;
        let mouseY = window.innerHeight * 0.5;
        let followerX = mouseX;
        let followerY = mouseY;
        let auraX = mouseX;
        let auraY = mouseY;
        let frameId = 0;

        page.dataset.pointerVisible = "false";
        page.dataset.pointerHover = "false";
        page.dataset.pointerTone = "violet";

        const interactiveTargets = Array.from(page.querySelectorAll("a, button"));

        const resolvePointerLabel = (target) => {
            if (!target) return "열기";
            if (target.matches(".home-public-v6-brand")) return "홈";
            if (target.matches(".home-public-v6-primary-link, .home-public-v6-login-link")) return "시작";
            if (target.matches(".home-public-v6-secondary-link, .home-public-v6-header-link")) return "탐색";
            if (target.matches(".home-public-v6-preview-login")) return "로그인";
            return "열기";
        };

        const resolvePointerTone = (target) => {
            if (!target) return "violet";
            if (target.matches(".home-public-v6-secondary-link, .home-public-v6-header-link")) return "lilac";
            if (target.matches(".home-public-v6-preview-login")) return "ink";
            if (target.matches(".home-public-v6-preview-item, .home-public-v6-bento-card, .home-public-v6-group-item")) return "plum";
            if (target.matches(".home-public-v6-brand, .home-public-v6-login-link")) return "ink";
            return "violet";
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
        };

        const handlePointerHoverOn = (event) => {
            const target = event.currentTarget;
            page.dataset.pointerHover = "true";
            page.dataset.pointerTone = resolvePointerTone(target);
            if (cursorLabel) {
                cursorLabel.textContent = resolvePointerLabel(target);
            }
        };

        const handlePointerHoverOff = () => {
            page.dataset.pointerHover = "false";
            page.dataset.pointerTone = "violet";
            if (cursorLabel) {
                cursorLabel.textContent = "열기";
            }
        };

        const renderPointer = () => {
            followerX += (mouseX - followerX) * 0.18;
            followerY += (mouseY - followerY) * 0.18;
            auraX += (mouseX - auraX) * 0.08;
            auraY += (mouseY - auraY) * 0.08;

            const isVisible = page.dataset.pointerVisible === "true";
            const isHoveringInteractive = page.dataset.pointerHover === "true";
            const followerScale = isHoveringInteractive ? 2.15 : 1;
            const auraScale = isHoveringInteractive ? 1.26 : 1;

            cursorFollower.style.transform = `translate3d(${followerX}px, ${followerY}px, 0) scale(${followerScale})`;
            cursorFollower.style.opacity = isVisible ? "1" : "0";
            cursorAura.style.transform = `translate3d(${auraX}px, ${auraY}px, 0) scale(${auraScale})`;
            cursorAura.style.opacity = isVisible ? (isHoveringInteractive ? "0.96" : "0.62") : "0";
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
