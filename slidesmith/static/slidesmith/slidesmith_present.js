import Reveal from "./vendor/revealjs/dist/reveal.esm.js";

function initSlidesmithPresentation() {
  const revealRoot = document.querySelector(".reveal");
  if (!revealRoot) {
    return;
  }

  const status = document.getElementById("slidesmith-presentation-status");
  const guide = document.getElementById("slidesmith-print-guide");
  const guideButton = document.getElementById("slidesmith-print-guide-button");

  const deck = new Reveal(revealRoot, {
    controls: true,
    progress: true,
    center: false,
    hash: false,
    transition: "slide",
    backgroundTransition: "fade",
    margin: 0.08,
  });

  deck.initialize().then(() => {
    const updateStatus = () => {
      const current = deck.getIndices().h + 1;
      const total = deck.getTotalSlides();
      const currentSlide = deck.getCurrentSlide();
      const label = currentSlide ? currentSlide.dataset.slideLabel : "";
      if (status) {
        status.textContent = `${current} / ${total}장 · ${label}`;
      }
    };

    updateStatus();
    deck.on("slidechanged", updateStatus);
    deck.on("ready", updateStatus);
  });

  if (guideButton && guide) {
    guideButton.addEventListener("click", () => {
      const isHidden = guide.hasAttribute("hidden");
      if (isHidden) {
        guide.removeAttribute("hidden");
      } else {
        guide.setAttribute("hidden", "hidden");
      }
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initSlidesmithPresentation);
} else {
  initSlidesmithPresentation();
}
