---
title: "OBBDemo 二进制发布和部署指南"
description: "使用 PyInstaller 构建跨平台二进制文件的完整指南"
type: "教程"
status: "完成"
priority: "中"
created_date: "2025-12-21"
last_updated: "2025-12-21"
related_documents:
  - "docs/development/setup.md"
  - "docs/management/PLANNING.md"
related_code:
  - "LCPSViewer.spec"
  - "pyproject.toml"
tags: ["deployment", "pyinstaller", "binary", "distribution"]
---

# OBBDemo 二进制发布和部署指南

本文档说明如何使用 PyInstaller 将 OBBDemo 打包为跨平台的独立可执行文件。

---

## 前置要求

### 系统要求

| 平台 | 要求 | 状态 |
|------|------|------|
| **Linux** | Ubuntu 18.04+ / 类似发行版 | ✅ 已测试 |
| **Windows** | Windows 10+ | ✅ 已测试 |
| **macOS** | 10.14+ | ⚠️ 未测试 |

### 软件依赖

- Python 3.13+
- uv（推荐）或 pip
- 所有项目依赖（通过 pyproject.toml 安装）

---

## 快速开始

### Step 1: 安装依赖

**使用 uv（推荐）**:
```bash
# 安装 uv（如果未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 同步项目依赖
uv sync

# 安装开发依赖（包括 PyInstaller）
uv sync --group dev
```

**使用 pip**:
```bash
pip install -e ".[dev]"
```

### Step 2: 构建可执行文件

```bash
# 激活虚拟环境
uv run pyinstaller LCPSViewer.spec

# 或使用传统方式
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate.bat  # Windows
pyinstaller LCPSViewer.spec
```

### Step 3: 测试可执行文件

```bash
# Linux
./dist/LCPSViewer -a localhost:5555 -m n

# Windows
dist\LCPSViewer.exe -a localhost:5555 -m n
```

---

## 构建配置详解

### LCPSViewer.spec 配置

项目使用 PyInstaller 的 `.spec` 文件进行精细化配置：

```python
# LCPSViewer.spec
a = Analysis(
    ['LCPSViewer.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'OpenGL.GL',
        'OpenGL.GLU',
        'pygame',
        'bson',
        'zmq',
    ],
    ...
)
```

**关键配置项**:

| 配置项 | 说明 | 值 |
|-------|------|-----|
| `hiddenimports` | 手动指定隐式导入的模块 | OpenGL.GL, pygame, bson, zmq 等 |
| `console` | 是否显示控制台窗口 | True（便于查看日志）|
| `onefile` | 是否打包为单文件 | True |

### 常见问题

#### 问题 1: PyInstaller 找不到 OpenGL 模块

**症状**: `ModuleNotFoundError: No module named 'OpenGL.GL'`

**解决方案**:
1. 确认 LCPSViewer.spec 中包含 `hiddenimports=['OpenGL.GL', 'OpenGL.GLU']`
2. 使用 `--collect-all PyOpenGL` 参数重新打包:
   ```bash
   pyinstaller --collect-all PyOpenGL LCPSViewer.spec
   ```

#### 问题 2: Windows 下缺少 DLL 文件

**症状**: 运行时提示缺少 `vcruntime140.dll` 或 `msvcp140.dll`

**解决方案**:
- 安装 [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
- 或者手动复制 DLL 到 dist/ 目录

#### 问题 3: 可执行文件体积过大

**当前**: ~40MB (Linux), ~45MB (Windows)

**优化方法**:
- 使用 `--exclude-module` 排除不必要的模块
- 使用 UPX 压缩（需安装 UPX）:
  ```bash
  pyinstaller --upx-dir=/path/to/upx LCPSViewer.spec
  ```

---

## 发布流程

### 手动发布

**Step 1: 构建所有平台**

在各个平台上分别执行：
```bash
# Linux
uv run pyinstaller LCPSViewer.spec
cp dist/LCPSViewer LCPSViewer-linux-x64

# Windows
uv run pyinstaller LCPSViewer.spec
copy dist\LCPSViewer.exe LCPSViewer-windows-x64.exe
```

**Step 2: 创建发布包**

```bash
# 打包所有文件
tar -czf OBBDemo-v0.1.0-linux-x64.tar.gz LCPSViewer-linux-x64
zip OBBDemo-v0.1.0-windows-x64.zip LCPSViewer-windows-x64.exe
```

**Step 3: 上传到 GitHub Releases**

1. 在 GitHub 上创建新的 Release
2. 上传打包好的文件
3. 添加发布说明和变更日志

### 自动化发布（GitHub Actions）

**TODO**: 待实现 CI/CD 流程（见 TASK.md § 计划任务）

建议使用 GitHub Actions 自动化构建：
```yaml
# .github/workflows/release.yml
name: Build and Release
on:
  push:
    tags:
      - 'v*'
jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v3
      - uses: astral-sh/setup-uv@v1
      - run: uv sync --group dev
      - run: uv run pyinstaller LCPSViewer.spec
      # 上传构建产物...
```

---

## 部署到目标环境

### Linux 部署

**直接运行**:
```bash
# 下载可执行文件
wget https://github.com/USER/OBBDemo/releases/download/v0.1.0/OBBDemo-v0.1.0-linux-x64.tar.gz

# 解压
tar -xzf OBBDemo-v0.1.0-linux-x64.tar.gz

# 添加执行权限
chmod +x LCPSViewer-linux-x64

# 运行
./LCPSViewer-linux-x64 -a localhost:5555
```

**安装到系统路径**（可选）:
```bash
sudo cp LCPSViewer-linux-x64 /usr/local/bin/obbdemo
sudo chmod +x /usr/local/bin/obbdemo

# 现在可以在任何地方运行
obbdemo -a localhost:5555
```

### Windows 部署

1. 下载 `.zip` 文件
2. 解压到任意目录
3. 双击运行 `LCPSViewer-windows-x64.exe`
4. 或在 PowerShell 中运行:
   ```powershell
   .\LCPSViewer-windows-x64.exe -a localhost:5555
   ```

---

## 验证和测试

### 功能测试清单

- [ ] 可执行文件启动正常
- [ ] 命令行参数解析正确
- [ ] ZMQ 连接正常
- [ ] OpenGL 渲染正常
- [ ] 压缩模式工作正常
- [ ] 日志输出正确

### 性能测试

- 启动时间: < 3 秒
- 内存占用: ~50-80 MB
- FPS (100 OBB): 60+ FPS

---

## 最佳实践

1. **版本管理**: 在文件名中包含版本号（如 `v0.1.0`）
2. **哈希校验**: 发布时提供 SHA256 哈希值
3. **发布说明**: 包含变更日志和已知问题
4. **测试**: 在目标平台上充分测试再发布
5. **回滚**: 保留历史版本以便回滚

---

## 相关文档

- [开发环境配置](../development/setup.md) - 开发环境搭建
- [快速开始指南](../usage/quick-start.md) - 基本使用方法
- [项目规划](../management/PLANNING.md) - 架构和技术栈

---

**维护者**: 项目团队
**最后更新**: 2025-12-21
