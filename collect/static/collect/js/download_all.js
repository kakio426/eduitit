/**
 * JSZip 기반 일괄 다운로드
 * - 파일 URL들을 fetch → ZIP 생성 → 브라우저 다운로드
 * - 진행 상태 표시
 */
async function downloadAllFiles() {
    var files = window.collectFiles || [];
    var title = window.collectTitle || '수합_파일';

    if (files.length === 0) {
        alert('다운로드할 파일이 없습니다.');
        return;
    }

    var btn = document.getElementById('download-all-btn');
    var label = document.getElementById('download-label');
    if (btn) btn.disabled = true;

    var zip = new JSZip();
    var completed = 0;

    for (var i = 0; i < files.length; i++) {
        var file = files[i];
        if (label) {
            label.textContent = '다운로드 중... ' + (completed + 1) + '/' + files.length;
        }

        try {
            var response = await fetch(file.url);
            if (!response.ok) {
                console.error('Failed to fetch:', file.name);
                continue;
            }
            var blob = await response.blob();
            // 파일명에 제출자 이름 붙이기: "홍길동_보고서.hwp"
            var fileName = file.contributor + '_' + file.name;
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
            console.error('Error downloading file:', file.name, err);
        }
    }

    if (completed === 0) {
        alert('다운로드에 실패했습니다.');
        if (btn) btn.disabled = false;
        if (label) label.textContent = '전체 파일 다운로드 (ZIP)';
        return;
    }

    if (label) label.textContent = 'ZIP 파일 생성 중...';

    try {
        var content = await zip.generateAsync({ type: 'blob' });
        var url = URL.createObjectURL(content);
        var a = document.createElement('a');
        a.href = url;
        a.download = title + '_제출파일.zip';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('ZIP generation error:', err);
        alert('ZIP 파일 생성 중 오류가 발생했습니다.');
    }

    if (btn) btn.disabled = false;
    if (label) label.textContent = '전체 파일 다운로드 (ZIP)';
}
