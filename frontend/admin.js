const API_BASE_URL = "/api/admin";

const state = {
  sessions: [],
  selected: null, // player_id
  detail: null,
};

const DOM = {
  sessionList: document.getElementById('session-list'),
  refreshBtn: document.getElementById('refresh-sessions'),
  detailBox: document.getElementById('session-detail'),
  clearBtn: document.getElementById('clear-session'),
  punishBtn: document.getElementById('punish-btn'),
  punishLevel: document.getElementById('punish-level'),
  punishReason: document.getElementById('punish-reason'),
};

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  if (res.status === 401 || res.status === 403) {
    alert('需要管理员权限或登录已失效');
    window.location.href = '/';
    throw new Error('unauthorized');
  }
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return null;
  return res.json();
}

async function loadSessions() {
  const list = await api(`/sessions/recent?limit=50`);
  state.sessions = list;
  renderSessionList();
}

function renderSessionList() {
  const frag = document.createDocumentFragment();
  state.sessions.forEach(s => {
    const div = document.createElement('div');
    div.className = 'session-item' + (state.selected === s.player_id ? ' active' : '');
    const last = new Date((s.last_modified || 0) * 1000).toLocaleString();
    div.innerHTML = `
      <div><strong>${s.player_id}</strong></div>
      <div style="font-size:12px;color:#6b7280">${last} · in_trial=${!!s.is_in_trial} · 機緣=${s.opportunities_remaining}</div>
    `;
    div.onclick = () => {
      state.selected = s.player_id;
      loadDetail();
      renderSessionList();
    };
    frag.appendChild(div);
  });
  DOM.sessionList.innerHTML = '';
  DOM.sessionList.appendChild(frag);
}

async function loadDetail() {
  if (!state.selected) return;
  DOM.detailBox.innerHTML = '<div class="system-message">加载中...</div>';
  try {
    const detail = await api(`/sessions/${encodeURIComponent(state.selected)}`);
    state.detail = detail;
    renderDetail();
  } catch (e) {
    DOM.detailBox.innerHTML = `<div class="system-message">加载失败：${String(e)}</div>`;
  }
}

function renderDetail() {
  if (!state.detail) {
    DOM.detailBox.innerHTML = '<div class="system-message">暂无详情</div>';
    DOM.clearBtn.disabled = true;
    DOM.punishBtn.disabled = true;
    return;
  }
  DOM.clearBtn.disabled = false;
  DOM.punishBtn.disabled = false;
  const safe = JSON.stringify(state.detail, null, 2);
  DOM.detailBox.innerHTML = `<pre>${safe}</pre>`;
}

async function clearSession() {
  if (!state.selected) return;
  if (!confirm(`确认清空会话：${state.selected}？`)) return;
  await api(`/sessions/${encodeURIComponent(state.selected)}/clear`, { method: 'POST' });
  await loadDetail();
}

async function punish() {
  if (!state.selected) return;
  const level = DOM.punishLevel.value;
  const reason = DOM.punishReason.value.trim();
  await api(`/punish`, { method: 'POST', body: JSON.stringify({ player_id: state.selected, level, reason }) });
  alert('已标记惩戒，将在用户下一次交互时处理。');
}

function init() {
  DOM.refreshBtn.onclick = loadSessions;
  DOM.clearBtn.onclick = clearSession;
  DOM.punishBtn.onclick = punish;
  loadSessions();
}

init();

