// ==================== 高级编辑器功能 ====================

/**
 * 切换编辑标签页
 */
function switchEditTab(tabName) {
  // 更新标签按钮状态
  document.querySelectorAll('.tab-btn').forEach(btn => {
    if (btn.dataset.tab === tabName) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // 更新内容显示
  document.querySelectorAll('.tab-content').forEach(content => {
    if (content.id === `tab-${tabName}`) {
      content.classList.add('active');
    } else {
      content.classList.remove('active');
    }
  });
}

/**
 * 初始化惩罚编辑器
 */
function initPunishmentEditor(punishment) {
  const typeSelect = document.getElementById('edit-punishment-type');
  const valueInput = document.getElementById('edit-punishment-value');
  const customTextarea = document.getElementById('edit-punishment-custom');

  // 检查元素是否存在
  if (!typeSelect || !valueInput || !customTextarea) {
    console.warn('惩罚编辑器元素未找到');
    return;
  }

  // 重置显示
  valueInput.style.display = 'none';
  customTextarea.style.display = 'none';

  if (!punishment) {
    typeSelect.value = '';
  } else if (typeof punishment === 'object' && punishment.type === 'punishment') {
    typeSelect.value = 'punishment';
    valueInput.value = punishment.value || 1;
    valueInput.style.display = 'block';
  } else {
    typeSelect.value = 'custom';
    customTextarea.value = JSON.stringify(punishment, null, 2);
    customTextarea.style.display = 'block';
  }

  // 绑定切换事件
  typeSelect.onchange = function() {
    valueInput.style.display = 'none';
    customTextarea.style.display = 'none';

    if (this.value === 'punishment') {
      valueInput.style.display = 'block';
      valueInput.value = 1;
    } else if (this.value === 'custom') {
      customTextarea.style.display = 'block';
      customTextarea.value = '{"type": "custom", "description": "自定义惩罚"}';
    }
  };
}

/**
 * 初始化游戏状态编辑器
 */
function initGameStateEditor(gameState) {
  const editor = document.getElementById('game-state-editor');
  const textarea = document.getElementById('edit-game-state');

  // 检查元素是否存在
  if (!editor) {
    console.warn('游戏状态编辑器容器未找到');
    return;
  }

  editor.innerHTML = '';

  // 使用当前会话数据或创建空对象
  if (!gameState || typeof gameState !== 'object') {
    // 如果有当前编辑的会话，尝试使用它的数据
    if (window.currentEditingSession) {
      gameState = {
        session_date: window.currentEditingSession.session_date,
        is_in_trial: window.currentEditingSession.is_in_trial,
        is_processing: window.currentEditingSession.is_processing,
        unchecked_rounds_count: window.currentEditingSession.unchecked_rounds_count,
        current_life: window.currentEditingSession.current_life,
        internal_history: window.currentEditingSession.internal_history,
        display_history: window.currentEditingSession.display_history,
        roll_event: window.currentEditingSession.roll_event
      };
    } else {
      gameState = {};
    }
  }

  // 为每个字段创建编辑控件
  Object.entries(gameState).forEach(([key, value]) => {
    addGameStateField(key, value);
  });

  // 如果没有字段，显示提示
  if (Object.keys(gameState).length === 0) {
    editor.innerHTML = '<div style="color: #718096; padding: 10px;">暂无游戏状态数据，点击下方添加字段</div>';
  }

  // 添加"添加字段"按钮
  const addBtn = document.createElement('button');
  addBtn.type = 'button';
  addBtn.className = 'btn-small';
  addBtn.textContent = '添加字段';
  addBtn.onclick = () => addGameStateField();
  editor.appendChild(addBtn);

  // 更新隐藏的textarea（如果存在）
  if (textarea) {
    textarea.value = JSON.stringify(gameState, null, 2);
  }
}

/**
 * 添加游戏状态字段
 */
function addGameStateField(key = '', value = '') {
  const editor = document.getElementById('game-state-editor');

  // 清除空提示
  const emptyMsg = editor.querySelector('div[style*="color: #718096"]');
  if (emptyMsg) {
    emptyMsg.remove();
  }

  // 移除添加按钮（稍后重新添加到末尾）
  const addBtn = editor.querySelector('button.btn-small');
  if (addBtn) {
    addBtn.remove();
  }

  const field = document.createElement('div');
  field.className = 'json-field';

  // HTML转义函数
  const escapeHtml = (text) => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  // 根据值的类型创建不同的输入控件
  let valueInput = '';
  if (value === null || value === undefined) {
    valueInput = `<input type="text" placeholder="字段值" value="null" class="field-value">`;
  } else if (typeof value === 'object') {
    // 对于对象和数组，使用textarea显示JSON
    const jsonStr = JSON.stringify(value, null, 2);
    valueInput = `<textarea class="field-value" style="min-height: 100px; width: 100%; font-family: monospace; font-size: 12px;" placeholder="JSON格式的值">${escapeHtml(jsonStr)}</textarea>`;
  } else if (typeof value === 'boolean') {
    valueInput = `
      <select class="field-value">
        <option value="true" ${value === true ? 'selected' : ''}>true</option>
        <option value="false" ${value === false ? 'selected' : ''}>false</option>
      </select>`;
  } else {
    valueInput = `<input type="text" placeholder="字段值" value="${escapeHtml(String(value))}" class="field-value">`;
  }

  field.innerHTML = `
    <label style="display: inline-block; min-width: 150px; font-weight: bold;">${escapeHtml(key || '新字段')}</label>
    <input type="text" placeholder="字段名" value="${escapeHtml(key)}" class="field-key" style="margin-right: 10px; width: 150px;">
    ${valueInput}
    <button type="button" onclick="removeGameStateField(this)" style="margin-left: 10px;">删除</button>
  `;

  editor.appendChild(field);

  // 重新添加"添加字段"按钮
  const newAddBtn = document.createElement('button');
  newAddBtn.type = 'button';
  newAddBtn.className = 'btn-small';
  newAddBtn.textContent = '添加字段';
  newAddBtn.onclick = () => addGameStateField();
  editor.appendChild(newAddBtn);

  updateGameStateTextarea();
}

/**
 * 删除游戏状态字段
 */
window.removeGameStateField = function(btn) {
  btn.parentElement.remove();
  updateGameStateTextarea();
}

/**
 * 更新游戏状态textarea
 */
function updateGameStateTextarea() {
  const editor = document.getElementById('game-state-editor');
  const textarea = document.getElementById('edit-game-state');

  if (!editor) {
    console.warn('游戏状态编辑器未找到');
    return;
  }

  const gameState = {};
  let fieldCount = 0;

  editor.querySelectorAll('.json-field').forEach(field => {
    const keyInput = field.querySelector('.field-key');
    const valueInput = field.querySelector('.field-value');

    if (!keyInput || !valueInput) return;

    const key = keyInput.value.trim();

    if (key) {
      fieldCount++;
      let parsedValue;

      // 根据输入类型处理值
      if (valueInput.tagName === 'TEXTAREA') {
        // 对于textarea，尝试解析为JSON
        const value = valueInput.value.trim();
        try {
          parsedValue = JSON.parse(value);
        } catch (e) {
          // 如果解析失败，保留原始字符串
          parsedValue = value;
        }
      } else if (valueInput.tagName === 'SELECT') {
        // 对于select，获取选中的值并转换为布尔值
        parsedValue = valueInput.value === 'true';
      } else {
        // 对于普通input，进行类型推断
        const value = valueInput.value.trim();
        if (value === 'true') parsedValue = true;
        else if (value === 'false') parsedValue = false;
        else if (value === 'null') parsedValue = null;
        else if (value === 'undefined') parsedValue = undefined;
        else if (!isNaN(value) && value !== '') parsedValue = Number(value);
        else parsedValue = value;
      }

      gameState[key] = parsedValue;
    }
  });

  console.log(`[游戏状态更新] 收集了 ${fieldCount} 个字段:`, gameState);

  // 只在textarea存在时更新
  if (textarea) {
    textarea.value = JSON.stringify(gameState, null, 2);
    console.log('[游戏状态更新] 已更新textarea内容');
  } else {
    console.warn('[游戏状态更新] textarea元素未找到');
  }
}

/**
 * 初始化试炼历史编辑器
 */
function initTrialHistoryEditor(trialHistory) {
  const editor = document.getElementById('trial-history-editor');
  const textarea = document.getElementById('edit-trial-history');

  // 检查元素是否存在
  if (!editor) {
    console.warn('试炼历史编辑器容器未找到');
    return;
  }

  // textarea 不是必需的，只用作内部数据存储

  editor.innerHTML = '';

  if (!Array.isArray(trialHistory)) {
    trialHistory = [];
  }

  // 为每个历史记录创建编辑控件
  trialHistory.forEach((trial, index) => {
    addTrialHistoryItem(trial, index);
  });

  // 如果没有历史，显示提示
  if (trialHistory.length === 0) {
    editor.innerHTML = '<div style="color: #718096; padding: 10px;">暂无试炼历史，点击"添加记录"创建新记录</div>';
  }

  // 更新隐藏的textarea（如果存在）
  if (textarea) {
    textarea.value = JSON.stringify(trialHistory, null, 2);
  }
}

/**
 * 添加试炼历史记录
 */
window.addTrialHistory = function() {
  const editor = document.getElementById('trial-history-editor');

  // 清除空提示
  const emptyMsg = editor.querySelector('div[style*="color: #718096"]');
  if (emptyMsg) {
    emptyMsg.remove();
  }

  const index = editor.children.length;
  const trial = {
    trial: index + 1,
    timestamp: Date.now(),
    result: 'pending'
  };

  addTrialHistoryItem(trial, index);
  updateTrialHistoryTextarea();
}

/**
 * 添加试炼历史项
 */
function addTrialHistoryItem(trial, index) {
  const editor = document.getElementById('trial-history-editor');

  const item = document.createElement('div');
  item.className = 'history-item';
  item.innerHTML = `
    <div class="history-item-header">
      <strong>试炼 #${index + 1}</strong>
      <button type="button" class="btn-small" style="background: #ef4444;" onclick="removeTrialHistory(${index})">删除</button>
    </div>
    <div class="json-field">
      <label>试炼编号</label>
      <input type="number" value="${trial.trial || index + 1}" data-field="trial">
    </div>
    <div class="json-field">
      <label>时间戳</label>
      <input type="number" value="${trial.timestamp || Date.now()}" data-field="timestamp">
    </div>
    <div class="json-field">
      <label>结果</label>
      <select data-field="result">
        <option value="success" ${trial.result === 'success' ? 'selected' : ''}>成功</option>
        <option value="failure" ${trial.result === 'failure' ? 'selected' : ''}>失败</option>
        <option value="pending" ${trial.result === 'pending' ? 'selected' : ''}>待定</option>
      </select>
    </div>
    <div class="json-field">
      <label>奖励</label>
      <input type="number" value="${trial.reward || 0}" data-field="reward" placeholder="0">
    </div>
    ${trial.description ? `
    <div class="json-field">
      <label>描述</label>
      <input type="text" value="${trial.description}" data-field="description">
    </div>
    ` : ''}
  `;

  editor.appendChild(item);
}

/**
 * 删除试炼历史
 */
window.removeTrialHistory = function(index) {
  const editor = document.getElementById('trial-history-editor');
  const items = editor.querySelectorAll('.history-item');

  if (items[index]) {
    items[index].remove();
    updateTrialHistoryTextarea();

    // 重新编号
    editor.querySelectorAll('.history-item').forEach((item, newIndex) => {
      const header = item.querySelector('.history-item-header strong');
      if (header) {
        header.textContent = `试炼 #${newIndex + 1}`;
      }
      const deleteBtn = item.querySelector('.history-item-header button');
      if (deleteBtn) {
        deleteBtn.setAttribute('onclick', `removeTrialHistory(${newIndex})`);
      }
    });
  }
}

/**
 * 更新试炼历史textarea
 */
function updateTrialHistoryTextarea() {
  const editor = document.getElementById('trial-history-editor');
  const textarea = document.getElementById('edit-trial-history');
  const trialHistory = [];

  editor.querySelectorAll('.history-item').forEach(item => {
    const trial = {};
    item.querySelectorAll('[data-field]').forEach(input => {
      const field = input.dataset.field;
      let value = input.value;

      // 类型转换
      if (input.type === 'number') {
        value = Number(value) || 0;
      }

      trial[field] = value;
    });
    trialHistory.push(trial);
  });

  textarea.value = JSON.stringify(trialHistory, null, 2);
}

/**
 * 初始化自定义字段编辑器
 */
function initCustomFieldsEditor(session) {
  const editor = document.getElementById('custom-fields-editor');

  // 检查元素是否存在
  if (!editor) {
    console.warn('自定义字段编辑器容器未找到');
    return;
  }

  editor.innerHTML = '';

  // 排除已知字段
  const knownFields = [
    'player_id', 'encrypted_id', 'opportunities_remaining', 'daily_success_achieved',
    'current_trial', 'trial_count', 'game_state', 'trial_history', 'pending_punishment',
    'last_modified'
  ];

  // 添加其他自定义字段
  Object.entries(session).forEach(([key, value]) => {
    if (!knownFields.includes(key)) {
      addCustomFieldItem(key, value);
    }
  });
}

/**
 * 添加自定义字段
 */
window.addCustomField = function() {
  const key = prompt('请输入字段名称:');
  if (key) {
    addCustomFieldItem(key, '');
  }
}

/**
 * 添加自定义字段项
 */
function addCustomFieldItem(key, value) {
  const editor = document.getElementById('custom-fields-editor');

  // HTML转义函数
  const escapeHtml = (text) => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  // 处理复杂数据类型
  let displayValue = value;
  let inputType = 'text';
  let inputElement = '';

  if (value === null || value === undefined) {
    displayValue = 'null';
  } else if (typeof value === 'object') {
    // 对于对象和数组，使用 textarea 显示 JSON
    displayValue = JSON.stringify(value, null, 2);
    inputElement = `<textarea data-custom-field="${escapeHtml(key)}" style="min-height: 100px; font-family: monospace; font-size: 12px;">${escapeHtml(displayValue)}</textarea>`;
  } else {
    // 对于基本类型，使用普通 input
    displayValue = String(value);
    inputElement = `<input type="text" value="${escapeHtml(displayValue)}" data-custom-field="${escapeHtml(key)}">`;
  }

  const field = document.createElement('div');
  field.className = 'json-field';
  field.innerHTML = `
    <label>${escapeHtml(key)}</label>
    ${inputElement}
    <button type="button" onclick="removeCustomField(this, '${escapeHtml(key)}')">删除</button>
  `;

  editor.appendChild(field);
}

/**
 * 删除自定义字段
 */
window.removeCustomField = function(btn, key) {
  if (confirm(`确定要删除字段 "${key}" 吗？`)) {
    btn.parentElement.remove();
  }
}

/**
 * 格式化游戏状态
 */
window.formatGameState = function() {
  updateGameStateTextarea();
  const textarea = document.getElementById('edit-game-state');
  try {
    const data = JSON.parse(textarea.value);
    textarea.value = JSON.stringify(data, null, 2);

    // 显示通知函数
    if (typeof showNotification === 'function') {
      showNotification('格式化成功', 'success');
    }
  } catch (e) {
    if (typeof showNotification === 'function') {
      showNotification('JSON格式错误', 'error');
    }
  }
}

/**
 * 美化JSON
 */
window.prettifyJSON = function() {
  const textarea = document.getElementById('edit-full-session');
  try {
    const data = JSON.parse(textarea.value);
    textarea.value = JSON.stringify(data, null, 2);

    if (typeof showNotification === 'function') {
      showNotification('美化成功', 'success');
    }
  } catch (e) {
    if (typeof showNotification === 'function') {
      showNotification('JSON格式错误: ' + e.message, 'error');
    }
  }
}

/**
 * 验证JSON
 */
window.validateJSON = function() {
  const textarea = document.getElementById('edit-full-session');
  const errorDiv = document.getElementById('json-error');

  try {
    JSON.parse(textarea.value);
    errorDiv.style.display = 'none';

    if (typeof showNotification === 'function') {
      showNotification('JSON格式正确', 'success');
    }
  } catch (e) {
    errorDiv.textContent = '错误: ' + e.message;
    errorDiv.style.display = 'block';

    if (typeof showNotification === 'function') {
      showNotification('JSON格式错误', 'error');
    }
  }
}

/**
 * 初始化编辑器事件监听
 */
function initEditorEvents() {
  // 绑定Tab切换事件
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      switchEditTab(btn.dataset.tab);
      // 切换到高级编辑标签时，确保更新textarea
      if (btn.dataset.tab === 'advanced') {
        updateGameStateTextarea();
        updateTrialHistoryTextarea();
      }
    });
  });

  // 监听游戏状态编辑器的变化
  document.addEventListener('input', (e) => {
    if (e.target.closest('#game-state-editor')) {
      updateGameStateTextarea();
    }
    if (e.target.closest('#trial-history-editor')) {
      updateTrialHistoryTextarea();
    }
  });

  // 监听游戏状态编辑器的change事件（用于select和textarea）
  document.addEventListener('change', (e) => {
    if (e.target.closest('#game-state-editor')) {
      updateGameStateTextarea();
    }
    if (e.target.closest('#trial-history-editor')) {
      updateTrialHistoryTextarea();
    }
  });
}

/**
 * 初始化current_life编辑器
 */
function initCurrentLifeEditor(currentLife) {
  // 查找current_life字段的编辑器
  const editor = document.getElementById('game-state-editor');
  if (!editor) return;

  // 查找current_life字段
  const fields = editor.querySelectorAll('.json-field');
  fields.forEach(field => {
    const keyInput = field.querySelector('.field-key');
    if (keyInput && keyInput.value === 'current_life') {
      // 为current_life创建更友好的编辑界面
      const valueInput = field.querySelector('.field-value');
      if (valueInput && valueInput.tagName === 'TEXTAREA') {
        // 添加辅助按钮
        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = 'margin-top: 5px;';

        const formatBtn = document.createElement('button');
        formatBtn.type = 'button';
        formatBtn.className = 'btn-small';
        formatBtn.textContent = '格式化';
        formatBtn.onclick = () => {
          try {
            const data = JSON.parse(valueInput.value);
            valueInput.value = JSON.stringify(data, null, 2);
          } catch (e) {
            alert('JSON格式错误: ' + e.message);
          }
        };

        const templateBtn = document.createElement('button');
        templateBtn.type = 'button';
        templateBtn.className = 'btn-small';
        templateBtn.textContent = '使用模板';
        templateBtn.onclick = () => {
          const template = {
            "姓名": "角色名称",
            "出身": "角色背景",
            "初始天赋": "天赋描述",
            "初始事件": "初始事件描述",
            "属性": {
              "筋骨": 50,
              "心境": 50,
              "机缘": 50,
              "慧根": 50,
              "福缘": 50,
              "胆魄": 50,
              "感知": 50
            },
            "生命值": 100,
            "最大生命值": 100,
            "灵石": 0,
            "物品": [],
            "状态效果": [],
            "位置": "起始位置",
            "故事事件": []
          };
          valueInput.value = JSON.stringify(template, null, 2);
          updateGameStateTextarea();
        };

        const validateBtn = document.createElement('button');
        validateBtn.type = 'button';
        validateBtn.className = 'btn-small';
        validateBtn.textContent = '验证结构';
        validateBtn.onclick = () => {
          try {
            const data = JSON.parse(valueInput.value);
            const requiredFields = ['姓名', '属性', '生命值', '最大生命值'];
            const missing = requiredFields.filter(field => !(field in data));

            if (missing.length > 0) {
              alert('缺少必需字段: ' + missing.join(', '));
            } else {
              alert('结构验证通过！');
            }
          } catch (e) {
            alert('JSON格式错误: ' + e.message);
          }
        };

        buttonContainer.appendChild(formatBtn);
        buttonContainer.appendChild(templateBtn);
        buttonContainer.appendChild(validateBtn);

        // 在textarea后面添加按钮容器
        valueInput.parentNode.insertBefore(buttonContainer, valueInput.nextSibling);
      }
    }
  });
}

// 导出函数供主文件使用
window.editorFunctions = {
  switchEditTab,
  initPunishmentEditor,
  initGameStateEditor,
  initTrialHistoryEditor,
  initCustomFieldsEditor,
  initCurrentLifeEditor,
  initEditorEvents,
  updateGameStateTextarea,
  updateTrialHistoryTextarea
};