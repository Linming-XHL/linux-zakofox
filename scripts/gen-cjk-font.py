#!/usr/bin/env python3
"""用任意 TrueType/OpenType 字体生成 cjktty 兼容的 CJK 点阵字体表。

cjktty 的内核侧约定（drivers/video/fbdev/core/bitblit.c: font_bits）：

    FONTDATAMAX = 65536 * 32      # 16x16，每个码点 32 字节
    FONTDATAMAX = 65536 * 128     # 32x32，每个码点 128 字节

    码点 cp 的字形位于  data[cp * stride : cp * stride + stride]

其中每个码点占两个「半宽字形槽位」：

    ch == 0xff （全角）→ data + cp*stride + 0        读 cellsize 字节
    ch == 0xfe （半角）→ data + cp*stride + cellsize  读 cellsize 字节

对 16x16：cellsize = 16，每个半宽字形是 8 像素宽 × 16 行（每行 1 字节）。
对 32x32：cellsize = 64，每个半宽字形是 16 像素宽 × 32 行（每行 2 字节）。

因此一个全角字形被拆成「左半 + 右半」两块连续存放，而不是按行交错。
本脚本按这个布局输出，并保留参考字体里的 `/* N 0xXXXX "字" */` 注释方便比对。

用法：
    python3 gen-cjk-font.py --font MapleMono_NF_CN_Regular.ttf --size 16 \\
        --output font_cjk_16x16.h

    可选 --only-cjk 跳过 ASCII 区间（内核里 ASCII 走常规 8x16 字体，
    这里保留是为了让 .h 的字节数严格等于 FONTDATAMAX）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("需要 Pillow：pip install pillow")

# 每个尺寸对应的 (半宽字形宽, 高, 每行字节数)
SIZES = {
    16: (8, 16, 1),
    32: (16, 32, 2),
}

def glyph_bitmap(font: ImageFont.FreeTypeFont, ch: str, w: int, h: int,
                 threshold: int = 110) -> list[list[int]]:
    """把单个字符渲染成 w×h 的二值点阵（行优先，1 = 亮点）。"""
    # 留一点内边距，避免描边贴边被裁掉
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    # 用 bbox 居中，让字形落在格子中央
    try:
        left, top, right, bottom = draw.textbbox((0, 0), ch, font=font)
    except Exception:
        left = top = right = bottom = 0
    gw, gh = right - left, bottom - top
    draw.text(((w - gw) // 2 - left, (h - gh) // 2 - top), ch, font=font, fill=255)

    px = img.load()
    return [[1 if px[x, y] > threshold else 0 for x in range(w)] for y in range(h)]


def is_renderable(cp: int) -> bool:
    """代理区（0xD800-0xDFFF）无法编码成 UTF-8，PIL 会直接报错，直接留空。"""
    return not (0xD800 <= cp <= 0xDFFF)


def pack_half(bits: list[list[int]], half_w: int, height: int, bytes_per_row: int) -> list[int]:
    """把 half_w×height 的点阵打包成 height*bytes_per_row 字节（MSB 在左）。"""
    out: list[int] = []
    for y in range(height):
        row = bits[y]
        acc = 0
        nbits = 0
        val = 0
        for x in range(half_w):
            val = (val << 1) | row[x]
            nbits += 1
            if nbits == 8:
                out.append(val)
                val = 0
                nbits = 0
        if nbits:
            out.append(val << (8 - nbits))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--font", required=True, help="TTF/OTF 字体路径")
    ap.add_argument("--size", type=int, default=16, choices=sorted(SIZES), help="点阵高度（16 或 32）")
    ap.add_argument("--output", required=True, help="输出的 .h 文件")
    ap.add_argument("--threshold", type=int, default=110, help="灰度阈值（默认 110）")
    ap.add_argument("--start", type=lambda s: int(s, 0), default=0, help="起始码点")
    ap.add_argument("--end", type=lambda s: int(s, 0), default=0xFFFF, help="结束码点（含）")
    args = ap.parse_args()

    half_w, height, bytes_per_row = SIZES[args.size]
    full_w = half_w * 2
    cellsize = height * bytes_per_row       # 单个半宽字形的字节数
    stride = cellsize * 2                   # 每个码点的字节数

    font = ImageFont.truetype(args.font, args.size)

    out = Path(args.output)
    total = 0
    with out.open("w", encoding="utf-8") as fh:
        fh.write("/* SPDX-License-Identifier: GPL-2.0 */\n")
        fh.write(f"/* generated from {Path(args.font).name} at {args.size}px */\n")
        for cp in range(args.start, args.end + 1):
            try:
                ch = chr(cp)
            except ValueError:
                ch = ""
            if not ch or not is_renderable(cp):
                bits = [[0] * full_w for _ in range(height)]
            else:
                try:
                    bits = glyph_bitmap(font, ch, full_w, height, args.threshold)
                except Exception:
                    bits = [[0] * full_w for _ in range(height)]

            left = [row[:half_w] for row in bits]
            right = [row[half_w:] for row in bits]

            data = pack_half(left, half_w, height, bytes_per_row) + \
                   pack_half(right, half_w, height, bytes_per_row)
            assert len(data) == stride, f"cp {cp:#x}: {len(data)} != {stride}"

            label = ch if ch and ch.isprintable() and cp > 0x20 else ""
            fh.write(f'/* {cp} 0x{cp:x}{f" {label!r}" if label else ""} */\n')
            fh.write(",".join(f"0x{b:02x}" for b in data))
            fh.write(",\n")
            total += len(data)

    expected = (args.end - args.start + 1) * stride
    status = "OK" if total == expected else "MISMATCH"
    print(f"{out}: {total} 字节（期望 {expected}） {status}")
    return 0 if total == expected else 1


if __name__ == "__main__":
    sys.exit(main())
