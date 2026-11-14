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

- 50 段透明 WebM 动画：待机（含喜怒哀惧 × 站/坐/跪 12 段心情待机）/ 互动差分 / 工作 / 移动（走路与跑步）/ 拖拽落地；单击互动（双击立即互动，连点 4 下触发"弹飞"彩蛋）、拖动、吸边探头（吸边双击打开对话）。废弃差分保留在素材包但不自动播放
- **心情系统**（移植自 house-companion 的 M1）：快乐/生气/难过/害怕四轴，时间衰减、AI 提案、程序裁决记账（同轴 5 分钟限频防刷屏）；心情影响互动差分权重与待机姿态（喜/怒/哀/惧各有站、坐、跪三种待机），右键可查看心情面板、安抚她、编辑人设
- **对话模式**：右键打开对话模式，直接让Kimi娘调用 Kimi Code 干活（走官方 `kimi acp` 协议，流式输出、权限确认气泡）。桌宠发起的会话存放在独立的 `KIMI_CODE_HOME`（`用户数据目录/kimi-home`），不会出现在 Kimi Code 桌面客户端的工作区列表里
- **任务同步**：你在 Kimi Code（CLI 和桌面客户端）里的任务进展，Kimi娘都会通过气泡提醒（只读本地会话状态文件，无需任何配置）

## 运行（需要 Python 3.12+ 与 Kimi Code CLI）

```sh
pip install -r requirements.txt
python app/pet.py          # 启动桌宠
python app/pet.py --self-test   # 离线自检
```

- 需要已安装并登录 Kimi Code CLI（`kimi login`）。找不到 CLI 时可设环境变量 `MAID_KIMI` 指向 `kimi.exe`。
- 透明动画解码依赖 `tools/ffmpeg.exe`（libvpx-vp9，保留 alpha 通道），完整发布包附带；源码运行请自行放置。

## 任务进展同步（自动，无需配置）

桌宠每 2 秒只读检查一次 `~/.kimi-code/sessions/*/*/state.json`（会话标题、状态、时间戳等元信息，不读取对话内容），Kimi Code CLI 和桌面客户端的任务开始/完成/失败都会触发气泡提醒与工作动画。桌宠自己发起的对话会被自动排除，不会重复提醒。

## 更换角色素材

素材全部外置在 `outputs/Kimi娘桌宠素材/`：

- `透明WebM/*.webm` —— 720×720、24fps、VP9 + alpha（yuva420p），角色脚底贴画面底部中央
- `素材清单.json` —— 每段动画的时长、缩放、偏移、台词、移动参数

想换角色：替换 webm 并改清单即可，不用改代码。新增互动差分就往 `variants` 数组里加一条（参考 `knockback` 段）。

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
