# RK3588 RKNPU 加载诊断

诊断日期：2026-09-08。状态：**已定位系统层设备树/驱动匹配问题，尚未修复，NPU 推理未通过。**

用户后续要求：优先完成 OpenViking 其他功能，RKNPU 仅进行无害测试，保持当前 NAS 系统、启动配置、设备树和驱动状态不变。以下涉及设备树适配与重启的内容均为未来保底方案，未获当前激活授权。

## 实机证据

目标板为 Orange Pi 5 Plus（RK3588、aarch64），系统为 fnOS 1.2.0401，当前内核为 `6.18.18.c963-trim`。以下证据来自安装飞牛 AI 引擎后的只读检查和一次 Runtime 初始化测试，不包含主机地址或凭据。

| 检查项 | 实际结果 | 含义 |
| --- | --- | --- |
| 飞牛 AI 引擎 | `trim.ai-runtime-rk3588` 1.0.0 已安装，包含 Python 3.11、RKNN Lite2 2.3.2、`librknnrt.so` 和 RK3588 `.rknn` 模型 | 用户态运行库和模型已经存在 |
| 内核模块 | `rknpu` 0.9.8 已加载；文件为 `/lib/modules/6.18.18.c963-trim/updates/trim/rk_vcodec/rknpu.ko`；vermagic 与内核匹配 | 不是单纯缺少模块或模块版本字符串不匹配 |
| 模块元数据 | 普通 alias 为 `rockchip-rknpu`；依赖 `rockchip_opp_select`、`rockchip_system_monitor` | 不能仅凭 alias 推断设备已经匹配或初始化 |
| 模块二进制 | 内部含 `rockchip,rk3588-rknpu` 和 device-tree data/entry missing 字符串，不含 `rockchip,rk3588-rknn-core` | 实际安装模块与主线逐核心 compatible 不匹配，与官方源码对照一致 |
| 平台设备 | `fdab0000.npu`、`fdac0000.npu`、`fdad0000.npu` 均存在，均无 `driver` 软链接 | 三个 NPU 设备均未绑定驱动 |
| 设备树匹配 | 三个设备的 compatible 均为 `rockchip,rk3588-rknn-core`，status 为 `okay`；modalias 为 `of:NnpuT(null)Crockchip,rk3588-rknn-core` | 使用 Linux 主线的逐核心设备描述 |
| 驱动目录 | `/sys/bus/platform/drivers/RKNPU` 只有 `bind`、`module`、`uevent`、`unbind` | 驱动已注册，但没有绑定任何平台设备 |
| 内核日志 | 三个 NPU 加入 IOMMU group 10、11、12，没有 RKNPU probe/初始化记录 | IOMMU 建组不等于 NPU 驱动已经工作 |
| 设备节点 | `/dev/dri` 只有显示设备 `card0`，未发现 RKNPU 节点 | RKNN Runtime 没有可打开的 NPU 设备 |
| Runtime 测试 | `load_rknn()` 返回 `0`；`init_runtime()` 返回 `-1`，报 `failed to open rknpu module/device`、`RKNN_ERR_FAIL` | 模型文件可读取；硬件运行时初始化失败；没有执行成功的 NPU 推理 |
| 动态设备树支持 | 内核配置为 `# CONFIG_OF_OVERLAY is not set`；不存在 configfs device-tree overlays 入口 | 当前没有可用的标准运行时 DT overlay 路径 |

内核配置检查未找到 `DRM_ACCEL_ROCKET`、`OF_CONFIGFS` 或 `ROCKCHIP_RKNPU` 配置项；此处不将“未找到配置项”解释为已经验证所有外置模块构建选项。`/sys/class/accel` 不存在。

## 根因判断

当前系统将**主线逐核心设备树**与 **Rockchip vendor RKNPU 用户态/驱动栈**组合使用，匹配方式不一致，导致模块存在而平台设备未绑定。AI 引擎安装解决了用户态依赖，不会自动改变已经启动的设备树。

Linux 6.18 的 [RK3588 设备树](https://github.com/torvalds/linux/blob/v6.18/arch/arm64/boot/dts/rockchip/rk3588-base.dtsi) 定义三个 `rockchip,rk3588-rknn-core` 节点；每个节点的三块小寄存器区域分别表示同一核心的 `pc`、`cna`、`core`。其对应的 [Rocket 驱动](https://github.com/torvalds/linux/blob/v6.18/drivers/accel/rocket/rocket_drv.c) 匹配该 compatible。

Rockchip 官方 [RKNPU 驱动](https://github.com/rockchip-linux/kernel/blob/develop-6.1/drivers/rknpu/rknpu_drv.c) 的 RK3588 匹配项为 `rockchip,rk3588-rknpu`。官方 [vendor 设备树](https://github.com/rockchip-linux/kernel/blob/develop-6.1/arch/arm64/boot/dts/rockchip/rk3588s.dtsi) 使用一个聚合 NPU 节点，将三个完整核心地址区域、三个 IRQ、时钟、复位、供电域和 IOMMU 统一描述。两种描述的资源布局与名称不同，**不能仅改 compatible 字符串，也不能用 `driver_override` 强行绑定现有逐核心节点**。

实际安装模块的二进制字符串已经核对：包含 `rockchip,rk3588-rknpu`，不包含 `rockchip,rk3588-rknn-core`，与上述匹配差异一致。上游源码用于解释资源布局；飞牛安装的模块可能带有补丁，后续候选修复仍需核对运行设备树的完整资源，不能把上游所有实现细节直接视为该二进制的已验证事实。

[Linux Rocket 文档](https://docs.kernel.org/accel/rocket/index.html)说明其用户态栈为 Mesa Gallium。Rocket 使用自身的 compute-accel/ioctl 接口，不能视为现有飞牛 `librknnrt.so` 的直接替代品。官方 [RKNN Toolkit2 文档](https://github.com/airockchip/rknn-toolkit2)也将 Lite2/Runtime 与负责硬件访问的 RKNPU 内核驱动明确分开。

## 未来保底修复路径（当前不执行）

1. 已读取的 `/boot/orangepiEnv.txt` 指定 `fdtfile=rockchip/rk3588-orangepi-5-plus.dtb`，`overlays`、`user_overlays` 均为空，`overlay_prefix=rk3588`。`boot.cmd` 读取该配置并加载 `dtb/${fdtfile}`，支持启动时从 `overlay-user` 加载 `user_overlays`，覆盖应用失败时恢复原 DT。`/boot/dtb-6.18.18-trim` 解析到 `/boot/dtb`，`/boot/extlinux/extlinux.conf` 不存在。候选基线因此应为 `/boot/dtb/rockchip/rk3588-orangepi-5-plus.dtb`；激活前还需核对实际执行的 `boot.scr` 与所读 `boot.cmd` 一致。
2. 保存当前 DTB、引导配置的备份和校验值，准备能实际选择的原配置回滚启动项，并确认失联后的本地控制台或恢复介质可用。备份文件本身不等于已经具备恢复能力。
3. 在离线副本中准备与**当前板型、当前内核及当前 vendor 模块**一致的聚合 NPU 描述，完整核对寄存器、IRQ specifier 单元数、clock/reset 名称、供电、IOMMU 和 OPP。禁用冲突的逐核心描述，避免两个驱动占用同一硬件。不要直接套用另一块板、另一版内核的 DTB，也不要先替换整套内核。
4. 对候选 DTB 或启动时 overlay 进行编译/反编译与差异检查；先确保差异只涉及必要 NPU 资源，再提交可审查的候选、部署步骤和回滚步骤。现有引导脚本已支持启动时 overlay，可优先评估保留基础 DTB 的方案；它不依赖内核运行时 `CONFIG_OF_OVERLAY`，但仍需要改动启动配置和重启。目标系统有 `/usr/bin/dtc`，未找到 `fdtget`、`fdtoverlay`，完整离线合并验证需准备相应工具。离线检查通过仍不代表能在硬件上启动或完成推理。
5. **在用户明确授权修改启动 DTB/配置与一次重启，并具备恢复保障后**，部署候选并进行启动验证。当前阶段没有执行这些操作。

当前内核关闭 `CONFIG_OF_OVERLAY`，无法通过通常的运行时 overlay 完成无重启修复。自制内核模块动态重建平台设备属于额外的内核开发，不作为这台在用 NAS 的最小修复方案。重复安装 AI 引擎、重复 `modprobe`、调整容器设备映射或 Python 参数，均不能修复当前未绑定的宿主机 NPU 设备。

若正确的设备树仍触发新的 probe 失败，依据实际日志继续处理驱动移植、供电或 IOMMU 问题；不得在尚未测试时承诺只改 DTB 一定解决全部兼容性。

## 验收标准

- RKNPU 平台驱动实际绑定聚合 NPU 设备，并产生明确的成功初始化日志。
- 发现属于 RKNPU 的设备节点，按设备归属判断，不硬编码 `renderD128` 或 `renderD129`。
- 使用 AI 引擎自带运行库与本机已有 RK3588 模型，确认 `init_runtime()` 成功。
- 使用模型所需的真实输入完成推理，校验输出形状、有限数值等基本正确性，并结合 NPU 中断计数或负载变化确认硬件参与。
- 验证 NAS 必要服务和 OpenViking 原有功能仍正常；只有上述证据通过后才能称为“RKNPU 已修复”。

本次没有卸载/替换驱动，没有修改内核、设备树或启动配置，没有重启系统，也没有宣称 NPU 推理通过。

## 本地 FnNAS 源码与原构建包补充核对

已核对 `D:/code/fnnas` 的 `2393b104c592647612567666f9ba150424a2fdf1`。该仓库包含镜像/内核二进制重打包脚本，不包含 RKNPU C 源码或 RK3588 DTS 源码。`rekernel` 先加入从 `ophub/kernel` 下载的补充 DTB，再用基础镜像/官方 DEB 中同名 DTB 覆盖；模块来自 fnOS 镜像/DEB。`renas` 原样解包这些 DTB/模块，未做 RKNPU binding 适配，且为 Orange Pi 5 Plus 生成空 `overlays`、`user_overlays`。仓库没有现成的匹配方案可无害启用。

原构建包 `dtb-rockchip-6.18.18-trim.tar.gz` 内板级 DTB 与当前 `/boot/dtb/rockchip/rk3588-orangepi-5-plus.dtb`、`/usr/lib/linux-image-6.18.18.c963-trim/rockchip/rk3588-orangepi-5-plus.dtb` 三者 SHA256 均为：

```text
136114654daf6d633d3891f6c247dc89441a340bd0209e41f30cdbf405cf4cda
```

这排除了“启动误选旧 DTB，而新内核包已有匹配版本”的解释。真实原构建 DTB 经本地 `dtc 1.7.0` 反编译/再编译后，771 个节点全部属性保持相同；只读审计确认三个启用的逐核心 NPU 节点与 vendor compatible 匹配数为 0。编译验证的是现有基线，不是已经修复的候选。

FnNAS 仓库新增 `tools/audit_rknpu_dtb.py` 作为不修改系统的离线检查入口，源码追踪与复验说明见其 `docs/rknpu-integration-audit.md`。目前可继续 CPU embedding 与 OpenViking 其他功能；未发现不改变宿主系统即可让现有 RKNN Runtime 使用 NPU 的方案。
