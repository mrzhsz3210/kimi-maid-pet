# 没药女仆桌宠（Kimi Code 版）开发说明

衍生自 bailong-desktop-pet v0.5.1，后端从 Codex 替换为 Kimi Code（`kimi acp`，ACP 协议），任务同步改为 Kimi Hooks。

## 开发者运行

1. 安装 64 位 Python（3.12+，上游构建使用 3.13）。
2. 在源码目录执行 `python -m pip install -r requirements.txt`。
3. 确认 `outputs/没药桌宠素材/`（随仓库）与 `tools/ffmpeg.exe`（不随仓库，自行放置）就位。
4. 安装并登录 Kimi Code CLI（`kimi login`）。
5. 执行 `python app/pet.py`；自检执行 `python app/pet.py --self-test`。任务进展同步开箱即用（CLI 与桌面端通吃）。

程序通过 FFmpeg 的 libvpx-vp9 解码透明通道，保留动作预加载；请不要用丢弃透明通道的默认 VP9 解码方式替换。

## 后端架构

- `app/chat_backend.py`：`KimiSession` 通过 stdio JSON-RPC 驱动 `kimi acp`（initialize → session/new|load → session/prompt；session/update 流式事件；session/request_permission 权限确认）。
- `app/desktop_task_sync.py`：每 2 秒只读扫描 `~/.kimi-code/sessions/*/*/state.json`（mtime 变化才读取）；只使用会话标题、lastPrompt、lastTurnReason、updatedAt 等元信息，不读 wire.jsonl 对话内容。
- `app/quota.py`：定位 kimi CLI 并确认可用；Kimi 暂无公开额度接口。
- 聊天模式（chat）不授予任何工具权限（permission 一律 cancelled）；工作模式（work）走正常审批。

## 测试

```
cd app
python -m unittest discover -p "test_*.py"      # 离线单测
python ../app/pet.py --self-test                 # 离线自检（需素材与 tools/ffmpeg）
python work/test_e2e_backend.py                  # 真实 Kimi 连通测试（消耗一次额度）
```

## 构建 Windows 包

在 Windows 上安装 PyInstaller 6.22.3 至 `.build-tools`：`python -m pip install --target .build-tools pyinstaller==6.22.3`。

运行 `python work/build_windows.py` 生成 EXE。整理完整 ZIP 使用 `python work/build_release.py`（需要 FFmpeg 与 outputs 素材）。

## 许可说明

上游 bailong-desktop-pet 未指定开源许可证；在获得原作者许可前请勿公开再分发本仓库代码。「没药」素材为本项目原创，见 ASSETS.md。本项目非 Kimi（Moonshot AI）官方产品。
