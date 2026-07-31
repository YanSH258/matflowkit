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
<h2>Figures</h2>
<h3>Energy per atom</h3><a href="figures/energy_per_atom_distribution.png"><img src="figures/energy_per_atom_distribution.png" alt="Energy per atom distribution"></a>
<h3>Forces</h3><a href="figures/force_distribution.png"><img src="figures/force_distribution.png" alt="Force distributions"></a>
<h3>Composition</h3><a href="figures/composition.png"><img src="figures/composition.png" alt="Composition distribution"></a>
<h2>Exact normalized duplicates</h2><p>{report['duplicates']['groups']} groups; {report['duplicates']['duplicate_frames']} redundant frames. Rounding: {report['duplicates']['normalization']['decimals']} decimals.</p>
<h2>Warnings</h2>{warning_html}
</body></html>"""
