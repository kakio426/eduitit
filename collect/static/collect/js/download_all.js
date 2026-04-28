/**
 * JSZip 기반 일괄 다운로드
 * - 파일 URL들을 fetch → ZIP 생성 → 브라우저 다운로드
 * - 진행 상태 표시
 */
async function downloadAllFiles() {
    var files = window.collectFiles || [];
    var title = window.collectTitle || '수합_파일';

    if (files.length === 0) {
        setDownloadStatus('파일 확인', true);
        return;
    }

    if (typeof JSZip === 'undefined') {
        setDownloadStatus('다시 시도', true);
        return;
    }

    var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-download-all-button]'));
    var labels = Array.prototype.slice.call(document.querySelectorAll('[data-download-label]'));
    setButtonsDisabled(buttons, true);

    var zip = new JSZip();
    var completed = 0;

    try {
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            setDownloadLabels(labels, '다운로드 중 ' + (i + 1) + '/' + files.length);

            try {
                var response = await fetch(file.url, { credentials: 'same-origin' });
                if (!response.ok) {
                    console.warn('collect-download-failed', file.name, response.status);
                    continue;
                }
                var blob = await response.blob();
                if (!blob || blob.size === 0) {
                    console.warn('collect-download-empty', file.name);
                    continue;
                }
                // 파일명에 제출자 이름 붙이기: "홍길동_보고서.hwp"
                var fileName = sanitizeZipName(file.contributor + '_' + file.name);
                // 중복 방지
                var baseName = fileName;
                var counter = 1;
                while (zip.files[fileName]) {
                    var parts = baseName.split('.');
                    if (parts.length > 1) {
                        var ext = parts.pop();
                        fileName = parts.join('.') + '_' + counter + '.' + ext;
                    } else {
                        fileName = baseName + '_' + counter;
                    }
                    counter++;
                }
                zip.file(fileName, blob);
                completed++;
            } catch (err) {
                console.warn('collect-download-error', file.name, err);
            }
        }

        if (completed === 0) {
            setDownloadStatus('다운로드 실패', true);
            return;
        }

        setDownloadLabels(labels, 'ZIP 생성 중');

        var content = await zip.generateAsync({ type: 'blob' });
        var url = URL.createObjectURL(content);
        var a = document.createElement('a');
        a.href = url;
        a.download = title + '_제출파일.zip';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setDownloadStatus('다운로드 시작', false);
    } catch (err) {
        console.warn('collect-zip-generation-error', err);
        setDownloadStatus('다시 시도', true);
    } finally {
        setButtonsDisabled(buttons, false);
        setDownloadLabels(labels, '제출 파일 받기');
    }
}

function setButtonsDisabled(buttons, disabled) {
    buttons.forEach(function (button) {
        button.disabled = disabled;
    });
}

function setDownloadLabels(labels, text) {
    labels.forEach(function (label) {
        label.textContent = text;
    });
}

function sanitizeZipName(value) {
    return String(value || '제출파일').replace(/[\\/:*?"<>|]/g, '_').trim() || '제출파일';
}

function setDownloadStatus(message, isError) {
    if (typeof window.setCollectStatus === 'function') {
        window.setCollectStatus(message, isError ? 'error' : 'success');
    }
}
