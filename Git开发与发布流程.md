# FmuSolver Git 开发与发布流程

本文档用于规范 FmuSolver 的日常开发、现场修复、第三方版本合并和正式发布流程。

## 1. 工作树分工

### 日常开发工作树

日常开发统一使用：

```powershell
C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER
```

用途：

- 开发新功能。
- 修复现场问题。
- 对比、合并别人提供的新版本。
- 编写测试脚本和维护工具。
- 提交并推送功能分支。

### 正式发布工作树

正式发布、打包、客户交付建议使用：

```powershell
C:\Spaceship\FMUSOLVER
```

用途：

- 只拉取远端 `master` 的正式版本。
- 只做发布前验证、打包和交付。
- 不建议在该目录直接做日常开发。

原因：

Git worktree 不允许同一个本地分支同时被两个工作树检出。如果 `C:\Spaceship\FMUSOLVER` 占用了本地 `master`，Codex 工作树就不能直接切换到本地 `master`。因此建议让发布目录长期占用 `master`，日常开发目录使用功能分支。

## 2. 分支职责

### `master`

正式发布分支。

规则：

- 只保存已经验证通过、可以打包交付的版本。
- 不直接在 `master` 上做日常开发。
- 每次合入前必须确认关键脚本可编译、主流程可运行。

### `feature/*`

新功能分支。

示例：

```powershell
feature/telemetry-pressure-test
feature/new-fmu-integration
```

### `fix/*`

问题修复分支。

示例：

```powershell
fix/telemetry-freeze
fix/orbit-pre-output
```

### 第三方版本分支

别人提供的新版本源码建议单独建立来源分支，例如：

```powershell
dabing
vendor/dabing-20260720
```

规则：

- 先完整导入到独立分支。
- 再对比 `master`。
- 确认差异后再合并到正式分支。

## 3. 日常开发流程

进入日常开发工作树：

```powershell
cd C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER
```

拉取远端最新状态：

```powershell
git fetch origin
```

基于远端 `master` 创建修复分支：

```powershell
git switch -c fix/telemetry-freeze origin/master
```

开发完成后检查改动：

```powershell
git status
git diff --stat
```

提交：

```powershell
git add -A
git commit -m "修复遥测长时间运行卡顿"
```

推送功能分支：

```powershell
git push -u origin fix/telemetry-freeze
```

## 4. 合并到正式 `master`

如果当前 Codex 工作树不能切换到 `master`，说明 `master` 正被发布工作树占用。这是正常情况。

推荐方式是在 Codex 工作树中确认当前分支可以快进 `master`：

```powershell
git fetch origin
git merge-base --is-ancestor origin/master 当前分支名
```

如果命令成功，说明可以安全快进。

推送当前分支到远端 `master`：

```powershell
git push origin 当前分支名:master
```

示例：

```powershell
git push origin dabing:master
```

推送后确认远端 `master` 提交：

```powershell
git fetch origin
git rev-parse origin/master
```

## 5. 发布目录更新流程

正式发布目录只拉取 `master`：

```powershell
cd C:\Spaceship\FMUSOLVER
git fetch origin
git pull --ff-only origin master
```

如果 `git pull --ff-only` 失败，说明发布目录里可能有本地改动或历史分叉。此时不要强行覆盖，应先执行：

```powershell
git status
git diff --stat
```

确认是否存在未提交改动。

## 6. 发布前检查

每次合入 `master` 前，至少执行关键脚本编译检查：

```powershell
python -m py_compile `
  .\Script\FmuLauncherUniversal.py `
  .\Script\fmu_player.py `
  .\Script\yaocetest\main.py `
  .\Script\DataVisualizerPython.py `
  .\Script\orbit_pre_runner.py
```

建议额外检查：

- 主程序能正常启动。
- 新 FMU 能正常初始化。
- 轨道预示能生成有效 `Orbit_Pre.txt`。
- 遥测注入能持续运行。
- PE 转发能收到数据。
- 长时间运行日志没有持续增长的异常错误。

## 7. 正式发布打标签

正式发布后建议打 tag，便于回滚和定位客户现场版本。

示例：

```powershell
git tag -a v2026.07.20-fmusolver -m "FmuSolver 2026-07-20 正式发布"
git push origin v2026.07.20-fmusolver
```

命名建议：

```text
vYYYY.MM.DD-说明
```

例如：

```text
v2026.07.20-orbit-pre-fix
v2026.07.20-telemetry-stability
```

## 8. 回滚策略

如果客户现场发现新版本不可用，优先回滚到上一个正式 tag：

```powershell
git fetch origin --tags
git checkout v2026.07.20-orbit-pre-fix
```

如果需要让 `master` 回退，必须先确认原因，再由负责人执行，避免误覆盖正式版本。

## 9. 推荐原则

- `master` 永远代表可发布版本。
- Codex 工作树负责开发和合并，不直接占用 `master`。
- 发布工作树负责打包和交付，只拉 `master`。
- 第三方源码先进入独立分支，再对比合并。
- 每次发布前必须验证关键脚本和主流程。
- 每次正式发布建议打 tag。
