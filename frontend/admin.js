// ==================== 工具函数 ====================

/**
 * 发送JSON请求
 */
async function fetchJSON(url, options = {}) {
  try {
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
  } catch (error) {
    console.error('请求失败:', error);
    throw error;
  }
}

/**
 * 格式化时间戳
 */
function formatTime(ts) {
  if (!ts) return '-';
  
  const d = new Date(ts * 1000);
  if (isNaN(d.getTime())) {
    return new Date(ts).toLocaleString('zh-CN');
  }
  
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

/**
 * 格式化相对时间
 */
function formatRelativeTime(ts) {
  if (!ts) return '-';
  
  const now = Date.now();
  const time = ts * 1000;
  const diff = now - time;
  
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days}天前`;
  if (hours > 0) return `${hours}小时前`;
  if (minutes > 0) return `${minutes}分钟前`;
  if (seconds > 0) return `${seconds}秒前`;
  return '刚刚';
}

/**
 * 显示通知
 */
function showNotification(message, type = 'info') {
  const colors = {
    success: '#48bb78',
    error: '#f56565',
    warning: '#ed8936',
    info: '#667eea'
  };
  
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: ${colors[type] || colors.info};
    color: white;
    padding: 16px 24px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 10000;
    animation: slideIn 0.3s ease-out;
    max-width: 400px;
    font-size: 14px;
  `;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease-out';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

// 添加动画样式
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(400px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  
  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(400px);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);

// ==================== 数据管理 ====================

let allSessions = [];
let filteredSessions = [];

/**
 * 加载会话列表
 */
async function loadSessions() {
  try {
    const limit = Number(document.getElementById('limit').value || 50);
    const data = await fetchJSON(`/api/admin/sessions?limit=${limit}`);
    
    allSessions = data || [];
    applyFilters();
    updateStatistics();
    renderSessions();
    
    showNotification(`成功加载 ${allSessions.length} 个会话`, 'success');
  } catch (error) {
    console.error('加载会话失败:', error);
    showNotification(`加载失败: ${error.message}`, 'error');
    renderError(error.message);
  }
}

/**
 * 应用过滤器
 */
function applyFilters() {
  const searchTerm = document.getElementById('search').value.toLowerCase();
  const filterType = document.getElementById('filter').value;
  
  filteredSessions = allSessions.filter(session => {
    // 搜索过滤
    if (searchTerm && !session.player_id.toLowerCase().includes(searchTerm)) {
      return false;
    }
    
    // 类型过滤
    if (filterType === 'punishment' && !session.pending_punishment) {
      return false;
    }
    if (filterType === 'success' && !session.daily_success_achieved) {
      return false;
    }
    
    return true;
  });
}

/**
 * 更新统计数据
 */
function updateStatistics() {
  const total = allSessions.length;
  const active = allSessions.filter(s => {
    const lastModified = s.last_modified || 0;
    const hourAgo = Date.now() / 1000 - 3600;
    return lastModified > hourAgo;
  }).length;
  const punishment = allSessions.filter(s => s.pending_punishment).length;
  const success = allSessions.filter(s => s.daily_success_achieved).length;
  
  document.getElementById('stat-total').textContent = total;
  document.getElementById('stat-active').textContent = active;
  document.getElementById('stat-punishment').textContent = punishment;
  document.getElementById('stat-success').textContent = success;
}

/**
 * 渲染会话列表
 */
function renderSessions() {
  const tbody = document.getElementById('sessions');
  
  if (filteredSessions.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5">
          <div class="empty-state">
            <p>😔 没有找到符合条件的会话</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }
  
  tbody.innerHTML = '';
  
  filteredSessions.forEach(session => {
    const tr = document.createElement('tr');
    
    // 玩家ID
    const tdId = document.createElement('td');
    tdId.innerHTML = `<div class="player-id" title="${session.player_id}">${session.player_id}</div>`;
    tr.appendChild(tdId);
    
    // 最近活动
    const tdTime = document.createElement('td');
    tdTime.innerHTML = `
      <div class="timestamp" title="${formatTime(session.last_modified)}">
        ${formatRelativeTime(session.last_modified)}
      </div>
    `;
    tr.appendChild(tdTime);
    
    // 状态
    const tdStatus = document.createElement('td');
    const badges = [];
    if (session.daily_success_achieved) {
      badges.push('<span class="badge badge-success">今日成功</span>');
    }
    if (session.pending_punishment) {
      badges.push('<span class="badge badge-danger">待惩罚</span>');
    }
    const lastModified = session.last_modified || 0;
    const hourAgo = Date.now() / 1000 - 3600;
    if (lastModified > hourAgo) {
      badges.push('<span class="badge badge-info">活跃</span>');
    }
    tdStatus.innerHTML = badges.join(' ') || '-';
    tr.appendChild(tdStatus);
    
    // 标记
    const tdMark = document.createElement('td');
    if (session.pending_punishment) {
      tdMark.innerHTML = `<small style="color: #e53e3e;">${JSON.stringify(session.pending_punishment)}</small>`;
    } else {
      tdMark.textContent = '-';
    }
    tr.appendChild(tdMark);
    
    // 操作
    const tdActions = document.createElement('td');
    tdActions.className = 'actions';
    tdActions.innerHTML = `
      <button class="btn btn-secondary btn-small" data-view="${session.encrypted_id || session.player_id}">
        👁️ 查看
      </button>
      <button class="btn btn-primary btn-small" data-opportunities="${session.encrypted_id || session.player_id}">
        🎲 机缘
      </button>
      <button class="btn btn-danger btn-small" data-clear="${session.encrypted_id || session.player_id}">
        🗑️ 清空
      </button>
    `;
    tr.appendChild(tdActions);
    
    tbody.appendChild(tr);
  });
}

/**
 * 渲染错误信息
 */
function renderError(message) {
  const tbody = document.getElementById('sessions');
  tbody.innerHTML = `
    <tr>
      <td colspan="5">
        <div class="empty-state" style="color: #f56565;">
          <p>❌ ${message}</p>
        </div>
      </td>
    </tr>
  `;
}

/**
 * 显示会话详情
 */
async function showDetail(idOrEnc) {
  try {
    const detail = await fetchJSON(`/api/admin/session/${encodeURIComponent(idOrEnc)}`);
    const detailDiv = document.getElementById('detail');
    
    // 语法高亮的JSON
    const jsonStr = JSON.stringify(detail, null, 2);
    detailDiv.innerHTML = `<pre style="margin: 0;">${escapeHtml(jsonStr)}</pre>`;
    
    // 滚动到详情面板
    detailDiv.parentElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    
    showNotification('会话详情加载成功', 'success');
  } catch (error) {
    console.error('加载详情失败:', error);
    showNotification(`加载详情失败: ${error.message}`, 'error');
    document.getElementById('detail').innerHTML = `
      <div class="empty-state" style="color: #f56565;">
        <p>❌ 加载失败: ${escapeHtml(error.message)}</p>
      </div>
    `;
  }
}

/**
 * 清空会话
 */
async function clearSession(idOrEnc) {
  if (!confirm('确定要清空这个会话吗？此操作不可撤销！')) {
    return;
  }
  
  try {
    await fetchJSON(`/api/admin/sessions/${encodeURIComponent(idOrEnc)}/clear`, {
      method: 'POST'
    });
    
    showNotification('会话已清空', 'success');
    await loadSessions();
  } catch (error) {
    console.error('清空会话失败:', error);
    showNotification(`清空失败: ${error.message}`, 'error');
  }
}

/**
 * 修改机缘次数
 */
async function updateOpportunities(idOrEnc) {
  // 先获取当前会话信息
  try {
    const session = await fetchJSON(`/api/admin/session/${encodeURIComponent(idOrEnc)}`);
    const currentOpportunities = session.opportunities_remaining || 0;
    
    // 弹出输入框让管理员输入新的机缘次数
    const input = prompt(
      `修改用户机缘次数\n当前机缘次数: ${currentOpportunities}\n请输入新的机缘次数 (0-100):`,
      currentOpportunities.toString()
    );
    
    if (input === null) {
      return; // 用户取消了
    }
    
    const newOpportunities = parseInt(input, 10);
    
    // 验证输入
    if (isNaN(newOpportunities) || newOpportunities < 0 || newOpportunities > 100) {
      showNotification('请输入0到100之间的有效数字', 'error');
      return;
    }
    
    // 发送更新请求
    await fetchJSON(`/api/admin/sessions/${encodeURIComponent(idOrEnc)}/update-opportunities`, {
      method: 'POST',
      body: JSON.stringify(newOpportunities)
    });
    
    showNotification(`机缘次数已更新为 ${newOpportunities}`, 'success');
    await loadSessions(); // 重新加载会话列表
  } catch (error) {
    console.error('修改机缘次数失败:', error);
    showNotification(`修改失败: ${error.message}`, 'error');
  }
}

/**
 * HTML转义
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ==================== 事件绑定 ====================

/**
 * 绑定所有事件
 */
function bindEvents() {
  // 刷新按钮
  document.getElementById('refresh').addEventListener('click', () => {
    loadSessions();
  });
  
  // 搜索框
  document.getElementById('search').addEventListener('input', () => {
    applyFilters();
    renderSessions();
  });
  
  // 过滤器
  document.getElementById('filter').addEventListener('change', () => {
    applyFilters();
    renderSessions();
  });
  
  // 限制数量
  document.getElementById('limit').addEventListener('change', () => {
    loadSessions();
  });
  
  // 表格操作按钮
  document.getElementById('sessions').addEventListener('click', (e) => {
    const viewId = e.target.getAttribute('data-view');
    if (viewId) {
      showDetail(viewId);
      return;
    }
    
    const clearId = e.target.getAttribute('data-clear');
    if (clearId) {
      clearSession(clearId);
      return;
    }
    
    const opportunitiesId = e.target.getAttribute('data-opportunities');
    if (opportunitiesId) {
      updateOpportunities(opportunitiesId);
      return;
    }
  });
  
  // 键盘快捷键
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + R: 刷新
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
      e.preventDefault();
      loadSessions();
    }
    
    // Ctrl/Cmd + F: 聚焦搜索框
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
      e.preventDefault();
      document.getElementById('search').focus();
    }
  });
}

// ==================== 初始化 ====================

/**
 * 初始化应用
 */
async function init() {
  console.log('🎮 管理员后台初始化中...');
  
  // 绑定事件
  bindEvents();
  
  // 加载数据
  try {
    await loadSessions();
    console.log('✅ 管理员后台初始化完成');
  } catch (error) {
    console.error('❌ 初始化失败:', error);
    showNotification(`初始化失败: ${error.message}`, 'error');
  }
}

// 启动应用
init();
