import os
import json
import re
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

AMAZON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

AMAZON_CATEGORIES = [
    {"key": "dresses", "name_en": "Dresses", "name_cn": "连衣裙与礼服", "url": "https://www.amazon.com/gp/bestsellers/fashion/1045024/"},
    {"key": "tops", "name_en": "Tops & Shirts", "name_cn": "上衣与衬衫", "url": "https://www.amazon.com/gp/bestsellers/fashion/2368343011/"},
    {"key": "outerwear", "name_en": "Outerwear & Coats", "name_cn": "外套与风衣", "url": "https://www.amazon.com/gp/bestsellers/fashion/1044456/"},
    {"key": "skirts", "name_en": "Skirts", "name_cn": "半身裙", "url": "https://www.amazon.com/gp/bestsellers/fashion/1045022/"},
    {"key": "sweaters", "name_en": "Sweaters & Knits", "name_cn": "毛衣与针织衫", "url": "https://www.amazon.com/gp/bestsellers/fashion/1044442/"},
    {"key": "pants", "name_en": "Pants & Jeans", "name_cn": "裤装与牛仔", "url": "https://www.amazon.com/gp/bestsellers/fashion/1048184/"},
    {"key": "activewear", "name_en": "Activewear & Sets", "name_cn": "运动与套装", "url": "https://www.amazon.com/gp/bestsellers/fashion/2368344011/"},
    {"key": "swimwear", "name_en": "Swimwear & Beach", "name_cn": "泳装与沙滩服", "url": "https://www.amazon.com/gp/bestsellers/fashion/1046672/"}
]

# SHEIN 精准分类及 cat_id / search_key
SHEIN_CATEGORIES = [
    {"key": "shein-dresses", "name_en": "Dresses", "name_cn": "连衣裙与礼服", "cat_id": "1727", "url": "https://us.shein.com/Women-Dresses-c-1727.html?sort=7"},
    {"key": "shein-tops", "name_en": "Tops & Blouses", "name_cn": "上衣与衬衫", "cat_id": "1738", "url": "https://us.shein.com/Women-Tops-Blouses-Tees-c-1738.html?sort=7"},
    {"key": "shein-outerwear", "name_en": "Outerwear & Coats", "name_cn": "外套与风衣", "cat_id": "1735", "url": "https://us.shein.com/Women-Outerwear-Coats-Jackets-c-1735.html?sort=7"},
    {"key": "shein-skirts", "name_en": "Skirts", "name_cn": "半身裙", "cat_id": "1732", "url": "https://us.shein.com/Women-Skirts-c-1732.html?sort=7"},
    {"key": "shein-sweaters", "name_en": "Knitwear & Sweaters", "name_cn": "毛衣与针织衫", "cat_id": "1734", "url": "https://us.shein.com/Women-Knitwear-Sweaters-Cardigans-c-1734.html?sort=7"},
    {"key": "shein-pants", "name_en": "Pants & Jeans", "name_cn": "裤装与牛仔", "cat_id": "1740", "url": "https://us.shein.com/Women-Pants-Jeans-Leggings-c-1740.html?sort=7"},
    {"key": "shein-activewear", "name_en": "Activewear & Sets", "name_cn": "运动与套装", "cat_id": "1780", "url": "https://us.shein.com/Two-Piece-Outfits-c-1780.html?sort=7"},
    {"key": "shein-swimwear", "name_en": "Swimwear & Beach", "name_cn": "泳装与沙滩服", "cat_id": "1784", "url": "https://us.shein.com/Women-Beachwear-Swimsuits-Bikinis-c-1784.html?sort=7"}
]

def clean_amazon_image(raw_url: str) -> str:
    if not raw_url:
        return ""
    match = re.search(r'/images/I/([A-Za-z0-9+%-]+?)(?:\._.*)?\.(jpg|png|jpeg)', raw_url)
    if match:
        return f"https://m.media-amazon.com/images/I/{match.group(1)}.jpg"
    return raw_url

def clean_shein_image(raw_url: str) -> str:
    if not raw_url:
        return ""
    if raw_url.startswith('//'):
        raw_url = 'https:' + raw_url
    raw_url = re.sub(r'_[0-9]+x[0-9]+\.(jpg|png|webp)', '.jpg', raw_url)
    return raw_url

def build_prompt_recipe(title: str, category_en: str, platform: str) -> str:
    clean_title = re.sub(r'[\(\)\[\],|]', ' ', title).strip()
    clean_title = ' '.join(clean_title.split()[:12])
    return (
        f"commercial fashion catalog photography of a model wearing {clean_title}, "
        f"high-end {category_en} editorial style, clean studio background, ultra-detailed fabric textures, "
        f"professional studio lighting, trending on {platform}, 8k resolution, photorealistic"
    )

def scrape_amazon_category(cat_info: dict, max_items: int = 20) -> list:
    items = []
    seen_images = set()
    print(f"[*] [Amazon] Scraping {cat_info['name_cn']} ({cat_info['name_en']})...")
    
    try:
        resp = requests.get(cat_info['url'], headers=AMAZON_HEADERS, timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.select('div[id="gridItemRoot"], div.zg-grid-general-faceout, div.p13n-grid-content, li.a-carousel-card, [class*="p13n-sc-uncoverable-faceout"]')
            
            for card in cards:
                if len(items) >= max_items:
                    break
                
                title_el = (
                    card.select_one('div[class*="_cDEzb_p13n-sc-css-line-clamp-"]') or 
                    card.select_one('.a-link-normal span._cDEzb_p13n-sc-css-line-clamp-1_1FnBlock') or
                    card.select_one('.p13n-sc-truncate-desktop-type2') or
                    card.select_one('.a-link-normal span')
                )
                img_el = card.select_one('img')
                
                if title_el and img_el:
                    title = title_el.get_text(strip=True)
                    if len(title) < 4 or title.replace(',', '').isdigit():
                        continue
                    
                    raw_img = img_el.get('src', '')
                    clean_img = clean_amazon_image(raw_img)
                    
                    if not clean_img or clean_img in seen_images:
                        continue
                    
                    seen_images.add(clean_img)
                    idx = len(items) + 1
                    
                    items.append({
                        "id": f"amz-{cat_info['key']}-{idx}",
                        "rank": idx,
                        "platform": "Amazon Fashion",
                        "category_key": cat_info['key'],
                        "category_name": cat_info['name_cn'],
                        "category_en": cat_info['name_en'],
                        "title": title,
                        "image_url": clean_img,
                        "heat_score": 100 - (idx * 2),
                        "tags": ["Amazon Hot", cat_info['name_en'], "Bestseller"],
                        "prompt_recipe": build_prompt_recipe(title, cat_info['name_en'], "Amazon")
                    })
    except Exception as e:
        print(f"[!] [Amazon] Error fetching {cat_info['name_en']}: {e}")
        
    print(f"  -> [Amazon] Extracted {len(items)} items for {cat_info['name_en']}")
    return items

def scrape_shein_trends(page, cat_info: dict, max_items: int = 15) -> list:
    items = []
    seen_images = set()
    print(f"[*] [SHEIN] Scraping {cat_info['name_cn']} ({cat_info['name_en']})...")
    
    try:
        # 使用 domcontentloaded 并设置短超时，不阻塞网络长连接
        page.goto(cat_info['url'], wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        page.keyboard.press("Escape")
        page.evaluate("window.scrollBy(0, 1200)")
        page.wait_for_timeout(1500)

        shein_products = page.evaluate("""
            () => {
                const list = [];
                const cards = document.querySelectorAll('section.product-card, div.product-card, div[class*="product-list__item"], [data-goods-id]');
                for (const c of cards) {
                    const img = c.querySelector('img');
                    const titleEl = c.querySelector('.goods-title-link, [class*="goods-title"], [class*="product-card-info__name"]');
                    const title = titleEl ? titleEl.innerText.trim() : (img ? img.alt : '');
                    let src = '';
                    if (img) {
                        src = img.getAttribute('data-src') || img.getAttribute('src') || img.getAttribute('data-origin-src') || '';
                    }
                    if (src && !src.includes('placeholder')) {
                        list.push({ title, src });
                    }
                }
                return list;
            }
        """)

        for p in shein_products:
            if len(items) >= max_items:
                break
            
            raw_img = p.get('src', '')
            clean_img = clean_shein_image(raw_img)
            title = p.get('title', '')
            
            if not clean_img or clean_img in seen_images or len(clean_img) < 15:
                continue
            if not title or len(title) < 4:
                title = f"SHEIN Trending {cat_info['name_en']} Fashion"

            seen_images.add(clean_img)
            idx = len(items) + 1
            
            items.append({
                "id": f"shein-{cat_info['key']}-{idx}",
                "rank": idx,
                "platform": "SHEIN",
                "category_key": cat_info['key'],
                "category_name": cat_info['name_cn'],
                "category_en": cat_info['name_en'],
                "title": title[:80],
                "image_url": clean_img,
                "heat_score": 99 - idx,
                "tags": ["SHEIN Hot", "Fast Fashion", cat_info['name_en']],
                "prompt_recipe": build_prompt_recipe(title, cat_info['name_en'], "SHEIN")
            })
    except Exception as e:
        print(f"[!] [SHEIN] Error fetching {cat_info['name_en']}: {e}")

    print(f"  -> [SHEIN] Extracted {len(items)} items for {cat_info['name_en']}")
    return items

def main():
    all_products = []

    # 1. 抓取 Amazon 8 大服装核心品类 (每类 20 款，共 160 款)
    for cat in AMAZON_CATEGORIES:
        cat_items = scrape_amazon_category(cat, max_items=20)
        all_products.extend(cat_items)
        time.sleep(1)

    # 2. 抓取 SHEIN 8 大服装核心品类
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
                locale="en-US"
            )
            page = context.new_page()
            
            for cat in SHEIN_CATEGORIES:
                cat_items = scrape_shein_trends(page, cat, max_items=15)
                all_products.extend(cat_items)
                time.sleep(1)
                
            browser.close()
    except Exception as e:
        print(f"[!] Playwright execution error: {e}")

    if len(all_products) == 0 and os.path.exists("data/ecommerce_hot_products.json"):
        print("[!] Scraping yielded no data, retaining existing file.")
        return

    platforms = list(set(item["platform"] for item in all_products))
    categories = [
        "连衣裙与礼服",
        "上衣与衬衫",
        "外套与风衣",
        "半身裙",
        "毛衣与针织衫",
        "裤装与牛仔",
        "运动与套装",
        "泳装与沙滩服"
    ]

    payload = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(all_products),
        "platforms": platforms,
        "categories": categories,
        "items": all_products
    }

    os.makedirs("data", exist_ok=True)
    out_file = "data/ecommerce_hot_products.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[+] Successfully saved {len(all_products)} items across 8 categories to {out_file}!")

if __name__ == "__main__":
    main()
