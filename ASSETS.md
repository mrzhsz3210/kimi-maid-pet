# 素材说明

## Kimi娘

`outputs/Kimi娘桌宠素材/`（黑丝）与 `outputs/Kimi娘桌宠素材-白丝/`（白丝）内的各 50 段透明 WebM 动画与 `素材清单.json` 由项目作者制作并随本仓库发布。**角色形象基于网络上的开源形象改编设计**，并非完全原创人设；原型形象的权利归其原作者/原许可所有。

构成：待机 20（含喜怒哀惧 × 站/坐/跪 12 段心情待机与 2 段中性坐/跪）、互动差分 16（含 knockback 彩蛋）、工作 6（其中 3 段已废弃、仅保留素材不参与自动播放）、移动 6（其中飞行 2 段已废弃）、系统 2（拖拽/落地）。

规格：VP9（libvpx-vp9）+ alpha 通道、720×720、24fps、角色锚点 bottom-center。

## 第三方素材

- `app/sounds/click.wav`：程序合成音效（无外部录音采样），Kenney 许可文本为上游遗留，见 `app/sounds/Kenney-License.txt`。
- 透明视频解码依赖 FFmpeg（libvpx-vp9），遵循其许可证；`tools/ffmpeg.exe` 不纳入 Git 历史，请从完整发布包或 FFmpeg 官方渠道获取。

## 上游项目

程序衍生自 [@jingh12312-rgb](https://github.com/jingh12312-rgb) 的 [bailong-desktop-pet](https://github.com/jingh12312-rgb/bailong-desktop-pet)，已获原作者授权。上游的「白龙娘」美术素材不包含在本仓库中，其许可见上游 ASSETS.md。
