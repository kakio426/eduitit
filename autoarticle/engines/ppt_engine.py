
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os
import json
import datetime
from io import BytesIO

from .constants import THEMES
from .utils import get_valid_images

class PPTEngine:
    def __init__(self, theme_name, school_name):
        self.theme_name = theme_name
        self.theme = THEMES.get(theme_name, THEMES["웜 & 플레이풀"])
        self.school_name = school_name
        self.prs = Presentation()
        # Set slide size to 16:9 (13.333 x 7.5 inches)
        self.prs.slide_width = Inches(13.333)
        self.prs.slide_height = Inches(7.5)

    def create_presentation(self, articles, output_path=None):
        """
        Creates a PPT presentation from a list of articles.
        Returns bytes if output_path is None.
        """
        self._add_title_slide()
        
        for art in articles:
            self._add_article_slide(art)
            
        if output_path:
            self.prs.save(output_path)
            return output_path
        else:
            buffer = BytesIO()
            self.prs.save(buffer)
            buffer.seek(0)
            return buffer

    def _add_title_slide(self):
        """Adds a professional main title slide."""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6]) # Blank layout
        
        # Background Color
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(*self.theme["sub"])
        
        # Center Box for Title
        left = Inches(2)
        top = Inches(2.5)
        width = Inches(9.333)
        height = Inches(2.5)
        
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, width, height
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(255, 255, 255)
        shape.line.width = Pt(0)
        shape.shadow.inherit = False
        
        # Title Text
        text_frame = shape.text_frame
        text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = text_frame.paragraphs[0]
        p.text = f"{self.school_name} 뉴스레터"
        p.alignment = PP_ALIGN.CENTER
        p.font.name = 'Malgun Gothic'
        p.font.size = Pt(44)
        p.font.bold = True
        p.font.color.rgb = RGBColor(*self.theme["main"])
        
        # Subtitle (Date)
        p = text_frame.add_paragraph()
        now = datetime.datetime.now()
        p.text = f"{now.year}학년도 {now.month}월 소식"
        p.alignment = PP_ALIGN.CENTER
        p.font.name = 'Malgun Gothic'
        p.font.size = Pt(24)
        p.font.color.rgb = RGBColor(80, 80, 80)

    def _add_article_slide(self, article):
        """Adds a content slide with 2-column layout (Text Left, Image Right)."""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6]) # Blank layout
        
        # 1. Header Bar (Visual Identity)
        header_height = Inches(1.0)
        header = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, self.prs.slide_width, header_height
        )
        header.fill.solid()
        header.fill.fore_color.rgb = RGBColor(*self.theme["main"])
        header.line.fill.background() # No outline
        
        # Header Text (Article Title)
        tf = header.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.text = article.get('title', '제목 없음')
        p.font.name = 'Malgun Gothic'
        p.font.size = Pt(28)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.LEFT
        tf.margin_left = Inches(0.5)
        
        # 2. Layout Grid
        # Left Column (Text): 0.5" ~ 7.0" (Width 6.5")
        # Right Column (Image): 7.5" ~ 12.8" (Width 5.3")
        # Top: 1.5"
        
        # --- Left Column: Content ---
        left_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(6.5), Inches(5.5))
        tf = left_box.text_frame
        tf.word_wrap = True
        
        # Metadata (Date/Loc)
        p = tf.add_paragraph()
        info_parts = []
        if article.get('date'): info_parts.append(f"{article['date']}")
        if article.get('location'): info_parts.append(f"{article['location']}")
        p.text = " | ".join(info_parts)
        p.font.size = Pt(14)
        p.font.color.rgb = RGBColor(128, 128, 128)
        p.space_after = Pt(10)
        
        # Body Content
        content_text = article.get('content', '')
        # Basic clean up if summarized
        if isinstance(content_text, list): # AI summary case
            for item in content_text:
                p = tf.add_paragraph()
                p.text = f"• {item}"
                p.font.size = Pt(20)
                p.space_after = Pt(10)
                p.level = 0
        else: # Raw text case
            # Truncate long text for PPT readability
            p = tf.add_paragraph()
            # Check for summary failure message or overly long text
            if "요약에 실패" in content_text or len(content_text) > 300:
                truncated = content_text[:300].rsplit(' ', 1)[0] if len(content_text) > 300 else content_text
                p.text = truncated + "..." if len(content_text) > 300 else content_text
            else:
                p.text = content_text
            p.font.size = Pt(18)
            p.font.name = "Malgun Gothic"
            
        # --- Right Column: Image ---
        imgs_raw = article.get('images', [])
        valid_imgs = get_valid_images(imgs_raw, max_count=1)

        if valid_imgs:
            # Place first image
            img_data = valid_imgs[0]
            try:
                # Add picture from BytesIO
                pic = slide.shapes.add_picture(img_data, Inches(7.2), Inches(1.5))
                
                # Resize logic (Fit within 5.5" W x 5.0" H)
                max_w = 5.5
                max_h = 5.0
                
                # Aspect ratio check happens automatically if we set only width or height?
                # No, we need to calculate. pptx creates with native size if no args.
                # But we passed pos. Let's adjust size.
                
                # Get current size
                img_w = pic.width.inches
                img_h = pic.height.inches
                aspect = img_w / img_h
                
                # Target
                if aspect > (max_w / max_h):
                    # Too wide, limit by width
                    pic.width = Inches(max_w)
                    pic.height = Inches(max_w / aspect)
                else:
                    # Too tall, limit by height
                    pic.height = Inches(max_h)
                    pic.width = Inches(max_h * aspect)
                    
                # Add nice border
                line = pic.line
                line.color.rgb = RGBColor(200, 200, 200)
                line.width = Pt(1)
                
            except Exception as e:
                print(f"Error adding image: {e}")
