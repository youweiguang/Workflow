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
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

# 欧美时尚核心服装细分类目
CATEGORIES = [
    {
        "key": "dresses",
        "name_en": "Dresses",
        "name_cn": "连衣裙与礼服",
        "url": "https://www.amazon.com/Best-Sellers-Womens-Dresses/zgbs/fashion/1045024/"
    },
    {
        "key": "tops",
        "name_en": "Tops & Shirts",
        "name_cn": "上衣与衬衫",
        "url": "https://www.amazon.com/Best-Sellers-Womens-Tops-Tees-Shirts/zgbs/fashion/2368343011/"
    },
    {
        "key": "outerwear",
        "name_en": "Outerwear & Coats",
        "name_cn": "外套与风衣",
        "url": "https://www.amazon.com/Best-Sellers-Womens-Outerwear-Jackets-Coats/zgbs/fashion/1044456/"
    },
    {
        "key": "skirts",
        "name_en": "Skirts",
        "name_cn": "半身裙",
        "url": "https://www.amazon.com/Best-Sellers-Womens-Skirts/zgbs/fashion/1045022/"
    },
    {
        "key": "sweaters",
        "name_en": "Sweaters & Knits",
        "name_cn": "毛衣与针织衫",
        "url": "https://www.amazon.com/Best-Sellers-Womens-Sweaters/zgbs/fashion/1044442/"
    }
]

def clean_image_url(raw_url: str) -> str:
    """提取亚马逊图片 ID 并转换为国内直连的全球高清 CDN 地址"""
    if not raw_url:
        return ""
    match = re.search(r'/images/I/([A-Za-z0-9+%-]+?)(?:\._.*)?\.(jpg|png|jpeg)', raw_url)
    if match:
        return f"https://m.media-amazon.com/images/I/{match.group(1)}.jpg"
    return raw_url

def build_prompt_recipe(title: str, category_en: str) -> str:
    """基于商品标题提炼适用于 AI 服装创作的高质量 Prompt"""
    # 清洗标题中的多余品牌名或促销符号
    clean_title = re.sub(r'[\(\)\[\],]', ' ', title).strip()
    clean_title = ' '.join(clean_title.split()[:12])
    return (
        f"commercial fashion catalog photography of a model wearing {clean_title}, "
        f"high-end {category_en} editorial style, clean background, ultra-detailed fabric textures, "
        f"professional studio lighting, 8k resolution, photorealistic"
    )

def scrape_category(cat_info: dict, max_items: int = 10) -> list:
    items = []
    print(f"[*] Scraping {cat_info['name_cn']} ({cat_info['name_en']})...")
    try:
        resp = requests.get(cat_info['url'], headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.select('.zg-grid-general-faceout, [id="gridItemRoot"]')[:max_items]
            
            for idx, card in enumerate(cards):
                title_el = card.select_one('div[class*="_cDEzb_p13n-sc-css-line-clamp-"]') or card.select_one('.a-link-normal span')
                img_el = card.select_one('img')
                
                if title_el and img_el:
                    title = title_el.get_text(strip=True)
                    raw_img = img_el.get('src', '')
                    clean_img = clean_image_url(raw_img)
                    
                    items.append({
                        "id": f"hot-{cat_info['key']}-{idx+1}",
                        "rank": idx + 1,
                        "platform": "Amazon Fashion US",
                        "category_key": cat_info['key'],
                        "category_name": cat_info['name_cn'],
                        "category_en": cat_info['name_en'],
                        "title": title,
                        "image_url": clean_img,
                        "heat_score": 100 - (idx * 2),
                        "tags": ["Bestseller", cat_info['name_en'], "Spring/Summer 2026"],
                        "prompt_recipe": build_prompt_recipe(title, cat_info['name_en'])
                    })
        else:
            print(f"[!] Warning: HTTP {resp.status_code} for {cat_info['name_en']}")
    except Exception as e:
        print(f"[!] Error fetching {cat_info['name_en']}: {e}")
    return items

def main():
    all_products = []
    for cat in CATEGORIES:
        cat_items = scrape_category(cat, max_items=8)
        all_products.extend(cat_items)
        time.sleep(1.5) # 礼貌延时

    # 容灾兜底：若全网拦截则保持原有/内置数据
    if len(all_products) == 0 and os.path.exists("data/ecommerce_hot_products.json"):
        print("[!] Scraping failed, keeping existing dataset.")
        return

    payload = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(all_products),
        "categories": [c["name_cn"] for c in CATEGORIES],
        "items": all_products
    }

    os.makedirs("data", exist_ok=True)
    out_file = "data/ecommerce_hot_products.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[+] Successfully saved {len(all_products)} trending fashion items to {out_file}!")

if __name__ == "__main__":
    main()
