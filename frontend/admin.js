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
  // 渲染桌面端表格
  renderDesktopTable();
  
  // 渲染移动端卡片
  renderMobileCards();
}

/**
 * 渲染桌面端表格
 */
function renderDesktopTable() {
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
    const badges = getSessionBadges(session);
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
      <button class="btn btn-primary btn-small" data-edit="${session.encrypted_id || session.player_id}">
        ✏️ 编辑
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
 * 渲染移动端卡片
 */
function renderMobileCards() {
  const container = document.getElementById('mobile-sessions');
  
  if (filteredSessions.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>😔 没有找到符合条件的会话</p>
      </div>
    `;
    return;
  }
  
  container.innerHTML = '';
  
  filteredSessions.forEach(session => {
    const card = document.createElement('div');
    card.className = 'mobile-card';
    
    const badges = getSessionBadges(session);
    const punishmentInfo = session.pending_punishment
      ? `<div style="color: #e53e3e; font-size: 11px; margin-top: 8px;">
          惩罚: ${JSON.stringify(session.pending_punishment)}
        </div>`
      : '';
    
    card.innerHTML = `
      <div class="mobile-card-header">
        <div class="mobile-card-id">${session.player_id}</div>
        <div class="mobile-card-time">${formatRelativeTime(session.last_modified)}</div>
      </div>
      <div class="mobile-card-badges">
        ${badges.join(' ')}
      </div>
      ${punishmentInfo}
      <div class="mobile-card-actions">
        <button class="btn btn-secondary btn-small" data-view="${session.encrypted_id || session.player_id}">
          👁️ 查看
        </button>
        <button class="btn btn-primary btn-small" data-edit="${session.encrypted_id || session.player_id}">
          ✏️ 编辑
        </button>
        <button class="btn btn-danger btn-small" data-clear="${session.encrypted_id || session.player_id}">
          🗑️ 清空
        </button>
      </div>
    `;
    
    container.appendChild(card);
  });
}

/**
 * 获取会话的徽章
 */
function getSessionBadges(session) {
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
  return badges;
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

// 存储当前查看的会话ID
let currentViewingId = null;

/**
 * 显示会话详情
 */
async function showDetail(idOrEnc) {
  try {
    currentViewingId = idOrEnc;
    const detail = await fetchJSON(`/api/admin/session/${encodeURIComponent(idOrEnc)}`);
    const detailDiv = document.getElementById('detail');
    
    // 语法高亮的JSON，确保在移动端也能正确显示
    const jsonStr = JSON.stringify(detail, null, 2);
    detailDiv.innerHTML = `<pre style="margin: 0; white-space: pre-wrap; word-wrap: break-word;">${escapeHtml(jsonStr)}</pre>`;
    
    // 显示编辑按钮
    const editBtn = document.getElementById('detail-edit-btn');
    if (editBtn) {
      editBtn.style.display = 'inline-flex';
    }
    
    // 在移动端自动展开详情面板
    if (window.innerWidth <= 768) {
      const panel = document.getElementById('detail-panel');
      const button = document.getElementById('mobile-detail-toggle');
      if (panel && panel.classList.contains('mobile-collapsed')) {
        panel.classList.remove('mobile-collapsed');
        if (button) {
          button.textContent = '📋 隐藏详情面板';
        }
      }
    }
    
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
 * 编辑当前查看的会话
 */
window.editCurrentSession = function() {
  if (currentViewingId) {
    openEditModal(currentViewingId);
  } else {
    showNotification('请先查看一个会话', 'warning');
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

// ==================== 编辑功能 ====================

let currentEditingId = null;
let currentEditingSession = null;

/**
 * 打开编辑对话框
 */
async function openEditModal(idOrEnc) {
  if (!idOrEnc) {
    showNotification('编辑会话ID不能为空', 'error');
    return;
  }

  try {
    currentEditingId = idOrEnc;
    currentEditingSession = null; // 重置当前编辑的会话数据

    // 获取会话详情
    const session = await fetchJSON(`/api/admin/session/${encodeURIComponent(idOrEnc)}`);
    currentEditingSession = session; // 保存当前会话数据

    // 重置到基础信息标签页（使用editorFunctions）
    if (window.editorFunctions) {
      window.editorFunctions.switchEditTab('basic');
    }

    // 填充基本字段
    document.getElementById('edit-player-id').value = session.player_id || '';
    document.getElementById('edit-opportunities').value = session.opportunities_remaining || 0;
    document.getElementById('edit-daily-success').value = session.daily_success_achieved ? 'true' : 'false';
    document.getElementById('edit-current-trial').value = session.current_trial || 1;
    document.getElementById('edit-trial-count').value = session.trial_count || 0;

    // 使用高级编辑器功能（如果可用）
    if (window.editorFunctions) {
      // 初始化惩罚编辑器
      window.editorFunctions.initPunishmentEditor(session.pending_punishment);

      // 初始化游戏状态编辑器
      window.editorFunctions.initGameStateEditor(session.game_state);

      // 初始化试炼历史编辑器
      window.editorFunctions.initTrialHistoryEditor(session.trial_history);

      // 初始化自定义字段编辑器
      window.editorFunctions.initCustomFieldsEditor(session);
    }

    // 填充完整会话JSON
    document.getElementById('edit-full-session').value = JSON.stringify(session, null, 2);

    // 显示对话框
    document.getElementById('edit-modal').classList.add('active');
  } catch (error) {
    console.error('打开编辑对话框失败:', error);
    showNotification(`打开编辑失败: ${error.message}`, 'error');
  }
}

/**
 * 关闭编辑对话框
 */
window.closeEditModal = function() {
  document.getElementById('edit-modal').classList.remove('active');
  currentEditingId = null;
}

/**
 * 保存编辑
 */
async function saveEdit(e) {
  e.preventDefault();

  if (!currentEditingId) {
    showNotification('编辑会话ID丢失', 'error');
    return;
  }

  // 保存ID副本，因为closeEditModal会清空它
  const editingId = currentEditingId;

  try {
    let updates = {};

    // 检查是否使用完整会话JSON
    const fullSessionText = document.getElementById('edit-full-session').value.trim();
    if (fullSessionText) {
      try {
        updates = JSON.parse(fullSessionText);
        // 移除不应该被修改的字段
        delete updates.player_id;
        delete updates.encrypted_id;
      } catch (e) {
        showNotification('完整会话JSON格式错误', 'error');
        return;
      }
    } else {
      // 收集各个字段
      const opportunities = parseInt(document.getElementById('edit-opportunities').value);
      if (!isNaN(opportunities)) {
        updates.opportunities_remaining = opportunities;
      }

      updates.daily_success_achieved = document.getElementById('edit-daily-success').value === 'true';

      const currentTrial = parseInt(document.getElementById('edit-current-trial').value);
      if (!isNaN(currentTrial)) {
        updates.current_trial = currentTrial;
      }

      const trialCount = parseInt(document.getElementById('edit-trial-count').value);
      if (!isNaN(trialCount)) {
        updates.trial_count = trialCount;
      }

      // 处理游戏状态
      const gameStateText = document.getElementById('edit-game-state').value.trim();
      if (gameStateText) {
        try {
          updates.game_state = JSON.parse(gameStateText);
        } catch (e) {
          showNotification('游戏状态JSON格式错误', 'error');
          return;
        }
      }

      // 处理试炼历史
      const trialHistoryText = document.getElementById('edit-trial-history').value.trim();
      if (trialHistoryText) {
        try {
          updates.trial_history = JSON.parse(trialHistoryText);
        } catch (e) {
          showNotification('试炼历史JSON格式错误', 'error');
          return;
        }
      }

      // 处理惩罚字段（从新的编辑器收集）
      const punishmentType = document.getElementById('edit-punishment-type').value;
      if (punishmentType === 'punishment') {
        const punishmentValue = parseInt(document.getElementById('edit-punishment-value').value);
        updates.pending_punishment = { type: 'punishment', value: punishmentValue || 1 };
      } else if (punishmentType === 'custom') {
        const punishmentText = document.getElementById('edit-punishment-custom').value.trim();
        if (punishmentText) {
          try {
            updates.pending_punishment = JSON.parse(punishmentText);
          } catch (e) {
            showNotification('惩罚字段JSON格式错误', 'error');
            return;
          }
        }
      } else {
        updates.pending_punishment = null;
      }

      // 处理自定义字段（从高级编辑器收集）
      const customFields = document.querySelectorAll('[data-custom-field]');
      customFields.forEach(input => {
        const key = input.dataset.customField;
        const value = input.value.trim();
        if (key && value) {
          // 尝试解析值类型
          let parsedValue = value;
          if (value === 'true') parsedValue = true;
          else if (value === 'false') parsedValue = false;
          else if (!isNaN(value) && value !== '') parsedValue = Number(value);

          updates[key] = parsedValue;
        }
      });
    }

    // 发送更新请求
    await fetchJSON(`/api/admin/sessions/${encodeURIComponent(editingId)}/update`, {
      method: 'POST',
      body: JSON.stringify(updates)
    });

    showNotification('会话更新成功', 'success');
    closeEditModal();

    // 重新加载列表
    await loadSessions();

    // 如果正在查看这个会话，刷新详情
    if (currentViewingId === editingId) {
      await showDetail(editingId);
    }
  } catch (error) {
    console.error('保存编辑失败:', error);
    showNotification(`保存失败: ${error.message}`, 'error');
  }
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
  
  // 表格操作按钮（桌面端）
  document.getElementById('sessions').addEventListener('click', handleActionClick);
  
  // 移动端卡片操作按钮
  document.getElementById('mobile-sessions').addEventListener('click', handleActionClick);
  
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
  
  // 绑定编辑表单提交事件
  const editForm = document.getElementById('edit-form');
  if (editForm) {
    editForm.addEventListener('submit', saveEdit);
  }
  
  // 点击模态框背景关闭
  const modal = document.getElementById('edit-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeEditModal();
      }
    });
  }
}

/**
 * 处理操作按钮点击
 */
function handleActionClick(e) {
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
  
  const editId = e.target.getAttribute('data-edit');
  if (editId) {
    openEditModal(editId);
    return;
  }
}

/**
 * 切换移动端详情面板
 */
window.toggleMobileDetail = function() {
  const panel = document.getElementById('detail-panel');
  const button = document.getElementById('mobile-detail-toggle');
  
  // 只在移动端切换折叠状态
  if (window.innerWidth <= 768) {
    if (panel.classList.contains('mobile-collapsed')) {
      panel.classList.remove('mobile-collapsed');
      button.textContent = '📋 隐藏详情面板';
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } else {
      panel.classList.add('mobile-collapsed');
      button.textContent = '📋 查看详情面板';
    }
  }
}

/**
 * 初始化详情面板状态
 */
function initDetailPanel() {
  const panel = document.getElementById('detail-panel');
  const button = document.getElementById('mobile-detail-toggle');
  
  // 在移动端默认折叠详情面板
  if (window.innerWidth <= 768) {
    panel.classList.add('mobile-collapsed');
    if (button) {
      button.textContent = '📋 查看详情面板';
    }
  } else {
    // 桌面端确保详情面板可见
    panel.classList.remove('mobile-collapsed');
  }
}

// 监听窗口大小变化
window.addEventListener('resize', () => {
  initDetailPanel();
});

// ==================== 初始化 ====================

/**
 * 检查管理员权限
 */
async function checkAdminPermission() {
  try {
    const response = await fetchJSON('/api/admin/check-permission');
    return response;
  } catch (error) {
    console.error('检查权限失败:', error);
    return null;
  }
}

/**
 * 显示非管理员界面
 */
function showNonAdminView(username) {
  // 隐藏所有管理功能
  document.querySelector('.container').innerHTML = `
    <div class="header">
      <h1>🎮 浮生十梦 - 用户面板</h1>
      <p class="subtitle">欢迎回来，${escapeHtml(username)}</p>
    </div>
    
    <div class="main-panel">
      <div class="empty-state">
        <h2 style="color: #667eea; margin-bottom: 16px;">👋 您好，${escapeHtml(username)}</h2>
        <p style="color: #718096; font-size: 16px; line-height: 1.6;">
          您当前没有管理员权限。<br>
          如需访问管理功能，请联系系统管理员。
        </p>
        <div style="margin-top: 24px;">
          <a href="/" class="btn btn-primary">返回游戏</a>
        </div>
      </div>
    </div>
    
    <div class="detail-panel">
      <h3>📋 权限说明</h3>
      <div style="padding: 20px; color: #4a5568; line-height: 1.8;">
        <p><strong>管理员权限要求：</strong></p>
        <ul style="margin-left: 20px;">
          <li>信任等级达到要求</li>
          <li>或在管理员白名单中</li>
        </ul>
        <p style="margin-top: 16px;">
          如果您认为这是一个错误，请联系管理员核实您的权限设置。
        </p>
      </div>
    </div>
  `;
}

/**
 * 初始化应用
 */
async function init() {
  console.log('🎮 管理员后台初始化中...');
  
  // 首先检查权限
  const permissionInfo = await checkAdminPermission();
  
  if (!permissionInfo) {
    // 无法获取权限信息，可能未登录
    document.querySelector('.container').innerHTML = `
      <div class="header">
        <h1>🎮 浮生十梦 - 管理员后台</h1>
        <p class="subtitle">请先登录</p>
      </div>
      
      <div class="main-panel">
        <div class="empty-state">
          <h2 style="color: #f56565; margin-bottom: 16px;">⚠️ 未登录</h2>
          <p style="color: #718096; font-size: 16px; margin-bottom: 24px;">
            请先登录以访问管理后台
          </p>
          <a href="/api/login/linuxdo" class="btn btn-primary">前往登录</a>
        </div>
      </div>
    `;
    return;
  }
  
  // 检查是否有管理员权限
  if (!permissionInfo.is_admin) {
    showNonAdminView(permissionInfo.username);
    console.log(`用户 ${permissionInfo.username} 无管理员权限`);
    return;
  }
  
  // 有管理员权限，显示完整的管理界面
  console.log(`✅ 用户 ${permissionInfo.username} 已验证管理员权限`);
  
  // 可选：在页面上显示当前管理员信息
  const subtitle = document.querySelector('.header .subtitle');
  if (subtitle) {
    subtitle.textContent = `当前管理员：${permissionInfo.username} | 信任等级：${permissionInfo.trust_level}`;
  }
  
  // 绑定事件
  bindEvents();
  
  // 初始化详情面板状态
  initDetailPanel();

  // 初始化高级编辑器事件（如果可用）
  if (window.editorFunctions && window.editorFunctions.initEditorEvents) {
    window.editorFunctions.initEditorEvents();
  }

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
