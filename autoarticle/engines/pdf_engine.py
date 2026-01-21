
from fpdf import FPDF
from PIL import Image as PILImage
import json
import os

from engines.constants import THEMES, FONT_PATH

class PDFEngine(FPDF):
    def __init__(self, theme_name, school_name):
        super().__init__()
        self.theme = THEMES.get(theme_name, THEMES["웜 & 플레이풀"])
        self.school_name = school_name
        # Ensure font exists or fallback
        if os.path.exists(FONT_PATH):
            self.add_font("NanumGothic", "", FONT_PATH)
        else:
            # Fallback to standard font if custom not found (avoids crash during dev)
            self.set_font("Arial", "", 12)
            
        # 상단 여백을 25mm로 설정하여 헤더(15mm)와 겹침 방지
        self.set_margins(10, 25, 10)
        self.set_auto_page_break(auto=True, margin=20)
        
    def header(self):
        # 표지가 아닐 때만 헤더 표시
        if not getattr(self, 'is_cover_page', False):
            try:
                # 배경 상자
                self.set_fill_color(*self.theme["main"])
                self.rect(0, 0, 210, 15, 'F')
                
                # 폰트 설정
                self.set_font("NanumGothic", "", 10) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", 10)
                self.set_text_color(255, 255, 255)
                
                # fpdf의 cell() 오류로 인한 겹침 방지를 위해 text()로 직접 좌표 지정
                # Y축 10mm 지점이 15mm 박스의 시각적 중앙입니다.
                header_text = f"{self.school_name} 소식지"
                self.text(12, 10, header_text)
                
                # 우측 날짜: 너비를 계산하여 수동 정렬
                import datetime
                date_text = datetime.datetime.now().strftime("%Y. %m. %d")
                date_w = self.get_string_width(date_text)
                self.text(198 - date_w, 10, date_text)
            except: pass

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            if os.path.exists(FONT_PATH):
                self.set_font("NanumGothic", "", 8)
            else:
                self.set_font("Arial", "", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'- {self.page_no()} -', align='C')

    def draw_cover(self):
        self.is_cover_page = True
        self.add_page()
        # 표지는 상단 여백을 무시하고 전체 배경색 칠함
        self.set_fill_color(*self.theme["sub"])
        self.rect(0, 0, 210, 297, 'F')
        
        self.set_y(100)
        if os.path.exists(FONT_PATH):
            self.set_font("NanumGothic", "", 42)
        else:
            self.set_font("Arial", "", 42)
        self.set_text_color(*self.theme["main"])
        self.cell(190, 30, self.school_name, align='C', ln=True)
        
        self.set_y(130)
        if os.path.exists(FONT_PATH):
            self.set_font("NanumGothic", "", 22)
        else:
            self.set_font("Arial", "", 22)
        self.set_text_color(70, 70, 70)
        import datetime
        now = datetime.datetime.now()
        self.cell(190, 20, f"{now.year}학년도 {now.month}월 뉴스레터", align='C', ln=True)
        
        self.set_draw_color(*self.theme["accent"])
        self.set_line_width(1.5)
        self.line(60, 155, 150, 155)
        self.cover_drawn = True

    def calculate_layout_params(self, text_length, image_count):
        """
        Calculates optimal layout parameters (font size, grid type)
        based on content length and number of images.
        """
        # Default settings
        params = {
            'font_size_content': 11,
            'grid_type': 'none',
            'scaling': 1.0
        }
        
        # Grid type determination
        if image_count == 0:
            params['grid_type'] = 'none'
        elif image_count == 1:
            params['grid_type'] = 'grid-1'
        elif image_count == 2:
            params['grid_type'] = 'grid-2'
        elif image_count == 3:
            params['grid_type'] = 'grid-3'
        else:
            params['grid_type'] = 'grid-4'
            
        # Copy-fitting Logic (Basic)
        if text_length > 1000 and image_count > 0:
            params['font_size_content'] = 10
            params['scaling'] = 0.8
        elif text_length > 1500:
            params['font_size_content'] = 9
            
        return params

    def calculate_article_height(self, article, scaling=1.0, content_font_size=11):
        """기사의 높이를 합산하여 반환 (add_article 로직과 100% 동기화)"""
        h = 0
        
        # 1. 제목 높이 (폰트 18, 줄높이 12)
        self.set_font("NanumGothic", "", 18) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", 18)
        title_lines = len(self.multi_cell(190, 12, str(article.get('title', '')), split_only=True))
        h += (title_lines * 12) + 2 # ln(2)
        
        # 2. 메타데이터 바 높이 (8mm + ln(5)로 축소 예정)
        h += 8 + 5 
        
        # 3. 이미지 그리드 높이
        imgs_raw = article.get('images', '[]')
        imgs = json.loads(imgs_raw) if isinstance(imgs_raw, str) else imgs_raw
        if imgs:
            cnt = len(imgs)
            if cnt == 1:
                try:
                    with PILImage.open(imgs[0]) as pil_img:
                        aspect = pil_img.size[1] / pil_img.size[0]
                        img_h = 140 * scaling * aspect
                        if img_h > 120 * scaling: img_h = 120 * scaling
                        h += img_h
                except: h += 90 * scaling
            else:
                rows = (cnt + 1) // 2
                max_row_h = 80 * scaling
                h += (rows * (max_row_h + 5)) # row + gap
            h += 5 # ln(5) after image grid
        
        # 4. 본문 높이 (줄높이 7)
        self.set_font("NanumGothic", "", content_font_size) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", content_font_size)
        content_lines = len(self.multi_cell(190, 7, str(article.get('content', '')), split_only=True))
        h += (content_lines * 7)
        
        return h

    def add_article(self, article, is_booklet=False):
        """기사를 추가함. is_booklet=True일 경우 각 기사를 정확히 1페이지에 강제 배치."""
        imgs_raw = article.get('images', '[]')
        imgs = json.loads(imgs_raw) if isinstance(imgs_raw, str) else imgs_raw
        
        # 기사가 시작되었으므로 표지 플래그 해제
        self.is_cover_page = False
        
        if is_booklet:
            # === BOOKLET 모드: 강제 1페이지 레이아웃 ===
            self.add_page()
            
            # 자동 페이지 넘김 비활성화 (이 기사는 절대 다음 페이지로 안 넘어감)
            self.set_auto_page_break(False)
            
            # 고정 영역 정의 (A4 세로 기준, 상단 여백 25mm, 하단 여백 20mm)
            y_cursor = 25  # 헤더 아래 시작점
            
            # 1. 제목 영역 (최대 30mm)
            self.set_xy(10, y_cursor)
            self.set_font("NanumGothic", "", 18) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", 18)
            self.set_text_color(*self.theme["main"])
            self.multi_cell(190, 10, str(article.get('title', '')))
            y_cursor = self.get_y() + 3
            
            # 2. 메타데이터 바 (8mm 고정)
            self.set_xy(10, y_cursor)
            self.set_font("NanumGothic", "", 9) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", 9)
            self.set_text_color(80, 80, 80)
            
            info_parts = []
            if article.get('date'): info_parts.append(f"일시: {article['date']}")
            if article.get('location'): info_parts.append(f"장소: {article['location']}")
            if article.get('grade'): info_parts.append(f"대상: {article['grade']}")
            meta_info = "  |  ".join(info_parts)
            
            self.set_fill_color(248, 248, 248)
            self.set_draw_color(220, 220, 220)
            self.cell(190, 8, meta_info, border=1, fill=True, align='L')
            y_cursor += 15
            
            # 3. 이미지 영역 (최대 100mm)
            if imgs:
                img_count = min(len(imgs), 2)  # 최대 2개만 사용
                
                if img_count == 1:
                    # 사진 1개: 중앙 정렬, 큰 크기
                    if os.path.exists(imgs[0]):
                        try:
                            from PIL import Image as PILImage
                            with PILImage.open(imgs[0]) as pil_img:
                                iw, ih = pil_img.size
                                aspect = ih / iw
                            
                            img_w = 120
                            img_h = img_w * aspect
                            if img_h > 100:
                                img_h = 100
                                img_w = img_h / aspect
                            
                            img_x = (210 - img_w) / 2
                            self.image(imgs[0], x=img_x, y=y_cursor, w=img_w, h=img_h)
                            y_cursor += img_h + 10
                        except:
                            y_cursor += 10
                else:
                    # 사진 2개 이상: 좌우 나란히 고정 크기 (각 90mm 너비)
                    fixed_w = 90
                    fixed_h = 70  # 고정 높이
                    gap = 10
                    
                    try:
                        # 왼쪽 사진
                        if os.path.exists(imgs[0]):
                            self.image(imgs[0], x=10, y=y_cursor, w=fixed_w, h=fixed_h)
                        
                        # 오른쪽 사진
                        if os.path.exists(imgs[1]):
                            self.image(imgs[1], x=10 + fixed_w + gap, y=y_cursor, w=fixed_w, h=fixed_h)
                        
                        y_cursor += fixed_h + 10
                    except:
                        y_cursor += 10
            
            # 4. 본문 영역 (y_cursor부터 페이지 하단 20mm까지)
            available_height = 297 - 20 - y_cursor  # 하단 여백 20mm
            self.set_xy(10, y_cursor)
            self.set_font("NanumGothic", "", 11) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", 11)
            self.set_text_color(30, 30, 30)
            
            content = str(article.get('content', ''))
            
            # 본문이 남은 공간에 들어가는지 시뮬레이션
            test_lines = self.multi_cell(190, 7, content, split_only=True)
            needed_height = len(test_lines) * 7
            
            if needed_height > available_height:
                # 공간 부족: 폰트 축소 또는 잘라내기
                # 방법 1: 폰트 크기 줄이기
                self.set_font("NanumGothic", "", 9) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", 9)
                test_lines = self.multi_cell(190, 6, content, split_only=True)
                needed_height = len(test_lines) * 6
                
                if needed_height > available_height:
                    # 여전히 부족: 텍스트 잘라내기
                    max_lines = int(available_height / 6)
                    truncated_content = '\n'.join(test_lines[:max_lines]) + "..."
                    self.multi_cell(190, 6, truncated_content)
                else:
                    self.multi_cell(190, 6, content)
            else:
                # 공간 충분: 정상 출력
                self.multi_cell(190, 7, content)
            
            # 자동 페이지 넘김 다시 활성화 (다음 기사를 위해)
            self.set_auto_page_break(True, margin=20)
        
        else:
            # === 일반 모드: 기존 로직 유지 ===
            layout = self.calculate_layout_params(len(article.get('content', '')), len(imgs))
            scaling = layout['scaling']
            content_font_size = layout['font_size_content']
            
            layout_temp = self.calculate_layout_params(len(article.get('content', '')), len(imgs))
            h_final = self.calculate_article_height(article, layout_temp['scaling'], layout_temp['font_size_content'])
            if self.page_no() == 0:
                self.add_page()
            elif self.get_y() + h_final > 270:
                self.add_page()
            
            # 제목
            self.set_x(10)
            self.set_font("NanumGothic", "", 18) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", 18)
            self.set_text_color(*self.theme["main"])
            self.multi_cell(190, 12, str(article.get('title', '')))
            self.ln(2)
            
            # 메타데이터
            self.set_font("NanumGothic", "", 9) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", 9)
            self.set_text_color(80, 80, 80)
            
            info_parts = []
            if article.get('date'): info_parts.append(f"일시: {article['date']}")
            if article.get('location'): info_parts.append(f"장소: {article['location']}")
            if article.get('grade'): info_parts.append(f"대상: {article['grade']}")
            meta_info = "  |  ".join(info_parts)
            
            self.set_fill_color(248, 248, 248)
            self.set_draw_color(220, 220, 220)
            self.set_x(10)
            self.cell(190, 8, meta_info, border=1, fill=True, align='L')
            self.set_y(self.get_y() + 12)
            
            # 이미지
            if imgs:
                self.render_image_grid(imgs, scaling=scaling)
                self.set_y(self.get_y() + 5)
            
            # 본문
            self.set_x(10)
            self.set_font("NanumGothic", "", content_font_size) if os.path.exists(FONT_PATH) else self.set_font("Arial", "", content_font_size)
            self.set_text_color(30, 30, 30)
            self.multi_cell(190, 7, str(article.get('content', '')))
            self.ln(10)

    def render_image_grid(self, imgs, scaling=1.0):
        cnt = len(imgs)
        gap = 5
        max_row_h = 80 * scaling # 한 줄 최대 높이 제한
        
        try:
            if cnt == 1:
                with PILImage.open(imgs[0]) as pil_img:
                    iw, ih = pil_img.size
                    aspect = ih / iw
                
                w = 140 * scaling
                h = w * aspect
                # 한 페이지를 너무 많이 차지하지 않도록 높이 제한
                if h > 120 * scaling:
                    h = 120 * scaling
                    w = h / aspect
                
                x = (210 - w) / 2
                self.image(imgs[0], x=x, w=w, h=h)
                self.set_y(self.get_y() + h)
                
            elif cnt >= 2:
                # 2개 이상일 때는 2개씩 한 줄에 배치 (그리드)
                # 3개일 경우 1개(위) + 2개(아래) 형식에서 -> 2개(위) + 1개(아래)로 변경하거나 일관성 있게 처리
                rows = (cnt + 1) // 2
                w_each = 92 * scaling
                
                idx = 0
                for r in range(rows):
                    curr_y = self.get_y()
                    row_imgs = imgs[idx:idx+2]
                    
                    # 현재 줄의 최대 높이 계산 (비율 유지)
                    current_row_max_h = 0
                    for img_path in row_imgs:
                        with PILImage.open(img_path) as pil_img:
                            iw, ih = pil_img.size
                            h_calc = w_each * (ih / iw)
                            if h_calc > current_row_max_h: current_row_max_h = h_calc
                    
                    # 줄 높이 제한
                    if current_row_max_h > max_row_h: current_row_max_h = max_row_h
                    
                    # 이미지 그리기
                    if len(row_imgs) >= 1:
                        self.image(row_imgs[0], x=10, y=curr_y, w=w_each, h=current_row_max_h)
                    if len(row_imgs) >= 2:
                        self.image(row_imgs[1], x=108, y=curr_y, w=w_each, h=current_row_max_h)
                    
                    self.set_y(curr_y + current_row_max_h + gap)
                    idx += 2
        except Exception as e:
            # 에러 발생 시 로그를 남기거나 안전하게 넘김
            print(f"PDF Image Error: {e}")
            pass

    def add_newspaper_page(self, articles):
        """
        Generates a one-page newspaper layout (A4) combining multiple articles.
        Optimized for 3-5 articles.
        """
        self.add_page()
        
        # Newspaper Header
        self.set_fill_color(*self.theme["main"])
        self.rect(0, 0, 210, 25, 'F')
        
        if os.path.exists(FONT_PATH):
             self.set_font("NanumGothic", "", 24)
        else:
             self.set_font("Arial", "", 24)
        
        self.set_text_color(255, 255, 255)
        self.text(12, 18, f"{self.school_name} 타임즈") # Newspaper Title
        
        self.set_font("Arial", "", 12)
        import datetime
        now = datetime.datetime.now()
        self.text(150, 18, now.strftime("%Y.%m.%d"))
        
        # Reset Y
        self.set_y(35)
        
        count = len(articles)
        if count == 0: return

        # === Headline Article (Top) ===
        main_art = articles[0]
        self.set_text_color(*self.theme["main"])
        if os.path.exists(FONT_PATH): self.set_font("NanumGothic", "", 22)
        else: self.set_font("Arial", "", 22)
        
        # Title
        self.multi_cell(190, 10, main_art['title'])
        self.ln(5)
        
        # Image & Content Layout (Simpler: Image Left, Text Right)
        imgs_raw = main_art.get('images', '[]')
        imgs = json.loads(imgs_raw) if isinstance(imgs_raw, str) else imgs_raw
        
        start_y = self.get_y()
        img_h = 0
        if imgs and os.path.exists(imgs[0]):
             try:
                 self.image(imgs[0], x=10, y=start_y, w=90)
                 img_h = 60 # Approx
             except: pass
        
        # Content on Right
        self.set_xy(105, start_y)
        self.set_text_color(20, 20, 20)
        if os.path.exists(FONT_PATH): self.set_font("NanumGothic", "", 10)
        else: self.set_font("Arial", "", 10)
        
        self.multi_cell(95, 6, main_art['content'][:400] + "...")
        
        # Move below
        next_y = start_y + 65 if img_h > 0 else self.get_y() + 10
        self.set_y(next_y)
        
        self.set_draw_color(200, 200, 200)
        self.line(10, next_y, 200, next_y)
        self.ln(5)
        
        # === Sub Articles (Bottom Grid) ===
        rest = articles[1:5]
        col_w = 90
        left_x = 10
        right_x = 105
        
        base_y = self.get_y()
        
        for i, art in enumerate(rest):
            is_left = (i % 2 == 0)
            cur_x = left_x if is_left else right_x
            row = i // 2
            cur_y = base_y + (row * 90) # 90mm height slot
            
            if cur_y > 270: break
            
            self.set_xy(cur_x, cur_y)
            
            # Sub Title
            self.set_text_color(*self.theme["main"])
            if os.path.exists(FONT_PATH): self.set_font("NanumGothic", "", 12)
            else: self.set_font("Arial", "", 12)
            self.cell(col_w, 8, art['title'], ln=True)
            
            # Sub Content
            self.set_text_color(40, 40, 40)
            if os.path.exists(FONT_PATH): self.set_font("NanumGothic", "", 9)
            else: self.set_font("Arial", "", 9)
            self.multi_cell(col_w, 5, art['content'][:150] + "...")
