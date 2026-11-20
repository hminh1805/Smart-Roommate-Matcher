# Chung NhÃ  â€“ Smart Roommate Matcher

Web app tÃ¬m báº¡n cÃ¹ng phÃ²ng kiá»ƒu Tinder. Backend Python thuáº§n (khÃ´ng cáº§n cÃ i thÆ° viá»‡n) + SQLite, frontend HTML/CSS/JS thuáº§n.

## Cháº¡y trÃªn mÃ¡y
```\ncd app\npython server.py
```
Má»Ÿ http://localhost:8000

## Deploy miá»…n phÃ­ lÃªn Render (láº¥y link cÃ´ng khai)
1. ÄÆ°a thÆ° má»¥c `app` lÃªn GitHub (repo má»›i, `app` lÃ  gá»‘c repo).
2. VÃ o https://render.com â†’ New â†’ Blueprint (hoáº·c Web Service) â†’ chá»n repo.
   `render.yaml` + `Dockerfile` Ä‘Ã£ cáº¥u hÃ¬nh sáºµn, báº¥m Deploy.
3. Sau ~2 phÃºt nháº­n link dáº¡ng `https://chung-nha.onrender.com`. Má»Ÿ lÃ  dÃ¹ng, khÃ´ng cáº§n cÃ i gÃ¬.

LÆ°u Ã½: gÃ³i free ngá»§ sau 15 phÃºt khÃ´ng dÃ¹ng (láº§n má»Ÿ Ä‘áº§u chá» ~30 giÃ¢y) vÃ  dá»¯ liá»‡u SQLite Ä‘Æ°á»£c reset khi redeploy. Dá»¯ liá»‡u máº«u tá»± Ä‘Æ°á»£c táº¡o láº¡i.

## TÃ­nh nÄƒng
- ÄÄƒng kÃ½ / Ä‘Äƒng nháº­p, hoáº·c dÃ¹ng thá»­ khÃ´ng cáº§n tÃ i khoáº£n
- Quáº¹t tháº» (kÃ©o trÃ¡i/pháº£i/lÃªn, phÃ­m nÃºt, hoÃ n tÃ¡c), Ä‘iá»ƒm tÆ°Æ¡ng há»£p 5 thÃ³i quen + ngÃ¢n sÃ¡ch + sá»Ÿ thÃ­ch + trÆ°á»ng
- Match tháº­t giá»¯a ngÆ°á»i dÃ¹ng tháº­t; há»“ sÆ¡ máº«u tá»± thÃ­ch láº¡i náº¿u Ä‘á»§ há»£p
- Chat cÃ³ "Ä‘ang nháº­pâ€¦", gá»£i Ã½ cÃ¢u há»i lÃ m quen
- Gá»£i Ã½ phÃ²ng (tÃ i trá»£/Æ°u tiÃªn) khi match, Ä‘áº·t lá»‹ch xem
- Äáº·t xe chuyá»ƒn Ä‘á»“, dá»n dáº¹p, mua Ä‘á»“ cÅ©; hoa há»“ng tÃ­nh tá»± Ä‘á»™ng
- Báº£ng Ä‘iá»u khiá»ƒn Ä‘á»‘i tÃ¡c B2B vá»›i sá»‘ liá»‡u tháº­t

