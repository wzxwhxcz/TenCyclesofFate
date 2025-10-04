async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return await res.json().catch(() => ({}));
}

function fmtTime(ts) {
  if (!ts) return '-';
  const d = new Date(ts * 1000);
  if (isNaN(d.getTime())) return new Date(ts).toLocaleString();
  return d.toLocaleString();
}

async function loadSessions() {
  const limit = Number(document.getElementById('limit').value || 50);
  const data = await fetchJSON(`/api/admin/sessions?limit=${limit}`);
  const tbody = document.getElementById('sessions');
  tbody.innerHTML = '';
  for (const s of data) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td title="${s.player_id}">${s.player_id}</td>
      <td>${fmtTime(s.last_modified)}</td>
      <td>${s.pending_punishment ? JSON.stringify(s.pending_punishment) : ''}</td>
      <td class="actions">
        <button data-view="${s.encrypted_id || s.player_id}">查看</button>
        <button data-clear="${s.encrypted_id || s.player_id}">清空</button>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

async function showDetail(idOrEnc) {
  const detail = await fetchJSON(`/api/admin/session/${encodeURIComponent(idOrEnc)}`);
  document.getElementById('detail').textContent = JSON.stringify(detail, null, 2);
}

async function clearSession(idOrEnc) {
  await fetchJSON(`/api/admin/sessions/${encodeURIComponent(idOrEnc)}/clear`, { method: 'POST' });
  await loadSessions();
}

async function makeCode() {
  const quota = Number(document.getElementById('quota').value);
  const name = document.getElementById('name').value;
  const res = await fetchJSON('/api/admin/redemptions', {
    method: 'POST',
    body: JSON.stringify({ quota, name }),
  });
  document.getElementById('code').textContent = res.code || '';
}

function bindEvents() {
  document.getElementById('refresh').addEventListener('click', loadSessions);
  document.getElementById('mkcode').addEventListener('click', makeCode);
  document.getElementById('sessions').addEventListener('click', (e) => {
    const view = e.target.getAttribute('data-view');
    if (view) return void showDetail(view);
    const clear = e.target.getAttribute('data-clear');
    if (clear) return void clearSession(clear);
  });
}

bindEvents();
loadSessions().catch((err) => {
  console.error(err);
  document.getElementById('detail').textContent = `加载失败：${err.message}`;
});

