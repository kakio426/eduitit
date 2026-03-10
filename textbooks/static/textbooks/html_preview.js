(function () {
    const FRAME_SANDBOX = 'allow-scripts allow-forms allow-downloads';
    const BASE_STYLE_BLOCK = [
        'html, body { margin: 0; min-height: 100%; background: #ffffff; overflow: auto; }',
        '* { box-sizing: border-box; }',
        'body { -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }',
        'img, svg, canvas, video, iframe { max-width: 100%; }',
        'button, input, select, textarea { font: inherit; }'
    ].join('\n');

    function debounce(fn, wait) {
        let timer = null;
        return function debounced() {
            const args = arguments;
            clearTimeout(timer);
            timer = window.setTimeout(function () {
                fn.apply(null, args);
            }, wait);
        };
    }

    function readJsonScript(id) {
        if (!id) {
            return '';
        }
        const el = document.getElementById(id);
        if (!el) {
            return '';
        }
        try {
            return JSON.parse(el.textContent);
        } catch (error) {
            return '';
        }
    }

    function injectBaseHead(documentHtml) {
        const additions = '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>' + BASE_STYLE_BLOCK + '</style>';
        let output = documentHtml;
        if (!/<!doctype/i.test(output)) {
            output = '<!doctype html>\n' + output;
        }
        if (/<head[^>]*>/i.test(output)) {
            return output.replace(/<head([^>]*)>/i, '<head$1>' + additions);
        }
        if (/<html[^>]*>/i.test(output)) {
            return output.replace(/<html([^>]*)>/i, '<html$1><head>' + additions + '</head>');
        }
        return '<!doctype html><html lang="ko"><head>' + additions + '</head><body>' + output + '</body></html>';
    }

    function buildPreviewDocument(rawHtml) {
        const trimmed = (rawHtml || '').trim();
        if (!trimmed) {
            return '';
        }
        if (/<(html|head|body)\b/i.test(trimmed) || /<!doctype/i.test(trimmed)) {
            return injectBaseHead(trimmed);
        }
        return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>' + BASE_STYLE_BLOCK + '</style></head><body>' + trimmed + '</body></html>';
    }

    function buildPopupDocument(previewDocument, viewport) {
        return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>교육 자료실 새 창 미리보기</title><style>' +
            'body{margin:0;font-family:"Pretendard","Noto Sans KR",sans-serif;background:linear-gradient(180deg,#eaf2ff,#f8fbff);color:#0f172a}' +
            '.shell{min-height:100vh;display:grid;grid-template-rows:auto 1fr;padding:20px;gap:16px}' +
            '.toolbar{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;background:rgba(255,255,255,.92);border:1px solid rgba(148,163,184,.2);box-shadow:0 20px 40px rgba(15,23,42,.08);padding:16px 18px;border-radius:24px}' +
            '.toggle{border:1px solid rgba(148,163,184,.22);background:#fff;color:#334155;font-weight:800;border-radius:999px;padding:10px 14px;margin-right:8px;cursor:pointer}' +
            '.toggle.is-active{background:#0f172a;color:#fff;border-color:#0f172a}' +
            '.stage{background:rgba(255,255,255,.78);border:1px solid rgba(148,163,184,.2);border-radius:28px;padding:16px;overflow:hidden;box-shadow:0 24px 60px rgba(15,23,42,.08)}' +
            '.device{width:100%;max-width:none;height:calc(100vh - 168px);min-height:640px;border-radius:24px;border:1px solid rgba(148,163,184,.24);overflow:hidden;background:#fff;box-shadow:0 20px 40px rgba(15,23,42,.12);margin:0 auto;transition:width .2s ease,max-width .2s ease}' +
            'body[data-viewport="mobile"] .device{width:390px;max-width:100%}' +
            'iframe{display:block;width:100%;height:100%;border:0;background:#fff}' +
            '@media (max-width: 767px){.shell{padding:12px}.device{height:calc(100vh - 152px);min-height:520px}}' +
            '</style></head><body data-viewport="' + viewport + '"><div class="shell"><div class="toolbar"><div><strong>교육 자료실 새 창 미리보기</strong><div style="color:#475569;margin-top:4px;font-size:14px;">현재 코드를 독립된 창에서 확인합니다.</div></div><div><button type="button" class="toggle" data-popup-viewport="desktop">데스크탑</button><button type="button" class="toggle" data-popup-viewport="mobile">모바일</button></div></div><div class="stage"><div class="device"><iframe id="popup-preview-frame" sandbox="' + FRAME_SANDBOX + '"></iframe></div></div></div><script>' +
            'const frame=document.getElementById("popup-preview-frame");frame.srcdoc=' + JSON.stringify(previewDocument) + ';' +
            'const buttons=Array.from(document.querySelectorAll("[data-popup-viewport]"));' +
            'function setViewport(mode){document.body.dataset.viewport=mode;buttons.forEach(function(btn){btn.classList.toggle("is-active",btn.dataset.popupViewport===mode);});}' +
            'buttons.forEach(function(btn){btn.addEventListener("click",function(){setViewport(btn.dataset.popupViewport);});});' +
            'setViewport(' + JSON.stringify(viewport) + ');' +
            '<' + '/script></body></html>';
    }

    function setStatus(el, message) {
        if (el) {
            el.textContent = message;
        }
    }

    function createPreviewController(root) {
        if (!root) {
            return null;
        }
        const frame = root.querySelector('[data-preview-frame]');
        const emptyState = root.querySelector('[data-preview-empty]');
        const status = root.querySelector('[data-preview-status]');
        const refreshButton = root.querySelector('[data-preview-refresh]');
        const sampleButton = root.querySelector('[data-preview-sample]');
        const popupButton = root.querySelector('[data-preview-open-window]');
        const viewportButtons = Array.from(root.querySelectorAll('[data-preview-viewport]'));
        const sourceInputId = root.dataset.previewSourceInputId || '';
        const sourceInput = sourceInputId ? document.getElementById(sourceInputId) : null;
        const initialHtml = readJsonScript(root.dataset.previewInitialScriptId || '');
        const sampleHtml = readJsonScript(root.dataset.previewSampleScriptId || '');
        let currentHtml = sourceInput ? sourceInput.value : initialHtml;
        let disabled = root.dataset.previewDisabled === 'true';

        function setViewport(mode) {
            root.dataset.previewViewport = mode;
            viewportButtons.forEach(function (button) {
                button.classList.toggle('is-active', button.dataset.previewViewport === mode);
            });
        }

        function setEmpty(message) {
            root.dataset.previewHasContent = 'false';
            if (emptyState) {
                emptyState.textContent = message;
            }
            if (frame) {
                frame.removeAttribute('srcdoc');
            }
        }

        function render(rawHtml) {
            currentHtml = rawHtml || '';
            if (disabled) {
                setEmpty(root.dataset.previewDisabledMessage || 'HTML 자료 탭에서 sandbox preview를 사용할 수 있습니다.');
                setStatus(status, root.dataset.previewDisabledMessage || 'HTML 자료 탭에서 sandbox preview를 사용할 수 있습니다.');
                return;
            }
            if (!currentHtml.trim()) {
                setEmpty(root.dataset.previewEmptyMessage || '제미나이에서 만든 HTML 코드를 붙여넣으면 여기에서 바로 확인할 수 있습니다.');
                setStatus(status, '코드를 붙여넣으면 바로 아래에서 비율과 버튼 위치를 확인할 수 있습니다.');
                return;
            }
            const previewDocument = buildPreviewDocument(currentHtml);
            if (!previewDocument) {
                setEmpty('미리보기를 만들지 못했습니다.');
                setStatus(status, 'HTML 코드를 다시 확인해 주세요.');
                return;
            }
            root.dataset.previewHasContent = 'true';
            setStatus(status, '미리보기를 다시 그리는 중입니다.');
            frame.srcdoc = previewDocument;
        }

        function setDisabled(nextDisabled, message) {
            disabled = !!nextDisabled;
            root.dataset.previewDisabled = disabled ? 'true' : 'false';
            if (message) {
                root.dataset.previewDisabledMessage = message;
            }
            render(sourceInput ? sourceInput.value : currentHtml);
        }

        if (frame) {
            frame.addEventListener('load', function () {
                if (root.dataset.previewHasContent === 'true' && root.dataset.previewDisabled !== 'true') {
                    setStatus(status, '렌더링을 마쳤습니다. 외부 리소스는 브라우저 정책에 따라 일부 다르게 보일 수 있습니다.');
                }
            });
        }

        if (sourceInput) {
            sourceInput.addEventListener('input', debounce(function () {
                render(sourceInput.value);
            }, 240));
        }
        if (refreshButton) {
            refreshButton.addEventListener('click', function () {
                render(sourceInput ? sourceInput.value : currentHtml);
            });
        }
        if (sampleButton && sourceInput) {
            sampleButton.addEventListener('click', function () {
                sourceInput.value = sampleHtml || '';
                render(sourceInput.value);
                sourceInput.focus();
            });
        }
        if (popupButton) {
            popupButton.addEventListener('click', function () {
                const previewDocument = buildPreviewDocument(sourceInput ? sourceInput.value : currentHtml);
                if (!previewDocument) {
                    setStatus(status, '새 창으로 확인할 코드가 아직 없습니다.');
                    return;
                }
                const popup = window.open('', '_blank', 'noopener,noreferrer,width=1440,height=960');
                if (!popup) {
                    setStatus(status, '팝업이 차단되어 새 창을 열지 못했습니다.');
                    return;
                }
                popup.document.open();
                popup.document.write(buildPopupDocument(previewDocument, root.dataset.previewViewport || 'desktop'));
                popup.document.close();
            });
        }
        viewportButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                setViewport(button.dataset.previewViewport);
            });
        });

        setViewport(root.dataset.previewViewport || 'desktop');
        render(currentHtml);

        root.__textbooksPreview = {
            render: render,
            setDisabled: setDisabled,
        };
        return root.__textbooksPreview;
    }

    function initCreateRoot() {
        const root = document.querySelector('[data-textbooks-create-root]');
        if (!root) {
            return;
        }
        const hiddenInput = root.querySelector('[data-create-source-type]');
        const modeButtons = Array.from(root.querySelectorAll('[data-create-mode]'));
        const pdfPanel = root.querySelector('[data-create-pdf-panel]');
        const pdfInput = root.querySelector('[data-create-pdf-input]');
        const contentLabel = root.querySelector('[data-create-content-label]');
        const contentHelp = root.querySelector('[data-create-content-help]');
        const contentInput = root.querySelector('[data-create-content-input]');
        const previewHost = document.querySelector('[data-create-preview-root]');
        const previewRoot = previewHost ? previewHost.querySelector('[data-textbooks-html-preview]') : null;
        const previewController = previewRoot ? previewRoot.__textbooksPreview : null;

        function setMode(mode) {
            root.dataset.mode = mode;
            if (hiddenInput) {
                hiddenInput.value = mode;
            }
            modeButtons.forEach(function (button) {
                button.classList.toggle('is-active', button.dataset.createMode === mode);
            });
            if (pdfPanel) {
                pdfPanel.classList.toggle('hidden', mode !== 'pdf');
            }
            if (pdfInput) {
                pdfInput.required = mode === 'pdf';
                if (mode !== 'pdf') {
                    pdfInput.value = '';
                }
            }
            if (!contentInput || !contentLabel || !contentHelp) {
                return;
            }
            if (mode === 'html') {
                contentLabel.textContent = 'Gemini 코드 붙여넣기';
                contentHelp.textContent = '제미나이에서 만든 전체 HTML 코드를 붙여넣으면 오른쪽 sandbox preview에 바로 반영됩니다.';
                contentInput.placeholder = '<!doctype html>부터 전체 코드를 붙여넣어 주세요.';
                contentInput.required = true;
                if (previewController) {
                    previewController.setDisabled(false);
                }
                return;
            }
            if (mode === 'pdf') {
                contentLabel.textContent = '메모 (선택)';
                contentHelp.textContent = 'PDF 자료에 대한 교사용 메모만 적습니다. PDF 자체는 오른쪽 미리보기 대상이 아닙니다.';
                contentInput.placeholder = '수업 메모나 안내를 적어 주세요.';
                contentInput.required = false;
                if (previewController) {
                    previewController.setDisabled(true, 'HTML 자료 탭에서 sandbox preview를 사용할 수 있습니다.');
                }
                return;
            }
            contentLabel.textContent = '내용';
            contentHelp.textContent = '텍스트 자료는 저장 후 상세 화면에서 읽기용으로 확인합니다.';
            contentInput.placeholder = '학생에게 보여 줄 글이나 교사용 정리 내용을 적어 주세요.';
            contentInput.required = false;
            if (previewController) {
                previewController.setDisabled(true, '텍스트 자료는 저장 후 상세 화면에서 읽기용으로 확인합니다.');
            }
        }

        modeButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                setMode(button.dataset.createMode);
            });
        });

        setMode(root.dataset.initialMode || 'html');
    }

    document.addEventListener('DOMContentLoaded', function () {
        Array.from(document.querySelectorAll('[data-textbooks-html-preview]')).forEach(createPreviewController);
        initCreateRoot();
    });

    window.TextbooksHtmlPreview = {
        buildPreviewDocument: buildPreviewDocument,
    };
})();



