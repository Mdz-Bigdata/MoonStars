import asyncio
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import trafilatura
from .models import ScrapedContent

class ScraperService:
    async def scrape_urls(self, urls: List[str]) -> List[ScrapedContent]:
        tasks = [self.scrape_url(url) for url in urls]
        return await asyncio.gather(*tasks)

    async def scrape_url(self, url: str) -> ScrapedContent:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                # Set viewport for high-res screenshots
                await page.set_viewport_size({"width": 1920, "height": 1080})
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Wait for any lazy content
                await asyncio.sleep(3)
                
                # Identification and screenshotting of visual fragments (Feishu blocks, etc.)
                from .models import VisualFragment
                import base64
                fragments = []
                
                # Selectors for complex blocks (Feishu specific and general)
                selectors = {
                    "table": ".bitable-container, table, .sheet-container, .table-block", 
                    "whiteboard": ".canvas-container, .drawing-board, .whiteboard-container, svg.board-svg",
                    "chart": ".chart-container, .echarts-for-react",
                    "screenshot": ".screenshot-block, .image-with-caption"
                }

                for frag_type, selector in selectors.items():
                    elements = await page.query_selector_all(selector)
                    for i, el in enumerate(elements[:5]): # Limit per doc
                        try:
                            # Take element screenshot
                            screenshot_bytes = await el.screenshot()
                            b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
                            fragments.append(VisualFragment(
                                id=f"{frag_type}_{i}",
                                type=frag_type,
                                data_base64=b64_data,
                                caption=f"Original {frag_type} from document"
                            ))
                        except:
                            continue

                html = await page.content()
                await browser.close()
                
                content_obj = self.parse_content(url, html)
                content_obj.visual_fragments = fragments
                return content_obj
        except Exception as e:
            # Fallback to static scrape if playwright fails
            return self.scrape_static(url)

    def scrape_static(self, url: str) -> ScrapedContent:
        import httpx
        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True)
            return self.parse_content(url, response.text)

    def parse_content(self, url: str, html: str) -> ScrapedContent:
        soup = BeautifulSoup(html, 'lxml')
        
        # Use trafilatura for high-quality text extraction
        # We enable tables for trafilatura extraction
        content = trafilatura.extract(html, include_links=False, include_images=False, include_tables=True) or ""
        
        # Extract title
        title = (
            soup.find('title').text if soup.find('title') else ""
            or soup.find('meta', property='og:title').get('content', "") if soup.find('meta', property='og:title') else ""
            or "Untitled"
        )
        
        # Extract tables separately for structured processing
        tables_extracted = []
        for table in soup.find_all('table'):
            # Convert simple table to a readable string/markdown
            rows = []
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                tables_extracted.append("\n".join(rows))
        
        # Extract images (including potential whiteboards/screenshots)
        images = []
        # Support more image patterns (e.g., Feishu's dynamic canvases or special image types)
        for img in soup.find_all(['img', 'canvas', 'svg']):
            src = img.get('src') or img.get('data-src')
            if src and (src.startswith('http') or src.startswith('//') or src.startswith('data:image')):
                images.append({
                    "src": src if src.startswith('http') or src.startswith('data:') else f"https:{src}",
                    "alt": img.get('alt', "") or img.get('title', "Drawing/Board")
                })
        
        # Extract headings for structure
        headings = []
        for tag in soup.find_all(['h1', 'h2', 'h3']):
            headings.append({
                "level": int(tag.name[1]),
                "text": tag.text.strip()
            })
            
        return ScrapedContent(
            url=url,
            title=title.strip(),
            content=content.strip(),
            images=images[:20], # Increase limit to capture more visuals
            tables=tables_extracted,
            headings=headings
        )
