# Kimi娘桌宠（Kimi Code 版）开发说明

衍生自 bailong-desktop-pet v0.5.1，后端从 Codex 替换为 Kimi Code（`kimi acp`，ACP 协议），任务同步改为 Kimi Hooks。

## 开发者运行

1. 安装 64 位 Python（3.12+，上游构建使用 3.13）。
2. 在源码目录执行 `python -m pip install -r requirements.txt`。
3. 确认 `outputs/Kimi娘桌宠素材/`（随仓库）与 `tools/ffmpeg.exe`（不随仓库，自行放置）就位。
4. 安装并登录 Kimi Code CLI（`kimi login`）。
5. 执行 `python app/pet.py`；自检执行 `python app/pet.py --self-test`。任务进展同步开箱即用（CLI 与桌面端通吃）。

程序通过 FFmpeg 的 libvpx-vp9 解码透明通道，保留动作预加载；请不要用丢弃透明通道的默认 VP9 解码方式替换。

## 后端架构

- `app/chat_backend.py`：`KimiSession` 通过 stdio JSON-RPC 驱动 `kimi acp`（initialize → session/new|load → session/prompt；session/update 流式事件；session/request_permission 权限确认）。acp 进程使用隔离的 `KIMI_CODE_HOME`（`kimi_home()` 创建并从 `~/.kimi-code` 播种配置与 credentials 目录联接），避免桌宠会话被桌面客户端索引（桌面客户端打开 ACP 会话会因"updated by another client"重试卡死）。
- `app/voice_input.py`：可选的本地语音前台。中英混合 sherpa-onnx KWS 常驻唤醒，唤醒后由 Silero VAD 检测语句结束，再用 SenseVoice 转写；语音进入 chat 会话，仅自动允许公开网页搜索/读取，其他工具仍取消。默认昵称“没药”显式标音为 `m ò y ào`，`Kimi` 使用英文音素，别名可在设置中修改。语音界面只显示识别文字、状态和最终回答；`listen` 动作循环聆听，`thinking` 动作为可选的思考循环，缺省复用工作动作。回答后可进入带超时的 followup VAD 状态，无需再次经过 KWS；倒计时只在尚未检测到人声时生效。
- `app/desktop_actions.py`：语音识别后的确定性本地动作分发。仅执行程序别名、网页搜索/URL、音量、提醒和白名单设置页，不把语音转换成任意 Shell。提醒使用 `用户数据目录/reminders.json` 持久化，程序别名保存在 `desktop-actions.json`；`app/desktop_ui.py` 提供管理界面。
- `app/voice_models.py` / `work/install_voice_models.py`：从 sherpa-onnx 官方发布页与模型作者的 Hugging Face 仓库下载外置模型，支持断点续传；模型位于 `用户数据目录/voice-models`，不进入源码或 EXE。`app/voice_ui.py` 提供设置和手动下载入口。
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

本项目衍生自 [@jingh12312-rgb](https://github.com/jingh12312-rgb) 的 bailong-desktop-pet，已获原作者授权发布。「Kimi娘」形象基于网络开源形象改编，素材说明见 ASSETS.md。本项目非 Kimi（Moonshot AI）官方产品。
