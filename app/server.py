#!/usr/bin/env python3
"""Smart Roommate Matcher - backend (Python stdlib + SQLite, không cần cài thư viện).

Chạy:  python server.py   ->  http://localhost:8000
"""
import gzip
import hashlib
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

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


# ----------------------------------------------------------------- database & caches
_PG_POOL = queue.LifoQueue(maxsize=8)
_AUTH_CACHE = {}
_AUTH_LOCK = threading.Lock()
_ROOMS_CACHE = []
_SERVICES_CACHE = {}
_STATIC_CACHE = {}


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
        _AUTH_CACHE[tok] = (dict(row), time.time() + 60)


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
                if conn.closed or now - ts > 240:
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
        self.conn.commit()

    def rollback(self):
        try:
            if self.conn and (not IS_PG or not self.conn.closed):
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
  tags TEXT DEFAULT '[]', is_bot INTEGER DEFAULT 0, onboarded INTEGER DEFAULT 0, created REAL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS swipes(from_id INTEGER, to_id INTEGER, kind TEXT, created REAL, PRIMARY KEY(from_id,to_id));
CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY AUTOINCREMENT, a INTEGER, b INTEGER, score INTEGER, created REAL, active INTEGER DEFAULT 1, UNIQUE(a,b));
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER, sender INTEGER, text TEXT, created REAL, visible_at REAL, read INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY, name TEXT, price INTEGER, district TEXT, descr TEXT, near TEXT, dist TEXT, sponsored INTEGER, emoji TEXT, beds INTEGER, amenities TEXT, owner TEXT);
CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY, kind TEXT, name TEXT, price INTEGER, unit TEXT, descr TEXT, rating REAL, jobs INTEGER, emoji TEXT, promoted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, item_id INTEGER, item_name TEXT, amount INTEGER, commission INTEGER, note TEXT, date TEXT, status TEXT DEFAULT 'new', created REAL);
CREATE TABLE IF NOT EXISTS impressions(id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER, user_id INTEGER, created REAL);
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
    c.execute(f"CREATE TABLE IF NOT EXISTS photos(user_id INTEGER PRIMARY KEY, data {'BYTEA' if IS_PG else 'BLOB'})")
    fresh = not c.execute("SELECT 1 FROM users WHERE is_bot=1").fetchone()
    if fresh:
        for i, b in enumerate(BOTS):
            n, e, g, age, uni, area, bmin, bmax, h, tags, bio = b
            c.execute(
                "INSERT INTO users(username,name,emoji,color,university,bio,age,gender,budget_min,budget_max,area,sleep,tidy,money,noise,guest,tags,is_bot,onboarded,created)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,1,?)",
                (f"bot{i}", n, e, i % 8, uni, bio, age, g, bmin, bmax, area, *h, json.dumps(tags, ensure_ascii=False), time.time()),
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
    now = time.time()
    c.execute("INSERT INTO messages(match_id,sender,text,created,visible_at) VALUES(?,?,?,?,?)", (match_id, bot_id, text, now + delay, now + delay))


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
    mid = c.insert_id("INSERT INTO matches(a,b,score,created) VALUES(?,?,?,?)", (a, b, score, time.time()))
    return c.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone(), True


def log_impressions(c, room_ids, user_id):
    if not room_ids:
        return
    now = time.time()
    vals = ",".join("(?,?,?)" for _ in room_ids)
    params = []
    for rid in room_ids:
        params.extend((rid, user_id, now))
    c.execute(f"INSERT INTO impressions(room_id,user_id,created) VALUES {vals}", tuple(params))


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


class Handler(BaseHTTPRequestHandler):
    server_version = "RoommateMatcher/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    # --- helpers
    def _tok(self):
        h = self.headers.get("Authorization", "")
        return h[7:] if h.startswith("Bearer ") else ""

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        gz = len(body) > 512 and "gzip" in self.headers.get("Accept-Encoding", "").lower()
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

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def route(self, method):
        u = urlparse(self.path)
        path, q = u.path, {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
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
                self.send_json(res)
            elif method == "GET" and path.startswith("/photo/"):
                self.photo(path[7:])
            elif method == "GET":
                self.static(path)
            else:
                raise Err(405, "Method not allowed")
        except Err as e:
            self.send_json({"error": e.msg}, e.code)
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

    def static(self, path):
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
        use_gz = len(data) > 512 and "gzip" in self.headers.get("Accept-Encoding", "").lower()
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
        self.wfile.write(payload)

    # --- API
    def api(self, c, method, path, q):
        # ---- public
        if path == "health":
            return {"ok": True}
        if path == "stats" and method == "GET":
            return self.stats(c)
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
            uid = c.insert_id("INSERT INTO users(username,salt,pw,name,color,created) VALUES(?,?,?,?,?,?)",
                              (username, salt, hash_pw(pw, salt), name, random.randint(0, 7), time.time()))
        tok = secrets.token_urlsafe(32)
        c.execute("INSERT INTO sessions VALUES(?,?,?)", (tok, uid, time.time()))
        me = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        _cache_set_user(tok, me)
        return {"token": tok, "user": self.me_dict(c, me)}

    def discover(self, c, me, q):
        uid = me["id"]
        try:
            min_score = int(q.get("min", 0) or 0)
            blo = float(q["blo"]) if q.get("blo") else None
            bhi = float(q["bhi"]) if q.get("bhi") else None
        except (TypeError, ValueError):
            raise Err(400, "Bộ lọc không hợp lệ")
        uni = q.get("uni", "")
        rows = c.execute(
            "SELECT u.*, ls.kind AS _lk"
            " FROM users u"
            " LEFT JOIN swipes ls ON ls.from_id=u.id AND ls.to_id=?"
            " WHERE u.id!=? AND u.onboarded=1"
            "   AND u.id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)"
            "   AND u.id NOT IN (SELECT CASE WHEN a=? THEN b ELSE a END FROM matches WHERE (a=? OR b=?) AND active=1)",
            (uid, uid, uid, uid, uid, uid)).fetchall()
        out = []
        for r in rows:
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
            # người thật đã thích / siêu thích mình -> ưu tiên lên đầu (siêu thích trên cùng)
            lk = r["_lk"] if r["_lk"] in ("like", "super") else ""
            d["liked_you"] = bool(lk)
            d["liked_kind"] = lk
            out.append(d)
        out.sort(key=lambda d: (0 if d["liked_kind"] == "super" else (1 if d["liked_kind"] == "like" else 2), -d["compat"]["score"]))
        meta = c.execute("SELECT id, university, area FROM users WHERE onboarded=1").fetchall()
        unis = sorted({r["university"] for r in meta if r["university"]})
        areas = sorted({r["area"] for r in meta if r["area"] and r["id"] != uid})
        return {"candidates": out[:40], "total": len(out), "universities": unis, "areas": areas}

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
            c.execute("INSERT INTO swipes(from_id,to_id,kind,created) VALUES(?,?,?,?) ON CONFLICT(from_id,to_id) DO UPDATE SET kind=excluded.kind, created=excluded.created", (uid, to, kind, time.time()))
            return {"matched": False}
        other = c.execute("SELECT * FROM users WHERE id=? AND id!=?", (to, uid)).fetchone()
        if not other:
            raise Err(404, "Không tìm thấy người dùng")
        res_extra = {}
        if kind == "super":
            used = int(c.execute("SELECT COUNT(*) n FROM swipes WHERE from_id=? AND kind='super' AND created>?", (uid, time.time() - 86400)).fetchone()["n"] or 0)
            if used >= SUPER_DAILY:
                raise Err(429, f"Hôm nay bạn đã dùng hết {SUPER_DAILY} lượt Siêu thích ⭐")
            res_extra["super_left"] = max(0, SUPER_DAILY - (used + 1))
        c.execute("INSERT INTO swipes(from_id,to_id,kind,created) VALUES(?,?,?,?) ON CONFLICT(from_id,to_id) DO UPDATE SET kind=excluded.kind, created=excluded.created", (uid, to, kind, time.time()))
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
        row = c.execute("SELECT * FROM swipes WHERE from_id=? ORDER BY created DESC LIMIT 1", (me["id"],)).fetchone()
        if not row:
            raise Err(400, "Không có gì để hoàn tác")
        a, b = sorted((row["from_id"], row["to_id"]))
        if c.execute("SELECT 1 FROM matches WHERE a=? AND b=?", (a, b)).fetchone():
            raise Err(400, "Đã match rồi, không thể hoàn tác")
        c.execute("DELETE FROM swipes WHERE from_id=? AND to_id=?", (row["from_id"], row["to_id"]))
        other = c.execute("SELECT * FROM users WHERE id=?", (row["to_id"],)).fetchone()
        res = {"user": user_row_to_dict(other, me)}
        if row["kind"] == "super":
            used = int(c.execute("SELECT COUNT(*) n FROM swipes WHERE from_id=? AND kind='super' AND created>?", (me["id"], time.time() - 86400)).fetchone()["n"] or 0)
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
            c.execute("INSERT INTO messages(match_id,sender,text,created,visible_at) VALUES(?,?,?,?,?)", (mid, uid, text, now, now))
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
        oid = c.insert_id("INSERT INTO orders(user_id,kind,item_id,item_name,amount,commission,note,date,created) VALUES(?,?,?,?,?,?,?,?,?)",
                          (me["id"], kind, item_id, name, amount, com, clean_text(b.get("note"), 300), clean_text(b.get("date"), 30), time.time()))
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
