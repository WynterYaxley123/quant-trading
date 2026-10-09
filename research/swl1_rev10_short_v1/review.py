"""Private, self-contained offline review assembled from verified existing results."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from research.swl1_failure_forensics.boundary import contained, sha
from research.swl1_short_horizon_exploration.charts import CHARTS
from research.swl1_short_horizon_exploration.design import REPORT_DIR
from research.swl1_short_horizon_exploration.verify import REPORTS, verify_reports

from .model import CODES, validate_asof
from .replay import load_spec, write


def private_preview(root: Path, preview: Path, pin: str) -> dict[str, Any]:
    spec, model_hash = load_spec(root)
    if preview.resolve() != preview or any(
        (parent / ".git").exists() for parent in (preview, *preview.parents)
    ):
        raise ValueError("PRIVATE_PREVIEW_OUTSIDE_GIT_REQUIRED")
    manifest_path = contained(preview, "manifest.json")
    if sha(manifest_path) != pin:
        raise ValueError("PRIVATE_MANIFEST_PIN_MISMATCH")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest["namespace"] != "RESEARCH_REPLAY_ONLY"
        or manifest["model_hash"] != model_hash
        or manifest["asof"] > spec["historical_cutoff"]
        or manifest["count"] != 30
        or manifest["source_commit"] != spec["source_commit"]
    ):
        raise ValueError("PRIVATE_PREVIEW_SCOPE_MISMATCH")
    if set(manifest["files"]) != {"observation.json", "scores.json", "ranking.json"}:
        raise ValueError("PRIVATE_PREVIEW_FILES_MISMATCH")
    for name, expected in manifest["files"].items():
        leaf = contained(preview, name)
        if leaf.stat().st_size > 128 * 1024 or sha(leaf) != expected:
            raise ValueError("PRIVATE_PREVIEW_HASH_MISMATCH")
    if manifest["implementation_sha256"] != {
        name: sha(contained(root, f"research/swl1_rev10_short_v1/{name}"))
        for name in ("model.py", "replay.py")
    }:
        raise ValueError("PRIVATE_PREVIEW_IMPLEMENTATION_MISMATCH")
    observation = json.loads(contained(preview, "observation.json").read_text())
    if (
        observation["status"] != "HISTORICAL_REPLAY"
        or observation["namespace"] != "RESEARCH_REPLAY_ONLY"
        or observation["formal_forecast"] is not False
        or observation["future_numeric_rows_read"] != 0
        or observation["asof"] != manifest["asof"]
        or observation["cutoff"] != spec["historical_cutoff"]
        or observation["input_sha256"] != spec["view_sha256"]
        or observation["names_reference_sha256"] != spec["universe_sha256"]
    ):
        raise ValueError("PRIVATE_PREVIEW_SCOPE_MISMATCH")
    window = tuple(observation["window_sessions"])
    if len(window) != 10 or window[-1] != manifest["asof"]:
        raise ValueError("PRIVATE_PREVIEW_WINDOW_MISMATCH")
    try:
        validate_asof(window, manifest["asof"], spec["historical_cutoff"])
    except ValueError as exc:
        raise ValueError("PRIVATE_PREVIEW_WINDOW_MISMATCH") from exc
    ranking: dict[str, Any] = json.loads(contained(preview, "ranking.json").read_text())
    if (
        ranking["count"] != 30
        or ranking["status"] != "HISTORICAL_REPLAY"
        or ranking["asof"] != manifest["asof"]
        or ranking["namespace"] != "RESEARCH_REPLAY_ONLY"
        or ranking["complete_universe"] is not True
        or ranking["ranking_basis"] != "REV10_DESCENDING_CODE_ASCENDING_TIES"
        or len(ranking["rows"]) != 30
    ):
        raise ValueError("PRIVATE_PREVIEW_SCOPE_MISMATCH")
    rows = ranking["rows"]
    if tuple(sorted(row["industry_code"] for row in rows)) != CODES:
        raise ValueError("PRIVATE_PREVIEW_UNIVERSE_MISMATCH")
    universe = json.loads(contained(root, spec["universe_file"]).read_text())
    names = {item["code"]: item["name"] for item in universe["metadata"] if item.get("name")}
    mean = sum(row["rev10_score"] for row in rows) / 30
    for i, row in enumerate(rows):
        code = row["industry_code"]
        if (
            row["rank"] != i + 1
            or row["industry_name"] != names.get(code, code)
            or row["name_verified"] != bool(names.get(code))
            or row["data_asof"] != manifest["asof"]
            or row["source_generation"] != observation["source_generation"]
            or row["data_completeness"] != "10_OF_10_FINITE_SESSIONS"
            or not all(
                type(row[key]) in (float, int) and math.isfinite(row[key])
                for key in ("rev10_score", "relative_score", "trailing_mean_return")
            )
            or abs(row["rev10_score"] + row["trailing_mean_return"]) > 1e-12
            or abs(row["relative_score"] - (row["rev10_score"] - mean)) > 1e-12
        ):
            raise ValueError("PRIVATE_PREVIEW_ROW_MISMATCH")
    if rows != sorted(rows, key=lambda row: (-row["rev10_score"], row["industry_code"])):
        raise ValueError("PRIVATE_PREVIEW_ORDER_MISMATCH")
    bottom = sorted(rows, key=lambda row: (row["rev10_score"], row["industry_code"]))[:5]
    scores = json.loads(contained(preview, "scores.json").read_text())
    if (
        ranking["top5"] != rows[:5]
        or ranking["bottom5"] != bottom
        or scores["rows"] != sorted(rows, key=lambda row: row["industry_code"])
    ):
        raise ValueError("PRIVATE_PREVIEW_EXTREMES_MISMATCH")
    return ranking


STYLE = """
:root{color-scheme:light;font-family:system-ui,'Microsoft YaHei',sans-serif;color:#182b3d;background:#edf2f5}
*{box-sizing:border-box}body{margin:0}section,.card,details{min-width:0}header{background:#142c40;color:#fff;padding:32px max(24px,calc((100vw - 1200px)/2))}
header small{color:#a9c6d8;letter-spacing:.1em}h1{font-size:30px;margin:10px 0}h2{font-size:20px;margin:0 0 16px}p{line-height:1.7}
main{max-width:1248px;margin:auto;padding:24px;display:grid;gap:24px}.badge{display:inline-block;background:#fdf0d7;color:#80500a;border-radius:4px;padding:5px 10px;font-size:12px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.card,section{background:white;border:1px solid #d9e3ea;border-radius:10px;padding:24px}
.value{font-size:30px;font-weight:650;font-variant-numeric:tabular-nums;color:#117b78;margin:8px 0}.muted{color:#596d7f;font-size:13px}.grid{display:grid;grid-template-columns:2fr 1fr;gap:24px}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px 10px;border-bottom:1px solid #e6edf2;text-align:left;white-space:nowrap}th{font-size:12px;color:#596d7f;background:#f5f8fa}
td.number{text-align:right;font-variant-numeric:tabular-nums}button{border:1px solid #cad8e2;border-radius:5px;padding:8px 14px;background:white;cursor:pointer;margin:0 8px 16px 0}button[aria-pressed=true]{background:#142c40;color:white;border-color:#142c40}
.state{padding:12px 0;border-bottom:1px solid #e6edf2;display:flex;justify-content:space-between;gap:12px}.blocked{color:#9b6212}.chart{background:white;overflow:auto}.chart img{width:100%;height:auto;min-width:600px}.charts{display:grid;gap:18px}details{background:white;border:1px solid #d9e3ea;border-radius:8px;padding:18px}summary{cursor:pointer;font-weight:600}
a{color:#117b78}code{font-size:12px;overflow-wrap:anywhere}footer{padding:24px;text-align:center;color:#596d7f;font-size:12px}li{margin:8px 0;line-height:1.6}
@media(max-width:760px){header{padding:24px}h1{font-size:25px}.metrics{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}main{padding:16px}.card,section{padding:18px}.value{font-size:25px}.chart img{min-width:0}td,th{padding:10px 8px}}
"""


def build_review(
    root: Path, output: Path, preview: Path | None = None, pin: str = ""
) -> dict[str, Any]:
    verify_reports(root)
    spec, model_hash = load_spec(root)
    report = json.loads(contained(root, f"{REPORT_DIR}/research-summary.json").read_text())
    ranking = private_preview(root, preview, pin) if preview is not None else None
    if (
        output.resolve() != output
        or any((parent / ".git").exists() for parent in (output, *output.parents))
        or any(p.is_symlink() for p in output.rglob("*"))
    ):
        raise ValueError("PRIVATE_REVIEW_OUTSIDE_GIT_REQUIRED")
    output.mkdir(parents=True, exist_ok=True)
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    for name in CHARTS:
        shutil.copyfile(contained(root, f"{REPORT_DIR}/{name}"), assets / name)
    cards = []
    for h in ("10", "5"):
        m = report["models"]["S2"][h]
        for title, value, note in (
            (
                f"H{h} 平均 RankIC",
                f"{m['rank_ic']['mean']:+.6f}",
                f"{m['signal_count']} 个历史截面",
            ),
            (
                f"H{h} RankIC 正向比例",
                f"{m['rank_ic']['positive_fraction']:.2%}",
                "重叠样本，非独立试验",
            ),
        ):
            cards.append(
                f'<div class="card"><div class="muted">{title}</div><div class="value">{value}</div><div class="muted">{note}</div></div>'
            )
    ranking_html = '<p role="alert">排名不可用：未配置经过核验的私有历史重放工件。</p>'
    if ranking is not None:
        top = {r["industry_code"] for r in ranking["top5"]}
        bottom = {r["industry_code"] for r in ranking["bottom5"]}
        rows = []
        for r in ranking["rows"]:
            code = r["industry_code"]
            rows.append(
                f'<tr data-top="{str(code in top).lower()}" data-bottom="{str(code in bottom).lower()}"><td>{r["rank"]:02}</td><td>{escape(r["industry_name"])}<br><span class="muted">{code}</span></td><td class="number">{r["rev10_score"] * 100:+.4f}%</td><td class="number">{r["relative_score"] * 100:+.4f}%</td><td class="number">{r["trailing_mean_return"] * 100:+.4f}%</td><td>10/10 · 完整</td></tr>'
            )
        ranking_html = f'<p><strong>历史研究排名 · 不代表今日行情</strong><br><span class="muted">截至 {ranking["asof"]} · 30/30 行业完整 · 原始评分降序，代码升序处理并列</span></p><div role="group" aria-label="排名范围"><button data-filter="top" aria-pressed="false">Top5</button><button data-filter="bottom" aria-pressed="false">Bottom5</button><button data-filter="all" aria-pressed="true">全部 30 行业</button></div><div class="scroll"><table id="ranking"><thead><tr><th>排名</th><th>行业 / 代码</th><th>REV10 原始评分</th><th>相对评分</th><th>10 日平均收益</th><th>完整性</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><p class="muted">评分及日均收益以百分比展示。HISTORICAL_REPLAY / RESEARCH_REPLAY_ONLY · 名称来自已冻结宇宙映射。</p>'
    if ranking is not None:
        generation = escape(ranking["rows"][0]["source_generation"])
        ranking_html += f'<details><summary>查看 source generation 与输入绑定</summary><code>{generation}</code><p class="muted">私有 manifest SHA256：{escape(pin)}</p></details>'
    comparisons = []
    for ident, label in (
        ("S0", "等权 / 零评分"),
        ("S1", "REV5"),
        ("S2", "REV10"),
        ("S3", "等权双反转"),
        ("S4", "固定双因子 Ridge"),
    ):
        values = [report["models"][ident][h]["rank_ic"]["mean"] for h in ("5", "10")]
        formatted = ["未定义" if v is None else f"{v:+.6f}" for v in values]
        comparisons.append(
            f"<tr><td>{label}</td><td>{formatted[0]}</td><td>{formatted[1]}</td></tr>"
        )
    blocks = []
    for i in range(4):
        values = [
            report["models"]["S2"][h]["calendar_blocks"][i]["rank_ic"]["mean"] for h in ("5", "10")
        ]
        blocks.append(
            f"<tr><td>固定时间块 {i + 1}</td><td>{values[0]:+.6f}</td><td>{values[1]:+.6f}</td></tr>"
        )
    chart_titles = (
        "信号 RankIC",
        "四个时间块",
        "Ridge 配对比较",
        "因子与目标相关性",
        "行业敏感性",
        "集中度与换手",
    )
    chart_html = "".join(
        f'<details><summary>{title}</summary><div class="chart"><img src="assets/{name}" alt="{title}" loading="lazy"></div></details>'
        for name, title in zip(CHARTS, chart_titles, strict=True)
    )
    draft = escape(
        contained(root, "docs/research/swl1-rev10-preregistration-draft.zh-CN.md").read_text()
    )
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SWL1 REV10 · 中文研究控制台（离线）</title><style>{STYLE}</style></head><body>
<header><small>QUANT TRADING / INDUSTRY RESEARCH</small><h1>REV10 · 短周期行业研究</h1><p>SWL1 REV10 Short-V1 · 固定规则，无需训练 · 主终点 H10 / 次终点 H5</p><span class="badge">EXPLORATORY_POST_HOC · 后验探索</span></header><main>
<div class="metrics">{"".join(cards)}</div><div class="grid"><section><h2>30 行业历史排名</h2>{ranking_html}</section><section><h2>规则与证据状态</h2><p>REV10 = 过去 10 个每日收益的负算术均值，含信号日收盘。横截面中心化不改变排名。</p>
<div class="state"><span>模型实现</span><strong>研究专用 · 已完成</strong></div><div class="state"><span>历史探索</span><strong>已完成</strong></div><div class="state"><span>预注册草案</span><strong>已准备</strong></div><div class="state"><span>统计设计</span><strong class="blocked">待完成</strong></div><div class="state"><span>正式预注册</span><strong class="blocked">未激活</strong></div><div class="state"><span>真实来源准入</span><strong class="blocked">0 / 未就绪</strong></div><div class="state"><span>生产签名身份</span><strong class="blocked">未建立</strong></div><div class="state"><span>真实前瞻观测</span><strong>0</strong></div><div class="state"><span>独立 Validation</span><strong>未开始</strong></div><p class="muted">CNEquity · 重建等权申万一级行业相对收益<br>历史数据截止：2026-09-29<br>旧访问隔离：NOT_CERTIFIED<br>V1 / V2：FAILED_VALIDATION<br>Final OOS：未开启</p></section></div>
<div class="grid"><section><h2>历史基线比较</h2><div class="scroll"><table><thead><tr><th>固定规格</th><th>H5 平均 RankIC</th><th>H10 平均 RankIC</th></tr></thead><tbody>{"".join(comparisons)}</tbody></table></div><p class="muted">本次固定规格 Ridge 未增加有效信息。等权 / 零横截面评分的 RankIC 未定义。</p></section><section><h2>REV10 四个时间块</h2><div class="scroll"><table><thead><tr><th>时间块</th><th>H5</th><th>H10</th></tr></thead><tbody>{"".join(blocks)}</tbody></table></div><p class="muted">后期 H5 明显减弱，不能将全样本正值解释为稳定预测能力。</p></section></div>
<section><h2>原始六张研究图</h2><div class="charts">{chart_html}</div></section><section><h2>稳定性与局限</h2><ul><li>逐一排除 30 个行业仍保留正向全样本均值；共同因素和联合偏差未排除。</li><li>样本重叠、行业相关，描述性块分析不构成独立验证。</li><li>当前分类重建未认证历史 PIT，生存偏差及复权约定未认证。</li><li>原始收益差不代表可执行净利润，机制仍未识别。</li><li>本次授权不等于供应商许可证或生产准入。</li></ul></section>
<details><summary>查看正式研究草案 · 尚未激活</summary><pre style="white-space:pre-wrap;line-height:1.7">{draft}</pre></details><section><h2>研究证据与下一步</h2><p>历史指标和图表直接读取经核验的 PR36 报告，无重复事实来源。后续需要来源权利、PIT/质量、生产身份、统计设计与单独正式授权。</p><a href="https://github.com/WynterYaxley123/quant-trading/pull/36">PR #36 历史研究</a><p class="muted">本离线成果无需 API、外部 CDN 或下载脚本。来源与文件哈希见同目录 delivery-manifest.json。</p><code>模型 hash：{model_hash}</code></section></main><footer>只读研究成果 · 不提供交易功能 · 独立未来验证尚未开始</footer>
<script>document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{{document.querySelectorAll('[data-filter]').forEach(other=>other.setAttribute('aria-pressed',String(other===button)));const rows=[...document.querySelectorAll('#ranking tbody tr')];rows.sort((a,b)=>button.dataset.filter==='bottom'?Number(b.cells[0].textContent)-Number(a.cells[0].textContent):Number(a.cells[0].textContent)-Number(b.cells[0].textContent));rows.forEach(row=>{{row.hidden=button.dataset.filter!=='all'&&row.dataset[button.dataset.filter]!=='true';row.parentElement.appendChild(row);}});}}));</script></body></html>"""
    (output / "index.html").write_text(html, encoding="utf-8")
    result = {
        "schema_version": 1,
        "classification": "EXPLORATORY_POST_HOC",
        "private_local_only": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "model_hash": model_hash,
        "historical_asof": ranking["asof"] if ranking else None,
        "ranking_count": 30 if ranking else 0,
        "preview_manifest_sha256": pin if ranking else None,
        "source_sha256": {
            name: sha(contained(root, name))
            for name in (
                *(f"{REPORT_DIR}/{name}" for name in REPORTS),
                "config/research/swl1-rev10-short-v1.json",
                spec["universe_file"],
                "docs/research/swl1-rev10-preregistration-draft.zh-CN.md",
            )
        },
        "files": {
            str(p.relative_to(output)).replace("\\", "/"): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file() and p.name != "delivery-manifest.json"
        },
    }
    write(output / "delivery-manifest.json", result)
    return {
        "status": "PRIVATE_OFFLINE_REVIEW_CREATED",
        "ranking_count": result["ranking_count"],
        "html_sha256": sha(output / "index.html"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--manifest-pin", default="")
    args = parser.parse_args()
    print(json.dumps(build_review(args.root, args.output, args.preview, args.manifest_pin)))


if __name__ == "__main__":
    main()
