# linux-zakofox

基于上游 stable 内核重建的桌面内核，融合 **Liquorix / zen 调优** 与 **cjktty 中文控制台**，
产出 Arch Linux 软件包 `linux-zakofox` 与 `linux-zakofox-headers`。

## 组成

| 部分 | 来源 | 说明 |
| --- | --- | --- |
| 基线 | `linux-7.3.3.tar.xz` (kernel.org) | 上游 stable，sha256 `79c66dde…c764f3d1` |
| 调度器 | `0001-zakofox-prjc-pds-7.3.patch` | tkg `0009-prjc.patch`，Project C 的 PDS/BMQ |
| 中文控制台 | `0002-zakofox-cjktty-7.2.patch` | cjktty，16×16 / 32×32 全 CJK 点阵字体 |
| zen 调优 | `01xx-zen-*.patch` | 从 Liquorix `v7.2.15-lqx2` 的 zen-sauce 中按子系统拆分并移植到 7.3 |

补丁按文件名排序应用：`0001` → `0002` → `0100` … `0200`。

## 关键特性

- **调度器**：`CONFIG_SCHED_PDS`（Liquorix 同款，桌面交互优先），可选 `SCHED_BMQ`
- **抢占模型**：`CONFIG_PREEMPT=y`，静态非 dynamic（与 Liquorix 一致）
- **时钟频率**：`CONFIG_HZ=1000`，`NO_HZ_FULL`，`RCU_NOCB_CPU_DEFAULT_ALL`
- **CPU 优化**：`CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE_O3`（`-O3`）
- **zen 调优**：`CONFIG_ZEN_INTERACTIVE=y`（block / VM / EEVDF / PDS / CPUFreq / split-lock 六类）
- **中文控制台**：`CONFIG_FONT_CJK_16x16` + `CONFIG_FONT_CJK_32x32`
- **网络**：BBR3 拥塞控制（`CONFIG_TCP_CONG_BBR3`），默认仍为 BBR
- **存储**：zen 的 IO 调度器默认策略（BFQ 优先，多队列回落到 Kyber）；zram 沿用 7.3 上游实现
- **虚拟光驱**：`drivers/scsi/vhba`（`CONFIG_VHBA=m`，`VHBA-MODULE`）
- **PCI**：ACS override 补丁
- **CPU 上限**：`CONFIG_NR_CPUS=128`（非 MAXSMP）
- **调试信息**：关闭（`DEBUG_INFO_NONE`），体积小、编译快

内核版本号：`7.3.3-zakofox`。

## 构建

### 本地

```bash
makepkg -s
```

需要 `base-devel bc cpio gettext libelf pahole perl python tar xz zstd`。

### GitHub Actions

`.github/workflows/build.yml` 在 `archlinux:base-devel` 容器内用 `makepkg` 构建，
产物以 artifact 形式上载。触发方式：推送 `main`（改动 `PKGBUILD` / `*.patch` / `*.config`）、
手动 `workflow_dispatch`（可指定并行任务数），或推送 `v*` tag。

## 目录

```
PKGBUILD                打包脚本（pkgbase=linux-zakofox）
zakofox-x86_64.config   内核配置（唯一事实来源）
0001-*.patch … 0200-*.patch
SHA256SUMS              补丁与配置校验值
scripts/gen-cjk-font.py 用 Maple Mono 生成 CJK 点阵字体的可选脚本
```

## 版本演进

`pkgver` 跟随上游 stable。升级时：

1. 改 `PKGBUILD` 里的 `pkgver` 与 tarball `sha256sums`，并同步 workflow 的 `KERNEL_VERSION`
2. 验证 `0001`（prjc）在新版本上能干净应用，否则换用对应版本的 tkg `0009-prjc.patch`
3. 验证 `0002`（cjktty）——7.3 起 fbcon 的旋转缓冲被内联进 `struct fbcon_par`，
   升级到 7.4 时需要重新对齐
4. `01xx` zen 补丁按需 rebase；`0120`（mm/zswap）与 `0110`（sched）最容易受上游重构影响

## 许可

内核本体 GPL-2.0-only。各补丁遵循其上游原始许可
（zen-sauce / Liquorix 为 GPL-2.0，prjc 为 GPL-2.0，cjktty 为 GPL-2.0）。
