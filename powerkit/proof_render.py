"""Deterministic, offline-safe HTML renderer for PowerKit proof manifests."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any, Iterable

from powerkit.proof import STATUS_LABELS, validated_bundle_artifact_path


STATUS_CLASS = {
    "IMPLEMENTED": "neutral",
    "PARTIALLY_VERIFIED": "warn",
    "VERIFIED": "success",
    "VERIFIED_WITH_CAVEATS": "warn",
    "FAILED_VERIFICATION": "danger",
    "UNABLE_TO_VERIFY": "neutral",
}
EMBEDDABLE_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def items(values: Iterable[object], *, css_class: str = "clean-list") -> str:
    rendered = "".join(f"<li>{e(value)}</li>" for value in values if str(value).strip())
    return f'<ul class="{css_class}">{rendered}</ul>' if rendered else ""


def section(title: str, body: str) -> str:
    return f'<section><h2>{e(title)}</h2>{body}</section>' if body.strip() else ""


def status_text(value: object) -> str:
    text = str(value).replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def artifact_image(proof_dir: Path, artifact: dict[str, Any]) -> str:
    if artifact.get("status") != "available":
        return f'<div class="evidence-missing">{e(status_text(artifact.get("status", "missing")))}</div>'
    media_type = artifact.get("media_type")
    stored_path = artifact.get("stored_path")
    if media_type not in EMBEDDABLE_IMAGE_TYPES or not isinstance(stored_path, str):
        return f'<div class="evidence-file">Evidence file: {e(artifact.get("label", "Artifact"))}</div>'
    try:
        path = validated_bundle_artifact_path(proof_dir, artifact)
    except RuntimeError:
        return '<div class="evidence-missing">Artifact unavailable: integrity check failed</div>'
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f'<figure><img src="data:{e(media_type)};base64,{encoded}" '
        f'alt="{e(artifact.get("alt", artifact.get("label", "Evidence")))}">'
        f'<figcaption>{e(artifact.get("caption") or artifact.get("label", ""))}</figcaption></figure>'
    )


def render_feature(module: dict[str, Any]) -> str:
    body = ""
    if module.get("capability"):
        body += f'<p class="lede-small">{e(module["capability"])}</p>'
    if module.get("experience_change"):
        body += f'<p>{e(module["experience_change"])}</p>'
    before = module.get("before", [])
    after = module.get("after", [])
    if isinstance(before, list) and isinstance(after, list) and (before or after):
        body += (
            '<div class="comparison"><div><h3>Before</h3>'
            + items(before)
            + '</div><div><h3>After</h3>'
            + items(after)
            + "</div></div>"
        )
    return section("Capability", body)


def render_bug(module: dict[str, Any]) -> str:
    steps = (
        ("What was broken", "symptom"),
        ("Contributing condition", "contributing_condition"),
        ("Root cause", "root_cause"),
        ("What changed", "fix"),
        ("Why the fix addresses it", "causal_link"),
        ("Regression proof", "regression_proof"),
    )
    cards = ""
    for title, key in steps:
        if module.get(key):
            cards += f'<div class="cause-step"><h3>{e(title)}</h3><p>{e(module[key])}</p></div>'
    return section("Root cause and fix", f'<div class="causal-chain">{cards}</div>' if cards else "")


def render_ui(
    module: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    proof_dir: Path,
) -> str:
    body = ""
    before_id = module.get("before_artifact")
    after_id = module.get("after_artifact")
    if before_id or after_id:
        panels = ""
        for label, artifact_id in (("Before", before_id), ("After", after_id)):
            if artifact_id and artifact_id in artifacts:
                content = artifact_image(proof_dir, artifacts[artifact_id])
            else:
                content = '<div class="evidence-missing">Not captured</div>'
            panels += f'<div><h3>{label}</h3>{content}</div>'
        body += f'<div class="comparison visual">{panels}</div>'
    states = module.get("states", [])
    if isinstance(states, list) and states:
        rows = ""
        for state in states:
            if not isinstance(state, dict):
                continue
            state_status = str(state.get("evidence_status", "not_verified")).lower()
            symbol = "✓" if state_status == "verified" else "—"
            rows += (
                f'<li><span class="state-symbol">{symbol}</span>'
                f'<strong>{e(state.get("name", "State"))}</strong>'
                f'<span>{e(status_text(state_status))}</span></li>'
            )
        body += f'<ul class="state-list">{rows}</ul>'
    if module.get("limitation"):
        body += f'<p class="callout warn"><strong>Visual limitation:</strong> {e(module["limitation"])}</p>'
    return section("Visual evidence", body)


def render_architecture(module: dict[str, Any]) -> str:
    before = module.get("before")
    after = module.get("after")
    body = ""
    if before or after:
        body += '<div class="comparison">'
        for label, value in (("Before", before), ("After", after)):
            content = items(value) if isinstance(value, list) else f'<pre>{e(value or "Not documented")}</pre>'
            body += f'<div><h3>{label}</h3>{content}</div>'
        body += "</div>"
    reasons = module.get("why", [])
    if isinstance(reasons, list) and reasons:
        body += f'<h3>Why this approach</h3>{items(reasons[:5])}'
    return section("Architecture", body)


def render_migration(module: dict[str, Any]) -> str:
    rows = ""
    for label, key in (
        ("Old state", "old_state"),
        ("New state", "new_state"),
        ("Compatibility", "compatibility"),
        ("Migration sequence", "sequence"),
        ("Rollback", "rollback"),
    ):
        value = module.get(key)
        if not value:
            continue
        rendered = items(value) if isinstance(value, list) else e(value)
        rows += f'<div class="fact-row"><dt>{e(label)}</dt><dd>{rendered}</dd></div>'
    checks = module.get("checks", [])
    if isinstance(checks, list) and checks:
        check_rows = "".join(
            f'<tr><th>{e(item.get("name", "Check"))}</th><td>{e(status_text(item.get("evidence_status", "not verified")))}</td></tr>'
            for item in checks
            if isinstance(item, dict)
        )
        rows += f'<table><tbody>{check_rows}</tbody></table>'
    return section("Migration and rollback", f'<dl class="facts">{rows}</dl>' if rows else "")


def render_security(module: dict[str, Any]) -> str:
    controls = module.get("controls", [])
    body = items(controls) if isinstance(controls, list) else ""
    if module.get("previous_exposure") or module.get("residual_risk"):
        body += '<dl class="facts compact">'
        for label, key in (
            ("Previous exposure", "previous_exposure"),
            ("Residual risk", "residual_risk"),
        ):
            if module.get(key):
                body += f'<div class="fact-row"><dt>{label}</dt><dd>{e(module[key])}</dd></div>'
        body += "</dl>"
    return section("Security result", body)


def render_performance(module: dict[str, Any]) -> str:
    measurements = module.get("measurements", [])
    if not isinstance(measurements, list) or not measurements:
        return ""
    rows = ""
    for item in measurements:
        if isinstance(item, dict):
            rows += (
                f'<tr><th>{e(item.get("scenario", "Scenario"))}</th>'
                f'<td>{e(item.get("before", "Not measured"))}</td>'
                f'<td>{e(item.get("after", "Not measured"))}</td>'
                f'<td>{e(item.get("change", ""))}</td>'
                f'<td>{e(status_text(item.get("evidence_status", "not verified")))}</td></tr>'
            )
    body = (
        '<div class="table-wrap"><table><thead><tr><th>Scenario</th><th>Before</th>'
        f'<th>After</th><th>Change</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )
    context = [
        f"Environment: {module['environment']}" if module.get("environment") else "",
        f"Workload: {module['workload']}" if module.get("workload") else "",
        f"Sample: {module['sample_size']}" if module.get("sample_size") else "",
    ]
    return section("Measurements", body + items(context, css_class="metadata-list"))


def render_dependency(module: dict[str, Any]) -> str:
    body = f'<p class="decision">{e(module["decision"])}</p>' if module.get("decision") else ""
    reasons = module.get("why", [])
    if isinstance(reasons, list) and reasons:
        body += f'<h3>Why</h3>{items(reasons)}'
    if module.get("recommended_path"):
        body += f'<h3>Recommended path</h3><p>{e(module["recommended_path"])}</p>'
    return section("Decision", body)


def render_review(module: dict[str, Any]) -> str:
    body = ""
    criteria = module.get("criteria", [])
    if isinstance(criteria, list):
        rows = "".join(
            f'<li><strong>{e(item.get("name", "Criterion"))}</strong><span>{e(status_text(item.get("evidence_status", "not verified")))}</span></li>'
            for item in criteria
            if isinstance(item, dict)
        )
        body += f'<ul class="state-list">{rows}</ul>' if rows else ""
    if module.get("verdict"):
        body += f'<p class="decision">{e(module["verdict"])}</p>'
    return section("Merge readiness", body)


def render_refactor(module: dict[str, Any]) -> str:
    values = []
    for label, key in (
        ("Behavior preserved", "behavior_preserved"),
        ("Structural improvement", "structural_improvement"),
        ("Deleted complexity", "deleted_complexity"),
        ("Compatibility", "compatibility"),
    ):
        if module.get(key):
            values.append(f"{label}: {module[key]}")
    return section("Refactor result", items(values))


def render_modules(proof: dict[str, Any], proof_dir: Path) -> str:
    modules = proof.get("modules", {})
    if not isinstance(modules, dict):
        return ""
    artifacts = {
        item.get("id"): item
        for item in proof.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    output = ""
    for task_type in proof["task"]["types"]:
        module = modules.get(task_type)
        if not isinstance(module, dict):
            continue
        if task_type == "feature":
            output += render_feature(module)
        elif task_type == "bug":
            output += render_bug(module)
        elif task_type == "ui":
            output += render_ui(module, artifacts, proof_dir)
        elif task_type == "architecture":
            output += render_architecture(module)
        elif task_type in {"migration", "database"}:
            output += render_migration(module)
        elif task_type == "security":
            output += render_security(module)
        elif task_type == "performance":
            output += render_performance(module)
        elif task_type == "dependency":
            output += render_dependency(module)
        elif task_type == "review":
            output += render_review(module)
        elif task_type == "refactor":
            output += render_refactor(module)
        elif task_type == "general" and isinstance(module.get("notes"), list):
            output += section("Notes", items(module["notes"]))
    return output


def render_scope(proof: dict[str, Any]) -> str:
    scope = proof.get("scope", {})
    blocks = ""
    if isinstance(scope, dict):
        for title, key in (
            ("What you asked for", "requested"),
            ("What was delivered", "delivered"),
            ("Not included", "not_included"),
        ):
            values = scope.get(key, [])
            if isinstance(values, list) and values:
                blocks += f'<div><h3>{e(title)}</h3>{items(values)}</div>'
    return section("Scope", f'<div class="scope-grid">{blocks}</div>' if blocks else "")


def render_understand(proof: dict[str, Any]) -> str:
    cards = ""
    for item in proof.get("understand", []):
        if not isinstance(item, dict) or not item.get("name"):
            continue
        cards += (
            '<article class="orientation-card">'
            f'<h3>{e(item["name"])}</h3><p>{e(item.get("responsibility", ""))}</p>'
        )
        if item.get("maintenance_note"):
            cards += f'<p class="maintenance">{e(item["maintenance_note"])}</p>'
        cards += "</article>"
    return section("Understand the change", f'<div class="orientation-grid">{cards}</div>' if cards else "")


def render_verification(proof: dict[str, Any]) -> str:
    summary = ""
    details = ""
    for record in proof.get("verification", []):
        if not isinstance(record, dict):
            continue
        state = record.get("status", "unknown")
        symbol = "✓" if state == "passed" else ("✗" if state in {"failed", "timed_out"} else "—")
        summary += (
            f'<li><span class="state-symbol">{symbol}</span>'
            f'<strong>{e(record.get("label", "Check"))}</strong>'
            f'<span>{e(status_text(state))}</span></li>'
        )
        detail = f"{record.get('level', 'unknown')} · {status_text(state)}"
        if record.get("exit_code") is not None:
            detail += f" · exit {record['exit_code']}"
        if record.get("duration_seconds") is not None:
            detail += f" · {record['duration_seconds']}s"
        details += (
            f'<div class="command"><p>{e(detail)}</p>'
            f'<code>{e(record.get("command") or "No command configured")}</code>'
        )
        if record.get("reason"):
            details += f'<p>{e(record["reason"])}</p>'
        details += "</div>"
    body = f'<ul class="state-list">{summary}</ul>' if summary else '<p>No verification evidence was recorded.</p>'
    if details:
        body += f'<details><summary>Show exact commands and results</summary><div class="details-body">{details}</div></details>'
    return section("What was verified", body)


def render_preserved_risks(proof: dict[str, Any]) -> str:
    output = ""
    scope = proof.get("scope", {})
    preserved = scope.get("preserved", []) if isinstance(scope, dict) else []
    if isinstance(preserved, list) and preserved:
        output += section("What did not change", items(preserved))
    body = ""
    caveats = proof.get("caveats", [])
    if isinstance(caveats, list) and caveats:
        body += f'<h3>Caveats</h3>{items(caveats)}'
    risk = proof.get("risk", {})
    risks = risk.get("items", []) if isinstance(risk, dict) else []
    if isinstance(risks, list) and risks:
        body += '<div class="risk-list">'
        for item in risks:
            if isinstance(item, dict):
                body += (
                    '<article class="risk-item">'
                    f'<span class="severity">{e(item.get("severity", "unspecified"))}</span>'
                    f'<h3>{e(item.get("summary", "Risk"))}</h3>'
                    f'<p>{e(item.get("mitigation", ""))}</p></article>'
                )
        body += "</div>"
    return output + section("Risks and caveats", body)


def render_raw_evidence(proof: dict[str, Any]) -> str:
    body = ""
    changes = proof.get("changes", [])
    if changes:
        rows = "".join(
            f'<tr><th><code>{e(item.get("path", ""))}</code></th><td>{e(item.get("change_type", ""))}</td><td>{e(item.get("summary", ""))}</td></tr>'
            for item in changes
            if isinstance(item, dict)
        )
        body += f'<h3>Changed files</h3><div class="table-wrap"><table><tbody>{rows}</tbody></table></div>'
    artifacts = proof.get("artifacts", [])
    if artifacts:
        rows = "".join(
            f'<tr><th>{e(item.get("label", "Artifact"))}</th><td>{e(item.get("kind", ""))}</td><td>{e(status_text(item.get("status", "")))}</td><td><code>{e(item.get("sha256") or "Not available")}</code></td></tr>'
            for item in artifacts
            if isinstance(item, dict)
        )
        body += f'<h3>Artifacts</h3><div class="table-wrap"><table><tbody>{rows}</tbody></table></div>'
    snapshot = proof.get("source_snapshot", {})
    if isinstance(snapshot, dict):
        body += f'<p class="digest">Source snapshot: <code>{e(snapshot.get("digest", "Unavailable"))}</code></p>'
    return section(
        "Evidence",
        f'<details><summary>Show files, artifacts, and source snapshot</summary><div class="details-body">{body}</div></details>' if body else "",
    )


REPORT_CSS = r"""
:root{color-scheme:light dark;--bg:#f4f1ea;--surface:#fffdfa;--ink:#20201d;--muted:#69675f;--line:#d8d2c7;--accent:#285b4c;--accent-soft:#e3eee9;--warn:#8a5a13;--warn-soft:#fbefd8;--danger:#9c382e;--danger-soft:#f8e4e1;--neutral:#5d625f;--shadow:0 18px 48px rgba(44,39,31,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{width:min(1080px,calc(100% - 32px));margin:36px auto 80px}.hero,section{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}.hero{padding:clamp(28px,5vw,56px)}.eyebrow{margin:0 0 12px;text-transform:uppercase;letter-spacing:.14em;font-size:.76rem;font-weight:750;color:var(--muted)}h1{font:700 clamp(2rem,6vw,4.35rem)/.98 ui-serif,Georgia,serif;letter-spacing:-.035em;margin:0;max-width:850px}.summary{font-size:clamp(1.05rem,2vw,1.32rem);max-width:760px;color:var(--muted);margin:24px 0 0}.status-row{display:flex;flex-wrap:wrap;gap:10px;margin:26px 0 0}.chip{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:8px 13px;font-weight:700;font-size:.9rem}.chip.success{color:var(--accent);background:var(--accent-soft)}.chip.warn{color:var(--warn);background:var(--warn-soft)}.chip.danger{color:var(--danger);background:var(--danger-soft)}.chip.neutral{color:var(--neutral)}.stale{margin:20px 0 0;padding:14px 16px;border:1px solid #e6cb97;border-radius:12px;background:var(--warn-soft);color:var(--warn)}section{padding:clamp(22px,4vw,38px);margin-top:18px}h2{font:700 clamp(1.35rem,3vw,2rem)/1.15 ui-serif,Georgia,serif;margin:0 0 18px}h3{font-size:.92rem;text-transform:uppercase;letter-spacing:.075em;margin:18px 0 8px;color:var(--muted)}p{margin:8px 0}.lede-small{font-size:1.2rem}.clean-list{padding:0;margin:8px 0;list-style:none}.clean-list li{position:relative;padding:5px 0 5px 22px}.clean-list li:before{content:"";position:absolute;left:2px;top:.82em;width:7px;height:7px;border-radius:50%;background:var(--accent)}.comparison,.scope-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.comparison>div,.scope-grid>div,.orientation-card,.cause-step,.risk-item{border:1px solid var(--line);border-radius:14px;padding:18px}.visual figure{margin:0}.visual img{display:block;width:100%;height:auto;border-radius:9px;border:1px solid var(--line)}figcaption{font-size:.86rem;color:var(--muted);margin-top:8px}.evidence-missing,.evidence-file{display:grid;min-height:180px;place-items:center;border:1px dashed var(--line);border-radius:9px;color:var(--muted);text-align:center;padding:18px}.state-list{list-style:none;padding:0;margin:10px 0}.state-list li{display:grid;grid-template-columns:26px 1fr auto;gap:10px;align-items:center;padding:11px 0;border-bottom:1px solid var(--line)}.state-symbol{font-weight:800;color:var(--accent)}.callout{padding:14px 16px;border-radius:10px}.callout.warn{background:var(--warn-soft);color:var(--warn)}.causal-chain{display:grid;gap:10px}.orientation-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}.orientation-card h3{color:var(--ink);margin-top:0}.maintenance{color:var(--accent);font-weight:650}.facts{margin:0}.fact-row{display:grid;grid-template-columns:minmax(140px,.35fr) 1fr;gap:18px;padding:13px 0;border-bottom:1px solid var(--line)}dt{font-weight:700}dd{margin:0}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{text-align:left;vertical-align:top;padding:11px;border-bottom:1px solid var(--line)}.decision{font:700 1.35rem/1.35 ui-serif,Georgia,serif;color:var(--accent)}.metadata-list{display:flex;gap:16px;flex-wrap:wrap;list-style:none;padding:0;color:var(--muted)}.risk-list{display:grid;gap:12px}.severity{font-size:.74rem;text-transform:uppercase;letter-spacing:.1em;font-weight:800;color:var(--warn)}details{margin-top:16px;border-top:1px solid var(--line);padding-top:14px}summary{cursor:pointer;font-weight:750;color:var(--accent)}summary:focus-visible{outline:3px solid #6ea38f;outline-offset:4px}.details-body{padding:14px 0}.command{padding:12px 0;border-bottom:1px solid var(--line)}code,pre{font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;padding:16px;border-radius:10px;background:var(--bg)}.digest{color:var(--muted);font-size:.85rem}footer{padding:28px 8px;color:var(--muted);font-size:.84rem}.skip-link{position:absolute;left:-9999px}.skip-link:focus{left:16px;top:16px;z-index:5;background:var(--surface);padding:10px;border:2px solid var(--accent)}
@media(max-width:720px){main{width:min(100% - 20px,1080px);margin-top:10px}.comparison,.scope-grid{grid-template-columns:1fr}.fact-row{grid-template-columns:1fr;gap:4px}.hero,section{border-radius:14px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media(prefers-color-scheme:dark){:root{--bg:#171816;--surface:#20221f;--ink:#f3f0e8;--muted:#b9b5aa;--line:#41443e;--accent:#9bd4bd;--accent-soft:#1e3a30;--warn:#f0c575;--warn-soft:#3c2d16;--danger:#f19a91;--danger-soft:#45231f;--neutral:#c2c7c2;--shadow:none}}
@media print{body{background:#fff;color:#000}main{width:100%;margin:0}.hero,section{box-shadow:none;break-inside:avoid}details>*{display:block!important}summary{display:none}}
"""


def render_html_report(
    proof: dict[str, Any], proof_dir: Path, freshness: dict[str, Any]
) -> str:
    task = proof["task"]
    outcome = proof["outcome"]
    verification = proof.get("verification", [])
    passed = sum(isinstance(record, dict) and record.get("status") == "passed" for record in verification)
    failed = sum(
        isinstance(record, dict) and record.get("status") in {"failed", "timed_out"}
        for record in verification
    )
    chips = (
        f'<span class="chip {STATUS_CLASS[outcome["status"]]}">{e(STATUS_LABELS[outcome["status"]])}</span>'
        f'<span class="chip neutral">{passed} check{"s" if passed != 1 else ""} passed</span>'
    )
    if failed:
        chips += f'<span class="chip danger">{failed} check{"s" if failed != 1 else ""} failed</span>'
    if proof.get("changes"):
        count = len(proof["changes"])
        chips += f'<span class="chip neutral">{count} changed file{"s" if count != 1 else ""}</span>'
    stale = ""
    if freshness.get("status") == "stale":
        count = len(freshness.get("changed_files", []))
        stale = (
            '<p class="stale"><strong>This proof no longer matches the current code.</strong> '
            f'{count} recorded source file{"s have" if count != 1 else " has"} changed.</p>'
        )
    independent = proof.get("independent_verification", {})
    independent_section = ""
    if isinstance(independent, dict) and independent.get("status") == "available":
        independent_section = section(
            "Independent verification",
            f'<p class="decision">{e(status_text(independent.get("verdict")))}</p>'
            f'<p>{e(independent.get("summary", ""))}</p>',
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{e(task['title'])} · PowerKit Proof</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<a class="skip-link" href="#report-content">Skip to report</a>
<main id="report-content">
<header class="hero">
<p class="eyebrow">{e(' + '.join(task['types']))} · {e(task['depth'].replace('_', ' ').title())} proof</p>
<h1>{e(task['title'])}</h1>
<p class="summary">{e(task['summary'])}</p>
<div class="status-row" aria-label="Outcome summary">{chips}</div>
{stale}
</header>
{render_scope(proof)}
{render_modules(proof, proof_dir)}
{render_understand(proof)}
{render_verification(proof)}
{independent_section}
{render_preserved_risks(proof)}
{render_raw_evidence(proof)}
<footer>Generated locally by PowerKit. No command output, environment values, or prompt history is stored by default.</footer>
</main>
</body>
</html>
"""
