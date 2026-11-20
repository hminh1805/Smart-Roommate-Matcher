/* Chung Nhà – Smart Roommate Matcher (frontend, vanilla JS) */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = n => Number(n).toLocaleString('vi-VN') + 'đ';
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

const S = { token: localStorage.getItem('rm_token'), user: null, tab: 'disc', deck: [], unis: [], filters: { min: 0, uni: '' }, last: null, busy: false, matches: [], unread: 0, svc: 'room', onb: null, loaded: false };
let chatTimer = null, pollTimer = null;

/* ---------- helpers ---------- */
async function api(path, method = 'GET', body) {
  const r = await fetch('/api/' + path, { method, headers: { 'Content-Type': 'application/json', ...(S.token ? { Authorization: 'Bearer ' + S.token } : {}) }, body: body ? JSON.stringify(body) : undefined });
  let d = {}; try { d = await r.json(); } catch (e) { }
  if (r.status === 401 && S.token && !path.match(/^(login|register|guest)$/)) { logout(true); throw new Error(d.error || 'Hết phiên'); }
  if (!r.ok) throw new Error(d.error || 'Có lỗi xảy ra');
  return d;
}
function toast(t) { const e = $('#toast'); e.textContent = t; e.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.remove('show'), 2600); }
const av = (u, s = 56) => `<div class="av c${u.color || 0}" style="--s:${s}px">${esc(u.emoji)}</div>`;
const verdict = n => n >= 100 ? 'Giống' : n >= 75 ? 'Gần giống' : n >= 50 ? 'Hơi lệch' : 'Khác';
const level = n => n >= 80 ? 'Rất hợp' : n >= 65 ? 'Khá hợp' : n >= 50 ? 'Tạm ổn' : 'Ít hợp';
const SHORT = { sleep: 'Giờ ngủ', tidy: 'Sạch sẽ', money: 'Chi tiêu', noise: 'Độ ồn', guest: 'Khách' };
const scoreColor = n => n >= 75 ? 'var(--ok)' : n >= 50 ? 'var(--warn)' : 'var(--bad)';
function openSheet(html) { $('#sheet').innerHTML = '<div class="grab"></div>' + html; $('#sheet-wrap').classList.add('show'); $('#sheet').scrollTop = 0; }
function closeSheet() { $('#sheet-wrap').classList.remove('show'); }
$('.scrim').onclick = closeSheet;
function timeStr(t) { const d = new Date(t * 1000); return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0'); }
function confetti(n = 60) {
  const cols = ['#F2603A', '#F6B73C', '#2C7A69', '#F29BB5', '#8EC5F2', '#fff'];
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
async function boot() {
  if (S.token) { try { S.user = (await api('me')).user; } catch (e) { S.token = null; } }
  route();
}
function logout(silent) {
  if (!silent && S.token) api('logout', 'POST').catch(() => { });
  localStorage.removeItem('rm_token'); S.token = null; S.user = null; S.deck = []; S.loaded = false; S.matches = [];
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
    <button class="btn ghost" style="margin-top:10px" id="a_guest">⚡ Dùng thử ngay, không cần đăng ký</button>
  </div>`;
  const go = async (kind, body) => {
    $('#a_err').textContent = '';
    try { const d = await api(kind, 'POST', body); S.token = d.token; S.user = d.user; localStorage.setItem('rm_token', d.token); route(); }
    catch (e) { $('#a_err') && ($('#a_err').textContent = e.message); }
  };
  $('#a_go').onclick = () => go(reg ? 'register' : 'login', { username: $('#a_user').value, password: $('#a_pw').value, name: reg ? $('#a_name').value : undefined });
  $('#a_pw').onkeydown = e => { if (e.key === 'Enter') $('#a_go').click(); };
  $('#a_guest').onclick = () => go('guest', {});
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
    <div class="field"><label>Chọn avatar</label><div class="emojis">${EMOJIS.map(e => `<button class="${o.emoji === e ? 'sel' : ''}" data-e="${e}">${e}</button>`).join('')}</div></div>
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
    next = first ? 'Bắt đầu tìm bạn cùng phòng 🚀' : 'Lưu thay đổi';
  }
  $('#screen').innerHTML = `${prog}<div class="view" style="padding-top:8px">${body}<div class="err" id="o_err"></div></div>
  <div class="foot">${step > 0 ? '<button class="btn ghost" id="o_back" style="width:90px">←</button>' : (!first ? '<button class="btn ghost" id="o_cancel" style="width:100px">Hủy</button>' : '')}<button class="btn coral" id="o_next">${next}</button></div>`;
  const scrape = () => {
    if (step === 0) { o.name = $('#o_name').value.trim(); o.age = +$('#o_age').value || 20; o.gender = $('#o_gender').value; o.university = $('#o_uni').value; o.area = $('#o_area').value.trim(); o.bio = $('#o_bio').value.trim(); }
  };
  if (step === 0) {
    document.querySelectorAll('[data-e]').forEach(b => b.onclick = () => { scrape(); o.emoji = b.dataset.e; onboarding(first, 0); });
    document.querySelectorAll('[data-c]').forEach(b => b.onclick = () => { scrape(); o.color = +b.dataset.c; onboarding(first, 0); });
    document.querySelectorAll('#o_pref button').forEach(b => b.onclick = () => { scrape(); o.pref_gender = b.dataset.p; onboarding(first, 0); });
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
    try {
      const d = await api('me', 'PUT', o); S.user = d.user; S.onb = null; S.deck = []; S.loaded = false;
      toast(first ? 'Hồ sơ đã sẵn sàng! Bắt đầu quẹt thôi 🎉' : 'Đã lưu hồ sơ'); shell(S.user.onboarded && !first ? 'me' : 'disc');
    } catch (e) { $('#o_err').textContent = e.message; }
  };
}

/* ---------- shell ---------- */
function shell(tab) {
  if (tab) S.tab = tab;
  $('#screen').innerHTML = `<div id="main" style="flex:1;display:flex;flex-direction:column;min-height:0"></div>
  <nav class="tabbar">${[['disc', 'Khám phá'], ['mat', 'Tin nhắn'], ['svc', 'Dịch vụ'], ['me', 'Hồ sơ']].map(([k, l]) => `<button data-t="${k}" class="${S.tab === k ? 'on' : ''}">${ICONS[k]}${l}<span class="bdg" id="bdg_${k}" style="display:none"></span></button>`).join('')}</nav>`;
  document.querySelectorAll('.tabbar button').forEach(b => b.onclick = () => { S.tab = b.dataset.t; shell(); });
  renderTab(); refreshUnread();
  clearInterval(pollTimer); pollTimer = setInterval(() => { refreshUnread(); if (S.tab === 'mat' && !$('.page')) loadMatches(true); }, 5000);
}
function renderTab() { ({ disc: renderDisc, mat: renderMatches, svc: renderSvc, me: renderMe })[S.tab](); }
async function refreshUnread() {
  try {
    const d = await api('matches'); S.matches = d.matches; S.unread = d.unread;
    const b = $('#bdg_mat'); if (b) { b.style.display = d.unread ? 'grid' : 'none'; b.textContent = d.unread; }
  } catch (e) { }
}

/* ---------- discover ---------- */
async function loadDeck() {
  const q = new URLSearchParams({ min: S.filters.min, uni: S.filters.uni });
  const d = await api('discover?' + q); S.deck = d.candidates; S.unis = d.universities; S.loaded = true;
}
async function renderDisc() {
  $('#main').innerHTML = `<div class="topbar"><div class="logo">🏠 Chung Nhà</div><div class="row" style="gap:8px"><button class="icon-btn" onclick="openFilters()" title="Bộ lọc">⚙️${S.filters.min || S.filters.uni ? '<span class="dot">•</span>' : ''}</button></div></div>
  <div class="dwrap"><div class="deck" id="deck"><div class="spin"></div></div><div class="acts" id="acts"></div></div>`;
  if (!S.loaded) { try { await loadDeck(); } catch (e) { return toast(e.message); } }
  drawDeck();
}
function ringSvg(n) {
  const r = 28, c = 2 * Math.PI * r;
  return `<svg width="62" height="62" viewBox="0 0 62 62"><circle cx="31" cy="31" r="${r}" fill="none" stroke="var(--paper2)" stroke-width="5"/><circle cx="31" cy="31" r="${r}" fill="none" stroke="${scoreColor(n)}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - n / 100)}"/></svg>`;
}
function cardHTML(u, pos) {
  const cp = u.compat;
  return `<div class="pcard ${pos ? 's' + pos : ''}" data-id="${u.id}">
    <div class="pc-hero c${u.color}">
      ${u.liked_you ? '<span class="chip coral pc-liked">💌 Đã thích bạn</span>' : ''}
      <div class="pc-ring">${ringSvg(cp.score)}<div><b style="color:${scoreColor(cp.score)}">${cp.score}%</b><small>${level(cp.score).toUpperCase()}</small></div></div>
      <div class="pc-emoji">${esc(u.emoji)}</div>
      <div class="stamp like">HỢP CẠ</div><div class="stamp nope">BỎ QUA</div><div class="stamp super">SIÊU THÍCH</div>
    </div>
    <div class="pc-body">
      <h3>${esc(u.name)} <span>${u.age}</span></h3>
      <div class="pc-meta">🎓 ${esc(u.university || 'Chưa cập nhật')}${u.area ? ' · 📍 ' + esc(u.area) : ''}</div>
      <div>${[`💰 Tối đa ${u.budget_max} tr`, (HOUSES.find(h => h[0] === u.house_type) || [])[1] + ' ' + HNAME[u.house_type], '⭐ ' + PNAME[u.priority]].map(t => `<span class="chip" style="background:var(--moss);color:#fff">${esc(t)}</span>`).join('')}</div>
      <div>${u.tags.slice(0, 2).map(t => `<span class="chip${cp.shared_tags.includes(t) ? ' ok' : ''}">${esc(t)}</span>`).join('')}</div>
      <div class="pc-bio">${esc(u.bio)}</div>
      <div class="minis">${cp.habits.map(h => `<div class="mini">${HAB.find(x => x.k === h.key).ic}<small style="color:var(--mu)">${SHORT[h.key]}</small><small style="color:${scoreColor(h.sim)}">${verdict(h.sim)}</small><i style="width:${h.sim}%;background:${scoreColor(h.sim)}"></i></div>`).join('')}</div>
    </div></div>`;
}
function drawDeck() {
  const deck = $('#deck'); if (!deck) return;
  if (!S.deck.length) {
    deck.innerHTML = `<div class="empty"><div class="em">🎉</div><h2 class="t">Bạn đã xem hết rồi!</h2><p class="mu">Quay lại sau để gặp thêm bạn mới, hoặc xem lại những người đã bỏ qua.</p><br>
    <button class="btn" onclick="resetPassed()">↺ Xem lại người đã bỏ qua</button>${S.filters.min || S.filters.uni ? '<button class="btn ghost" style="margin-top:10px" onclick="S.filters={min:0,uni:\'\'};S.loaded=false;renderDisc()">Xóa bộ lọc</button>' : ''}</div>`;
    $('#acts').innerHTML = ''; return;
  }
  deck.innerHTML = S.deck.slice(0, 3).map((u, i) => cardHTML(u, i)).reverse().join('');
  $('#acts').innerHTML = `<button class="a-undo" onclick="undoSwipe()" title="Hoàn tác">↺</button><button class="a-no" onclick="flyTop('pass')"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button><button class="a-super" onclick="flyTop('super')" title="Siêu thích">⭐</button><button class="a-like" onclick="flyTop('like')">💚</button>`;
  bindDrag(deck.lastElementChild);
}
function topCard() { const d = $('#deck'); return d && d.querySelector('.pcard:last-child'); }
function bindDrag(el) {
  let sx, sy, dx = 0, dy = 0, on = false, moved = 0;
  const st = { like: el.querySelector('.stamp.like'), nope: el.querySelector('.stamp.nope'), sup: el.querySelector('.stamp.super') };
  el.onpointerdown = e => { on = true; moved = 0; sx = e.clientX; sy = e.clientY; el.style.transition = 'none'; el.setPointerCapture(e.pointerId); };
  el.onpointermove = e => {
    if (!on) return; dx = e.clientX - sx; dy = e.clientY - sy; moved = Math.max(moved, Math.abs(dx) + Math.abs(dy));
    el.style.transform = `translate(${dx}px,${dy}px) rotate(${dx / 16}deg)`;
    const up = dy < -40 && Math.abs(dx) < 80;
    st.like.style.opacity = up ? 0 : Math.min(1, dx / 90); st.nope.style.opacity = up ? 0 : Math.min(1, -dx / 90); st.sup.style.opacity = up ? Math.min(1, -dy / 90) : 0;
    const nx = el.previousElementSibling; if (nx) { const p = Math.min(1, Math.hypot(dx, dy) / 150); nx.style.transform = `scale(${.95 + .05 * p}) translateY(${14 - 14 * p}px)`; }
  };
  el.onpointerup = () => {
    if (!on) return; on = false;
    if (moved < 6) { el.style.transition = ''; return openDetail(S.deck[0]); }
    if (dx > 110) return fly('like', dx, dy); if (dx < -110) return fly('pass', dx, dy); if (dy < -120) return fly('super', dx, dy);
    el.style.transition = 'transform .3s cubic-bezier(.2,1.4,.4,1)'; el.style.transform = ''; Object.values(st).forEach(s => s.style.opacity = 0);
    const nx = el.previousElementSibling; if (nx) nx.style.transform = '';
    dx = dy = 0;
  };
}
function flyTop(kind) { if (S.busy || !topCard()) return; fly(kind, 0, 0); }
function fly(kind, dx, dy) {
  if (S.busy) return; S.busy = true; const el = topCard();
  const tx = kind === 'like' ? 520 : kind === 'pass' ? -520 : dx * 2, ty = kind === 'super' ? -700 : dy + 60;
  el.style.transition = 'transform .38s cubic-bezier(.4,0,.8,.6),opacity .38s'; el.style.opacity = 0.2;
  el.style.transform = `translate(${tx}px,${ty}px) rotate(${kind === 'like' ? 24 : kind === 'pass' ? -24 : 0}deg)`;
  const st = el.querySelector('.stamp.' + (kind === 'like' ? 'like' : kind === 'pass' ? 'nope' : 'super')); if (st) st.style.opacity = 1;
  setTimeout(() => commitSwipe(kind), 300);
}
async function commitSwipe(kind) {
  const u = S.deck.shift(); S.last = u;
  try {
    const d = await api('swipe', 'POST', { to: u.id, kind });
    if (d.matched) { S.last = null; refreshUnread(); showMatch(d.match); }
    else if (kind !== 'pass') toast(d.note || 'Đã gửi lượt thích 💚');
  } catch (e) { toast(e.message); }
  S.busy = false;
  if (!S.deck.length) { try { await loadDeck(); } catch (e) { } }
  if (S.tab === 'disc') drawDeck();
}
async function undoSwipe() {
  if (S.busy) return;
  try { const d = await api('undo', 'POST'); S.deck.unshift(d.user); drawDeck(); toast('Đã hoàn tác'); } catch (e) { toast(e.message); }
}
async function resetPassed() { await api('reset-swipes', 'POST'); S.loaded = false; renderDisc(); }
function openFilters() {
  openSheet(`<h2 class="t">Bộ lọc</h2><div class="filters">
  <div class="habit"><div class="hd"><div>Độ hợp tối thiểu</div><span id="fv">${S.filters.min}%</span></div><input type="range" min="0" max="90" step="5" value="${S.filters.min}" id="f_min"></div>
  <div class="field"><label>Trường</label><select class="input" id="f_uni"><option value="">Tất cả các trường</option>${S.unis.concat(S.filters.uni && !S.unis.includes(S.filters.uni) ? [S.filters.uni] : []).map(x => `<option ${S.filters.uni === x ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select></div></div>
  <button class="btn" style="margin-top:20px" id="f_ok">Áp dụng</button>`);
  $('#f_min').oninput = e => $('#fv').textContent = e.target.value + '%';
  $('#f_ok').onclick = () => { S.filters = { min: +$('#f_min').value, uni: $('#f_uni').value }; S.loaded = false; closeSheet(); renderDisc(); };
}
function openDetail(u) {
  if (!u) return; const cp = u.compat;
  openSheet(`<div class="dhero c${u.color}">${av({ emoji: u.emoji, color: 9 }, 64).replace('c9', 'cx').replace('class="av cx"', 'class="av" style="background:rgba(255,255,255,.25);--s:64px"')}<div><div style="font-family:var(--display);font-size:24px;font-weight:800">${esc(u.name)}, ${u.age}</div><div style="font-size:13px;opacity:.9">🎓 ${esc(u.university)}<br>📍 ${esc(u.area || 'Chưa rõ')} · 💰 Tối đa ${u.budget_max} tr</div></div></div>
  <div class="row"><div class="grow"><span class="mu">Mức hợp nhau · ${level(cp.score)}</span><div style="font-family:var(--display);font-size:38px;font-weight:800;color:${scoreColor(cp.score)}">${cp.score}%</div></div><div class="grow" style="text-align:right"><span class="mu">Ngân sách thuê</span><div style="font-family:var(--display);font-size:20px;font-weight:800">${cp.budget >= 60 ? 'Khớp nhau' : cp.budget >= 25 ? 'Hơi lệch' : 'Lệch nhiều'}</div></div></div>
  <p style="font-size:14px;line-height:1.5;margin:10px 0">${esc(u.bio)}</p><div>${u.tags.map(t => `<span class="chip${cp.shared_tags.includes(t) ? ' ok' : ''}">${esc(t)}</span>`).join('')}</div>
  <h3 class="t">So sánh thói quen</h3><div class="legend"><span><i style="background:var(--moss)"></i>Bạn</span><span><i style="background:var(--coral)"></i>${esc(u.name.split(' ').pop())}</span></div>
  ${cp.habits.map(h => { const m = HAB.find(x => x.k === h.key); return `<div class="cmp"><div class="l"><span>${m.ic} ${m.l}</span><span style="color:${scoreColor(h.sim)}">${verdict(h.sim)}</span></div><div class="tr"><div class="dt me" style="left:${(h.me - 1) * 25}%"></div><div class="dt th" style="left:${(h.them - 1) * 25}%"></div></div><div class="ends" style="display:flex;justify-content:space-between;font-size:10px;color:var(--mu);margin-top:6px"><span>${m.a}</span><span>${m.b}</span></div></div>`; }).join('')}
  <h3 class="t">🏘️ Nhu cầu thuê nhà</h3><div class="card" style="padding:0 14px">${[['💰 Tiền thuê tối đa', S.user.budget_max + ' triệu', u.budget_max + ' triệu', Math.abs(S.user.budget_max - u.budget_max) <= 0.5 ? 100 : Math.abs(S.user.budget_max - u.budget_max) <= 1.5 ? 75 : 25], ['🏠 Loại nhà', HNAME[S.user.house_type], HNAME[u.house_type], S.user.house_type === u.house_type ? 100 : 50], ['⭐ Ưu tiên', PNAME[S.user.priority], PNAME[u.priority], S.user.priority === u.priority ? 100 : 50]].map(([l, a, b, s]) => `<div class="ordr" style="align-items:center"><div><b>${l}</b><div class="mu">Bạn: ${esc(a)} · ${esc(u.name.split(' ').pop())}: ${esc(b)}</div></div><b style="color:${scoreColor(s)};white-space:nowrap">${s === 100 ? 'Giống' : s >= 75 ? 'Gần giống' : s >= 50 ? 'Hơi lệch' : 'Lệch'}</b></div>`).join('')}</div>
  <h3 class="t">💡 Gợi ý từ hệ thống</h3>${cp.insights.map(i => `<div class="insight"><span>•</span><span>${esc(i)}</span></div>`).join('') || '<p class="mu">Hai bạn khá trung tính, hãy trò chuyện thêm nhé.</p>'}
  <div class="row" style="margin-top:18px"><button class="btn ghost" onclick="closeSheet();flyTop('pass')">✕ Bỏ qua</button><button class="btn coral" onclick="closeSheet();flyTop('like')">💚 Thích</button></div>`);
}

/* ---------- match overlay ---------- */
function showMatch(m) {
  const me = S.user, u = m.user;
  const el = document.createElement('div'); el.className = 'matchov';
  el.innerHTML = `<div style="text-align:center;font-weight:700;letter-spacing:2px;font-size:12px;opacity:.8;margin-top:10px">${level(m.score).toUpperCase()} · ${m.score}%</div><h1>Hợp cạ rồi!</h1>
  <div class="pair">${av(me, 96)}<div class="heart">💚</div>${av(u, 96)}</div>
  <p style="text-align:center;opacity:.9;font-size:14px;line-height:1.5;margin-bottom:8px">Bạn và <b>${esc(u.name)}</b> đã thích nhau.<br>${esc(u.compat.insights[0] || 'Hãy nhắn tin làm quen nhé!')}</p>
  <div style="font-weight:700;margin:12px 0 4px">🏘️ Gợi ý phòng cho hai bạn</div>
  <div class="rscroll">${(m.rooms || []).map(r => `<div class="rcard">${r.sponsored ? '<span class="chip ad">Tài trợ</span>' : ''}${r.near_you ? '<span class="chip ok">Gần trường</span>' : ''}
    <div style="font-weight:700;margin:4px 0">${r.emoji} ${esc(r.name)}</div><div class="mu">📍 ${esc(r.district)} · ${r.dist}</div>
    <div class="price" style="margin:6px 0 2px">${fmt(r.price)}<span class="mu">/tháng</span></div><div class="mu">≈ ${fmt(Math.round(r.price / 2))}/người</div>
    <button class="btn sm coral" style="width:100%;margin-top:10px" data-room="${r.id}">Đặt lịch xem</button></div>`).join('')}</div>
  <div style="flex:1"></div>
  <button class="btn coral" id="m_chat">💬 Nhắn tin cho ${esc(u.name.split(' ').pop())}</button>
  <button class="btn ghost" id="m_go" style="margin-top:10px;color:#fff;border-color:rgba(255,255,255,.4)">Tiếp tục quẹt</button>`;
  $('#overlay').appendChild(el); confetti(80);
  el.querySelectorAll('[data-room]').forEach(b => b.onclick = () => bookSheet('room', m.rooms.find(r => r.id == b.dataset.room)));
  $('#m_go').onclick = () => { el.remove(); if (S.tab === 'disc') drawDeck(); };
  $('#m_chat').onclick = () => { el.remove(); openChat(m.id); };
}

/* ---------- matches & chat ---------- */
async function renderMatches() {
  $('#main').innerHTML = `<div class="topbar"><div class="logo">Tin nhắn</div></div><div class="view" id="mlist"><div class="spin"></div></div>`;
  loadMatches();
}
async function loadMatches() {
  try { const d = await api('matches'); S.matches = d.matches; S.unread = d.unread; } catch (e) { return; }
  const el = $('#mlist'); if (!el) return;
  const ms = S.matches;
  if (!ms.length) { el.innerHTML = `<div class="empty"><div class="em">💌</div><h2 class="t">Chưa có match nào</h2><p class="mu">Sang tab Khám phá và thả tim vài bạn. Bạn nào hợp thói quen sẽ match ngay!</p><br><button class="btn" onclick="S.tab='disc';shell()">Đi quẹt thôi</button></div>`; return; }
  el.innerHTML = `<h3 class="t" style="margin-top:4px">Match mới</h3><div class="nm">${ms.map(m => `<button onclick="openChat(${m.id})">${av(m.user, 62)}${esc(m.user.name.split(' ').pop())}</button>`).join('')}</div>
  <h3 class="t" style="margin-top:4px">Cuộc trò chuyện</h3>${ms.map(m => `<div class="conv ${m.unread ? 'unread' : ''}" onclick="openChat(${m.id})">${av(m.user, 54)}<div class="grow" style="flex:1;min-width:0"><b>${esc(m.user.name)}</b> <span class="chip ok" style="margin:0 0 0 4px">${m.score}%</span><div class="lm">${m.last ? (m.last.mine ? 'Bạn: ' : '') + esc(m.last.text) : 'Nói xin chào đi nào 👋'}</div></div>${m.unread ? `<div class="ub">${m.unread}</div>` : ''}</div>`).join('')}`;
}
async function openChat(id) {
  closeChat();
  const mt = S.matches.find(m => m.id === id) || (await api('matches')).matches.find(m => m.id === id); if (!mt) return;
  const page = document.createElement('div'); page.className = 'page'; page.id = 'chatpage';
  page.innerHTML = `<div class="page-h"><button class="back" id="c_back">←</button>${av(mt.user, 42)}<div style="flex:1;min-width:0"><b>${esc(mt.user.name)}</b><div class="mu" id="c_sub">${esc(mt.user.university)}</div></div><button class="icon-btn" id="c_more">⋯</button></div>
  <div class="msgs" id="msgs"></div><div class="ice" id="ice">${ICEBREAK.map(t => `<button>${t}</button>`).join('')}</div>
  <div class="composer"><input class="input" id="c_in" placeholder="Nhập tin nhắn…" maxlength="1000" autocomplete="off"><button class="send" id="c_send">➤</button></div>`;
  $('#overlay').appendChild(page);
  let last = 0, sending = false;
  const msgs = $('#msgs');
  const poll = async () => {
    if (!$('#msgs')) return;
    try {
      const d = await api(`matches/${id}/messages?after=${last}`);
      const wasBottom = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 80;
      msgs.querySelector('.typing')?.remove();
      d.messages.forEach(m => { last = Math.max(last, m.id); const e = document.createElement('div'); e.className = 'msg' + (m.mine ? ' me' : ''); e.innerHTML = `${esc(m.text)}<time>${timeStr(m.at)}</time>`; msgs.appendChild(e); });
      if (d.messages.length) $('#ice') && d.messages.some(m => m.mine) && $('#ice').remove();
      if (d.typing) { msgs.insertAdjacentHTML('beforeend', '<div class="typing"><i></i><i></i><i></i></div>'); $('#c_sub').textContent = 'đang nhập…'; } else $('#c_sub').textContent = mt.user.university;
      if (d.messages.length || d.typing) if (wasBottom || last <= d.messages[0]?.id) msgs.scrollTop = msgs.scrollHeight;
    } catch (e) { }
  };
  const send = async (text) => {
    text = (text || $('#c_in').value).trim(); if (!text || sending) return; sending = true; $('#c_in').value = '';
    try { await api(`matches/${id}/messages`, 'POST', { text }); await poll(); msgs.scrollTop = msgs.scrollHeight; } catch (e) { toast(e.message); }
    sending = false;
  };
  $('#c_send').onclick = () => send(); $('#c_in').onkeydown = e => { if (e.key === 'Enter') send(); };
  $('#ice').querySelectorAll('button').forEach(b => b.onclick = () => { send(b.textContent); });
  $('#c_back').onclick = () => { closeChat(); refreshUnread(); if (S.tab === 'mat') loadMatches(); };
  $('#c_more').onclick = () => openSheet(`<h2 class="t">${esc(mt.user.name)}</h2>
    <button class="btn" onclick="closeSheet();showRoomsFor(${id})">🏘️ Xem phòng gợi ý cho 2 bạn</button>
    <button class="btn ghost" style="margin-top:10px" onclick="closeSheet();openDetail(S.matches.find(m=>m.id==${id}).user)">👤 Xem độ hợp chi tiết</button>
    <button class="btn ghost" style="margin-top:10px;color:var(--bad)" id="unm">Hủy match</button>`);
  setTimeout(() => { const u = $('#unm'); if (u) u.onclick = async () => { if (!confirm('Hủy match với ' + mt.user.name + '?')) return; await api(`matches/${id}/unmatch`, 'POST'); closeSheet(); closeChat(); S.loaded = false; loadMatches(); refreshUnread(); }; }, 0);
  const obs = new MutationObserver(() => { const u = $('#unm'); if (u && !u.onclick) u.onclick = async () => { if (!confirm('Hủy match với ' + mt.user.name + '?')) return; await api(`matches/${id}/unmatch`, 'POST'); closeSheet(); closeChat(); loadMatches(); refreshUnread(); }; });
  obs.observe($('#sheet'), { childList: true });
  await poll(); msgs.scrollTop = msgs.scrollHeight;
  chatTimer = setInterval(poll, 1800);
}
function closeChat() { clearInterval(chatTimer); const p = $('#chatpage'); if (p) p.remove(); }
async function showRoomsFor(id) {
  const d = await api(`matches/${id}/rooms`);
  openSheet(`<h2 class="t">Phòng gợi ý cho 2 bạn</h2><p class="mu" style="margin-bottom:10px">Xếp theo ngân sách chung và khoảng cách tới trường.</p>${d.rooms.map(r => roomCard(r)).join('')}`);
  bindBook(d.rooms);
}

/* ---------- services ---------- */
function roomCard(r) {
  return `<div class="card"><div class="svc"><div class="ic">${r.emoji}</div><div style="flex:1;min-width:0"><div>${r.sponsored ? '<span class="chip ad">Tài trợ</span>' : ''}${r.near_you ? '<span class="chip ok">Gần trường bạn</span>' : ''}</div>
  <b>${esc(r.name)}</b><div class="mu">📍 ${esc(r.district)} · cách trường ${r.dist} · ${esc(r.owner)}</div></div></div>
  <p class="mu" style="margin:8px 0">${esc(r.desc)}</p><div>${r.amenities.map(a => `<span class="chip">${esc(a)}</span>`).join('')}</div>
  <div class="row" style="margin-top:6px"><div class="grow"><div class="price">${fmt(r.price)}<span class="mu">/tháng</span></div><div class="mu">≈ ${fmt(Math.round(r.price / 2))}/người${r.fits === false ? ' · ⚠️ vượt ngân sách' : ''}</div></div><button class="btn sm coral" data-book="${r.id}">Đặt lịch xem</button></div></div>`;
}
function svcCard(s) {
  return `<div class="card"><div class="svc"><div class="ic">${s.emoji}</div><div style="flex:1;min-width:0">${s.promoted ? '<span class="chip ad">Ưu tiên hiển thị</span>' : ''}<div><b>${esc(s.name)}</b></div><div class="stars">★ ${s.rating} <span class="mu">· ${s.jobs} lượt</span></div></div></div>
  <p class="mu" style="margin:8px 0">${esc(s.desc)}</p><div class="row"><div class="grow price">${s.unit === 'từ' ? 'Từ ' : ''}${fmt(s.price)}<span class="mu">${s.unit === 'từ' ? '' : '/' + s.unit}</span></div><button class="btn sm" data-book="${s.id}">Đặt ngay</button></div></div>`;
}
function bindBook(items, kind) {
  document.querySelectorAll('[data-book]').forEach(b => b.onclick = () => { const it = items.find(x => x.id == b.dataset.book); bookSheet(it.kind || kind, it); });
}
async function renderSvc() {
  $('#main').innerHTML = `<div class="topbar"><div class="logo">Hệ sinh thái</div></div><div class="view"><p class="mu" style="margin-bottom:10px">Mọi thứ cho một lần chuyển nhà trọn gói.</p>
  <div class="seg">${SVC.map(([k, ic, l]) => `<button class="${S.svc === k ? 'on' : ''}" data-s="${k}">${ic} ${l}</button>`).join('')}</div><div id="slist" style="margin-top:14px"><div class="spin"></div></div></div>`;
  document.querySelectorAll('[data-s]').forEach(b => b.onclick = () => { S.svc = b.dataset.s; renderSvc(); });
  try {
    if (S.svc === 'room') { const d = await api('rooms'); $('#slist').innerHTML = d.rooms.map(roomCard).join(''); bindBook(d.rooms); }
    else { const d = await api('services?kind=' + S.svc); $('#slist').innerHTML = d.services.map(svcCard).join(''); bindBook(d.services, S.svc); }
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
    $('#b_ok').disabled = true;
    try { await api('orders', 'POST', { kind: it.kind || kind, item_id: it.id, date: $('#b_date').value, note: $('#b_note').value }); closeSheet(); confetti(40); toast('✅ Đã gửi yêu cầu! Xem trong Hồ sơ → Đơn của tôi'); if (S.user) S.user.counts.orders++; }
    catch (e) { toast(e.message); $('#b_ok').disabled = false; }
  };
}

/* ---------- profile ---------- */
function radar(h) {
  const n = HAB.length, R = 78, cx = 110, cy = 100;
  const pt = (i, v) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return [cx + Math.cos(a) * R * v / 5, cy + Math.sin(a) * R * v / 5]; };
  const grid = [1, 2, 3, 4, 5].map(v => `<polygon points="${HAB.map((_, i) => pt(i, v).join(',')).join(' ')}" fill="none" stroke="var(--line)"/>`).join('');
  const poly = HAB.map((x, i) => pt(i, h[x.k]).join(',')).join(' ');
  const labels = HAB.map((x, i) => { const [px, py] = pt(i, 6.3); return `<text x="${px}" y="${py + 4}" text-anchor="middle" font-size="15">${x.ic}</text>`; }).join('');
  return `<svg viewBox="0 0 220 200" style="width:100%;max-width:260px;display:block;margin:auto">${grid}<polygon points="${poly}" fill="rgba(242,96,58,.25)" stroke="var(--coral)" stroke-width="2.5" stroke-linejoin="round"/>${HAB.map((x, i) => { const [px, py] = pt(i, h[x.k]); return `<circle cx="${px}" cy="${py}" r="4" fill="var(--coral)"/>`; }).join('')}${labels}</svg>`;
}
async function renderMe() {
  try { S.user = (await api('me')).user; } catch (e) { }
  const u = S.user;
  $('#main').innerHTML = `<div class="view" style="padding-top:14px">
  <div class="phero c${u.color}">${av({ emoji: u.emoji, color: 9 }, 84).replace('class="av c9"', 'class="av" style="background:rgba(255,255,255,.28);margin:auto;--s:84px"')}<h2>${esc(u.name)}, ${u.age}</h2><div style="font-size:13px;opacity:.9">🎓 ${esc(u.university || 'Chưa chọn trường')} · 📍 ${esc(u.area || '—')}</div>
  ${u.guest ? '<div style="margin-top:8px;font-size:12px;background:rgba(0,0,0,.2);border-radius:10px;padding:6px 10px;display:inline-block">Tài khoản dùng thử</div>' : ''}</div>
  <div class="statrow"><div class="stat"><b>${u.counts.swiped}</b><span>Đã quẹt</span></div><div class="stat"><b>${u.counts.matches}</b><span>Match</span></div><div class="stat"><b>${u.liked_me}</b><span>Thích bạn</span></div></div>
  <div class="card"><b>Chân dung sinh hoạt</b>${radar(u.habits)}<div style="margin-top:6px">${u.tags.map(t => `<span class="chip">${esc(t)}</span>`).join('')}</div><p class="mu" style="margin-top:6px">💰 Tiền thuê tối đa ${u.budget_max} triệu/người/tháng · ${HNAME[u.house_type]} · ưu tiên ${PNAME[u.priority].toLowerCase()}</p></div>
  <button class="btn" onclick="S.onb=null;onboarding(false,0)">✏️ Chỉnh sửa hồ sơ & thói quen</button>
  <button class="btn ghost" style="margin-top:10px" onclick="openOrders()">🧾 Đơn của tôi (${u.counts.orders})</button>
  <button class="btn ghost" style="margin-top:10px" onclick="openPartner()">📊 Bảng điều khiển đối tác (B2B)</button>
  <button class="btn ghost" style="margin-top:10px;color:var(--bad)" onclick="logout()">Đăng xuất</button><div style="height:10px"></div></div>`;
}
async function openOrders() {
  const d = await api('orders');
  openSheet(`<h2 class="t">Đơn của tôi</h2>${d.orders.length ? d.orders.map(o => `<div class="ordr"><div><b>${esc(o.name)}</b><div class="mu">📅 ${esc(o.date || '—')} · ${esc(o.status)}${o.note ? '<br>“' + esc(o.note) + '”' : ''}</div></div><div class="price" style="font-size:14px;white-space:nowrap">${fmt(o.amount)}</div></div>`).join('') : '<p class="mu" style="padding:20px 0">Bạn chưa đặt dịch vụ nào. Qua tab Dịch vụ để đặt xe, dọn phòng hoặc xem trọ nhé.</p>'}`);
}
async function openPartner() {
  const s = await api('stats');
  const kinds = { room: 'Xem phòng', truck: 'Xe chuyển', clean: 'Dọn dẹp', used: 'Đồ cũ' };
  const mx = Math.max(1, ...Object.values(s.by_kind).map(k => k.commission));
  openSheet(`<h2 class="t">Bảng điều khiển đối tác</h2><p class="mu">Số liệu thật từ toàn bộ người dùng, minh họa mô hình doanh thu B2B của nền tảng.</p>
  <div class="kpi"><div class="stat"><b>${s.users}</b><span>Người dùng</span></div><div class="stat"><b>${s.matches}</b><span>Cặp match</span></div>
  <div class="stat"><b>${s.impressions}</b><span>Lượt hiển thị phòng tài trợ</span></div><div class="stat"><b>${s.orders}</b><span>Đơn dịch vụ / xem phòng</span></div>
  <div class="stat"><b style="font-size:17px">${fmt(s.sponsor_revenue)}</b><span>Phí quảng cáo chủ trọ (2.000đ/lượt)</span></div><div class="stat"><b style="font-size:17px">${fmt(s.commission)}</b><span>Hoa hồng (10–15%)</span></div></div>
  <h3 class="t">Hoa hồng theo dịch vụ</h3><div class="bars">${Object.entries(kinds).map(([k, l]) => { const v = (s.by_kind[k] || { commission: 0, orders: 0 }); return `<div class="br"><span>${l}</span><div><i style="width:${v.commission / mx * 100}%"></i></div><b>${fmt(v.commission)}</b></div>`; }).join('')}</div>
  <h3 class="t">Phòng được xem nhiều nhất</h3>${s.top_rooms.map(r => `<div class="ordr"><span>${esc(r.name)}</span><b>${r.views} lượt</b></div>`).join('') || '<p class="mu">Chưa có dữ liệu.</p>'}
  <h3 class="t">Doanh thu ước tính</h3><div class="card" style="text-align:center"><div class="price" style="font-size:28px">${fmt(s.sponsor_revenue + s.commission)}</div><div class="mu">Phí hiển thị + hoa hồng</div></div>`);
}
boot();

