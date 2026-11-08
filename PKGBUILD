# Maintainer: Linming-XHL <linmingxhl@qq.com>
#
# linux-zakofox — 基于上游 stable 内核，并入 Liquorix/zen 调优与 PDS 调度器，
#                 以及 cjktty 中文控制台补丁。
#
# 补丁顺序（按文件名排序依次应用）：
#   0001  tkg 0009-prjc.patch      PDS/BMQ 调度器（Project C / Alfred Chen）
#   0002  cjktty                   CJK 控制台字体与 UTF-8 渲染
#   01xx  zen 调优补丁（按子系统拆分）
pkgbase=linux-zakofox
pkgname=("$pkgbase" "$pkgbase-headers")
pkgver=7.3.3
pkgrel=1
_srcname=linux-${pkgver}
arch=(x86_64)
url="https://github.com/Linming-XHL/linux-zakofox"
license=(GPL-2.0-only)
makedepends=(
  bc
  cpio
  gettext
  libelf
  pahole
  perl
  python
  tar
  xz
  zstd
)
options=(!debug !strip)
source=(
  "$_srcname.tar.xz::https://mirrors.edge.kernel.org/pub/linux/kernel/v${pkgver%%.*}.x/$_srcname.tar.xz"
  zakofox-x86_64.config
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
)
sha256sums=(
  '79c66dde66cd96877fcde8f7d36aec946b1f423d2b97b5a7b1751b75c764f3d1'
  '3460e9baab45dce6caaa4a367ac1ce3d0ed30299ad4fbf536f451e07c5c9e508'
  'ed3de48f23ef25c64a8b0124451a7338c6ad51816baf7bcb8c4ee7c5f277867b'
  '9c40a638126adc2b5973f00aa09b30ce1b105c716f230c2fab9d538b254da74b'
  '195f1467522ddbf2698b4d37bb5f1944b1fa85859ce61babe14b62c41a47fa18'
  '436fcb0752d8771d7267aa85a78f6d3da79cc88678f9addb9f9d7f7ca7a8edbd'
  '3bd0c07e164430b7c8cbd1428249efbda8efab6294eed316708079967fbd9ef7'
  '6d509c3535684ff65151c2e0169ebb4237eac35f07dd0fc15b98cbc17aa01977'
  '40138d283071bef4f55c0875b7e7fdbc54b7eebd3a70ee3d50d7e4b915366148'
  '5d275f87d83e5b096260c4f7cf990276fc344074a90defbf7cdda91cb6ee8eda'
  '72abfd2c88c1997b8d997363cc8497f72c146c683b89c2e118fc362f64704227'
  '6747d8767f4389732ee4d254f0bb1e5c0f48823b481c1928c7562154d9782c4a'
  '6b624e18aae4b10c8f42822763de0f3c00349ae36b8f12158c6afd209958bacf'
  '7ff28ead30720ca0a4f250566be39846653bf41edf7389397f891ff1903a2aff'
  '509b2fc01fbf493d0da237a528b10af92b523753c0c701dcd74aa6c95d74a886'
)

_patches=(
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
)

export KBUILD_BUILD_USER=$pkgbase
export KBUILD_BUILD_HOST=zakofox

prepare() {
  cd "$_srcname"

  local p
  for p in "${_patches[@]}"; do
    msg2 "应用 $p"
    patch -Np1 --no-backup-if-mismatch -i "$srcdir/$p"
  done

  cp "$srcdir/zakofox-x86_64.config" .config
  make olddefconfig

  # 目标 config 无法完全归约时，把漂移打印出来，避免静默改变内核特性
  if ! diff -u "$srcdir/zakofox-x86_64.config" .config >/dev/null; then
    warning "内核配置相对 zakofox-x86_64.config 发生漂移："
    diff -u "$srcdir/zakofox-x86_64.config" .config \
      | grep -E '^[+-][^+-]' | grep -vE '^[+-]$' || true
  fi
}

build() {
  cd "$_srcname"
  make -s kernelrelease > version
  msg2 "内核版本：$(<version)"

  make -j"$(nproc)" all
}

package_linux-zakofox() {
  pkgdesc="Zakofox 内核 ${pkgver}：上游 stable + Liquorix/zen 调优 + PDS 调度器 + cjktty"
  depends=(coreutils kmod)
  optdepends=(
    'linux-firmware: firmware images for the kernel modules'
    'wireguard-tools: for WireGuard support'
    'nvidia: proprietary NVIDIA driver support'
  )
  provides=(KSMBD-MODULE NTSYNC-MODULE VIRTUALBOX-GUEST-MODULES WIREGUARD-MODULE VHBA-MODULE)
  conflicts=(linux)

  cd "$_srcname"

  local modulesdir="$pkgdir/usr/lib/modules/$(<version)"

  install -dm755 "$modulesdir"
  install -Dm644 "$(make -s image_name)" "$modulesdir/vmlinuz"
  echo "$pkgbase" > "$modulesdir/pkgbase"
  install -Dm644 System.map "$modulesdir/System.map"
  install -Dm644 .config "$pkgdir/boot/config-$pkgbase"

  ZSTD_CLEVEL=19 make INSTALL_MOD_PATH="$pkgdir/usr" INSTALL_MOD_STRIP=1 \
    DEPMOD=/doesnt/exist modules_install

  # 模块安装会创建指向构建目录的 symlink
  rm -f "$modulesdir/build" "$modulesdir/source"
}

package_linux-zakofox-headers() {
  pkgdesc="Headers and scripts for building modules for the $pkgbase kernel"
  depends=("$pkgbase=$pkgver-$pkgrel" coreutils)
  provides=("$pkgbase-headers=$pkgver-$pkgrel" linux-headers)
  conflicts=(linux-headers)

  cd "$_srcname"

  local builddir="$pkgdir/usr/lib/modules/$(<version)/build"

  echo "Installing build files..."
  install -m644 -Dt "$builddir" .config Makefile Module.symvers System.map version vmlinux
  local f
  for f in localversion.*; do
    [[ -e $f ]] && install -m644 -Dt "$builddir" "$f"
  done
  install -dm755 "$builddir/tools/bpf/bpftool"
  if [[ -f tools/bpf/bpftool/vmlinux.h ]]; then
    install -m644 tools/bpf/bpftool/vmlinux.h "$builddir/tools/bpf/bpftool/vmlinux.h"
  fi

  echo "Installing headers..."
  cp -a include "$builddir"
  cp -a arch/x86/include "$builddir/arch/x86/"
  cp -a scripts "$builddir"

  echo "Installing KConfig files..."
  find . -name 'Kconfig*' -exec install -Dm644 {} "$builddir/"{} \;

  echo "Removing unneeded architectures..."
  local arch
  for arch in "$builddir"/arch/*/; do
    [[ $arch = */x86/ ]] && continue
    echo "Removing $(basename "$arch")"
    rm -rf "$arch"
  done

  echo "Removing documentation..."
  rm -rf "$builddir/Documentation"

  echo "Removing broken symlinks..."
  find -L "$builddir" -type l -printf 'Removing %p\n' -delete

  echo "Removing loose objects..."
  find "$builddir" -type f -name '*.o' -printf 'Removing %p\n' -delete

  echo "Stripping build tools..."
  local file
  while read -rd '' file; do
    case "$(file -S -b -L --mime-type "$file")" in
      application/x-sharedlib\;*)    strip -v "$file" ;;
      application/x-archive\;*)      strip -v "$file" ;;
      application/x-executable\;*)   strip -v "$file" ;;
      application/x-pie-executable\;*) strip -v "$file" ;;
    esac
  done < <(find "$builddir" -type f -perm -u+x -print0)

  echo "Stripping vmlinux..."
  strip -v "$builddir/vmlinux"

  echo "Adding symlink..."
  mkdir -p "$pkgdir/usr/src"
  ln -sr "$builddir" "$pkgdir/usr/src/$pkgbase"
}
