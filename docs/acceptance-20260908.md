# 2026-09-08 RK3588 实机验收

## 范围与结论

最新状态为 `0.4.16-9`：已安装，显示名为 `OpenViking`，保留旧安装 ID `openviking-local` 避免数据迁移。用户已取消子域名方案，使用普通 URL。下文早期域名、网关及改名尝试是历史记录，不是当前启用方案。

设备为用户的 ARM64 / RK3588 飞牛 NAS。基线为 OpenViking v0.4.16，纯文本、本地 BGE 512 维 CPU Embedding，不配置 VLM。

这不是全功能或正式发布完成声明：用户已确认飞牛实际生成的子域名在正确路径下可显示公网连接页，远程登录和业务流程仍待验证；NPU 无法初始化，未修改当前 NAS 内核或设备树。没有图片理解或生成式摘要。

## 已通过的设备测试

- 离线 Embedding：容器 `--network none`，512 维、有限数值，中文 NAS 查询的相关文档得分高于水果及篮球文档。
- 健康和鉴权：`/health`、`/ready`、`/studio/` 返回 200；未认证数据请求返回 401；Root Key 不能直接代替租户数据 Key。
- 中文文件：上传、等待入库、检索通过，原文档 `viking://resources/fpk-smoke-1788828037/nas/nas.md` 排第一，得分 `0.7461162805557251`。
- 停启持久化：应用中心控制的停启后，原文档及检索结果不变。
- 离线升级：应用中心从 `0.4.16-1` 升级至 `0.4.16-4`，界面显示新版本和“打开”；容器 `running / healthy`，使用新启动器。
- 自动初始化：新建 `fnos` 工作区和 `owner` 管理用户；已有记录不重复创建，凭据不输出到应用日志。
- 快照及恢复：停机快照包含 93 个文件，恢复后逐文件 SHA-256 完全一致；恢复前状态另行保留；恢复后旧文档查询通过。
- 应用外恢复副本：另存至设备私有测试目录并再次校验摘要，未放入 SMB 共享目录。
- 保留数据卸载重装：GUI 选择“保留配置和工作区”；只移除应用及自己的容器/网络。重装相同离线包后，原工作区、凭据及文档保留，服务健康。
- 自动工作区会话：创建、追加中文消息、读取上下文、列表和删除通过；其他工作区读取被拒绝，未认证请求返回 401。仅删除本次创建的临时测试会话。
- Windows 与 Linux 10 项单元测试通过；工作区初始化回归覆盖首次创建、已有工作区保留和不一致拒绝启动。
- `-4` 升级至 `-5`：应用中心版本和“打开”验证通过，容器健康；升级脚本实际生成 `20260908T023437027728Z` 完整快照。
- `-5` 首次连接页：应用按钮打开 `/studio/fnos.html`；错误 Key 显示拒绝提示，原安装 Key 成功进入 Studio，页面显示 `fnos / owner`。按用户明确授权保存工作区凭据；不保存 Root Key，不重新生成用户 Key。
- 窄屏几何检查：375px 视口未出现横向溢出，输入和按钮高度 48px。截图通道超时，未宣称截图视觉验收通过；临时视口覆盖已重置。

## 升级失败及修复证据

预加载镜像测试包的第一次升级失败：fnOS 清理旧项目镜像后尝试从 Docker Hub 拉取完整镜像 ID。原数据目录仍在，已通过事先导出的镜像恢复服务并验证原文档。

在 `upgrade_callback` 加载镜像仍然失败，证明该设备的 Docker 项目资源处理发生在升级回调之前。本地版改为由 `cmd/main` 先加载离线镜像，再 `docker compose up --pull never`；升级至 `-4` 成功。未改变宿主 Docker 全局配置或其他项目。

## 离线文件

本地包包含 Docker 镜像与 GGUF 模型；归档、模型、FPK 均记录摘要。FPK 通过 Windows SMB 复制至 `\\rknas\视频\openviking-fpk-test` 并核验 SHA-256。飞牛文件选择器未显示该新目录，使用浏览器文件上传器直接选择 UNC 文件完成升级。

`0.4.16-4` 的 FPK SHA-256：

```text
792565e1f99a9efb5ada2bcc4c25c5c3cbfc4df236b557e98ff7b9b1227d30ca
```

当前 `0.4.16-5` 的 FPK SHA-256（本地及 SMB 副本一致）：

```text
b7e452acaa6784dec4b5ff840b8a3c18001ea94062d5d317ee2072752818e02f
```

## 0.4.16-6 网关适配（尚待升级）

- 配置官方 `gatewayPrefix` / `gatewaySocket`，Socket 适配器保留 API Key 鉴权，并适配 Studio 资源、路由和连接服务地址前缀。
- 镜像环境内 17 项自动化测试通过：NAS 身份缺失拒绝、API 无 Key 拒绝、路径边界、静态资源前缀、连接页、大请求体、Cookie/身份 Header 剥离、重定向、WebSocket、不同 UID 存储分区。
- ARM64 NAS 独立临时适配器通过：Unix Socket、现有 Studio 资源、无认证拒绝、有认证账户读取及已有中文测试文档检索。测试使用合成 NAS UID，仅验证适配器；不代表真实 NAS 登录或 FN Connect 成功。
- 临时适配器容器已停止并移除，不修改工作区数据；原应用仍为 `0.4.16-5`、`running/healthy`。
- 新包已复制到 `\\rknas\视频\openviking-fpk-test\openviking-local-0.4.16-6-arm64-test.fpk`，本地与 SMB SHA-256 均为 `11f14493dd2290fd10ea5a714d3e3bfbe9afa7445f3e384b6cbd6a2f490a38b`。
- 浏览器控制连续超时 / Debugger unattached，尚未执行新包升级。需要手动升级后检查系统注册、真实 NAS 登录、桌面入口、浏览器 Studio 操作及公网链路。

## 后续定位与 0.4.16-7 修复

- 用户安装 `-6` 后，实机确认版本 `0.4.16-6`、容器 `running/healthy`、Socket 存在；Socket 适配器检查通过，但不能证明桌面打开链路正确。
- 本机图标打开 `http://192.168.8.102:1933/app/openviking-local/studio/fnos.html`；用户在另一台互联网电脑点击图标实际得到 `https://openviking-local-main.helywin.fnos.net/app/openviking-local/studio/fnos.html`，两者混用了端口入口与网关前缀。
- NAS 的 `1933` 端口返回与公网相同的 `NOT_FOUND` JSON。用户明确确认移除 `/app/openviking-local` 后，公网显示连接页。
- `-7` 恢复纯端口入口，移除多余网关适配器及其安装目录挂载；保留原 API Key、工作区数据和连接页。Windows 与 Linux 的 12 项回归测试通过，包含新增入口路径测试。
- 上一节网关测试为历史排查证据，临时实现已从 `-7` 移除；修正版尚待安装，不宣称图标已通过公网验收。

## 剩余验收

- `-8` 源码按用户授权统一应用 ID 为 `openviking`，本地模式不再依赖应用名判断生命周期，旧包存在时阻止新身份安装。fnpack 1.2.3 在应用 ID 改名后仍拒绝无后缀入口 `openviking`，故保留合法入口 `openviking.main`。精确前缀 `openviking` 尚未实现，也未在 NAS 迁移或部署；不宣称新域名已经绑定。

- 子域名前缀：尝试将本地版入口 ID 单独改为 `openviking`，被官方 fnpack 明确拒绝：入口名必须以 `openviking-local` 开头。该尝试已撤回；若按入口 ID 规则实现精确前缀，需要另行规划应用 ID 变更及数据迁移，尚未执行。

- 截图视觉审查：浏览器截图通道超时，目前只有实际 DOM 布局检查。
- 公网：升级 `-7` 后确认图标自动打开正确地址，继续验证远程 Key 登录和业务操作。连接页显示是用户在外网确认的结果，不冒充本机独立公网验收。
- 标准版 amd64/arm64 及其他 NAS 没有实机验收。
- NPU 诊断见 [rknpu-diagnosis.md](rknpu-diagnosis.md)，后续刷机或设备树修改需另行授权。

## 0.4.16-9 专用 NAS 目录与显示名称验收

- 显示名统一为 `OpenViking`，兼容包保留原安装 ID。入口为普通 URL `/studio/fnos.html`，没有新增网关、子域名绑定或修改 FN Connect 设置。
- 资源声明保留 `openviking/models` 和 `openviking/documents`，不再被离线打包逻辑清空。文件通过飞牛“应用文件”共享目录管理，不给整盘或其他个人目录授权。
- 实际目录为 `/vol1/@appshare/openviking/models` 和 `/vol1/@appshare/openviking/documents`，容器分别挂载到 `/models`、`/nas/documents`，均为只读。含 Key 的私有工作区仍位于原应用数据目录。
- 升级前停机快照为 `20260908T061528163049Z`，并另存至应用目录外的私有测试目录。官方 `appcenter-cli install-local` 完成旧包停止、重装和 `-9` 启动；原工作区和 Key 保留，旧 NAS 文档检索得分仍为 `0.7461162805557251`。
- NAS 用户可读模型、可写文档目录；实际容器对两个目录写入均被拒绝。读取 `nas-storage-check.txt` 后上传、入库、检索通过，测试资源为 `viking://resources/fpk-nas-storage-adfa3ab9e437`。
- 使用共享目录中的 GGUF、`--network none` 验证 512 维 CPU Embedding 通过；模型 SHA-256 与固定值一致。
- 容器 `running/healthy`、`privileged=false`，安装临时凭据文件已删除。主 NAS 管理页和普通应用 URL 均返回 200，FN Connect 和 nginx 服务仍 active。
- Linux 25 项测试通过；Windows 跳过 5 项 Linux 生命周期测试。Chrome 控制返回 `Debugger unattached`，未将实机配置及挂载检查冒充设置页视觉验收。
- 本地与 SMB 兼容安装包 SHA-256 均为 `876dba486171928d69601e66620d370d767db227f920891f57f1a1d233de5f2d`。
- 本轮未验证标准版或其他 NAS。共享目录不自动建立索引，也不包含在私有工作区快照中，应另行配置 NAS 文件备份。
