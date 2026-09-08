---
title: "OpenViking 飞牛 fnOS FPK 打包方案"
status: "已实现测试版，部分真机验收完成"
updated_at: "2026-09-08"
---

# OpenViking 飞牛 fnOS FPK 打包方案

> 2026-09-08 实施变更：按用户要求，本轮仅做纯文本，不配置 VLM。下文 VLM、自动升级回滚等内容属于原规划，不表示已实现。实际功能、权限与未验收项以根目录 README.md 为准。本地 Embedding、FPK 安装及中文 HTTP 检索已在 RK3588 上验证；生命周期需要 root 权限访问 Docker，但服务容器不挂载 Docker socket。

## 1. 目标

将 OpenViking 打包为可在飞牛 fnOS 应用中心手动安装的 `.fpk`，提供：

- Docker 项目托管与应用生命周期管理；
- 固定端口的桌面入口，打开 OpenViking Web Studio；
- 配置、工作区和模型数据持久化；
- 安装/配置/卸载向导；
- x86_64 与 ARM64 的清晰发布边界；
- RK3588 真机可用的本地文本 Embedding 版本；
- 安装、重启、升级和卸载的可验证验收流程。

第一版不以“上架应用中心”为目标，先交付可手动安装、可升级、可回滚的 FPK。

## 2. 已核对的上游事实

截至 2026-08-31：

- OpenViking 当前发布版本为 `v0.4.16`；
- 官方镜像为 `ghcr.io/volcengine/openviking:v0.4.16`；
- 官方镜像清单同时包含 `linux/amd64` 与 `linux/arm64`；
- 容器默认通过 `1933` 提供 HTTP API 和 `/studio`；
- 容器内持久化根目录为 `/app/.openviking`；
- Docker 入口默认监听 `0.0.0.0`，因此 `ov.conf` 必须配置 `server.root_api_key`；
- 官方镜像默认同时启动 VikingBot；FPK 第一版不需要该能力，应明确关闭；
- `/health` 只表示进程存活，`/ready` 才检查存储、Embedding 等依赖是否就绪。

重要限制：官方 `v0.4.16` 镜像构建时没有安装 `openviking[local-embed]`。只在配置中选择 `provider=local` 会因为缺少 `llama-cpp-python` 而启动失败。

参考：

- [OpenViking Docker 部署](https://github.com/volcengine/OpenViking/blob/v0.4.16/docs/en/guides/03-deployment.md)
- [OpenViking v0.4.16 Dockerfile](https://github.com/volcengine/OpenViking/blob/v0.4.16/Dockerfile)
- [OpenViking v0.4.16 Python 可选依赖](https://github.com/volcengine/OpenViking/blob/v0.4.16/pyproject.toml)
- [OpenViking 官方镜像清单](https://github.com/volcengine/OpenViking/pkgs/container/openviking/1156390034?tag=v0.4.16)
- [飞牛 fnOS 开发文档](https://developer.fnnas.com/docs/)

## 3. 发布物设计

不把“镜像支持 ARM64”直接等同于“所有模型能力均支持 RK3588”。建议使用同一套 FPK 工程生成两个边界明确的发布物。

### 3.1 标准版

- App ID：`openviking`
- OpenViking：官方多架构镜像；
- Embedding：远程 API 或用户已有的独立 Ollama 服务；
- VLM：远程 API；
- 初始 `platform`：在 amd64 和 arm64 都完成真机验收前，分别构建和声明；两端验收通过后才能改为 `platform=all`；
- 适合资源有限、希望安装简单的 NAS。

### 3.2 RK3588 本地 Embedding 版

- App ID：`openviking-local`；
- 初始 `platform=arm`；
- 使用基于官方 `v0.4.16` 制作的派生 ARM64 镜像；
- 派生镜像必须预装并固定 `llama-cpp-python` 版本；
- Embedding 使用 OpenViking 内置的 `bge-small-zh-v1.5-f16`；
- VLM 仍使用远程 API；
- 完成其他架构验收前不声明 `platform=all`。

这一路径在 RK3588 上使用 ARM CPU 指令执行推理，不会自动使用 RK3588 NPU。NPU 加速属于独立的 RKNN Embedding 服务项目，不纳入第一版 FPK。

## 4. RK3588 与本地 Embedding

OpenViking 当前内置 local provider 只注册了一个模型：

| 字段 | 值 |
|---|---|
| provider | `local` |
| model | `bge-small-zh-v1.5-f16` |
| dimension | `512` |
| input | `text` |
| 格式 | GGUF F16 |
| 文件名 | `bge-small-zh-v1.5-f16.gguf` |
| 当前文件大小 | `47,886,240` bytes |
| 推理后端 | `llama-cpp-python` / CPU |

参考实现：[local_embedders.py](https://github.com/volcengine/OpenViking/blob/main/openviking/models/embedder/local_embedders.py)

模型文件默认会下载到 `~/.cache/openviking/models`。在官方容器中 `HOME=/app`，因此默认位置是 `/app/.cache/openviking/models`，不在 `/app/.openviking` 持久化挂载内。FPK 不得依赖这个默认路径。

本地版采用以下二选一策略：

1. 推荐：将经过 SHA-256 校验的 GGUF 放入 FPK 的 `app/models/`，以只读方式挂载到 `/models`；
2. 在线版：下载到 `${TRIM_PKGVAR}/models`，挂载到 `/models`，同时记录并校验 SHA-256。

不允许每次容器重建后重新从 Hugging Face 下载，也不允许未校验下载结果就启动服务。

本地版配置示例：

```json
{
  "server": {
    "port": 1933,
    "root_api_key": "由安装向导提供"
  },
  "storage": {
    "workspace": "/app/.openviking/data",
    "agfs": { "backend": "local" },
    "vectordb": { "backend": "local", "name": "context" }
  },
  "embedding": {
    "dense": {
      "provider": "local",
      "model": "bge-small-zh-v1.5-f16",
      "model_path": "/models/bge-small-zh-v1.5-f16.gguf",
      "dimension": 512,
      "input": "text"
    }
  },
  "vlm": {
    "provider": "由安装向导提供",
    "api_base": "由安装向导提供",
    "api_key": "由安装向导提供",
    "model": "由安装向导提供"
  },
  "log": {
    "level": "INFO",
    "output": "stdout"
  }
}
```

注意：Embedding 模型、维度或模型文件身份发生变化时，已有向量索引可能不兼容。配置界面不得把“切换模型”表现为无损操作，升级流程也不得静默替换模型。

## 5. FPK 工程结构

使用官方 Docker 模板初始化：

```bash
fnpack create openviking --template docker
```

目标结构：

```text
openviking/
├── manifest
├── ICON.PNG
├── ICON_256.PNG
├── LICENSE
├── app/
│   ├── docker/
│   │   └── docker-compose.yaml
│   ├── models/
│   │   ├── bge-small-zh-v1.5-f16.gguf
│   │   └── SHA256SUMS
│   └── ui/
│       ├── config
│       └── images/
│           ├── icon_64.png
│           └── icon_256.png
├── cmd/
│   ├── main
│   ├── install_init
│   ├── install_callback
│   ├── upgrade_init
│   ├── upgrade_callback
│   ├── uninstall_init
│   ├── uninstall_callback
│   ├── config_init
│   └── config_callback
├── config/
│   ├── privilege
│   └── resource
└── wizard/
    ├── install
    ├── config
    ├── upgrade
    └── uninstall
```

标准版不包含 `app/models/`。本地版必须记录模型来源、许可证和 SHA-256。

## 6. Manifest

RK3588 本地版初始示例：

```ini
appname=openviking-local
version=0.4.16-1
display_name=OpenViking Local
desc=OpenViking for fnOS with local text embedding.
source=thirdparty
platform=arm
maintainer=helywin
distributor=helywin
desktop_uidir=ui
desktop_applaunchname=openviking-local.main
service_port=1933
checkport=true
ctl_stop=true
```

`os_min_version` 不能凭空填写，应在目标 fnOS 设备完成安装测试后，将实际最低通过版本写入发布 Manifest。

第一版固定宿主机端口 `1933`，不在安装向导中提供端口选择。原因是：

- `${TRIM_SERVICE_PORT}` 来自 `manifest.service_port`；
- `app/ui/config` 也必须指向同一个端口；
- 将普通向导字段误当成 `TRIM_SERVICE_PORT` 会造成 Compose、桌面入口和状态检查不一致。

## 7. Docker Compose

标准版示意：

```yaml
services:
  openviking:
    image: ghcr.io/volcengine/openviking:v0.4.16@sha256:<multi-arch-index-digest>
    container_name: openviking-fnos
    restart: unless-stopped
    environment:
      OPENVIKING_WITH_BOT: "0"
    ports:
      - "${TRIM_SERVICE_PORT}:1933"
    volumes:
      - "${TRIM_PKGVAR}/openviking:/app/.openviking"
```

RK3588 本地版示意：

```yaml
services:
  openviking:
    image: <registry>/openviking-fnos-local:v0.4.16-1@sha256:<arm64-image-digest>
    container_name: openviking-fnos-local
    restart: unless-stopped
    environment:
      OPENVIKING_WITH_BOT: "0"
    ports:
      - "${TRIM_SERVICE_PORT}:1933"
    volumes:
      - "${TRIM_PKGVAR}/openviking:/app/.openviking"
      - "${TRIM_APPDEST}/models:/models:ro"
```

发布时必须把占位 digest 替换为实际 digest。禁止使用可漂移的 `latest`。

不要使用通用的 `container_name: openviking`，避免与用户手工部署的容器冲突。容器名、Docker project 名和 `cmd/main` 的状态检查目标必须保持稳定。

## 8. fnOS 资源与桌面入口

`config/resource`：

```json
{
  "docker-project": {
    "projects": [
      {
        "name": "openviking-local",
        "path": "docker"
      }
    ]
  }
}
```

`config/privilege` 保持最小权限：

```json
{
  "defaults": {
    "run-as": "package"
  },
  "username": "openviking-local",
  "groupname": "openviking-local"
}
```

`app/ui/config` 使用固定端口并只向管理员展示：

```json
{
  ".url": {
    "openviking-local.main": {
      "title": "OpenViking",
      "icon": "images/icon_{0}.png",
      "type": "url",
      "protocol": "http",
      "port": "1933",
      "url": "/studio",
      "allUsers": false,
      "control": {
        "accessPerm": "readonly"
      }
    }
  }
}
```

真机验收时同时测试 `type=url` 和 `type=iframe`。只有确认 Studio 的鉴权、Cookie、CSP 和跳转在 iframe 中都正常，才可以改为内嵌窗口。

## 9. 安装与配置向导

### 9.1 共同字段

- Root API Key：`password`，必填；
- VLM Provider；
- VLM API Base；
- VLM Model；
- VLM API Key：`password`，必填；
- 是否允许安装过程联网拉取镜像：明确提示。

### 9.2 标准版额外字段

- Embedding Provider；
- Embedding API Base；
- Embedding Model；
- Embedding Dimension；
- Embedding API Key：`password`。

### 9.3 本地版固定字段

- Embedding Provider 固定为 `local`；
- Model 固定为 `bge-small-zh-v1.5-f16`；
- Dimension 固定为 `512`；
- 不显示没有实际作用的“本地模型”下拉框。

生命周期脚本必须：

- 再次校验所有向导输入；
- 原子写入 `${TRIM_PKGVAR}/openviking/ov.conf`；
- 目录权限设置为 `0700`，配置文件设置为 `0600`；
- 不把 API Key、Root API Key 或完整配置写入日志；
- 不把完整配置放入 Compose 环境变量，避免通过 `docker inspect` 暴露；
- 配置写入失败时，在 `${TRIM_TEMP_LOGFILE}` 输出不含密钥的明确错误。

## 10. 生命周期与健康检查

`cmd/main` 的职责：

- `start` / `stop`：交由 fnOS Docker project 管理；
- `status`：检查目标容器存在、状态为 running，且 Docker health 不是 unhealthy；
- 状态检查不得只依赖进程名或端口占用；
- 错误信息不得包含配置和密钥。

服务启动后的验收顺序：

1. `GET /health` 返回成功；
2. `GET /ready` 返回 ready，Embedding、AGFS 和 VectorDB 均正常；
3. `/studio` 可以打开；
4. 使用 Root API Key 执行一次鉴权 API 请求；
5. 写入一份中文测试文档；
6. 等待语义处理完成；
7. 使用中文查询召回该文档；
8. 重启容器后重复查询，确认索引和配置仍在。

仅看到容器 running 或 `/health` 成功，不算安装验收通过。

## 11. 升级与卸载

升级流程必须：

- 备份旧 `ov.conf`；
- 保留 `${TRIM_PKGVAR}/openviking`；
- 使用新版本镜像 digest；
- 启动后执行 `/ready` 和最小读写检索验证；
- 验证失败时保留旧配置与数据，给出可执行的回滚说明；
- 不自动改变 Embedding provider、model、dimension 或 model identity。

卸载向导提供两个明确选项：

- 保留配置和工作区数据；
- 删除配置、工作区和在线下载的模型。

删除操作必须只针对当前 App 的已解析数据目录，禁止使用未验证变量或宽泛路径递归删除。FPK 内只读模型随应用本体卸载，不属于用户数据。

## 12. 在线、国内镜像与离线边界

引用远程 Docker 镜像的 FPK 是“在线轻量安装包”，不是离线包。安装成功依赖：

- fnOS Docker 服务可用；
- NAS 能访问对应镜像仓库；
- 镜像支持目标架构；
- 本地版模型已包含在 FPK，或模型下载地址可访问。

国内部署可以把完全相同 digest 的镜像同步到国内 Registry，但必须验证同步后的内容和架构清单。安装向导不提供任意镜像地址输入，避免不可复现和供应链风险。

真正离线交付需要额外解决镜像归档、`docker load` 权限、FPK 体积和 fnOS 生命周期支持，必须单独设计并在真机验证，不能仅把镜像 tar 放入 FPK 就宣称离线可用。

## 13. 安全与许可证

- Root API Key 和模型 API Key 不得写入仓库、构建日志或发布制品示例；
- 对外只开放 `1933`，第一版不额外开放 VikingBot 端口；
- 固定 OpenViking 版本、镜像 digest、派生镜像构建来源和依赖版本；
- 本地 GGUF 必须固定下载来源、文件大小和 SHA-256；
- 发布派生镜像或公开 FPK 前，履行 OpenViking AGPL-3.0 的源码与许可证义务；
- 同时核对并随包保留 Embedding 模型的许可证与归属信息。

## 14. 构建与验收清单

### 构建检查

- `fnpack` 版本已记录；
- `fnpack build` 成功；
- FPK 内没有 `.env`、真实密钥、临时文件和构建缓存；
- 图标尺寸、格式和大小符合 fnOS 要求；
- Manifest 的 App ID、版本、platform、端口和入口一致；
- 镜像 tag 与 digest 一致；
- 本地模型 SHA-256 校验通过。

### RK3588 真机检查

- `uname -m` 为 `aarch64`；
- Docker 报告架构为 ARM64；
- FPK 可以首次安装、启动、停止和再次启动；
- 容器使用 ARM64 镜像，不经过 QEMU 模拟；
- `/health` 与 `/ready` 均通过；
- 本地 BGE 模型完成真实中文写入和查询；
- 重启 NAS 后应用、配置、索引和模型仍可用；
- 记录首次启动耗时、空闲内存、峰值内存和批量入库吞吐；
- 验证持续负载下无过热降频导致的不可接受退化；
- 不宣称或暗示使用了 RK3588 NPU。

### 升级与卸载检查

- 从上一 FPK 版本升级后数据仍可检索；
- 升级失败时能够恢复旧配置和镜像；
- 卸载保留数据后重装可以恢复；
- 卸载删除数据只删除当前 App 数据；
- 工作区之外的文件和其他 Docker 项目不受影响。

## 15. 实施顺序

1. 用 `fnpack --template docker` 生成原始骨架并保存工具版本；
2. 先完成标准版 FPK，验证 fnOS 生命周期、固定端口和 Studio 入口；
3. 从官方 `v0.4.16` 构建 ARM64 local-embed 派生镜像；
4. 固定并校验 BGE GGUF，接入只读模型挂载；
5. 完成安装/配置/卸载向导与安全配置写入；
6. 在 RK3588 上完成真实写入、Embedding、检索、重启和升级验收；
7. 根据实测结果填写最低 fnOS 版本和资源建议；
8. 只有在 amd64 与 arm64 均通过相同验收后，才发布 `platform=all`。

## 16. 当前结论

OpenViking 可以打包成飞牛 FPK，RK3588 也有明确可行路径，但必须区分三层能力：

1. OpenViking 官方容器是否支持 ARM64：支持；
2. 官方容器是否已经包含本地 Embedding 依赖：没有；
3. RK3588 本地 Embedding 是否使用 NPU：当前方案不使用，只走 ARM CPU。

因此，第一版不能把官方镜像、本地模型下拉框和 `platform=all` 简单拼在一起。应先交付可验证的标准版，再交付经过 RK3588 真机验收的 local-embed ARM 版。
