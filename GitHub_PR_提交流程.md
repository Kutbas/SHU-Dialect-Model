# GitHub Pull Request 提交流程

这个文档是给当前项目用的，目标是把你本地改动提到 GitHub，然后发起 Pull Request 给学长合并。

## 1. 提交前先确认什么应该进仓库

### 应该提交

- `www/index.html`
- `www/live2d-host.js`
- `www/live2d-host.css`
- `www/live2d-widget/`
- 这次新增的更新说明文档

### 不应该提交

- `.venv_XiaoHu/`
- `python-3.12.3-amd64.exe`
- `install_log.txt`
- `uvicorn_out.txt`
- `uvicorn_err.txt`
- `www/live2d-widget-loading-test/`

## 2. 你自己的 GitHub 仓库准备

因为原仓库的远程是：

- `origin = https://github.com/Kutbas/SHU-Dialect-Model.git`

通常你没有直接 push 到原作者仓库的权限，所以标准做法是：

1. 先在 GitHub 网页上 Fork 原仓库到你自己的账号
2. 再把你自己的 Fork 加成一个新的远程，比如叫 `myfork`

## 3. 推荐操作步骤

下面这些命令在项目目录里执行：

```powershell
cd D:\Study_Main\Xiao_Hu\SHU-Dialect-Model-main
```

### 第一步：查看当前改动

```powershell
git status
```

### 第二步：添加你自己的 Fork 远程

把下面地址换成你自己的 GitHub 用户名：

```powershell
git remote add myfork https://github.com/你的用户名/SHU-Dialect-Model.git
git remote -v
```

如果之前已经加过 `myfork`，就不用重复加。

### 第三步：把需要的文件加入暂存区

```powershell
git add .gitignore
git add www/index.html
git add www/live2d-host.js
git add www/live2d-host.css
git add www/live2d-widget
git add LIVE2D_更新说明_20260416.md
git add GitHub_PR_提交流程.md
```

### 第四步：再次检查是否有不该提交的东西

```powershell
git status
```

这一步一定要看：

- 不要把 `.venv_XiaoHu`
- 不要把 `.exe`
- 不要把日志文件
- 不要把 `www/live2d-widget-loading-test`

带进去。

### 第五步：提交 commit

```powershell
git commit -m "Add XiaoHu Live2D integration and interaction bubble"
```

### 第六步：推送到你自己的 Fork

你当前本地分支是：

- `feature/dev`

所以直接推送：

```powershell
git push myfork feature/dev
```

如果 GitHub 提示需要登录，就按提示完成。

## 4. 在 GitHub 网页上发 Pull Request

推送成功后：

1. 打开你自己的 Fork 仓库网页
2. GitHub 通常会自动提示 `Compare & pull request`
3. 点击进入
4. 选择：
   - base repository：`Kutbas/SHU-Dialect-Model`
   - base branch：通常是对方让你合并进的分支
   - compare：你自己的 `feature/dev`
5. 填标题和说明
6. 提交 Pull Request

## 5. Pull Request 说明里建议怎么写

你可以直接参考这种写法：

### 标题

```text
Add XiaoHu Live2D integration, multi-state switching, and interaction bubble
```

### 描述

```text
This PR integrates XiaoHu Live2D into the main chat page.

Changes included:
- add a right-side Live2D display area for XiaoHu theme
- add runtime Live2D widget resources into www/live2d-widget
- support loading / speaking / yes / deny state switching
- use loading as the default idle state
- add click interaction bubble with Shanghainese phrases
- add project update notes for future maintenance
```

## 6. 学长最可能会关心什么

你在 PR 里最好主动说明这三点：

1. 数字人运行资源已经放进仓库，所以别人 clone 后能直接跑
2. 本地虚拟环境和安装包没有提交
3. 当前是可演示版本，后续还可以继续优化状态切换平滑度

## 7. 如果你担心自己操作失误

最稳的办法是：

1. 先只执行 `git status`
2. 再执行 `git add ...`
3. 再执行一次 `git status`
4. 把结果发给我
5. 我帮你最后确认后，你再 `git commit` 和 `git push`

这样最安全，不容易把不该提交的东西推上去。
