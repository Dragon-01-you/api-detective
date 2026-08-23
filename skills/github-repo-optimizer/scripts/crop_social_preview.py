#!/usr/bin/env python3
"""社交预览图裁剪器 — 任意尺寸图 → GitHub 标准 1280x640 (2:1)。

GitHub 社交预览规格: 1280x640, PNG/JPG/GIF, <1MB
用法:
  python3 crop_social_preview.py input.jpg [-o social_preview.jpg] [--quality 88]
依赖: pillow
"""
import argparse
import sys
from PIL import Image


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="源图路径（建议先生成 16:9 横图）")
    ap.add_argument("-o", "--out", default="social_preview.jpg")
    ap.add_argument("--quality", type=int, default=88)
    args = ap.parse_args()

    im = Image.open(args.input).convert("RGB")
    w, h = im.size
    target_h = w // 2  # 2:1
    if h < target_h:
        sys.exit(f"源图 {w}x{h} 过窄，无法裁出 2:1（宽需≤2倍高）。请用横版图。")
    top = (h - target_h) // 2  # 中心裁剪
    out = im.crop((0, top, w, top + target_h)).resize((1280, 640), Image.LANCZOS)
    for q in (args.quality, 80, 70, 60):
        out.save(args.out, quality=q, optimize=True)
        import os
        if os.path.getsize(args.out) < 1024 * 1024:
            print(f"OK: {args.out} 1280x640 quality={q} "
                  f"{os.path.getsize(args.out)//1024}KB (<1MB)")
            return
    print(f"⚠️ quality=60 仍超1MB，请换更简单的图或手动压缩")


if __name__ == "__main__":
    main()
