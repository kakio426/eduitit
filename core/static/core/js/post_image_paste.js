(function() {
    'use strict';

    const textarea = document.getElementById('post-content-textarea');
    const fileInput = document.getElementById('post-image-input');
    const previewContainer = document.getElementById('image-preview-container');
    const previewImage = document.getElementById('image-preview');
    const removeBtn = document.getElementById('remove-image-btn');

    // 로그인 사용자만 실행
    if (!textarea || !fileInput) return;

    // 이미지 검증
    function validateImage(file) {
        const MAX_SIZE = 10 * 1024 * 1024; // 10MB
        const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];

        if (!ALLOWED_TYPES.includes(file.type)) {
            alert('이미지 파일만 업로드 가능합니다 (JPEG, PNG, GIF, WebP)');
            return false;
        }
        if (file.size > MAX_SIZE) {
            alert('이미지 크기는 10MB 이하만 가능합니다');
            return false;
        }
        return true;
    }

    // 이미지 최적화 함수
    async function optimizeImage(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    // Canvas로 리사이징
                    const MAX_DIMENSION = 1920;
                    let width = img.width;
                    let height = img.height;

                    // 비율 유지하며 리사이징
                    if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
                        if (width > height) {
                            height = (height / width) * MAX_DIMENSION;
                            width = MAX_DIMENSION;
                        } else {
                            width = (width / height) * MAX_DIMENSION;
                            height = MAX_DIMENSION;
                        }
                    }

                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    // JPEG로 변환 (85% 품질)
                    canvas.toBlob(
                        (blob) => {
                            if (blob) {
                                const optimizedFile = new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), {
                                    type: 'image/jpeg',
                                    lastModified: Date.now()
                                });

                                // 최적화 후에도 10MB 초과 시 에러
                                if (optimizedFile.size > 10 * 1024 * 1024) {
                                    alert('이미지가 너무 큽니다. 다른 이미지를 선택해주세요.');
                                    reject(new Error('File too large after optimization'));
                                } else {
                                    console.log(`이미지 최적화 완료: ${(file.size / 1024 / 1024).toFixed(2)}MB → ${(optimizedFile.size / 1024 / 1024).toFixed(2)}MB`);
                                    resolve(optimizedFile);
                                }
                            } else {
                                reject(new Error('Canvas to Blob failed'));
                            }
                        },
                        'image/jpeg',
                        0.85  // 85% 품질
                    );
                };
                img.onerror = () => reject(new Error('Image load failed'));
                img.src = e.target.result;
            };
            reader.onerror = () => reject(new Error('FileReader failed'));
            reader.readAsDataURL(file);
        });
    }

    // 미리보기 표시
    function showPreview(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            previewContainer.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }

    // 붙여넣기 이벤트 (최적화 적용)
    textarea.addEventListener('paste', async (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;

        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') === 0) {
                e.preventDefault();
                const file = items[i].getAsFile();

                if (file && validateImage(file)) {
                    try {
                        // 이미지 최적화
                        const optimizedFile = await optimizeImage(file);

                        // file input에 최적화된 이미지 할당
                        const dataTransfer = new DataTransfer();
                        dataTransfer.items.add(optimizedFile);
                        fileInput.files = dataTransfer.files;

                        showPreview(optimizedFile);
                    } catch (error) {
                        console.error('이미지 최적화 실패:', error);
                        alert('이미지 처리에 실패했습니다. 다시 시도해주세요.');
                    }
                }
                break;
            }
        }
    });

    // 파일 선택 버튼 (최적화 적용)
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file && validateImage(file)) {
            try {
                // 이미지 최적화
                const optimizedFile = await optimizeImage(file);

                // file input에 최적화된 이미지 재할당
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(optimizedFile);
                fileInput.files = dataTransfer.files;

                showPreview(optimizedFile);
            } catch (error) {
                console.error('이미지 최적화 실패:', error);
                alert('이미지 처리에 실패했습니다. 다시 시도해주세요.');
            }
        }
    });

    // 미리보기 삭제
    removeBtn.addEventListener('click', () => {
        previewContainer.classList.add('hidden');
        fileInput.value = '';
        previewImage.src = '';
    });

    // HTMX 폼 제출 후 미리보기 초기화
    document.body.addEventListener('htmx:afterRequest', (event) => {
        // post_create 요청이 성공한 경우에만 초기화
        if (event.detail.successful && event.detail.pathInfo.requestPath.includes('post/create')) {
            previewContainer.classList.add('hidden');
            fileInput.value = '';
            previewImage.src = '';
        }
    });
})();
