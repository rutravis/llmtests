#!/usr/bin/env python3
"""Render a battery JSON report as a single self-contained HTML file.

Usage:
    python3 make_html_report.py                      # newest results/report-*.json
    python3 make_html_report.py results/report-X.json [--out FILE]

The output is one HTML file with inline CSS/JS and no external assets, so it
can be served from any static web server or opened directly in a browser.
"""

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"

_CSS = """
:root{--bg:#0f1117;--card:#171a23;--line:#262b38;--fg:#e6e9f0;--dim:#98a0b3;
--ok:#2ecc71;--bad:#e74c3c;--warn:#f39c12;--acc:#4f9cf9}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;padding:28px}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:26px;letter-spacing:.3px}
.meta{color:var(--dim);margin:6px 0 22px}
.meta b{color:var(--fg);font-weight:600}
.overview{display:flex;gap:22px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 24px;margin-bottom:22px;flex-wrap:wrap}
.ring{--p:0%;width:120px;height:120px;border-radius:50%;flex:0 0 auto;
background:conic-gradient(var(--ok) calc(var(--p)), #2a3040 0);display:flex;align-items:center;justify-content:center}
.ring>div{width:88px;height:88px;border-radius:50%;background:var(--card);display:flex;flex-direction:column;align-items:center;justify-content:center}
.ring .pct{font-size:22px;font-weight:700}
.ring .sub{font-size:11px;color:var(--dim)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;flex:1;min-width:260px}
.stat{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.stat .v{font-size:20px;font-weight:700}
.stat .k{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.6px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;cursor:pointer}
.card.sel{border-color:var(--acc)}
.card .sname{font-size:14px;font-weight:600;margin-bottom:6px}
.card .snum{font-size:12px;color:var(--dim)}
.bar{height:6px;border-radius:3px;background:#2a3040;margin-top:8px;overflow:hidden}
.bar>div{height:100%;border-radius:3px;background:var(--ok)}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.controls input[type=search]{flex:1;min-width:200px;background:var(--card);border:1px solid var(--line);border-radius:8px;color:var(--fg);padding:8px 12px;font-size:14px;outline:none}
.controls input[type=search]:focus{border-color:var(--acc)}
button{background:var(--card);border:1px solid var(--line);border-radius:8px;color:var(--fg);padding:8px 12px;font-size:13px;cursor:pointer}
button:hover{border-color:var(--acc)}
button.sel{border-color:var(--acc);color:var(--acc)}
.test{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:10px;overflow:hidden}
.test.hidden{display:none}
.trow{display:flex;align-items:center;gap:12px;padding:12px 16px;cursor:pointer;user-select:none}
.trow:hover{background:#1b1f2b}
.chip{flex:0 0 auto;font-size:11px;font-weight:700;border-radius:5px;padding:3px 8px;letter-spacing:.5px}
.chip.pass{background:#173d2b;color:var(--ok)}
.chip.fail{background:#3d1a1a;color:var(--bad)}
.chip.err{background:#3d2f14;color:var(--warn)}
.tname{flex:0 0 auto;font-weight:600;font-size:14px;min-width:220px}
.tbar{flex:1;height:6px;border-radius:3px;background:#2a3040;overflow:hidden;min-width:80px}
.tbar>div{height:100%;background:var(--acc)}
.tsidemetrics{flex:0 0 auto;color:var(--dim);font-size:12px;text-align:right}
.tbody{border-top:1px solid var(--line);padding:14px 18px;display:none}
.tbody.open{display:block}
.dets{list-style:none;margin-bottom:12px}
.dets li{color:var(--dim);font-size:13px;padding:2px 0 2px 16px;position:relative}
.dets li:before{content:'▸';position:absolute;left:2px;color:var(--acc)}
details{margin-top:10px}
summary{cursor:pointer;color:var(--acc);font-size:13px;font-weight:600;padding:4px 0}
pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto;font:12.5px/1.55 'SF Mono',Consolas,Menlo,monospace;white-space:pre-wrap;word-break:break-word;max-height:520px}
.foot{color:var(--dim);font-size:12px;margin-top:26px;text-align:center}
@media(max-width:640px){.tname{min-width:0;flex:1}.tsidemetrics{display:none}}
"""

_JS = """
function toggleBody(row){row.nextElementSibling.classList.toggle('open')}
function toggleAll(open){document.querySelectorAll('.tbody').forEach(b=>b.classList.toggle('open',open))}
function applyFilter(){
  var q=document.getElementById('q').value.toLowerCase();
  var suite=document.querySelector('#suites .card.sel').dataset.suite;
  var st=document.querySelector('.stbtn.sel').dataset.st;
  document.querySelectorAll('.test').forEach(function(t){
    var ok=(!q||t.dataset.name.indexOf(q)>=0)
      &&(suite==='all'||t.dataset.suite===suite)
      &&(st==='all'||t.dataset.status===st);
    t.classList.toggle('hidden',!ok);
  });
}
document.querySelectorAll('#suites .card').forEach(function(c){
  c.onclick=function(){
    document.querySelectorAll('#suites .card').forEach(function(x){x.classList.remove('sel')});
    c.classList.add('sel');applyFilter();
  };
});
document.querySelectorAll('.stbtn').forEach(function(b){
  b.onclick=function(){
    document.querySelectorAll('.stbtn').forEach(function(x){x.classList.remove('sel')});
    b.classList.add('sel');applyFilter();
  };
});
document.getElementById('q').addEventListener('input',applyFilter);
"""


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _fmt_duration(sec: float) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _status_chip(t: dict) -> str:
    if t.get("error"):
        return '<span class="chip err">ERROR</span>'
    return f'<span class="chip {"pass" if t["passed"] else "fail"}">{"PASS" if t["passed"] else "FAIL"}</span>'


def _test_html(key: str, t: dict) -> str:
    out = []
    out.append(f'<div class="test" data-suite="{_esc(key)}" data-name="'
               f'{_esc(t["name"].lower())}" data-status="{"err" if t.get("error") else ("pass" if t["passed"] else "fail")}">')
    out.append(f'<div class="trow" onclick="toggleBody(this)">')
    out.append(_status_chip(t))
    out.append(f'<span class="tname">{_esc(t["name"])}</span>')
    out.append(f'<div class="tbar"><div style="width:{max(2, round(t["score"] * 100))}%"></div></div>')
    side = f'{t["score"]:.0%} · {_fmt_duration(t.get("elapsed_s", 0))}'
    if t.get("prefill_ms"):
        side += f' · prefill {int(t["prefill_ms"])}ms'
    if t.get("gen_speed") and t["gen_speed"] > 0:
        side += f' · {t["gen_speed"]} tok/s'
    pt = t.get("prompt_tokens", 0) or 0
    ct = t.get("completion_tokens", 0) or 0
    rt = t.get("reasoning_tokens", 0) or 0
    if pt or ct:
        side += f' · {pt}→{ct}'
    if rt:
        side += f' ({rt} think)'
    if t.get("finish_reason"):
        side += f' · finish: {_esc(t["finish_reason"])}'
    out.append(f'<span class="tsidemetrics">{side}</span>')
    out.append('</div><div class="tbody">')

    if t.get("error"):
        out.append(f'<ul class="dets"><li><b>API error:</b> {_esc(t["error"])}</li></ul>')
    elif t.get("details"):
        out.append('<ul class="dets">')
        out.extend(f'<li>{_esc(d)}</li>' for d in t["details"])
        out.append('</ul>')

    if t.get("model_output"):
        out.append('<details open><summary>Model output</summary>'
                   f'<pre>{_esc(t["model_output"])}</pre></details>')
    reasoning = t.get("reasoning") or ""
    if reasoning:
        out.append(f'<details><summary>Reasoning ({len(reasoning):,} chars)</summary>'
                   f'<pre>{_esc(reasoning)}</pre></details>')
    out.append('</div></div>')
    return "".join(out)


def generate_html(report: dict) -> str:
    ts = report.get("timestamp", "")
    try:
        date_str = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        date_str = ts or "unknown date"

    overall = report.get("overall", {})
    pct = overall.get("pct", 0) or 0
    suites = report.get("suites", {})

    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{_esc(report.get("model", "LLM"))} — LLM Evaluation</title>',
             f'<style>{_CSS}</style></head><body><div class="wrap">']

    # header: model name + testing date
    parts.append(f'<h1>{_esc(report.get("model", "unknown model"))}</h1>')
    tested = (f'Tested <b>{_esc(date_str)}</b> · endpoint <b>{_esc(report.get("base_url", "n/a"))}</b>'
              f' · <b>{overall.get("total", 0)}</b> tests in <b>{_fmt_duration(overall.get("total_elapsed_s", 0))}</b>')
    parts.append(f'<div class="meta">{tested}</div>')
    # Session / model config details (inferred from model name + env vars)
    sess = report.get("session", {})
    if sess:
        parts.append('<div class="overview" style="margin-bottom:14px">')
        parts.append('<div style="font-size:13px;font-weight:600;margin-right:auto;color:var(--dim)">SESSION</div>')
        parts.append('<div class="stats">')
        for k, v in sess.items():
            if v is None or (isinstance(v, str) and not v):
                continue
            vk = {"ctx_window": "ctx", "gpu_offload_layers": "gpu layers",
                  "reasoning_budget_tokens": "think budget", "moe_experts": "experts",
                  "speculative_decoding": "spec-dec", "draft_tokens_per_step": "drafts/step",
                  "cache_quantization": "cache quant", "system_fingerprint": "fingerprint",
                  "base_url": "endpoint"}.get(k, k)
            parts.append(f'<div class="stat"><div class="v">{_esc(str(v))}</div><div class="k">{vk}</div></div>')
        parts.append('</div></div>')

    # overview
    parts.append('<div class="overview">')
    parts.append(f'<div class="ring" style="--p:{round(pct * 100)}%"><div>'
                 f'<span class="pct">{pct:.0%}</span><span class="sub">overall</span></div></div>')
    errored = sum(1 for s in suites.values() for t in s.get("tests", []) if t.get("error"))
    stats = [(overall.get("passed", 0), "passed"),
             (overall.get("total", 0) - overall.get("passed", 0) - errored, "failed"),
             (errored, "api errors"),
             (len(suites), "suites")]
    parts.append('<div class="stats">')
    for v, k in stats:
        parts.append(f'<div class="stat"><div class="v">{v}</div><div class="k">{k}</div></div>')
    parts.append('</div></div>')

    # suite cards (clickable filters)
    parts.append('<div id="suites" class="cards">')
    all_sel = ' class="card sel"' if True else ""
    parts.append(f'<div{all_sel} data-suite="all"><div class="sname">All suites</div>'
                 f'<div class="snum">{overall.get("total", 0)} tests</div></div>')
    for key, s in suites.items():
        spct = (s["passed"] / s["total"]) if s.get("total") else 0
        parts.append(f'<div class="card" data-suite="{_esc(key)}">'
                     f'<div class="sname">{_esc(s.get("name", key))}</div>'
                     f'<div class="snum">{s.get("passed", 0)}/{s.get("total", 0)} passed · avg {s.get("avg_score", 0):.0%}</div>'
                     f'<div class="bar"><div style="width:{round(spct * 100)}%"></div></div></div>')
    parts.append('</div>')

    # controls
    parts.append('<div class="controls"><input id="q" type="search" placeholder="Filter tests…">'
                 '<button class="stbtn sel" data-st="all">All</button>'
                 '<button class="stbtn" data-st="pass">Passed</button>'
                 '<button class="stbtn" data-st="fail">Failed</button>'
                 '<button class="stbtn" data-st="err">Errors</button>'
                 '<button onclick="toggleAll(true)">Expand all</button>'
                 '<button onclick="toggleAll(false)">Collapse all</button></div>')

    # tests
    for key, s in suites.items():
        parts.extend(_test_html(key, t) for t in s.get("tests", []))

    parts.append(f'<div class="foot">llmtests evaluation battery · generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</div>')
    parts.append(f'</div><script>{_JS}</script></body></html>')
    return "".join(parts)


def newest_report() -> Path:
    reports = sorted(RESULTS_DIR.glob("report-*.json"))
    if not reports:
        sys.exit("no results/report-*.json found")
    return reports[-1]


def write_html(report_path: Path, out_path: Path | None = None) -> Path:
    report = json.loads(report_path.read_text())
    if out_path is None:
        model = (report.get("model", "model").replace("/", "_"))
        out_path = RESULTS_DIR / f"{model}-{report_path.stem.replace('report-', '')}.html"
    out_path.write_text(generate_html(report))
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", nargs="?", help="report JSON (default: newest in results/)")
    ap.add_argument("--out", help="output HTML path")
    args = ap.parse_args()
    report_path = Path(args.report) if args.report else newest_report()
    out = write_html(report_path, Path(args.out) if args.out else None)
    print(f"HTML report: {out}")


if __name__ == "__main__":
    main()
