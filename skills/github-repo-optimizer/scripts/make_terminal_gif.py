#!/usr/bin/env python3
"""终端演示 GIF 渲染器 — 纯 PIL 实现，无需录屏软件。

用法:
  # 方式1: JSON 行数组 [文本, 语义色] (cmd/info/ok/warn/bad/dim)
  python3 make_terminal_gif.py \
    --lines-json '[["$ my-cmd --flag","cmd"],["[*] working...","info"],
                   ["[+] done","ok"],["[!] warning","warn"],
                   ["score: 33/100 -> FAKE","bad"]]' \
    --out demo.gif --title "myproject — zsh"

  # 方式2: 从文件读 (--lines-file，每行 "文本|语义色")

依赖: pillow (pip install pillow)
注意: 无 CJK 字体环境(容器常见)请用英文内容，否则渲染豆腐块。
      用 fc-list | grep -i cjk 检查字体可用性。
"""
import argparse
import json
import sys

from PIL import Image, ImageDraw, ImageFont

# GitHub dark 主题配色
COLORS = {
    "bg": (13, 17, 23),
    "bar": (22, 27, 34),
    "fg": (230, 237, 243),
    "dim": (139, 148, 158),
    "cmd": (121, 192, 255),
    "ok": (63, 185, 80),
    "warn": (210, 153, 34),
    "bad": (248, 81, 73),
}
SEMANTIC = {"cmd": "cmd", "ok": "ok", "warn": "warn", "bad": "bad",
            "info": "fg", "dim": "dim", "fg": "fg"}


def load_lines(args):
    if args.lines_json:
        raw = json.loads(args.lines_json)
        return [(t, SEMANTIC.get(s, "fg")) for t, s in raw]
    if args.lines_file:
        out = []
        with open(args.lines_file, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    out.append(("", "fg"))
                    continue
                if "|" in line:
                    t, s = line.rsplit("|", 1)
                    out.append((t, SEMANTIC.get(s.strip(), "fg")))
                else:
                    out.append((line, "fg"))
        return out
    # 无输入时渲染内置示例
    return [
        ("$ echo 'pass --lines-json or --lines-file'", "cmd"),
        ("[*] rendering demo GIF ...", "info"),
        ("[+] done", "ok"),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lines-json", help='JSON 数组，如 [["$ cmd","cmd"],["[+] ok","ok"]]')
    ap.add_argument("--lines-file", help="每行 '文本|语义色' 的文件")
    ap.add_argument("--out", default="demo.gif")
    ap.add_argument("--title", default="terminal — zsh")
    ap.add_argument("--width", type=int, default=820)
    ap.add_argument("--height", type=int, default=500)
    ap.add_argument("--font-size", type=int, default=15)
    ap.add_argument("--font", default="/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
    ap.add_argument("--hold-frames", type=int, default=14)
    args = ap.parse_args()

    try:
        font = ImageFont.truetype(args.font, args.font_size)
    except OSError:
        sys.exit(f"字体不存在: {args.font}\n(容器内常见路径: /usr/share/fonts/truetype/dejavu/)")

    lines = load_lines(args)
    W, H, BAR, PAD = args.width, args.height, 34, 18
    LINE_H = args.font_size + 7
    max_lines = (H - BAR - PAD * 2) // LINE_H
    if len(lines) > max_lines:
        sys.exit(f"内容 {len(lines)} 行超出画布容量 {max_lines} 行，请精简或增大 --height")

    def render(shown, cursor_on=True):
        img = Image.new("RGB", (W, H), COLORS["bg"])
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, BAR], fill=COLORS["bar"])
        for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            d.ellipse([14 + i * 22, 11, 26 + i * 22, 23], fill=c)
        tw = d.textlength(args.title, font=font)
        d.text(((W - tw) / 2, 9), args.title, font=font, fill=COLORS["dim"])
        y = BAR + PAD
        for text, sem in shown:
            d.text((PAD, y), text, font=font, fill=COLORS[sem])
            y += LINE_H
        if shown:
            cx = PAD + d.textlength(shown[-1][0], font=font)
            if cursor_on:
                d.rectangle([cx, y - LINE_H + 3, cx + 9, y - 3], fill=COLORS["cmd"])
            else:
                d.rectangle([cx, y - LINE_H + 3, cx + 9, y - 3], outline=COLORS["cmd"])
        return img

    frames = []
    # 阶段1: 首个以 $ 开头的命令行做打字动画（2字符/帧）
    cmd_count = 0
    for t, s in lines:
        if t.startswith("$"):
            cmd_count += 1
    head = lines[:cmd_count] if cmd_count else lines[:1]
    rest = lines[len(head):]
    total = sum(len(t) for t, _ in head)
    for step in range(0, total + 1, 2):
        shown, budget = [], step
        for text, sem in head:
            if budget <= 0:
                break
            shown.append((text[:budget], sem))
            budget -= len(text)
        frames.append((render(shown), 70))
    # 阶段2: 输出逐行出现
    shown = list(head)
    for line in rest:
        frames.append((render(shown + [line]), 130))
        frames.append((render(shown + [line]), 130))
        shown.append(line)
    # 阶段3: 停留 + 光标闪烁
    for i in range(args.hold_frames):
        frames.append((render(shown, cursor_on=(i % 2 == 0)), 160))

    imgs = [f for f, _ in frames]
    durations = [d for _, d in frames]
    imgs[0].save(args.out, save_all=True, append_images=imgs[1:],
                 duration=durations, loop=0, optimize=True)
    import os
    size_kb = os.path.getsize(args.out) / 1024
    print(f"OK: {args.out} | {len(imgs)} 帧 | {size_kb:.0f}KB"
          + (" ⚠️ 超1MB，建议精简行数" if size_kb > 1024 else ""))


if __name__ == "__main__":
    main()
