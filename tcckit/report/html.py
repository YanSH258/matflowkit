"""Small dependency-free HTML renderer for dataset reports."""

from __future__ import annotations

from html import escape


def _value(value) -> str:
    if value is None:
        return "not available"
    if isinstance(value, float):
        return f"{value:.8g}"
    return escape(str(value))


def render_deepmd_report(report: dict, systems: list[dict]) -> str:
    dataset = report["dataset"]
    properties = report["properties"]
    rows = "".join(
        "<tr>" + "".join(
            f"<td>{escape(str(row[key]))}</td>"
            for key in ("system", "frames", "natoms", "elements", "has_energy", "has_force", "has_virial")
        ) + "</tr>"
        for row in systems
    )
    warnings = report["warnings"]
    warning_html = (
        "<ul>" + "".join(f"<li>{escape(item['message'])}</li>" for item in warnings) + "</ul>"
        if warnings else "<p>None.</p>"
    )
    statistic_rows = []
    for name in ("total", "per_atom", "relative_within_composition"):
        values = properties["energy"].get(name)
        if values:
            statistic_rows.append(
                f"<tr><td>{escape(name)}</td>" + "".join(
                    f"<td>{_value(values.get(key))}</td>" for key in ("count", "min", "max", "mean", "std")
                ) + "</tr>"
            )
    force_rows = []
    for name in ("component", "magnitude", "max_atomic_force_per_frame"):
        values = properties["force"].get(name)
        if values:
            force_rows.append(
                f"<tr><td>{escape(name)}</td>" + "".join(
                    f"<td>{_value(values.get(key))}</td>" for key in ("count", "min", "max", "mean", "std")
                ) + "</tr>"
            )
    threshold = properties["force"].get("threshold")
    threshold_text = (
        f"<p>Atomic force magnitudes above {_value(threshold)} eV/Å: "
        f"{properties['force']['atoms_above_threshold']}</p>"
        if threshold is not None else ""
    )
    minimum_distance = report.get("geometry", {}).get("minimum_distance", {})
    distance_rows = "".join(
        f"<tr><td>{escape(pair)}</td><td>{_value(distance)}</td></tr>"
        for pair, distance in minimum_distance.get("by_element_pair", {}).items()
    )
    distance_threshold = minimum_distance.get("threshold")
    distance_threshold_text = (
        f"<p>Frames below {_value(distance_threshold)} Å: "
        f"{minimum_distance.get('frames_below_threshold')}</p>"
        if distance_threshold is not None
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>DeepMD dataset report</title><style>
body{{font-family:Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222;line-height:1.45}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}th,td{{border:1px solid #ccc;padding:.45rem;text-align:left}}
th{{background:#f2f2f2}}img{{max-width:100%;height:auto;border:1px solid #ddd}}code{{background:#f4f4f4;padding:.1rem .25rem}}
</style></head><body>
<h1>DeepMD dataset report</h1>
<p>Source: <code>{escape(dataset['path'])}</code></p>
<p>{dataset['systems']} systems, {dataset['frames']} frames; elements: {escape(', '.join(dataset['elements']))}</p>
<p><a href="report.json">report.json</a> · <a href="systems.csv">systems.csv</a> · <a href="duplicates.csv">duplicates.csv</a></p>
<h2>Systems</h2><table><thead><tr><th>system</th><th>frames</th><th>natoms</th><th>elements</th><th>energy</th><th>force</th><th>virial</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Energy statistics (eV)</h2><table><thead><tr><th>quantity</th><th>count</th><th>min</th><th>max</th><th>mean</th><th>std</th></tr></thead><tbody>{''.join(statistic_rows)}</tbody></table>
<h2>Force statistics (eV/Å)</h2><table><thead><tr><th>quantity</th><th>count</th><th>min</th><th>max</th><th>mean</th><th>std</th></tr></thead><tbody>{''.join(force_rows)}</tbody></table>{threshold_text}
<h2>Minimum interatomic distance</h2>
<p>Overall minimum: {_value(minimum_distance.get('overall'))} Å.</p>{distance_threshold_text}
<table><thead><tr><th>element pair</th><th>minimum distance (Å)</th></tr></thead><tbody>{distance_rows}</tbody></table>
<h2>Figures</h2>
<h3>Energy per atom</h3><a href="figures/energy_per_atom_distribution.png"><img src="figures/energy_per_atom_distribution.png" alt="Energy per atom distribution"></a>
<h3>Forces</h3><a href="figures/force_distribution.png"><img src="figures/force_distribution.png" alt="Force distributions"></a>
<h3>Composition</h3><a href="figures/composition.png"><img src="figures/composition.png" alt="Composition distribution"></a>
<h2>Exact normalized duplicates</h2><p>{report['duplicates']['groups']} groups; {report['duplicates']['duplicate_frames']} redundant frames. Rounding: {report['duplicates']['normalization']['decimals']} decimals.</p>
<h2>Warnings</h2>{warning_html}
</body></html>"""


def render_abacus_report(report: dict) -> str:
    summary = report["summary"]
    job_rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{_value(row.get(key))}</td>"
            for key in (
                "task",
                "calculation",
                "basis_type",
                "status",
                "ionic_steps",
                "final_energy_eV",
                "maximum_force_eV_A",
                "detail",
            )
        )
        + "</tr>"
        for row in report["jobs"]
    )
    warning_html = (
        "<ul>"
        + "".join(f"<li>{escape(item['message'])}</li>" for item in report["warnings"])
        + "</ul>"
        if report["warnings"]
        else "<p>无。</p>"
    )
    calculation_text = "，".join(
        f"{escape(name)} {count}" for name, count in summary["calculations"].items()
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>ABACUS 任务报告</title><style>
body{{font-family:Arial,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#222;line-height:1.45}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}th,td{{border:1px solid #ccc;padding:.45rem;text-align:left}}
th{{background:#f2f2f2}}img{{max-width:100%;height:auto;border:1px solid #ddd}}code{{background:#f4f4f4;padding:.1rem .25rem}}
</style></head><body>
<h1>ABACUS 任务报告</h1>
<p>任务目录：<code>{escape(report['root'])}</code></p>
<p>共 {summary['tasks']} 个任务；PASS {summary['pass']}；未完成 {summary['incomplete']}。{calculation_text}</p>
<p><a href="report.json">report.json</a> · <a href="jobs.csv">jobs.csv</a> · <a href="failed_jobs.csv">failed_jobs.csv</a></p>
<h2>任务状态</h2><a href="figures/task_status.png"><img src="figures/task_status.png" alt="任务状态统计"></a>
<h2>Relax 指标</h2><a href="figures/relax_metrics.png"><img src="figures/relax_metrics.png" alt="Relax 离子步和最终最大力"></a>
<h2>逐任务结果</h2>
<table><thead><tr><th>任务</th><th>类型</th><th>基组</th><th>状态</th><th>离子步</th><th>最终能量 (eV)</th><th>最终最大力 (eV/Å)</th><th>说明</th></tr></thead><tbody>{job_rows}</tbody></table>
<h2>事实提示</h2>{warning_html}
</body></html>"""
