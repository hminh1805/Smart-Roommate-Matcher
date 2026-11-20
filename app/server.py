#!/usr/bin/env python3
"""Smart Roommate Matcher - backend (Python stdlib + SQLite, không cần cài thư viện).

Chạy:  python server.py   ->  http://localhost:8000
"""
import hashlib
import json
import mimetypes
import os
import random
import re
import secrets
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "data", "app.db"))
PORT = int(os.environ.get("PORT", "8000"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

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


# ----------------------------------------------------------------- database
def db():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


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


def init_db():
    c = db()
    c.executescript(SCHEMA)
    c.execute("PRAGMA journal_mode=WAL")
    if not c.execute("SELECT 1 FROM users WHERE is_bot=1").fetchone():
        for i, b in enumerate(BOTS):
            n, e, g, age, uni, area, bmin, bmax, h, tags, bio = b
            c.execute(
                "INSERT INTO users(username,name,emoji,color,university,bio,age,gender,budget_min,budget_max,area,sleep,tidy,money,noise,guest,tags,is_bot,onboarded,created)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,1,?)",
                (f"bot{i}", n, e, i % 8, uni, bio, age, g, bmin, bmax, area, *h, json.dumps(tags, ensure_ascii=False), time.time()),
            )
    if not c.execute("SELECT 1 FROM rooms").fetchone():
        for r in ROOMS:
            c.execute("INSERT INTO rooms VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (*r[:5], json.dumps(r[5], ensure_ascii=False), *r[6:10], json.dumps(r[10], ensure_ascii=False), r[11]))
        for s in SERVICES:
            c.execute("INSERT INTO services VALUES(?,?,?,?,?,?,?,?,?,?)", s)
    c.commit()
    c.close()


# ----------------------------------------------------------------- logic
def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()


def user_row_to_dict(u, me=None, full=True):
    d = {
        "id": u["id"], "name": u["name"], "emoji": u["emoji"], "color": u["color"],
        "university": u["university"], "bio": u["bio"], "age": u["age"], "gender": u["gender"],
        "area": u["area"], "budget_min": u["budget_min"], "budget_max": u["budget_max"],
        "habits": {k: u[k] for k in HABITS}, "tags": json.loads(u["tags"] or "[]"),
        "is_bot": bool(u["is_bot"]),
    }
    if me is not None:
        d["compat"] = compat(me, u)
    return d


def compat(a, b):
    tot = sum(WEIGHTS.values())
    dist = sum(WEIGHTS[k] * abs(a[k] - b[k]) / 4 for k in HABITS) / tot
    habit = 1 - dist
    span = max(a["budget_max"], b["budget_max"]) - min(a["budget_min"], b["budget_min"])
    overlap = max(0, min(a["budget_max"], b["budget_max"]) - max(a["budget_min"], b["budget_min"]))
    budget = overlap / span if span > 0 else 1.0
    ta, tb = set(json.loads(a["tags"] or "[]")), set(json.loads(b["tags"] or "[]"))
    tagsim = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    same_uni = 1.0 if a["university"] and a["university"] == b["university"] else 0.0
    raw = 0.72 * habit + 0.14 * budget + 0.09 * tagsim + 0.05 * same_uni
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
    if budget >= 0.6:
        insights.append("Ngân sách thuê phòng khá khớp nhau")
    return {"score": score, "habits": items, "budget": round(budget * 100), "shared_tags": shared, "insights": insights}


def gender_ok(a, b):
    if a["pref_gender"] == "same" and a["gender"] != b["gender"]:
        return False
    if b["pref_gender"] == "same" and a["gender"] != b["gender"]:
        return False
    return True


def match_public(c, m, me_id):
    other_id = m["b"] if m["a"] == me_id else m["a"]
    me = c.execute("SELECT * FROM users WHERE id=?", (me_id,)).fetchone()
    other = c.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
    now = time.time()
    last = c.execute("SELECT * FROM messages WHERE match_id=? AND visible_at<=? ORDER BY id DESC LIMIT 1", (m["id"], now)).fetchone()
    unread = c.execute("SELECT COUNT(*) n FROM messages WHERE match_id=? AND sender!=? AND read=0 AND visible_at<=?", (m["id"], me_id, now)).fetchone()["n"]
    return {
        "id": m["id"], "score": m["score"], "created": m["created"], "unread": unread,
        "user": user_row_to_dict(other, me),
        "last": {"text": last["text"], "mine": last["sender"] == me_id, "at": last["created"]} if last else None,
    }


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
    cur = c.execute("INSERT INTO matches(a,b,score,created) VALUES(?,?,?,?)", (a, b, score, time.time()))
    return c.execute("SELECT * FROM matches WHERE id=?", (cur.lastrowid,)).fetchone(), True


def rooms_for(c, me, other, user_id, log=True):
    avg_max = (me["budget_max"] + other["budget_max"]) / 2 if other else me["budget_max"]
    unis = {me["university"], other["university"] if other else ""}
    out = []
    for r in c.execute("SELECT * FROM rooms").fetchall():
        near = json.loads(r["near"])
        per = r["price"] / 2 / 1_000_000
        fits = per <= avg_max + 0.3
        near_hit = any(u in near for u in unis if u)
        rank = (r["sponsored"] * 2) + (2 if near_hit else 0) + (1 if fits else -1)
        out.append((rank, r, per, fits, near_hit))
    out.sort(key=lambda x: -x[0])
    res = []
    for rank, r, per, fits, near_hit in out[:4]:
        d = room_dict(r)
        d.update({"per_person": round(per, 2), "fits": fits, "near_you": near_hit})
        res.append(d)
        if log and r["sponsored"]:
            c.execute("INSERT INTO impressions(room_id,user_id,created) VALUES(?,?,?)", (r["id"], user_id, time.time()))
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
    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 100_000:
            raise Err(413, "Dữ liệu quá lớn")
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            raise Err(400, "JSON không hợp lệ")

    def auth(self, c):
        h = self.headers.get("Authorization", "")
        tok = h[7:] if h.startswith("Bearer ") else ""
        row = c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (tok,)).fetchone() if tok else None
        if not row:
            raise Err(401, "Phiên đăng nhập đã hết hạn")
        return row

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
                c = db()
                try:
                    self.send_json(self.api(c, method, path[5:].strip("/"), q))
                    c.commit()
                finally:
                    c.close()
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

    def static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        fp = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            fp = os.path.join(STATIC, "index.html")  # SPA fallback
        with open(fp, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or "javascript" in ctype or "json" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

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
                return {"user": self.me_dict(c, me)}
        if path == "logout" and method == "POST":
            tok = self.headers.get("Authorization", "")[7:]
            c.execute("DELETE FROM sessions WHERE token=?", (tok,))
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
            rows = c.execute("SELECT * FROM matches WHERE (a=? OR b=?) AND active=1 ORDER BY id DESC", (uid, uid)).fetchall()
            ms = [match_public(c, m, uid) for m in rows]
            ms.sort(key=lambda m: -((m["last"] or {}).get("at") or m["created"]))
            return {"matches": ms, "unread": sum(m["unread"] for m in ms)}
        m = re.fullmatch(r"matches/(\d+)/(messages|unmatch|rooms)", path)
        if m:
            return self.match_ops(c, me, int(m.group(1)), m.group(2), method, q)
        if path == "rooms" and method == "GET":
            rooms = [room_dict(r) for r in c.execute("SELECT * FROM rooms ORDER BY sponsored DESC, price").fetchall()]
            for r in rooms:
                if r["sponsored"]:
                    c.execute("INSERT INTO impressions(room_id,user_id,created) VALUES(?,?,?)", (r["id"], uid, time.time()))
            return {"rooms": rooms}
        if path == "services" and method == "GET":
            rows = c.execute("SELECT * FROM services WHERE kind=? ORDER BY promoted DESC, rating DESC", (q.get("kind", "truck"),)).fetchall()
            return {"services": [service_dict(s) for s in rows]}
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
        d["liked_me"] = c.execute(
            "SELECT COUNT(*) n FROM swipes s JOIN users u ON u.id=s.from_id WHERE s.to_id=? AND u.is_bot=0 AND s.kind IN('like','super')"
            " AND s.from_id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)", (me["id"], me["id"])).fetchone()["n"]
        d["counts"] = {
            "swiped": c.execute("SELECT COUNT(*) n FROM swipes WHERE from_id=?", (me["id"],)).fetchone()["n"],
            "matches": c.execute("SELECT COUNT(*) n FROM matches WHERE (a=? OR b=?) AND active=1", (me["id"], me["id"])).fetchone()["n"],
            "orders": c.execute("SELECT COUNT(*) n FROM orders WHERE user_id=?", (me["id"],)).fetchone()["n"],
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
            cur = c.execute("INSERT INTO users(username,salt,pw,name,color,created) VALUES(?,?,?,?,?,?)",
                            (username, salt, hash_pw(pw, salt), name, random.randint(0, 7), time.time()))
            uid = cur.lastrowid
        tok = secrets.token_urlsafe(32)
        c.execute("INSERT INTO sessions VALUES(?,?,?)", (tok, uid, time.time()))
        me = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return {"token": tok, "user": self.me_dict(c, me)}

    def discover(self, c, me, q):
        uid = me["id"]
        min_score = int(q.get("min", 0) or 0)
        uni = q.get("uni", "")
        rows = c.execute(
            "SELECT * FROM users WHERE id!=? AND onboarded=1 AND id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)"
            " AND id NOT IN (SELECT CASE WHEN a=? THEN b ELSE a END FROM matches WHERE (a=? OR b=?) AND active=1)",
            (uid, uid, uid, uid, uid)).fetchall()
        out = []
        for r in rows:
            if not gender_ok(me, r):
                continue
            if uni and r["university"] != uni:
                continue
            d = user_row_to_dict(r, me)
            if d["compat"]["score"] < min_score:
                continue
            # người thật đã thích mình -> ưu tiên lên đầu
            liked = c.execute("SELECT kind FROM swipes WHERE from_id=? AND to_id=?", (r["id"], uid)).fetchone()
            d["liked_you"] = bool(liked and liked["kind"] in ("like", "super"))
            out.append(d)
        out.sort(key=lambda d: (not d["liked_you"], -d["compat"]["score"]))
        unis = sorted({r["university"] for r in c.execute("SELECT university FROM users WHERE onboarded=1").fetchall() if r["university"]})
        return {"candidates": out[:40], "total": len(out), "universities": unis}

    def swipe(self, c, me, b):
        uid, to = me["id"], int(b.get("to", 0))
        kind = b.get("kind")
        if kind not in ("like", "pass", "super"):
            raise Err(400, "Hành động không hợp lệ")
        other = c.execute("SELECT * FROM users WHERE id=? AND id!=?", (to, uid)).fetchone()
        if not other:
            raise Err(404, "Không tìm thấy người dùng")
        c.execute("INSERT OR REPLACE INTO swipes VALUES(?,?,?,?)", (uid, to, kind, time.time()))
        if kind == "pass":
            return {"matched": False}
        score = compat(me, other)["score"]
        mutual = False
        if other["is_bot"]:
            mutual = kind == "super" and score >= 45 or score >= BOT_LIKE_THRESHOLD
        else:
            r = c.execute("SELECT kind FROM swipes WHERE from_id=? AND to_id=?", (to, uid)).fetchone()
            mutual = bool(r and r["kind"] in ("like", "super"))
        if not mutual:
            return {"matched": False, "note": "Đã gửi lượt thích, chờ họ thích lại" if not other["is_bot"] else "Bạn ấy chưa thấy hợp lắm, thử người khác nhé"}
        m, created = create_match(c, uid, to, score)
        if created and other["is_bot"]:
            bot_say(c, m["id"], other["id"], bot_opening(other, score), 2.0)
        mp = match_public(c, m, uid)
        mp["rooms"] = rooms_for(c, me, other, uid)
        return {"matched": True, "match": mp, "new": created}

    def undo(self, c, me):
        row = c.execute("SELECT * FROM swipes WHERE from_id=? ORDER BY created DESC LIMIT 1", (me["id"],)).fetchone()
        if not row:
            raise Err(400, "Không có gì để hoàn tác")
        a, b = sorted((row["from_id"], row["to_id"]))
        if c.execute("SELECT 1 FROM matches WHERE a=? AND b=?", (a, b)).fetchone():
            raise Err(400, "Đã match rồi, không thể hoàn tác")
        c.execute("DELETE FROM swipes WHERE from_id=? AND to_id=?", (row["from_id"], row["to_id"]))
        other = c.execute("SELECT * FROM users WHERE id=?", (row["to_id"],)).fetchone()
        return {"user": user_row_to_dict(other, me)}

    def match_ops(self, c, me, mid, op, method, q):
        uid = me["id"]
        m = c.execute("SELECT * FROM matches WHERE id=? AND (a=? OR b=?) AND active=1", (mid, uid, uid)).fetchone()
        if not m:
            raise Err(404, "Không tìm thấy cuộc trò chuyện")
        other_id = m["b"] if m["a"] == uid else m["a"]
        other = c.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
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
        after = int(q.get("after", 0) or 0)
        c.execute("UPDATE messages SET read=1 WHERE match_id=? AND sender!=? AND visible_at<=?", (mid, uid, now))
        rows = c.execute("SELECT * FROM messages WHERE match_id=? AND id>? AND visible_at<=? ORDER BY id", (mid, after, now)).fetchall()
        typing = bool(c.execute("SELECT 1 FROM messages WHERE match_id=? AND sender=? AND visible_at>?", (mid, other_id, now)).fetchone())
        return {"messages": [{"id": r["id"], "mine": r["sender"] == uid, "text": r["text"], "at": r["created"]} for r in rows],
                "typing": typing, "user": user_row_to_dict(other, me)}

    def make_order(self, c, me, b):
        kind = b.get("kind")
        item_id = int(b.get("item_id", 0))
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
        cur = c.execute("INSERT INTO orders(user_id,kind,item_id,item_name,amount,commission,note,date,created) VALUES(?,?,?,?,?,?,?,?,?)",
                        (me["id"], kind, item_id, name, amount, com, clean_text(b.get("note"), 300), clean_text(b.get("date"), 30), time.time()))
        o = c.execute("SELECT * FROM orders WHERE id=?", (cur.lastrowid,)).fetchone()
        return {"order": order_dict(o)}

    def stats(self, c):
        one = lambda sql, *a: c.execute(sql, a).fetchone()[0] or 0
        by_kind = {r["kind"]: {"orders": r["n"], "gmv": r["g"], "commission": r["cm"]} for r in c.execute(
            "SELECT kind, COUNT(*) n, SUM(amount) g, SUM(commission) cm FROM orders GROUP BY kind").fetchall()}
        top_rooms = [{"name": r["name"], "views": r["n"]} for r in c.execute(
            "SELECT r.name, COUNT(*) n FROM impressions i JOIN rooms r ON r.id=i.room_id GROUP BY r.id ORDER BY n DESC LIMIT 3").fetchall()]
        return {
            "users": one("SELECT COUNT(*) FROM users WHERE is_bot=0"),
            "matches": one("SELECT COUNT(*) FROM matches"),
            "messages": one("SELECT COUNT(*) FROM messages"),
            "swipes": one("SELECT COUNT(*) FROM swipes"),
            "impressions": one("SELECT COUNT(*) FROM impressions"),
            "orders": one("SELECT COUNT(*) FROM orders"),
            "commission": one("SELECT SUM(commission) FROM orders"),
            "sponsor_revenue": one("SELECT COUNT(*) FROM impressions") * 2000,  # giả định 2.000đ / lượt hiển thị
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
