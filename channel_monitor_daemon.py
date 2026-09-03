# coding=utf-8
import os
import sys
import time
import json
import secrets
import random
from loguru import logger

# Đảm bảo UTF-8 cho console Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from utils.common_util import init
from dy_apis.douyin_api import DouyinAPI
from utils.data_util import handle_work_info, download_work

HISTORY_FILE = "datas/downloaded_history.json"
DEFAULT_CHANNELS = [
    "Binbinbin9993",  # ID kênh 彬彬说车
]
# Chu kỳ quét (giây): 180 giây (3 phút) là tần suất lý tưởng
CHECK_INTERVAL = 180


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_history(history_set):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(history_set), f, ensure_ascii=False, indent=2)


def resolve_channel_sec_uid(auth, channel_id):
    """Chuyển đổi Douyin ID (unique_id) sang sec_uid."""
    if channel_id.startswith("MS4wLjABAAAA"):
        return channel_id, channel_id
    
    users = DouyinAPI.search_some_user(auth, channel_id, 3)
    target = None
    for u in users:
        info = u.get('user_info', {})
        if info.get('unique_id') == channel_id or info.get('short_id') == channel_id:
            target = info
            break
    if not target and users:
        target = users[0].get('user_info', {})
    
    if target:
        return target.get('sec_uid'), target.get('nickname', channel_id)
    return None, channel_id


def start_monitoring(channel_ids, interval=CHECK_INTERVAL):
    auth, base_path = init()
    if not auth.cookie.get('UIFID'):
        auth.cookie['UIFID'] = secrets.token_hex(192)

    history = load_history()
    logger.info(f"Khởi động Daemon theo dõi video mới cho {len(channel_ids)} kênh...")
    logger.info(f"Lịch sử hiện tại đã lưu: {len(history)} video.")

    # 1. Thu thập sec_uid của các kênh
    channel_map = {}
    for cid in channel_ids:
        sec_uid, nickname = resolve_channel_sec_uid(auth, cid)
        if sec_uid:
            channel_map[cid] = {"sec_uid": sec_uid, "nickname": nickname}
            logger.info(f"-> Đã nạp kênh: {nickname} (ID: {cid})")
        else:
            logger.error(f"-> Không tìm thấy kênh: {cid}")
        time.sleep(1)

    if not channel_map:
        logger.error("Không có kênh hợp lệ nào để theo dõi. Thoát.")
        return

    logger.info("=" * 60)
    logger.info(f"BẮT ĐẦU CHẠY VÒNG LẶP THEO DÕI (Quét mỗi {interval} giây)")
    logger.info("=" * 60)

    # 2. Vòng lặp giám sát liên tục
    while True:
        for cid, meta in channel_map.items():
            nickname = meta["nickname"]
            sec_uid = meta["sec_uid"]
            user_url = f"https://www.douyin.com/user/{sec_uid}"

            try:
                # Lấy 18 video mới nhất của kênh
                res = DouyinAPI.get_user_work_info(auth, user_url, '0')
                aweme_list = res.get('aweme_list', [])
                if not aweme_list:
                    continue

                # Sắp xếp theo create_time giảm dần để lấy video mới nhất (bỏ qua video ghim)
                sorted_works = sorted(aweme_list, key=lambda x: x.get('create_time', 0), reverse=True)

                for work in sorted_works:
                    aweme_id = work.get('aweme_id')
                    if not aweme_id or aweme_id in history:
                        continue

                    # Phát hiện video mới chưa từng tải!
                    title = work.get('desc', 'Không tiêu đề')
                    create_time = work.get('create_time', 0)
                    dt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(create_time))

                    logger.success(f"🔥 PHÁT HIỆN VIDEO MỚI TỪ KÊNH [{nickname}]!")
                    logger.info(f"   Tiêu đề: {title}")
                    logger.info(f"   ID: {aweme_id} | Ngày đăng: {dt}")
                    logger.info("   -> Đang tiến hành tải File Gốc Master về máy...")

                    # Xử lý lấy thông tin (lõi data_util đã tự động trỏ tới luồng Master)
                    work_info = handle_work_info(work)
                    saved_path = download_work(work_info, base_path['media'], save_choice='media-video')

                    logger.success(f"✅ ĐÃ TẢI XONG VIDEO MỚI: {saved_path}")

                    # Cập nhật lịch sử
                    history.add(aweme_id)
                    save_history(history)

            except Exception as err:
                logger.warning(f"Lỗi tạm thời khi quét kênh {nickname}: {err}")

            # Nghỉ ngẫu nhiên 3 - 5 giây giữa các kênh để chống bị chặn tần suất
            time.sleep(random.uniform(3, 5))

        # Nghỉ giữa các chu kỳ quét
        logger.info(f"Hoàn thành lượt kiểm tra lúc {time.strftime('%H:%M:%S')}. Nghỉ {interval}s trước khi quét tiếp...")
        time.sleep(interval)


if __name__ == '__main__':
    channels = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_CHANNELS
    start_monitoring(channels)