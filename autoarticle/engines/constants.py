
import os

# [Railway 배포용 경로 설정]
# Railway에서 'RAILWAY_ENVIRONMENT'라는 변수가 있으면 '/app/data'를 쓰고, 
# 내 컴퓨터(로컬)면 그냥 현재 폴더('.')를 씁니다.
BASE_DIR = "/app/data" if os.environ.get('RAILWAY_ENVIRONMENT') else "."

# DB 파일 경로
DB_PATH = os.path.join(BASE_DIR, "articles.db")

# Chroma DB 폴더 경로
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db_school")

# 이미지 저장 경로도 안전한 곳으로
IMAGE_DIR = os.path.join(BASE_DIR, "uploaded_images")

# 폰트 경로 (프로젝트 루트 기준 절대 경로)
# constants.py 위치: autoarticle/engines/constants.py -> ../../..
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_PATH = os.path.join(PROJECT_ROOT, "NanumGothic-Regular.ttf")

# 폴더 생성 (권한 에러 방지)
try:
    if BASE_DIR != "." and not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR, exist_ok=True)
    if not os.path.exists(CHROMA_PATH):
        os.makedirs(CHROMA_PATH, exist_ok=True)
except Exception as e:
    print(f"[WARNING] Failed to create directories at {BASE_DIR}: {e}")
    # Fallback to local /tmp or similar if needed, but for now just log
    pass

THEMES = {
    "웜 & 플레이풀": {"main": (255, 140, 66), "sub": (255, 251, 240), "accent": (6, 214, 160), "hex": "#FF8C42"},
    "꿈꾸는 파랑": {"main": (0, 80, 150), "sub": (230, 240, 255), "accent": (0, 120, 215), "hex": "#005096"},
    "발랄한 노랑": {"main": (255, 180, 0), "sub": (255, 250, 230), "accent": (255, 140, 0), "hex": "#FFB400"},
    "산뜻한 민트": {"main": (0, 168, 107), "sub": (235, 250, 245), "accent": (0, 128, 90), "hex": "#00A86B"}
}

