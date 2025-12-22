# 修复验证测试计划

## 修复内容

1. **问题 1**: 模式不匹配时的友好错误提示
2. **问题 2**: 文本模式下 zmq.error.Again 异常处理

## 测试场景

### 场景 1: Normal Mode 正常工作（回归测试）
**目的**: 确保修复没有破坏正常功能

**步骤**:
```bash
# Terminal 1: 启动发送端（normal mode）
cd /home/hao/Workspace/Learn/Exercise/OBBViewer/build
./sendOBB -m n -n 40

# Terminal 2: 启动接收端（normal mode）
cd /home/hao/Workspace/Learn/Exercise/OBBViewer
uv run python recvOBB.py -a localhost:5555 -m n
```

**预期结果**:
- ✅ 接收端成功接收并显示 41 个 OBB（40 obs + 1 sprWarn）
- ✅ 发送端发送完数据后退出
- ✅ 接收端不再崩溃，而是继续等待新数据（或用户按 Ctrl+C 退出）
- ✅ 退出时显示接收统计信息

---

### 场景 2: 模式不匹配友好错误提示
**目的**: 验证模式不匹配时的错误提示

**步骤**:
```bash
# Terminal 1: 启动发送端（compressed mode）
cd /home/hao/Workspace/Learn/Exercise/OBBViewer/build
./sendOBB -m c -n 5

# Terminal 2: 启动接收端（normal mode - 错误的模式）
cd /home/hao/Workspace/Learn/Exercise/OBBViewer
uv run python recvOBB.py -a localhost:5555 -m n
```

**预期结果**:
- ✅ 接收端检测到 UnicodeDecodeError
- ✅ 显示友好的错误信息：
  ```
  ❌ 错误: 无法解码数据为 UTF-8
  可能原因: 发送端使用了压缩模式 (-m c)，但接收端使用了普通模式 (-m n)
  解决方案: 确保发送端和接收端的 -m 参数一致
    示例: ./sendOBB -m n  配合  python recvOBB.py -a localhost:5555 -m n
  ```
- ✅ 抛出 RuntimeError 并终止（避免后续错误）

---

### 场景 3: Compressed Mode 正常工作（回归测试）
**目的**: 确保压缩模式仍然正常工作

**步骤**:
```bash
# Terminal 1: 启动发送端（compressed mode）
cd /home/hao/Workspace/Learn/Exercise/OBBViewer/build
./sendOBB -m c -n 10

# Terminal 2: 启动接收端（compressed mode）
cd /home/hao/Workspace/Learn/Exercise/OBBViewer
uv run python recvOBB.py -a localhost:5555 -m c
```

**预期结果**:
- ✅ 接收端成功接收并显示 11 个 OBB（10 obs + 1 sprWarn）
- ✅ 显示压缩统计信息（压缩率等）
- ✅ 接收端不崩溃

---

## 验证检查清单

- [ ] 场景 1: Normal mode 正常工作
- [ ] 场景 2: 模式不匹配友好错误提示
- [ ] 场景 3: Compressed mode 正常工作
- [ ] 接收端在发送端退出后不崩溃
- [ ] 错误信息清晰且有帮助

## 附加说明

### 关于 OBB 数量
- **预期行为**: `-n 40` 会生成 41 个 OBB（40 obs + 1 sprWarn）
- **原因**: 这符合 LCPS 设计，sprWarn 是额外添加的警告区域
- **不是 bug**: 如果用户只想要 40 个 OBB，应该使用 `-n 39`
