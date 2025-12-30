# Release

发布新版本：升级小版本号，更新 CLAUDE.md，创建 PR 到 main 分支。

## Instructions

按以下步骤执行发布流程：

### Step 1: 确保在 main 分支且工作区干净

```bash
git checkout main
git pull origin main
git status
```

如果有未提交的更改，先提示用户处理。

### Step 2: 读取当前版本号

从 `.claude-plugin/plugin.json` 读取当前版本号（格式：x.y.z）。

### Step 3: 计算新版本号

升级小版本号（minor version）：
- 0.1.0 -> 0.2.0
- 0.2.5 -> 0.3.0
- 1.0.0 -> 1.1.0

### Step 4: 创建 release 分支

```bash
git checkout -b release/vX.Y.Z
```

分支名使用新版本号。

### Step 5: 更新 plugin.json

修改 `.claude-plugin/plugin.json` 中的 `version` 字段为新版本号。

### Step 6: 更新 CLAUDE.md

在 CLAUDE.md 文件开头添加版本信息（如果没有的话），或更新已有的版本号：

```markdown
# Vibe Ops Plugin

> Version: X.Y.Z
```

### Step 7: 提交更改

```bash
git add .claude-plugin/plugin.json CLAUDE.md
git commit -m "chore: bump version to vX.Y.Z"
```

### Step 8: 推送分支

```bash
git push -u origin release/vX.Y.Z
```

### Step 9: 创建 PR

使用 gh 命令创建 PR：

```bash
gh pr create --base main --title "Release vX.Y.Z" --body "$(cat <<'EOF'
## Summary

- Bump version to vX.Y.Z

## Checklist

- [ ] Version updated in plugin.json
- [ ] CLAUDE.md updated

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Step 10: 返回结果

告诉用户：
- 新版本号
- PR 链接
- 下一步操作（review 和 merge PR）
