"""Self-contained HTML scorecard generator for HammerDB-Scale results."""

from __future__ import annotations

import importlib.resources
import json
from datetime import datetime


def _load_chartjs() -> str:
    """Load the embedded Chart.js minified source."""
    ref = importlib.resources.files("hammerdb_scale.reports").joinpath("chartjs.min.js")
    return ref.read_text(encoding="utf-8")


def generate_scorecard(
    summary: dict,
    pure_metrics: dict | None = None,
) -> str:
    """Generate a self-contained HTML scorecard from summary.json data."""
    benchmark = summary.get("benchmark", "tprocc")
    if benchmark == "tproch":
        return _render_tproch(summary, pure_metrics)
    return _render_tprocc(summary, pure_metrics)




_CSS = """\
:root {
  --green: #10b981;
  --green-bg: #ecfdf5;
  --blue: #3b82f6;
  --blue-bg: #eff6ff;
  --orange: #f59e0b;
  --orange-bg: #fffbeb;
  --red: #ef4444;
  --red-bg: #fef2f2;
  --yellow: #eab308;
  --gray-50: #f8fafc;
  --gray-100: #f1f5f9;
  --gray-200: #e2e8f0;
  --gray-600: #475569;
  --gray-700: #334155;
  --gray-800: #1e293b;
  --gray-900: #0f172a;
  --white: #ffffff;
  --shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
  --radius: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--gray-50);
  color: var(--gray-900);
  line-height: 1.5;
}
.header {
  background: var(--gray-800);
  color: var(--white);
  padding: 24px 32px;
}
.header h1 { font-size: 1.5rem; margin-bottom: 4px; }
.header-meta { display: flex; flex-wrap: wrap; gap: 24px; font-size: 0.875rem; opacity: 0.85; margin-top: 8px; }
.header-meta span { white-space: nowrap; }
.content { max-width: 1200px; margin: 0 auto; padding: 24px 32px; }
.banner-warn {
  background: #fef3c7; border: 1px solid #fbbf24; border-radius: var(--radius);
  padding: 12px 16px; margin-bottom: 20px; color: #92400e; font-size: 0.875rem;
}
/* Summary cards */
.cards { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 28px; }
.card {
  flex: 1 1 calc(25% - 12px); max-width: calc(25% - 12px); min-width: 180px; border-radius: var(--radius);
  padding: 20px; color: var(--white); box-shadow: var(--shadow);
}
.card-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.9; }
.card-value { font-size: 2rem; font-weight: 700; margin-top: 4px; font-variant-numeric: tabular-nums; }
.card-green { background: var(--green); }
.card-blue { background: var(--blue); }
.card-orange { background: var(--orange); }
.card-gray { background: var(--gray-600); }
.card-red { background: var(--red); }
/* Tables */
table { width: 100%; border-collapse: collapse; margin-bottom: 28px; font-size: 0.875rem; }
thead { background: var(--gray-800); color: var(--white); }
th { padding: 10px 14px; text-align: left; font-weight: 600; }
td { padding: 10px 14px; border-bottom: 1px solid var(--gray-200); }
tbody tr:nth-child(even) { background: var(--gray-50); }
tbody tr:nth-child(odd) { background: var(--white); }
.num { text-align: right; font-variant-numeric: tabular-nums; font-family: "SF Mono", "Cascadia Code", Consolas, monospace; }
.status-ok { color: var(--green); font-weight: 600; }
.status-fail { color: var(--red); font-weight: 600; }
/* Charts */
.chart-container { background: var(--white); border-radius: var(--radius); box-shadow: var(--shadow); padding: 20px; margin-bottom: 28px; }
.chart-container h3 { font-size: 1rem; margin-bottom: 12px; color: var(--gray-700); }
.chart-container canvas { width: 100% !important; max-height: 400px; }
/* Config */
details { margin-bottom: 28px; }
summary { cursor: pointer; font-weight: 600; font-size: 1rem; color: var(--gray-700); padding: 12px 0; }
details pre { background: var(--gray-100); border-radius: var(--radius); padding: 16px; overflow-x: auto; font-size: 0.8rem; line-height: 1.6; }
/* Footer */
.footer { text-align: center; padding: 20px 32px; font-size: 0.75rem; color: var(--gray-600); border-top: 1px solid var(--gray-200); margin-top: 20px; }
/* Section heading */
.section-title { font-size: 1.1rem; font-weight: 600; color: var(--gray-700); margin-bottom: 12px; }
/* Print */
@media print {
  body { background: white; }
  .header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .card { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  thead { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .content { max-width: none; }
}
"""




def _fmt_number(n: int | float | None) -> str:
    if n is None:
        return "-"
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{n:,}"


def _fmt_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def _escape(text: str) -> str:
    """Minimal HTML escaping."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _latency_card_class(latency_us: float | None) -> str:
    if latency_us is None:
        return "card-gray"
    if latency_us < 500:
        return "card-green"
    if latency_us <= 2000:
        return "card-orange"
    return "card-red"


def _header_html(summary: dict) -> str:
    test_id = summary.get("test_id", "")
    ts = summary.get("timestamp", "")
    name = summary.get("deployment_name", "")
    benchmark = summary.get("benchmark", "")
    cfg = summary.get("config", {})
    db_type = cfg.get("database_type", "")
    target_count = cfg.get("target_count", 0)

    meta_items = [
        f"Test ID: {_escape(test_id)}",
        f"Benchmark: {benchmark.upper()}",
        f"Database: {db_type}",
        f"Targets: {target_count}",
    ]
    if "warehouses" in cfg:
        meta_items.append(f"Warehouses: {_fmt_number(cfg['warehouses'])}")
    if "virtual_users" in cfg:
        meta_items.append(f"VUs: {cfg['virtual_users']}")
    if "rampup_minutes" in cfg:
        meta_items.append(f"Rampup: {cfg['rampup_minutes']}m")
    if "duration_minutes" in cfg:
        meta_items.append(f"Duration: {cfg['duration_minutes']}m")
    if "scale_factor" in cfg:
        meta_items.append(f"Scale Factor: {cfg['scale_factor']}")
    if ts:
        try:
            dt = datetime.fromisoformat(ts)
            meta_items.append(f"Time: {dt.strftime('%Y-%m-%d %H:%M UTC')}")
        except ValueError:
            meta_items.append(f"Time: {ts}")

    meta_spans = "".join(f"<span>{item}</span>" for item in meta_items)

    return f"""<div class="header">
  <h1>HammerDB-Scale Scorecard</h1>
  <div style="font-size: 0.9rem; opacity: 0.9; margin-top: 2px;">{_escape(name)}</div>
  <div class="header-meta">{meta_spans}</div>
</div>"""


def _failure_banner(targets: list[dict]) -> str:
    total = len(targets)
    failed = sum(1 for t in targets if t.get("status") == "failed")
    if failed == 0:
        return ""
    completed = total - failed
    return (
        f'<div class="banner-warn">'
        f"&#9888; {completed} of {total} targets completed successfully. "
        f"{failed} target{'s' if failed > 1 else ''} failed. "
        f"Aggregates reflect completed targets only."
        f"</div>"
    )


def _config_snapshot(summary: dict) -> str:
    cfg = summary.get("config", {})
    lines = json.dumps(cfg, indent=2)
    return f"""<details>
  <summary>Configuration Snapshot</summary>
  <pre>{_escape(lines)}</pre>
</details>"""


def _footer_html(summary: dict) -> str:
    version = summary.get("version", "2.0.0")
    test_id = summary.get("test_id", "")
    ts = summary.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(ts)
        ts_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        ts_fmt = ts
    return (
        f'<div class="footer">'
        f"Generated by HammerDB-Scale {version} | {ts_fmt} | {_escape(test_id)}"
        f"</div>"
    )




def _storage_charts_js(pure_metrics: dict | None) -> str:
    """Generate Chart.js code for storage performance graphs."""
    if not pure_metrics:
        return ""

    samples = pure_metrics.get("raw_metrics", [])
    if not samples:
        return ""

    # Use sample index as label when timestamps are empty
    timestamps = [s.get("timestamp", "") for s in samples]
    if not any(timestamps):
        timestamps = list(range(1, len(samples) + 1))

    read_lat = [s.get("read_latency_us", 0) for s in samples]
    write_lat = [s.get("write_latency_us", 0) for s in samples]
    read_iops = [s.get("read_iops", 0) for s in samples]
    write_iops = [s.get("write_iops", 0) for s in samples]
    read_bw = [round(s.get("read_bandwidth_mbps", 0), 1) for s in samples]
    write_bw = [round(s.get("write_bandwidth_mbps", 0), 1) for s in samples]
    has_bw = any(v > 0 for v in read_bw) or any(v > 0 for v in write_bw)

    html = f"""
<div class="chart-container">
  <h3>Latency Over Time (\u00b5s)</h3>
  <canvas id="latencyChart"></canvas>
</div>
<div class="chart-container">
  <h3>IOPS Over Time</h3>
  <canvas id="iopsChart"></canvas>
</div>"""

    if has_bw:
        html += f"""
<div class="chart-container">
  <h3>Bandwidth Over Time (MB/s)</h3>
  <canvas id="bwChart"></canvas>
</div>"""

    html += f"""
<script>
(function() {{
  const labels = {json.dumps(timestamps)};
  const readLat = {json.dumps(read_lat)};
  const writeLat = {json.dumps(write_lat)};
  const readIops = {json.dumps(read_iops)};
  const writeIops = {json.dumps(write_iops)};
  const tickOpts = {{ maxTicksLimit: 10 }};

  new Chart(document.getElementById('latencyChart'), {{
    type: 'line',
    data: {{
      labels: labels,
      datasets: [
        {{ label: 'Read Latency (\\u00b5s)', data: readLat, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', fill: true, tension: 0.3, pointRadius: 0 }},
        {{ label: 'Write Latency (\\u00b5s)', data: writeLat, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)', fill: true, tension: 0.3, pointRadius: 0 }}
      ]
    }},
    options: {{ responsive: true, scales: {{ x: {{ ticks: tickOpts }}, y: {{ beginAtZero: true }} }} }}
  }});

  new Chart(document.getElementById('iopsChart'), {{
    type: 'line',
    data: {{
      labels: labels,
      datasets: [
        {{ label: 'Read IOPS', data: readIops, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.3)', fill: true, tension: 0.3, pointRadius: 0 }},
        {{ label: 'Write IOPS', data: writeIops, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.3)', fill: true, tension: 0.3, pointRadius: 0 }}
      ]
    }},
    options: {{ responsive: true, scales: {{ x: {{ ticks: tickOpts }}, y: {{ beginAtZero: true }} }} }}
  }});"""

    if has_bw:
        html += f"""

  const readBw = {json.dumps(read_bw)};
  const writeBw = {json.dumps(write_bw)};
  new Chart(document.getElementById('bwChart'), {{
    type: 'line',
    data: {{
      labels: labels,
      datasets: [
        {{ label: 'Read MB/s', data: readBw, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.3)', fill: true, tension: 0.3, pointRadius: 0 }},
        {{ label: 'Write MB/s', data: writeBw, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.3)', fill: true, tension: 0.3, pointRadius: 0 }}
      ]
    }},
    options: {{ responsive: true, scales: {{ x: {{ ticks: tickOpts }}, y: {{ beginAtZero: true }} }} }}
  }});"""

    html += """
})();
</script>"""

    return html




def _storage_section_html(pure_metrics: dict | None) -> str:
    """Render the full Storage Performance section: cards, stats table, and charts."""
    if not pure_metrics:
        return ""

    raw = pure_metrics.get("raw_metrics", [])
    if not raw:
        return ""

    summ = pure_metrics.get("summary", {})

    # Compute from raw if summary is missing (full JSON path has it pre-computed)
    def _from_raw(key: str) -> list:
        return [s.get(key, 0) for s in raw if s.get(key, 0)]

    def _avg(vals: list) -> float:
        return sum(vals) / len(vals) if vals else 0

    w_lat_avg = summ.get("write_latency_us_avg") or _avg(_from_raw("write_latency_us"))
    w_lat_p95 = summ.get("write_latency_us_p95", 0)
    w_lat_p99 = summ.get("write_latency_us_p99", 0)
    r_lat_avg = summ.get("read_latency_us_avg") or _avg(_from_raw("read_latency_us"))
    r_lat_p95 = summ.get("read_latency_us_p95", 0)
    r_lat_p99 = summ.get("read_latency_us_p99", 0)

    w_iops_avg = summ.get("write_iops_avg") or _avg(_from_raw("write_iops"))
    w_iops_max = summ.get("write_iops_max") or max(_from_raw("write_iops") or [0])
    r_iops_avg = summ.get("read_iops_avg") or _avg(_from_raw("read_iops"))
    r_iops_max = summ.get("read_iops_max") or max(_from_raw("read_iops") or [0])

    w_bw_avg = summ.get("write_bandwidth_mbps_avg", 0)
    w_bw_max = summ.get("write_bandwidth_mbps_max", 0)
    r_bw_avg = summ.get("read_bandwidth_mbps_avg", 0)
    r_bw_max = summ.get("read_bandwidth_mbps_max", 0)
    has_bw = w_bw_avg > 0 or r_bw_avg > 0

    avg_r_block = summ.get("avg_read_block_size_kb_avg") or summ.get("avg_read_block_size_kb", 0)
    avg_w_block = summ.get("avg_write_block_size_kb_avg") or summ.get("avg_write_block_size_kb", 0)

    w_lat_class = _latency_card_class(w_lat_avg)
    r_lat_class = _latency_card_class(r_lat_avg)

    # 8 summary cards: write/read pairs for latency, IOPS, BW, block size
    cards = f"""<div class="cards">
  <div class="card {w_lat_class}"><div class="card-label">Avg Write Latency</div><div class="card-value">{w_lat_avg:,.0f} \u00b5s</div></div>
  <div class="card {r_lat_class}"><div class="card-label">Avg Read Latency</div><div class="card-value">{r_lat_avg:,.0f} \u00b5s</div></div>
  <div class="card card-blue"><div class="card-label">Peak Write IOPS</div><div class="card-value">{_fmt_number(int(w_iops_max))}</div></div>
  <div class="card card-blue"><div class="card-label">Peak Read IOPS</div><div class="card-value">{_fmt_number(int(r_iops_max))}</div></div>"""

    if has_bw:
        cards += f"""
  <div class="card card-blue"><div class="card-label">Avg Write BW</div><div class="card-value">{w_bw_avg:,.1f} MB/s</div></div>
  <div class="card card-blue"><div class="card-label">Avg Read BW</div><div class="card-value">{r_bw_avg:,.1f} MB/s</div></div>"""

    if avg_w_block or avg_r_block:
        cards += f"""
  <div class="card card-gray"><div class="card-label">Avg Write Block Size</div><div class="card-value">{avg_w_block:.1f} KB</div></div>
  <div class="card card-gray"><div class="card-label">Avg Read Block Size</div><div class="card-value">{avg_r_block:.1f} KB</div></div>"""

    cards += "\n</div>"

    # Stats table helper
    def _fv(v: float, unit: str = "") -> str:
        """Format a numeric value with optional unit."""
        s = f"{v:,.1f}" if isinstance(v, float) and not v.is_integer() else f"{v:,.0f}"
        return f"{s} {unit}".strip() if unit else s

    # Latency rows (avg / p95 / p99)
    lat_rows = ""
    for label, avg, p95, p99, unit in [
        ("Write Latency", w_lat_avg, w_lat_p95, w_lat_p99, "\u00b5s"),
        ("Read Latency", r_lat_avg, r_lat_p95, r_lat_p99, "\u00b5s"),
    ]:
        if avg or p95 or p99:
            lat_rows += f"<tr><td>{label}</td><td class='num'>{_fv(avg, unit)}</td><td class='num'>{_fv(p95, unit)}</td><td class='num'>{_fv(p99, unit)}</td></tr>"

    lat_table = ""
    if lat_rows:
        lat_table = f"""<table>
  <thead><tr><th>Metric</th><th class="num">Avg</th><th class="num">P95</th><th class="num">P99</th></tr></thead>
  <tbody>{lat_rows}</tbody>
</table>"""

    # Throughput rows (avg / max) — separate table with different headers
    tp_rows = ""
    for label, avg, peak, unit in [
        ("Write IOPS", w_iops_avg, w_iops_max, ""),
        ("Read IOPS", r_iops_avg, r_iops_max, ""),
    ]:
        if avg or peak:
            tp_rows += f"<tr><td>{label}</td><td class='num'>{_fv(avg, unit)}</td><td class='num'>{_fv(peak, unit)}</td></tr>"
    if has_bw:
        for label, avg, peak, unit in [
            ("Write BW", w_bw_avg, w_bw_max, "MB/s"),
            ("Read BW", r_bw_avg, r_bw_max, "MB/s"),
        ]:
            if avg or peak:
                tp_rows += f"<tr><td>{label}</td><td class='num'>{_fv(avg, unit)}</td><td class='num'>{_fv(peak, unit)}</td></tr>"
    if avg_w_block:
        tp_rows += f"<tr><td>Avg Write Block Size</td><td class='num'>{avg_w_block:.1f} KB</td><td></td></tr>"
    if avg_r_block:
        tp_rows += f"<tr><td>Avg Read Block Size</td><td class='num'>{avg_r_block:.1f} KB</td><td></td></tr>"

    tp_table = ""
    if tp_rows:
        tp_table = f"""<table>
  <thead><tr><th>Metric</th><th class="num">Avg</th><th class="num">Max</th></tr></thead>
  <tbody>{tp_rows}</tbody>
</table>"""

    stats_table = lat_table + tp_table

    # Time-series charts
    charts = _storage_charts_js(pure_metrics)

    return f"""<h2 class="section-title">Storage Performance <span style="font-weight:400;font-size:0.85rem;color:var(--gray-600);">({len(raw)} samples)</span></h2>
{cards}
{stats_table}
{charts}"""


def _render_tprocc(summary: dict, pure_metrics: dict | None) -> str:
    targets = summary.get("targets", [])
    agg = summary.get("aggregate", {})
    has_storage = pure_metrics is not None and bool(pure_metrics.get("raw_metrics"))

    total_tpm = agg.get("total_tpm", 0)
    total_nopm = agg.get("total_nopm", 0)
    avg_tpm = agg.get("avg_tpm", 0)
    completed = agg.get("targets_completed", 0)
    avg_nopm = int(total_nopm / completed) if completed else 0

    cards_html = f"""<div class="cards">
  <div class="card card-green"><div class="card-label">Total TPM</div><div class="card-value">{_fmt_number(total_tpm)}</div></div>
  <div class="card card-green"><div class="card-label">Total NOPM</div><div class="card-value">{_fmt_number(total_nopm)}</div></div>
  <div class="card card-blue"><div class="card-label">Avg TPM / Target</div><div class="card-value">{_fmt_number(avg_tpm)}</div></div>
  <div class="card card-blue"><div class="card-label">Avg NOPM / Target</div><div class="card-value">{_fmt_number(avg_nopm)}</div></div>
</div>"""

    # Per-target table
    rows = []
    for t in targets:
        idx = t.get("index", 0)
        name = _escape(t.get("name", ""))
        host = _escape(t.get("host", ""))
        status = t.get("status", "")
        dur = _fmt_duration(t.get("duration_seconds"))
        tprocc = t.get("tprocc", {})
        tpm = _fmt_number(tprocc.get("tpm")) if tprocc else "-"
        nopm = _fmt_number(tprocc.get("nopm")) if tprocc else "-"
        if status == "completed":
            st_html = '<span class="status-ok">&#10003; Completed</span>'
        elif status == "failed":
            st_html = '<span class="status-fail">&#10007; Failed</span>'
        else:
            st_html = _escape(status.title())
        rows.append(
            f"<tr><td class='num'>{idx}</td><td>{name}</td><td>{host}</td>"
            f"<td>{st_html}</td><td>{dur}</td><td class='num'>{tpm}</td><td class='num'>{nopm}</td></tr>"
        )

    table_html = f"""<h2 class="section-title">Per-Target Results</h2>
<table>
  <thead><tr><th>#</th><th>Target</th><th>Host</th><th>Status</th><th>Duration</th><th class="num">TPM</th><th class="num">NOPM</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>"""

    # TPM distribution chart
    target_names = [t.get("name", f"target-{i}") for i, t in enumerate(targets)]
    tpm_values = [
        t.get("tprocc", {}).get("tpm", 0) if t.get("status") == "completed" else 0
        for t in targets
    ]
    bar_colors = [
        "'#ef4444'" if t.get("status") == "failed" else "'#10b981'"
        for t in targets
    ]

    nopm_values = [
        t.get("tprocc", {}).get("nopm", 0) if t.get("status") == "completed" else 0
        for t in targets
    ]

    chart_html = f"""<div class="chart-container">
  <h3>TPM Distribution</h3>
  <canvas id="tpmChart"></canvas>
</div>
<div class="chart-container">
  <h3>NOPM Distribution</h3>
  <canvas id="nopmChart"></canvas>
</div>
<script>
new Chart(document.getElementById('tpmChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(target_names)},
    datasets: [{{
      label: 'TPM',
      data: {json.dumps(tpm_values)},
      backgroundColor: [{', '.join(bar_colors)}],
      borderRadius: 4
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true }} }}
  }}
}});
new Chart(document.getElementById('nopmChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(target_names)},
    datasets: [{{
      label: 'NOPM',
      data: {json.dumps(nopm_values)},
      backgroundColor: [{', '.join(bar_colors)}],
      borderRadius: 4
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true }} }}
  }}
}});
</script>"""

    storage_section = _storage_section_html(pure_metrics) if has_storage else ""

    chartjs_src = _load_chartjs()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HammerDB-Scale Scorecard</title>
<style>{_CSS}</style>
</head>
<body>
{_header_html(summary)}
<div class="content">
{_failure_banner(targets)}
{cards_html}
{table_html}
<script>{chartjs_src}</script>
{chart_html}
{storage_section}
{_config_snapshot(summary)}
</div>
{_footer_html(summary)}
</body>
</html>"""




def _render_tproch(summary: dict, pure_metrics: dict | None) -> str:
    targets = summary.get("targets", [])
    agg = summary.get("aggregate", {})
    cfg = summary.get("config", {})
    has_storage = pure_metrics is not None and bool(pure_metrics.get("raw_metrics"))

    avg_qphh = agg.get("avg_qphh", 0)

    # Compute min/max QphH from individual targets
    qphh_vals = [
        t.get("tproch", {}).get("qphh", 0)
        for t in targets if t.get("status") == "completed" and "tproch" in t
    ]
    min_qphh = min(qphh_vals) if qphh_vals else 0
    max_qphh = max(qphh_vals) if qphh_vals else 0

    cards_html = f"""<div class="cards">
  <div class="card card-green"><div class="card-label">Avg QphH</div><div class="card-value">{_fmt_number(avg_qphh)}</div></div>
  <div class="card card-green"><div class="card-label">Max QphH</div><div class="card-value">{_fmt_number(max_qphh)}</div></div>
  <div class="card card-blue"><div class="card-label">Min QphH</div><div class="card-value">{_fmt_number(min_qphh)}</div></div>
  <div class="card card-gray"><div class="card-label">Queries / Target</div><div class="card-value">{len(agg.get('per_query_avg', []))}</div></div>
</div>"""

    # Per-target table
    rows = []
    for t in targets:
        idx = t.get("index", 0)
        name = _escape(t.get("name", ""))
        host = _escape(t.get("host", ""))
        status = t.get("status", "")
        dur = _fmt_duration(t.get("duration_seconds"))
        tproch = t.get("tproch", {})
        qphh = _fmt_number(tproch.get("qphh")) if tproch else "-"
        if status == "completed":
            st_html = '<span class="status-ok">&#10003; Completed</span>'
        elif status == "failed":
            st_html = '<span class="status-fail">&#10007; Failed</span>'
        else:
            st_html = _escape(status.title())
        rows.append(
            f"<tr><td class='num'>{idx}</td><td>{name}</td><td>{host}</td>"
            f"<td>{st_html}</td><td>{dur}</td><td class='num'>{qphh}</td></tr>"
        )

    table_html = f"""<h2 class="section-title">Per-Target Results</h2>
<table>
  <thead><tr><th>#</th><th>Target</th><th>Host</th><th>Status</th><th>Duration</th><th class="num">QphH</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>"""

    # Per-query timing table
    per_query_avg = agg.get("per_query_avg", [])
    query_rows = []
    query_labels = []
    query_times = []
    for q in per_query_avg:
        qn = q.get("query", 0)
        avg_s = q.get("avg_seconds", 0)
        min_s = q.get("min_seconds", 0)
        max_s = q.get("max_seconds", 0)
        query_rows.append(
            f"<tr><td>Q{qn}</td><td class='num'>{avg_s:.1f}</td>"
            f"<td class='num'>{min_s:.1f}</td><td class='num'>{max_s:.1f}</td></tr>"
        )
        query_labels.append(f"Q{qn}")
        query_times.append(avg_s)

    query_table_html = ""
    if query_rows:
        query_table_html = f"""<h2 class="section-title">Per-Query Timing</h2>
<table>
  <thead><tr><th>Query</th><th class="num">Avg (s)</th><th class="num">Min (s)</th><th class="num">Max (s)</th></tr></thead>
  <tbody>{"".join(query_rows)}</tbody>
</table>"""

    # QphH distribution chart
    target_names = [t.get("name", f"target-{i}") for i, t in enumerate(targets)]
    qphh_values = [
        t.get("tproch", {}).get("qphh", 0) if t.get("status") == "completed" else 0
        for t in targets
    ]
    bar_colors = [
        "'#ef4444'" if t.get("status") == "failed" else "'#10b981'"
        for t in targets
    ]

    dist_chart_html = f"""<div class="chart-container">
  <h3>QphH Distribution</h3>
  <canvas id="qphhChart"></canvas>
</div>
<script>
new Chart(document.getElementById('qphhChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(target_names)},
    datasets: [{{
      label: 'QphH',
      data: {json.dumps(qphh_values)},
      backgroundColor: [{', '.join(bar_colors)}],
      borderRadius: 4
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true }} }}
  }}
}});
</script>"""

    # Per-query bar chart
    query_chart_html = ""
    if query_labels:
        query_chart_html = f"""<div class="chart-container">
  <h3>Average Time per Query</h3>
  <canvas id="queryChart"></canvas>
</div>
<script>
new Chart(document.getElementById('queryChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(query_labels)},
    datasets: [{{
      label: 'Avg Time (s)',
      data: {json.dumps(query_times)},
      backgroundColor: '#3b82f6',
      borderRadius: 4
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true, title: {{ display: true, text: 'Seconds' }} }} }}
  }}
}});
</script>"""

    storage_section = _storage_section_html(pure_metrics) if has_storage else ""

    chartjs_src = _load_chartjs()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HammerDB-Scale Scorecard</title>
<style>{_CSS}</style>
</head>
<body>
{_header_html(summary)}
<div class="content">
{_failure_banner(targets)}
{cards_html}
{table_html}
{query_table_html}
<script>{chartjs_src}</script>
{dist_chart_html}
{query_chart_html}
{storage_section}
{_config_snapshot(summary)}
</div>
{_footer_html(summary)}
</body>
</html>"""
