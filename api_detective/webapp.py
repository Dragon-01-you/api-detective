#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webapp: 本地 Web UI 报告可视化（零新增依赖，纯 Python 标准库）。

启动: python -m api_detective web [--port 8501] [--reports ./reports]

技术选型（为什么不用 Streamlit/FastAPI）:
  - 本项目铁律是极简依赖（核心 3 个）。Web UI 用 http.server + 内嵌单页 HTML
    + SSE（chunked 响应）实现全部功能，零新增依赖
  - 仅监听 127.0.0.1——零遥测原则的延伸：不上传任何数据，不对外网暴露

功能:
  a) 输入表单: base_url + api_key + model 下拉（自动拉 /v1/models）
  b) SSE 实时推送每个探针进度
  c) 检测完成后生成报告卡片（SVG 恒有；装了 Pillow 则另存 report_card.jpg）
  d) 每份报告唯一 report_id，保存到 reports/<id>/，本地 /r/<id> 可访问
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

REPORTS_DIR = "./reports"
_runs: dict[str, dict] = {}   # report_id → {queue, status, proc}


# ----------------------------------------------------------------------
# 检测执行（subprocess 复用 CLI，天然隔离）
# ----------------------------------------------------------------------
def _run_dig(report_id: str, base_url: str, api_key: str, model: str,
             budget: int | None, compare_model: str | None,
             baseline: str | None, q: "queue.Queue[str]") -> None:
    out_dir = os.path.join(REPORTS_DIR, report_id)
    os.makedirs(out_dir, exist_ok=True)
    cmd = [sys.executable, "-m", "api_detective", "dig",
           "--base-url", base_url, "--api-key", api_key,
           "--model", model, "--out", out_dir]
    if budget:
        cmd += ["--budget", str(budget)]
    if compare_model:
        cmd += ["--compare-model", compare_model]
    if baseline:
        cmd += ["--baseline", baseline]
    rec = _runs[report_id]
    rec["cmd_tail"] = " ".join(cmd).replace(api_key, "sk-***")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=os.getcwd())
        rec["proc"] = proc
        for line in proc.stdout:  # type: ignore[union-attr]
            q.put(line.rstrip())
        proc.wait()
        rec["status"] = "done" if proc.returncode == 0 else "failed"
    except Exception as e:  # noqa: BLE001
        q.put(f"[webapp] dig 启动失败: {e}")
        rec["status"] = "failed"
    finally:
        q.put(None)  # 结束标记
        _maybe_make_card(report_id, out_dir, model)


def _maybe_make_card(report_id: str, out_dir: str, model: str) -> None:
    """生成报告卡片：SVG 恒有；Pillow 可用时另存 JPG。"""
    try:
        res_path = os.path.join(out_dir, "_final_results.json")
        if not os.path.isfile(res_path):
            return
        with open(res_path, encoding="utf-8") as f:
            results = json.load(f)
        v = results.get("verdict") or {}
        score = v.get("score", "?")
        tier = v.get("tier", "?")
        p = v.get("p_genuine")
        clues = (v.get("clues") or [])[:3]
        url = f"http://localhost:8501/r/{report_id}"
        svg = _render_card_svg(report_id, model, score, tier, p, clues, url)
        with open(os.path.join(out_dir, "report_card.svg"), "w",
                  encoding="utf-8") as f:
            f.write(svg)
        # Pillow 可选: SVG→JPG 直接重绘（不做 SVG 光栅化）
        try:
            _render_card_jpg(out_dir, report_id, model, score, tier, p,
                             clues, url)
        except ImportError:
            pass
    except Exception:  # noqa: BLE001 —— 卡片失败不影响报告
        pass


def _card_texts(clues: list) -> list[str]:
    out = []
    for c in clues:
        t = c.get("finding") or c.get("id") or ""
        out.append(_xml_escape(t[:60]))
    return out or ["（无显著线索）"]


def _xml_escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _render_card_svg(rid: str, model: str, score, tier, p,
                     clues: list, url: str) -> str:
    color = "#e0533d" if isinstance(score, int) and score < 45 else \
        ("#e8a33d" if isinstance(score, int) and score < 65 else "#3da85c")
    lines = _card_texts(clues)
    clue_rows = "".join(
        f'<text x="40" y="{230 + i * 34}" font-size="16" fill="#444">'
        f'• {lines[i]}</text>' for i in range(len(lines)))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420">
<rect width="640" height="420" rx="18" fill="#fafbfc" stroke="#d8dee4"/>
<rect width="640" height="92" rx="18" fill="#1b2430"/>
<text x="40" y="46" font-size="26" font-weight="bold" fill="#fff">API Detective 报告卡片</text>
<text x="40" y="74" font-size="15" fill="#9fb0c3">model: {_xml_escape(model)} · id: {rid[:8]}</text>
<text x="40" y="165" font-size="58" font-weight="bold" fill="{color}">{score}</text>
<text x="160" y="165" font-size="20" fill="#333">/100 · {_xml_escape(tier)}</text>
<text x="160" y="192" font-size="15" fill="#777">P(正品) = {p if p is not None else 'N/A'}</text>
<text x="40" y="205" font-size="14" fill="#999">关键证据</text>
{clue_rows}
<text x="40" y="385" font-size="14" fill="#4a90d9">{_xml_escape(url)}</text>
</svg>"""


def _render_card_jpg(out_dir: str, rid: str, model: str, score, tier, p,
                     clues: list, url: str) -> None:
    from PIL import Image, ImageDraw  # 可选依赖
    img = Image.new("RGB", (640, 420), "#fafbfc")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 640, 92], 18, fill="#1b2430")
    d.text((40, 24), "API Detective Report", fill="#ffffff")
    d.text((40, 52), f"model: {model[:40]} · id: {rid[:8]}", fill="#9fb0c3")
    color = "#e0533d" if isinstance(score, int) and score < 45 else \
        ("#e8a33d" if isinstance(score, int) and score < 65 else "#3da85c")
    d.text((40, 120), str(score), fill=color)
    d.text((160, 128), f"/100  {tier}", fill="#333333")
    d.text((160, 155), f"P(genuine) = {p}", fill="#777777")
    y = 215
    for c in clues[:3]:
        d.text((40, y), f"* {str(c.get('finding'))[:56]}", fill="#444444")
        y += 34
    d.text((40, 380), url, fill="#4a90d9")
    img.save(os.path.join(out_dir, "report_card.jpg"), quality=92)


# ----------------------------------------------------------------------
# 内嵌单页前端
# ----------------------------------------------------------------------
_INDEX_HTML = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>API Detective — 本地控制台</title>
<style>
:root{--bg:#0f141a;--panel:#161d26;--line:#232d3a;--txt:#dbe4ee;--dim:#8296ad;--ok:#3da85c;--warn:#e8a33d;--bad:#e0533d;--acc:#4a90d9}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--txt)}
.wrap{max-width:860px;margin:0 auto;padding:36px 20px}
h1{font-size:26px}h1 span{color:var(--acc)}
.sub{color:var(--dim);margin-top:-8px;font-size:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;margin-top:22px}
label{display:block;font-size:13px;color:var(--dim);margin:12px 0 6px}
input,select{width:100%;padding:10px 12px;border-radius:8px;border:1px solid var(--line);background:#0d1218;color:var(--txt);font-size:14px}
.row{display:flex;gap:12px}.row>div{flex:1}
button{margin-top:18px;width:100%;padding:12px;border:none;border-radius:8px;background:var(--acc);color:#fff;font-size:15px;cursor:pointer}
button:disabled{opacity:.5;cursor:wait}
#log{margin-top:22px;background:#0a0e13;border:1px solid var(--line);border-radius:10px;padding:14px;height:320px;overflow-y:auto;font:12px/1.7 ui-monospace,Consolas,monospace;white-space:pre-wrap;display:none}
.report{margin-top:18px;display:none}
.badge{display:inline-block;padding:4px 12px;border-radius:20px;font-weight:600}
.kv{font-size:14px;line-height:2}
a{color:var(--acc)}
</style></head><body><div class="wrap">
<h1>🔍 API <span>Detective</span> 本地控制台</h1>
<p class="sub">零遥测：仅监听 127.0.0.1，所有数据保存在本地 ./reports</p>
<div class="card">
<label>Base URL（OpenAI 兼容，通常以 /v1 结尾）</label>
<input id="base_url" placeholder="https://relay.example.com/v1">
<label>API Key（仅本地使用）</label>
<input id="api_key" type="password" placeholder="sk-xxx">
<div class="row">
<div><label>模型（声称的 SKU）</label><input id="model" placeholder="点击下方按钮自动拉取"></div>
<div><label>预算（计费调用上限，防烧钱）</label><input id="budget" type="number" value="120"></div>
</div>
<div class="row">
<div><label>对照模型（可选，MET 同一性检验）</label><input id="compare_model" placeholder="同站第二个模型"></div>
<div><label>官方基线（可选，严格比对）</label><input id="baseline" placeholder="如 gpt-4o"></div>
</div>
<button id="btn_models" onclick="fetchModels()">拉取模型列表</button>
<button id="btn" onclick="startDig()">开始取证</button>
</div>
<div id="log"></div>
<div class="card report" id="report"></div>
</div>
<script>
async function fetchModels(){
 const b=document.getElementById('base_url').value.trim(),k=document.getElementById('api_key').value.trim();
 if(!b||!k){alert('先填 Base URL 和 API Key');return}
 const btn=document.getElementById('btn_models');btn.disabled=true;btn.textContent='拉取中...';
 try{const r=await fetch('/api/models?base_url='+encodeURIComponent(b)+'&api_key='+encodeURIComponent(k));
 const j=await r.json();
 if(j.models&&j.models.length){const m=document.getElementById('model');
 m.value=j.models[0];m.setAttribute('list','ml');
 let dl='<datalist id="ml">';j.models.forEach(x=>dl+='<option value="'+x+'">');dl+='</datalist>';
 document.body.insertAdjacentHTML('beforeend',dl);alert('拉到 '+j.models.length+' 个模型，已填入第一个。输入框可下拉选择')}else{alert('拉取失败: '+(j.error||'空列表'))}}
 catch(e){alert('拉取失败: '+e)}finally{btn.disabled=false;btn.textContent='拉取模型列表'}
}
async function startDig(){
 const p={base_url:document.getElementById('base_url').value.trim(),
 api_key:document.getElementById('api_key').value.trim(),
 model:document.getElementById('model').value.trim(),
 budget:document.getElementById('budget').value,
 compare_model:document.getElementById('compare_model').value.trim(),
 baseline:document.getElementById('baseline').value.trim()};
 if(!p.base_url||!p.api_key||!p.model){alert('Base URL / API Key / 模型 均必填');return}
 const btn=document.getElementById('btn');btn.disabled=true;btn.textContent='取证进行中...';
 const log=document.getElementById('log');log.style.display='block';log.textContent='';
 const rep=document.getElementById('report');rep.style.display='none';
 try{
  const r=await fetch('/api/dig',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
  const j=await r.json();const rid=j.report_id;
  const es=new EventSource('/api/progress/'+rid);
  es.onmessage=ev=>{if(ev.data==='__END__'){es.close();loadReport(rid);return}
   log.textContent+=ev.data+'\\n';log.scrollTop=log.scrollHeight};
  es.onerror=()=>{es.close();loadReport(rid)}
 }catch(e){alert('启动失败: '+e);btn.disabled=false;btn.textContent='开始取证'}
}
async function loadReport(rid){
 const btn=document.getElementById('btn');btn.disabled=false;btn.textContent='开始取证';
 try{const r=await fetch('/api/report/'+rid);const j=await r.json();
 const v=j.verdict||{};const c=v.score<45?'var(--bad)':(v.score<65?'var(--warn)':'var(--ok)');
 const clueList=(v.clues||[]).slice(0,6).map(x=>'<div class="kv">• '+x.finding+'</div>').join('');
 const rep=document.getElementById('report');rep.style.display='block';
 rep.innerHTML='<h2 style="margin:0">判决：<span style="color:'+c+'">'+v.score+'/100 · '+v.tier+'</span></h2>'
 +'<div class="kv">P(正品) = '+v.p_genuine+' · 证据覆盖率 '+Math.round((v.coverage||0)*100)+'%'
 +(v.inconclusive?' · <b style="color:var(--warn)">证据不足</b>':'')+'</div>'
 +'<h3>关键证据</h3>'+clueList
 +'<div class="kv" style="margin-top:14px">报告目录: <a href="/r/'+rid+'" target="_blank">/r/'+rid+'</a>（DOSSIER.md · report_card.svg · 全量 JSON）</div>'
 }catch(e){}
}
</script></body></html>"""


# ----------------------------------------------------------------------
# HTTP 服务
# ----------------------------------------------------------------------
def _fetch_models(base_url: str, api_key: str) -> dict:
    import requests
    url = base_url.rstrip("/") + "/models"
    if not base_url.rstrip("/").endswith("/v1"):
        url = base_url.rstrip("/") + "/v1/models"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {api_key}"},
                         timeout=20)
        js = r.json()
        models = [m.get("id") for m in js.get("data", []) if m.get("id")]
        return {"models": sorted(models)}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:300]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 静默访问日志
        pass

    # ---- helpers ----
    def _json(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text: str, code: int = 200) -> None:
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- GET ----
    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._html(_INDEX_HTML)
        elif u.path == "/api/models":
            qs = parse_qs(u.query)
            self._json(_fetch_models(qs.get("base_url", [""])[0],
                                     qs.get("api_key", [""])[0]))
        elif u.path.startswith("/api/progress/"):
            rid = u.path.rsplit("/", 1)[-1]
            self._sse(rid)
        elif u.path.startswith("/api/report/"):
            rid = u.path.rsplit("/", 1)[-1]
            path = os.path.join(REPORTS_DIR, rid, "_final_results.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    self._json(json.load(f))
            else:
                self._json({"error": "报告尚未生成"}, 404)
        elif u.path.startswith("/r/"):
            rid = u.path.split("/r/")[-1].strip("/")
            self._report_page(rid)
        else:
            self._json({"error": "not found"}, 404)

    # ---- POST ----
    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        if u.path == "/api/dig":
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n).decode())
            except ValueError:
                self._json({"error": "bad json"}, 400)
                return
            rid = uuid.uuid4().hex[:12]
            q: "queue.Queue[str]" = queue.Queue()
            _runs[rid] = {"queue": q, "status": "running"}
            t = threading.Thread(
                target=_run_dig,
                args=(rid, body.get("base_url", ""), body.get("api_key", ""),
                      body.get("model", ""), body.get("budget") or None,
                      body.get("compare_model") or None,
                      body.get("baseline") or None, q),
                daemon=True)
            t.start()
            self._json({"report_id": rid})
        else:
            self._json({"error": "not found"}, 404)

    # ---- SSE ----
    def _sse(self, rid: str) -> None:
        rec = _runs.get(rid)
        if not rec:
            self._json({"error": "unknown report_id"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        q: "queue.Queue[str]" = rec["queue"]
        try:
            while True:
                try:
                    item = q.get(timeout=90)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\\n\\n")
                    self.wfile.flush()
                    continue
                if item is None:
                    self.wfile.write(b"data: __END__\\n\\n")
                    self.wfile.flush()
                    break
                payload = json.dumps(item, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\\n\\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- 报告页 ----
    def _report_page(self, rid: str) -> None:
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", rid)[:32]
        res_path = os.path.join(REPORTS_DIR, rid, "_final_results.json")
        if not os.path.isfile(res_path):
            self._html(f"<h2>报告 {rid} 尚未生成</h2>", 404)
            return
        with open(res_path, encoding="utf-8") as f:
            results = json.load(f)
        v = results.get("verdict") or {}
        meta = results.get("meta") or {}
        clues = v.get("clues") or []
        rows = "".join(
            f"<tr><td>{_x(c.get('category'))}</td>"
            f"<td>{_x(c.get('finding'))}</td>"
            f"<td>{_x(c.get('layman'))}</td></tr>"
            for c in clues)
        self._html(f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>报告 {rid}</title><style>
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0f141a;color:#dbe4ee;margin:0;padding:40px 20px}}
.w{{max-width:900px;margin:0 auto}}h1{{font-size:22px}}
table{{border-collapse:collapse;width:100%;margin-top:18px;font-size:13px}}
td,th{{border:1px solid #232d3a;padding:8px 10px;text-align:left;vertical-align:top}}
th{{background:#161d26}}.score{{font-size:48px;font-weight:700}}
a{{color:#4a90d9}}</style></head><body><div class="w">
<h1>🔍 API Detective 报告 <small style="color:#8296ad">{_x(rid)}</small></h1>
<p>端点: {_x(meta.get('base_url'))} · 模型: {_x(meta.get('model'))} · {_x(meta.get('ts_utc'))}</p>
<div class="score">{_x(v.get('score'))}/100</div>
<p><b>{_x(v.get('tier'))}</b> — {_x(v.get('tier_desc'))}</p>
<p>P(正品) = {_x(v.get('p_genuine'))} · 覆盖率 {_x(v.get('coverage'))} · 温度 {_x(v.get('temperature'))}</p>
{_x(v.get('edge_case_note'))}
<table><tr><th>类别</th><th>发现</th><th>小白解释</th></tr>{rows}</table>
<p style="color:#8296ad;font-size:12px;margin-top:26px">{_x(v.get('disclaimer'))}</p>
<p>本地文件: ./reports/{_x(rid)}/（DOSSIER.md · report_card.svg · 全量 JSON 证据）</p>
</div></body></html>""")


def _x(s) -> str:
    return _xml_escape(str(s if s is not None else ""))


# ----------------------------------------------------------------------
def run_webapp(port: int = 8501, reports_dir: str = REPORTS_DIR) -> None:
    global REPORTS_DIR
    REPORTS_DIR = reports_dir
    os.makedirs(REPORTS_DIR, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[*] API Detective Web UI: http://127.0.0.1:{port}")
    print(f"[*] 报告目录: {os.path.abspath(REPORTS_DIR)}（零遥测，仅本地监听）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] 已停止")
