# 本地游戏库管理器

一款完全离线的 Windows 桌面游戏库管理器：扫描本机游戏目录、按标签整理、双击启动并记录游玩次数。界面参考 Playnite 的深色三栏风格。

数据全部存在本地 `games.db`，运行时不联网、不上传、不需要账号。

## 功能

- **扫描导入**：选 1~N 个根目录，只读发现 `.exe`；按游戏目录分组，默认只勾每组的主程序，工具 / 编辑器 / 安装卸载类默认隐藏但可展开改选；**人工勾选后才入库**
- **整理**：网格 / 列表视图、即时搜索、标签筛选、最近游玩、统计盒
- **管理**：添加 / 编辑 / 删除（删除有二次确认）
- **启动与记录**：双击或「启动游戏」→ 卡片显示运行中角标、状态栏显示运行数 → 进程退出后写回 `last_played` / `play_count`；启动失败给明确报错且不记次数
- **真实数据**：左栏标签、统计、详情条全部来自 `games.db`，没有装饰性的假控件

## 快速开始

### 方式一：独立 exe（推荐，给别人用最省事）

`build_exe.bat` 生成 `dist\本地游戏库管理器.exe`（约 13 MB，单文件、无黑窗口、内嵌图标）。**只发这一个文件**给别人即可，双击就能用，不需要发本仓库其它任何文件。

要求：

- Windows 10/11 **64 位**
- **WebView2 Runtime**（Win11 和较新 Win10 随 Edge 自带；老机器或精简系统需装微软官方「WebView2 Runtime 常青版」）。exe 只带了互操作 dll，Runtime 本体依赖系统
- 未签名的 exe 首次运行会触发 SmartScreen，点「更多信息 → 仍要运行」；个别杀软对 PyInstaller 程序误报，需加白名单

首次运行自动在 exe 旁生成 `games.db`。升级时**先关闭程序**再覆盖 exe，数据原样保留（程序运行时 exe 被占用，无法覆盖）。

### 方式二：源码运行（开发 / 改代码即时生效）

```
setup.bat        # 首次：联网一次，把依赖装进 vendor/
run.bat          # 源码启动（会弹 cmd 黑窗口）
```

无黑窗口的启动方式：双击 `launch.vbs`，或用 `create_shortcut.ps1` 创建桌面快捷方式。改了代码想更新 exe 时重跑 `build_exe.bat`。

源码入口是 `python -m src.webapp`。脚本会优先用系统 Python 3.9+，找不到就回退到 DSH 内置 Python 3.12。注意 `vendor\runtime.txt` 记录的是实际装依赖的解释器 —— `vendor` 里的 `.pyd` 与 CPython 版本绑定，**setup 与 run 必须用同一个 Python**，所以 `run.bat` 会优先读这个文件。

## 三个 bat 脚本

| 脚本 | 作用 | 产物 | 联网 |
|---|---|---|---|
| `setup.bat` | 装运行时依赖（`pywebview==6.2.1`） | `vendor/` + `vendor/runtime.txt` | 首次一次 |
| `run.bat` | 源码模式启动 | 无，直接开窗口 | 否 |
| `build_exe.bat` | 用 PyInstaller 打包独立 exe | `dist/本地游戏库管理器.exe` | 首次一次 |

`setup.bat` 装的是**运行时**依赖（`vendor/`），`build_exe.bat` 装的是**构建工具**（`.build-venv/`），两套环境互不复用。`create_shortcut.ps1` 创建桌面快捷方式，加 `-UseExe` 则指向打包出的 exe。

产物（`dist/`、`vendor/`、`games.db`、构建目录）全部被 `.gitignore` 忽略，**不进 Git 仓库**。

## 技术栈

- 后端：Python 3.12 标准库（`sqlite3` / `subprocess` / `pathlib`）
- 界面：本地 HTML/CSS/JS（`web/index.html`）
- 桥接：pywebview 的 `js_api`，JS 进程内直调 Python（`src/api.py`）
- 窗口：系统 WebView2。**不是 HTTP 服务** —— 页面以 `file://` 直载，没有端口、没有本地服务器
- 数据：SQLite 单文件 `games.db`

`src/db.py` / `scanner.py` / `launcher.py` 是纯逻辑层，不依赖界面，可单独复用。

## 数据位置

| 场景 | `games.db` 位置 |
|---|---|
| 源码启动 | 项目根目录 |
| exe 在 `<项目根>/dist` | **同一个**项目根目录（两条路线共用一份数据） |
| exe 被单独拷到别处 | exe 旁边 |

由 `src/paths.py` 统一解析：onefile 打包后资源从临时解压目录读，而数据必须写到持久目录。数据文件含本机路径，被 `.gitignore` 忽略。

## 目录结构

```
game-manager/
├─ run.bat / setup.bat / build_exe.bat   启动与构建
├─ launch.vbs                           无控制台窗口启动
├─ create_shortcut.ps1                  桌面快捷方式（-UseExe 指向 exe）
├─ build_entry.py / game-manager.spec   PyInstaller 入口与配置
├─ requirements.txt                     pywebview==6.2.1
├─ assets/app.ico                       应用图标
├─ web/index.html                       真前端
├─ design/preview.html                  静态样式稿（双击浏览器可看，内置假数据）
├─ src/
│   ├─ api.py        桥接层：JS 可调的 Python 方法
│   ├─ webapp.py     窗口入口
│   ├─ db.py         SQLite 数据层
│   ├─ scanner.py    只读扫描、分组、主程序打分
│   ├─ launcher.py   启动进程
│   └─ paths.py      源码 / frozen 路径解析
└─ tests/            单元测试
```

## 测试

```
python -m unittest discover -s tests -t .
```

当前 88 个用例，覆盖数据层、扫描规则、启动器、桥接层与路径解析。

## 已知边界

- 不做封面 / 网络元数据抓取、存档云同步、Mod 管理、Steam/Epic 对接、自动更新、安装包
- 不识别 `.lnk` 快捷方式与 Steam 库清单
- 启动参数按空白切分，不支持带空格的引号值
- 仅 Windows x64；封面用纯色 + 首字母占位（不引入第三方图像库）

## 分发

给别人用直接发 `dist\本地游戏库管理器.exe` 即可。注意 **exe 不在 Git 仓库里**：clone 本仓库后必须跑 `setup.bat` + `build_exe.bat` 才能生成；想让人直接下载，请把 exe 传到 GitHub Release 附件。
