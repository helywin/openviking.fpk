# OpenViking 飞牛 FPK（测试版）

基于 OpenViking `v0.4.16`。本地版使用 BGE 512 维 CPU Embedding，不配置 VLM，不要求外部生成模型 API，不提供图片理解或生成式摘要，也未启用 RK3588 NPU。

## 当前版本与访问

`0.4.16-9` 已在用户的 RK3588 / ARM64 NAS 安装并验证。应用显示名称统一为 **OpenViking**。入口保留普通 URL：`http://NAS地址:1933/studio/fnos.html`；不新增统一网关或子域名绑定，不改 FN Connect 设置。飞牛自身的自动转发行为由平台管理，本包不保证任意自定义域名。

新安装默认应用 ID 为 `openviking`。升级早期设备时使用 `--app-id openviking-local`，保留旧安装身份、配置、容器和工作区；这个内部 ID 不作为显示名称。两种模式不能并装，也不能直接切换已有 Embedding 模型。

## NAS 文件与模型

应用通过 `config/resource` 声明两个专用共享目录。可在飞牛文件管理器的“应用文件”中查找 `openviking`。

| 内容 | NAS 实机路径 | 容器路径 | 容器权限 |
| --- | --- | --- | --- |
| Embedding 模型 | `/vol1/@appshare/openviking/models` | `/models` | 只读 |
| 用户文档 | `/vol1/@appshare/openviking/documents` | `/nas/documents` | 只读 |
| 私有配置、Key、索引 | `/var/apps/<应用ID>/var/openviking` | `/app/.openviking` | 读写，不共享 |

`vol1` 是当前设备实测值；代码从飞牛的 `TRIM_DATA_SHARE_PATHS` 解析路径，不固定存储空间。首次启动从离线包复制固定 GGUF 到共享模型目录，复制前后验证 SHA-256；已有模型只校验、不覆盖。模型被替换或损坏时拒绝启动，避免悄悄改变索引对应的模型。

飞牛“已授权文件”列表用于管理员额外授权的已有目录，与应用声明的专用共享目录不是同一个列表。本版只映射以上专用目录，没有给整个 NAS 或其他个人文件夹授权；该手动授权列表可以为空。把文档放进目录不等于自动建立索引，仍需导入 OpenViking。

已在 NAS 验证用户能读取模型、写入文档目录，容器不能改写两者；从共享目录读取测试文本后，经过上传、入库和检索成功。验证示例为 `nas-storage-check.txt`，不含私有数据。

## 配置与数据保护

首次连接页需要安装向导设置的 OpenViking Root API Key（至少 24 字符），不是 NAS 密码。连接页读取当前工作区用户凭据后进入 Studio，不轮换 Key；只在受信任浏览器保存工作区凭据，不保存 Root Key。HTTP 仅用于可信局域网，不要把 `1933` 直接暴露到公网。

配置 `ov.conf` 和初始化记录 `fnos-workspace.json` 保存在应用私有目录，权限 0600，不放进共享目录。服务容器不挂载 Docker socket、不使用 privileged。生命周期脚本需要 root 操作自己的 Docker 项目，不修改系统账号或 FN Connect。

升级前制作完整工作区停机快照并验证逐文件摘要，必要时另存应用目录外。工作区快照不包含外部共享目录；`documents` 请另外使用 NAS 备份。恢复助手保留恢复前数据。卸载选择保留数据时不删除工作区；无论该选项如何，应用脚本都不清除用户共享文档和共享模型。

## 构建

需要 Python 3.10+、Docker 和官方 fnpack。Windows 使用 Linux fnpack 容器构建，保留生命周期脚本的执行权限：

```powershell
python scripts/build.py --variant standard --arch amd64 --container-build --fnpack .tools/fnpack-linux-amd64
python scripts/download_model.py
python scripts/build.py --variant local --app-id openviking-local --arch arm64 --container-build --fnpack .tools/fnpack-linux-amd64 --image sha256:YOUR_IMAGE_ID --image-archive YOUR_IMAGE_ARCHIVE --model .build/models/bge-small-zh-v1.5-f16.gguf --model-sha256 ab9b81d9cd329c712eee379cf0068eabe6a5e2a01d0def61535eba9384085e2c
```

本地镜像使用 `docker/local/Dockerfile` 在 ARM64 环境构建。离线归档用 `docker save` 导出；构建时校验镜像配置 ID 和 GGUF 摘要，安装时再次校验归档。新设备省略 `--app-id openviking-local`，使用默认身份 `openviking`。仅预加载镜像的测试包可用 `--preloaded-image`，不能冒充通用离线交付。

所有模式由 `cmd/main` 管理自身 Compose 项目：先准备镜像、解析专用共享目录、校验模型，再启动。运行时的只读挂载写入私有 `nas-volumes.json`；不依赖 Docker 项目资源在升级回调之前拉取镜像，也不会清空 `data-share` 资源声明。

## 验证边界

```powershell
python -m unittest discover -s tests -v
```

Windows 跳过 Linux 生命周期脚本测试；完整测试在镜像内执行，25 项通过。覆盖配置、快照、工作区初始化、两种包身份、显示名称、共享目录声明、模型校验、只读挂载以及启停卸载。

实机已通过 `-7` → `-9` 安装、旧文档检索、共享目录读取/只读拒写/入库检索、共享模型摘要及普通 URL 健康检查。官方 `appcenter-cli install-local` 在该设备上执行停启和重装流程，保留了原工作区；应用外快照已留存。浏览器控制当前返回 `Debugger unattached`，未把设备配置检查冒充 Chrome 视觉验收。

`tests/smoke_storage.py` 在安装的容器内验证专用共享目录；`tests/smoke_local.py` 可用 `--network none` 验证 NAS 共享模型离线推理。标准版和其他设备未做本轮实机验收，不宣称正式发布完成。详细历史及限制见 [实机验收记录](docs/acceptance-20260908.md)。

## 来源

- [OpenViking v0.4.16](https://github.com/volcengine/OpenViking/tree/v0.4.16)：发布派生镜像时需履行上游及依赖许可证要求。
- [BGE GGUF 来源](https://huggingface.co/CompendiumLabs/bge-small-zh-v1.5-gguf)：模型与代码独立授权，发布时保留来源与许可。
- [飞牛应用资源](https://developer.fnnas.com/docs/core-concepts/resource)：共享目录及应用资源定义；当前图标仍为官方模板占位图标。
