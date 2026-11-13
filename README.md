# linux-zakofox

基于上游 Linux 稳定版自行维护的桌面内核。基线是 **linux-7.3.3**（kernel.org stable tarball），
在其上按序应用 13 个补丁，再配一份为桌面交互场景调过的 `x86_64` 配置，最终构建成 Arch Linux 软件包
`linux-zakofox` 与 `linux-zakofox-headers`。内核版本串为 `7.3.3-zakofox`。

目标场景：日常桌面、开发编译、游戏。取舍原则是**交互延迟与响应速度优先，但不拿兼容性换**：
每个改动都能用 `CONFIG_ZEN_INTERACTIVE` 或内核命令行/sysctl 关掉，不引入需要用户额外配置才能
正常运行的默认行为。已发现但尚未修掉的偏离项列在文末「已知问题」。

## 产出的包

| 包名 | 内容 | provides / conflicts |
| --- | --- | --- |
| `linux-zakofox` | `vmlinuz`、全部模块（zstd 压缩）、`System.map`、`/boot/config` | `KSMBD-MODULE` `NTSYNC-MODULE` `VIRTUALBOX-GUEST-MODULES` `WIREGUARD-MODULE` `VHBA-MODULE`；`conflicts=(linux)` |
| `linux-zakofox-headers` | `/usr/lib/modules/7.3.3-zakofox/build` 完整头文件树、`scripts/`、`Module.symvers`、`vmlinux.h`（若存在） | `linux-headers=7.3.3-1`；`conflicts=(linux-headers)` |

`vmlinuz` 装在 `/usr/lib/modules/7.3.3-zakofox/vmlinuz`，`pkgbase` 文件同步写入该目录，
供 Arch 的 `mkinitcpio` / `systemd-boot` 钩子识别。模块安装后 `depmod` 由 pacman hook 触发。
`options=(!debug !strip)`：配置里已关调试信息，因此不需要 `strip`，也避免误伤 `vmlinux` 符号表。

## 补丁清单

13 个补丁按文件名排序依次应用（`PKGBUILD` 的 `prepare()` 里逐个 `patch -Np1`）。
补丁不干净时 `patch` 会打印 `FAILED` 并留下 `.rej`，构建通常要到编译阶段才报错——
所以改完补丁务必先本地验证一遍（见「升级上游版本」）。

| 编号 | 大小 | 名称 | 一句话 |
| --- | --- | --- | --- |
| `0001` | 334 KB | prjc PDS 调度器 | 引入 Project C 的 `alt_*` 调度器实现，默认 PDS，可选 BMQ |
| `0002` | 12.4 MB | cjktty | VT/fbcon 层的 UTF-8 双缓冲 + 内置 CJK 点阵字体 |
| `0100` | 4.2 KB | 核心配置项 | `ZEN_INTERACTIVE` 总开关、`-O3` 选项、PDS 设为默认、`NAME = Zakofox` |
| `0110` | 9.9 KB | 调度参数 | EEVDF 时间片/迁移成本/带宽片调小，附 kunit 拓扑测试 |
| `0120` | 17 KB | 内存与 zswap | zswap 异步压缩请求重构、`mmdrop` 内联化、`max_map_count` 上限提高 |
| `0130` | 1.3 KB | 块层默认调度器 | 单队列默认 BFQ、多队列默认 Kyber |
| `0140` | 117 KB | 网络 | BBR3 拥塞控制、TCP ECN low 标记、相关 uapi 与 selftest 同步 |
| `0150` | 1.9 KB | CPU 调频 | `ondemand` 更激进的上调阈值，`intel_pstate=enable` 反转开关 |
| `0160` | 4 KB | 显卡 | amdgpu `ignore_min_pcap` 参数、i915 eDP sink 唤醒修复 |
| `0170` | 3.7 KB | PCI | `pcie_acs_override=` 参数，拆分 IOMMU 组 |
| `0180` | 5.6 KB | 中断与时间 | 中断强制线程化选项、tick/vtime 热路径内联 |
| `0190` | 32 KB | 虚拟光驱 | `drivers/scsi/vhba`（`CONFIG_VHBA=m`） |
| `0200` | 10.7 KB | 架构与杂项 | x86-64 ISA 等级选择、split-lock 默认放宽、evdev RCU 回收等 |

### 0001 · prjc PDS 调度器（45 个文件）

Project C 的 `alt_*` 调度器，以 `CONFIG_SCHED_ALT` 为总开关、与 CFS 二选一编译。
新增 `kernel/sched/alt_core.c`、`alt_core.h`、`alt_sched.h`、`alt_debug.c`、`alt_topology.c`、
`alt_topology.h`、`pds.h`、`bmq.h`，以及 `Documentation/scheduler/sched-BMQ.txt`；
并把调度器与内核其余部分的接口在 `SCHED_ALT` 下对齐：

- `kernel/sched/{Makefile,build_policy.c,build_utility.c,sched.h,topology.c,debug.c,stats.c,stats.h,
  syscalls.c,idle.c,cputime.c,pelt.c,pelt.h,cpufreq_schedutil.c}`
- 阻塞/唤醒链路：`kernel/locking/{rtmutex.c,ww_mutex.h}`、`kernel/delayacct.c`、`kernel/exit.c`、
  `include/linux/sched/{deadline.h,rt.h,prio.h,topology.h}`、`include/linux/sched.h`
- `kernel/workqueue.c`（per-CPU 工作队列与 alt 调度器的亲和性配合）
- `kernel/cgroup/cpuset.c`（cpuset 与 alt 调度器共存）
- `kernel/{sysctl.c,time/posix-cpu-timers.c,trace/trace_osnoise.c,trace/trace_selftest.c}`
- `fs/proc/base.c`、`fs/f2fs/checkpoint.c`（把 `sched_setscheduler` 相关的权限/回收路径适配）
- `init/Kconfig`（`choice prompt "Alternative CPU Scheduler"`）、`kernel/Kconfig.preempt`

PDS 的特点是「每 CPU 一个运行队列 + 位图选核 + 不需要全局锁」，唤醒延迟稳定，
对交互和游戏帧生成时间友好；BMQ 是同一实现的另一种任务选优策略，配置里默认不启用。

### 0002 · cjktty 中文控制台（17 个文件）

让 VT/fbcon 直接显示 UTF-8 中文，不依赖用户态字体切换：

- `drivers/tty/vt/vt.c`：控制台缓冲扩为两倍（`vc_screenbuf_size * 2`），前半是原有的 `u16`
  字符码，后半（`screenpos_utf8()`）存原始 UTF-16 码点，供全角字形查表用；`screen_glyph()`
  在遇到 `0xff`/`0xfe` 占位时返回真实码点；`kzalloc(vc->vc_screenbuf_size * 2)`。
- `drivers/tty/vt/selection.c`：选区复制按 UTF-8 还原，复制中文不乱码。
- `drivers/video/fbdev/core/bitblit.c`：`font_bits()` 增加 `ch == 0xff/0xfe` 分支，
  按 `cellsize` 选 `CJK16x16` / `CJK32x32` 字体，索引为
  `fontdata + c_utf * cellsize_utf * 2 (+ cellsize_utf)`——即每个码点占两个相邻字形槽
  （半角位 + 全角位），因此 `.charcount = 65536 * 2`。
- `drivers/video/fbdev/core/{fbcon.c,fbcon.h}` 及四个旋转实现
  `{fbcon_ccw.c,fbcon_cw.c,fbcon_rotate.c,fbcon_ud.c}`：旋转缓冲同样要多维护一份 CJK 缓冲，
  否则旋转过的控制台中文会错位。
- `lib/fonts/{Kconfig,Makefile,font.h,fonts.c,font_cjk_16x16.c,font_cjk_32x32.c}`：
  新增 `CONFIG_FONT_CJK_16x16` / `CONFIG_FONT_CJK_32x32`（`depends on FRAMEBUFFER_CONSOLE && VT_CONSOLE`，
  `select CONSOLE_TRANSLATIONS`），字体索引 `CJK16x16_IDX = 14`、`CJK32x32_IDX = 15`。

16×16 字体数据由补丁内联携带：65536 个字形 × 32 字节 = 2 MB 二进制，写成
`/* 序号 0xXXXX */` 注释的 C 数组后 `font_cjk_16x16.h` 是 12 MB 文本。
**32×32 的 `.h` 在补丁里是空文件**，见「已知问题」。

### 0100 · 核心配置项（4 个文件）

- `init/Kconfig`：新增 `config ZEN_INTERACTIVE`（`bool "Tune kernel for interactivity"`，默认 y），
  下面所有调优补丁都以它为条件——关掉即可回到纯上游行为，不需要逐个撤销补丁。
- `init/Kconfig`：`Alternative CPU Scheduler` 的默认值改为
  `default SCHED_PDS if ZEN_INTERACTIVE` + `default SCHED_BMQ`。
- `init/Kconfig` + `Makefile`：新增 `config CC_OPTIMIZE_FOR_PERFORMANCE_O3` 及
  `KBUILD_CFLAGS += -O3` 分支（**当前配置未启用，实际用 `-O2`**）。
- `Makefile`：`NAME = Zakofox`；`init/Makefile` 在 `UTS_VERSION` 里插一个 `ZEN` 标记，
  `uname -v` 可区分。
- `kernel/sched/debug.c`：`SCHED_ALT` 下屏蔽 `cgroup_mode` 相关代码，否则与 alt 调度器重复定义。

### 0110 · 调度参数（3 个文件）

仅在 `CONFIG_ZEN_INTERACTIVE` 下生效：

| 参数 | 上游 | zakofox | 影响 |
| --- | --- | --- | --- |
| `sysctl_sched_base_slice` | 0.70 ms | 0.40 ms | EEVDF 基础时间片缩短，切换更细粒度 |
| `sysctl_sched_migration_cost` | 0.50 ms | 0.30 ms | 负载均衡更愿意搬任务 |
| `sysctl_sched_cfs_bandwidth_slice` | 5 ms | 3 ms | cgroup 带宽片更细 |

另新增 `kernel/sched/alt_topology_test.c`（kunit 测试，验证 P/E 核与 SMT 的选核逻辑）。

### 0120 · 内存与 zswap（6 个文件）

- `mm/zswap.c`：把每次压缩/解压都要走的 `acomp_req` 分配改成每 CPU 复用 + 异步回调，
  写回路径不再在原子上下文里同步等待压缩完成。
- `include/linux/mm.h`：`DEFAULT_MAX_MAP_COUNT` 从 `USHRT_MAX - MAPCOUNT_ELF_CORE_MARGIN`（≈65530）
  提到 `INT_MAX - MAPCOUNT_ELF_CORE_MARGIN`。Wine/Proton、JVM、大型浏览器这类大量 `mmap`
  的程序不再需要手动 `sysctl -w vm.max_map_count=...`。
- `include/linux/sched/mm.h`：`mmdrop` / `mmdrop_sched` / `mmdrop_lazy_tlb_sched` /
  `membarrier_mm_sync_core_before_usermode` 改 `__always_inline`（都在上下文切换热路径上）。
- `Documentation/mm/multigen_lru.rst` 两处文档同步。

### 0130 · 块层默认调度器（1 个文件）

`block/elevator.c` 的 `elevator_set_default()`：`ZEN_INTERACTIVE` 下

- 单队列（`nr_hw_queues == 1` 或共享 tag 集）：默认 **BFQ**（`CONFIG_IOSCHED_BFQ` 存在时），
  桌面交互与顺序读写下延迟更平滑；
- 多队列（NVMe 等）：默认 **Kyber**（`CONFIG_MQ_IOSCHED_KYBER` 存在时），
  在不牺牲吞吐的前提下给读请求优先权。

都不满足时保持上游的 `mq-deadline` 回落逻辑。

### 0140 · 网络（19 个文件）

- 新增 `net/ipv4/tcp_bbr3.c` 与 `CONFIG_TCP_CONG_BBR3`（`tcp_bbr3` 可 `sysctl` 切换，
  默认拥塞控制仍是 `cubic`，见配置表）。
- `TCP_ECN_LOW` 标记（`include/uapi/linux/tcp.h`、`include/net/tcp.h`、`net/ipv4/tcp_input.c`）：
  低延迟场景下 ECN 的标记策略更积极。
- `net/ipv4/{tcp.c,tcp_cong.c,tcp_bbr.c,tcp_input.c,tcp_output.c,tcp_metrics.c,tcp_timer.c}`、
  `include/net/{tcp.h,tcp_cong.h,inet_connection_sock.h}`、
  `include/uapi/linux/{tcp.h,inet_diag.h,rtnetlink.h}` 同步；
- `tools/testing/selftests/net/tcp_ca_kfunc.c` 跟着改。

### 0150 · CPU 调频（3 个文件）

`drivers/cpufreq/cpufreq_ondemand.c`：`DEF_FREQUENCY_UP_THRESHOLD` 80 → 55，
`MICRO_FREQUENCY_UP_THRESHOLD` 95 → 60，`DEF_SAMPLING_DOWN_FACTOR` 1 → 5
（升频更早、降频更慢，桌面短时负载不会来回抖动）。
`intel_pstate` 增加 `enable` 覆盖值，可以覆盖之前 `disable` 的内核命令行。
同时去掉 `CPU_FREQ_GOV_SCHEDUTIL` 的 `select`，避免和 PDS 的负载估算重复。

### 0160 · 显卡（4 个文件）

- amdgpu：新增 `ignore_min_pcap` 模块参数（部分显卡的最低功耗上限设得过高，
  导致频率被人为压低），并在 `amdgpu_pm.c` 的 sysfs 里对应返回 0。
- i915：`intel_edp_wake_sink()`，eDP 面板睡眠唤醒时补一次 `DP_SET_POWER` 写，修部分笔记本
  唤醒后黑屏。

### 0170 · PCI（1 个文件）

`drivers/pci/quirks.c`：`pcie_acs_override=` 参数（`downstream` / `multifunction` / `id:vvvv:dddd`），
把没有真实 ACS 的设备拆成独立 IOMMU 组，方便 VFIO 直通。**会 taint 内核**，且不是安全边界。

### 0180 · 中断与时间（6 个文件）

- `kernel/irq/Kconfig` + `kernel/irq/manage.c`：新增 `CONFIG_FORCE_IRQ_THREADING`（默认关）
  与 `nothreadirqs` 命令行反转开关。
- `kernel/time/tick-sched.h`、`include/linux/vtime.h`、`kernel/sched/cputime.c`：
  `tick_nohz_full_enabled()` / `tick_nohz_task_switch()` / `vtime_accounting_enabled*()` /
  `vtime_task_switch()` 改 `__always_inline`，减少每 tick 与上下文切换的函数调用开销。

### 0190 · 虚拟光驱（5 个文件）

`drivers/scsi/vhba/`：vhba 内核模块（`CONFIG_VHBA=m`），配合 CDEmu 之类把镜像挂成光驱。
`drivers/scsi/{Kconfig,Makefile}` 注册，`VHBA-MODULE` 由包 provides。

### 0200 · 架构与杂项（13 个文件）

- `arch/x86/Kconfig.cpu` + `arch/x86/Makefile`：新增 `X86_64_VERSION`（1..3，默认 1 = x86-64 baseline），
  在 `!X86_NATIVE_CPU` 时按 psABI 微架构等级统一出编译参数；本配置取 1，保证在任何 x86-64 机器上可启动。
- `arch/x86/kernel/cpu/bus_lock.c`：`ZEN_INTERACTIVE` 下 `sysctl_sld_mitigate` 默认 0
  （split lock 检测的缓解默认关闭，性能优先；可用 sysctl 打开）。
- `drivers/input/evdev.c`：客户端释放改成 RCU 回调延迟回收，避免高频输入下 `synchronize_rcu()` 卡顿。
- `fs/btrfs/compression.c`、`fs/erofs/zdata.c`：`PageWorkingset()` → `folio_test_workingset(page_folio())`
  的 folio 迁移适配。
- `arch/{x86,arm,riscv,s390,sparc}/include/asm/mmu_context.h`、
  `arch/x86/include/asm/sync_core.h`、`include/linux/perf_event.h`：热路径函数 `__always_inline`。
- `Documentation/admin-guide/kernel-parameters.txt`：上述新参数（`nothreadirqs`、
  `pcie_acs_override=`、`sched_pds_sleep_credit=`、`intel_pstate=enable`）的说明。

## 内核配置要点

配置唯一事实来源是 `zakofox-x86_64.config`：`prepare()` 里复制成 `.config` 后跑
`make olddefconfig`，若有漂移会打印 diff 作为警告（不中断构建），需人工确认漂移是否可接受。

| 配置项 | 值 | 原因 |
| --- | --- | --- |
| `CONFIG_ZEN_INTERACTIVE` | `y` | 全部调优的总开关 |
| `CONFIG_SCHED_ALT` + `CONFIG_SCHED_PDS` | `y` / `y` | 桌面交互优先的调度器 |
| `CONFIG_PREEMPT` | `y`（`PREEMPT_DYNAMIC` 关） | 静态全抢占，避免 dynamic 模式下的静态键分支 |
| `CONFIG_HZ` | `1000` | 桌面响应 |
| `CONFIG_NO_HZ_FULL` | `y` | 空闲 CPU 不被打扰 |
| `CONFIG_RCU_NOCB_CPU_DEFAULT_ALL` | `y` | 回调卸载到 rcuo 线程，减少软中断抖动 |
| `CONFIG_NR_CPUS` | `128`（非 `MAXSMP`） | 够用且显著缩短编译、减小镜像 |
| `CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE` | `y`（`-O2`） | 当前取上游默认；`-O3` 选项已备好未启用 |
| `CONFIG_LTO_NONE` | `y` | 避免 LTO 与 cjktty 大字体文件、PDS 的编译期问题 |
| `CONFIG_LOCALVERSION` | `"-zakofox"` | 版本串；`LOCALVERSION_AUTO` 关 |
| `CONFIG_DEBUG_INFO_NONE` | `y` | 不要 DWARF/BTF，包体积从数百 MB 降到 ~160 MB |
| `CONFIG_FONT_CJK_16x16` / `FONT_CJK_32x32` | `y` / `y` | 控制台中文 |
| `CONFIG_TCP_CONG_BBR3` | `y` | 可选拥塞控制；`CONFIG_DEFAULT_TCP_CONG="cubic"` 保持上游默认 |
| `CONFIG_ZSWAP` + `ZSWAP_DEFAULT_ON` | `y` / `y`，压缩器 `zstd` | 内存紧张时的兜底，无需手动开 |
| `CONFIG_ZRAM` | `y`，默认 `zstd` 多后端 | 沿用 7.3 上游实现（见下） |
| `CONFIG_MODULE_COMPRESS_ZSTD` + `_ALL` | `y` | 模块全量 zstd 压缩 |
| `CONFIG_MODULE_SIG_ALL` + `SHA512` | `y` | 模块签名（`MODULE_SIG_FORCE` 关，仍可加载外部模块） |
| `CONFIG_X86_64_VERSION` | `1` | x86-64 baseline，兼容任何 x86-64 机器 |
| `CONFIG_VHBA` | `m` | 虚拟光驱 |

CPU 侧未启用 `CONFIG_X86_NATIVE_CPU`：内核需要能在别的机器上启动，
`make localmodconfig` 风格的「只对本机 CPU 优化」不适合发行包。想要本机极限性能可在
`X86_64_VERSION` 上调到 2/3 后自行重编。

## 构建

### 本地

```bash
makepkg -s          # 或 makepkg -sioc 保留构建目录
```

依赖：`base-devel bc cpio gettext libelf pahole perl python tar xz zstd`。
4 核机器上 `--noprepare` 全量约 3～5 小时（`make -j$(nproc)`），建议至少 8 核 / 16 GB。

### GitHub Actions

`.github/workflows/build.yml`：在 `archlinux:base-devel` 容器里以非 root 用户跑
`makepkg --noconfirm --nocheck --cleanbuild --syncdeps`，`ccache` 与内核源码 tarball 走 Actions cache
（key 带 `hashFiles('PKGBUILD','*.config','*.patch')`），job 超时 350 分钟。
产物 `linux-zakofox-7.3.3`（两个 `.pkg.tar.zst`，约 160 MB）与 `build-logs` 上载为 artifact；
包本身不上传 release，需要的话自行下载 artifact 后 `pacman -U`。

触发条件：推送 `main` 且改动 `PKGBUILD` / `*.patch` / `*.config` / `scripts/**` / workflow 自身，
或手动 `workflow_dispatch`（可指定并行任务数）。只改 `README.md`、`LICENSE` 不会触发重建。

> **注意**：workflow 里 `concurrency: cancel-in-progress: true`。一次全量构建约 2 小时 15 分，
> 这期间不要往 `main` 推任何会匹配上述路径的提交，否则正在跑的构建会被取消——
> 只改 `README.md`、`LICENSE` 不受影响。

## 目录结构

```
PKGBUILD                 打包脚本（pkgbase=linux-zakofox，两个 pkgname）
zakofox-x86_64.config    内核配置，唯一事实来源
0001-zakofox-prjc-pds-7.3.patch
0002-zakofox-cjktty-7.2.patch
0100-zen-core-config.patch
0110-zen-sched.patch
0120-zen-mm-zswap.patch
0130-zen-block-elevator.patch
0140-zen-tcp.patch
0150-zen-cpufreq.patch
0160-zen-gpu.patch
0170-zen-pci-acs.patch
0180-zen-irq-vtime.patch
0190-zen-vhba.patch
0200-zen-arch-misc.patch
SHA256SUMS               补丁与配置的校验值
scripts/gen-cjk-font.py  用 TTF 生成 CJK 点阵字体的工具（可选）
.github/workflows/build.yml
```

补丁与配置必须平铺在仓库根目录：makepkg 的 `source=()` 对本地文件只按 basename 查找，
带子目录的路径（`patches/x.patch`）会直接报「没有在创建目录中找到，也不是一个 URL」。

## 自定义控制台字体

`scripts/gen-cjk-font.py` 可以把任意含中文的 TTF 渲染成内核要的点阵表，用来替换补丁里的
`lib/fonts/font_cjk_16x16.h` / `font_cjk_32x32.h`：

```bash
# 16x16，U+4E00..9FFF 中日韩统一表意文字
python3 scripts/gen-cjk-font.py --font /usr/share/fonts/TTF/YourFont.ttf --size 16 \
    --start 0x4e00 --end 0x9fff --output /tmp/font_cjk_16x16.h
```

输出格式与 cjktty 一致：每个码点「先左半 16/64 字节、再右半」两个槽位，逐行写
`/* 序号 0xXXXX */` 注释，方便 diff。`--size 32` 生成 128 字节/字形的 32×32 表。
不指定 `--start/--end` 时遍历整个 BMP（会跳过代理区与无法渲染的码点）。

## 升级上游版本

1. 改 `PKGBUILD` 的 `pkgver` 与 tarball `sha256sums`，同步 workflow 的 `KERNEL_VERSION`；
2. 验证 `0001`（prjc）能在新版本上干净应用；不行就换对应版本的 tkg `0009-prjc.patch`；
3. 验证 `0002`（cjktty）：7.3 起 fbcon 的旋转缓冲被内联进 `struct fbcon_par`，
   从 7.2 版补丁直接搬能过是因为相关条件判断恰好兼容，升到 7.4 需重新对齐；
4. `01xx` / `02xx` 按需 rebase，最容易受上游重构影响的是 `0110`（sched）、
   `0120`（mm/zswap）、`0200`（arch/x86）；
5. `makepkg --nobuild` 看 `.config` 漂移，逐个大文件 `make <obj>.o` 先验证再全量编。

## 已知问题

- **32×32 CJK 字体是空表**：`CONFIG_FONT_CJK_32x32=y` 但 `lib/fonts/font_cjk_32x32.h` 在补丁里
  是 0 字节，`.charcount` 却声明为 `65536 * 2`。控制台用 16 行字体（默认）时不会走这条路径，
  一旦把 VT 字体设成 32 行（`setfont` 一个大字体），中文查表会读到越界数据。
  修法二选一：用 `scripts/gen-cjk-font.py --size 32` 生成数据补进补丁，
  或直接 `CONFIG_FONT_CJK_32x32` 关闭。
- **非特权 user namespace 默认关闭**：`0180` 带入了 `kernel.unprivileged_userns_clone` sysctl，
  在 7.3 上游没有 `CONFIG_USER_NS_UNPRIVILEGED` 这个选项，因此默认值落到 0，
  会让 bwrap/Flatpak/Firefox 这类非特权沙箱失败。临时可 `sysctl -w kernel.unprivileged_userns_clone=1`，
  长期应把该 hunk 从 `0180` 中移除。
- **`-O3` 未启用**：`0100` 提供了 `CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE_O3`，但配置里仍是 `-O2`。
- **zram 未做 zen 式重构**：7.3 上游已有 `CONFIG_ZRAM_BACKEND_*` 多后端与 `zcomp` 新接口，
  旧式 zram 补丁在其上会编译失败，因此 zram 完全走上游实现，只保留块层默认调度器的调优。

## 许可

内核本体 `GPL-2.0-only`（见 `LICENSE`）。各补丁遵循其上游原始许可：
prjc 调度器 GPL-2.0，cjktty GPL-2.0，其余调优补丁 GPL-2.0。

---

## 站在巨人的肩膀上

这个项目没有一行内核代码是凭空写的：上游内核、调度器、中文控制台、点阵字体、打包脚本，
全部来自下面这些项目与人。感谢他们。

**上游内核**

- Linux 内核（Linus Torvalds）—— https://github.com/torvalds/linux
- kernel.org 发布与镜像 —— https://www.kernel.org/

**调度器**

- Project C / prjc（PDS、BMQ，Alfred Chen）—— https://gitlab.com/alfredchen/linux-prjc
- linux-tkg（提供按内核版本适配好的 prjc 补丁）—— https://github.com/Frogging-Family/linux-tkg

**桌面内核调优**

- zen-kernel（zen-sauce 调优补丁集的来源）—— https://github.com/zen-kernel/zen-kernel
- Liquorix（Liquorix kernel 打包与配置参考）—— https://github.com/damentz/liquorix-package

**中文控制台**

- cjktty 原始补丁（zhmars）—— https://github.com/zhmars/cjktty-patches
- cjktty 维护分支（Capricornus007，7.x 系列补丁）—— https://github.com/Capricornus007/cjktty-patches

**打包与参考**

- Arch Linux 官方 linux 打包脚本 —— https://gitlab.archlinux.org/archlinux/packaging/packages/linux
- Arch Linux —— https://archlinux.org/

**字体**

- Maple Mono（`scripts/gen-cjk-font.py` 的推荐字体来源）—— https://github.com/subframe7536/maple-font
