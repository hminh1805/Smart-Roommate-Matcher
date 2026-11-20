# Chung Nhà – Smart Roommate Matcher

Web app tìm bạn cùng phòng kiểu Tinder. Backend Python thuần (không cần cài thư viện) + SQLite, frontend HTML/CSS/JS thuần.

## Chạy trên máy
```
python server.py
```
Mở http://localhost:8000

## Deploy miễn phí lên Render (lấy link công khai)
1. Đưa thư mục `app` lên GitHub (repo mới, `app` là gốc repo).
2. Vào https://render.com → New → Blueprint (hoặc Web Service) → chọn repo.
   `render.yaml` + `Dockerfile` đã cấu hình sẵn, bấm Deploy.
3. Sau ~2 phút nhận link dạng `https://chung-nha.onrender.com`. Mở là dùng, không cần cài gì.

Lưu ý: gói free ngủ sau 15 phút không dùng (lần mở đầu chờ ~30 giây) và dữ liệu SQLite được reset khi redeploy. Dữ liệu mẫu tự được tạo lại.

## Tính năng
- Đăng ký / đăng nhập, hoặc dùng thử không cần tài khoản
- Quẹt thẻ (kéo trái/phải/lên, phím nút, hoàn tác), điểm tương hợp 5 thói quen + ngân sách + sở thích + trường
- Match thật giữa người dùng thật; hồ sơ mẫu tự thích lại nếu đủ hợp
- Chat có "đang nhập…", gợi ý câu hỏi làm quen
- Gợi ý phòng (tài trợ/ưu tiên) khi match, đặt lịch xem
- Đặt xe chuyển đồ, dọn dẹp, mua đồ cũ; hoa hồng tính tự động
- Bảng điều khiển đối tác B2B với số liệu thật
