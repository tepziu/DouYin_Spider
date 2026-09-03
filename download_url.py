# coding=utf-8
import os
import sys
import re
import time
import requests
from loguru import logger

# Đảm bảo UTF-8 cho console Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from utils.common_util import init
from dy_apis.douyin_api import DouyinAPI
from utils.data_util import handle_work_info, download_work


def extract_url(text: str) -> str:
    """Bóc tách URL từ văn bản copy chia sẻ của Douyin."""
    match = re.search(r'https?://[a-zA-Z0-9\.\-_/]+', text)
    if match:
        return match.group(0)
    return text.strip()


def resolve_short_url(url: str) -> str:
    """Phân giải short URL (v.douyin.com) sang URL video chuẩn."""
    if "v.douyin.com" in url:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        r = requests.get(url, headers=headers, allow_redirects=False, timeout=10)
        location = r.headers.get("Location")
        if location:
            # Bóc tách aweme_id từ Location
            m = re.search(r'/video/(\d+)', location)
            if m:
                return f"https://www.douyin.com/video/{m.group(1)}"
            return location
    return url


def download_video_from_url(input_text: str):
    auth, base_path = init()
    
    raw_url = extract_url(input_text)
    logger.info(f"Đang phân giải link: {raw_url}")
    target_url = resolve_short_url(raw_url)
    logger.info(f"Link video chuẩn: {target_url}")

    logger.info("Đang lấy thông tin tác phẩm từ Douyin...")
    res = DouyinAPI.get_work_info(auth, target_url)
    detail = res.get("aweme_detail", {})
    if not detail:
        logger.error("Không lấy được thông tin chi tiết video!")
        return None

    title = detail.get("desc", "Không tiêu đề")
    author_name = detail.get("author", {}).get("nickname", "Tác giả")
    vid = detail.get("video", {}).get("play_addr", {}).get("uri", "")

    logger.info(f"=== Thông tin video ===")
    logger.info(f"Tác giả: {author_name}")
    logger.info(f"Tiêu đề: {title}")
    logger.info(f"VID: {vid}")

    work_info = handle_work_info(detail)
    logger.info(f"Bắt đầu tải File Gốc Master (chưa qua nén lại)...")
    saved_path = download_work(work_info, base_path["media"], save_choice="media-video")
    logger.success(f"TẢI HOÀN TẤT FILE GỐC MASTER! Đường dẫn: {saved_path}")
    return saved_path


if __name__ == '__main__':
    text = sys.argv[1] if len(sys.argv) > 1 else "https://v.douyin.com/hBUbjDqMhOI/"
    download_video_from_url(text)