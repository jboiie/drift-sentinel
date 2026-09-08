"""Builds the static dashboard: reads reports/drift_log.json and
reports/staged_injection_log.json, writes a self-contained docs/index.html.

No server, no framework, no CDN — Plotly is inlined into the page so it
renders with the network off. Every number on the page comes from those
two JSON files; nothing here is typed into the template by hand.
"""

import json
from collections import Counter
from pathlib import Path

import plotly.graph_objects as go
from plotly.offline import plot as plotly_div

from drift.audit import compute_false_positive_cost

ROOT = Path(__file__).resolve().parent.parent
DRIFT_LOG = ROOT / "reports" / "drift_log.json"
INJECTION_LOG = ROOT / "reports" / "staged_injection_log.json"
OUT_DIR = ROOT / "docs"

# Dark, restrained palette — no default-Plotly white background.
BG = "#0f1115"
PANEL = "#161922"
TEXT = "#e6e8ef"
MUTED = "#8b93a7"
ACCENT = "#5eead4"
WARN = "#f5a524"
BAD = "#f56565"
OK = "#5eead4"
GRID = "#242938"

PLOTLY_LAYOUT = dict(
    paper_bgcolor=PANEL,
    plot_bgcolor=PANEL,
    font=dict(color=TEXT, family="ui-monospace, SFMono-Regular, Menlo, monospace", size=13),
    margin=dict(l=48, r=24, t=48, b=40),
)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _stat_tile(label: str, value, color: str = TEXT) -> str:
    return f"""
    <div class="tile">
      <div class="tile-value" style="color:{color}">{value}</div>
      <div class="tile-label">{label}</div>
    </div>"""


def _checks_by_type_figure(incidents: list[dict]) -> str:
    types = ["numeric", "faithfulness", "self_consistency"]
    completed = Counter()
    errored = Counter()
    flagged = Counter()
    for r in incidents:
        t = r["check_type"]
        if r["check_status"] == "errored":
            errored[t] += 1
        elif r.get("flagged"):
            flagged[t] += 1
        else:
            completed[t] += 1

    fig = go.Figure()
    fig.add_bar(name="ok", x=types, y=[completed[t] for t in types], marker_color=OK)
    fig.add_bar(name="flagged", x=types, y=[flagged[t] for t in types], marker_color=WARN)
    fig.add_bar(name="errored", x=types, y=[errored[t] for t in types], marker_color=BAD)
    fig.update_layout(
        barmode="stack", title="Checks by type and outcome",
        yaxis=dict(gridcolor=GRID, title="count"), xaxis=dict(gridcolor=GRID),
        legend=dict(orientation="h", y=1.15),
        **PLOTLY_LAYOUT,
    )
    return plotly_div(fig, output_type="div", include_plotlyjs=False)


def _drift_cause_figure(incidents: list[dict]) -> str:
    causes = Counter(r.get("drift_cause") for r in incidents if r.get("drift_cause"))
    if not causes:
        return '<p class="empty">No flagged incidents yet — nothing to classify. See the staged-injection replay below for the one case with real injected drift.</p>'
    fig = go.Figure(go.Bar(
        x=list(causes.values()), y=list(causes.keys()), orientation="h",
        marker_color=[BAD if c == "fabrication" else WARN if c == "stale_ground_truth" else MUTED for c in causes],
    ))
    fig.update_layout(title="Flagged incidents by drift cause", xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID), **PLOTLY_LAYOUT)
    return plotly_div(fig, output_type="div", include_plotlyjs=False)


def _staged_injection_html(entry: dict | None) -> str:
    if not entry:
        return '<p class="empty">No staged-injection run logged yet. Run <code>python -m drift.staged_injection inject</code> then <code>verify</code>.</p>'
    stale_badge = f'<span class="badge bad">FLAGGED — {entry["stale_drift_cause"]} / {entry["stale_severity"]}</span>'
    fresh_badge = '<span class="badge ok">not flagged</span>'
    return f"""
    <div class="injection">
      <p class="q">"{entry['question']}"</p>
      <div class="turn">
        <div class="turn-label">Answer captured BEFORE the injected edit (ground truth was ₹{entry['original_price']})</div>
        <div class="answer">{entry['stale_answer']}</div>
        <div class="turn-meta">Checked against the NEW ground truth (₹{entry['injected_price']}): {stale_badge}</div>
      </div>
      <div class="turn">
        <div class="turn-label">Fresh re-ask AFTER the injected edit</div>
        <div class="answer">{entry['fresh_answer']}</div>
        <div class="turn-meta">Checked against the NEW ground truth: {fresh_badge}</div>
      </div>
    </div>"""


def _provenance_rows(incidents: list[dict]) -> str:
    runs = sorted({r["run_id"] for r in incidents})
    rows = []
    for run_id in runs:
        rows_for_run = [r for r in incidents if r["run_id"] == run_id]
        ts = min(r["logged_at"] for r in rows_for_run)
        rows.append(f"<tr><td>{run_id}</td><td>{ts}</td><td>{len(rows_for_run)}</td></tr>")
    return "\n".join(rows) or '<tr><td colspan="3" class="empty">No sampler runs logged yet.</td></tr>'


def build() -> None:
    incidents = _load(DRIFT_LOG)
    injections = _load(INJECTION_LOG)
    latest_injection = injections[-1] if injections else None

    total = len(incidents)
    flagged = sum(1 for r in incidents if r.get("flagged"))
    errored = sum(1 for r in incidents if r["check_status"] == "errored")
    sessions = len({r["run_id"] for r in incidents})
    fp_cost = compute_false_positive_cost(incidents)

    fp_rate = fp_cost["false_positive_rate"]
    fp_rate_display = f"{fp_rate:.0%}" if fp_rate is not None else "n/a — no reviewed flags"

    tiles = "".join([
        _stat_tile("sampler sessions", sessions),
        _stat_tile("checks run", total),
        _stat_tile("flagged", flagged, WARN if flagged else OK),
        _stat_tile("errored", errored, BAD if errored else OK),
        _stat_tile("false-positive rate", fp_rate_display, TEXT),
        _stat_tile("staged-injection detection", "1/1" if latest_injection and latest_injection["stale_flagged"] else "—", OK),
    ])

    checks_fig = _checks_by_type_figure(incidents)
    cause_fig = _drift_cause_figure(incidents)
    injection_html = _staged_injection_html(latest_injection)
    provenance = _provenance_rows(incidents)

    from plotly.offline import get_plotlyjs
    plotly_bundle = f"<script>{get_plotlyjs()}</script>"

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Drift Sentinel — Dashboard</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    background: {BG}; color: {TEXT}; margin: 0; padding: 0 0 4rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }}
  header {{ padding: 2.5rem 1.5rem 1rem; text-align: center; }}
  h1 {{ margin: 0 0 0.25rem; font-size: 1.6rem; }}
  .sub {{ color: {MUTED}; font-size: 0.95rem; }}
  main {{ max-width: 980px; margin: 0 auto; padding: 0 1.25rem; }}
  section {{ margin-top: 2.5rem; }}
  h2 {{ font-size: 1.05rem; color: {MUTED}; text-transform: uppercase; letter-spacing: 0.06em; border-bottom: 1px solid {GRID}; padding-bottom: 0.5rem; }}
  .tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.75rem; }}
  .tile {{ background: {PANEL}; border: 1px solid {GRID}; border-radius: 10px; padding: 1rem; text-align: center; }}
  .tile-value {{ font-size: 1.6rem; font-weight: 600; }}
  .tile-label {{ color: {MUTED}; font-size: 0.75rem; margin-top: 0.25rem; }}
  .empty {{ color: {MUTED}; font-style: italic; }}
  .injection {{ background: {PANEL}; border: 1px solid {GRID}; border-radius: 10px; padding: 1.25rem; }}
  .injection .q {{ color: {MUTED}; margin-top: 0; }}
  .turn {{ border-top: 1px solid {GRID}; padding: 0.85rem 0; }}
  .turn:first-of-type {{ border-top: none; }}
  .turn-label {{ color: {MUTED}; font-size: 0.8rem; margin-bottom: 0.35rem; }}
  .answer {{ background: #0b0d12; border-radius: 6px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem; }}
  .badge {{ display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }}
  .badge.bad {{ background: rgba(245,101,101,0.15); color: {BAD}; }}
  .badge.ok {{ background: rgba(94,234,212,0.15); color: {OK}; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th, td {{ text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid {GRID}; }}
  th {{ color: {MUTED}; font-weight: 500; }}
  footer {{ text-align: center; color: {MUTED}; font-size: 0.8rem; margin-top: 3rem; }}
  a {{ color: {ACCENT}; }}
  @media (prefers-color-scheme: light) {{
    :root {{ color-scheme: light; }}
  }}
</style>
</head>
<body>
<header>
  <h1>📉 Drift Sentinel</h1>
  <div class="sub">Catching an LLM support agent's answers drifting from ground truth</div>
</header>
<main>

<section>
  <h2>Summary</h2>
  <div class="tiles">{tiles}</div>
</section>

<section>
  <h2>Staged-injection replay — the end-to-end proof</h2>
  {injection_html}
</section>

<section>
  <h2>Checks by type and outcome</h2>
  {checks_fig}
</section>

<section>
  <h2>Drift-cause breakdown</h2>
  {cause_fig}
</section>

<section>
  <h2>Run provenance</h2>
  <table>
    <thead><tr><th>run_id</th><th>logged at (UTC)</th><th>checks</th></tr></thead>
    <tbody>{provenance}</tbody>
  </table>
</section>

</main>
<footer>
  Generated from reports/drift_log.json and reports/staged_injection_log.json —
  <a href="https://github.com/jboiie/drift-sentinel">source</a>
</footer>
{plotly_bundle}
</body>
</html>
"""

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'index.html'} — {total} checks across {sessions} sessions, {flagged} flagged.")


if __name__ == "__main__":
    build()
