---
title: "OBBDemo 快速开始指南"
description: "5分钟快速上手 OBBDemo - 安装、运行和基本使用"
type: "教程"
status: "完成"
priority: "高"
created_date: "2025-12-20"
last_updated: "2025-12-20"
related_documents:
  - "docs/development/setup.md"
  - "docs/api/data-format.md"
related_code:
  - "sender.cpp"
  - "recv.py"
---

# OBBDemo 快速开始指南

## 5 分钟快速启动

### Step 1: 安装依赖 (2 分钟)

**Python 端**:
```bash
pip install pyzmq pygame PyOpenGL numpy bson
```

**C++ 端**:
```bash
# Ubuntu
sudo apt install libzmq3-dev nlohmann-json3-dev
```

详细安装指南见 [开发环境配置](../development/setup.md)。

---

### Step 2: 运行发送端 (1 分钟)

**编译 C++ sender**:
```bash
cd /path/to/OBBDemo
g++ -std=c++11 sender.cpp -o sender -lzmq
```

**运行**:
```bash
./sender
```

**预期输出**:
```
Send OBB 0
Send OBB 1
Send OBB 2
...
```

---

### Step 3: 运行接收端 (2 分钟)

**运行 Python receiver**:
```bash
python3 recv.py -a localhost:5555 -m n
```

**参数说明**:
- `-a localhost:5555`: 连接地址（IP:PORT）
- `-m n`: 数据模式（n = normal, c = compressed）

**预期效果**:
- 打开 800x600 的 OpenGL 窗口
- 显示白色线框立方体
- 实时更新（每 100ms）

---

## 命令行参数

### recv.py 参数

```bash
python3 recv.py -a <IP:PORT> [-m <MODE>] [-d]
```

| 参数 | 简写 | 说明 | 默认值 | 必需 |
|------|------|------|--------|------|
| `--address` | `-a` | 连接地址（IP:PORT）| 无 | ✅ |
| `--mode` | `-m` | 数据模式（n/c）| n | ❌ |
| `--debug` | `-d` | 调试模式 | 关闭 | ❌ |

**示例**:
```bash
# 普通模式，本地连接
python3 recv.py -a localhost:5555 -m n

# 压缩模式，远程连接
python3 recv.py -a 192.168.1.100:5555 -m c

# 启用调试
python3 recv.py -a localhost:5555 -d
```

---

## 使用场景

### 场景 1: 本地开发和调试

**配置**:
- Sender: `tcp://*:5555`
- Receiver: `-a localhost:5555 -m n`

**优势**:
- 低延迟
- 无网络配置
- 便于调试

---

### 场景 2: 局域网多机演示

**配置**:
- Sender (IP: 192.168.1.100): `tcp://*:5555`
- Receiver: `-a 192.168.1.100:5555 -m c`

**优势**:
- 支持多个接收端同时连接
- 压缩模式节省带宽

---

### 场景 3: 压缩数据传输

**配置**:
- Receiver: `-a <IP>:5555 -m c`

**适用于**:
- 大量 OBB 数据（>100 个）
- 包含点云数据
- 低带宽网络

**注意**: 当前 sender.cpp 未实现压缩发送，需自行修改。

---

## 键盘和鼠标控制

**当前版本**: 固定视角（无交互控制）

**计划支持**（见 TASK.md § 任务 11）:
- `F1-F4`: 切换相机视角
- 鼠标拖拽: 旋转视角
- 滚轮: 缩放

---

## 故障排查

### 问题 1: 接收端窗口空白

**可能原因**:
1. Sender 未启动
2. IP:PORT 配置错误
3. 网络不通

**解决步骤**:
```bash
# 1. 检查 sender 是否运行
ps aux | grep sender

# 2. 检查端口监听
netstat -an | grep 5555

# 3. 测试网络连通性
ping <sender_ip>
```

---

### 问题 2: 数据不更新

**可能原因**:
- ZMQ "慢连接者"问题（见 KNOWLEDGE.md § 问题 3）

**解决方案**:
1. 先启动 sender
2. 等待 1 秒
3. 启动 receiver

---

### 问题 3: 帧率过低

**可能原因**:
- OBB 数量过多（>1000）
- 硬件性能不足

**解决方案**:
- 减少 sender 发送的 OBB 数量
- 使用压缩模式（`-m c`）
- 降低发送频率

---

## 下一步

- 查看 [数据格式规范](../api/data-format.md) 了解如何自定义数据
- 查看 [系统架构](../architecture/system-design.md) 理解系统设计
- 查看 [TASK.md](../../docs/management/TASK.md) 了解计划功能
