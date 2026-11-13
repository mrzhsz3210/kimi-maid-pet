# 没药女仆桌宠（Kimi Code 版）

住在桌面上的星空女仆「没药」，与 **Kimi Code** 联动的动态桌宠。
基于 [bailong-desktop-pet](https://github.com/jingh12312-rgb/bailong-desktop-pet)（GPT白龙娘动态桌宠 v0.5.1）改造：后端从 Codex 换成了 Kimi Code，角色素材换成了原创角色「没药」。

## 功能

- 36 段透明 WebM 动画：待机 / 互动差分 / 工作 / 移动 / 拖拽落地，单击互动、拖动、吸边探头
- **对话模式**：右键打开对话模式，直接让没药调用 Kimi Code 干活（走官方 `kimi acp` 协议，流式输出、权限确认气泡）
- **任务同步**：你在 Kimi Code CLI / 桌面客户端里的任务进展，没药会通过气泡提醒（基于 Kimi Hooks，见下文）
- 双击查看 Kimi CLI 状态（Kimi 暂无公开额度接口，额度请见客户端）

## 运行（需要 Python 3.12+ 与 Kimi Code CLI）

```sh
pip install -r requirements.txt
python app/pet.py          # 启动桌宠
python app/pet.py --self-test   # 离线自检
```

- 需要已安装并登录 Kimi Code CLI（`kimi login`）。找不到 CLI 时可设环境变量 `MAID_KIMI` 指向 `kimi.exe`。
- 透明动画解码依赖 `tools/ffmpeg.exe`（libvpx-vp9，保留 alpha 通道），完整发布包附带；源码运行请自行放置。

## 任务进展同步（Kimi Hooks）

桌宠本体不会读你的会话内容；Kimi 的 hooks 只把事件元信息（会话标题、工具名、状态）追加到本地日志，桌宠每秒读取一次：

```sh
python work/install_hooks.py            # 安装 hooks 到 ~/.kimi-code/config.toml（自动备份原配置）
python work/install_hooks.py --uninstall
```

生效事件：`TurnStarted` / `PostToolUse` / `PostToolUseFailure` / `PermissionRequest` / `Stop` / `StopFailure` / `Interrupt`。

## 更换角色素材

素材全部外置在 `outputs/没药桌宠素材/`：

- `透明WebM/*.webm` —— 720×720、24fps、VP9 + alpha（yuva420p），角色脚底贴画面底部中央
- `素材清单.json` —— 每段动画的时长、缩放、偏移、台词、移动参数

想换角色：替换 webm 并改清单即可，不用改代码。新增互动差分就往 `variants` 数组里加一条（参考 `knockback` 段）。

## 版权与许可说明（重要）

- 本仓库程序部分衍生自 bailong-desktop-pet。**原项目未指定开源许可证**，公开源码不等于授权再分发；在获得原作者明确许可前，请勿公开再分发本仓库的代码。美术素材（白龙娘）许可见原项目 ASSETS.md。
- 「没药」角色素材（`outputs/没药桌宠素材/`）为本项目原创。
- 运行库与 ffmpeg 遵循各自许可证。
- 本项目非 Kimi（Moonshot AI）官方产品。

## 目录结构

```
app/            桌宠程序（pet.py 主程序、chat_backend.py Kimi ACP 后端、desktop_task_sync.py hooks 同步）
outputs/没药桌宠素材/   动画素材与清单
tools/          ffmpeg（透明 WebM 解码，需自备）
work/           hooks 安装脚本等工具
```
