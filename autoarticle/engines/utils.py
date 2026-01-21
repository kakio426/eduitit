import os
import uuid
import json
from engines.constants import IMAGE_DIR

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
