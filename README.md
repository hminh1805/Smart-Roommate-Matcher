# Smart Roommate Matcher

Web app tìm bạn cùng phòng kiểu Tinder. Backend Python thuần (không cần cài thư viện) + SQLite, frontend HTML/CSS/JS thuần.

## Chạy trên máy
```bash
cd app
python server.py
```
Mở http://localhost:8000

## Deploy miễn phí lên Render (lấy link công khai)
1. Đẩy code lên GitHub (`https://github.com/hminh1805/Smart-Roommate-Matcher`).
2. Vào https://render.com → **New** → **Blueprint** → chọn repo `Smart-Roommate-Matcher`.
   `render.yaml` + `Dockerfile` đã cấu hình sẵn, bấm **Apply** / **Deploy**.
3. Sau ~2 phút nhận link dạng `https://smart-roommate-matcher.onrender.com`. Ai mở link cũng dùng được, không cần tải gì.

Lưu ý: gói free ngủ sau 15 phút không dùng (lần mở đầu chờ ~30 giây) và dữ liệu SQLite được reset khi redeploy. Dữ liệu mẫu tự được tạo lại.

## Tính năng
- Đăng ký / đăng nhập, hoặc dùng thử ngay không cần tài khoản
- Tải ảnh thật làm avatar (tự cắt vuông & nén) hoặc chọn biểu tượng
- Quẹt thẻ (kéo trái/phải/lên, phím nút, hoàn tác), điểm tương hợp từ 5 thói quen + loại nhà + ưu tiên + ngân sách + sở thích + trường
- Bộ lọc chi tiết theo khu vực, ngân sách, loại nhà, ưu tiên, trường, giờ giấc, sạch sẽ, sở thích, có ảnh thật
- Match thật giữa người dùng thật; hồ sơ mẫu tự thích lại nếu đủ hợp
- Chat có "đang nhập…", gợi ý câu hỏi làm quen
- Gợi ý phòng (tài trợ/ưu tiên) khi match, đặt lịch xem
- Đặt xe chuyển đồ, dọn dẹp, mua đồ cũ; hoa hồng tính tự động
- Bảng điều khiển đối tác B2B với số liệu thật
