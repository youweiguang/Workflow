import os
import json
import re
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
}

# 1. Amazon 8 大核心欧美服装细分类目
AMAZON_CATEGORIES = [
    {"key": "dresses", "name_en": "Dresses", "name_cn": "连衣裙与礼服", "url": "https://www.amazon.com/gp/bestsellers/fashion/1045024/"},
    {"key": "tops", "name_en": "Tops & Shirts", "name_cn": "上衣与衬衫", "url": "https://www.amazon.com/gp/bestsellers/fashion/2368343011/"},
    {"key": "outerwear", "name_en": "Outerwear & Coats", "name_cn": "外套与风衣", "url": "https://www.amazon.com/gp/bestsellers/fashion/1044456/"},
    {"key": "skirts", "name_en": "Skirts", "name_cn": "半身裙", "url": "https://www.amazon.com/gp/bestsellers/fashion/1045022/"},
    {"key": "sweaters", "name_en": "Sweaters & Knits", "name_cn": "毛衣与针织衫", "url": "https://www.amazon.com/gp/bestsellers/fashion/1044442/"},
    {"key": "pants", "name_en": "Pants & Jeans", "name_cn": "裤装与牛仔", "url": "https://www.amazon.com/gp/bestsellers/fashion/1048184/"},
    {"key": "activewear", "name_en": "Activewear & Sets", "name_cn": "运动与套装", "url": "https://www.amazon.com/gp/bestsellers/fashion/1045028/"},
    {"key": "swimwear", "name_en": "Swimwear & Beach", "name_cn": "泳装与沙滩服", "url": "https://www.amazon.com/gp/bestsellers/fashion/1046674/"}
]

# 2. ASOS 8 大核心欧美潮流分类 (官方公开数据端点)
ASOS_CATEGORIES = [
    {"key": "dresses", "name_en": "Dresses", "name_cn": "连衣裙与礼服", "cat_id": "8799"},
    {"key": "tops", "name_en": "Tops & Shirts", "name_cn": "上衣与衬衫", "cat_id": "4169"},
    {"key": "outerwear", "name_en": "Outerwear & Coats", "name_cn": "外套与风衣", "cat_id": "2641"},
    {"key": "skirts", "name_en": "Skirts", "name_cn": "半身裙", "cat_id": "2639"},
    {"key": "sweaters", "name_en": "Sweaters & Knits", "name_cn": "毛衣与针织衫", "cat_id": "2637"},
    {"key": "pants", "name_en": "Pants & Jeans", "name_cn": "裤装与牛仔", "cat_id": "2640"},
    {"key": "activewear", "name_en": "Activewear & Sets", "name_cn": "运动与套装", "cat_id": "26090"},
    {"key": "swimwear", "name_en": "Swimwear & Beach", "name_cn": "泳装与沙滩服", "cat_id": "2238"}
]

def clean_amazon_image(raw_url: str) -> str:
    """提取亚马逊图片 ID 并转换为国内直连的全球高清 CDN 地址"""
    if not raw_url:
        return ""
    match = re.search(r'/images/I/([A-Za-z0-9+%-]+?)(?:\._.*)?\.(jpg|png|jpeg)', raw_url)
    if match:
        return f"https://m.media-amazon.com/images/I/{match.group(1)}.jpg"
    return raw_url

def clean_asos_image(raw_url: str) -> str:
    """转换 ASOS 图片为高清直连大图"""
    if not raw_url:
        return ""
    if raw_url.startswith('//'):
        raw_url = 'https:' + raw_url
    if not raw_url.startswith('http'):
        raw_url = f"https://{raw_url}"
    return f"{raw_url}?$n_640w$&wid=640&fit=constrain"

def build_prompt_recipe(title: str, category_en: str, platform: str) -> str:
    """基于商品标题提炼适用于 AI 服装创作的高质量 Prompt"""
    clean_title = re.sub(r'[\(\)\[\],|]', ' ', title).strip()
    clean_title = ' '.join(clean_title.split()[:12])
    return (
        f"commercial fashion catalog photography of a model wearing {clean_title}, "
        f"high-end {category_en} editorial style, clean studio background, ultra-detailed fabric textures, "
        f"professional studio lighting, trending on {platform}, 8k resolution, photorealistic"
    )

def scrape_amazon_category(cat_info: dict, max_items: int = 15) -> list:
    items = []
    seen_images = set()
    print(f"[*] [Amazon] Scraping {cat_info['name_cn']} ({cat_info['name_en']})...")
    
    try:
        resp = requests.get(cat_info['url'], headers=HEADERS, timeout=20)
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
                        "tags": ["Amazon Bestseller", cat_info['name_en'], "Hot Selling"],
                        "prompt_recipe": build_prompt_recipe(title, cat_info['name_en'], "Amazon")
                    })
        else:
            print(f"[!] [Amazon] HTTP {resp.status_code} for {cat_info['name_en']}")
    except Exception as e:
        print(f"[!] [Amazon] Error fetching {cat_info['name_en']}: {e}")
        
    print(f"  -> [Amazon] Extracted {len(items)} items for {cat_info['name_en']}")
    return items

def scrape_asos_category(cat_info: dict, max_items: int = 10) -> list:
    items = []
    seen_images = set()
    print(f"[*] [ASOS] Scraping {cat_info['name_cn']} ({cat_info['name_en']})...")
    
    url = f"https://api.asos.com/product/search/v2/categories/{cat_info['cat_id']}?offset=0&limit={max_items*2}&store=US&lang=en-US&currency=USD&sort=freshness"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            products = data.get('products', [])
            for p in products:
                if len(items) >= max_items:
                    break
                
                title = p.get('name', '').strip()
                raw_img = p.get('imageUrl', '')
                clean_img = clean_asos_image(raw_img)
                
                if not title or not clean_img or clean_img in seen_images:
                    continue
                
                seen_images.add(clean_img)
                idx = len(items) + 1
                
                items.append({
                    "id": f"asos-{cat_info['key']}-{idx}",
                    "rank": idx,
                    "platform": "ASOS Trends",
                    "category_key": cat_info['key'],
                    "category_name": cat_info['name_cn'],
                    "category_en": cat_info['name_en'],
                    "title": title,
                    "image_url": clean_img,
                    "heat_score": 98 - (idx * 2),
                    "tags": ["ASOS Trend", "UK/US Fashion", cat_info['name_en']],
                    "prompt_recipe": build_prompt_recipe(title, cat_info['name_en'], "ASOS")
                })
        else:
            print(f"[!] [ASOS] HTTP {resp.status_code} for {cat_info['name_en']}")
    except Exception as e:
        print(f"[!] [ASOS] Error fetching {cat_info['name_en']}: {e}")
        
    print(f"  -> [ASOS] Extracted {len(items)} items for {cat_info['name_en']}")
    return items

def main():
    all_products = []
    
    # 1. 抓取 Amazon 8 大核心品类 (每类 15 款，共 120 款)
    for cat in AMAZON_CATEGORIES:
        cat_items = scrape_amazon_category(cat, max_items=15)
        all_products.extend(cat_items)
        time.sleep(0.8)

    # 2. 抓取 ASOS 8 大核心品类 (每类 10 款，共 80 款)
    for cat in ASOS_CATEGORIES:
        cat_items = scrape_asos_category(cat, max_items=10)
        all_products.extend(cat_items)
        time.sleep(0.5)

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

    print(f"[+] Successfully saved {len(all_products)} items from {platforms} across {len(categories)} categories to {out_file}!")

if __name__ == "__main__":
    main()
