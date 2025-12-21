# CONTEXT.md

**最后会话**: 2025-12-21 14:30
**Git 基准**: commit 42a3eab

## 📍 上下文指针 (Context Pointers)

### 当前工作焦点
- **已完成**: sender 和 recv.py 的 rotation 数据格式对齐（四元数）✅
- **相关架构**: PLANNING.md § 技术栈 § 数据格式规范
- **相关知识**: KNOWLEDGE.md § 已知问题 § 压缩模式不可用问题记录

### 会话状态
- **Git commits (本次会话)**: 3 commits (7566a8c → fb695c0 → 42a3eab)
- **修改文件数**: 6 files (sender.cpp, recv.py, KNOWLEDGE.md, TASK.md, LCPSViewer.py, .gitignore)
- **主要变更领域**: 数据格式对齐、错误处理改进、文档更新、任务规划

### 下次启动时
- **推荐命令**: `/wf_03_prime`
- **推荐下一步**:
  1. 执行任务 10.1：实现 sender 压缩模式支持（见 TASK.md 第 293 行）
  2. 或继续任务 10：规范化 C++ 构建配置
  3. 手动测试：`./build/sender &` + `uv run python recv.py -a localhost:5555 -m n`
