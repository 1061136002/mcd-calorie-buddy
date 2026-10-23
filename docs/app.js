/* 麦麦热量管家 · 网页版
   纯前端，数据来自麦当劳官方 MCP 的营养数据快照 + 菜单接口的价格与图片。
   算法与 scripts/plan.py 保持一致。 */

const GOALS = {
  balanced:     { protein: 1.00, calcium: 0.05, sodium: 0.15, carb: 0.00, label: '均衡' },
  high_protein: { protein: 1.80, calcium: 0.05, sodium: 0.10, carb: 0.00, label: '高蛋白' },
  low_sodium:   { protein: 0.50, calcium: 0.05, sodium: 3.00, carb: 0.00, label: '控钠' },
  low_carb:     { protein: 1.20, calcium: 0.05, sodium: 0.15, carb: 0.15, label: '低碳' },
  high_calcium: { protein: 0.80, calcium: 0.30, sodium: 0.15, carb: 0.00, label: '补钙' }
};

const CAT_LABEL = { main: '主食', side: '小食', drink: '饮料', dessert: '甜品' };
const NA_LIMIT = 2000;
const PER_PAGE = 5;

const state = {
  items: [],
  combos: [],
  meta: {},
  budget: 600,
  money: 60,
  goal: 'balanced',
  fill: 0.75,
  maxItems: 4,
  exclude: new Set(['dessert']),
  onlyAvail: true,
  sort: 'score',
  page: 0,
  basket: [],
  pickerCat: 'all'
};

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
const money = (v) => '¥' + (Math.round(v * 10) / 10).toFixed(1);

function totals(items) {
  const t = { k: 0, p: 0, f: 0, c: 0, na: 0, ca: 0 };
  for (const i of items) {
    t.k += i.k; t.p += i.p; t.f += i.f; t.c += i.c; t.na += i.na; t.ca += i.ca;
  }
  return t;
}

function priceOf(items) {
  const known = items.filter((i) => typeof i.pr === 'number');
  if (!known.length) return null;
  return known.reduce((a, i) => a + i.pr, 0);
}

function score(items, w) {
  const t = totals(items);
  return w.protein * t.p + w.calcium * t.ca / 100 - w.sodium * t.na / 100 - w.carb * t.c;
}

/* ---- 组合搜索：与 plan.py 相同的 DFS + 剪枝 ---- */
function search(items, budget, w, fill, maxItems, order) {
  const pools = order.map((cat) =>
    items.filter((i) => i.cat === cat && i.k <= budget).sort((a, b) => a.k - b.k));
  const out = [];
  const picked = [];
  (function walk(idx, used) {
    if (out.length >= 20000) return;
    if (idx === order.length) {
      if (!picked.length || picked.length > maxItems) return;
      if (used > budget || used < budget * fill) return;
      out.push({ items: picked.slice(), t: totals(picked), s: score(picked, w), left: budget - used });
      return;
    }
    walk(idx + 1, used);
    for (const item of pools[idx]) {
      if (used + item.k > budget) break;
      picked.push(item);
      walk(idx + 1, used + item.k);
      picked.pop();
    }
  })(0, 0);
  out.sort((a, b) => b.s - a.s || a.left - b.left);
  return out;
}

function dedupe(plans) {
  const seen = new Set();
  return plans.filter((p) => {
    const key = p.items.filter((i) => i.cat !== 'drink').map((i) => i.n).join('|');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function diversify(plans) {
  const count = {};
  return plans.filter((p) => {
    const main = (p.items.find((i) => i.cat === 'main') || {}).n || '';
    count[main] = (count[main] || 0) + 1;
    return count[main] <= 2;
  });
}

/* ---- 渲染小件 ---- */
function thumb(item, size) {
  if (item.img) {
    const img = el('img');
    img.src = item.img;
    img.alt = item.n;
    img.loading = 'lazy';
    return img;
  }
  return el('div', size === 'sm' ? 'dot' : 'ph', item.n.slice(0, 1));
}

function foodCard(item) {
  const box = el('div', 'food');
  const t = el('div', 'thumb');
  t.appendChild(thumb(item));
  box.appendChild(t);
  if (typeof item.pr === 'number') box.appendChild(el('span', 'pbadge', money(item.pr)));
  box.appendChild(el('div', 'name', item.n));
  box.appendChild(el('div', 'sub', item.k + ' kcal' + (item.av ? '' : ' · 暂无在售')));
  if (!item.av) box.querySelector('.sub').classList.add('gone');
  return box;
}

function metrics(t) {
  const box = el('div', 'metrics');
  const add = (key, val, warn) => {
    const d = el('div');
    d.appendChild(el('div', 'm-val' + (warn ? ' warn' : ''), String(val)));
    d.appendChild(el('div', 'm-key', key));
    box.appendChild(d);
  };
  add('热量', t.k + ' kcal');
  add('蛋白', t.p + ' g');
  add('脂肪', t.f + ' g');
  add('碳水', t.c + ' g');
  add('钠', t.na + ' mg', t.na > NA_LIMIT * 0.75);
  add('钙', t.ca + ' mg');
  return box;
}

function naNote(t) {
  if (t.na > NA_LIMIT * 0.75) {
    return el('p', 'hint', '这一餐的钠 ' + t.na + 'mg，已占成人每日参考摄入量的 ' +
      Math.round(t.na / NA_LIMIT * 100) + '%，控钠人群慎选。');
  }
  return null;
}

/* ---- 智能配餐 ---- */
function currentItems() {
  return state.onlyAvail ? state.items.filter((i) => i.av) : state.items;
}

function renderPlans() {
  const box = $('#plans');
  box.innerHTML = '';
  const budget = state.budget;
  const w = GOALS[state.goal];
  const order = ['main', 'side', 'drink', 'dessert'].filter((c) => !state.exclude.has(c));

  if (!order.length) {
    box.appendChild(el('p', 'hint', '所有分类都被排除了，至少留一个。'));
    return;
  }

  let plans = diversify(dedupe(
    search(currentItems(), budget, w, state.fill, state.maxItems, order)
  ));

  const withPrice = plans.filter((p) => priceOf(p.items) !== null);
  if (state.money > 0) {
    const affordable = withPrice.filter((p) => priceOf(p.items) <= state.money);
    if (affordable.length) plans = affordable;
  }

  const sorters = {
    'score': null,
    'price-asc': (a, b) => (priceOf(a.items) ?? 1e9) - (priceOf(b.items) ?? 1e9),
    'price-desc': (a, b) => (priceOf(b.items) ?? -1) - (priceOf(a.items) ?? -1),
    'protein': (a, b) => b.t.p - a.t.p,
    'kcal': (a, b) => a.t.k - b.t.k
  };
  if (sorters[state.sort]) plans = plans.slice().sort(sorters[state.sort]);

  const pages = Math.max(1, Math.ceil(plans.length / PER_PAGE));
  if (state.page >= pages) state.page = 0;
  const slice = plans.slice(state.page * PER_PAGE, state.page * PER_PAGE + PER_PAGE);

  $('#plan-hint').textContent =
    '在 ' + currentItems().length + ' 个餐品里搜索 · 目标 ' + w.label +
    ' · 价格上限 ' + (state.money > 0 ? money(state.money) : '不限') +
    ' · 共 ' + plans.length + ' 个方案' + (pages > 1 ? '（第 ' + (state.page + 1) + '/' + pages + ' 批）' : '');

  if (!slice.length) {
    box.appendChild(el('p', 'hint',
      '这个预算下没有符合条件的组合。试试提高热量预算或价格上限，或降低饱腹度要求。'));
    return;
  }

  slice.forEach((p, idx) => {
    const card = el('div', 'plan');
    const top = el('div', 'plan-top');
    const left = el('div');
    left.appendChild(el('div', 'plan-title', '方案 ' + (state.page * PER_PAGE + idx + 1)));
    left.appendChild(el('div', 'sub', p.items.map((i) => CAT_LABEL[i.cat]).join(' + ')));
    top.appendChild(left);

    const right = el('div');
    const kcal = el('div', 'plan-kcal', String(p.t.k));
    kcal.appendChild(el('small', null, '/ ' + budget + ' kcal'));
    right.appendChild(kcal);
    const pr = priceOf(p.items);
    if (pr !== null) right.appendChild(el('div', 'plan-price', money(pr)));
    top.appendChild(right);
    card.appendChild(top);

    const foods = el('div', 'foods');
    p.items.forEach((i) => foods.appendChild(foodCard(i)));
    card.appendChild(foods);

    card.appendChild(metrics(p.t));

    const bar = el('div', 'bar' + (p.t.k > budget ? ' over' : ''));
    const f = el('i');
    f.style.width = Math.min(100, Math.round(p.t.k / budget * 100)) + '%';
    bar.appendChild(f);
    card.appendChild(bar);

    const note = naNote(p.t);
    if (note) card.appendChild(note);
    card.appendChild(el('div', 'tags',
      '剩余热量预算 ' + p.left + ' kcal' + (pr !== null ? ' · 单价合计 ' + money(pr) : '')));

    box.appendChild(card);
  });
}

/* ---- 自己搭配 ---- */
function renderPicker() {
  const box = $('#picker');
  box.innerHTML = '';
  const kw = ($('#search').value || '').trim();
  let list = state.items.filter((i) => !kw || i.n.includes(kw));
  if (state.pickerCat !== 'all') list = list.filter((i) => i.cat === state.pickerCat);
  list.sort((a, b) => (a.av === b.av ? a.k - b.k : (a.av ? -1 : 1)));

  $('#picker-hint').textContent = '共 ' + list.length + ' 个餐品' +
    (state.onlyAvail ? '（标注「暂无在售」的是营养库里已下架的季节限定）' : '');

  list.forEach((i) => {
    const b = el('button');
    const dot = el('span');
    dot.appendChild(thumb(i, 'sm'));
    b.appendChild(dot);
    b.appendChild(el('span', null, i.n));
    b.appendChild(el('span', 'pk', i.k + ' kcal' + (typeof i.pr === 'number' ? ' · ' + money(i.pr) : '')));
    if (!i.av) b.style.opacity = '.55';
    b.onclick = () => {
      if (!state.basket.find((x) => x.n === i.n)) state.basket.push(i);
      renderBasket();
    };
    box.appendChild(b);
  });
}

function renderBasket() {
  const box = $('#basket');
  box.innerHTML = '';
  if (!state.basket.length) {
    box.appendChild(el('p', 'empty', '还没选餐品。在上面搜索或按分类挑，点一下加进来。'));
    $('#totals').className = 'totals';
    return;
  }
  state.basket.forEach((i) => {
    const wrap = el('div', 'food');
    wrap.appendChild(foodCard(i));
    const rm = el('button', 'ghost', '移除');
    rm.style.marginTop = '6px';
    rm.onclick = () => {
      state.basket = state.basket.filter((x) => x.n !== i.n);
      renderBasket();
    };
    wrap.appendChild(rm);
    box.appendChild(wrap);
  });

  const t = totals(state.basket);
  const pr = priceOf(state.basket);
  const out = $('#totals');
  out.innerHTML = '';
  out.className = 'totals on';
  out.appendChild(metrics(t));

  const bar = el('div', 'bar' + (t.k > state.budget ? ' over' : ''));
  const f = el('i');
  f.style.width = Math.min(100, Math.round(t.k / state.budget * 100)) + '%';
  bar.appendChild(f);
  out.appendChild(bar);

  const parts = ['对照热量预算 ' + state.budget + ' kcal：' +
    (t.k > state.budget ? '超出 ' + (t.k - state.budget) : '还剩 ' + (state.budget - t.k))];
  if (pr !== null) parts.push('合计 ' + money(pr) +
    (state.money > 0 ? (pr > state.money ? '，超出价格上限 ' + money(pr - state.money) : '，在价格上限内') : ''));
  out.appendChild(el('p', 'hint', parts.join(' · ')));

  const note = naNote(t);
  if (note) out.appendChild(note);
}

/* ---- 社区套餐 ---- */
function renderCommunity() {
  const box = $('#community');
  box.innerHTML = '';
  state.combos.forEach((c) => {
    const card = el('div', 'plan');
    const top = el('div', 'plan-top');
    const left = el('div');
    left.appendChild(el('div', 'plan-title', c.name));
    left.appendChild(el('div', 'sub', c.author + ' · ' + c.created_at));
    top.appendChild(left);

    const right = el('div');
    const kcal = el('div', 'plan-kcal', String(c.nutrition.energy_kcal));
    kcal.appendChild(el('small', null, 'kcal'));
    right.appendChild(kcal);
    if (c.price !== null && c.price !== undefined) {
      right.appendChild(el('div', 'plan-price', money(c.price)));
    }
    top.appendChild(right);
    card.appendChild(top);

    const foods = el('div', 'foods');
    c.items.forEach((name, idx) => {
      const item = state.items.find((x) => x.n === name) ||
        { n: name, k: 0, img: (c.images || [])[idx] || '', av: false };
      foods.appendChild(foodCard(item));
    });
    card.appendChild(foods);

    card.appendChild(metrics({
      k: c.nutrition.energy_kcal, p: c.nutrition.protein_g, f: c.nutrition.fat_g,
      c: c.nutrition.carbohydrate_g, na: c.nutrition.sodium_mg, ca: c.nutrition.calcium_mg
    }));
    if (c.note) card.appendChild(el('p', 'hint', c.note));
    if (c.tags && c.tags.length) card.appendChild(el('div', 'tags', '标签：' + c.tags.join('、')));

    const load = el('button', 'ghost', '载入我的套餐');
    load.style.marginTop = '10px';
    load.onclick = () => {
      state.basket = c.items.map((n) => state.items.find((x) => x.n === n)).filter(Boolean);
      switchTab('analyze');
      renderBasket();
    };
    card.appendChild(load);
    box.appendChild(card);
  });
}

/* ---- 交互 ---- */
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === 'tab-' + name));
}

function bind() {
  document.querySelectorAll('.tab').forEach((t) => { t.onclick = () => switchTab(t.dataset.tab); });

  const budget = $('#budget'), brange = $('#budget-range');
  const setBudget = (v) => {
    state.budget = Math.max(100, Math.min(2000, v));
    budget.value = state.budget; brange.value = Math.min(1200, state.budget);
    renderPlans(); renderBasket();
  };
  budget.oninput = () => setBudget(Number(budget.value) || 600);
  brange.oninput = () => setBudget(Number(brange.value));

  const moneyIn = $('#money'), mrange = $('#money-range');
  const setMoney = (v) => {
    state.money = Math.max(0, Math.min(300, v));
    moneyIn.value = state.money; mrange.value = Math.min(150, state.money || 10);
    renderPlans(); renderBasket();
  };
  moneyIn.oninput = () => setMoney(Number(moneyIn.value) || 0);
  mrange.oninput = () => setMoney(Number(mrange.value));

  $('#sort').onchange = (e) => { state.sort = e.target.value; state.page = 0; renderPlans(); };

  const fill = $('#fill');
  fill.oninput = () => {
    state.fill = Number(fill.value) / 100;
    $('#fill-val').textContent = fill.value + '%';
    renderPlans();
  };

  document.querySelectorAll('#goals .chip').forEach((g) => {
    g.onclick = () => {
      document.querySelectorAll('#goals .chip').forEach((x) => x.classList.remove('active'));
      g.classList.add('active');
      state.goal = g.dataset.goal;
      state.page = 0;
      renderPlans();
    };
  });

  document.querySelectorAll('#cats .chip').forEach((c) => {
    c.onclick = () => {
      const cat = c.dataset.cat;
      if (state.exclude.has(cat)) state.exclude.delete(cat); else state.exclude.add(cat);
      c.classList.toggle('active', !state.exclude.has(cat));
      state.page = 0;
      renderPlans();
    };
  });

  $('#toggle-avail').onclick = (e) => {
    state.onlyAvail = !state.onlyAvail;
    e.target.classList.toggle('active', state.onlyAvail);
    state.page = 0;
    renderPlans();
  };

  $('#refresh').onclick = () => { state.page += 1; renderPlans(); };

  $('#search').oninput = renderPicker;
  document.querySelectorAll('#picker-cats .chip').forEach((c) => {
    c.onclick = () => {
      document.querySelectorAll('#picker-cats .chip').forEach((x) => x.classList.remove('active'));
      c.classList.add('active');
      state.pickerCat = c.dataset.cat;
      renderPicker();
    };
  });
  $('#clear').onclick = () => { state.basket = []; renderBasket(); };
}

async function boot() {
  let ndata, cdata;
  if (window.__MCD_DATA__) {
    // 单文件自包含模式：数据由 build_web_data.py 内联进页面
    ndata = window.__MCD_DATA__.nutrition;
    cdata = window.__MCD_DATA__.combos;
    state.meta = window.__MCD_DATA__.meta || {};
  } else {
    try {
      const [nres, cres] = await Promise.all([fetch('data/nutrition.json'), fetch('data/combos.json')]);
      ndata = await nres.json();
      cdata = await cres.json();
      state.meta = ndata;
    } catch (err) {
      $('#plans').appendChild(el('p', 'hint',
        '数据加载失败：' + err.message + '。请通过 HTTP 打开本页面，不要直接双击 html 文件。'));
      return;
    }
  }
  state.items = ndata.items;
  state.combos = cdata.combos;
  if (state.meta.price_note) $('#price-note').textContent = '价格说明：' + state.meta.price_note;
  bind();
  renderPlans();
  renderPicker();
  renderBasket();
  renderCommunity();
}

boot();
