# Python 完整版安装指南

## 步骤 1: 下载 Python

1. 访问 Python 官方网站：https://www.python.org/downloads/
2. 点击 "Download Python 3.12.x"（或最新稳定版本）
3. 下载完成后，运行安装程序

## 步骤 2: 安装 Python

**重要提示：** 在安装过程中，请务必勾选以下选项：

1. ✅ **勾选 "Add Python to PATH"** （这是最重要的步骤！）
2. 选择 "Customize installation"（自定义安装）
3. 在 "Optional Features" 页面，确保勾选：
   - ✅ pip
   - ✅ tcl/tk and IDLE
   - ✅ Python test suite
   - ✅ py launcher
   - ✅ for all users (requires admin privileges)

4. 在 "Advanced Options" 页面，建议勾选：
   - ✅ Install for all users
   - ✅ Associate files with Python
   - ✅ Create shortcuts for installed applications
   - ✅ Add Python to environment variables
   - ✅ Precompile standard library

5. 自定义安装位置（可选）：
   - 默认：`C:\Program Files\Python312\`
   - 或选择其他位置，如：`C:\Python312\`

6. 点击 "Install" 开始安装

## 步骤 3: 验证安装

安装完成后，打开新的命令提示符（CMD）或 PowerShell 窗口，运行以下命令验证：

```cmd
python --version
```

应该显示类似：`Python 3.12.x`

```cmd
pip --version
```

应该显示 pip 的版本信息

## 步骤 4: 安装项目依赖

在项目目录中运行：

```cmd
cd d:\bailai\TenCyclesofFate-master
pip install -r backend\requirements.txt
```

## 步骤 5: 运行项目

安装完成后，使用以下命令运行项目：

```cmd
run_windows.bat
```

或直接运行：

```cmd
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## 常见问题

### 问题 1: "python" 命令未找到

**解决方案：**
1. 重新安装 Python，确保勾选 "Add Python to PATH"
2. 或手动添加到 PATH：
   - 右键 "此电脑" → "属性" → "高级系统设置"
   - 点击 "环境变量"
   - 在 "系统变量" 中找到 "Path"，点击 "编辑"
   - 添加 Python 安装路径，例如：
     - `C:\Program Files\Python312\`
     - `C:\Program Files\Python312\Scripts\`

### 问题 2: pip 安装包失败

**解决方案：**
```cmd
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

### 问题 3: 权限问题

**解决方案：**
以管理员身份运行命令提示符或 PowerShell

## 卸载 Windows Store 版本的 Python（可选）

如果您想卸载 Windows Store 版本：

1. 打开 "设置" → "应用" → "应用和功能"
2. 搜索 "Python"
3. 找到 "Python 3.x (from Microsoft Store)"
4. 点击 "卸载"

## 下一步

安装完成后，请在新的命令提示符窗口中重新运行 `run_windows.bat` 脚本。