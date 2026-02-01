import asyncio
from playwright.async_api import async_playwright
import os
import time

async def capture_all_cards():
    MBTICS = [
        'ISTJ', 'ISFJ', 'INFJ', 'INTJ',
        'ISTP', 'ISFP', 'INFP', 'INTP',
        'ESTP', 'ESFP', 'ENFP', 'ENTP',
        'ESTJ', 'ESFJ', 'ENFJ', 'ENTJ'
    ]
    
    output_dir = os.path.abspath('static/ssambti/images/share_cards')
    os.makedirs(output_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Set viewport to match the card height if possible, or just large enough
        context = await browser.new_context(viewport={'width': 800, 'height': 1200})
        page = await context.new_page()
        
        for mbti in MBTICS:
            url = f'http://127.0.0.1:8000/ssambti/generator/{mbti}/'
            print(f"Capturing {mbti} from {url}...")
            
            try:
                await page.goto(url, wait_until='networkidle')
                # Wait for any additional fonts/images
                await asyncio.sleep(2)
                
                # Take screenshot of the specific element
                element = await page.query_selector('#shareCard')
                if element:
                    save_path = os.path.join(output_dir, f'{mbti}_card.png')
                    await element.screenshot(path=save_path)
                    print(f"✅ Saved to {save_path}")
                else:
                    print(f"❌ Failed to find #shareCard for {mbti}")
            except Exception as e:
                print(f"❌ Error for {mbti}: {e}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_all_cards())
