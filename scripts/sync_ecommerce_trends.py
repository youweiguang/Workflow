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
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
}

# 8 大核心服装品类 (Amazon Fashion US)
AMAZON_CATEGORIES = [
    {
        "key": "dresses",
        "name_en": "Dresses",
        "name_cn": "连衣裙与礼服",
        "url": "https://www.amazon.com/gp/bestsellers/fashion/1045024/"
    },
    {
        "key": "tops",
        "name_en": "Tops & Shirts",
        "name_cn": "上衣与衬衫",
        "url": "https://www.amazon.com/gp/bestsellers/fashion/2368343011/"
    },
    {
        "key": "outerwear",
        "name_en": "Outerwear & Coats",
        "name_cn": "外套与风衣",
        "url": "https://www.amazon.com/gp/bestsellers/fashion/1044456/"
    },
    {
        "key": "skirts",
        "name_en": "Skirts",
        "name_cn": "半身裙",
        "url": "https://www.amazon.com/gp/bestsellers/fashion/1045022/"
    },
    {
        "key": "sweaters",
        "name_en": "Sweaters & Knits",
        "name_cn": "毛衣与针织衫",
        "url": "https://www.amazon.com/gp/bestsellers/fashion/1044442/"
    },
    {
        "key": "pants",
        "name_en": "Pants & Jeans",
        "name_cn": "裤装与牛仔",
        "url": "https://www.amazon.com/gp/bestsellers/fashion/1048184/"
    },
    {
        "key": "activewear",
        "name_en": "Activewear & Sets",
        "name_cn": "运动与套装",
        "url": "https://www.amazon.com/gp/bestsellers/fashion/2368344011/"
    },
    {
        "key": "swimwear",
        "name_en": "Swimwear & Beach",
        "name_cn": "泳装与沙滩服",
        "url": "https://www.amazon.com/gp/bestsellers/fashion/1046672/"
    }
]

# 8 大核心服装品类 (SHEIN Trends)
SHEIN_CATEGORIES = [
    {
        "key": "shein-dresses",
        "name_en": "Dresses",
        "name_cn": "连衣裙与礼服",
        "url": "https://us.shein.com/trends/Women-Dresses-sc-00667087.html?sort=7"
    },
    {
        "key": "shein-tops",
        "name_en": "Tops & Blouses",
        "name_cn": "上衣与衬衫",
        "url": "https://us.shein.com/trends/Women-Tops-Blouses-Tees-sc-00667088.html?sort=7"
    },
    {
        "key": "shein-outerwear",
        "name_en": "Outerwear & Coats",
        "name_cn": "外套与风衣",
        "url": "https://us.shein.com/trends/Women-Outerwear-Coats-Jackets-sc-00667089.html?sort=7"
    },
    {
        "key": "shein-skirts",
        "name_en": "Skirts",
        "name_cn": "半身裙",
        "url": "https://us.shein.com/trends/Women-Skirts-sc-00667090.html?sort=7"
    },
    {
        "key": "shein-sweaters",
        "name_en": "Knitwear & Sweaters",
        "name_cn": "毛衣与针织衫",
        "url": "https://us.shein.com/trends/Women-Knitwear-Sweaters-Cardigans-sc-00667091.html?sort=7"
    },
    {
        "key": "shein-pants",
        "name_en": "Pants & Jeans",
        "name_cn": "裤装与牛仔",
        "url": "https://us.shein.com/trends/Women-Pants-Jeans-Leggings-sc-00667092.html?sort=7"
    },
    {
        "key": "shein-activewear",
        "name_en": "Activewear & Sets",
        "name_cn": "运动与套装",
        "url": "https://us.shein.com/trends/Women-Two-Piece-Outfits-Sets-sc-00667093.html?sort=7"
    },
    {
        "key": "shein-swimwear",
        "name_en": "Swimwear & Beach",
        "name_cn": "泳装与沙滩服",
        "url": "https://us.shein.com/trends/Women-Beachwear-Swimsuits-Bikinis-sc-00667094.html?sort=7"
    }
]

def clean_amazon_image(raw_url: str) -> str:
    """提取亚马逊图片 ID 并转换为国内直连的全球高清 CDN 地址"""
    if not raw_url:
        return ""
    match = re.search(r'/images/I/([A-Za-z0-9+%-]+?)(?:\._.*)?\.(jpg|png|jpeg)', raw_url)
    if match:
        return f"https://m.media-amazon.com/images/I/{match.group(1)}.jpg"
    return raw_url

def clean_shein_image(raw_url: str) -> str:
    """清洗 SHEIN 缩略图为国内直连高清大图"""
    if not raw_url:
        return ""
    if raw_url.startswith('//'):
        raw_url = 'https:' + raw_url
    raw_url = re.sub(r'_[0-9]+x[0-9]+\.(jpg|png|webp)', '.jpg', raw_url)
    return raw_url

def build_prompt_recipe(title: str, category_en: str, platform: str) -> str:
    """基于商品标题提炼适用于 AI 服装创作的高质量 Prompt"""
    clean_title = re.sub(r'[\(\)\[\],|]', ' ', title).strip()
    clean_title = ' '.join(clean_title.split()[:12])
    return (
        f"commercial fashion catalog photography of a model wearing {clean_title}, "
        f"high-end {category_en} editorial style, clean studio background, ultra-detailed fabric textures, "
        f"professional studio lighting, trending on {platform}, 8k resolution, photorealistic"
    )

def scrape_amazon_category(cat_info: dict, max_items: int = 10) -> list:
    items = []
    seen_images = set()
    print(f"[*] [Amazon] Scraping {cat_info['name_cn']} ({cat_info['name_en']})...")
    
    try:
        resp = requests.get(cat_info['url'], headers=AMAZON_HEADERS, timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.select('div[id="gridItemRoot"], div.zg-grid-general-faceout, div.p13n-grid-content, li.a-carousel-card')
            
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
                    if len(title) < 5 or title.replace(',', '').isdigit():
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
        else:
            print(f"[!] [Amazon] HTTP {resp.status_code} for {cat_info['name_en']}")
    except Exception as e:
        print(f"[!] [Amazon] Error fetching {cat_info['name_en']}: {e}")
        
    print(f"  -> [Amazon] Extracted {len(items)} items for {cat_info['name_en']}")
    return items

def scrape_shein_trends(playwright_browser, cat_info: dict, max_items: int = 10) -> list:
    items = []
    seen_images = set()
    print(f"[*] [SHEIN] Scraping {cat_info['name_cn']} ({cat_info['name_en']})...")
    
    try:
        context = playwright_browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            viewport={"width": 390, "height": 844},
            locale="en-US"
        )
        page = context.new_page()
        page.goto(cat_info['url'], wait_until="domcontentloaded", timeout=30000)
        
        page.evaluate("window.scrollBy(0, 800)")
        time.sleep(2)

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        cards = soup.select('.product-list-item, .fsp-element, .product-card, div[class*="product-card"], a[class*="goods-title"]')
        if not cards:
            cards = soup.select('div[class*="product"], a[href*="-p-"]')

        for card in cards:
            if len(items) >= max_items:
                break
            
            img_el = card.select_one('img')
            title = card.get_text(strip=True) or card.get('title') or ""
            
            if img_el:
                raw_img = img_el.get('data-src') or img_el.get('src') or ""
                clean_img = clean_shein_image(raw_img)
                
                if not clean_img or 'placeholder' in clean_img or clean_img in seen_images:
                    continue
                if not title or len(title) < 4:
                    title = f"SHEIN Trending {cat_info['name_en']} Item"

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
                    "tags": ["SHEIN Trending", "Fast Fashion", cat_info['name_en']],
                    "prompt_recipe": build_prompt_recipe(title, cat_info['name_en'], "SHEIN")
                })
        context.close()
    except Exception as e:
        print(f"[!] [SHEIN] Error fetching {cat_info['name_en']}: {e}")

    print(f"  -> [SHEIN] Extracted {len(items)} items for {cat_info['name_en']}")
    return items

def main():
    all_products = []

    # 1. 抓取 Amazon 8 大服装核心品类 (每类 10 款)
    for cat in AMAZON_CATEGORIES:
        cat_items = scrape_amazon_category(cat, max_items=20)
        all_products.extend(cat_items)
        time.sleep(1)

    # 2. 抓取 SHEIN 8 大服装核心品类 (每类 10 款)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for cat in SHEIN_CATEGORIES:
                cat_items = scrape_shein_trends(browser, cat, max_items=20)
                all_products.extend(cat_items)
                time.sleep(0.5)
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
