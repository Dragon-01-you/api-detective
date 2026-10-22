#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 README 用的两张示意图（纯代码绘制，极简黑白，与项目视觉规范一致）。

只用四个颜色：纸 #F4F4F2 / 墨 #111111 / 唯一强调色 藏青 #132A5E / 三级灰。
输出 assets/how_it_works.svg|png 与 assets/case_forensics.svg|png。

    python3 tools/make_readme_art.py
"""
import os
import subprocess
import sys

PAPER = "#F4F4F2"
INK = "#111111"
NAVY = "#132A5E"
G2 = "#EAE8E3"
G3 = "#D4D2CC"
G4 = "#8C8A84"
G5 = "#5A5A56"

SANS = ("Inter, 'Noto Sans SC', 'Noto Sans CJK SC', -apple-system, "
        "'Helvetica Neue', Arial, sans-serif")
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")
CHROME = os.environ.get(
    "OM_CHROME",
    "/root/.cache/puppeteer/chrome/linux-155.0.8059.39/chrome-linux64/chrome")


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def t(x, y, s, size=15, fill=INK, weight=400, anchor="start", ls=0,
      family=SANS, opacity=1.0):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    l = f' letter-spacing="{ls}"' if ls else ""
    o = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}"{a}{l}{o}>{esc(s)}</text>')


def rule(x1, y, x2, color=G3, width=1):
    return (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" '
            f'stroke="{color}" stroke-width="{width}"/>')


def vrule(x, y1, y2, color=G3, width=1):
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{width}"/>')


def wrap(text, budget):
    out, cur = [], ""
    for ch in text:
        w = 1 if ord(ch) < 128 else 2
        cur_w = sum(1 if ord(c) < 128 else 2 for c in cur)
        if cur_w + w > budget:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def canvas(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="{PAPER}"/>' + body + "</svg>")


# ----------------------------------------------------------------------
def how_it_works():
    W, H, PAD = 1600, 700, 64
    R = W - PAD
    cols, gap = 4, 52
    cw = (R - PAD - gap * (cols - 1)) // cols
    xs = [PAD + i * (cw + gap) for i in range(cols)]

    b = []
    b.append(t(PAD, 88, "芯火 XH", 30, INK, 700, ls="0.01em"))
    b.append(t(PAD + 150, 86, "取证流水线 · FORENSICS PIPELINE", 14, G4, 400, ls="0.18em"))
    b.append(t(R, 86, "零遥测 · 全本地留档 · 运行时仅 3 个依赖", 14, G5, 400, anchor="end"))
    b.append(rule(PAD, 120, R))

    heads = [
        ("01", "输入", "INPUT"),
        ("02", "探针族", "PROBES"),
        ("03", "判决引擎 v2", "VERDICT"),
        ("04", "输出", "OUTPUT"),
    ]
    for (num, zh, en), x in zip(heads, xs):
        b.append(rule(x, 162, x + cw, INK, 1.5))
        b.append(t(x, 194, num, 12, G4, 500, ls="0.22em"))
        b.append(t(x, 230, zh, 23, INK, 700))
        b.append(t(x, 253, en, 11, G4, 500, ls="0.2em"))

    for x in xs[:-1]:
        gx = x + cw + gap // 2
        b.append(f'<line x1="{x + cw}" y1="162" x2="{gx - 9}" y2="162" stroke="{G3}"/>')
        b.append(f'<line x1="{gx + 5}" y1="162" x2="{x + cw + gap}" y2="162" stroke="{G3}"/>')
        b.append(f'<path d="M{gx - 6} 157 L{gx + 1} 162 L{gx - 6} 167" fill="none" '
                 f'stroke="{NAVY}" stroke-width="1.6"/>')

    x = xs[0]
    b.append(t(x, 292, "URL + API Key", 17, INK, 500, family=MONO))
    for i, line in enumerate([
        "阶段 0 · 零成本侦察",
        "模型清单 / 定价表 / 首页指纹",
        "金丝雀探针先探计费可用性",
        "被挡则自动降级，不烧冤枉钱",
    ]):
        b.append(t(x, 330 + i * 30, line, 15, G5))

    x = xs[1]
    probes = [
        ("身份测谎", "13 问"),
        ("提示词武库", "37 组"),
        ("厂商知识归属", "8 项"),
        ("LLMmap 预训练指纹", "8×52"),
        ("路由 · 分词器 · 行为指纹", "—"),
        ("加密签名 + 安全审计", "5 类"),
        ("学力测验 + 风格画像", "—"),
        ("MET 同一性检验", "—"),
    ]
    for i, (name, cnt) in enumerate(probes):
        y = 292 + i * 31
        b.append(t(x, y, name, 15.5, INK if cnt != "—" else G5))
        b.append(t(x + cw, y, cnt, 13, G4, 500, anchor="end", family=MONO))
        if i < len(probes) - 1:
            b.append(rule(x, y + 11, x + cw, G2))

    x = xs[2]
    b.append(t(x, 292, "类别归一化", 15, G5))
    b.append(t(x, 322, "温度 Softmax（T = 0.5）", 15, G5))
    b.append(t(x, 404, "0–100", 46, INK, 700, family=MONO))
    b.append(t(x, 432, "score · P(正品) · 覆盖率", 13, G4))
    b.append(rule(x, 456, x + cw))
    b.append(t(x, 486, "覆盖率 < 35% 触发", 14, G5))
    b.append(t(x, 508, "「证据不足」保护", 14, G5))

    x = xs[3]
    b.append(t(x, 292, "DOSSIER.md", 16, INK, 500, family=MONO))
    b.append(t(x, 322, "report_card.svg", 14, G5, family=MONO))
    for i, line in enumerate([
        "全量 JSON 证据链",
        "100+ 份证据文件逐条留档",
        "可直接用于平台投诉与维权",
    ]):
        b.append(t(x, 356 + i * 30, line, 15, G5))

    b.append(rule(PAD, 520, R, G2))
    b.append(t(PAD, 546, "判决档位 / TIERS", 11, G4, 500, ls="0.2em"))

    tiers = [
        (0, "确证贴牌 / 拼装", INK),
        (25, "高度可疑", G5),
        (45, "可疑", G4),
        (65, "大体可信", G3),
        (85, "正品直连 / 可信转售", G2),
        (100, None, None),
    ]
    bar_y, bar_h = 570, 7

    def px(v):
        return PAD + (R - PAD) * v / 100.0

    for i in range(len(tiers) - 1):
        lo, name, fill = tiers[i]
        hi = tiers[i + 1][0]
        x0, x1 = px(lo), px(hi)
        b.append(f'<rect x="{x0 + 1:.1f}" y="{bar_y}" width="{x1 - x0 - 2:.1f}" '
                 f'height="{bar_h}" fill="{fill}"/>')
        b.append(t(x0 + 1, 562, str(lo), 10, G4, 500, family=MONO))
        b.append(t(x0 + 8, bar_y + 34, name, 14, INK if lo == 0 else G5,
                   600 if lo == 0 else 400))
    b.append(t(R, 562, "100", 10, G4, 500, anchor="end", family=MONO))

    b.append(rule(PAD, 632, R))
    b.append(t(PAD, 666, "证据落地 ./reports/<id>/ · 每条结论带原始 JSON，可复核、可反驳", 13, G5))
    b.append(t(R, 666, "Python 3.10+ · openai / tiktoken / requests", 13, G4, anchor="end"))
    return canvas(W, H, "".join(b))


def case_forensics():
    W, H, PAD = 1600, 800, 64
    R = W - PAD
    LX, RX = PAD, 1000

    b = []
    b.append(t(PAD, 84, "Relay-X · 脱敏案例", 28, INK, 700))
    b.append(t(PAD, 112, "2026-08 复测 · 站点身份与联系方式已按合规要求隐去", 13, G4))
    b.append(t(R, 84, "单次取证消耗 < $0.05", 14, G5, anchor="end"))
    b.append(rule(PAD, 138, R))

    b.append(vrule(RX - 44, 170, 744))

    b.append(t(LX, 180, "证据链 / EVIDENCE CHAIN", 12, G4, 500, ls="0.2em"))
    rows = [
        ("01", "宣称官方直连，8 条渠道中 6 条由同一家第三方后端供货", "贴牌转售"),
        ("02", "中文身份问题 100% 改道另一型号，英文提问正常（p<0.001）", "内容路由"),
        ("03", "提取到三层注入提示词：身份层 / 皮肤层 / 思维链指令层", "封口指令"),
        ("04", "同一 SKU 在 60 秒内先后命中两家上游，一家回显默认欢迎语", "渠道轮换"),
        ("05", "网关按 OpenAI 系分词器计费，与 cl100k 基线精确吻合", "计费错配"),
    ]
    top, rh = 202, 94
    for i, (num, text, tag) in enumerate(rows):
        y = top + i * rh
        b.append(rule(LX, y, RX - 84, G2))
        b.append(t(LX, y + 36, num, 12, G4, 500, family=MONO))
        for j, line in enumerate(wrap(text, 92)):
            b.append(t(LX + 38, y + 36 + j * 24, line, 16, INK if j == 0 else G5))
        b.append(t(RX - 84, y + 36, tag, 12, G4, 500, anchor="end", ls="0.08em"))
    b.append(rule(LX, top + len(rows) * rh, RX - 84, G3))

    bx, by = LX, 704
    b.append(t(bx, by, "8 条渠道 · 6 条指向同一上游", 13, INK, 500))
    for i in range(8):
        filled = i < 6
        b.append(f'<rect x="{bx + i * 26}" y="{by + 12}" width="16" height="16" '
                 f'fill="{INK if filled else "none"}" '
                 f'stroke="{INK if filled else G3}" stroke-width="1"/>')
    b.append(t(bx + 8 * 26 + 10, by + 25, "渠道池轮换，同一后端反复出现", 12, G4))

    b.append(t(RX, 180, "判决 / VERDICT", 12, G4, 500, ls="0.2em"))
    b.append(t(RX, 336, "33", 128, INK, 700, family=MONO, ls="-0.02em"))
    b.append(t(RX + 150, 334, "/ 100", 24, G4, 400, family=MONO))
    b.append(t(RX, 380, "高度可疑（大概率假货）", 21, INK, 700))

    sx0, sx1, sy = RX, R, 440
    mx = sx0 + (sx1 - sx0) * 33 / 100
    b.append(rule(sx0, sy, sx1, G3))
    b.append(f'<line x1="{sx0}" y1="{sy}" x2="{mx}" y2="{sy}" stroke="{NAVY}" stroke-width="3"/>')
    for v in (0, 25, 45, 65, 85, 100):
        px = sx0 + (sx1 - sx0) * v / 100
        b.append(f'<line x1="{px}" y1="{sy - 5}" x2="{px}" y2="{sy + 5}" '
                 f'stroke="{G4}" stroke-width="1"/>')
        b.append(t(px, sy + 22, str(v), 10, G4, anchor="middle", family=MONO))
    b.append(f'<line x1="{mx}" y1="{sy - 15}" x2="{mx}" y2="{sy - 3}" '
             f'stroke="{NAVY}" stroke-width="2"/>')
    b.append(f'<path d="M{mx - 5} {sy - 19} L{mx + 5} {sy - 19} L{mx} {sy - 9} Z" '
             f'fill="{NAVY}"/>')
    b.append(t(mx + 10, sy - 12, "33", 11, NAVY, 600, family=MONO))

    stats = [("P(正品)", "0.0005"), ("证据文件", "100+ 份"), ("留档方式", "全量 JSON")]
    for i, (k, v) in enumerate(stats):
        x = RX + i * 168
        b.append(t(x, 520, k, 12, G4))
        b.append(t(x, 548, v, 19, INK, 600, family=MONO))

    b.append(rule(RX, 588, R, G2))
    for j, line in enumerate([
        "结论基于黑盒行为证据。要 100% 铁证，",
        "可加跑官方端点同题对照（--baseline / MET）。",
    ]):
        b.append(t(RX, 620 + j * 24, line, 12, G5))

    b.append(rule(PAD, 762, R))
    b.append(t(PAD, 788, "芯火 XH · github.com/Dragon-01-you/xh-forensics", 12, G4))
    b.append(t(R, 788, "同理可跑自己的端点：xh dig --base-url ... --key ...", 12, G4, anchor="end"))
    return canvas(W, H, "".join(b))


# ----------------------------------------------------------------------
def render(svg_path, png_path, w, h):
    if not (CHROME and os.path.isfile(CHROME)):
        print(f"[!] 未找到 Chrome，跳过位图渲染：{png_path}")
        return False
    tmp = os.path.join("/tmp", "art_" + os.path.basename(svg_path) + ".html")
    with open(svg_path, encoding="utf-8") as f:
        svg = f.read()
    with open(tmp, "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8">'
                "<style>html,body{margin:0;background:%s}svg{display:block}</style>%s"
                % (PAPER, svg))
    subprocess.run(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=2", f"--window-size={w},{h}",
         f"--screenshot={png_path}", "file://" + tmp],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[+] {png_path} {os.path.getsize(png_path)} B")
    return True


def main():
    os.makedirs(ASSETS, exist_ok=True)
    art = [("how_it_works", how_it_works(), 1600, 700),
           ("case_forensics", case_forensics(), 1600, 800)]
    for name, svg, w, h in art:
        svg_path = os.path.join(ASSETS, name + ".svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"[+] {svg_path} {len(svg)} B")
        render(svg_path, os.path.join(ASSETS, name + ".png"), w, h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
