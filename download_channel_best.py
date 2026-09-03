# coding=utf-8
import os
import sys
import time
import secrets
import requests
from loguru import logger

# Đảm bảo UTF-8 cho console Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from utils.common_util import init
from dy_apis.douyin_api import DouyinAPI
from utils.data_util import handle_work_info, download_work


def get_original_master_stream(video_data):
    """
    Lấy trực tiếp File Gốc Master (chưa qua nén lại của Douyin).
    Sử dụng endpoint chuyển tiếp của Mobile App với ratio=default.
    """
    vid = video_data.get('play_addr', {}).get('uri')
    if not vid:
        return None, 0
    gateway_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={vid}&ratio=default"
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 musical_ly_25.1.1',
    }
    try:
        r = requests.get(gateway_url, headers=headers, allow_redirects=True, stream=True, timeout=10)
        if r.status_code == 200:
            content_length = int(r.headers.get('Content-Length', 0))
            real_url = r.url
            size_mb = content_length / (1024 * 1024)
            logger.info(f"Đã bắt link File Gốc Master: {size_mb:.2f} MB (H.264 chưa qua nén lại)")
            return real_url, content_length
    except Exception as e:
        logger.warning(f"Lỗi khi lấy link master: {e}")
    return None, 0


def download_newest_video_by_user_id(douyin_id: str):
    auth, base_path = init()
    if not auth.cookie.get('UIFID'):
        auth.cookie['UIFID'] = secrets.token_hex(192)

    logger.info(f"Đang tìm kiếm thông tin kênh Douyin: {douyin_id}...")
    users = DouyinAPI.search_some_user(auth, douyin_id, 3)
    target_user = None
    for u in users:
        info = u.get('user_info', {})
        if info.get('unique_id') == douyin_id or info.get('short_id') == douyin_id:
            target_user = info
            break
    
    if not target_user and users:
        target_user = users[0].get('user_info', {})

    if not target_user:
        logger.error(f"Không tìm thấy kênh Douyin nào với ID: {douyin_id}")
        return None

    nickname = target_user.get('nickname')
    sec_uid = target_user.get('sec_uid')
    unique_id = target_user.get('unique_id')
    logger.info(f"Tìm thấy kênh: {nickname} (ID: {unique_id}) - sec_uid: {sec_uid}")

    user_url = f"https://www.douyin.com/user/{sec_uid}"
    time.sleep(2)
    res = DouyinAPI.get_user_work_info(auth, user_url, '0')
    aweme_list = res.get('aweme_list', [])
    if not aweme_list:
        logger.warning(f"Kênh {nickname} chưa có video nào hoặc danh sách trống.")
        return None

    # Lọc và sắp xếp theo create_time giảm dần để lấy video mới nhất (bỏ qua video ghim)
    sorted_works = sorted(aweme_list, key=lambda x: x.get('create_time', 0), reverse=True)
    newest_work = sorted_works[0]

    aweme_id = newest_work.get('aweme_id')
    title = newest_work.get('desc', 'Không tiêu đề')
    create_time = newest_work.get('create_time')
    dt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(create_time))
    is_top = newest_work.get('is_top', 0)

    logger.info(f"=== Video mới nhất của kênh ===")
    logger.info(f"ID: {aweme_id}")
    logger.info(f"Tiêu đề: {title}")
    logger.info(f"Thời gian đăng: {dt} (is_top={is_top})")

    video_data = newest_work.get('video', {})
    
    # 100% chỉ tải File Gốc Master (Original Master Upload)
    master_url, size = get_original_master_stream(video_data)
    work_info = handle_work_info(newest_work)
    if master_url:
        work_info['video_addr'] = master_url

    logger.info("Bắt đầu tải File Gốc Master về máy...")
    saved_path = download_work(work_info, base_path['media'], save_choice='media-video')
    logger.info(f"TẢI XONG FILE GỐC MASTER! Lưu tại: {saved_path}")
    return saved_path


if __name__ == '__main__':
    target_id = sys.argv[1] if len(sys.argv) > 1 else 'Binbinbin9993'
    download_newest_video_by_user_id(target_id)