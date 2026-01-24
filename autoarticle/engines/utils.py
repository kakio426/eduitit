import os
import uuid
import json
import tempfile
import requests
from io import BytesIO
from .constants import IMAGE_DIR


def get_image_data(img_path):
    """
    이미지 경로/URL에서 이미지 데이터를 가져옵니다.
    URL인 경우 다운로드하고, 로컬 파일인 경우 파일을 읽습니다.

    Returns: BytesIO object 또는 None
    """
    if not img_path:
        return None

    try:
        # URL인 경우
        if img_path.startswith(('http://', 'https://')):
            response = requests.get(img_path, timeout=10)
            if response.status_code == 200:
                return BytesIO(response.content)
            return None
        # 로컬 파일인 경우
        elif os.path.exists(img_path):
            with open(img_path, 'rb') as f:
                return BytesIO(f.read())
        return None
    except Exception as e:
        print(f"이미지 로드 실패: {img_path} - {e}")
        return None


def get_valid_images(imgs_raw, max_count=5):
    """
    이미지 목록에서 유효한 이미지들의 BytesIO 객체를 반환합니다.

    Args:
        imgs_raw: JSON 문자열 또는 리스트
        max_count: 최대 이미지 개수

    Returns: list of BytesIO objects
    """
    if not imgs_raw:
        return []

    imgs = json.loads(imgs_raw) if isinstance(imgs_raw, str) else imgs_raw
    if not imgs:
        return []

    valid_images = []
    for img_path in imgs[:max_count]:
        img_data = get_image_data(img_path)
        if img_data:
            valid_images.append(img_data)

    return valid_images


def download_image_to_temp(img_path):
    """
    이미지를 임시 파일로 다운로드합니다. (PDF 엔진용)

    Args:
        img_path: 이미지 URL 또는 로컬 경로

    Returns: 임시 파일 경로 또는 None
    """
    if not img_path:
        return None

    try:
        # URL인 경우
        if img_path.startswith(('http://', 'https://')):
            response = requests.get(img_path, timeout=10)
            if response.status_code == 200:
                # 확장자 추출
                ext = '.jpg'
                if 'png' in img_path.lower():
                    ext = '.png'
                elif 'gif' in img_path.lower():
                    ext = '.gif'
                elif 'webp' in img_path.lower():
                    ext = '.webp'

                # 임시 파일 생성
                temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                temp_file.write(response.content)
                temp_file.close()
                return temp_file.name
            return None
        # 로컬 파일인 경우
        elif os.path.exists(img_path):
            return img_path
        return None
    except Exception as e:
        print(f"이미지 다운로드 실패: {img_path} - {e}")
        return None


def get_valid_image_paths(imgs_raw, max_count=5):
    """
    이미지 목록에서 유효한 이미지 파일 경로들을 반환합니다. (PDF 엔진용)
    URL인 경우 임시 파일로 다운로드합니다.

    Args:
        imgs_raw: JSON 문자열 또는 리스트
        max_count: 최대 이미지 개수

    Returns: list of file paths (임시 파일 포함)
    """
    if not imgs_raw:
        return []

    imgs = json.loads(imgs_raw) if isinstance(imgs_raw, str) else imgs_raw
    if not imgs:
        return []

    valid_paths = []
    for img_path in imgs[:max_count]:
        temp_path = download_image_to_temp(img_path)
        if temp_path:
            valid_paths.append(temp_path)

    return valid_paths


def cleanup_temp_files(file_paths):
    """
    임시 파일들을 정리합니다.

    Args:
        file_paths: 파일 경로 리스트
    """
    for path in file_paths:
        try:
            if path and os.path.exists(path) and tempfile.gettempdir() in path:
                os.remove(path)
        except Exception:
            pass

def ensure_image_dir():
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

def save_article_with_images(db_service, data, uploaded_files):
    ensure_image_dir()
    
    # 이미지 저장 Logic
    image_paths = []
    if uploaded_files:
        for file in uploaded_files:
            img_id = str(uuid.uuid4())
            # Handle both Streamlit UploadedFile (has name) and internal usage
            ext = 'png'
            if hasattr(file, 'name') and '.' in file.name:
                ext = file.name.split('.')[-1]
                
            file_path = os.path.join(IMAGE_DIR, f"{img_id}.{ext}")
            
            with open(file_path, "wb") as f:
                f.write(file.getbuffer() if hasattr(file, 'getbuffer') else file.read() if hasattr(file, 'read') else file)
            image_paths.append(file_path)
    
    new_data = {
        "id": str(uuid.uuid4()),
        "date": data['date'],
        "school": data['school'],
        "grade": data['grade'],
        "event_name": data['event_name'],
        "location": data['location'],
        "tone": data['tone'],
        "keywords": data['keywords'],
        "title": data['title'],
        "content": data['content'],
        "images": json.dumps(image_paths),
        "hashtags": json.dumps(data.get('hashtags', []))
    }
    
    db_service.save_article(new_data)
    return new_data
