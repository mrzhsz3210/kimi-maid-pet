# Kimi娘桌宠（Kimi Code 版）

住在桌面上的星空女仆「Kimi娘」，与 **Kimi Code** 联动的动态桌宠。

> 本项目基于 **[@jingh12312-rgb](https://github.com/jingh12312-rgb)** 的 [bailong-desktop-pet（GPT白龙娘动态桌宠）](https://github.com/jingh12312-rgb/bailong-desktop-pet) v0.5.1 改造，已获得原作者授权。桌宠框架（动画播放、吸边、气泡、移动等）的功劳属于上游作者；本项目在此基础上把后端从 Codex 换成了 Kimi Code，并换上了「Kimi娘」角色（形象基于网络开源形象改编）。如果你喜欢这个桌宠框架，请也去给上游点个 Star！

## 功能

| 日常待机 | 工作·取书翻阅 | 庆祝 | 彩蛋·弹飞 |
| --- | --- | --- | --- |
| ![日常待机](docs/preview/idle.gif) | ![工作](docs/preview/work02.gif) | ![庆祝](docs/preview/18.gif) | ![弹飞](docs/preview/knockback.gif) |

| 跑步移动 | 心情待机·喜（坐姿） |
| --- | --- |
| ![跑步](docs/preview/move02.gif) | ![喜·坐姿](docs/preview/idle11.gif) |

- 51 段透明 WebM 动画：待机（含喜怒哀惧 × 站/坐/跪 12 段心情待机）/ 互动差分 / 聆听 / 工作 / 移动（走路与跑步）/ 拖拽落地；单击互动（双击立即互动，连点 4 下触发"弹飞"彩蛋）、拖动、左右/下方吸边探头（吸边双击打开对话）。废弃差分保留在素材包但不自动播放
- **心情系统**（移植自 house-companion 的 M1）：快乐/生气/难过/害怕四轴，时间衰减、AI 提案、程序裁决记账（同轴 5 分钟限频防刷屏）；心情影响互动差分权重与待机姿态（喜/怒/哀/惧各有站、坐、跪三种待机；中性坐姿和跪姿在所有心情下都保留候选，中性与当前心情动作的权重为 7:3），右键可查看心情面板、安抚她、编辑人设
- **对话模式**：右键打开对话模式，直接让Kimi娘调用 Kimi Code 干活（走官方 `kimi acp` 协议，流式输出、权限确认气泡）。桌宠发起的会话存放在独立的 `KIMI_CODE_HOME`（`用户数据目录/kimi-home`），不会出现在 Kimi Code 桌面客户端的工作区列表里
- **本地语音输入**：可叫她“没药”（明确读作 mò yào）、“Kimi”或“Kimi娘”唤醒；聆听动作循环播放，说完并静音约 1.2 秒后自动识别和回复。气泡依次显示识别状态、听见的内容、思考/联网状态与最终回答，不自动打开文字输入框或流式摘要。昵称、别名和静音时长均可设置。默认回答后保留 20 秒免唤醒连续对话，已开始说话不会被倒计时打断，可说“没事了”退出；开关和时长可配置。唤醒与语音识别在本机运行，不保存原始录音；识别文字会发送给 Kimi。语音聊天可自动搜索和读取公开网页，但不批准文件修改、命令执行或其他工具
- **桌面动作**：语音可打开登记过的程序、用默认浏览器搜索/打开网页、调节音量与静音、创建本地定时提醒，或打开闹钟/免打扰/飞行模式等系统设置页。使用固定白名单，不执行任意命令；程序别名、搜索引擎和提醒可在「桌面动作设置」中管理
- **任务同步**：你在 Kimi Code（CLI 和桌面客户端）里的任务进展，Kimi娘都会通过气泡提醒（只读本地会话状态文件，无需任何配置）

## 运行（需要 Python 3.12+ 与 Kimi Code CLI）

```sh
pip install -r requirements.txt
python app/pet.py          # 启动桌宠
python app/pet.py --self-test   # 离线自检
```

- 需要已安装并登录 Kimi Code CLI（`kimi login`）。找不到 CLI 时可设环境变量 `MAID_KIMI` 指向 `kimi.exe`。
- 语音输入首次使用前执行 `python work/install_voice_models.py` 下载本地模型，然后右键开启「启用语音唤醒」。模型也可在「语音对话设置…」中下载；不启用语音时不需要打开麦克风。
- 透明动画解码依赖 `tools/ffmpeg.exe`（libvpx-vp9，保留 alpha 通道），完整发布包附带；源码运行请自行放置。

## 任务进展同步（自动，无需配置）

桌宠每 2 秒只读检查一次 `~/.kimi-code/sessions/*/*/state.json`（会话标题、状态、时间戳等元信息，不读取对话内容），Kimi Code CLI 和桌面客户端的任务开始/完成/失败都会触发气泡提醒与工作动画。桌宠自己发起的对话会被自动排除，不会重复提醒。

## 更换角色素材

素材全部外置在 `outputs/Kimi娘桌宠素材/`：

- `透明WebM/*.webm` —— 720×720、24fps、VP9 + alpha（yuva420p），角色脚底贴画面底部中央
- `素材清单.json` —— 每段动画的时长、缩放、偏移、台词、移动参数

想换角色：替换 webm 并改清单即可，不用改代码。新增互动差分就往 `variants` 数组里加一条（参考 `knockback` 段）。语音聆听使用 `listen`；可再添加 ID 为 `thinking` 的循环差分作为思考动作，缺省时复用工作动作。

### 双外观（黑丝 / 白丝）

右键菜单 →「外观（丝袜）」可在黑丝与白丝两套外观间热切换（无需重启）。白丝素材在 `outputs/Kimi娘桌宠素材-白丝/`（结构与原素材一致，按 crf32 重压缩以控制体积）。新增一套外观：复制素材文件夹并在 `pet.py` 的 `APPEARANCES` 里登记即可。

## 版权与许可说明

- 本仓库程序部分衍生自 [@jingh12312-rgb](https://github.com/jingh12312-rgb) 的 [bailong-desktop-pet](https://github.com/jingh12312-rgb/bailong-desktop-pet)，**已获得原作者授权发布**。上游的「白龙娘」美术素材不包含在本仓库中，其许可见上游 ASSETS.md。
- 「Kimi娘」角色素材（`outputs/Kimi娘桌宠素材/`）由项目作者制作；**形象基于网络开源形象改编**，并非完全原创人设，原型权利归其原作者/原许可所有。
- 运行库与 ffmpeg 遵循各自许可证。
- 本项目非 Kimi（Moonshot AI）官方产品。

## 目录结构

```
app/            桌宠程序（pet.py 主程序、chat_backend.py Kimi ACP 后端、desktop_task_sync.py 会话状态监听）
outputs/Kimi娘桌宠素材/   动画素材与清单
tools/          ffmpeg（透明 WebM 解码，需自备）
work/           构建与测试工具
```

## 支持作者

如果这个桌宠给你带来了好心情，可以来我的爱发电坐坐：[afdian.com/a/mrzhsz3210](https://afdian.com/a/mrzhsz3210)
