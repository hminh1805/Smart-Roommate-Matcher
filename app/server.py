#!/usr/bin/env python3
"""Smart Roommate Matcher - backend (Python stdlib + SQLite, không cần cài thư viện).

Chạy:  python server.py   ->  http://localhost:8000
"""
import csv
import gzip
import hashlib
import io
import json
import mimetypes
import os
import queue
import random
import re
import secrets
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "data", "app.db"))
PORT = int(os.environ.get("PORT", "8000"))
if not IS_PG:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
if IS_PG:
    import psycopg
    from psycopg.rows import dict_row

GFORM_ID = os.environ.get("GFORM_ID", "1FAIpQLScdrtJhaZqZPcbm23yuSHfcj3BnW_cLO5_iGEoHl1ubgLnuKw").strip()
GSHEET_ID = os.environ.get("GSHEET_ID", "1yyhkIJoekoE07vBuJdx3BTPCEeSwWZqS3ysyo1geUwU").strip()
GFORM_VIEW_URL = f"https://docs.google.com/forms/d/e/{GFORM_ID}/viewform" if GFORM_ID else ""
GFORM_POST_URL = os.environ.get(
    "GFORM_POST_URL",
    f"https://docs.google.com/forms/d/e/{GFORM_ID}/formResponse" if GFORM_ID else "",
).strip()
GSHEET_EDIT_URL = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit" if GSHEET_ID else ""
GSHEET_CSV_URL = os.environ.get(
    "GSHEET_CSV_URL",
    f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/export?format=csv" if GSHEET_ID else "",
).strip()
GSHEET_XLSX_URL = os.environ.get(
    "GSHEET_XLSX_URL",
    f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/export?format=xlsx" if GSHEET_ID else "",
).strip()

GFORM_DEV = {
    "mobile": "📱 Điện thoại",
    "desktop": "💻 Laptop / Máy tính bảng",
    "both": "📱💻 Cả hai",
}
GFORM_STAR = {
    1: "1 ★ (Chưa ổn)",
    2: "2 ★",
    3: "3 ★",
    4: "4 ★",
    5: "5 ★ (Rất ổn)",
}
GFORM_FEAT_PAIRS = [
    ("Quẹt kiểu Tinder mượt mà", "Quẹt kiểu Tinder mượt mà, giao diện đẹp"),
    ("Chấm % & 5 ô thói quen", "Chấm % hợp nhau & 5 ô so sánh thói quen rõ ràng"),
    ("Bộ lọc 10 nhóm + Ảnh thật", "Bộ lọc 10 nhóm tiêu chí + Ảnh thật"),
    ("Match + Gợi ý phòng trọ", "Màn hình Match kèm gợi ý phòng trọ gần trường"),
    ("Chat + Gợi ý mở lời", "Nhắn tin trực tiếp + câu gợi ý mở lời thông minh"),
    ("Xe chuyển · Dọn dẹp · Đồ cũ", "Đặt xe chuyển đồ, dọn phòng, đồ cũ 1 chạm"),
    ("Miễn phí 0đ sinh viên", "Miễn phí 0đ hoàn toàn cho sinh viên"),
]
GFORM_FEAT_TO_FULL = dict(GFORM_FEAT_PAIRS)
GFORM_ISS = {
    "smooth": "✅ Chạy rất mượt, không gặp lỗi gì",
    "lag": "🐢 Hơi chậm / lag nhẹ ở một số màn hình",
    "ui_bug": "🎨 Có chỗ hiển thị bị lệch / đè chữ",
    "func_bug": "⚙️ Gặp lỗi chức năng (quẹt / chat / đăng nhập)",
}
GFORM_SHARK = {
    "strong": "💰 Đầu tư mạnh tay (từ 3 tỷ ảo trở lên)",
    "explore": "💡 Sẵn sàng thăm dò (1 – 2 tỷ ảo)",
    "consider": "🤔 Cân nhắc thêm nếu cải tiến rõ ràng hơn",
    "no": "⏸️ Chưa sẵn sàng đầu tư",
}
GFORM_PITCH = {
    "viral": "Chứng minh rõ hơn cách kéo người dùng mới (chi phí 0đ – viral trường ĐH)",
    "margin": "Làm rõ biên lợi nhuận & cam kết từ chủ trọ / đối tác xe chuyển",
    "safety": "Cách chống tài khoản ảo & giữ an toàn cho sinh viên khi ở ghép",
    "scale": "Lộ trình mở rộng ra nhiều trường ĐH trong 6–12 tháng",
}

HABITS = ["sleep", "tidy", "money", "noise", "guest"]
WEIGHTS = {"sleep": 1.5, "tidy": 1.5, "money": 1.5, "noise": 1.0, "guest": 1.0}
HABIT_LABEL = {
    "sleep": "Giờ giấc", "tidy": "Gọn gàng", "money": "Sòng phẳng tiền",
    "noise": "Độ ồn", "guest": "Đưa bạn về phòng",
}
HABIT_ADVICE = {
    "sleep": "Thống nhất giờ tắt đèn / giờ báo thức để không ai bị làm phiền.",
    "tidy": "Lập lịch trực nhật luân phiên và quy ước khu vực chung.",
    "money": "Dùng sổ chung chia tiền điện, nước, wifi rõ ràng theo tháng.",
    "noise": "Thỏa thuận khung giờ yên tĩnh và dùng tai nghe khi cần.",
    "guest": "Báo trước khi đưa bạn về phòng và giới hạn giờ về.",
}
COMMISSION = {"room": 0.10, "truck": 0.12, "clean": 0.12, "used": 0.15}
BOT_LIKE_THRESHOLD = 66
SUPER_DAILY = 3
VN_TZ = timezone(timedelta(hours=7))


def fmt_vn_time(ts=None):
    if ts is None:
        ts = time.time()
    return datetime.fromtimestamp(float(ts), VN_TZ).strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------------------------------------------- database & caches
_PG_POOL = queue.LifoQueue(maxsize=8)
_AUTH_CACHE = {}
_AUTH_LOCK = threading.Lock()
_USERS_CACHE = {"ts": 0.0, "rows": {}}
_USERS_LOCK = threading.Lock()
_GSHEET_LOCK = threading.Lock()
_GSHEET_CACHE = {"ts": 0.0, "rows": [], "ok": False}
_RECENT_SYNCED = []
_ROOMS_CACHE = []
_SERVICES_CACHE = {}
_STATIC_CACHE = {}


def _invalidate_users_cache():
    with _USERS_LOCK:
        _USERS_CACHE["ts"] = 0.0
        _USERS_CACHE["rows"] = {}


def _get_all_users(c):
    now = time.time()
    with _USERS_LOCK:
        if _USERS_CACHE["rows"] and now - _USERS_CACHE["ts"] < 30.0:
            return dict(_USERS_CACHE["rows"])
    rows = {r["id"]: dict(r) for r in c.execute("SELECT * FROM users").fetchall()}
    with _USERS_LOCK:
        _USERS_CACHE["ts"] = time.time()
        _USERS_CACHE["rows"] = dict(rows)
    return rows


def _cache_get_user(tok):
    if not tok:
        return None
    with _AUTH_LOCK:
        item = _AUTH_CACHE.get(tok)
        if not item:
            return None
        u, exp = item
        if time.time() > exp:
            _AUTH_CACHE.pop(tok, None)
            return None
        return dict(u)


def _cache_set_user(tok, row):
    if not tok or not row:
        return
    with _AUTH_LOCK:
        if len(_AUTH_CACHE) > 2000:
            _AUTH_CACHE.clear()
        _AUTH_CACHE[tok] = (dict(row), time.time() + 600)


def _cache_drop_token(tok):
    if not tok:
        return
    with _AUTH_LOCK:
        _AUTH_CACHE.pop(tok, None)


def _cache_drop_user(uid):
    with _AUTH_LOCK:
        for k in [k for k, (u, _) in _AUTH_CACHE.items() if u["id"] == uid]:
            _AUTH_CACHE.pop(k, None)


class DB:
    def __init__(self):
        self._closed = False
        if IS_PG:
            self.conn = None
            now = time.time()
            while True:
                try:
                    conn, ts = _PG_POOL.get_nowait()
                except queue.Empty:
                    break
                if conn.closed or now - ts > 900:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    continue
                try:
                    if conn.info.transaction_status != 0:
                        conn.rollback()
                    self.conn = conn
                    break
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
            if self.conn is None:
                self.conn = psycopg.connect(
                    DATABASE_URL,
                    autocommit=True,
                    row_factory=dict_row,
                    prepare_threshold=None,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3,
                )
        else:
            self.conn = sqlite3.connect(DB_PATH, timeout=15)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql, params=()):
        if IS_PG:
            sql = sql.replace("?", "%s")
        return self.conn.execute(sql, params)

    def insert_id(self, sql, params=()):
        if IS_PG:
            return self.execute(sql + " RETURNING id", params).fetchone()["id"]
        return self.execute(sql, params).lastrowid

    def exec_script(self, script):
        if IS_PG:
            for stmt in script.split(";"):
                if stmt.strip():
                    self.conn.execute(stmt)
        else:
            self.conn.executescript(script)

    def commit(self):
        if not IS_PG:
            self.conn.commit()

    def rollback(self):
        try:
            if self.conn and (not IS_PG or (not self.conn.closed and self.conn.info.transaction_status != 0)):
                self.conn.rollback()
        except Exception:
            pass

    def discard(self):
        self._closed = True
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        self.conn = None

    def close(self):
        if self._closed or not self.conn:
            return
        self._closed = True
        conn = self.conn
        self.conn = None
        if IS_PG:
            try:
                if conn.closed:
                    return
                if conn.info.transaction_status != 0:
                    conn.rollback()
                _PG_POOL.put_nowait((conn, time.time()))
                return
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def db():
    return DB()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, salt TEXT, pw TEXT,
  name TEXT, emoji TEXT DEFAULT '🙂', color INTEGER DEFAULT 0, university TEXT DEFAULT '',
  bio TEXT DEFAULT '', age INTEGER DEFAULT 20, gender TEXT DEFAULT 'khac', pref_gender TEXT DEFAULT 'any',
  budget_min REAL DEFAULT 2, budget_max REAL DEFAULT 4, area TEXT DEFAULT '',
  sleep INTEGER DEFAULT 3, tidy INTEGER DEFAULT 3, money INTEGER DEFAULT 3, noise INTEGER DEFAULT 3, guest INTEGER DEFAULT 3,
  tags TEXT DEFAULT '[]', is_bot INTEGER DEFAULT 0, onboarded INTEGER DEFAULT 0, created REAL, created_real_time TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, created REAL, created_real_time TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS swipes(from_id INTEGER, to_id INTEGER, kind TEXT, created REAL, created_real_time TEXT DEFAULT '', PRIMARY KEY(from_id,to_id));
CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY AUTOINCREMENT, a INTEGER, b INTEGER, score INTEGER, created REAL, created_real_time TEXT DEFAULT '', active INTEGER DEFAULT 1, UNIQUE(a,b));
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER, sender INTEGER, text TEXT, created REAL, created_real_time TEXT DEFAULT '', visible_at REAL, read INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY, name TEXT, price INTEGER, district TEXT, descr TEXT, near TEXT, dist TEXT, sponsored INTEGER, emoji TEXT, beds INTEGER, amenities TEXT, owner TEXT);
CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY, kind TEXT, name TEXT, price INTEGER, unit TEXT, descr TEXT, rating REAL, jobs INTEGER, emoji TEXT, promoted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, item_id INTEGER, item_name TEXT, amount INTEGER, commission INTEGER, note TEXT, date TEXT, status TEXT DEFAULT 'new', created REAL, created_real_time TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS impressions(id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER, user_id INTEGER, created REAL, created_real_time TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER DEFAULT 0, tester_name TEXT DEFAULT 'Ẩn danh',
  device TEXT DEFAULT 'mobile', r_ui INTEGER DEFAULT 5, r_ux INTEGER DEFAULT 5,
  r_match INTEGER DEFAULT 5, r_eco INTEGER DEFAULT 5, r_overall INTEGER DEFAULT 5,
  fav_features TEXT DEFAULT '[]', issue_type TEXT DEFAULT 'smooth',
  shark_invest TEXT DEFAULT 'explore', pitch_closer TEXT DEFAULT '',
  suggestion TEXT DEFAULT '', synced INTEGER DEFAULT 0, created REAL, created_real_time TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_feedback_created ON feedback(created);
CREATE INDEX IF NOT EXISTS ix_msg ON messages(match_id,id);
CREATE INDEX IF NOT EXISTS ix_swipes_to ON swipes(to_id,from_id);
CREATE INDEX IF NOT EXISTS ix_swipes_from_kind ON swipes(from_id,kind,created);
CREATE INDEX IF NOT EXISTS ix_matches_a ON matches(a,active);
CREATE INDEX IF NOT EXISTS ix_matches_b ON matches(b,active);
CREATE INDEX IF NOT EXISTS ix_orders_user ON orders(user_id,id);
CREATE INDEX IF NOT EXISTS ix_users_onb ON users(onboarded);
"""

BOTS = [
    # name, emoji, gender, age, uni, area, bmin, bmax, habits(sleep,tidy,money,noise,guest), tags, bio
    ("Minh Anh", "👩‍🎓", "nu", 20, "ĐH Kinh tế TP.HCM", "Bình Thạnh", 2.5, 4, (2, 4, 5, 2, 2), ["📚 Chăm học", "☕ Cà phê", "🚭 Không hút thuốc"], "Sinh viên năm 3, thích góc học tập yên tĩnh và cuối tuần đi cà phê sách."),
    ("Quốc Bảo", "👨‍💻", "nam", 21, "ĐH Bách Khoa", "Quận 10", 3, 5, (5, 2, 3, 4, 3), ["🎮 Game", "🎧 Nhạc", "🍳 Nấu ăn"], "Dev tập sự, cú đêm chính hiệu. Biết nấu vài món, đổi cơm lấy việc dọn nhà được không?"),
    ("Thảo Vy", "👩‍🎨", "nu", 20, "ĐH Văn Lang", "Bình Thạnh", 2, 3.5, (3, 5, 4, 1, 1), ["🌱 Sống xanh", "🐱 Thú cưng", "🎬 Phim"], "Học thiết kế, phòng luôn gọn như showroom. Có một bé mèo nhỏ rất ngoan."),
    ("Hoàng Nam", "🧑‍🔬", "nam", 22, "ĐH Khoa học Tự nhiên", "Quận 5", 2.5, 4, (4, 3, 4, 3, 4), ["🏋️ Gym", "📚 Chăm học", "🚭 Không hút thuốc"], "Dậy sớm đi gym, tối về làm thí nghiệm. Thoải mái, dễ tính, hay rủ ăn chung."),
    ("Ngọc Trâm", "👩‍💼", "nu", 21, "ĐH Ngoại thương", "Bình Thạnh", 3, 5, (1, 4, 5, 2, 2), ["📚 Chăm học", "☕ Cà phê", "🚭 Không hút thuốc"], "Ngủ sớm dậy sớm, chia tiền sòng phẳng từng đồng, thích bếp sạch sẽ."),
    ("Đức Huy", "🧑‍🎤", "nam", 21, "ĐH Công nghiệp", "Gò Vấp", 2, 3, (5, 1, 2, 5, 5), ["🎧 Nhạc", "🎮 Game", "🎬 Phim"], "Tay guitar nghiệp dư, nhà luôn có tiếng cười. Hơi bừa nhưng hứa dọn cuối tuần."),
    ("Khánh Linh", "👩‍🏫", "nu", 20, "ĐH Sư phạm TP.HCM", "Quận 5", 2, 3.5, (2, 4, 4, 2, 2), ["📚 Chăm học", "🌱 Sống xanh", "🍳 Nấu ăn"], "Sắp thành cô giáo tương lai, thích nấu ăn và trồng cây ban công."),
    ("Gia Huy", "🧑‍🚀", "nam", 22, "ĐH Tôn Đức Thắng", "Quận 7", 3.5, 5.5, (4, 3, 3, 3, 3), ["🏋️ Gym", "🎮 Game", "☕ Cà phê"], "Làm part-time buổi tối, cuối tuần rảnh đi bóng rổ. Cân bằng mọi thứ."),
    ("Phương Thảo", "👩‍🔧", "nu", 21, "ĐH Bách Khoa", "Quận 10", 3, 4.5, (3, 3, 4, 3, 3), ["🎧 Nhạc", "🎬 Phim", "🐱 Thú cưng"], "Ngành điện – điện tử, thích sửa đồ trong phòng, bóng đèn hỏng cứ để mình."),
    ("Tuấn Kiệt", "🧑‍🍳", "nam", 20, "ĐH FPT", "Quận 9", 2.5, 4, (5, 2, 3, 4, 4), ["🍳 Nấu ăn", "🎮 Game", "🎧 Nhạc"], "Học CNTT, mê nấu lẩu đêm khuya. Ai thích ăn khuya thì hợp nhau lắm."),
    ("Bảo Ngọc", "👩‍⚕️", "nu", 22, "ĐH Y Dược TP.HCM", "Quận 5", 3, 5, (1, 5, 5, 1, 1), ["📚 Chăm học", "🚭 Không hút thuốc", "🌱 Sống xanh"], "Sinh viên Y, giờ học căng nên rất cần phòng yên tĩnh, sạch sẽ."),
    ("Anh Khoa", "🧑‍🎨", "nam", 21, "ĐH Kiến trúc TP.HCM", "Quận 3", 3, 4.5, (4, 2, 3, 3, 3), ["🎬 Phim", "☕ Cà phê", "🎧 Nhạc"], "Học kiến trúc nên hay thức khuya làm đồ án, mô hình giấy bày đầy bàn nhưng vui tính."),
    ("Mai Phương", "👩‍💻", "nu", 20, "ĐH FPT", "Quận 9", 2.5, 4, (3, 4, 4, 2, 2), ["🎮 Game", "🐱 Thú cưng", "🚭 Không hút thuốc"], "Học lập trình, hay làm việc ở nhà. Thích có người cùng nấu cơm và xem phim cuối tuần."),
    ("Thanh Tùng", "🧑‍💼", "nam", 22, "ĐH Kinh tế TP.HCM", "Phú Nhuận", 3.5, 5, (2, 4, 5, 2, 2), ["📚 Chăm học", "🏋️ Gym", "🚭 Không hút thuốc"], "Sắp ra trường, đi thực tập. Cần bạn ở ghép nghiêm túc, đúng hẹn, chia tiền rõ."),
    ("Hải Yến", "👩‍🍳", "nu", 21, "ĐH Văn Lang", "Gò Vấp", 2, 3.2, (3, 3, 3, 4, 4), ["🍳 Nấu ăn", "🎧 Nhạc", "☕ Cà phê"], "Hướng ngoại, hay mời bạn về chơi. Ưu tiên phòng có bếp để nấu ăn."),
]

ROOMS = [
    # id, name, price, district, desc, near(list), dist, sponsored, emoji, beds, amenities, owner
    (1, "Phòng 25m² có gác lửng", 3800000, "Bình Thạnh", "Gác rộng, cửa sổ thoáng, giờ giấc tự do. Gần chợ và bến xe buýt.", ["ĐH Kinh tế TP.HCM", "ĐH Văn Lang", "ĐH Ngoại thương"], "1,2 km", 1, "🏠", 2, ["Wifi", "Máy lạnh", "Gác lửng", "Giữ xe"], "Cô Lan"),
    (2, "Chung cư mini full nội thất", 5500000, "Quận 10", "2 phòng ngủ nhỏ, bếp riêng, thang máy, bảo vệ 24/7.", ["ĐH Bách Khoa", "ĐH Khoa học Tự nhiên"], "0,8 km", 1, "🏢", 2, ["Nội thất", "Thang máy", "Bảo vệ 24/7", "Máy giặt"], "Anh Hùng"),
    (3, "Phòng 2 giường – Gò Vấp", 3200000, "Gò Vấp", "Phòng có máy lạnh, wifi miễn phí, khu an ninh, giờ giấc thoải mái.", ["ĐH Công nghiệp", "ĐH Văn Lang"], "1,5 km", 0, "🛏️", 2, ["Wifi", "Máy lạnh", "Giữ xe"], "Chú Bảy"),
    (4, "Studio ban công – Quận 7", 6200000, "Quận 7", "Studio hiện đại, ban công đầy nắng, gần Lotte Mart.", ["ĐH Tôn Đức Thắng", "ĐH Kinh tế TP.HCM"], "1,0 km", 1, "🌇", 2, ["Ban công", "Nội thất", "Bếp", "Thang máy"], "Chị Mai"),
    (5, "Phòng trọ yên tĩnh – Quận 5", 3500000, "Quận 5", "Nhà dân 3 tầng, chủ ở chung, giờ giấc nề nếp, cực yên tĩnh.", ["ĐH Sư phạm TP.HCM", "ĐH Y Dược TP.HCM", "ĐH Khoa học Tự nhiên"], "0,6 km", 0, "🏡", 2, ["Yên tĩnh", "Wifi", "Máy lạnh"], "Cô Hạnh"),
    (6, "Căn hộ dịch vụ – Thủ Đức", 4800000, "Quận 9", "Gần khu công nghệ cao, có hồ bơi và phòng gym chung.", ["ĐH FPT"], "0,9 km", 1, "🏙️", 2, ["Hồ bơi", "Gym", "Nội thất", "Bãi xe"], "Công ty Nhà Xanh"),
    (7, "Phòng mới xây – Phú Nhuận", 4200000, "Phú Nhuận", "Nhà mới, cửa vân tay, có bếp riêng từng phòng.", ["ĐH Kinh tế TP.HCM", "ĐH Kiến trúc TP.HCM"], "1,8 km", 0, "🚪", 2, ["Cửa vân tay", "Bếp riêng", "Wifi"], "Anh Dũng"),
    (8, "Phòng 30m² gần Quận 3", 4500000, "Quận 3", "Phòng rộng rãi, trần cao, cho phép nuôi mèo nhỏ.", ["ĐH Kiến trúc TP.HCM", "ĐH Bách Khoa"], "1,1 km", 0, "🐈", 2, ["Pet-friendly", "Máy lạnh", "Wifi"], "Chị Thu"),
]

SERVICES = [
    # id, kind, name, price, unit, descr, rating, jobs, emoji, promoted
    (1, "truck", "Anh Tùng – Xe ba gác", 150000, "chuyến", "Chuyển đồ trong nội thành, có dây chằng và bạt che.", 4.9, 120, "🛺", 1),
    (2, "truck", "Chú Sáu – Xe tải mini", 300000, "chuyến", "Xe tải 500kg, có bốc xếp, báo giá trước.", 4.8, 86, "🚚", 0),
    (3, "truck", "Hà Express – Xe van", 220000, "chuyến", "Phù hợp 2 người chuyển phòng, nhận lịch gấp trong ngày.", 4.7, 64, "🚐", 0),
    (4, "clean", "Đội vệ sinh Sạch Xinh", 250000, "phòng", "Dọn phòng mới sau khi thuê, khoảng 2 giờ.", 4.9, 210, "🧼", 1),
    (5, "clean", "Dọn nhà Mây Trắng", 200000, "phòng", "Bao gồm lau kính, vệ sinh toilet, hút bụi.", 4.6, 98, "🧽", 0),
    (6, "clean", "Tổng vệ sinh 2 người", 350000, "phòng", "Phù hợp phòng chia 2 người, tặng nước lau sàn.", 4.8, 77, "✨", 0),
    (7, "used", "Sinh Viên Shop – Đồ cũ", 50000, "từ", "Quạt, kệ sách, nệm, bàn học giá sinh viên.", 4.7, 305, "🛋️", 1),
    (8, "used", "Combo Nệm + Quạt + Kệ", 450000, "combo", "Combo đồ cũ đã vệ sinh, giao tận nơi.", 4.6, 58, "🛏️", 0),
    (9, "used", "Bàn học gấp gọn", 120000, "cái", "Bàn học gấp gọn, nhẹ, dễ mang lên gác.", 4.5, 41, "📚", 0),
]


HOUSE_TYPES = {"tro": "Phòng trọ", "mini": "Chung cư mini", "chungcu": "Căn hộ / chung cư"}
PRIORITIES = {"cheap": "Giá rẻ", "near": "Gần trường", "quality": "Sạch đẹp, tiện nghi"}


def _load_catalog(c):
    global _ROOMS_CACHE, _SERVICES_CACHE
    _ROOMS_CACHE = [room_dict(r) for r in c.execute("SELECT * FROM rooms ORDER BY sponsored DESC, price").fetchall()]
    svc = {}
    for s in c.execute("SELECT * FROM services ORDER BY promoted DESC, rating DESC").fetchall():
        sd = service_dict(s)
        svc.setdefault(sd["kind"], []).append(sd)
    _SERVICES_CACHE = svc


def _get_rooms(c):
    if not _ROOMS_CACHE:
        _load_catalog(c)
    return _ROOMS_CACHE


def _get_services(c, kind):
    if not _SERVICES_CACHE:
        _load_catalog(c)
    return _SERVICES_CACHE.get(kind, [])


def init_db():
    with _AUTH_LOCK:
        _AUTH_CACHE.clear()
    c = db()
    schema = SCHEMA
    if IS_PG:
        schema = (schema
                  .replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                  .replace(" REAL", " DOUBLE PRECISION"))
    c.exec_script(schema)
    if not IS_PG:
        c.execute("PRAGMA journal_mode=WAL")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()}
    else:
        cols = {r["column_name"] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='users'").fetchall()}
    if "house_type" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN house_type TEXT DEFAULT 'tro'")
        c.execute("ALTER TABLE users ADD COLUMN priority TEXT DEFAULT 'cheap'")
    if "photo_v" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN photo_v INTEGER DEFAULT 0")
    if not IS_PG:
        fb_cols = {r["name"] for r in c.execute("PRAGMA table_info(feedback)").fetchall()}
    else:
        fb_cols = {r["column_name"] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='feedback'").fetchall()}
    if "pitch_closer" not in fb_cols:
        c.execute("ALTER TABLE feedback ADD COLUMN pitch_closer TEXT DEFAULT ''")
    if "synced" not in fb_cols:
        c.execute("ALTER TABLE feedback ADD COLUMN synced INTEGER DEFAULT 0")
    time_tables = ("users", "sessions", "swipes", "matches", "messages", "orders", "impressions", "feedback")
    for tbl in time_tables:
        if not IS_PG:
            t_cols = {r["name"] for r in c.execute(f"PRAGMA table_info({tbl})").fetchall()}
        else:
            t_cols = {r["column_name"] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=?", (tbl,)).fetchall()}
        if "created_real_time" not in t_cols:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN created_real_time TEXT DEFAULT ''")
        if IS_PG:
            c.execute(f"UPDATE {tbl} SET created_real_time = to_char(to_timestamp(created) AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY-MM-DD HH24:MI:SS') WHERE (created_real_time IS NULL OR created_real_time = '') AND created IS NOT NULL AND created > 0")
        else:
            c.execute(f"UPDATE {tbl} SET created_real_time = strftime('%Y-%m-%d %H:%M:%S', created, 'unixepoch', '+7 hours') WHERE (created_real_time IS NULL OR created_real_time = '') AND created IS NOT NULL AND created > 0")
    c.execute(f"CREATE TABLE IF NOT EXISTS photos(user_id INTEGER PRIMARY KEY, data {'BYTEA' if IS_PG else 'BLOB'})")
    fresh = not c.execute("SELECT 1 FROM users WHERE is_bot=1").fetchone()
    if fresh:
        for i, b in enumerate(BOTS):
            n, e, g, age, uni, area, bmin, bmax, h, tags, bio = b
            now = time.time()
            c.execute(
                "INSERT INTO users(username,name,emoji,color,university,bio,age,gender,budget_min,budget_max,area,sleep,tidy,money,noise,guest,tags,is_bot,onboarded,created,created_real_time)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,1,?,?)",
                (f"bot{i}", n, e, i % 8, uni, bio, age, g, bmin, bmax, area, *h, json.dumps(tags, ensure_ascii=False), now, fmt_vn_time(now)),
            )
    if fresh or "house_type" not in cols:
        for r in c.execute("SELECT id,budget_max FROM users WHERE is_bot=1").fetchall():
            bm = r["budget_max"]
            ht = "tro" if bm < 3.6 else ("mini" if bm < 4.8 else "chungcu")
            pr = "cheap" if bm < 3.3 else (["near", "quality", "near"][r["id"] % 3] if bm < 4.8 else "quality")
            c.execute("UPDATE users SET house_type=?, priority=? WHERE id=?", (ht, pr, r["id"]))
    if not c.execute("SELECT 1 FROM rooms").fetchone():
        for r in ROOMS:
            c.execute("INSERT INTO rooms VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (*r[:5], json.dumps(r[5], ensure_ascii=False), *r[6:10], json.dumps(r[10], ensure_ascii=False), r[11]))
        for s in SERVICES:
            c.execute("INSERT INTO services VALUES(?,?,?,?,?,?,?,?,?,?)", s)
    c.commit()
    _load_catalog(c)
    c.close()
    _invalidate_users_cache()
    if IS_PG:
        def _warm_pg_pool():
            for _ in range(2):
                try:
                    if _PG_POOL.qsize() >= 3:
                        break
                    conn = psycopg.connect(
                        DATABASE_URL, autocommit=True, row_factory=dict_row, prepare_threshold=None,
                        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
                    )
                    _PG_POOL.put_nowait((conn, time.time()))
                except Exception:
                    break
        threading.Thread(target=_warm_pg_pool, daemon=True).start()


# ----------------------------------------------------------------- logic
def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()


def user_row_to_dict(u, me=None, full=True):
    d = {
        "id": u["id"], "name": u["name"], "emoji": u["emoji"], "color": u["color"],
        "university": u["university"], "bio": u["bio"], "age": u["age"], "gender": u["gender"],
        "area": u["area"], "budget_min": u["budget_min"], "budget_max": u["budget_max"],
        "house_type": u["house_type"], "priority": u["priority"],
        "habits": {k: u[k] for k in HABITS}, "tags": json.loads(u["tags"] or "[]"),
        "is_bot": bool(u["is_bot"]),
        "photo": f"/photo/{u['id']}?v={u['photo_v']}" if u["photo_v"] else "",
    }
    if me is not None:
        d["compat"] = compat(me, u)
    return d


def compat(a, b):
    tot = sum(WEIGHTS.values())
    dist = sum(WEIGHTS[k] * abs(a[k] - b[k]) / 4 for k in HABITS) / tot
    habit = 1 - dist
    budget = max(0.0, 1 - abs(a["budget_max"] - b["budget_max"]) / 3.0)  # lệch 3 triệu trở lên = 0
    order = ["tro", "mini", "chungcu"]
    gap = abs(order.index(a["house_type"]) - order.index(b["house_type"]))
    house = (1.0, 0.5, 0.0)[gap]
    prio = 1.0 if a["priority"] == b["priority"] else 0.4
    housing = 0.65 * house + 0.35 * prio
    ta, tb = set(json.loads(a["tags"] or "[]")), set(json.loads(b["tags"] or "[]"))
    tagsim = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    same_uni = 1.0 if a["university"] and a["university"] == b["university"] else 0.0
    raw = 0.58 * habit + 0.14 * budget + 0.14 * housing + 0.09 * tagsim + 0.05 * same_uni
    score = max(20, min(99, round(35 + 65 * raw)))
    items = []
    for k in HABITS:
        diff = abs(a[k] - b[k])
        items.append({"key": k, "label": HABIT_LABEL[k], "me": a[k], "them": b[k], "sim": round(100 - diff * 25)})
    items_sorted = sorted(items, key=lambda x: -x["sim"])
    best = [x["label"] for x in items_sorted[:2] if x["sim"] >= 75]
    gaps = [x for x in items_sorted[::-1] if x["sim"] <= 50][:2]
    insights = []
    if best:
        insights.append("Rất hợp về: " + " & ".join(best))
    for g in gaps:
        insights.append(f"Cần thống nhất {g['label'].lower()}: {HABIT_ADVICE[g['key']]}")
    shared = sorted(ta & tb)
    if shared:
        insights.append("Điểm chung: " + ", ".join(shared))
    if budget >= 0.7:
        insights.append("Ngân sách tối đa gần bằng nhau")
    elif budget < 0.4:
        insights.append(f"Ngân sách chênh nhau: bạn tối đa {a['budget_max']:g} tr, bạn ấy {b['budget_max']:g} tr, cần bàn lại mức giá phòng")
    if gap == 0:
        insights.append(f"Cùng muốn thuê {HOUSE_TYPES[a['house_type']].lower()}")
    elif gap == 2:
        insights.append(f"Khác nhu cầu nhà: bạn muốn {HOUSE_TYPES[a['house_type']].lower()}, bạn ấy muốn {HOUSE_TYPES[b['house_type']].lower()}")
    if a["priority"] != b["priority"]:
        insights.append(f"Ưu tiên khác nhau: bạn chọn «{PRIORITIES[a['priority']].lower()}», bạn ấy chọn «{PRIORITIES[b['priority']].lower()}»")
    return {"score": score, "habits": items, "budget": round(budget * 100), "shared_tags": shared, "insights": insights}


def gender_ok(a, b):
    if a["pref_gender"] == "same" and a["gender"] != b["gender"]:
        return False
    if b["pref_gender"] == "same" and a["gender"] != b["gender"]:
        return False
    return True


def match_public(c, m, me_id, me=None, other=None, fresh=False):
    other_id = m["b"] if m["a"] == me_id else m["a"]
    if me is None:
        me = c.execute("SELECT * FROM users WHERE id=?", (me_id,)).fetchone()
    if other is None:
        other = c.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
    if fresh:
        last, unread = None, 0
    else:
        now = time.time()
        last = c.execute("SELECT * FROM messages WHERE match_id=? AND visible_at<=? ORDER BY id DESC LIMIT 1", (m["id"], now)).fetchone()
        unread = int(c.execute("SELECT COUNT(*) n FROM messages WHERE match_id=? AND sender!=? AND read=0 AND visible_at<=?", (m["id"], me_id, now)).fetchone()["n"] or 0)
    return {
        "id": m["id"], "score": m["score"], "created": m["created"], "unread": unread,
        "user": user_row_to_dict(other, me),
        "last": {"text": last["text"], "mine": last["sender"] == me_id, "at": last["created"]} if last else None,
    }


def matches_public(c, me):
    uid = me["id"]
    rows = c.execute(
        "SELECT u.*, m.id AS _mid, m.score AS _mscore, m.created AS _mcreated"
        " FROM matches m"
        " JOIN users u ON u.id = CASE WHEN m.a=? THEN m.b ELSE m.a END"
        " WHERE (m.a=? OR m.b=?) AND m.active=1"
        " ORDER BY m.id DESC",
        (uid, uid, uid),
    ).fetchall()
    if not rows:
        return []
    now = time.time()
    agg_rows = c.execute(
        "SELECT msg.match_id, msg.sender, msg.text, msg.created, agg.unread"
        " FROM ("
        "   SELECT match_id, MAX(id) AS last_id,"
        "          SUM(CASE WHEN sender!=? AND read=0 THEN 1 ELSE 0 END) AS unread"
        "   FROM messages"
        "   WHERE visible_at<=?"
        "     AND match_id IN (SELECT id FROM matches WHERE (a=? OR b=?) AND active=1)"
        "   GROUP BY match_id"
        " ) agg"
        " JOIN messages msg ON msg.id = agg.last_id",
        (uid, now, uid, uid),
    ).fetchall()
    by_mid = {r["match_id"]: r for r in agg_rows}
    ms = []
    for r in rows:
        info = by_mid.get(r["_mid"])
        ms.append({
            "id": r["_mid"],
            "score": r["_mscore"],
            "created": r["_mcreated"],
            "unread": int(info["unread"] or 0) if info else 0,
            "user": user_row_to_dict(r, me),
            "last": {"text": info["text"], "mine": info["sender"] == uid, "at": info["created"]} if info else None,
        })
    ms.sort(key=lambda m: -((m["last"] or {}).get("at") or m["created"]))
    return ms


def bot_say(c, match_id, bot_id, text, delay):
    t = time.time() + delay
    c.execute("INSERT INTO messages(match_id,sender,text,created,created_real_time,visible_at) VALUES(?,?,?,?,?,?)", (match_id, bot_id, text, t, fmt_vn_time(t), t))


def bot_reply(bot, text, uname):
    t = text.lower()
    first = uname.split()[-1] if uname else "bạn"
    sl, ti, mo, no, gu = (bot[k] for k in HABITS)
    if re.search(r"ngủ|thức|giờ giấc|dậy|khuya|sớm", t):
        return ("Mình thường ngủ khoảng 22h và dậy 6h sáng nhé." if sl <= 2 else
                "Mình cú đêm, hay thức tới 1-2h sáng, nhưng dùng tai nghe nên không ồn đâu." if sl >= 4 else
                "Mình ngủ khoảng 23h30, linh hoạt được, bạn cứ nói giờ của bạn.")
    if re.search(r"tiền|chia|điện|nước|wifi|trả|cọc", t):
        return ("Mình thích chia sòng phẳng, ghi sổ chung mỗi tháng cho rõ ràng 👍" if mo >= 4 else
                "Mình khá thoải mái, mình chia đều là ổn, có gì nói thẳng với nhau nhé.")
    if re.search(r"dọn|sạch|bẩn|gọn|rác|bếp|vệ sinh", t):
        return ("Mình khá kỹ, dọn mỗi ngày một chút, hy vọng bạn cũng thích sạch sẽ 😄" if ti >= 4 else
                "Mình không quá khắt khe, nhưng cuối tuần sẽ dọn tổng vệ sinh nhé." if ti >= 3 else
                "Thú thật mình hơi bừa, nhưng mình hứa sẽ luân phiên trực nhật!")
    if re.search(r"ồn|nhạc|yên tĩnh|loa|ồn ào", t):
        return ("Mình thích yên tĩnh, buổi tối chỉ nghe nhạc nhỏ thôi." if no <= 2 else
                "Mình thích không khí vui vẻ, nhưng sẽ giữ yên tĩnh khi bạn cần học nhé.")
    if re.search(r"bạn bè|khách|người yêu|về phòng|đưa", t):
        return ("Mình ít đưa ai về, nếu có sẽ báo trước cho bạn." if gu <= 2 else
                "Thỉnh thoảng bạn mình ghé chơi, mình luôn nhắn trước nhé 👍")
    if re.search(r"phòng|xem|thuê|giá|gần|trọ|khi nào|cuối tuần", t):
        return "Hay là cuối tuần này mình cùng đi xem phòng nhé? Mình thấy mục Dịch vụ có vài phòng khá ổn đó."
    if re.search(r"chào|hi\b|hello|xin chào|alo", t):
        return f"Chào {first}! Rất vui được làm quen 😊"
    if re.search(r"cảm ơn|thanks|ok", t):
        return "Okie bạn, mình cũng nghĩ vậy!"
    return random.choice([
        "Mình thấy ổn đó, bạn kể thêm về thói quen sinh hoạt của bạn đi?",
        "Hay quá! Mình cũng đang tìm người ở ghép đàng hoàng.",
        "Bạn dự định dọn vào ở khi nào vậy?",
        "Nghe hợp lý đó, mình đồng ý 👍",
    ])


def bot_opening(bot, score):
    opts = [f"Chào bạn! App báo tụi mình hợp nhau {score}%, mình tò mò quá 😄",
            "Hi! Mình thấy thói quen sinh hoạt của tụi mình khá giống nhau, bạn đang tìm phòng khu nào?",
            "Chào bạn ơi, rất vui vì match được với bạn! Bạn định thuê trong khoảng bao nhiêu một tháng?"]
    return random.choice(opts)


def create_match(c, a_id, b_id, score):
    a, b = sorted((a_id, b_id))
    row = c.execute("SELECT * FROM matches WHERE a=? AND b=?", (a, b)).fetchone()
    if row:
        c.execute("UPDATE matches SET active=1 WHERE id=?", (row["id"],))
        return c.execute("SELECT * FROM matches WHERE id=?", (row["id"],)).fetchone(), False
    now = time.time()
    mid = c.insert_id("INSERT INTO matches(a,b,score,created,created_real_time) VALUES(?,?,?,?,?)", (a, b, score, now, fmt_vn_time(now)))
    return c.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone(), True


def log_impressions(c, room_ids, user_id):
    if not room_ids:
        return
    now = time.time()
    now_str = fmt_vn_time(now)
    vals = ",".join("(?,?,?,?)" for _ in room_ids)
    params = []
    for rid in room_ids:
        params.extend((rid, user_id, now, now_str))
    c.execute(f"INSERT INTO impressions(room_id,user_id,created,created_real_time) VALUES {vals}", tuple(params))


def rooms_for(c, me, other, user_id, log=True):
    avg_max = (me["budget_max"] + other["budget_max"]) / 2 if other else me["budget_max"]
    unis = {me["university"], other["university"] if other else ""}
    out = []
    for r in _get_rooms(c):
        near = r["near"]
        per = r["price"] / 2 / 1_000_000
        fits = per <= avg_max + 0.3
        near_hit = any(u in near for u in unis if u)
        rtype = "tro" if r["price"] < 3_800_000 else ("mini" if r["price"] < 5_800_000 else "chungcu")
        want = {me["house_type"], other["house_type"] if other else me["house_type"]}
        type_hit = rtype in want
        prio = {me["priority"], other["priority"] if other else me["priority"]}
        rank = (int(r["sponsored"]) * 1) + (2 if near_hit and "near" in prio else 1 if near_hit else 0) + (2 if type_hit else 0) + (2 if fits else -2)
        out.append((rank, r, per, fits, near_hit))
    out.sort(key=lambda x: -x[0])
    res = []
    sp_ids = []
    for rank, r, per, fits, near_hit in out[:4]:
        d = dict(r)
        d.update({"per_person": round(per, 2), "fits": fits, "near_you": near_hit})
        res.append(d)
        if log and r["sponsored"]:
            sp_ids.append(r["id"])
    log_impressions(c, sp_ids, user_id)
    return res


def room_dict(r):
    return {"id": r["id"], "kind": "room", "name": r["name"], "price": r["price"], "district": r["district"], "desc": r["descr"],
            "near": json.loads(r["near"]), "dist": r["dist"], "sponsored": bool(r["sponsored"]), "emoji": r["emoji"],
            "beds": r["beds"], "amenities": json.loads(r["amenities"]), "owner": r["owner"]}


def service_dict(s):
    return {"id": s["id"], "kind": s["kind"], "name": s["name"], "price": s["price"], "unit": s["unit"], "desc": s["descr"],
            "rating": s["rating"], "jobs": s["jobs"], "emoji": s["emoji"], "promoted": bool(s["promoted"])}


def order_dict(o):
    age = time.time() - o["created"]
    status = "Đã gửi yêu cầu" if age < 60 else ("Đối tác đã xác nhận" if age < 6 * 3600 else "Hoàn tất")
    return {"id": o["id"], "kind": o["kind"], "name": o["item_name"], "amount": o["amount"], "note": o["note"],
            "date": o["date"], "status": status, "created": o["created"]}


# ----------------------------------------------------------------- http
class Err(Exception):
    def __init__(self, code, msg):
        self.code, self.msg = code, msg


def clean_text(s, n):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def apply_profile(c, uid, p):
    allowed_gender = {"nam", "nu", "khac"}
    fields = {
        "name": clean_text(p.get("name"), 40), "emoji": clean_text(p.get("emoji"), 8) or "🙂",
        "university": clean_text(p.get("university"), 60), "bio": clean_text(p.get("bio"), 220),
        "area": clean_text(p.get("area"), 40),
    }
    if not fields["name"]:
        raise Err(400, "Vui lòng nhập tên")
    try:
        fields["age"] = max(16, min(40, int(p.get("age", 20))))
        fields["color"] = int(p.get("color", 0)) % 8
        bmin = float(p.get("budget_min", 2))
        bmax = float(p.get("budget_max", 4))
        fields["budget_min"], fields["budget_max"] = min(bmin, bmax), max(bmin, bmax)
        for k in HABITS:
            fields[k] = max(1, min(5, int(p.get(k, 3))))
    except (TypeError, ValueError):
        raise Err(400, "Dữ liệu không hợp lệ")
    g = p.get("gender", "khac")
    fields["gender"] = g if g in allowed_gender else "khac"
    fields["pref_gender"] = "same" if p.get("pref_gender") == "same" else "any"
    fields["house_type"] = p.get("house_type") if p.get("house_type") in HOUSE_TYPES else "tro"
    fields["priority"] = p.get("priority") if p.get("priority") in PRIORITIES else "cheap"
    tags = [clean_text(t, 30) for t in (p.get("tags") or [])][:8]
    fields["tags"] = json.dumps(tags, ensure_ascii=False)
    fields["onboarded"] = 1
    sets = ",".join(f"{k}=?" for k in fields)
    c.execute(f"UPDATE users SET {sets} WHERE id=?", (*fields.values(), uid))
    _invalidate_users_cache()


GFORM_FEAT_FROM_FULL = {full: short for short, full in GFORM_FEAT_PAIRS}


def _parse_sheet_ts(raw):
    s = str(raw or "").strip()
    if not s:
        return 0.0
    tz = timezone(timedelta(hours=7))
    for fmt in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=tz).timestamp()
        except ValueError:
            pass
    return 0.0


def _parse_sheet_star(raw):
    m = re.search(r"[1-5]", str(raw or ""))
    return int(m.group(0)) if m else 0


def _parse_sheet_favs(raw):
    s = str(raw or "")
    if not s:
        return []
    out = []
    # Match known phrases directly instead of splitting on commas, since two Google Form options contain commas.
    for short_lbl, full_lbl in GFORM_FEAT_PAIRS:
        if full_lbl in s or short_lbl in s:
            out.append(short_lbl)
    return out


def _norm_favs_list(raw):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except Exception:
            return _parse_sheet_favs(raw)
    if not isinstance(raw, list):
        return []
    out = []
    for x in raw[:7]:
        s = clean_text(x, 80)
        s = GFORM_FEAT_FROM_FULL.get(s, s)
        if s and s not in out:
            out.append(s)
    return out


def _parse_sheet_device(raw):
    s = str(raw or "").lower()
    if "cả hai" in s or "both" in s:
        return "both"
    if "laptop" in s or "máy tính" in s or "desktop" in s or "pc" in s:
        return "desktop"
    return "mobile"


def _parse_sheet_issue(raw):
    s = str(raw or "").lower()
    if "lỗi chức năng" in s or "func_bug" in s:
        return "func_bug"
    if "lệch" in s or "đè chữ" in s or "hiển thị" in s or "ui_bug" in s:
        return "ui_bug"
    if "lag" in s or "chậm" in s:
        return "lag"
    return "smooth"


def _parse_sheet_shark(raw):
    s = str(raw or "").lower()
    if "mạnh" in s or "3 tỷ" in s or "strong" in s:
        return "strong"
    if "chưa sẵn sàng" in s or "chưa đầu tư" in s or s.strip() == "no":
        return "no"
    if "cân nhắc" in s or "consider" in s:
        return "consider"
    return "explore"


def _parse_sheet_pitch(raw):
    s = str(raw or "").lower()
    if not s.strip():
        return ""
    if "kéo người dùng" in s or "0đ" in s or "viral" in s:
        return "viral"
    if "biên lợi nhuận" in s or "đối tác" in s or "margin" in s:
        return "margin"
    if "chống tài khoản ảo" in s or "an toàn" in s or "safety" in s:
        return "safety"
    if "mở rộng" in s or "6–12" in s or "6-12" in s or "scale" in s:
        return "scale"
    return ""


def _fb_fingerprint(r):
    return (
        (r.get("tester_name") or "Ẩn danh").strip(),
        r.get("device") or "mobile",
        int(r.get("r_ui") or 0),
        int(r.get("r_ux") or 0),
        int(r.get("r_match") or 0),
        int(r.get("r_eco") or 0),
        int(r.get("r_overall") or 0),
        r.get("issue_type") or "smooth",
        r.get("shark_invest") or "explore",
        (r.get("suggestion") or "").strip(),
    )


def _fetch_gsheet_rows(force=False):
    if not GSHEET_CSV_URL:
        return []
    now = time.time()
    with _GSHEET_LOCK:
        if not force and _GSHEET_CACHE["ok"] and now - _GSHEET_CACHE["ts"] < 15.0:
            return [dict(r) for r in _GSHEET_CACHE["rows"]]
    try:
        req = urllib.request.Request(GSHEET_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        ct = (resp.headers.get("Content-Type") or "").lower()
        if "text/html" in ct and raw.lstrip()[:1] == b"<":
            raise ValueError("Google Sheet returned HTML instead of public CSV")
        text = raw.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            rows = []
        else:
            col = {}
            for i, h in enumerate(header):
                hl = (h or "").strip().lower()
                if "thời gian" in hl or "timestamp" in hl:
                    col.setdefault("ts", i)
                elif "tên" in hl or "biệt danh" in hl:
                    col.setdefault("name", i)
                elif "thiết bị" in hl:
                    col.setdefault("device", i)
                elif "giao diện" in hl or "(ui)" in hl:
                    col.setdefault("r_ui", i)
                elif "độ mượt" in hl or "(ux)" in hl:
                    col.setdefault("r_ux", i)
                elif "5 thói quen" in hl or "quẹt tinder" in hl:
                    col.setdefault("r_match", i)
                elif "hệ sinh thái" in hl:
                    col.setdefault("r_eco", i)
                elif "tổng thể" in hl:
                    col.setdefault("r_overall", i)
                elif "thích nhất" in hl:
                    col.setdefault("fav", i)
                elif "kỹ thuật" in hl:
                    col.setdefault("issue", i)
                elif "shark" in hl or "10 tỷ" in hl:
                    col.setdefault("shark", i)
                elif "câu chốt" in hl:
                    col.setdefault("pitch", i)
                elif "đề xuất" in hl or "cải tiến" in hl:
                    col.setdefault("suggestion", i)
            get = lambda r, k: (r[col[k]].strip() if k in col and col[k] < len(r) else "")
            parsed = []
            for idx, r in enumerate(reader, start=1):
                if not any((x or "").strip() for x in r):
                    continue
                stars = [
                    _parse_sheet_star(get(r, "r_ui")),
                    _parse_sheet_star(get(r, "r_ux")),
                    _parse_sheet_star(get(r, "r_match")),
                    _parse_sheet_star(get(r, "r_eco")),
                    _parse_sheet_star(get(r, "r_overall")),
                ]
                if not any(stars):
                    continue
                r_ui, r_ux, r_match, r_eco, r_overall = [s or 5 for s in stars]
                parsed.append({
                    "id": f"gs-{idx}",
                    "tester_name": clean_text(get(r, "name"), 40) or "Ẩn danh",
                    "device": _parse_sheet_device(get(r, "device")),
                    "r_ui": r_ui,
                    "r_ux": r_ux,
                    "r_match": r_match,
                    "r_eco": r_eco,
                    "r_overall": r_overall,
                    "fav_features": _parse_sheet_favs(get(r, "fav")),
                    "issue_type": _parse_sheet_issue(get(r, "issue")),
                    "shark_invest": _parse_sheet_shark(get(r, "shark")),
                    "pitch_closer": _parse_sheet_pitch(get(r, "pitch")),
                    "suggestion": clean_text(get(r, "suggestion"), 600),
                    "created": _parse_sheet_ts(get(r, "ts")) or float(idx),
                    "source": "sheet",
                })
            parsed.reverse()
            rows = parsed
        with _GSHEET_LOCK:
            _GSHEET_CACHE["ts"] = time.time()
            _GSHEET_CACHE["rows"] = [dict(r) for r in rows]
            _GSHEET_CACHE["ok"] = True
        return rows
    except Exception as e:
        sys.stderr.write(f"GSheet fetch error: {e}\n")
        with _GSHEET_LOCK:
            return [dict(r) for r in _GSHEET_CACHE["rows"]]


def _post_to_gform(row):
    if not GFORM_POST_URL:
        return False
    pairs = [
        ("entry.625760835", "" if row["tester_name"] == "Ẩn danh" else row["tester_name"]),
        ("entry.1776861047", GFORM_DEV.get(row["device"], GFORM_DEV["mobile"])),
        ("entry.1776861047_sentinel", ""),
        ("entry.1186649542", GFORM_STAR.get(row["r_ui"], GFORM_STAR[5])),
        ("entry.1186649542_sentinel", ""),
        ("entry.52005247", GFORM_STAR.get(row["r_ux"], GFORM_STAR[5])),
        ("entry.52005247_sentinel", ""),
        ("entry.2046561775", GFORM_STAR.get(row["r_match"], GFORM_STAR[5])),
        ("entry.2046561775_sentinel", ""),
        ("entry.1306876798", GFORM_STAR.get(row["r_eco"], GFORM_STAR[5])),
        ("entry.1306876798_sentinel", ""),
        ("entry.1160174372", GFORM_STAR.get(row["r_overall"], GFORM_STAR[5])),
        ("entry.1160174372_sentinel", ""),
        ("entry.765746675_sentinel", ""),
    ]
    for feat in row["fav_features"]:
        pairs.append(("entry.765746675", GFORM_FEAT_TO_FULL.get(feat, feat)))
    pairs.extend([
        ("entry.1235497208", GFORM_ISS.get(row["issue_type"], GFORM_ISS["smooth"])),
        ("entry.1235497208_sentinel", ""),
        ("entry.338099251", GFORM_SHARK.get(row["shark_invest"], GFORM_SHARK["explore"])),
        ("entry.338099251_sentinel", ""),
        ("entry.816095684", row.get("suggestion") or ""),
        ("fvv", "1"),
        ("pageHistory", "0"),
        ("submissionTimestamp", "-1"),
    ])
    pitch = row.get("pitch_closer") or ""
    if pitch in GFORM_PITCH:
        pairs.append(("entry.1802690077", GFORM_PITCH[pitch]))
        pairs.append(("entry.1802690077_sentinel", ""))
    body = urlencode(pairs).encode("utf-8")
    req = urllib.request.Request(
        GFORM_POST_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "Mozilla/5.0",
            "Referer": GFORM_VIEW_URL or GFORM_POST_URL,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        sys.stderr.write(f"GForm forward error: {e}\n")
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "RoommateMatcher/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    # --- helpers
    def _tok(self):
        h = self.headers.get("Authorization", "")
        return h[7:] if h.startswith("Bearer ") else ""

    def send_json(self, data, code=200, head_only=False):
        body = json.dumps(data, ensure_ascii=False).encode()
        gz = (not head_only) and len(body) > 512 and "gzip" in self.headers.get("Accept-Encoding", "").lower()
        if gz:
            body = gzip.compress(body, compresslevel=5)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if gz:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 700_000:
            raise Err(413, "Dữ liệu quá lớn")
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            raise Err(400, "JSON không hợp lệ")

    def auth(self, c):
        tok = self._tok()
        if not tok:
            raise Err(401, "Phiên đăng nhập đã hết hạn")
        cached = _cache_get_user(tok)
        if cached is not None:
            return cached
        row = c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (tok,)).fetchone()
        if not row:
            raise Err(401, "Phiên đăng nhập đã hết hạn")
        _cache_set_user(tok, row)
        return dict(row)

    def do_GET(self):
        self.route("GET")

    def do_HEAD(self):
        self.route("HEAD")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def route(self, method):
        u = urlparse(self.path)
        path, q = u.path, {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if path == "/api/health" and method in ("GET", "HEAD"):
                self.send_json({"ok": True}, head_only=(method == "HEAD"))
                return
            if path == "/api/feedback.csv" and method == "GET":
                self.feedback_csv()
                return
            if path == "/api/feedback.xlsx" and method == "GET":
                self.feedback_xlsx()
                return
            if path.startswith("/api/"):
                res = None
                for attempt in (0, 1):
                    c = db()
                    try:
                        res = self.api(c, method, path[5:].strip("/"), q)
                        c.commit()
                        break
                    except Err:
                        c.rollback()
                        raise
                    except Exception as e:
                        _cache_drop_token(self._tok())
                        if IS_PG and isinstance(e, (psycopg.OperationalError, psycopg.InterfaceError)):
                            c.discard()
                            if attempt == 0:
                                continue
                        else:
                            c.rollback()
                        raise
                    finally:
                        c.close()
                self.send_json(res, head_only=(method == "HEAD"))
            elif method == "GET" and path.startswith("/photo/"):
                self.photo(path[7:])
            elif method in ("GET", "HEAD"):
                self.static(path, head_only=(method == "HEAD"))
            else:
                raise Err(405, "Method not allowed")
        except Err as e:
            self.send_json({"error": e.msg}, e.code, head_only=(method == "HEAD"))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa
            import traceback
            traceback.print_exc()
            self.send_json({"error": "Lỗi máy chủ: " + str(e)}, 500)

    def photo(self, pid):
        row = None
        for attempt in (0, 1):
            c = db()
            try:
                row = c.execute("SELECT data FROM photos WHERE user_id=?", (int(pid) if pid.isdigit() else 0,)).fetchone()
                break
            except Exception as e:
                if IS_PG and isinstance(e, (psycopg.OperationalError, psycopg.InterfaceError)):
                    c.discard()
                    if attempt == 0:
                        continue
                raise
            finally:
                c.close()
        if not row:
            raise Err(404, "Không có ảnh")
        data = bytes(row["data"])
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(data)

    def static(self, path, head_only=False):
        if path in ("", "/"):
            path = "/index.html"
        fp = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            fp = os.path.join(STATIC, "index.html")  # SPA fallback
        mtime = os.path.getmtime(fp)
        entry = _STATIC_CACHE.get(fp)
        if not entry or entry[0] != mtime:
            with open(fp, "rb") as f:
                data = f.read()
            gz_data = gzip.compress(data, compresslevel=6) if len(data) > 512 else data
            etag = f'"{hashlib.md5(data).hexdigest()}"'
            ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
            entry = (mtime, data, gz_data, etag, ctype)
            _STATIC_CACHE[fp] = entry
        _, data, gz_data, etag, ctype = entry
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        use_gz = (not head_only) and len(data) > 512 and "gzip" in self.headers.get("Accept-Encoding", "").lower()
        payload = gz_data if use_gz else data
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or "javascript" in ctype or "json" in ctype else ""))
        if use_gz:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("ETag", etag)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)

    # --- API
    def api(self, c, method, path, q):
        # ---- public
        if path == "health":
            return {"ok": True}
        if path == "stats" and method == "GET":
            return self.stats(c)
        if path == "feedback":
            if method == "GET":
                return self.feedback_stats(c)
            if method == "POST":
                return self.submit_feedback(c, self.body())
        if path in ("register", "login", "guest") and method == "POST":
            return self.do_auth(c, path)

        me = self.auth(c)
        uid = me["id"]

        if path == "me":
            if method == "GET":
                return {"user": self.me_dict(c, me)}
            if method == "PUT":
                apply_profile(c, uid, self.body())
                me = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
                _cache_drop_user(uid)
                _cache_set_user(self._tok(), me)
                return {"user": self.me_dict(c, me)}
        if path == "photo" and method == "POST":
            import base64
            d = str(self.body().get("data") or "")
            if d:
                m = re.fullmatch(r"data:image/(?:jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=]+)", d)
                if not m:
                    raise Err(400, "Ảnh không hợp lệ")
                raw = base64.b64decode(m.group(1))
                if len(raw) > 400_000:
                    raise Err(413, "Ảnh quá lớn")
                if not (raw[:3] == b"\xff\xd8\xff" or raw[:4] == b"\x89PNG" or raw[:4] == b"RIFF"):
                    raise Err(400, "Định dạng ảnh không hỗ trợ")
                c.execute("INSERT INTO photos(user_id,data) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data", (uid, raw))
                c.execute("UPDATE users SET photo_v=? WHERE id=?", (int(time.time()), uid))
            else:
                c.execute("DELETE FROM photos WHERE user_id=?", (uid,))
                c.execute("UPDATE users SET photo_v=0 WHERE id=?", (uid,))
            me = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            _invalidate_users_cache()
            _cache_drop_user(uid)
            _cache_set_user(self._tok(), me)
            return {"user": self.me_dict(c, me)}
        if path == "logout" and method == "POST":
            tok = self._tok()
            c.execute("DELETE FROM sessions WHERE token=?", (tok,))
            _cache_drop_token(tok)
            return {"ok": True}
        if path == "discover" and method == "GET":
            return self.discover(c, me, q)
        if path == "swipe" and method == "POST":
            return self.swipe(c, me, self.body())
        if path == "undo" and method == "POST":
            return self.undo(c, me)
        if path == "reset-swipes" and method == "POST":
            c.execute("DELETE FROM swipes WHERE from_id=? AND kind='pass'", (uid,))
            return {"ok": True}
        if path == "matches" and method == "GET":
            ms = matches_public(c, me)
            return {"matches": ms, "unread": sum(m["unread"] for m in ms)}
        m = re.fullmatch(r"matches/(\d+)/(messages|unmatch|rooms)", path)
        if m:
            return self.match_ops(c, me, int(m.group(1)), m.group(2), method, q)
        if path == "rooms" and method == "GET":
            rooms = [dict(r) for r in _get_rooms(c)]
            log_impressions(c, [r["id"] for r in rooms if r["sponsored"]], uid)
            return {"rooms": rooms}
        if path == "services" and method == "GET":
            return {"services": [dict(s) for s in _get_services(c, q.get("kind", "truck"))]}
        if path == "orders":
            if method == "GET":
                rows = c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
                return {"orders": [order_dict(o) for o in rows]}
            if method == "POST":
                return self.make_order(c, me, self.body())
        raise Err(404, "Không tìm thấy")

    def me_dict(self, c, me):
        d = user_row_to_dict(me)
        d["username"] = me["username"]
        d["pref_gender"] = me["pref_gender"]
        d["onboarded"] = bool(me["onboarded"])
        d["guest"] = me["username"].startswith("guest_")
        uid = me["id"]
        cutoff = time.time() - 86400
        row = c.execute(
            "SELECT"
            " (SELECT COUNT(*) FROM swipes s JOIN users u ON u.id=s.from_id WHERE s.to_id=? AND u.is_bot=0 AND s.kind IN('like','super') AND s.from_id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)) AS liked_me,"
            " (SELECT COUNT(*) FROM swipes WHERE from_id=? AND kind='super' AND created>?) AS used_super,"
            " (SELECT COUNT(*) FROM swipes WHERE from_id=?) AS swiped,"
            " (SELECT COUNT(*) FROM matches WHERE (a=? OR b=?) AND active=1) AS matches,"
            " (SELECT COUNT(*) FROM orders WHERE user_id=?) AS orders",
            (uid, uid, uid, cutoff, uid, uid, uid, uid),
        ).fetchone()
        d["liked_me"] = int(row["liked_me"] or 0)
        d["super_left"] = max(0, SUPER_DAILY - int(row["used_super"] or 0))
        d["counts"] = {
            "swiped": int(row["swiped"] or 0),
            "matches": int(row["matches"] or 0),
            "orders": int(row["orders"] or 0),
        }
        return d

    def do_auth(self, c, kind):
        b = self.body()
        if kind == "guest":
            username = "guest_" + secrets.token_hex(4)
            pw = secrets.token_hex(8)
            name = "Bạn mới"
        else:
            username = clean_text(b.get("username"), 30).lower()
            pw = str(b.get("password") or "")
            name = clean_text(b.get("name"), 40)
        if kind == "login":
            row = c.execute("SELECT * FROM users WHERE username=? AND is_bot=0", (username,)).fetchone()
            if not row or hash_pw(pw, row["salt"]) != row["pw"]:
                raise Err(401, "Sai tên đăng nhập hoặc mật khẩu")
            uid = row["id"]
        else:
            if kind == "register":
                if not re.fullmatch(r"[a-z0-9_.]{3,30}", username):
                    raise Err(400, "Tên đăng nhập 3-30 ký tự: chữ thường, số, _ hoặc .")
                if len(pw) < 6:
                    raise Err(400, "Mật khẩu tối thiểu 6 ký tự")
                if not name:
                    raise Err(400, "Vui lòng nhập tên hiển thị")
                if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                    raise Err(409, "Tên đăng nhập đã tồn tại")
            salt = secrets.token_hex(16)
            now = time.time()
            uid = c.insert_id("INSERT INTO users(username,salt,pw,name,color,created,created_real_time) VALUES(?,?,?,?,?,?,?)",
                              (username, salt, hash_pw(pw, salt), name, random.randint(0, 7), now, fmt_vn_time(now)))
            _invalidate_users_cache()
        tok = secrets.token_urlsafe(32)
        now = time.time()
        c.execute("INSERT INTO sessions(token,user_id,created,created_real_time) VALUES(?,?,?,?)", (tok, uid, now, fmt_vn_time(now)))
        me = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        _cache_set_user(tok, me)
        return {"token": tok, "user": self.me_dict(c, me)}

    def discover(self, c, me, q):
        uid = me["id"]
        if q.get("reset_pass") == "1":
            c.execute("DELETE FROM swipes WHERE from_id=? AND kind='pass'", (uid,))
        try:
            min_score = int(q.get("min", 0) or 0)
            blo = float(q["blo"]) if q.get("blo") else None
            bhi = float(q["bhi"]) if q.get("bhi") else None
        except (TypeError, ValueError):
            raise Err(400, "Bộ lọc không hợp lệ")
        uni = q.get("uni", "")
        rel_rows = c.execute(
            "SELECT 1 AS t, to_id AS oid, kind FROM swipes WHERE from_id=?"
            " UNION ALL "
            "SELECT 2 AS t, from_id AS oid, kind FROM swipes WHERE to_id=? AND kind IN ('like','super')"
            " UNION ALL "
            "SELECT 3 AS t, CASE WHEN a=? THEN b ELSE a END AS oid, '' AS kind FROM matches WHERE (a=? OR b=?) AND active=1",
            (uid, uid, uid, uid, uid),
        ).fetchall()
        swiped_out = {r["oid"]: r["kind"] for r in rel_rows if r["t"] == 1}
        liked_in = {r["oid"]: r["kind"] for r in rel_rows if r["t"] == 2}
        matched_ids = {r["oid"] for r in rel_rows if r["t"] == 3}
        all_users = _get_all_users(c)
        onb_users = [u for u in all_users.values() if u.get("onboarded")]
        out = []
        for r in onb_users:
            rid = r["id"]
            if rid == uid or rid in swiped_out or rid in matched_ids:
                continue
            if not gender_ok(me, r):
                continue
            if uni and r["university"] != uni:
                continue
            if q.get("area") and q["area"].lower() not in (r["area"] or "").lower():
                continue
            if q.get("house") and r["house_type"] != q["house"]:
                continue
            if q.get("prio") and r["priority"] != q["prio"]:
                continue
            if blo is not None and r["budget_max"] < blo:
                continue
            if bhi is not None and r["budget_max"] > bhi:
                continue
            if q.get("tag") and q["tag"] not in json.loads(r["tags"] or "[]"):
                continue
            if q.get("sleep") == "early" and r["sleep"] > 2:
                continue
            if q.get("sleep") == "late" and r["sleep"] < 4:
                continue
            if q.get("tidy") == "high" and r["tidy"] < 4:
                continue
            if q.get("photo") == "1" and not r["photo_v"]:
                continue
            d = user_row_to_dict(r, me)
            if d["compat"]["score"] < min_score:
                continue
            lk_raw = liked_in.get(rid, "")
            lk = lk_raw if lk_raw in ("like", "super") else ""
            d["liked_you"] = bool(lk)
            d["liked_kind"] = lk
            out.append(d)
        out.sort(key=lambda d: (0 if d["liked_kind"] == "super" else (1 if d["liked_kind"] == "like" else 2), -d["compat"]["score"]))
        unis = sorted({r["university"] for r in onb_users if r.get("university")})
        areas = sorted({r["area"] for r in onb_users if r.get("area") and r["id"] != uid})
        passed_cnt = sum(1 for k in swiped_out.values() if k == "pass")
        return {"candidates": out[:40], "total": len(out), "universities": unis, "areas": areas, "passed_count": passed_cnt}

    def swipe(self, c, me, b):
        uid = me["id"]
        try:
            to = int(b.get("to", 0))
        except (TypeError, ValueError):
            raise Err(400, "Người dùng không hợp lệ")
        kind = b.get("kind")
        if kind not in ("like", "pass", "super"):
            raise Err(400, "Hành động không hợp lệ")
        if kind == "pass":
            if to <= 0 or to == uid:
                raise Err(404, "Không tìm thấy người dùng")
            now = time.time()
            c.execute("INSERT INTO swipes(from_id,to_id,kind,created,created_real_time) VALUES(?,?,?,?,?) ON CONFLICT(from_id,to_id) DO UPDATE SET kind=excluded.kind, created=excluded.created, created_real_time=excluded.created_real_time", (uid, to, kind, now, fmt_vn_time(now)))
            return {"matched": False}
        other = _get_all_users(c).get(to) if to != uid else None
        if other is None:
            other = c.execute("SELECT * FROM users WHERE id=? AND id!=?", (to, uid)).fetchone()
        if not other:
            raise Err(404, "Không tìm thấy người dùng")
        res_extra = {}
        if kind == "super":
            used = int(c.execute("SELECT COUNT(*) n FROM swipes WHERE from_id=? AND kind='super' AND created>?", (uid, time.time() - 86400)).fetchone()["n"] or 0)
            if used >= SUPER_DAILY:
                raise Err(429, f"Hôm nay bạn đã dùng hết {SUPER_DAILY} lượt Siêu thích ⭐")
            res_extra["super_left"] = max(0, SUPER_DAILY - (used + 1))
        now = time.time()
        c.execute("INSERT INTO swipes(from_id,to_id,kind,created,created_real_time) VALUES(?,?,?,?,?) ON CONFLICT(from_id,to_id) DO UPDATE SET kind=excluded.kind, created=excluded.created, created_real_time=excluded.created_real_time", (uid, to, kind, now, fmt_vn_time(now)))
        score = compat(me, other)["score"]
        mutual = False
        if other["is_bot"]:
            mutual = kind == "super" and score >= 45 or score >= BOT_LIKE_THRESHOLD
        else:
            r = c.execute("SELECT kind FROM swipes WHERE from_id=? AND to_id=?", (to, uid)).fetchone()
            mutual = bool(r and r["kind"] in ("like", "super"))
        if not mutual:
            note = ("Đã gửi Siêu thích ⭐ — hồ sơ bạn sẽ được đẩy lên đầu!" if kind == "super" else "Đã gửi lượt thích, chờ họ thích lại") if not other["is_bot"] else "Bạn ấy chưa thấy hợp lắm, thử người khác nhé"
            return {"matched": False, "note": note, **res_extra}
        m, created = create_match(c, uid, to, score)
        if created and other["is_bot"]:
            bot_say(c, m["id"], other["id"], bot_opening(other, score), 2.0)
        mp = match_public(c, m, uid, me=me, other=other, fresh=created)
        mp["rooms"] = rooms_for(c, me, other, uid)
        return {"matched": True, "match": mp, "new": created, **res_extra}

    def undo(self, c, me):
        uid = me["id"]
        row = c.execute(
            "SELECT s.from_id, s.to_id, s.kind AS _skind,"
            " EXISTS(SELECT 1 FROM matches m WHERE (m.a=s.from_id AND m.b=s.to_id) OR (m.a=s.to_id AND m.b=s.from_id)) AS _matched,"
            " u.*"
            " FROM swipes s JOIN users u ON u.id=s.to_id"
            " WHERE s.from_id=? ORDER BY s.created DESC LIMIT 1",
            (uid,),
        ).fetchone()
        if not row:
            raise Err(400, "Không có gì để hoàn tác")
        if row["_matched"]:
            raise Err(400, "Đã match rồi, không thể hoàn tác")
        c.execute("DELETE FROM swipes WHERE from_id=? AND to_id=?", (row["from_id"], row["to_id"]))
        res = {"user": user_row_to_dict(row, me)}
        if row["_skind"] == "super":
            used = int(c.execute("SELECT COUNT(*) n FROM swipes WHERE from_id=? AND kind='super' AND created>?", (uid, time.time() - 86400)).fetchone()["n"] or 0)
            res["super_left"] = max(0, SUPER_DAILY - used)
        return res

    def match_ops(self, c, me, mid, op, method, q):
        uid = me["id"]
        other = c.execute(
            "SELECT u.*, m.id AS _mid FROM matches m"
            " JOIN users u ON u.id = CASE WHEN m.a=? THEN m.b ELSE m.a END"
            " WHERE m.id=? AND (m.a=? OR m.b=?) AND m.active=1",
            (uid, mid, uid, uid),
        ).fetchone()
        if not other:
            raise Err(404, "Không tìm thấy cuộc trò chuyện")
        other_id = other["id"]
        if op == "unmatch" and method == "POST":
            c.execute("UPDATE matches SET active=0 WHERE id=?", (mid,))
            return {"ok": True}
        if op == "rooms":
            return {"rooms": rooms_for(c, me, other, uid)}
        now = time.time()
        if method == "POST":
            text = clean_text(self.body().get("text"), 1000)
            if not text:
                raise Err(400, "Tin nhắn trống")
            c.execute("INSERT INTO messages(match_id,sender,text,created,created_real_time,visible_at) VALUES(?,?,?,?,?,?)", (mid, uid, text, now, fmt_vn_time(now), now))
            if other["is_bot"]:
                bot_say(c, mid, other_id, bot_reply(other, text, me["name"]), random.uniform(1.2, 2.8))
            return {"ok": True}
        try:
            after = int(q.get("after", 0) or 0)
        except (TypeError, ValueError):
            after = 0
        rows = c.execute(
            "SELECT id, sender, text, created, visible_at, read"
            " FROM messages WHERE match_id=? AND (id>? OR (sender=? AND visible_at>?))"
            " ORDER BY id",
            (mid, after, other_id, now),
        ).fetchall()
        if any(r["sender"] != uid and not r["read"] and r["visible_at"] <= now for r in rows):
            c.execute("UPDATE messages SET read=1 WHERE match_id=? AND sender!=? AND read=0 AND visible_at<=?", (mid, uid, now))
        vis_rows = [r for r in rows if r["id"] > after and r["visible_at"] <= now]
        msgs = [{"id": r["id"], "mine": r["sender"] == uid, "text": r["text"], "at": r["created"]} for r in vis_rows]
        pend_ids = [r["id"] for r in rows if r["visible_at"] > now]
        cursor = max((r["id"] for r in vis_rows), default=after)
        if pend_ids:
            cursor = max(after, min(cursor, min(pend_ids) - 1))
        typing = bool(pend_ids)
        return {"messages": msgs, "cursor": cursor, "typing": typing, "user": user_row_to_dict(other, me)}

    def make_order(self, c, me, b):
        kind = b.get("kind")
        try:
            item_id = int(b.get("item_id", 0))
        except (TypeError, ValueError):
            raise Err(400, "Dịch vụ không hợp lệ")
        if kind == "room":
            r = c.execute("SELECT * FROM rooms WHERE id=?", (item_id,)).fetchone()
            if not r:
                raise Err(404, "Không tìm thấy phòng")
            name, amount, base = "Xem phòng: " + r["name"], r["price"], r["price"] * 0.5
        elif kind in ("truck", "clean", "used"):
            s = c.execute("SELECT * FROM services WHERE id=? AND kind=?", (item_id, kind)).fetchone()
            if not s:
                raise Err(404, "Không tìm thấy dịch vụ")
            name, amount, base = s["name"], s["price"], s["price"]
        else:
            raise Err(400, "Loại đơn không hợp lệ")
        com = int(round(base * COMMISSION[kind] / 1000) * 1000)
        now = time.time()
        oid = c.insert_id("INSERT INTO orders(user_id,kind,item_id,item_name,amount,commission,note,date,created,created_real_time) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (me["id"], kind, item_id, name, amount, com, clean_text(b.get("note"), 300), clean_text(b.get("date"), 30), now, fmt_vn_time(now)))
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        return {"order": order_dict(o)}

    def stats(self, c):
        s = c.execute(
            "SELECT"
            " (SELECT COUNT(*) FROM users WHERE is_bot=0) AS users,"
            " (SELECT COUNT(*) FROM matches) AS matches,"
            " (SELECT COUNT(*) FROM messages) AS messages,"
            " (SELECT COUNT(*) FROM swipes) AS swipes,"
            " (SELECT COUNT(*) FROM impressions) AS impressions,"
            " (SELECT COUNT(*) FROM orders) AS orders,"
            " (SELECT SUM(commission) FROM orders) AS commission"
        ).fetchone()
        by_kind = {r["kind"]: {"orders": int(r["n"] or 0), "gmv": int(r["g"] or 0), "commission": int(r["cm"] or 0)} for r in c.execute(
            "SELECT kind, COUNT(*) n, SUM(amount) g, SUM(commission) cm FROM orders GROUP BY kind").fetchall()}
        top_rooms = [{"name": r["name"], "views": int(r["n"] or 0)} for r in c.execute(
            "SELECT r.name, COUNT(*) n FROM impressions i JOIN rooms r ON r.id=i.room_id GROUP BY r.id, r.name ORDER BY n DESC LIMIT 3").fetchall()]
        imps = int(s["impressions"] or 0)
        return {
            "users": int(s["users"] or 0),
            "matches": int(s["matches"] or 0),
            "messages": int(s["messages"] or 0),
            "swipes": int(s["swipes"] or 0),
            "impressions": imps,
            "orders": int(s["orders"] or 0),
            "commission": int(s["commission"] or 0),
            "sponsor_revenue": imps * 2000,  # giả định 2.000đ / lượt hiển thị
            "by_kind": by_kind, "top_rooms": top_rooms,
        }

    def opt_auth(self, c):
        try:
            return self.auth(c)
        except Err:
            return None

    def submit_feedback(self, c, b):
        me = self.opt_auth(c)
        uid = me["id"] if me else 0
        default_name = (me["name"] if me and me["name"] != "Bạn mới" else "")
        tester_name = clean_text(b.get("tester_name"), 40) or default_name or "Ẩn danh"
        device = b.get("device") if b.get("device") in ("mobile", "desktop", "both") else "mobile"
        scores = {}
        for k in ("r_ui", "r_ux", "r_match", "r_eco", "r_overall"):
            raw = b.get(k)
            if raw is None or isinstance(raw, bool):
                raise Err(400, "Vui lòng chọn điểm đánh giá từ 1 đến 5 sao")
            try:
                v = int(raw)
            except (TypeError, ValueError):
                raise Err(400, "Điểm đánh giá không hợp lệ")
            scores[k] = max(1, min(5, v))
        favs = _norm_favs_list(b.get("fav_features"))
        if not favs:
            raise Err(400, "Vui lòng chọn ít nhất 1 điểm bạn thích nhất")
        issue = b.get("issue_type") if b.get("issue_type") in ("smooth", "lag", "ui_bug", "func_bug") else "smooth"
        shark = b.get("shark_invest") if b.get("shark_invest") in ("strong", "explore", "consider", "no") else "explore"
        pitch_closer = b.get("pitch_closer") if b.get("pitch_closer") in GFORM_PITCH else ""
        suggestion = clean_text(b.get("suggestion"), 600)
        now = time.time()
        row_dict = {
            "id": "pending",
            "tester_name": tester_name,
            "device": device,
            "r_ui": scores["r_ui"],
            "r_ux": scores["r_ux"],
            "r_match": scores["r_match"],
            "r_eco": scores["r_eco"],
            "r_overall": scores["r_overall"],
            "fav_features": favs,
            "issue_type": issue,
            "shark_invest": shark,
            "pitch_closer": pitch_closer,
            "suggestion": suggestion,
            "created": now,
            "source": "pending",
        }
        fp = _fb_fingerprint(row_dict)
        sheet_rows = _fetch_gsheet_rows(force=False)
        sheet_count = sum(1 for sr in sheet_rows if _fb_fingerprint(sr) == fp)
        with _GSHEET_LOCK:
            max_exp = max((e["expected"] for e in _RECENT_SYNCED if e["fp"] == fp and e["exp"] > now), default=0)
        expected = max(sheet_count, max_exp) + 1
        synced = _post_to_gform(row_dict)
        fid = c.insert_id(
            "INSERT INTO feedback(user_id,tester_name,device,r_ui,r_ux,r_match,r_eco,r_overall,fav_features,issue_type,shark_invest,pitch_closer,suggestion,synced,created,created_real_time)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, tester_name, device, scores["r_ui"], scores["r_ux"], scores["r_match"], scores["r_eco"], scores["r_overall"],
             json.dumps(favs, ensure_ascii=False), issue, shark, pitch_closer, suggestion, 1 if synced else 0, now, fmt_vn_time(now)),
        )
        row_dict["id"] = f"pending-{fid}"
        if synced:
            with _GSHEET_LOCK:
                _GSHEET_CACHE["ts"] = 0.0
                _RECENT_SYNCED.append({"fp": fp, "expected": expected, "row": row_dict, "exp": now + 25.0})
        return {"ok": True, "id": fid, "synced_to_google": bool(synced)}

    def _all_feedback_rows(self, c, force_sheet=False):
        sheet_rows = _fetch_gsheet_rows(force=force_sheet)
        fp_counts = {}
        for r in sheet_rows:
            fp = _fb_fingerprint(r)
            fp_counts[fp] = fp_counts.get(fp, 0) + 1
        now = time.time()
        pending = []
        with _GSHEET_LOCK:
            kept = []
            for entry in _RECENT_SYNCED:
                if entry["exp"] <= now:
                    continue
                if fp_counts.get(entry["fp"], 0) >= entry["expected"]:
                    continue
                kept.append(entry)
                pending.append(dict(entry["row"]))
            _RECENT_SYNCED[:] = kept
        db_rows = []
        for r in c.execute("SELECT * FROM feedback WHERE COALESCE(synced, 0) = 0 ORDER BY id DESC").fetchall():
            d = dict(r)
            d["fav_features"] = _norm_favs_list(d.get("fav_features"))
            d["pitch_closer"] = d.get("pitch_closer") or ""
            d["source"] = "db"
            db_rows.append(d)
        merged = pending + sheet_rows + db_rows
        merged.sort(key=lambda r: float(r.get("created") or 0), reverse=True)
        return merged

    def feedback_stats(self, c):
        rows = self._all_feedback_rows(c)
        n = len(rows)
        by_dev = {"mobile": 0, "desktop": 0, "both": 0}
        by_iss = {"smooth": 0, "lag": 0, "ui_bug": 0, "func_bug": 0}
        by_shk = {"strong": 0, "explore": 0, "consider": 0, "no": 0}
        by_pitch = {"viral": 0, "margin": 0, "safety": 0, "scale": 0}
        sums = {"r_ui": 0, "r_ux": 0, "r_match": 0, "r_eco": 0, "r_overall": 0}
        feat_cnt = {}
        items = []
        for idx, r in enumerate(rows):
            if r.get("device") in by_dev:
                by_dev[r["device"]] += 1
            if r.get("issue_type") in by_iss:
                by_iss[r["issue_type"]] += 1
            if r.get("shark_invest") in by_shk:
                by_shk[r["shark_invest"]] += 1
            if r.get("pitch_closer") in by_pitch:
                by_pitch[r["pitch_closer"]] += 1
            for k in sums:
                sums[k] += int(r.get(k) or 0)
            favs = r["fav_features"] if isinstance(r.get("fav_features"), list) else _norm_favs_list(r.get("fav_features"))
            for f in favs:
                feat_cnt[f] = feat_cnt.get(f, 0) + 1
            if idx < 80:
                items.append({
                    "id": r.get("id"),
                    "tester_name": r.get("tester_name") or "Ẩn danh",
                    "device": r.get("device") or "mobile",
                    "r_ui": int(r.get("r_ui") or 0),
                    "r_ux": int(r.get("r_ux") or 0),
                    "r_match": int(r.get("r_match") or 0),
                    "r_eco": int(r.get("r_eco") or 0),
                    "r_overall": int(r.get("r_overall") or 0),
                    "fav_features": favs,
                    "issue_type": r.get("issue_type") or "smooth",
                    "shark_invest": r.get("shark_invest") or "explore",
                    "pitch_closer": r.get("pitch_closer") or "",
                    "suggestion": r.get("suggestion") or "",
                    "created": r.get("created") or 0,
                })
        avg = {
            "ui": round(sums["r_ui"] / n, 2) if n else 0,
            "ux": round(sums["r_ux"] / n, 2) if n else 0,
            "match": round(sums["r_match"] / n, 2) if n else 0,
            "eco": round(sums["r_eco"] / n, 2) if n else 0,
            "overall": round(sums["r_overall"] / n, 2) if n else 0,
        }
        top_features = [{"name": k, "count": v} for k, v in sorted(feat_cnt.items(), key=lambda x: (-x[1], x[0]))]
        return {
            "total": n,
            "averages": avg,
            "by_device": by_dev,
            "by_issue": by_iss,
            "by_shark": by_shk,
            "by_pitch": by_pitch,
            "invest_ready_pct": round((by_shk["strong"] + by_shk["explore"]) * 100 / n) if n else 0,
            "smooth_pct": round(by_iss["smooth"] * 100 / n) if n else 0,
            "top_features": top_features,
            "items": items,
            "source": "google_sheet" if GSHEET_CSV_URL else "database",
            "gform_url": GFORM_VIEW_URL,
            "gsheet_url": GSHEET_EDIT_URL,
        }

    def feedback_csv(self):
        rows = []
        for attempt in (0, 1):
            c = db()
            try:
                rows = self._all_feedback_rows(c, force_sheet=True)
                break
            except Exception as e:
                if IS_PG and isinstance(e, (psycopg.OperationalError, psycopg.InterfaceError)):
                    c.discard()
                    if attempt == 0:
                        continue
                raise
            finally:
                c.close()
        dev_map = {"mobile": "Điện thoại", "desktop": "Laptop / Máy tính bảng", "both": "Cả hai"}
        iss_map = {"smooth": "Chạy rất mượt", "lag": "Hơi lag nhẹ", "ui_bug": "Lỗi hiển thị", "func_bug": "Lỗi chức năng"}
        shk_map = {"strong": "Đầu tư mạnh (≥3 tỷ)", "explore": "Thăm dò (1-2 tỷ)", "consider": "Cân nhắc thêm", "no": "Chưa đầu tư"}
        pitch_map = {
            "viral": "Kéo user 0đ (viral ĐH)",
            "margin": "Biên lợi nhuận & đối tác",
            "safety": "Chống nick ảo & an toàn",
            "scale": "Mở rộng 6–12 tháng",
        }
        tz = timezone(timedelta(hours=7))
        safe_cell = lambda s: ("'" + str(s)) if s and str(s)[0] in ("=", "+", "-", "@", "\t", "\r") else str(s or "")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["ID", "Thời gian (UTC+7)", "Người đánh giá", "Thiết bị", "Điểm UI", "Điểm UX",
                    "Chấm 5 thói quen", "Hệ sinh thái", "Tổng thể", "Tính năng thích",
                    "Trải nghiệm kỹ thuật", "Mức độ đầu tư (10 tỷ ảo)", "Câu chốt Pitch", "Đề xuất & Cải tiến"])
        for r in rows:
            ts_val = float(r.get("created") or 0)
            ts = datetime.fromtimestamp(ts_val, tz).strftime("%Y-%m-%d %H:%M") if ts_val > 1_000_000_000 else ""
            fav_list = r["fav_features"] if isinstance(r.get("fav_features"), list) else _norm_favs_list(r.get("fav_features"))
            favs = ", ".join(fav_list)
            w.writerow([
                r.get("id", ""), ts, safe_cell(r.get("tester_name") or ""),
                dev_map.get(r.get("device"), r.get("device") or ""),
                r.get("r_ui", ""), r.get("r_ux", ""), r.get("r_match", ""), r.get("r_eco", ""), r.get("r_overall", ""),
                favs, iss_map.get(r.get("issue_type"), r.get("issue_type") or ""),
                shk_map.get(r.get("shark_invest"), r.get("shark_invest") or ""),
                pitch_map.get(r.get("pitch_closer") or "", ""),
                safe_cell(r.get("suggestion") or ""),
            ])
        data = ("\ufeff" + buf.getvalue()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="smart-roommate-feedback.csv"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def feedback_xlsx(self):
        if GSHEET_XLSX_URL:
            try:
                req = urllib.request.Request(GSHEET_XLSX_URL, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                if len(data) > 100 and data[:2] == b"PK":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    self.send_header("Content-Disposition", 'attachment; filename="smart-roommate-feedback.xlsx"')
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(data)
                    return
            except Exception as e:
                sys.stderr.write(f"GSheet xlsx fetch error: {e}\n")
        self.feedback_csv()


def main():
    init_db()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"Smart Roommate Matcher đang chạy tại http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
