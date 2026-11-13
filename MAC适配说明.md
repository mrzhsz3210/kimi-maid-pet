macOS适配说明（继承自上游 v0.5.1，尚未实机验收）

注意：本文档为上游 bailong-desktop-pet 的历史文档，其中 Codex 相关内容在 Kimi 版中已由 `kimi acp` 与 Kimi Hooks 替代，下文仅供参考，尚未按 Kimi 版重写。

本次仅交付Windows安装包；Mac适配代码保留在项目app目录，构建入口work/build_macos.py。此说明不代表已经有可用Mac安装包。
已适配：.app资源定位、用户Library/Application Support/KimiMaidPet读写、Kimi可执行文件定位、Qt音效、LaunchAgent随Kimi启动、菜单栏入口、跨Space窗口与全屏检测。
保留：动画、拖动、左右吸边、自移动、大小调节、气泡和对话逻辑。任务同步取决于本机 Kimi hooks 配置。
在Mac上用独立Python虚拟环境安装requirements-macos.txt，再运行 python work/build_macos.py。动画读取当前outputs/白龙桌宠素材，不需要Windows运行库；程序不收集账号凭证或用户历史。
此脚本按运行机器架构构建，不假装同时支持Intel与Apple Silicon。首次应分别在两种Mac上验证。内置临时签名仅供本地测试，公开发布须正式签名和公证，勿引导用户关闭系统安全机制。
需实机检查：菜单栏隐藏/恢复、多个显示器与Space、全屏开关、音效、自动启动开关、退出、权限限制下的全屏检测、Codex登录/额度和任务状态。
全屏检测依赖macOS提供的窗口信息；权限不足可能无法检测，应根据实机结果补充说明。当前Windows平台测试仅验证路径和分支，不能代替Mac实机测试。
参考：https://www.pyinstaller.org/en/stable/ （打包必须在目标系统运行）
