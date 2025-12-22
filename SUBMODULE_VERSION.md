# Git Submodule 版本管理

## 当前版本

| Submodule | 版本 | Commit | 说明 |
|-----------|------|--------|------|
| cppzmq | v4.11.0 | 3bcbd9d | ZeroMQ C++ 绑定库 |

## 为什么固定版本？

**问题**: 如果 submodule 指向浮动的 commit，不同开发者克隆项目时可能获得不同版本，导致：
- 构建不一致
- 难以复现问题
- 依赖冲突

**解决**: 将 submodule 固定到稳定的 release tag（如 v4.11.0），确保所有开发者使用相同版本。

## 如何更新 submodule 版本

### 查看可用版本

```bash
cd thirdparty/cppzmq
git fetch --tags
git tag --list 'v4.*' --sort=-version:refname | head -10
```

### 切换到新版本

```bash
# 1. 进入 submodule 目录
cd thirdparty/cppzmq

# 2. 切换到目标版本
git checkout v4.12.0  # 替换为目标版本

# 3. 回到父仓库
cd ../..

# 4. 验证构建
rm -rf build && mkdir build && cd build
cmake ..
make

# 5. 如果构建成功，提交变更
git add thirdparty/cppzmq
git commit -m "chore: 更新 cppzmq 到 v4.12.0"
```

### 克隆项目时获取正确版本

```bash
# 方法 1: 克隆时自动初始化 submodule
git clone --recurse-submodules https://github.com/your/repo.git

# 方法 2: 克隆后手动初始化
git clone https://github.com/your/repo.git
cd repo
git submodule update --init --recursive
```

## 版本选择原则

1. **优先使用 stable release**（带 tag 的版本，如 v4.11.0）
2. **避免使用开发分支**（main, master, develop）
3. **避免使用未标记的 commit**
4. **定期更新到最新 stable 版本**（每季度检查一次）

## 常见问题

### Q: submodule 状态显示 `+` 或 `-` 怎么办？

```bash
# 检查 submodule 状态
git submodule status

# 输出示例：
# +fbbff88... thirdparty/cppzmq (v4.11.0-2-gfbbff88)
#  ↑ 表示 submodule 有未提交的变更

# 解决方法：
cd thirdparty/cppzmq
git checkout v4.11.0  # 切回到固定版本
cd ../..
```

### Q: 如何查看 submodule 当前版本？

```bash
# 方法 1: 查看 git status
git submodule status

# 方法 2: 查看 submodule 的 tag
cd thirdparty/cppzmq
git describe --tags
```

### Q: 更新 submodule 版本后构建失败怎么办？

1. 检查新版本的 Breaking Changes
2. 查看新版本的 CHANGELOG 或 Release Notes
3. 如果无法解决，回退到之前的版本：
   ```bash
   cd thirdparty/cppzmq
   git checkout v4.11.0  # 之前的工作版本
   cd ../..
   ```

## 版本历史

| 日期 | 版本 | 变更说明 |
|------|------|---------|
| 2025-12-23 | v4.11.0 | 初始固定版本，避免版本漂移 |

