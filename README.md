# OpenViking 飞牛 FPK（测试版）

基于 OpenViking `v0.4.16` 的 Docker 应用包。当前模式是**纯文本**：不配置 VLM，不要求外部生成模型 API，不提供图片理解或生成式目录摘要。本地版使用 BGE 512 维 CPU Embedding，不使用 RK3588 NPU。

## 当前验收边界

当前源码版本 `0.4.16-8`：标准版和本地版的应用 ID 均统一为 `openviking`，入口与 `desktop_applaunchname` 为 `openviking.main`。fnpack 1.2.3 仍拒绝无后缀入口 `openviking`，因此精确绑定 `openviking.<NAS域名>` 尚未实现；按已观察规则预计生成 `openviking-main`，仍待部署验证，不将其说成用户要求的精确前缀。两种模式不能并装，也不能直接切换已有 Embedding 模型。Compose 项目及容器统一为 `openviking` / `openviking-fnos`，本地离线启停按 `settings.json` 的 `variant=local` 判断。新配置位置统一为 `/var/apps/openviking/var/openviking/ov.conf`，下文旧目录是历史验收路径。

**旧设备迁移尚未执行。** `openviking-local` → `openviking` 是应用身份变更，不是原地升级。安装前必须停止旧应用，制作逐文件校验的完整快照并另存应用目录之外，保留数据卸载旧包，随后将快照恢复到新应用数据目录，并验证原 Key、工作区与检索结果。安装器检测到旧包仍在时会拒绝安装。不要删除旧数据；当前 NAS 仍保留旧安装。

2026-09-08 已在 RK3588 / ARM64 飞牛设备完成本地 Embedding 离线测试、FPK 安装、启动、健康检查、Studio HTTP 访问、鉴权和中文文本入库/检索。无 VLM 时，上游目录摘要可能显示 `Directory overview is not ready`；正文检索可用。

本地离线包已在同一设备通过飞牛应用中心从 `0.4.16-1` 升级至 `-4`，再升级至 `0.4.16-5`；健康检查、自动 `fnos/owner` 工作区、旧文档检索、停机快照恢复和保留数据卸载重装均通过。`-5` 的首次连接入口已通过浏览器错误 Key 拒绝和成功连接验证。包内包含 ARM64 Docker 镜像与模型，不依赖预加载镜像。早期 `-1`/`-2` 预加载测试包不能用于通用离线交付。公网子域名仍待登录后验证；标准版及其他设备尚未实机验收，不宣称正式发布完成。详见 [实机验收记录](docs/acceptance-20260908.md)。

## FN Connect 入口修复（0.4.16-7，待安装）

用户从互联网电脑点击 `-6` 图标后，飞牛实际生成 `https://openviking-local-main.helywin.fnos.net/app/openviking-local/studio/fnos.html`，返回 OpenViking `NOT_FOUND`。NAS 的 `1933` 端口请求相同路径可复现同一错误；用户移除 `/app/openviking-local` 后，确认公网显示连接页。因此问题是入口混用了端口服务和系统网关路径，不是 FN Connect 无法转发该应用。

`-7` 恢复纯端口入口 `/studio/fnos.html`，移除多余的 Socket 适配器及其安装目录挂载，不关闭认证、不改工作区数据。不要按应用名猜域名，使用飞牛图标实际生成的链接。设备当前已安装 `-6`，修正版尚待安装；公网已确认范围仅为用户看到连接页，不等于远程登录、上传或检索均通过。

旧网关适配器曾通过独立测试，但不能代表图标访问链路正确；该临时实现已移除。相关排查历史见验收记录。

当前 12 项回归测试在 Windows 与 Linux 上均通过，包括新增的端口入口路径检查。

## 安装与权限

安装 FPK 后，在应用中心启动并点击“打开”，进入 `http://NAS地址:1933/studio/fnos.html`。输入安装向导设置的 OpenViking Root API Key，即可自动连接工作区并进入 Studio。标准版需填写 OpenAI 兼容 Embedding 地址、模型和维度；local 版包含固定 GGUF 模型，不需要模型 API Key。两版都需要至少 24 字符的 OpenViking Root API Key。

生命周期脚本以 root 运行，用于 Docker 镜像检查和隔离配置助手；不修改 NAS root 密码，不把应用用户加入 docker 组。服务容器不挂载 Docker socket、不使用 privileged，仅挂载应用数据和只读模型。HTTP 服务仅建议在可信局域网使用；没有配置 HTTPS，不要直接暴露公网。

Root API Key 是 OpenViking 管理凭据，**不是 NAS root 密码**。上游 Root Key 不能直接进行数据操作。启动器会在首次启动时创建 `fnos` 工作区及 `owner` 用户，凭据以 0600 保存在应用私有数据目录的 `fnos-workspace.json`，已有工作区不覆盖。连接页通过上游认证接口读取该工作区当前用户凭据，不轮换或重新生成 Key；只在当前浏览器保存工作区管理凭据，不保存 Root Key。仅在可信设备使用；其他自定义工作区仍通过 Studio 原有连接设置进入。

配置位于 `/var/apps/openviking-local/var/openviking/ov.conf`（标准版去掉 `-local`），权限 0600。实机验收使用临时生成的 Root Key；管理员可通过 sudo 在本机查看，或在飞牛应用配置向导中设置自己的 Root Key 后重启。测试用户凭据保存在设备私有测试目录的 `smoke-user.json`，不打入 FPK、不提交仓库。请勿把这些文件发到公共渠道。

## 构建

需要 Python 3.10+、Docker 和官方 fnpack。Windows 上使用 Linux fnpack 容器构建，确保 FPK 生命周期文件保留执行权限：

```powershell
python scripts/build.py --variant standard --arch amd64 --container-build --fnpack .tools/fnpack-linux-amd64
python scripts/build.py --variant standard --arch arm64 --container-build --fnpack .tools/fnpack-linux-amd64
python scripts/download_model.py
```

本地版先在 ARM64 环境构建 `docker/local/Dockerfile`，将镜像发布到自己的仓库并获取 digest，然后：

```powershell
python scripts/build.py --variant local --arch arm64 --container-build --fnpack .tools/fnpack-linux-amd64 --image YOUR_REGISTRY/IMAGE@sha256:YOUR_DIGEST --model .build/models/bge-small-zh-v1.5-f16.gguf --model-sha256 ab9b81d9cd329c712eee379cf0068eabe6a5e2a01d0def61535eba9384085e2c
```

仅用于已有镜像的测试设备，可加 `--preloaded-image` 并将 `--image` 设置为该设备的完整 `sha256:镜像ID`。每次构建生成 FPK、SHA-256 和构建元数据；元数据的默认状态不是验收证明。

离线交付使用 `docker save` 导出完整派生镜像，构建时增加 `--image-archive 路径`，同时把 `--image` 设置为对应完整镜像 ID，不再使用 `--preloaded-image`。构建验证镜像配置摘要、模型摘要，安装校验镜像归档 SHA-256 后加载。镜像、模型和含密配置均不提交 Git。

本地版由 `cmd/main` 管理自身 Compose 项目的启停，先加载镜像再以 `--pull never` 启动。原因是实机 fnOS 的 `docker-project` 在升级回调前拉取镜像，导致仅在回调加载离线镜像仍然失败。标准版仍使用 `docker-project` 资源管理。

## 验证与数据保护

```powershell
python -m unittest discover -s tests -v
```

`tests/smoke_local.py` 在派生镜像中挂载 `/models` 后执行，可使用 `--network none` 验证离线 Embedding。`tests/smoke_http.py` 在验收设备上测试已运行的服务，会创建专用测试工作区及测试文本；只读配置挂载到 `/config`，私有测试目录挂载到 `/tests`，用户凭据以 0600 保存。设置 `SMOKE_VERIFY_URI` 可仅检索已有测试文本，用于停启后验证持久化。

修改配置时保留上一份配置，拒绝直接切换现有 Embedding 模型/维度。**配置备份不等于数据备份**：新的升级前脚本会在停止应用后复制完整数据并逐文件验证 SHA-256。快照位于应用 `var/backups`；恢复助手先检查摘要，恢复前状态保留在 `var/pre-restore-*`。这些目录可能含凭据，应仅允许管理员访问。旧版本升级脚本不一定具备完整快照能力，首次从旧测试包升级前必须另行停机备份。不要在唯一一份生产数据上测试卸载或删除数据。

## 来源

- [OpenViking 源代码（v0.4.16）](https://github.com/volcengine/OpenViking/tree/v0.4.16)：上游许可证及其依赖许可证随上游项目维护；发布派生镜像前应履行相应源码提供与通知义务。
- [BGE GGUF 来源](https://huggingface.co/CompendiumLabs/bge-small-zh-v1.5-gguf)：模型与代码独立授权，发布时保留模型来源和对应许可。
- [飞牛开发文档](https://developer.fnnas.com/docs/)：FPK 使用官方 Docker 模板；当前图标仍是模板占位图标。
