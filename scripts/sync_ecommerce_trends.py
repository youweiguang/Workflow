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

# 欧美时尚核心服装细分类目（使用最稳定的标准 /gp/bestsellers 路径）
CATEGORIES = [
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
    clean_title = re.sub(r'[\(\)\[\],|]', ' ', title).strip()
    clean_title = ' '.join(clean_title.split()[:12])
    return (
        f"commercial fashion catalog photography of a model wearing {clean_title}, "
        f"high-end {category_en} editorial style, clean studio background, ultra-detailed fabric textures, "
        f"professional studio lighting, 8k resolution, photorealistic"
    )

def scrape_category(cat_info: dict, max_items: int = 8) -> list:
    items = []
    seen_images = set()
    print(f"[*] Scraping {cat_info['name_cn']} ({cat_info['name_en']})...")
    
    try:
        resp = requests.get(cat_info['url'], headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # 兼容多种亚马逊 Best Sellers 网格卡片结构
            cards = soup.select('div[id="gridItemRoot"], div.zg-grid-general-faceout, div.p13n-grid-content, li.a-carousel-card')
            
            for card in cards:
                if len(items) >= max_items:
                    break
                
                # 兼容多版本标题选择器
                title_el = (
                    card.select_one('div[class*="_cDEzb_p13n-sc-css-line-clamp-"]') or 
                    card.select_one('.a-link-normal span._cDEzb_p13n-sc-css-line-clamp-1_1FnBlock') or
                    card.select_one('.p13n-sc-truncate-desktop-type2') or
                    card.select_one('.a-link-normal span')
                )
                img_el = card.select_one('img')
                
                if title_el and img_el:
                    title = title_el.get_text(strip=True)
                    # 过滤纯数字等误抓评论数的情况
                    if len(title) < 5 or title.replace(',', '').isdigit():
                        continue
                    
                    raw_img = img_el.get('src', '')
                    clean_img = clean_image_url(raw_img)
                    
                    # 过滤空图与重复图片
                    if not clean_img or clean_img in seen_images:
                        continue
                    
                    seen_images.add(clean_img)
                    idx = len(items) + 1
                    
                    items.append({
                        "id": f"hot-{cat_info['key']}-{idx}",
                        "rank": idx,
                        "platform": "Amazon Fashion US",
                        "category_key": cat_info['key'],
                        "category_name": cat_info['name_cn'],
                        "category_en": cat_info['name_en'],
                        "title": title,
                        "image_url": clean_img,
                        "heat_score": 100 - (idx * 2),
