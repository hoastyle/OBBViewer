---
title: "OBBDemo 开发环境配置"
description: "开发环境搭建、依赖安装、编译构建和调试指南"
type: "教程"
status: "完成"
priority: "高"
created_date: "2025-12-20"
last_updated: "2025-12-20"
related_documents:
  - "docs/usage/quick-start.md"
  - "docs/management/PLANNING.md"
related_code:
  - "CMakeLists.txt"
  - "LCPSViewer.spec"
---

# OBBDemo 开发环境配置

## 系统要求

### 支持的操作系统

| 操作系统 | 版本 | 状态 |
|---------|------|------|
| **Ubuntu** | 18.04+ | ✅ 完全支持 |
| **Windows** | 10+ | ✅ 完全支持 |
| **macOS** | 10.14+ | ⚠️ 未测试（理论支持）|

### 硬件要求

- **CPU**: 2 核心+
- **RAM**: 2 GB+
- **GPU**: 支持 OpenGL 2.1+
- **网络**: 本地回环（localhost）或局域网

---

## Python 开发环境

### 1. 安装 Python

**推荐版本**: Python 3.7+

```bash
# Ubuntu
sudo apt update
sudo apt install python3 python3-pip

# macOS
brew install python3

# Windows
# 下载安装包: https://www.python.org/downloads/
```

### 2. 安装 Python 依赖

```bash
pip install pyzmq pygame PyOpenGL numpy bson zlib
```

**可选**（用于内存分析）:
```bash
pip install pympler
```

**依赖列表详解**:

| 包 | 用途 | 版本 |
|---|------|------|
| **pyzmq** | ZeroMQ Python 绑定 | latest |
| **pygame** | 窗口和事件管理 | latest |
| **PyOpenGL** | OpenGL 渲染 | latest |
| **numpy** | 数值计算 | latest |
| **bson** | 二进制序列化 | latest |
| **zlib** | 内置，数据压缩 | - |
| **pympler** | 内存分析（可选）| latest |

### 3. 验证安装

```bash
python3 -c "import zmq, pygame, OpenGL, numpy, bson; print('All dependencies OK')"
```

---

## C++ 开发环境

### 1. 安装编译工具

**Ubuntu**:
```bash
sudo apt install build-essential cmake g++
```

**Windows**:
- 安装 Visual Studio 2019+ 或 MinGW
- 安装 CMake: https://cmake.org/download/

**macOS**:
```bash
xcode-select --install
brew install cmake
```

### 2. 安装 C++ 依赖

**Ubuntu**:
```bash
sudo apt install libzmq3-dev nlohmann-json3-dev libtbb-dev
```

**依赖说明**:

| 库 | 用途 | 安装方式 |
|---|------|---------|
| **libzmq** | ZeroMQ 核心库 | `apt install libzmq3-dev` |
| **nlohmann/json** | JSON 序列化 | `apt install nlohmann-json3-dev` |
| **Intel TBB** | 并行计算（可选）| `apt install libtbb-dev` |

### 3. 初始化 cppzmq Submodule

**cppzmq 通过 Git Submodule 管理**，无需手动安装。

**首次克隆项目后，初始化 submodule**:
```bash
git submodule update --init --recursive
```

**说明**: cppzmq 是 header-only 库，CMake 会自动通过 `add_subdirectory(thirdparty/cppzmq)` 引入。

---

## 项目构建

### Python 接收端

**无需构建**，直接运行：
```bash
python3 recv.py -a localhost:5555 -m n
```

### C++ 发送端

**构建步骤**:
```bash
mkdir build && cd build
cmake ..
make
```

**运行**:
```bash
./sender
```

---

## IDE 配置

### VS Code 配置

**推荐扩展**:
- Python (Microsoft)
- C/C++ (Microsoft)
- CMake Tools

**配置文件** (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "/usr/bin/python3",
  "C_Cpp.default.configurationProvider": "ms-vscode.cmake-tools"
}
```

### PyCharm 配置

1. 打开项目目录
2. 配置 Python 解释器（File > Settings > Project > Python Interpreter）
3. 添加依赖包

---

## 打包和发布

### Python 打包（PyInstaller）

**安装 PyInstaller**:
```bash
pip install pyinstaller
```

**打包命令**:
```bash
pyinstaller LCPSViewer.spec
```

**输出目录**: `dist/LCPSViewer`

**Windows 注意事项**:
- 确保 OpenGL.dll 在系统路径中
- 可能需要添加 `--collect-all PyOpenGL` 参数

### C++ 发布

编译后的二进制文件位于 `build/sender`，可直接分发（需确保目标系统安装了 libzmq）。

---

## 常见问题

### 问题 1: ImportError: No module named 'OpenGL'

**解决方案**:
```bash
pip install PyOpenGL PyOpenGL_accelerate
```

### 问题 2: CMake 找不到 ZMQ

**解决方案**:
```bash
# 确保安装了 libzmq-dev
sudo apt install libzmq3-dev

# 或指定路径
cmake -DZMQ_DIR=/path/to/zmq ..
```

### 问题 3: Windows 下 pygame 窗口闪退

**原因**: 缺少 OpenGL 驱动

**解决方案**:
1. 更新显卡驱动
2. 安装 Mesa3D OpenGL 软件实现
