/* 麦麦热量管家 · 网页版
   纯前端，数据来自麦当劳官方 MCP 的营养数据快照。
   算法与 scripts/plan.py 保持一致。 */

const GOALS = {
  balanced:     { protein: 1.00, calcium: 0.05, sodium: 0.15, carb: 0.00, label: '均衡' },
  high_protein: { protein: 1.80, calcium: 0.05, sodium: 0.10, carb: 0.00, label: '高蛋白' },
  low_sodium:   { protein: 0.50, calcium: 0.05, sodium: 3.00, carb: 0.00, label: '控钠' },
  low_carb:     { protein: 1.20, calcium: 0.05, sodium: 0.15, carb: 0.15, label: '低碳' },
  high_calcium: { protein: 0.80, calcium: 0.30, sodium: 0.15, carb: 0.00, label: '补钙' }
};

const CAT_LABEL = { main: '主食', side: '小食', drink: '饮料', dessert: '甜品' };
const NA_LIMIT = 2000; // 成人每日钠参考摄入量

const state = {
  items: [],
  combos: [],
  budget: 600,
  goal: 'balanced',
  fill: 0.75,
  maxItems: 4,
  exclude: new Set(['dessert']),
  basket: []
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

function sum(items, key) {
  return items.reduce((acc, i) => acc + i[key], 0);
}

function totals(items) {
  return {
    k: sum(items, 'k'), p: sum(items, 'p'), f: sum(items, 'f'),
    c: sum(items, 'c'), na: sum(items, 'na'), ca: sum(items, 'ca')
  };
}

function score(items, w) {
  const t = totals(items);
  return w.protein * t.p + w.calcium * t.ca / 100 - w.sodium * t.na / 100 - w.carb * t.c;
}

/* ---- 组合搜索：与 plan.py 相同的 DFS + 剪枝 ---- */
function search(items, budget, w, fill, maxItems, order) {
  const pools = order
    .map((cat) => items.filter((i) => i.cat === cat && i.k <= budget)
      .sort((a, b) => a.k - b.k));
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

/* 去掉只差一杯饮料的重复方案 */
function dedupe(plans) {
  const seen = new Set();
  return plans.filter((p) => {
    const key = p.items.filter((i) => i.cat !== 'drink').map((i) => i.n).join('|');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/* 同一个主食最多出现两次，保证给出的是不同思路 */
function diversify(plans, limit) {
  const picked = [];
  const count = {};
  for (const p of plans) {
    const main = (p.items.find((i) => i.cat === 'main') || {}).n || '';
    count[main] = (count[main] || 0) + 1;
    if (count[main] > 2) continue;
    picked.push(p);
    if (picked.length >= limit) break;
  }
  return picked;
}

function foodCard(item) {
  const box = el('div', 'food');
  if (item.img) {
    const img = el('img');
    img.src = item.img;
    img.alt = item.n;
    img.loading = 'lazy';
    box.appendChild(img);
  } else {
    box.appendChild(el('div', 'ph', item.n.slice(0, 1)));
  }
  box.appendChild(el('div', 'name', item.n));
  box.appendChild(el('div', 'kcal', item.k + ' kcal'));
  return box;
}

function nutritionLine(t, budget) {
  const line = el('div', 'nut');
  const add = (label, value, unit, warn) => {
    const s = el('span');
    const b = el('b', null, String(value));
    if (warn) b.className = 'warn';
    s.appendChild(document.createTextNode(label + ' '));
    s.appendChild(b);
    s.appendChild(document.createTextNode(unit));
    line.appendChild(s);
  };
  add('热量', t.k, ' kcal');
  add('蛋白', t.p, ' g');
  add('脂肪', t.f, ' g');
  add('碳水', t.c, ' g');
  add('钠', t.na, ' mg', t.na > NA_LIMIT * 0.75);
  add('钙', t.ca, ' mg');
  if (budget) add('剩余', t.k <= budget ? budget - t.k : 0, ' kcal');
  return line;
}

function warnNote(t) {
  if (t.na > NA_LIMIT * 0.75) {
    return el('p', 'hint', '注意：这一餐的钠 ' + t.na + 'mg，已占成人每日参考摄入量的 ' +
      Math.round(t.na / NA_LIMIT * 100) + '%，控钠人群慎选。');
  }
  return null;
}

function renderPlans() {
  const box = $('#plans');
  box.innerHTML = '';
  const order = ['main', 'side', 'drink', 'dessert'].filter((c) => !state.exclude.has(c));
  const budget = state.budget;
  const w = GOALS[state.goal];

  if (!order.length) {
    box.appendChild(el('p', 'hint', '所有分类都被排除了，至少留一个。'));
    return;
  }

  const plans = diversify(dedupe(
    search(state.items, budget, w, state.fill, state.maxItems, order)
  ), 5);

  $('#plan-hint').textContent =
    '在 ' + state.items.length + ' 个餐品里搜索 · 目标 ' + w.label +
    ' · 至少用掉预算的 ' + Math.round(state.fill * 100) + '%';

  if (!plans.length) {
    box.appendChild(el('p', 'hint', '这个预算下没有符合条件的组合，试试提高预算或降低饱腹度要求。'));
    return;
  }

  plans.forEach((p, idx) => {
    const card = el('div', 'plan');

    const head = el('div', 'plan-head');
    head.appendChild(el('span', 'plan-rank', '方案 ' + (idx + 1)));
    const kcal = el('div', 'plan-kcal', String(p.t.k));
    kcal.appendChild(el('small', null, ' / ' + budget + ' kcal'));
    head.appendChild(kcal);
    card.appendChild(head);

    const foods = el('div', 'foods');
    p.items.forEach((i) => foods.appendChild(foodCard(i)));
    card.appendChild(foods);

    card.appendChild(nutritionLine(p.t, budget));

    const bar = el('div', 'bar' + (p.t.k > budget ? ' over' : ''));
    const fillEl = el('i');
    fillEl.style.width = Math.min(100, Math.round(p.t.k / budget * 100)) + '%';
    bar.appendChild(fillEl);
    card.appendChild(bar);

    const note = warnNote(p.t);
    if (note) card.appendChild(note);

    card.appendChild(el('div', 'tags',
      '结构：' + p.items.map((i) => CAT_LABEL[i.cat]).join('、')));

    box.appendChild(card);
  });
}

/* ---- 套餐分析器 ---- */
function renderPicker(keyword) {
  const box = $('#picker');
  box.innerHTML = '';
  const kw = (keyword || '').trim();
  const list = state.items.filter((i) => !kw || i.n.includes(kw)).slice(0, 60);
  if (!list.length) {
    box.appendChild(el('p', 'hint', '没找到匹配的餐品。'));
    return;
  }
  list.forEach((i) => {
    const b = el('button', null, i.n + ' · ' + i.k + 'kcal');
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
    box.appendChild(el('p', 'empty', '还没选餐品。在上面搜索框里搜，点一下加进来。'));
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
  const out = $('#totals');
  out.innerHTML = '';
  out.className = 'totals on';
  out.appendChild(nutritionLine(t));

  const bar = el('div', 'bar' + (t.k > state.budget ? ' over' : ''));
  const f = el('i');
  f.style.width = Math.min(100, Math.round(t.k / state.budget * 100)) + '%';
  bar.appendChild(f);
  out.appendChild(bar);
  out.appendChild(el('p', 'hint',
    '对照预算 ' + state.budget + ' kcal：' +
    (t.k > state.budget ? '超出 ' + (t.k - state.budget) + ' kcal' : '还剩 ' + (state.budget - t.k) + ' kcal')));

  const note = warnNote(t);
  if (note) out.appendChild(note);
}

/* ---- 社区套餐 ---- */
function renderCommunity() {
  const box = $('#community');
  box.innerHTML = '';
  state.combos.forEach((c) => {
    const card = el('div', 'plan');
    const head = el('div', 'plan-head');
    head.appendChild(el('span', 'plan-rank', c.author + ' · ' + c.created_at));
    const kcal = el('div', 'plan-kcal', String(c.nutrition.energy_kcal));
    kcal.appendChild(el('small', null, ' kcal'));
    head.appendChild(kcal);
    card.appendChild(head);

    const title = el('div', 'nut');
    const b = el('b', null, c.name);
    title.appendChild(b);
    card.appendChild(title);

    const foods = el('div', 'foods');
    c.items.forEach((name, idx) => {
      const item = state.items.find((x) => x.n === name) || { n: name, k: 0, img: (c.images || [])[idx] || '' };
      foods.appendChild(foodCard(item));
    });
    card.appendChild(foods);

    const t = {
      k: c.nutrition.energy_kcal, p: c.nutrition.protein_g, f: c.nutrition.fat_g,
      c: c.nutrition.carbohydrate_g, na: c.nutrition.sodium_mg, ca: c.nutrition.calcium_mg
    };
    card.appendChild(nutritionLine(t));
    if (c.note) card.appendChild(el('p', 'hint', c.note));
    if (c.tags && c.tags.length) card.appendChild(el('div', 'tags', '标签：' + c.tags.join('、')));

    const load = el('button', 'ghost', '载入分析器');
    load.style.marginTop = '10px';
    load.onclick = () => {
      state.basket = c.items
        .map((n) => state.items.find((x) => x.n === n))
        .filter(Boolean);
      switchTab('analyze');
      renderBasket();
    };
    card.appendChild(load);

    box.appendChild(card);
  });
}

/* ---- 交互 ---- */
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t) => {
    t.classList.toggle('active', t.dataset.tab === name);
  });
  document.querySelectorAll('.tab-panel').forEach((p) => {
    p.classList.toggle('active', p.id === 'tab-' + name);
  });
}

function bind() {
  document.querySelectorAll('.tab').forEach((t) => {
    t.onclick = () => switchTab(t.dataset.tab);
  });

  const budget = $('#budget');
  budget.oninput = () => {
    state.budget = Math.max(50, Math.min(3000, Number(budget.value) || 600));
    renderPlans();
    renderBasket();
  };

  const fill = $('#fill');
  fill.oninput = () => {
    state.fill = Number(fill.value) / 100;
    $('#fill-val').textContent = fill.value + '%';
    renderPlans();
  };

  const maxitems = $('#maxitems');
  maxitems.oninput = () => {
    state.maxItems = Number(maxitems.value);
    $('#max-val').textContent = maxitems.value;
    renderPlans();
  };

  document.querySelectorAll('.goal').forEach((g) => {
    g.onclick = () => {
      document.querySelectorAll('.goal').forEach((x) => x.classList.remove('active'));
      g.classList.add('active');
      state.goal = g.dataset.goal;
      renderPlans();
    };
  });

  document.querySelectorAll('.chip').forEach((c) => {
    c.onclick = () => {
      const cat = c.dataset.cat;
      if (state.exclude.has(cat)) state.exclude.delete(cat);
      else state.exclude.add(cat);
      c.classList.toggle('active', !state.exclude.has(cat));
      renderPlans();
    };
  });

  $('#search').oninput = (e) => renderPicker(e.target.value);
  $('#clear').onclick = () => { state.basket = []; renderBasket(); };
}

async function boot() {
  try {
    const [nres, cres] = await Promise.all([
      fetch('data/nutrition.json'),
      fetch('data/combos.json')
    ]);
    const ndata = await nres.json();
    const cdata = await cres.json();
    state.items = ndata.items;
    state.combos = cdata.combos;
  } catch (err) {
    $('#plans').appendChild(el('p', 'hint',
      '数据加载失败：' + err.message + '。请通过 HTTP 打开本页面（不要直接双击 html 文件）。'));
    return;
  }
  bind();
  renderPlans();
  renderPicker('');
  renderBasket();
  renderCommunity();
}

boot();
