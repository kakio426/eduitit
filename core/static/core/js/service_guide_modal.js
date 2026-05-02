(function () {
    var dataNode = document.getElementById('service-guide-modal-data');
    var modal = document.querySelector('[data-service-guide-modal]');
    if (!dataNode || !modal) {
        return;
    }

    var guides = [];
    try {
        guides = JSON.parse(dataNode.textContent || '[]');
    } catch (error) {
        guides = [];
    }
    if (!Array.isArray(guides) || !guides.length) {
        return;
    }

    var guideById = new Map();
    guides.forEach(function (guide, index) {
        guide.index = index;
        guideById.set(String(guide.id), guide);
    });

    var state = {
        guideIndex: 0,
        slideIndex: 0,
        lastFocus: null,
    };

    var titleNode = document.getElementById('serviceGuideModalTitle');
    var descriptionNode = document.getElementById('serviceGuideModalDescription');
    var serviceListNode = modal.querySelector('[data-service-guide-service-list]');
    var screenFrameNode = modal.querySelector('[data-service-guide-screen-frame]');
    var screenCaptionNode = modal.querySelector('[data-service-guide-screen-caption]');
    var stepLabelNode = modal.querySelector('[data-service-guide-step-label]');
    var badgeNode = modal.querySelector('[data-service-guide-badge]');
    var slideTitleNode = modal.querySelector('[data-service-guide-slide-title]');
    var slideContentNode = modal.querySelector('[data-service-guide-slide-content]');
    var focusNoteNode = modal.querySelector('[data-service-guide-focus-note]');
    var pointsNode = modal.querySelector('[data-service-guide-points]');
    var dotsNode = modal.querySelector('[data-service-guide-dots]');
    var prevButton = modal.querySelector('[data-service-guide-prev]');
    var nextButton = modal.querySelector('[data-service-guide-next]');
    var launchLink = modal.querySelector('[data-service-guide-launch]');

    function text(value) {
        return typeof value === 'string' ? value : '';
    }

    function escapeHtml(value) {
        return text(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function clampNumber(value, fallback, min, max) {
        var number = Number(value);
        if (!Number.isFinite(number)) {
            number = fallback;
        }
        return Math.min(Math.max(number, min), max);
    }

    function getFocus(slide) {
        var focus = slide && typeof slide.focus === 'object' ? slide.focus : {};
        var rect = focus && typeof focus.rect === 'object' ? focus.rect : {};
        var x = clampNumber(rect.x, 12, 0, 92);
        var y = clampNumber(rect.y, 16, 0, 88);
        var width = clampNumber(rect.w, 42, 8, 92 - x);
        var height = clampNumber(rect.h, 34, 8, 88 - y);
        var zoom = clampNumber(focus.zoom, 2.35, 1.4, 3.4);
        return {
            label: text(focus.label) || '확대 포인트',
            title: text(focus.title) || '지금 볼 부분',
            hint: text(focus.hint) || '강조된 영역에서 이 단계의 핵심 조작을 확인합니다.',
            rect: {
                x: x,
                y: y,
                w: width,
                h: height,
                cx: x + (width / 2),
                cy: y + (height / 2),
            },
            zoom: zoom,
        };
    }

    function cssUrl(value) {
        return text(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    }

    function getCurrentGuide() {
        return guides[state.guideIndex] || guides[0];
    }

    function getCurrentSlides() {
        var guide = getCurrentGuide();
        return Array.isArray(guide.slides) && guide.slides.length ? guide.slides : [];
    }

    function getCurrentSlide() {
        var slides = getCurrentSlides();
        return slides[state.slideIndex] || slides[0] || {};
    }

    function setChanging() {
        modal.classList.add('is-changing');
        window.setTimeout(function () {
            modal.classList.remove('is-changing');
        }, 170);
    }

    function renderServices() {
        if (!serviceListNode) {
            return;
        }
        serviceListNode.innerHTML = guides.map(function (guide, index) {
            var activeClass = index === state.guideIndex ? ' is-active' : '';
            var count = Number(guide.slideCount || (guide.slides || []).length || 0);
            return [
                '<button type="button" class="service-guide-modal__service-button' + activeClass + '" data-service-guide-service-id="' + escapeHtml(String(guide.id)) + '">',
                '<span class="service-guide-modal__service-name">' + escapeHtml(guide.serviceName || guide.title || '서비스') + '</span>',
                '<span class="service-guide-modal__service-count">' + count + '단계</span>',
                '</button>',
            ].join('');
        }).join('');
    }

    function renderDots() {
        var slides = getCurrentSlides();
        if (!dotsNode) {
            return;
        }
        dotsNode.innerHTML = slides.map(function (_slide, index) {
            var activeClass = index === state.slideIndex ? ' is-active' : '';
            return '<button type="button" class="service-guide-modal__dot' + activeClass + '" data-service-guide-slide-index="' + index + '" aria-label="' + (index + 1) + '단계로 이동"></button>';
        }).join('');
    }

    function renderScreenshot(slide, guide) {
        if (!screenFrameNode) {
            return;
        }
        var screenshotUrl = text(slide.screenshotUrl);
        if (screenshotUrl) {
            var focus = getFocus(slide);
            var style = [
                '--focus-x:' + focus.rect.x + '%;',
                '--focus-y:' + focus.rect.y + '%;',
                '--focus-w:' + focus.rect.w + '%;',
                '--focus-h:' + focus.rect.h + '%;',
                '--focus-cx:' + focus.rect.cx + '%;',
                '--focus-cy:' + focus.rect.cy + '%;',
                '--zoom-size:' + Math.round(focus.zoom * 100) + '%;',
                '--zoom-x:' + focus.rect.cx + '%;',
                '--zoom-y:' + focus.rect.cy + '%;',
            ].join('');
            screenFrameNode.innerHTML = [
                '<div class="service-guide-modal__screen-stage" style="' + style + '">',
                '<img src="' + escapeHtml(screenshotUrl) + '" alt="' + escapeHtml(slide.screenshotAlt || guide.serviceName || '서비스 화면') + '" loading="eager">',
                '<span class="service-guide-modal__spotlight" aria-hidden="true"></span>',
                '<span class="service-guide-modal__focus-pin" aria-hidden="true"></span>',
                '<aside class="service-guide-modal__zoom-card" aria-label="' + escapeHtml(focus.title) + '">',
                '<div class="service-guide-modal__zoom-label"><i class="fa-solid fa-magnifying-glass-plus"></i> ' + escapeHtml(focus.label) + '</div>',
                '<div class="service-guide-modal__zoom-image" style="background-image:url(&quot;' + cssUrl(screenshotUrl) + '&quot;);"></div>',
                '<strong>' + escapeHtml(focus.title) + '</strong>',
                '<p>' + escapeHtml(focus.hint) + '</p>',
                '</aside>',
                '</div>',
            ].join('');
        } else {
            screenFrameNode.innerHTML = [
                '<div class="service-guide-modal__screen-placeholder">',
                '<div>',
                '<i class="fa-regular fa-image"></i>',
                '<p>실제 화면 캡처 준비 중</p>',
                '</div>',
                '</div>',
            ].join('');
        }
        if (screenCaptionNode) {
            screenCaptionNode.textContent = screenshotUrl ? (guide.serviceName + ' 실제 화면') : '화면 캡처 없음';
        }
    }

    function renderFocusNote(slide) {
        if (!focusNoteNode) {
            return;
        }
        var focus = getFocus(slide);
        focusNoteNode.hidden = false;
        focusNoteNode.innerHTML = [
            '<span>' + escapeHtml(focus.label) + '</span>',
            '<strong>' + escapeHtml(focus.title) + '</strong>',
            '<p>' + escapeHtml(focus.hint) + '</p>',
        ].join('');
    }

    function renderPoints(slide) {
        if (!pointsNode) {
            return;
        }
        var points = Array.isArray(slide.points) ? slide.points.filter(Boolean) : [];
        pointsNode.innerHTML = points.map(function (point) {
            return '<li>' + escapeHtml(point) + '</li>';
        }).join('');
    }

    function syncLaunch(guide) {
        if (!launchLink) {
            return;
        }
        if (!guide.launchHref) {
            launchLink.hidden = true;
            return;
        }
        launchLink.hidden = false;
        launchLink.href = guide.launchHref;
        launchLink.innerHTML = escapeHtml(guide.launchLabel || '서비스 열기') + ' <i class="fa-solid fa-arrow-up-right-from-square"></i>';
        if (guide.launchIsExternal) {
            launchLink.target = '_blank';
            launchLink.rel = 'noopener noreferrer';
        } else {
            launchLink.removeAttribute('target');
            launchLink.removeAttribute('rel');
        }
    }

    function renderSlide(options) {
        var guide = getCurrentGuide();
        var slides = getCurrentSlides();
        var slide = getCurrentSlide();
        if (options && options.animate) {
            setChanging();
        }

        if (titleNode) {
            titleNode.textContent = guide.title || guide.serviceName || '서비스 이용방법';
        }
        if (descriptionNode) {
            descriptionNode.textContent = guide.description || '';
        }
        if (stepLabelNode) {
            stepLabelNode.textContent = slide.stepLabel || ((state.slideIndex + 1) + '/' + slides.length);
        }
        if (badgeNode) {
            badgeNode.textContent = slide.badge || '';
        }
        if (slideTitleNode) {
            slideTitleNode.textContent = slide.title || '시작';
        }
        if (slideContentNode) {
            slideContentNode.textContent = slide.content || '';
        }

        renderServices();
        renderDots();
        renderScreenshot(slide, guide);
        renderFocusNote(slide);
        renderPoints(slide);
        syncLaunch(guide);

        if (prevButton) {
            prevButton.disabled = state.slideIndex <= 0;
        }
        if (nextButton) {
            nextButton.disabled = state.slideIndex >= slides.length - 1;
        }
    }

    function openGuideModal(manualId, slideIndex) {
        var guide = guideById.get(String(manualId)) || guides[0];
        state.guideIndex = guide.index || 0;
        state.slideIndex = Math.max(0, Number(slideIndex || 0));
        state.lastFocus = document.activeElement;
        modal.hidden = false;
        document.body.classList.add('service-guide-modal-open');
        renderSlide({ animate: false });
        window.requestAnimationFrame(function () {
            modal.classList.add('is-open');
            var closeButton = modal.querySelector('[data-service-guide-close]');
            if (closeButton) {
                closeButton.focus({ preventScroll: true });
            }
        });
    }

    function closeGuideModal() {
        modal.classList.remove('is-open');
        document.body.classList.remove('service-guide-modal-open');
        window.setTimeout(function () {
            modal.hidden = true;
            if (state.lastFocus && typeof state.lastFocus.focus === 'function') {
                state.lastFocus.focus({ preventScroll: true });
            }
        }, 180);
    }

    function goToSlide(nextIndex) {
        var slides = getCurrentSlides();
        var maxIndex = Math.max(0, slides.length - 1);
        state.slideIndex = Math.min(Math.max(0, nextIndex), maxIndex);
        renderSlide({ animate: true });
    }

    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('[data-service-guide-trigger]');
        if (trigger) {
            var manualId = trigger.getAttribute('data-service-guide-trigger');
            if (guideById.has(String(manualId))) {
                event.preventDefault();
                openGuideModal(manualId, 0);
                return;
            }
        }

        if (event.target.closest('[data-service-guide-close]')) {
            event.preventDefault();
            closeGuideModal();
            return;
        }

        var serviceButton = event.target.closest('[data-service-guide-service-id]');
        if (serviceButton) {
            var guide = guideById.get(String(serviceButton.getAttribute('data-service-guide-service-id')));
            if (guide) {
                state.guideIndex = guide.index || 0;
                state.slideIndex = 0;
                renderSlide({ animate: true });
            }
            return;
        }

        var dotButton = event.target.closest('[data-service-guide-slide-index]');
        if (dotButton) {
            goToSlide(Number(dotButton.getAttribute('data-service-guide-slide-index') || 0));
        }
    });

    if (prevButton) {
        prevButton.addEventListener('click', function () {
            goToSlide(state.slideIndex - 1);
        });
    }
    if (nextButton) {
        nextButton.addEventListener('click', function () {
            goToSlide(state.slideIndex + 1);
        });
    }

    document.addEventListener('keydown', function (event) {
        if (modal.hidden) {
            return;
        }
        if (event.key === 'Escape') {
            event.preventDefault();
            closeGuideModal();
        } else if (event.key === 'ArrowLeft') {
            event.preventDefault();
            goToSlide(state.slideIndex - 1);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            goToSlide(state.slideIndex + 1);
        }
    });

    window.openServiceGuide = openGuideModal;

    document.addEventListener('DOMContentLoaded', function () {
        var autostartId = modal.getAttribute('data-service-guide-autostart');
        if (autostartId && guideById.has(String(autostartId))) {
            openGuideModal(autostartId, 0);
        }
    });
})();
