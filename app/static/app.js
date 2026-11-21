/* Smart Roommate Matcher (frontend, vanilla JS) */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = n => Number(n).toLocaleString('vi-VN') + 'đ';
const shortVnd = n => n >= 1e6 ? (Math.round(n / 1e5) / 10) + 'tr' : Math.round(n / 1e3) + 'k';
const HAB = [
  { k: 'sleep', ic: '🌙', l: 'Giờ giấc', a: 'Dậy sớm', b: 'Cú đêm' },
  { k: 'tidy', ic: '🧹', l: 'Gọn gàng', a: 'Thoải mái', b: 'Rất sạch' },
  { k: 'money', ic: '💸', l: 'Sòng phẳng tiền', a: 'Dễ tính', b: 'Chia rõ ràng' },
  { k: 'noise', ic: '🔊', l: 'Độ ồn', a: 'Yên tĩnh', b: 'Sôi động' },
  { k: 'guest', ic: '👥', l: 'Đưa bạn về phòng', a: 'Hiếm khi', b: 'Thường xuyên' },
];
const EMOJIS = ['😎', '🙂', '😄', '🤓', '🥳', '😺', '🦊', '🐼', '👩‍🎓', '👨‍🎓', '👩‍💻', '👨‍💻', '👩‍🎨', '🧑‍🎤', '🧑‍🔬', '🧑‍🍳'];
const TAGS = ['🎮 Game', '📚 Chăm học', '🍳 Nấu ăn', '🏋️ Gym', '🎧 Nhạc', '🐱 Thú cưng', '🚭 Không hút thuốc', '🎬 Phim', '☕ Cà phê', '🌱 Sống xanh'];
const UNIS = ['ĐH Bách Khoa', 'ĐH Khoa học Tự nhiên', 'ĐH Kinh tế TP.HCM', 'ĐH Văn Lang', 'ĐH Ngoại thương', 'ĐH Công nghiệp', 'ĐH Sư phạm TP.HCM', 'ĐH Tôn Đức Thắng', 'ĐH FPT', 'ĐH Y Dược TP.HCM', 'ĐH Kiến trúc TP.HCM', 'Trường khác'];
const ICEBREAK = ['Bạn thường ngủ lúc mấy giờ? 🌙', 'Bạn chia tiền điện nước thế nào? 💸', 'Bạn có hay nấu ăn không? 🍳', 'Cuối tuần đi xem phòng nhé? 🏠', 'Bạn hay đưa bạn bè về phòng không? 👥'];
const HOUSES = [['tro', '🏠', 'Phòng trọ', 'Rẻ, đơn giản'], ['mini', '🏢', 'Chung cư mini', 'Tầm trung, đủ đồ'], ['chungcu', '🌆', 'Căn hộ', 'Sạch đẹp, cao cấp']];
const PRIOS = [['cheap', '💸', 'Giá rẻ', 'Tiết kiệm nhất'], ['near', '📍', 'Gần trường', 'Đi bộ được'], ['quality', '✨', 'Sạch đẹp', 'Tiện nghi tốt']];
const HNAME = Object.fromEntries(HOUSES.map(h => [h[0], h[2]])), PNAME = Object.fromEntries(PRIOS.map(p => [p[0], p[2]]));
const SVC = [['room', '🏘️', 'Phòng trọ'], ['truck', '🚚', 'Xe chuyển'], ['clean', '🧽', 'Dọn dẹp'], ['used', '🛋️', 'Đồ cũ']];
const FB_CRIT = [['r_ui', 'Giao diện & Bố cục (UI)'], ['r_ux', 'Độ mượt & Dễ dùng (UX)'], ['r_match', 'Chấm điểm 5 thói quen'], ['r_eco', 'Hệ sinh thái (Trọ · Xe · Dọn)'], ['r_overall', 'Hài lòng tổng thể']];
const FB_FEATS = ['Quẹt kiểu Tinder mượt mà', 'Chấm % & 5 ô thói quen', 'Bộ lọc 10 nhóm + Ảnh thật', 'Match + Gợi ý phòng trọ', 'Chat + Gợi ý mở lời', 'Xe chuyển · Dọn dẹp · Đồ cũ', 'Miễn phí 0đ sinh viên'];
const FB_DEV = [['mobile', '📱 Điện thoại'], ['desktop', '💻 Laptop / PC'], ['both', '📱💻 Cả hai']];
const FB_ISS = [['smooth', '✅ Chạy rất mượt'], ['lag', '🐢 Hơi lag nhẹ'], ['ui_bug', '🎨 Lỗi hiển thị'], ['func_bug', '⚙️ Lỗi chức năng']];
const FB_SHARK = [['strong', '💰 Đầu tư mạnh (≥3 tỷ)'], ['explore', '💡 Thăm dò (1–2 tỷ)'], ['consider', '🤔 Cân nhắc thêm'], ['no', '⏸️ Chưa đầu tư']];
const FB_PITCH = [['viral', '🚀 Kéo user 0đ (viral ĐH)'], ['margin', '💵 Biên lợi nhuận & đối tác'], ['safety', '🛡️ Chống nick ảo & an toàn'], ['scale', '📈 Mở rộng 6–12 tháng']];
const GFORM_URL = 'https://docs.google.com/forms/d/e/1FAIpQLScdrtJhaZqZPcbm23yuSHfcj3BnW_cLO5_iGEoHl1ubgLnuKw/viewform';
const GSHEET_URL = 'https://docs.google.com/spreadsheets/d/1yyhkIJoekoE07vBuJdx3BTPCEeSwWZqS3ysyo1geUwU/edit';

const S = { token: localStorage.getItem('rm_token'), user: null, tab: 'disc', deck: [], unis: [], filters: { min: 0, uni: '', area: '', house: '', prio: '', bud: '', tag: '', sleep: '', tidy: '', photo: '' }, last: null, history: [], passedCount: 0, deckLoading: false, busy: false, matches: [], matchesLoaded: false, unread: 0, svc: 'room', svcCache: {}, onb: null, fb: null, loaded: false };
let chatTimer = null, pollTimer = null, pollBusy = false, swipeChain = Promise.resolve(), deckReqId = 0;

/* ---------- helpers ---------- */
async function api(path, method = 'GET', body) {
  const r = await fetch('/api/' + path, { method, headers: { 'Content-Type': 'application/json', ...(S.token ? { Authorization: 'Bearer ' + S.token } : {}) }, body: body ? JSON.stringify(body) : undefined });
  let d = {}; try { d = await r.json(); } catch (e) { }
  if (r.status === 401 && S.token && !path.match(/^(login|register|guest)$/)) { logout(true); throw new Error(d.error || 'Hết phiên'); }
  if (!r.ok) throw new Error(d.error || 'Có lỗi xảy ra');
  return d;
}
function toast(t) { const e = $('#toast'); e.textContent = t; e.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.remove('show'), 2600); }
const av = (u, s = 56) => `<div class="av c${u.color || 0}" style="--s:${s}px">${u.photo ? `<img src="${esc(u.photo)}" alt="">` : esc(u.emoji)}</div>`;
const avBig = (u, s) => `<div class="av" style="background:rgba(255,255,255,.28);--s:${s}px;margin:auto">${u.photo ? `<img src="${esc(u.photo)}" alt="">` : esc(u.emoji)}</div>`;
function pickPhoto(file) {
  return new Promise((res, rej) => {
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => {
      const S_ = 480, cv = document.createElement('canvas'); cv.width = cv.height = S_;
      const m = Math.min(img.width, img.height), sx = (img.width - m) / 2, sy = (img.height - m) / 2;
      cv.getContext('2d').drawImage(img, sx, sy, m, m, 0, 0, S_, S_); URL.revokeObjectURL(url);
      res(cv.toDataURL('image/jpeg', 0.82));
    };
    img.onerror = () => rej(new Error('Không đọc được ảnh này'));
    img.src = url;
  });
}
const verdict = n => n >= 100 ? 'Giống' : n >= 75 ? 'Gần giống' : n >= 50 ? 'Hơi lệch' : 'Khác';
const level = n => n >= 80 ? 'Rất hợp' : n >= 65 ? 'Khá hợp' : n >= 50 ? 'Tạm ổn' : 'Ít hợp';
const SHORT = { sleep: 'Giờ ngủ', tidy: 'Sạch sẽ', money: 'Chi tiêu', noise: 'Độ ồn', guest: 'Khách' };
const scoreColor = n => n >= 75 ? 'var(--ok)' : n >= 50 ? 'var(--warn)' : 'var(--bad)';
function openSheet(html) { $('#sheet').innerHTML = '<div class="grab"></div>' + html; $('#sheet-wrap').classList.add('show'); $('#sheet').scrollTop = 0; }
function closeSheet() { $('#sheet-wrap').classList.remove('show'); }
$('.scrim').onclick = closeSheet;
function timeStr(t) { const d = new Date(t * 1000); return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0'); }
function confetti(n = 60) {
  const cols = ['#2BD46A', '#FF8A1F', '#FFC83D', '#3DB2FF', '#9B6BFF', '#FF4D6D', '#FFFFFF'];
  const app = $('#app');
  for (let i = 0; i < n; i++) {
    const c = document.createElement('i'); c.className = 'confetti';
    c.style.left = Math.random() * 100 + '%'; c.style.background = cols[i % cols.length];
    c.style.animationDuration = 1.6 + Math.random() * 1.8 + 's'; c.style.animationDelay = Math.random() * .5 + 's';
    app.appendChild(c); setTimeout(() => c.remove(), 4000);
  }
}
const ICONS = {
  disc: '<svg viewBox="0 0 24 24"><path d="M12 21s-7-4.5-9.3-9A5.3 5.3 0 0 1 12 6.3 5.3 5.3 0 0 1 21.3 12C19 16.500 12 21 12 21z"/></svg>',
  mat: '<svg viewBox="0 0 24 24"><path d="M21 12a8 8 0 0 1-11.7 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>',
  svc: '<svg viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5V21H3z"/><path d="M9 21v-6h6v6"/></svg>',
  me: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c1-4.200 4-6 8-6s7 1.800 8 6"/></svg>',
};

/* ---------- boot / auth ---------- */
function checkHash() {
  if (location.hash === '#feedback') openFeedback('form');
  else if (location.hash === '#stats') openFeedback('stats');
}
window.addEventListener('hashchange', checkHash);
async function boot() {
  if (S.token) { try { S.user = (await api('me')).user; } catch (e) { S.token = null; } }
  route();
  checkHash();
}
function logout(silent) {
  if (!silent && S.token) api('logout', 'POST').catch(() => { });
  localStorage.removeItem('rm_token'); S.token = null; S.user = null; S.deck = []; S.history = []; S.passedCount = 0; S.deckLoading = false; S.loaded = false; S.matches = []; S.matchesLoaded = false; S.svcCache = {};
  clearInterval(pollTimer); closeChat(); closeSheet(); route();
}
function route() {
  clearInterval(pollTimer);
  if (!S.user) return authScreen('login');
  if (!S.user.onboarded) return onboarding(true);
  shell();
}
function authScreen(mode) {
  const reg = mode === 'register';
  $('#screen').innerHTML = `<div class="auth">
    <div class="house">🏠</div>
    <div class="big">Ở chung mà<br><em>hợp cạ.</em></div>
    <p class="mu" style="font-size:14px;margin-bottom:12px">Quẹt tìm bạn cùng phòng theo thói quen sinh hoạt. Miễn phí cho sinh viên.</p>
    <div class="seg"><button class="${!reg ? 'on' : ''}" onclick="authScreen('login')">Đăng nhập</button><button class="${reg ? 'on' : ''}" onclick="authScreen('register')">Đăng ký</button></div>
    ${reg ? '<div class="field"><label>Tên hiển thị</label><input class="input" id="a_name" placeholder="VD: Minh Anh" maxlength="40"></div>' : ''}
    <div class="field"><label>Tên đăng nhập</label><input class="input" id="a_user" placeholder="chữ thường, số" autocapitalize="none" autocomplete="username"></div>
    <div class="field"><label>Mật khẩu</label><input class="input" id="a_pw" type="password" placeholder="Tối thiểu 6 ký tự" autocomplete="${reg ? 'new-password' : 'current-password'}"></div>
    <div class="err" id="a_err"></div>
    <button class="btn" id="a_go">${reg ? 'Tạo tài khoản' : 'Đăng nhập'}</button>
    <button class="btn ghost" style="margin-top:8px" id="a_guest">⚡ Dùng thử ngay, không cần đăng ký</button>
    <button class="btn sm ghost" style="margin-top:8px;align-self:center" onclick="openFeedback('form')">⭐ Đánh giá nhanh bản Demo</button>
  </div>`;
  const go = async (kind, body, btn) => {
    $('#a_err').textContent = '';
    const goBtn = $('#a_go'), gBtn = $('#a_guest'), old = btn.textContent;
    goBtn.disabled = true; gBtn.disabled = true; btn.textContent = 'Đang xử lý…';
    try { const d = await api(kind, 'POST', body); S.token = d.token; S.user = d.user; localStorage.setItem('rm_token', d.token); route(); }
    catch (e) {
      if ($('#a_err')) $('#a_err').textContent = e.message;
      goBtn.disabled = false; gBtn.disabled = false; btn.textContent = old;
    }
  };
  $('#a_go').onclick = () => go(reg ? 'register' : 'login', { username: $('#a_user').value, password: $('#a_pw').value, name: reg ? $('#a_name').value : undefined }, $('#a_go'));
  $('#a_pw').onkeydown = e => { if (e.key === 'Enter') $('#a_go').click(); };
  $('#a_guest').onclick = () => go('guest', {}, $('#a_guest'));
}

/* ---------- onboarding ---------- */
function onboarding(first, step = 0) {
  const u = S.user;
  if (!S.onb) S.onb = { name: u.name === 'Bạn mới' ? '' : u.name, emoji: u.emoji || '😎', color: u.color || 0, age: u.age || 20, gender: u.gender || 'khac', pref_gender: u.pref_gender || 'any', university: u.university || '', area: u.area || '', bio: u.bio || '', budget_min: u.budget_min || 2, budget_max: u.budget_max || 4, tags: [...(u.tags || [])], house_type: u.house_type || 'tro', priority: u.priority || 'cheap', ...u.habits };
  S.onb._first = first;
  const o = S.onb;
  const prog = `<div class="prog">${[0, 1, 2].map(i => `<i class="${i <= step ? 'on' : ''}"></i>`).join('')}</div>`;
  let body = '', next = 'Tiếp tục';
  if (step === 0) {
    body = `<h2 class="t">${first ? 'Chào mừng bạn! 👋' : 'Sửa hồ sơ'}</h2><p class="mu">Giới thiệu nhanh để mọi người biết bạn là ai.</p>
    <div class="photo-up"><div id="pu_av">${av({ emoji: o.emoji, color: o.color, photo: S.user.photo }, 92)}</div><div style="flex:1"><b>Ảnh đại diện</b><p class="mu" style="margin:2px 0 8px">Dùng ảnh thật của bạn để được tin tưởng hơn. Ảnh có mặt người sẽ nhận nhiều lượt thích hơn.</p>
    <label class="btn sm coral" style="display:inline-block;cursor:pointer">📷 ${S.user.photo ? 'Đổi ảnh' : 'Tải ảnh lên'}<input type="file" id="pu_file" accept="image/*" hidden></label>${S.user.photo ? ' <button class="btn sm ghost" id="pu_del">Xóa ảnh</button>' : ''}</div></div>
    <div class="field"><label>Hoặc chọn biểu tượng</label><div class="emojis">${EMOJIS.map(e => `<button class="${o.emoji === e ? 'sel' : ''}" data-e="${e}">${e}</button>`).join('')}</div></div>
    <div class="field"><label>Màu nền</label><div class="colors">${[0, 1, 2, 3, 4, 5, 6, 7].map(i => `<button class="c${i} ${o.color === i ? 'sel' : ''}" data-c="${i}"></button>`).join('')}</div></div>
    <div class="field"><label>Tên hiển thị</label><input class="input" id="o_name" value="${esc(o.name)}" maxlength="40" placeholder="Tên của bạn"></div>
    <div class="row field"><div class="grow"><label>Tuổi</label><input class="input" id="o_age" type="number" min="16" max="40" value="${o.age}"></div>
    <div class="grow"><label>Giới tính</label><select class="input" id="o_gender"><option value="nu" ${o.gender === 'nu' ? 'selected' : ''}>Nữ</option><option value="nam" ${o.gender === 'nam' ? 'selected' : ''}>Nam</option><option value="khac" ${o.gender === 'khac' ? 'selected' : ''}>Khác</option></select></div></div>
    <div class="field"><label>Muốn ở ghép với</label><div class="seg" id="o_pref"><button data-p="any" class="${o.pref_gender === 'any' ? 'on' : ''}">Ai cũng được</button><button data-p="same" class="${o.pref_gender === 'same' ? 'on' : ''}">Cùng giới</button></div></div>
    <div class="field"><label>Trường</label><select class="input" id="o_uni"><option value="">— Chọn trường —</option>${UNIS.map(x => `<option ${o.university === x ? 'selected' : ''}>${x}</option>`).join('')}</select></div>
    <div class="field"><label>Khu vực muốn thuê</label><input class="input" id="o_area" value="${esc(o.area)}" placeholder="VD: Bình Thạnh, Quận 10…"></div>
    <div class="field"><label>Giới thiệu bản thân</label><textarea class="input" id="o_bio" rows="3" maxlength="220" placeholder="Một vài dòng về bạn…">${esc(o.bio)}</textarea></div>`;
  } else if (step === 1) {
    body = `<h2 class="t">Thói quen sinh hoạt</h2><p class="mu">Kéo thanh trượt đúng với con người bạn. Đây là thứ quyết định độ hợp nhau.</p>
    ${HAB.map(h => `<div class="habit"><div class="hd"><div>${h.ic} ${h.l}</div><span id="hv_${h.k}">${o[h.k]}/5</span></div><input type="range" min="1" max="5" value="${o[h.k]}" data-h="${h.k}"><div class="ends"><span>${h.a}</span><span>${h.b}</span></div></div>`).join('')}`;
  } else {
    body = `<h2 class="t">Bạn muốn thuê kiểu gì?</h2><p class="mu">Hai người muốn khác nhau (một người thích chung cư sạch, một người cần trọ rẻ) rất dễ bất đồng, nên mình hỏi trước.</p>
    <div class="field"><label>Loại nhà muốn thuê</label><div class="opts" id="o_house">${HOUSES.map(([k, ic, l, d]) => `<button class="opt ${o.house_type === k ? 'sel' : ''}" data-ht="${k}"><span>${ic}</span><b>${l}</b><small>${d}</small></button>`).join('')}</div></div>
    <div class="field"><label>Điều bạn ưu tiên nhất</label><div class="opts" id="o_prio">${PRIOS.map(([k, ic, l, d]) => `<button class="opt ${o.priority === k ? 'sel' : ''}" data-pr="${k}"><span>${ic}</span><b>${l}</b><small>${d}</small></button>`).join('')}</div></div>
    <div class="habit"><div class="hd"><div>💰 Tiền thuê tối đa mỗi người / tháng</div><span id="bv">${o.budget_max} triệu</span></div>
    <input type="range" min="1" max="10" step="0.5" value="${o.budget_max}" id="bmax"><div class="ends"><span>1 triệu</span><span>10 triệu</span></div></div>
    <div class="field"><label>Sở thích & lối sống</label><div id="o_tags">${TAGS.map(t => `<button class="chip ${o.tags.includes(t) ? 'sel' : ''}" data-t="${t}" style="border:0;font-size:13px;padding:8px 12px">${t}</button>`).join('')}</div></div>`;
    next = first ? 'Bắt đầu tìm bạn 🚀' : 'Lưu thay đổi';
  }
  $('#screen').innerHTML = `${prog}<div class="view" style="padding-top:8px">${body}<div class="err" id="o_err"></div></div>
  <div class="foot">${step > 0 ? '<button class="btn ghost" id="o_back" style="width:90px">←</button>' : (!first ? '<button class="btn ghost" id="o_cancel" style="width:100px">Hủy</button>' : '')}<button class="btn coral" id="o_next">${next}</button></div>`;
  const scrape = () => {
    if (step === 0) {
    o.name = $('#o_name').value.trim(); o.age = +$('#o_age').value || 20; o.gender = $('#o_gender').value; o.university = $('#o_uni').value; o.area = $('#o_area').value.trim(); o.bio = $('#o_bio').value.trim(); }
  };
  if (step === 0) {
    $('#pu_file').onchange = async e => {
      const f = e.target.files[0]; if (!f) return; scrape();
      try { const d = await api('photo', 'POST', { data: await pickPhoto(f) }); S.user.photo = d.user.photo; toast('Đã cập nhật ảnh đại diện 📷'); onboarding(first, 0); } catch (er) { toast(er.message); }
    };
    if ($('#pu_del')) $('#pu_del').onclick = async () => { scrape(); const d = await api('photo', 'POST', { data: '' }); S.user.photo = d.user.photo; onboarding(first, 0); };
    document.querySelectorAll('[data-e]').forEach(b => b.onclick = () => {
      o.emoji = b.dataset.e;
      document.querySelectorAll('[data-e]').forEach(x => x.classList.toggle('sel', x === b));
      $('#pu_av').innerHTML = av({ emoji: o.emoji, color: o.color, photo: S.user.photo }, 92);
    });
    document.querySelectorAll('[data-c]').forEach(b => b.onclick = () => {
      o.color = +b.dataset.c;
      document.querySelectorAll('[data-c]').forEach(x => x.classList.toggle('sel', x === b));
      $('#pu_av').innerHTML = av({ emoji: o.emoji, color: o.color, photo: S.user.photo }, 92);
    });
    document.querySelectorAll('#o_pref button').forEach(b => b.onclick = () => {
      o.pref_gender = b.dataset.p;
      document.querySelectorAll('#o_pref button').forEach(x => x.classList.toggle('on', x === b));
    });
  }
  if (step === 1) document.querySelectorAll('[data-h]').forEach(r => r.oninput = () => { o[r.dataset.h] = +r.value; $('#hv_' + r.dataset.h).textContent = r.value + '/5'; });
  if (step === 2) {
    const upd = () => { const b = +$('#bmax').value; o.budget_max = b; o.budget_min = Math.max(1, b - 1.5); $('#bv').textContent = `${b} triệu`; };
    $('#bmax').oninput = upd; upd();
    document.querySelectorAll('[data-ht]').forEach(b => b.onclick = () => { o.house_type = b.dataset.ht; document.querySelectorAll('[data-ht]').forEach(x => x.classList.toggle('sel', x === b)); });
    document.querySelectorAll('[data-pr]').forEach(b => b.onclick = () => { o.priority = b.dataset.pr; document.querySelectorAll('[data-pr]').forEach(x => x.classList.toggle('sel', x === b)); });
    document.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { const t = b.dataset.t; o.tags = o.tags.includes(t) ? o.tags.filter(x => x !== t) : [...o.tags, t]; b.classList.toggle('sel'); });
  }
  if ($('#o_back')) $('#o_back').onclick = () => { scrape(); onboarding(first, step - 1); };
  if ($('#o_cancel')) $('#o_cancel').onclick = () => { S.onb = null; shell(); };
  $('#o_next').onclick = async () => {
    scrape();
    if (step === 0 && !o.name) return $('#o_err').textContent = 'Vui lòng nhập tên của bạn';
    if (step < 2) return onboarding(first, step + 1);
    const btn = $('#o_next'), old = btn.textContent;
    btn.disabled = true; btn.textContent = 'Đang lưu…';
    try {
      const d = await api('me', 'PUT', o); S.user = d.user; S.onb = null; S.deck = []; S.history = []; S.loaded = false;
      toast(first ? 'Hồ sơ đã sẵn sàng! Bắt đầu quẹt thôi 🎉' : 'Đã lưu hồ sơ'); shell(S.user.onboarded && !first ? 'me' : 'disc');
    } catch (e) { $('#o_err').textContent = e.message; btn.disabled = false; btn.textContent = old; }
  };
}

/* ---------- shell ---------- */
function shell(tab) {
  if (tab) S.tab = tab;
  $('#screen').innerHTML = `<div id="main" style="flex:1;display:flex;flex-direction:column;min-height:0"></div>
  <nav class="tabbar">${[['disc', 'Khám phá'], ['mat', 'Tin nhắn'], ['svc', 'Dịch vụ'], ['me', 'Hồ sơ']].map(([k, l]) => `<button data-t="${k}" class="${S.tab === k ? 'on' : ''}">${ICONS[k]}${l}<span class="bdg" id="bdg_${k}" style="display:none"></span></button>`).join('')}</nav>`;
  document.querySelectorAll('.tabbar button').forEach(b => b.onclick = () => switchTab(b.dataset.t));
  renderTab(); refreshUnread();
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (document.hidden || pollBusy) return;
    pollBusy = true;
    try { await refreshUnread(); } finally { pollBusy = false; }
  }, 10000);
}
function switchTab(tab) {
  if (tab === S.tab && $('#main')?.children.length) return;
  S.tab = tab;
  document.querySelectorAll('.tabbar button').forEach(b => b.classList.toggle('on', b.dataset.t === tab));
  renderTab();
}
function renderTab() { ({ disc: renderDisc, mat: renderMatches, svc: renderSvc, me: renderMe })[S.tab](); }
async function refreshUnread() {
  try {
    const d = await api('matches'); S.matches = d.matches; S.unread = d.unread; S.matchesLoaded = true;
    const b = $('#bdg_mat'); if (b) { b.style.display = d.unread ? 'grid' : 'none'; b.textContent = d.unread; }
    if (S.tab === 'mat' && !$('.page')) drawMatches();
  } catch (e) { }
}

/* ---------- discover ---------- */
async function loadDeck(resetPass = false) {
  const reqId = ++deckReqId;
  S.deckLoading = true;
  try {
    const q = filterQuery(resetPass);
    const d = await api('discover?' + q);
    if (reqId !== deckReqId) return;
    S.deck = d.candidates; S.unis = d.universities; S.areas = d.areas;
    S.passedCount = d.passed_count ?? 0; S.loaded = true;
    d.candidates.slice(0, 4).forEach(u => { if (u.photo) { const im = new Image(); im.src = u.photo; } });
  } finally {
    if (reqId === deckReqId) S.deckLoading = false;
  }
}
async function renderDisc(resetPass = false) {
  $('#main').innerHTML = `<div class="topbar"><div class="logo">🏠 Smart Roommate</div><div class="row" style="gap:6px;flex:none"><button class="filter-btn fb-btn" onclick="openFeedback('form')">⭐ Góp ý</button><button class="filter-btn" onclick="openFilters()">${FUNNEL}Bộ lọc${filterActive() ? `<span class="fb">${filterActive()}</span>` : ''}</button></div></div>
  <div class="dwrap"><div class="deck" id="deck"><div class="spin"></div></div><div class="acts" id="acts"></div></div>`;
  if (!S.loaded || resetPass) { try { await loadDeck(resetPass); } catch (e) { return toast(e.message); } }
  drawDeck();
}
function ringSvg(n) {
  const r = 28, c = 2 * Math.PI * r;
  return `<svg width="62" height="62" viewBox="0 0 62 62"><circle cx="31" cy="31" r="${r}" fill="none" stroke="var(--paper2)" stroke-width="5"/><circle cx="31" cy="31" r="${r}" fill="none" stroke="${scoreColor(n)}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - n / 100)}"/></svg>`;
}
function cardHTML(u, pos) {
  const cp = u.compat;
  return `<div class="pcard ${pos ? 's' + pos : ''}" data-id="${u.id}">
    <div class="pc-hero c${u.color}" ${u.photo ? `style="background:url('${esc(u.photo)}') center/cover"` : ''}>
      ${u.liked_kind === 'super' ? '<span class="chip super-tag pc-liked">⭐ Đã siêu thích bạn</span>' : (u.liked_you ? '<span class="chip coral pc-liked">💌 Đã thích bạn</span>' : '')}
      <div class="pc-ring">${ringSvg(cp.score)}<div><b style="color:${scoreColor(cp.score)}">${cp.score}%</b><small>${level(cp.score).toUpperCase()}</small></div></div>
      ${u.photo ? '' : `<div class="pc-emoji">${esc(u.emoji)}</div>`}
      <div class="stamp like">HỢP CẠ</div><div class="stamp nope">BỎ QUA</div><div class="stamp super">SIÊU THÍCH</div>
    </div>
    <div class="pc-body">
      <h3>${esc(u.name)} <span>${u.age}</span></h3>
      <div class="pc-meta">🎓 ${esc(u.university || 'Chưa cập nhật')}${u.area ? ' · 📍 ' + esc(u.area) : ''}</div>
      <div>${[[`💰 Tối đa ${u.budget_max} tr`, 'coin'], [(HOUSES.find(h => h[0] === u.house_type) || [])[1] + ' ' + HNAME[u.house_type], 'sky'], ['⭐ ' + PNAME[u.priority], 'grape']].map(([t, cls]) => `<span class="chip ${cls}">${esc(t)}</span>`).join('')}</div>
      <div>${u.tags.slice(0, 2).map(t => `<span class="chip${cp.shared_tags.includes(t) ? ' ok' : ''}">${esc(t)}</span>`).join('')}</div>
      <div class="pc-bio">${esc(u.bio)}</div>
      <div class="minis">${cp.habits.map(h => `<div class="mini">${HAB.find(x => x.k === h.key).ic}<small style="color:var(--mu)">${SHORT[h.key]}</small><small style="color:${scoreColor(h.sim)}">${verdict(h.sim)}</small><i style="width:${h.sim}%;background:${scoreColor(h.sim)}"></i></div>`).join('')}</div>
    </div></div>`;
}
function drawDeck() {
  const deck = $('#deck'); if (!deck) return;
  if (!S.deck.length) {
    if (S.deckLoading) { deck.innerHTML = '<div class="spin"></div>'; return; }
    if (filterActive() && !S.passedCount) {
      deck.innerHTML = `<div class="empty"><div class="em">🔍</div><h2 class="t">Chưa có hồ sơ khớp bộ lọc</h2><p class="mu">Không tìm thấy bạn nào đạt đủ các tiêu chí đang lọc. Bạn thử nới độ hợp tối thiểu hoặc bớt tiêu chí lọc nhé.</p><br>
      <button class="btn" onclick="openFilters()">🎛️ Chỉnh lại bộ lọc</button><button class="btn ghost" style="margin-top:10px" onclick="S.filters={...FDEF};S.loaded=false;renderDisc(true)">✕ Xóa bộ lọc</button></div>`;
    } else {
      deck.innerHTML = `<div class="empty"><div class="em">🎉</div><h2 class="t">Bạn đã xem hết rồi!</h2><p class="mu">Quay lại sau để gặp thêm bạn mới, hoặc xem lại những người đã bỏ qua.</p><br>
      <button class="btn" onclick="resetPassed()">↺ Xem lại người đã bỏ qua</button>${filterActive() ? '<button class="btn ghost" style="margin-top:10px" onclick="S.filters={...FDEF};S.loaded=false;renderDisc(true)">Xóa bộ lọc</button>' : ''}</div>`;
    }
    $('#acts').innerHTML = ''; return;
  }
  deck.innerHTML = S.deck.slice(0, 3).map((u, i) => cardHTML(u, i)).reverse().join('');
  const sl = S.user?.super_left ?? 3;
  $('#acts').innerHTML = `<button class="a-undo" onclick="undoSwipe()" title="Hoàn tác">↺</button><button class="a-no" onclick="flyTop('pass')" title="Bỏ qua"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button><button class="a-like" onclick="flyTop('like')" title="Thích">💚</button><button class="a-super ${sl ? '' : 'dim'}" onclick="flyTop('super')" title="Siêu thích (còn ${sl}/ngày)">⭐<span class="scnt">${sl}</span></button>`;
  bindDrag(deck.lastElementChild);
}
function topCard() { const d = $('#deck'); return d && [...d.querySelectorAll('.pcard:not(.flying)')].pop(); }
function syncActs() {
  const sl = S.user?.super_left ?? 3, sb = $('#acts .a-super'), sc = $('#acts .scnt');
  if (sb) { sb.classList.toggle('dim', sl <= 0); sb.title = `Siêu thích (còn ${sl}/ngày)`; }
  if (sc) sc.textContent = sl;
}
function bindDrag(el) {
  let sx, sy, dx = 0, dy = 0, on = false, moved = 0, raf = 0;
  const st = { like: el.querySelector('.stamp.like'), nope: el.querySelector('.stamp.nope'), sup: el.querySelector('.stamp.super') };
  el.onpointerdown = e => { on = true; moved = 0; dx = 0; dy = 0; sx = e.clientX; sy = e.clientY; el.style.transition = 'none'; el.setPointerCapture(e.pointerId); };
  el.onpointermove = e => {
    if (!on) return; dx = e.clientX - sx; dy = e.clientY - sy; moved = Math.max(moved, Math.abs(dx) + Math.abs(dy));
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      if (!on) return;
      el.style.transform = `translate(${dx}px,${dy}px) rotate(${dx / 16}deg)`;
      const up = dy < -40 && Math.abs(dx) < 80;
      st.like.style.opacity = up ? 0 : Math.min(1, dx / 90); st.nope.style.opacity = up ? 0 : Math.min(1, -dx / 90); st.sup.style.opacity = up ? Math.min(1, -dy / 90) : 0;
      const nx = el.previousElementSibling; if (nx) { const p = Math.min(1, Math.hypot(dx, dy) / 150); nx.style.transition = 'none'; nx.style.transform = `scale(${.95 + .05 * p}) translateY(${10 - 10 * p}px)`; }
    });
  };
  el.onpointerup = () => {
    if (!on) return; on = false;
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    if (moved < 6) { el.style.transition = ''; return openDetail(S.deck[0]); }
    if (dx > 100) return fly('like', dx, dy); if (dx < -100) return fly('pass', dx, dy); if (dy < -110) return fly('super', dx, dy);
    el.style.transition = 'transform .28s cubic-bezier(.2,1.4,.4,1)'; el.style.transform = ''; Object.values(st).forEach(s => s.style.opacity = 0);
    const nx = el.previousElementSibling; if (nx) { nx.style.transition = 'transform .28s ease'; nx.style.transform = ''; }
    dx = dy = 0;
  };
  el.onpointercancel = () => {
    if (!on) return; on = false;
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    el.style.transition = 'transform .28s ease'; el.style.transform = ''; Object.values(st).forEach(s => s.style.opacity = 0);
    const nx = el.previousElementSibling; if (nx) { nx.style.transition = 'transform .28s ease'; nx.style.transform = ''; }
    dx = dy = 0;
  };
}
function flyTop(kind) { if (!topCard()) return; fly(kind, 0, 0); }
function fly(kind, dx, dy) {
  const el = topCard(); if (!el) return;
  if (kind === 'super' && (S.user?.super_left ?? 3) <= 0) {
    el.style.transition = 'transform .28s cubic-bezier(.2,1.4,.4,1)'; el.style.transform = ''; el.querySelectorAll('.stamp').forEach(s => s.style.opacity = 0);
    return toast('Hôm nay bạn đã dùng hết 3 lượt Siêu thích ⭐');
  }
  const u = S.deck.shift(); S.last = u;
  S.history.push({ user: u, kind }); if (S.history.length > 10) S.history.shift();
  if (kind === 'pass') S.passedCount = (S.passedCount || 0) + 1;
  if (S.user?.counts) S.user.counts.swiped++;
  if (kind === 'super' && S.user) { S.user.super_left = Math.max(0, (S.user.super_left ?? 3) - 1); syncActs(); }
  el.classList.add('flying'); el.style.pointerEvents = 'none';
  const tx = kind === 'like' ? 520 : kind === 'pass' ? -520 : dx * 2, ty = kind === 'super' ? -700 : dy + 60;
  el.style.transition = 'transform .32s cubic-bezier(.2,.8,.3,1), opacity .32s'; el.style.opacity = 0;
  el.style.transform = `translate(${tx}px,${ty}px) rotate(${kind === 'like' ? 22 : kind === 'pass' ? -22 : 0}deg)`;
  const st = el.querySelector('.stamp.' + (kind === 'like' ? 'like' : kind === 'pass' ? 'nope' : 'super')); if (st) st.style.opacity = 1;
  setTimeout(() => el.remove(), 330);

  const deck = $('#deck');
  const next = el.previousElementSibling;
  if (next && !next.classList.contains('flying')) {
    next.classList.remove('s1', 's2');
    next.style.transition = 'transform .25s cubic-bezier(.2,.9,.3,1), opacity .25s';
    next.style.transform = '';
    bindDrag(next);
    const third = next.previousElementSibling;
    if (third) { third.classList.remove('s2'); third.classList.add('s1'); }
    if (S.deck[2]) deck.insertAdjacentHTML('afterbegin', cardHTML(S.deck[2], 2));
  } else if (!S.deck.length) {
    setTimeout(() => { if (S.tab === 'disc' && !S.deck.length && !S.deckLoading) drawDeck(); }, 220);
  }
  swipeChain = swipeChain.then(() => commitSwipe(u, kind)).catch(() => {});
}
async function commitSwipe(u, kind) {
  try {
    const d = await api('swipe', 'POST', { to: u.id, kind });
    if (d.super_left !== undefined && S.user) { S.user.super_left = d.super_left; syncActs(); }
    if (d.matched) {
      S.last = null;
      S.history = S.history.filter(x => x.user.id !== u.id);
      S.matches = [d.match, ...S.matches.filter(m => m.id !== d.match.id)];
      S.matchesLoaded = true;
      if (d.new && S.user?.counts) S.user.counts.matches++;
      if (S.tab === 'disc' && !$('#chatpage') && !$('.matchov')) showMatch(d.match);
      else toast('🎉 Hợp cạ với ' + d.match.user.name + '! Xem ở tab Tin nhắn');
      refreshUnread();
    } else if (kind !== 'pass') toast(d.note || 'Đã gửi lượt thích 💚');
  } catch (e) { toast(e.message); }
  if (!S.deck.length) {
    try { await loadDeck(); } catch (e) { }
    if (S.tab === 'disc' && !topCard()) drawDeck();
  }
}
async function undoSwipe() {
  if (S.history.length) {
    ++deckReqId;
    const item = S.history.pop();
    if (!S.deck.some(x => x.id === item.user.id)) S.deck.unshift(item.user);
    if (S.user?.counts) S.user.counts.swiped = Math.max(0, S.user.counts.swiped - 1);
    if (item.kind === 'super' && S.user) S.user.super_left = Math.min(3, (S.user.super_left ?? 0) + 1);
    if (item.kind === 'pass') S.passedCount = Math.max(0, (S.passedCount || 1) - 1);
    drawDeck();
    const top = topCard();
    if (top && top.animate) top.animate([{ transform: 'translateX(-36px) scale(.95)', opacity: .55 }, { transform: 'none', opacity: 1 }], { duration: 170, easing: 'cubic-bezier(.2,1.3,.4,1)' });
    toast('Đã hoàn tác ↺');
    swipeChain = swipeChain.then(async () => {
      try {
        const d = await api('undo', 'POST');
        if (d.super_left !== undefined && S.user) { S.user.super_left = d.super_left; syncActs(); }
      } catch (e) {
        S.deck = S.deck.filter(x => x.id !== item.user.id);
        if (S.tab === 'disc') drawDeck();
        toast(e.message);
      }
    });
    return;
  }
  if (S.busy) return;
  S.busy = true;
  ++deckReqId;
  swipeChain = swipeChain.then(async () => {
    try {
      const d = await api('undo', 'POST');
      if (S.user?.counts) S.user.counts.swiped = Math.max(0, S.user.counts.swiped - 1);
      if (d.super_left !== undefined && S.user) S.user.super_left = d.super_left;
      if (!S.deck.some(x => x.id === d.user.id)) S.deck.unshift(d.user);
      if (S.tab === 'disc') drawDeck();
      toast('Đã hoàn tác ↺');
    } catch (e) { toast(e.message); }
    finally { S.busy = false; }
  });
}
async function resetPassed() {
  S.history = S.history.filter(x => x.kind !== 'pass');
  await swipeChain.catch(() => {});
  await api('reset-swipes', 'POST'); S.loaded = false; renderDisc();
}
const FDEF = { min: 0, uni: '', area: '', house: '', prio: '', bud: '', tag: '', sleep: '', tidy: '', photo: '' };
const BUDS = { a: ['Dưới 3 triệu', 0, 3], b: ['3 – 4 triệu', 3, 4], c: ['4 – 5 triệu', 4, 5], d: ['Trên 5 triệu', 5, 99] };
const filterActive = () => Object.keys(FDEF).filter(k => S.filters[k] && S.filters[k] !== FDEF[k]).length;
function filterQuery(resetPass = false) {
  const f = S.filters, q = new URLSearchParams();
  ['min', 'uni', 'area', 'house', 'prio', 'tag', 'sleep', 'tidy', 'photo'].forEach(k => { if (f[k]) q.set(k, f[k]); });
  if (f.bud) { q.set('blo', BUDS[f.bud][1]); q.set('bhi', BUDS[f.bud][2]); }
  if (resetPass) q.set('reset_pass', '1');
  return q.toString();
}
const FUNNEL = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h18l-7 8v6l-4 2v-8z"/></svg>';
function openFilters() {
  const F = { ...FDEF, ...S.filters };
  const grp = (key, label, opts) => `<div class="field"><label>${label}</label><div class="fgrp" data-g="${key}">${opts.map(([v, t]) => `<button class="chip fchip ${F[key] === v ? 'sel' : ''}" data-v="${esc(v)}">${esc(t)}</button>`).join('')}</div></div>`;
  openSheet(`<div class="row"><h2 class="t" style="flex:1">Bộ lọc</h2><button class="btn sm ghost" id="f_clear">Xóa hết</button></div>
  <div class="habit"><div class="hd"><div>Độ hợp tối thiểu</div><span id="fv">${F.min ? F.min + '%' : 'Tất cả'}</span></div><input type="range" min="0" max="90" step="10" value="${F.min}" id="f_min"></div>
  ${grp('area', '📍 Khu vực muốn thuê', (S.areas || []).map(a => [a, a]))}
  ${grp('bud', '💰 Tiền thuê tối đa của họ', Object.entries(BUDS).map(([k, v]) => [k, v[0]]))}
  ${grp('house', '🏠 Loại nhà', HOUSES.map(h => [h[0], h[1] + ' ' + h[2]]))}
  ${grp('prio', '⭐ Họ ưu tiên', PRIOS.map(p => [p[0], p[1] + ' ' + p[2]]))}
  ${grp('uni', '🎓 Trường', (S.unis || []).map(u => [u, u]))}
  ${grp('sleep', '🌙 Giờ giấc', [['early', 'Ngủ sớm, dậy sớm'], ['late', 'Cú đêm']])}
  ${grp('tidy', '🧹 Sạch sẽ', [['high', 'Người gọn gàng']])}
  ${grp('tag', '🎯 Sở thích', TAGS.map(t => [t, t]))}
  ${grp('photo', '📷 Hồ sơ', [['1', 'Chỉ người có ảnh thật']])}
  <div class="fstick"><button class="btn" id="f_ok">Áp dụng</button></div>`);
  $('#f_min').oninput = e => { F.min = +e.target.value; $('#fv').textContent = F.min ? F.min + '%' : 'Tất cả'; };
  document.querySelectorAll('.fgrp').forEach(g => g.querySelectorAll('.fchip').forEach(b => b.onclick = () => {
    const k = g.dataset.g, v = b.dataset.v; F[k] = F[k] === v ? '' : v;
    g.querySelectorAll('.fchip').forEach(x => x.classList.toggle('sel', x.dataset.v === F[k]));
  }));
  $('#f_clear').onclick = () => { S.filters = { ...FDEF }; S.history = S.history.filter(x => x.kind !== 'pass'); S.loaded = false; closeSheet(); renderDisc(true); };
  $('#f_ok').onclick = () => { S.filters = F; S.history = S.history.filter(x => x.kind !== 'pass'); S.loaded = false; closeSheet(); renderDisc(true); };
}
function openDetail(u, actions = true) {
  if (!u) return; const cp = u.compat;
  openSheet(`<div class="dhero c${u.color}">${avBig(u, 64).replace('margin:auto', 'margin:0')}<div><div style="font-family:var(--display);font-size:24px;font-weight:800">${esc(u.name)}, ${u.age}</div><div style="font-size:13px;opacity:.9">🎓 ${esc(u.university)}<br>📍 ${esc(u.area || 'Chưa rõ')} · 💰 Tối đa ${u.budget_max} tr</div></div></div>
  <div class="row"><div class="grow"><span class="mu">Mức hợp nhau · ${level(cp.score)}</span><div style="font-family:var(--display);font-size:38px;font-weight:800;color:${scoreColor(cp.score)}">${cp.score}%</div></div><div class="grow" style="text-align:right"><span class="mu">Ngân sách thuê</span><div style="font-family:var(--display);font-size:20px;font-weight:800">${cp.budget >= 60 ? 'Khớp nhau' : cp.budget >= 25 ? 'Hơi lệch' : 'Lệch nhiều'}</div></div></div>
  <p style="font-size:14px;line-height:1.5;margin:10px 0">${esc(u.bio)}</p><div>${u.tags.map(t => `<span class="chip${cp.shared_tags.includes(t) ? ' ok' : ''}">${esc(t)}</span>`).join('')}</div>
  <h3 class="t">So sánh thói quen</h3><div class="legend"><span><i style="background:var(--moss)"></i>Bạn</span><span><i style="background:var(--coral)"></i>${esc(u.name.split(' ').pop())}</span></div>
  ${cp.habits.map(h => { const m = HAB.find(x => x.k === h.key); return `<div class="cmp"><div class="l"><span>${m.ic} ${m.l}</span><span style="color:${scoreColor(h.sim)}">${verdict(h.sim)}</span></div><div class="tr"><div class="dt me" style="left:${(h.me - 1) * 25}%"></div><div class="dt th" style="left:${(h.them - 1) * 25}%"></div></div><div class="ends" style="display:flex;justify-content:space-between;font-size:10px;color:var(--mu);margin-top:6px"><span>${m.a}</span><span>${m.b}</span></div></div>`; }).join('')}
  <h3 class="t">🏘️ Nhu cầu thuê nhà</h3><div class="card" style="padding:0 14px">${[['💰 Tiền thuê tối đa', S.user.budget_max + ' triệu', u.budget_max + ' triệu', Math.abs(S.user.budget_max - u.budget_max) <= 0.5 ? 100 : Math.abs(S.user.budget_max - u.budget_max) <= 1.5 ? 75 : 25], ['🏠 Loại nhà', HNAME[S.user.house_type], HNAME[u.house_type], S.user.house_type === u.house_type ? 100 : 50], ['⭐ Ưu tiên', PNAME[S.user.priority], PNAME[u.priority], S.user.priority === u.priority ? 100 : 50]].map(([l, a, b, s]) => `<div class="ordr" style="align-items:center"><div><b>${l}</b><div class="mu">Bạn: ${esc(a)} · ${esc(u.name.split(' ').pop())}: ${esc(b)}</div></div><b style="color:${scoreColor(s)};white-space:nowrap">${s === 100 ? 'Giống' : s >= 75 ? 'Gần giống' : s >= 50 ? 'Hơi lệch' : 'Lệch'}</b></div>`).join('')}</div>
  <h3 class="t">💡 Gợi ý từ hệ thống</h3>${cp.insights.map(i => `<div class="insight"><span>•</span><span>${esc(i)}</span></div>`).join('') || '<p class="mu">Hai bạn khá trung tính, hãy trò chuyện thêm nhé.</p>'}
  ${actions ? '<div class="row" style="margin-top:18px"><button class="btn ghost" onclick="closeSheet();flyTop(\'pass\')">✕ Bỏ qua</button><button class="btn coral" onclick="closeSheet();flyTop(\'like\')">💚 Thích</button></div>' : '<button class="btn ghost" style="margin-top:18px" onclick="closeSheet()">Đóng</button>'}`);
}

/* ---------- match overlay ---------- */
function showMatch(m) {
  const me = S.user, u = m.user;
  const el = document.createElement('div'); el.className = 'matchov';
  el.innerHTML = `<div style="text-align:center"><span class="match-pill">⭐ ${level(m.score).toUpperCase()} · ${m.score}%</span></div><h1>Hợp cạ rồi!</h1>
  <div class="pair">${av(me, 96)}<div class="heart">💚</div>${av(u, 96)}</div>
  <p style="text-align:center;opacity:.92;font-size:14px;font-weight:700;line-height:1.5;margin-bottom:8px">Bạn và <b>${esc(u.name)}</b> đã thích nhau.<br>${esc(u.compat.insights[0] || 'Hãy nhắn tin làm quen nhé!')}</p>
  <div style="font-weight:800;margin:10px 0 4px">🏘️ Gợi ý phòng cho hai bạn</div>
  <div class="rscroll">${(m.rooms || []).map(r => `<div class="rcard"><div>${r.sponsored ? '<span class="chip ad">Tài trợ</span>' : ''}${r.near_you ? '<span class="chip ok">Gần trường</span>' : ''}</div>
    <div style="font-weight:800;margin:4px 0;font-size:14.5px">${r.emoji} ${esc(r.name)}</div><div class="mu">📍 ${esc(r.district)} · ${r.dist}</div>
    <div class="price" style="margin:6px 0 2px">${fmt(r.price)}<span class="mu">/tháng</span></div><div class="mu">≈ ${fmt(Math.round(r.price / 2))}/người</div>
    <button class="btn sm coral" style="width:100%;margin-top:auto;padding-top:8px" data-room="${r.id}">Đặt lịch xem</button></div>`).join('')}</div>
  <div style="flex:1"></div>
  <button class="btn" id="m_chat">💬 Nhắn tin cho ${esc(u.name.split(' ').pop())}</button>
  <button class="btn ghost" id="m_go" style="margin-top:10px;background:rgba(255,255,255,.12);color:#fff;border-color:rgba(255,255,255,.55);box-shadow:0 3px 0 rgba(0,0,0,.35)">Tiếp tục quẹt</button>`;
  $('#overlay').appendChild(el); confetti(80);
  el.querySelectorAll('[data-room]').forEach(b => b.onclick = () => bookSheet('room', m.rooms.find(r => r.id == b.dataset.room)));
  $('#m_go').onclick = () => { el.remove(); if (S.tab === 'disc') drawDeck(); };
  $('#m_chat').onclick = () => { el.remove(); openChat(m.id); };
}

/* ---------- matches & chat ---------- */
function drawMatches() {
  const el = $('#mlist'); if (!el) return;
  const ms = S.matches;
  if (!ms.length) { el.innerHTML = `<div class="empty"><div class="em">💌</div><h2 class="t">Chưa có match nào</h2><p class="mu">Sang tab Khám phá và thả tim vài bạn. Bạn nào hợp thói quen sẽ match ngay!</p><br><button class="btn" onclick="switchTab('disc')">Đi quẹt thôi</button></div>`; return; }
  el.innerHTML = `<h3 class="t" style="margin-top:4px">Match mới</h3><div class="nm">${ms.map(m => `<button onclick="openChat(${m.id})">${av(m.user, 62)}${esc(m.user.name.split(' ').pop())}</button>`).join('')}</div>
  <h3 class="t" style="margin-top:4px">Cuộc trò chuyện</h3>${ms.map(m => `<div class="conv ${m.unread ? 'unread' : ''}" onclick="openChat(${m.id})">${av(m.user, 54)}<div class="grow" style="flex:1;min-width:0"><b>${esc(m.user.name)}</b> <span class="chip ok" style="margin:0 0 0 4px">${m.score}%</span><div class="lm">${m.last ? (m.last.mine ? 'Bạn: ' : '') + esc(m.last.text) : 'Nói xin chào đi nào 👋'}</div></div>${m.unread ? `<div class="ub">${m.unread}</div>` : ''}</div>`).join('')}`;
}
async function renderMatches() {
  $('#main').innerHTML = `<div class="topbar"><div class="logo">Tin nhắn</div></div><div class="view" id="mlist">${S.matchesLoaded ? '' : '<div class="spin"></div>'}</div>`;
  if (S.matchesLoaded) drawMatches();
  loadMatches();
}
async function loadMatches() {
  try {
    const d = await api('matches'); S.matches = d.matches; S.unread = d.unread; S.matchesLoaded = true;
    const b = $('#bdg_mat'); if (b) { b.style.display = d.unread ? 'grid' : 'none'; b.textContent = d.unread; }
    if (S.tab === 'mat') drawMatches();
  } catch (e) { }
}
async function openChat(id) {
  closeChat();
  const mt = S.matches.find(m => m.id === id) || (await api('matches')).matches.find(m => m.id === id); if (!mt) return;
  const page = document.createElement('div'); page.className = 'page'; page.id = 'chatpage';
  page.innerHTML = `<div class="page-h"><button class="back" id="c_back">←</button>${av(mt.user, 42)}<div style="flex:1;min-width:0"><b>${esc(mt.user.name)}</b><div class="mu" id="c_sub">${esc(mt.user.university)}</div></div><button class="icon-btn" id="c_more">⋯</button></div>
  <div class="msgs" id="msgs"></div><div class="ice" id="ice">${ICEBREAK.map(t => `<button>${t}</button>`).join('')}</div>
  <div class="composer"><input class="input" id="c_in" placeholder="Nhập tin nhắn…" maxlength="1000" autocomplete="off"><button class="send" id="c_send">➤</button></div>`;
  $('#overlay').appendChild(page);
  let last = 0, chatBusy = false, chatPromise = null;
  const seen = new Set();
  const msgs = $('#msgs');
  const poll = async (force = false) => {
    if (!$('#msgs')) return;
    if (!force && document.hidden) return;
    if (chatBusy) {
      if (!force) return;
      await chatPromise;
      if (!$('#msgs')) return;
    }
    chatBusy = true;
    chatPromise = (async () => {
      try {
        const d = await api(`matches/${id}/messages?after=${last}`);
        if (!$('#msgs')) return;
        const wasBottom = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 80;
        msgs.querySelector('.typing')?.remove();
        if (d.messages.length) msgs.querySelectorAll('.msg.pending.sent').forEach(x => x.remove());
        let added = false;
        d.messages.forEach(m => {
          if (seen.has(m.id)) return;
          seen.add(m.id);
          added = true;
          const e = document.createElement('div'); e.className = 'msg' + (m.mine ? ' me' : ''); e.innerHTML = `${esc(m.text)}<time>${timeStr(m.at)}</time>`; msgs.appendChild(e);
        });
        if (typeof d.cursor === 'number') last = d.cursor;
        else if (d.messages.length) last = Math.max(last, d.messages[d.messages.length - 1].id);
        if (d.messages.length) $('#ice') && d.messages.some(m => m.mine) && $('#ice').remove();
        if (d.typing) { msgs.insertAdjacentHTML('beforeend', '<div class="typing"><i></i><i></i><i></i></div>'); $('#c_sub').textContent = 'đang nhập…'; } else $('#c_sub').textContent = mt.user.university;
        if (added || d.typing) if (wasBottom || last <= d.messages[0]?.id) msgs.scrollTop = msgs.scrollHeight;
      } catch (e) { }
    })();
    try { await chatPromise; } finally { chatBusy = false; chatPromise = null; }
  };
  const send = async (text) => {
    text = (text || $('#c_in').value).trim(); if (!text) return;
    $('#c_in').value = '';
    $('#ice')?.remove();
    const pend = document.createElement('div');
    pend.className = 'msg me pending';
    pend.innerHTML = `${esc(text)}<time>Đang gửi…</time>`;
    msgs.appendChild(pend);
    msgs.scrollTop = msgs.scrollHeight;
    try {
      await api(`matches/${id}/messages`, 'POST', { text });
      pend.classList.add('sent');
      await poll(true);
      msgs.scrollTop = msgs.scrollHeight;
      setTimeout(() => poll(), 1600);
    } catch (e) {
      pend.remove();
      toast(e.message);
    }
  };
  $('#c_send').onclick = () => send(); $('#c_in').onkeydown = e => { if (e.key === 'Enter') send(); };
  $('#ice').querySelectorAll('button').forEach(b => b.onclick = () => { send(b.textContent); });
  $('#c_back').onclick = () => { closeChat(); refreshUnread(); if (S.tab === 'mat') drawMatches(); };
  $('#c_more').onclick = () => {
    openSheet(`<h2 class="t">${esc(mt.user.name)}</h2>
      <button class="btn" id="cm_rooms">🏘️ Xem phòng gợi ý cho 2 bạn</button>
      <button class="btn ghost" style="margin-top:10px" id="cm_detail">👤 Xem độ hợp chi tiết</button>
      <button class="btn ghost" style="margin-top:10px;color:var(--bad)" id="unm">Hủy match</button>`);
    $('#cm_rooms').onclick = () => { closeSheet(); showRoomsFor(id); };
    $('#cm_detail').onclick = () => { closeSheet(); openDetail(mt.user, false); };
    $('#unm').onclick = async () => {
      if (!confirm('Hủy match với ' + mt.user.name + '?')) return;
      try {
        await api(`matches/${id}/unmatch`, 'POST');
        closeSheet(); closeChat(); S.loaded = false;
        if (S.user?.counts) S.user.counts.matches = Math.max(0, S.user.counts.matches - 1);
        await loadMatches();
      } catch (e) { toast(e.message); }
    };
  };
  await poll(true); msgs.scrollTop = msgs.scrollHeight;
  chatTimer = setInterval(() => poll(), 2500);
}
function closeChat() { clearInterval(chatTimer); const p = $('#chatpage'); if (p) p.remove(); }
async function showRoomsFor(id) {
  openSheet(`<h2 class="t">Phòng gợi ý cho 2 bạn</h2><div class="spin"></div>`);
  try {
    const d = await api(`matches/${id}/rooms`);
    if (!$('#sheet-wrap').classList.contains('show')) return;
    $('#sheet').innerHTML = `<div class="grab"></div><h2 class="t">Phòng gợi ý cho 2 bạn</h2><p class="mu" style="margin-bottom:10px">Xếp theo ngân sách chung và khoảng cách tới trường.</p>${d.rooms.map(r => roomCard(r)).join('')}`;
    bindBook(d.rooms);
  } catch (e) { closeSheet(); toast(e.message); }
}

/* ---------- services ---------- */
function roomCard(r) {
  return `<div class="ticket"><div class="tk-left ${r.sponsored ? 'tk-coin' : 'tk-grape'}"><div class="tk-ic">${r.emoji}</div><div class="tk-val">${shortVnd(Math.round(r.price / 2))}</div><div class="tk-unit">/người</div></div>
  <div class="tk-right"><div>${r.sponsored ? '<span class="chip ad">Tài trợ</span>' : ''}${r.near_you ? '<span class="chip ok">Gần trường</span>' : ''}</div>
  <div class="tk-title">${esc(r.name)}</div><div class="mu">📍 ${esc(r.district)} · cách trường ${r.dist} · ${esc(r.owner)}</div>
  <p class="mu" style="margin:2px 0">${esc(r.desc)}</p><div>${r.amenities.map(a => `<span class="chip">${esc(a)}</span>`).join('')}</div>
  <div class="row" style="margin-top:4px"><div class="grow"><div class="price">${fmt(r.price)}<span class="mu">/tháng</span></div>${r.fits === false ? '<div class="mu" style="color:var(--red7)">⚠️ Vượt ngân sách</div>' : ''}</div><button class="btn sm coral" data-book="${r.id}">Đặt lịch xem</button></div></div></div>`;
}
function svcCard(s) {
  const k = s.kind || S.svc;
  const tone = k === 'truck' ? 'tk-orange' : k === 'clean' ? 'tk-sky' : 'tk-green';
  return `<div class="ticket"><div class="tk-left ${tone}"><div class="tk-ic">${s.emoji}</div><div class="tk-val">${shortVnd(s.price)}</div><div class="tk-unit">${s.unit === 'từ' ? 'giá từ' : '/' + esc(s.unit)}</div></div>
  <div class="tk-right">${s.promoted ? '<div><span class="chip ad">Ưu tiên hiển thị</span></div>' : ''}<div class="tk-title">${esc(s.name)}</div><div class="stars">★ ${s.rating} <span class="mu">· ${s.jobs} lượt</span></div>
  <p class="mu" style="margin:2px 0">${esc(s.desc)}</p><div class="row" style="margin-top:4px"><div class="grow price">${s.unit === 'từ' ? 'Từ ' : ''}${fmt(s.price)}<span class="mu">${s.unit === 'từ' ? '' : '/' + s.unit}</span></div><button class="btn sm" data-book="${s.id}">Đặt ngay</button></div></div></div>`;
}
function bindBook(items, kind) {
  document.querySelectorAll('[data-book]').forEach(b => b.onclick = () => { const it = items.find(x => x.id == b.dataset.book); bookSheet(it.kind || kind, it); });
}
async function renderSvc() {
  $('#main').innerHTML = `<div class="topbar"><div class="logo">Hệ sinh thái</div></div><div class="view"><p class="mu" style="margin-bottom:10px">Mọi thứ cho một lần chuyển nhà trọn gói.</p>
  <div class="seg">${SVC.map(([k, ic, l]) => `<button class="${S.svc === k ? 'on' : ''}" data-s="${k}">${ic} ${l}</button>`).join('')}</div><div id="slist" style="margin-top:14px"><div class="spin"></div></div></div>`;
  document.querySelectorAll('[data-s]').forEach(b => b.onclick = () => { S.svc = b.dataset.s; renderSvc(); });
  const drawSvc = (kind, items) => {
    if (S.tab !== 'svc' || S.svc !== kind || !$('#slist')) return;
    if (kind === 'room') { $('#slist').innerHTML = items.map(roomCard).join(''); bindBook(items); }
    else { $('#slist').innerHTML = items.map(svcCard).join(''); bindBook(items, kind); }
  };
  const kind = S.svc;
  if (S.svcCache[kind]) return drawSvc(kind, S.svcCache[kind]);
  try {
    const d = kind === 'room' ? await api('rooms') : await api('services?kind=' + kind);
    const items = kind === 'room' ? d.rooms : d.services;
    S.svcCache[kind] = items;
    drawSvc(kind, items);
  } catch (e) { toast(e.message); }
}
function bookSheet(kind, it) {
  const t = new Date(Date.now() + 864e5).toISOString().slice(0, 10);
  const room = kind === 'room';
  openSheet(`<h2 class="t">${room ? 'Đặt lịch xem phòng' : 'Xác nhận đặt dịch vụ'}</h2><div class="card row"><div class="svc" style="flex:1"><div class="ic">${it.emoji}</div><div><b>${esc(it.name)}</b><div class="price">${fmt(it.price)}</div></div></div></div>
  <div class="field"><label>${room ? 'Ngày xem phòng' : 'Ngày thực hiện'}</label><input class="input" id="b_date" type="date" value="${t}" min="${t}"></div>
  <div class="field"><label>Ghi chú</label><textarea class="input" id="b_note" rows="2" placeholder="${room ? 'VD: Mình và bạn cùng phòng sẽ đi chung' : 'VD: Địa chỉ lấy đồ, số lượng đồ…'}"></textarea></div>
  <p class="mu" style="margin:10px 0">${room ? 'Miễn phí xem phòng. Chủ trọ sẽ liên hệ xác nhận lịch.' : 'Thanh toán trực tiếp cho đối tác sau khi hoàn thành.'}</p>
  <button class="btn coral" id="b_ok">Xác nhận</button>`);
  $('#b_ok').onclick = async () => {
    $('#b_ok').disabled = true; $('#b_ok').textContent = 'Đang gửi…';
    try { await api('orders', 'POST', { kind: it.kind || kind, item_id: it.id, date: $('#b_date').value, note: $('#b_note').value }); closeSheet(); confetti(40); toast('✅ Đã gửi yêu cầu! Xem trong Hồ sơ → Đơn của tôi'); if (S.user) S.user.counts.orders++; }
    catch (e) { toast(e.message); $('#b_ok').disabled = false; $('#b_ok').textContent = 'Xác nhận'; }
  };
}

/* ---------- profile ---------- */
function radar(h) {
  const n = HAB.length, R = 72, cx = 110, cy = 108;
  const pt = (i, v) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return [cx + Math.cos(a) * R * v / 5, cy + Math.sin(a) * R * v / 5]; };
  const grid = [1, 2, 3, 4, 5].map(v => `<polygon points="${HAB.map((_, i) => pt(i, v).join(',')).join(' ')}" fill="none" stroke="#D5C4A1" stroke-width="1.5"/>`).join('');
  const poly = HAB.map((x, i) => pt(i, h[x.k]).join(',')).join(' ');
  const labels = HAB.map((x, i) => { const [px, py] = pt(i, 6.2); return `<text x="${px}" y="${py + 5}" text-anchor="middle" font-size="15">${x.ic}</text>`; }).join('');
  return `<svg viewBox="0 0 220 205" style="width:100%;max-width:260px;display:block;margin:auto">${grid}<polygon points="${poly}" fill="rgba(43,212,106,.32)" stroke="#1B1A3A" stroke-width="2.5" stroke-linejoin="round"/>${HAB.map((x, i) => { const [px, py] = pt(i, h[x.k]); return `<circle cx="${px}" cy="${py}" r="4.5" fill="#FF8A1F" stroke="#1B1A3A" stroke-width="1.8"/>`; }).join('')}${labels}</svg>`;
}
function drawMe() {
  const u = S.user; if (!u || S.tab !== 'me') return;
  const prevScroll = $('#meview')?.scrollTop || 0;
  $('#main').innerHTML = `<div class="view" id="meview" style="padding-top:14px">
  <div class="phero c${u.color}">${avBig(u, 96)}<h2>${esc(u.name)}, ${u.age}</h2><div style="font-size:13px;font-weight:700;opacity:.92">🎓 ${esc(u.university || 'Chưa chọn trường')} · 📍 ${esc(u.area || '—')}</div>
  ${u.guest ? '<div style="margin-top:8px;font-size:12px;font-weight:800;background:rgba(27,26,58,.45);border:2px solid rgba(255,255,255,.7);border-radius:999px;padding:5px 12px;display:inline-block">Tài khoản dùng thử</div>' : ''}</div>
  <div class="statrow"><div class="stat"><b id="me_swiped">${u.counts.swiped}</b><span>Đã quẹt</span></div><div class="stat"><b id="me_matches">${u.counts.matches}</b><span>Match</span></div><div class="stat"><b id="me_liked">${u.liked_me}</b><span>Thích bạn</span></div></div>
  <div class="card"><b>Chân dung sinh hoạt</b>${radar(u.habits)}<div style="margin-top:6px">${u.tags.map(t => `<span class="chip">${esc(t)}</span>`).join('')}</div><p class="mu" style="margin-top:6px">💰 Tiền thuê tối đa ${u.budget_max} triệu/người/tháng · ${HNAME[u.house_type]} · ưu tiên ${PNAME[u.priority].toLowerCase()}</p></div>
  <button class="btn" onclick="S.onb=null;onboarding(false,0)">✏️ Chỉnh sửa hồ sơ & thói quen</button>
  <button class="btn ghost" style="margin-top:10px" onclick="openOrders()">🧾 Đơn của tôi (<span id="me_orders">${u.counts.orders}</span>)</button>
  <button class="btn coin" style="margin-top:10px" onclick="openFeedback('form')">📝 Đánh giá & Thống kê khảo sát</button>
  <button class="btn grape" style="margin-top:10px" onclick="openPartner()">📊 Bảng điều khiển đối tác (B2B)</button>
  <button class="btn ghost" style="margin-top:10px;color:var(--bad)" onclick="logout()">Đăng xuất</button><div style="height:10px"></div></div>`;
  if (prevScroll && $('#meview')) $('#meview').scrollTop = prevScroll;
}
async function renderMe() {
  drawMe();
  try {
    const d = await api('me'); S.user = d.user;
    if (S.tab !== 'me') return;
    if ($('#meview')) {
      if ($('#me_swiped')) $('#me_swiped').textContent = S.user.counts.swiped;
      if ($('#me_matches')) $('#me_matches').textContent = S.user.counts.matches;
      if ($('#me_liked')) $('#me_liked').textContent = S.user.liked_me;
      if ($('#me_orders')) $('#me_orders').textContent = S.user.counts.orders;
    } else drawMe();
  } catch (e) { }
}
async function openOrders() {
  openSheet(`<h2 class="t">Đơn của tôi</h2><div class="spin"></div>`);
  try {
    const d = await api('orders');
    if (!$('#sheet-wrap').classList.contains('show')) return;
    $('#sheet').innerHTML = `<div class="grab"></div><h2 class="t">Đơn của tôi</h2>${d.orders.length ? d.orders.map(o => `<div class="ordr"><div><b>${esc(o.name)}</b><div class="mu">📅 ${esc(o.date || '—')} · ${esc(o.status)}${o.note ? '<br>“' + esc(o.note) + '”' : ''}</div></div><div class="price" style="font-size:14px;white-space:nowrap">${fmt(o.amount)}</div></div>`).join('') : '<p class="mu" style="padding:20px 0">Bạn chưa đặt dịch vụ nào. Qua tab Dịch vụ để đặt xe, dọn phòng hoặc xem trọ nhé.</p>'}`;
  } catch (e) { closeSheet(); toast(e.message); }
}
async function openPartner() {
  openSheet(`<h2 class="t">Bảng điều khiển đối tác</h2><div class="spin"></div>`);
  try {
    const s = await api('stats');
    if (!$('#sheet-wrap').classList.contains('show')) return;
    const kinds = { room: 'Xem phòng', truck: 'Xe chuyển', clean: 'Dọn dẹp', used: 'Đồ cũ' };
    const mx = Math.max(1, ...Object.values(s.by_kind).map(k => k.commission));
    $('#sheet').innerHTML = `<div class="grab"></div><h2 class="t">Bảng điều khiển đối tác</h2><p class="mu">Số liệu thật từ toàn bộ người dùng, minh họa mô hình doanh thu B2B của nền tảng.</p>
    <div class="kpi"><div class="stat"><b>${s.users}</b><span>Người dùng</span></div><div class="stat"><b>${s.matches}</b><span>Cặp match</span></div>
    <div class="stat"><b>${s.impressions}</b><span>Lượt hiển thị phòng tài trợ</span></div><div class="stat"><b>${s.orders}</b><span>Đơn dịch vụ / xem phòng</span></div>
    <div class="stat"><b style="font-size:17px">${fmt(s.sponsor_revenue)}</b><span>Phí quảng cáo chủ trọ (2.000đ/lượt)</span></div><div class="stat"><b style="font-size:17px">${fmt(s.commission)}</b><span>Hoa hồng (10–15%)</span></div></div>
    <h3 class="t">Hoa hồng theo dịch vụ</h3><div class="bars">${Object.entries(kinds).map(([k, l]) => { const v = (s.by_kind[k] || { commission: 0, orders: 0 }); return `<div class="br"><span>${l}</span><div><i style="width:${v.commission / mx * 100}%"></i></div><b>${fmt(v.commission)}</b></div>`; }).join('')}</div>
    <h3 class="t">Phòng được xem nhiều nhất</h3>${s.top_rooms.map(r => `<div class="ordr"><span>${esc(r.name)}</span><b>${r.views} lượt</b></div>`).join('') || '<p class="mu">Chưa có dữ liệu.</p>'}
    <h3 class="t">Doanh thu ước tính</h3><div class="card" style="text-align:center"><div class="price" style="font-size:28px">${fmt(s.sponsor_revenue + s.commission)}</div><div class="mu">Phí hiển thị + hoa hồng</div></div>`;
  } catch (e) { closeSheet(); toast(e.message); }
}

async function openFeedback(tab = 'form') {
  if (!S.fb) S.fb = {
    tester_name: S.user && S.user.name && S.user.name !== 'Bạn mới' ? S.user.name : '',
    device: window.innerWidth < 520 ? 'mobile' : 'desktop',
    r_ui: 5, r_ux: 5, r_match: 5, r_eco: 5, r_overall: 5,
    fav_features: [], issue_type: 'smooth', shark_invest: 'explore', pitch_closer: '', suggestion: '',
  };
  const header = `<div class="row" style="margin-bottom:8px"><h2 class="t" style="flex:1">Đánh giá trải nghiệm</h2><button class="btn sm ghost" onclick="closeSheet()">✕</button></div>
  <div class="seg" style="margin-bottom:12px"><button class="${tab === 'form' ? 'on' : ''}" data-fbt="form">📝 Gửi đánh giá</button><button class="${tab === 'stats' ? 'on' : ''}" data-fbt="stats">📊 Thống kê</button></div>`;
  const bindTabs = () => document.querySelectorAll('[data-fbt]').forEach(b => b.onclick = () => {
    if ($('#fb_name')) S.fb.tester_name = $('#fb_name').value;
    if ($('#fb_sug')) S.fb.suggestion = $('#fb_sug').value;
    openFeedback(b.dataset.fbt);
  });

  if (tab === 'form') {
    const f = S.fb;
    openSheet(`${header}<p class="mu">Khảo sát nhanh (~45 giây) — kết quả tự động đồng bộ về Google Form & bảng Excel của nhóm. <a href="${GFORM_URL}" target="_blank" rel="noopener" style="color:#1565C0;font-weight:800;text-decoration:underline">📋 Hoặc mở trực tiếp Google Forms ↗</a></p>
    <div class="field"><label>Tên của bạn (không bắt buộc)</label><input class="input" id="fb_name" value="${esc(f.tester_name)}" maxlength="40" placeholder="VD: Minh Quân (hoặc để trống)"></div>
    <div class="field"><label>Bạn đang test trên thiết bị nào?</label><div class="seg" id="fb_dev">${FB_DEV.map(([k, l]) => `<button data-v="${k}" class="${f.device === k ? 'on' : ''}">${l}</button>`).join('')}</div></div>
    <div class="field"><label>Chấm điểm trải nghiệm Web App (1 → 5 sao)</label><div class="card" style="padding:4px 12px">${FB_CRIT.map(([k, l]) => `<div class="star-row"><div class="star-lbl">${l}</div><div class="stars-pick" data-sk="${k}">${[1, 2, 3, 4, 5].map(n => `<button data-sv="${n}" class="${n <= f[k] ? 'on' : ''}">★</button>`).join('')}</div></div>`).join('')}</div></div>
    <div class="field"><label>Điểm bạn thích nhất khi dùng thử? (chọn ít nhất 1)</label><div class="fgrp" id="fb_fav">${FB_FEATS.map(t => `<button class="chip fchip ${f.fav_features.includes(t) ? 'sel' : ''}" data-v="${esc(t)}">${esc(t)}</button>`).join('')}</div></div>
    <div class="field"><label>Trải nghiệm kỹ thuật thực tế</label><div class="fgrp" id="fb_iss">${FB_ISS.map(([k, l]) => `<button class="chip fchip ${f.issue_type === k ? 'sel' : ''}" data-v="${k}">${l}</button>`).join('')}</div></div>
    <div class="field"><label>Góc nhìn "Shark" (giả sử bạn cầm 10 tỷ ảo)</label><p class="mu" style="margin-bottom:6px">Mức độ sẵn sàng rót vốn cho sản phẩm này ở thời điểm hiện tại?</p><div class="fgrp" id="fb_shk">${FB_SHARK.map(([k, l]) => `<button class="chip fchip ${f.shark_invest === k ? 'sel' : ''}" data-v="${k}">${l}</button>`).join('')}</div></div>
    <div class="field"><label>Nếu có 1 câu chốt khiến bạn muốn xuống tiền mạnh hơn khi nhóm pitch? (không bắt buộc)</label><div class="fgrp" id="fb_pitch">${FB_PITCH.map(([k, l]) => `<button class="chip fchip ${f.pitch_closer === k ? 'sel' : ''}" data-v="${k}">${l}</button>`).join('')}</div></div>
    <div class="field"><label>💡 Đề xuất & Cải tiến</label><textarea class="input" id="fb_sug" rows="3" maxlength="600" placeholder="Điểm nào còn bất tiện hoặc bạn muốn nhóm sửa/bổ sung thêm gì?">${esc(f.suggestion)}</textarea></div>
    <div class="fstick"><button class="btn" id="fb_go">🚀 Gửi đánh giá ngay</button></div>`);
    bindTabs();
    $('#fb_name').oninput = e => { f.tester_name = e.target.value; };
    $('#fb_sug').oninput = e => { f.suggestion = e.target.value; };
    document.querySelectorAll('#fb_dev button').forEach(b => b.onclick = () => { f.device = b.dataset.v; document.querySelectorAll('#fb_dev button').forEach(x => x.classList.toggle('on', x === b)); });
    document.querySelectorAll('.stars-pick').forEach(g => g.querySelectorAll('button').forEach(b => b.onclick = () => {
      const k = g.dataset.sk, v = +b.dataset.sv; f[k] = v;
      g.querySelectorAll('button').forEach(x => x.classList.toggle('on', +x.dataset.sv <= v));
    }));
    document.querySelectorAll('#fb_fav .fchip').forEach(b => b.onclick = () => {
      const v = b.dataset.v; f.fav_features = f.fav_features.includes(v) ? f.fav_features.filter(x => x !== v) : [...f.fav_features, v];
      b.classList.toggle('sel');
    });
    document.querySelectorAll('#fb_iss .fchip').forEach(b => b.onclick = () => { f.issue_type = b.dataset.v; document.querySelectorAll('#fb_iss .fchip').forEach(x => x.classList.toggle('sel', x === b)); });
    document.querySelectorAll('#fb_shk .fchip').forEach(b => b.onclick = () => { f.shark_invest = b.dataset.v; document.querySelectorAll('#fb_shk .fchip').forEach(x => x.classList.toggle('sel', x === b)); });
    document.querySelectorAll('#fb_pitch .fchip').forEach(b => b.onclick = () => {
      const v = b.dataset.v; f.pitch_closer = f.pitch_closer === v ? '' : v;
      document.querySelectorAll('#fb_pitch .fchip').forEach(x => x.classList.toggle('sel', x.dataset.v === f.pitch_closer));
    });
    $('#fb_go').onclick = async () => {
      if (!f.fav_features.length) { toast('Chọn ít nhất 1 điểm bạn thích nhất nhé ⭐'); return; }
      const btn = $('#fb_go'); btn.disabled = true; btn.textContent = 'Đang gửi…';
      try {
        const res = await api('feedback', 'POST', f);
        S.fb = null; confetti(45);
        toast(res.synced_to_google ? 'Đã gửi & đồng bộ Google Form + Excel! 🎉' : 'Cảm ơn bạn đã góp ý! 🎉');
        openFeedback('stats');
      } catch (e) { toast(e.message); btn.disabled = false; btn.textContent = '🚀 Gửi đánh giá ngay'; }
    };
    return;
  }

  openSheet(`${header}<div class="spin"></div>`);
  bindTabs();
  try {
    const d = await api('feedback');
    if (!$('#sheet-wrap').classList.contains('show')) return;
    const avgKeys = [['ui', 'Giao diện (UI)'], ['ux', 'Độ mượt (UX)'], ['match', '5 thói quen'], ['eco', 'Hệ sinh thái'], ['overall', 'Tổng thể']];
    const devLbl = Object.fromEntries(FB_DEV), issLbl = Object.fromEntries(FB_ISS), shkLbl = Object.fromEntries(FB_SHARK);
    const mxFeat = Math.max(1, ...(d.top_features || []).map(x => x.count));
    const formLink = d.gform_url || GFORM_URL;
    const sheetLink = d.gsheet_url || GSHEET_URL;
    $('#sheet').innerHTML = `<div class="grab"></div>${header}
    ${d.source === 'google_sheet' ? '<p class="mu" style="margin-bottom:8px;font-size:12px">🔄 Dữ liệu đồng bộ trực tiếp từ Google Form & Google Sheet của nhóm.</p>' : ''}
    <div class="kpi">
      <div class="stat"><b>${d.total}</b><span>Lượt đánh giá</span></div>
      <div class="stat"><b>${d.total ? d.averages.overall + '/5' : '—'}</b><span>Điểm tổng thể</span></div>
      <div class="stat"><b>${d.invest_ready_pct}%</b><span>Sẵn sàng rót vốn</span></div>
      <div class="stat"><b>${d.smooth_pct}%</b><span>Chạy rất mượt</span></div>
    </div>
    <a class="btn coin" href="/api/feedback.xlsx" download="smart-roommate-feedback.xlsx">⬇️ Tải file Excel (.xlsx) từ Google Sheet</a>
    <div class="row" style="margin-top:8px;gap:8px">
      <a class="btn sm ghost grow" href="${esc(sheetLink)}" target="_blank" rel="noopener" style="text-align:center">📊 Mở Google Sheet ↗</a>
      <button class="btn sm ghost grow" id="fb_copy">📋 Copy link Google Form</button>
    </div>
    <h3 class="t">Điểm trung bình 5 tiêu chí</h3>
    <div class="bars fb-bars">${avgKeys.map(([k, l]) => { const v = d.averages[k] || 0; return `<div class="br"><span>${l}</span><div><i style="width:${v / 5 * 100}%"></i></div><b>${v}/5</b></div>`; }).join('')}</div>
    <h3 class="t">Tâm lý "Shark" (10 tỷ ảo)</h3>
    <div class="bars fb-bars">${FB_SHARK.map(([k, l]) => { const v = d.by_shark[k] || 0; return `<div class="br"><span>${l}</span><div><i style="width:${d.total ? v / d.total * 100 : 0}%"></i></div><b>${v}</b></div>`; }).join('')}</div>
    <h3 class="t">Tính năng được thích nhất</h3>
    <div class="bars fb-bars">${d.top_features.length ? d.top_features.map(x => `<div class="br"><span>${esc(x.name)}</span><div><i style="width:${x.count / mxFeat * 100}%"></i></div><b>${x.count}</b></div>`).join('') : '<p class="mu">Chưa có dữ liệu.</p>'}</div>
    <h3 class="t">Đề xuất & Cải tiến mới nhất</h3>
    ${d.items.length ? d.items.map(it => `<div class="fb-item"><div class="row"><b class="grow">${esc(it.tester_name)}</b><span class="chip coin">${it.r_overall}★</span><span class="chip sky">${esc(devLbl[it.device] || it.device)}</span></div><div><span class="chip ok">${esc(issLbl[it.issue_type] || it.issue_type)}</span><span class="chip grape">${esc(shkLbl[it.shark_invest] || it.shark_invest)}</span></div>${it.suggestion ? `<p>“${esc(it.suggestion)}”</p>` : '<p class="mu" style="font-style:italic">Không ghi đề xuất thêm</p>'}</div>`).join('') : '<p class="mu">Chưa có lượt đánh giá nào. Gửi link #feedback để nhóm bạn trải nghiệm nhé!</p>'}`;
    bindTabs();
    $('#fb_copy').onclick = async () => {
      try { await navigator.clipboard.writeText(formLink); toast('Đã copy link Google Form!'); } catch (e) { toast(formLink); }
    };
  } catch (e) { toast(e.message); }
}
boot();
