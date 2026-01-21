from PIL import Image, ImageDraw, ImageFont
import io
import os
from .constants import FONT_PATH, THEMES

class CardNewsEngine:
    def __init__(self, theme_name):
        self.theme = THEMES[theme_name]
        self.size = (1080, 1080)
        self.font_path = FONT_PATH
        
    def _get_font(self, size, bold=False):
        return ImageFont.truetype(self.font_path, size)

    def _draw_wrapped_text(self, draw, text, position, font, max_width, fill, max_lines=2):
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
                if len(lines) >= max_lines: break
        
        if len(lines) < max_lines:
            lines.append(current_line)
        
        if len(lines) == max_lines:
            last_line = lines[-1]
            bbox = draw.textbbox((0, 0), last_line, font=font)
            if bbox[2] - bbox[0] > max_width - 30:
                while last_line and draw.textbbox((0, 0), last_line + "...", font=font)[2] > max_width:
                    last_line = last_line[:-1]
                lines[-1] = last_line + "..."

        y = position[1]
        for line in lines:
            draw.text((position[0], int(y)), line, font=font, fill=fill)
            y += font.size * 1.4
        return int(y)

    def create_card(self, title, date, location, grade, hashtags, images):
        canvas = Image.new("RGB", self.size, (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        
        main_rgb = self.theme["main"]
        accent_rgb = self.theme["accent"]
        
        badge_w = 120
        draw.rounded_rectangle((50, 50, 50 + badge_w, 100), radius=25, fill=main_rgb)
        draw.text((50 + 20, 60), grade if grade else "소식", font=self._get_font(22), fill=(255, 255, 255))
        
        draw.text((50 + badge_w + 20, 55), "학교 소식지", font=self._get_font(24), fill=(30, 30, 30))
        draw.text((50 + badge_w + 20, 85), date, font=self._get_font(18), fill=(150, 150, 150))

        title_y = 140
        next_y = self._draw_wrapped_text(draw, title, (50, title_y), self._get_font(56), 980, (20, 20, 20), max_lines=2)
        
        loc_y = next_y + 10
        if location:
            draw.text((50, loc_y), f"📍 {location}", font=self._get_font(28), fill=accent_rgb)
            img_y = loc_y + 60
        else:
            img_y = loc_y + 20

        img_w = 980
        img_h = 580
        img_box = (50, int(img_y), 50 + img_w, int(img_y + img_h))
        
        draw.rectangle((48, int(img_y - 2), 52 + img_w, int(img_y + img_h + 2)), fill=(245, 245, 245))
        
        if images:
            self._render_image_grid(canvas, images, img_box)
            
        tag_y = img_y + img_h + 30
        tag_str = " ".join([f"#{t}" for t in hashtags])
        self._draw_wrapped_text(draw, tag_str, (50, tag_y), self._get_font(34), 980, main_rgb, max_lines=2)
        
        draw.text((820, 1010), "AI School Story", font=self._get_font(20), fill=(220, 220, 220))
        
        return canvas

    def _render_image_grid(self, canvas, image_paths, box):
        x, y, x2, y2 = box
        w, h = x2 - x, y2 - y
        
        imgs = []
        for p in image_paths[:4]:
            try:
                if isinstance(p, str):
                    imgs.append(Image.open(p))
                else:
                    imgs.append(Image.open(io.BytesIO(p.getbuffer()) if hasattr(p, 'getbuffer') else p))
            except: continue
            
        if not imgs: return

        gap = 10
        if len(imgs) == 1:
            self._paste_cover(canvas, imgs[0], (x, y, w, h))
        elif len(imgs) == 2:
            half_w = (w - gap) // 2
            self._paste_cover(canvas, imgs[0], (x, y, half_w, h))
            self._paste_cover(canvas, imgs[1], (x + half_w + gap, y, half_w, h))
        elif len(imgs) == 3:
            big_w = (w * 2) // 3
            small_w = w - big_w - gap
            half_h = (h - gap) // 2
            self._paste_cover(canvas, imgs[0], (x, y, big_w, h))
            self._paste_cover(canvas, imgs[1], (x + big_w + gap, y, small_w, half_h))
            self._paste_cover(canvas, imgs[2], (x + big_w + gap, y + half_h + gap, small_w, half_h))
        else: # 4
            half_w = (w - gap) // 2
            half_h = (h - gap) // 2
            self._paste_cover(canvas, imgs[0], (x, y, half_w, half_h))
            self._paste_cover(canvas, imgs[1], (x + half_w + gap, y, half_w, half_h))
            self._paste_cover(canvas, imgs[2], (x, y + half_h + gap, half_w, half_h))
            self._paste_cover(canvas, imgs[3], (x + half_w + gap, y + half_h + gap, half_w, half_h))

    def _paste_cover(self, canvas, img, rect):
        rx, ry, rw, rh = rect
        iw, ih = img.size
        i_aspect = iw / ih
        r_aspect = rw / rh
        
        if i_aspect > r_aspect:
            new_h = int(rh)
            new_w = int(rh * i_aspect)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - rw) // 2
            img = img.crop((int(left), 0, int(left + rw), int(rh)))
        else:
            new_w = int(rw)
            new_h = int(rw / i_aspect)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - rh) // 2
            img = img.crop((0, int(top), int(rw), int(top + rh)))
            
        canvas.paste(img, (int(rx), int(ry)))
