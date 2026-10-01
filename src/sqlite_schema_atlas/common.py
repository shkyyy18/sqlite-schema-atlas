"""Local-only output helpers. Never execute inputs or make network calls."""

import argparse
import html
import json
import math
from pathlib import Path
import sys

MAX_INPUT = 8 * 1024 * 1024


def read_bytes(path, limit=MAX_INPUT):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("Input must be a regular non-symlink file")
    with p.open("rb") as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input exceeds size limit")
    return data


def text(path):
    return read_bytes(path).decode("utf-8-sig")


def load_json(value):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("Duplicate JSON key")
            result[k] = v
        return result

    def constant(_):
        raise ValueError("Non-finite JSON number")

    data = json.loads(value, object_pairs_hook=pairs, parse_constant=constant)
    stack = [(data, 0)]
    count = 0
    while stack:
        obj, depth = stack.pop()
        count += 1
        if depth > 50 or count > 300000:
            raise ValueError("JSON exceeds complexity limit")
        if isinstance(obj, float) and not math.isfinite(obj):
            raise ValueError("Non-finite JSON number")
        if isinstance(obj, dict):
            stack.extend((x, depth + 1) for x in obj.values())
        elif isinstance(obj, list):
            stack.extend((x, depth + 1) for x in obj)
    return data


def display(value):
    return html.escape(
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    )


def render(report, title):
    sections = []
    summary = []
    for name, data in report.items():
        if not isinstance(data, (list, dict)) and name != "boundary":
            summary.append("<div><span>" + display(name.replace("_", " ")) + "</span><strong>" + display(data) + "</strong></div>")
            continue
        if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
            keys = list(dict.fromkeys(k for row in data for k in row))
            head = "".join("<th>" + display(k) + "</th>" for k in keys)
            rows = "".join(
                "<tr>"
                + "".join("<td>" + display(row.get(k, "")) + "</td>" for k in keys)
                + "</tr>"
                for row in data[:1000]
            )
            body = (
                '<div class="scroll"><table><thead><tr>'
                + head
                + "</tr></thead><tbody>"
                + rows
                + "</tbody></table></div>"
            )
            if len(data) > 1000:
                body += (
                    "<p>Preview limited to 1,000 rows. Export JSON for all rows.</p>"
                )
        else:
            body = "<pre>" + display(data) + "</pre>"
        sections.append(
            "<section><h2>"
            + display(name.replace("_", " "))
            + "</h2>"
            + body
            + "</section>"
        )
    return (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>"""
        + display(title)
        + """</title><style>
*{box-sizing:border-box}body{font:15px/1.65 system-ui,sans-serif;background:#0c1420;color:#d9e5f3;margin:0}main{max-width:1200px;padding:38px 22px;margin:auto}h1{font-size:clamp(28px,5vw,42px);margin:10px 0}h2{font-size:16px;color:#8be5c9;text-transform:capitalize}header p{color:#abc0d6}section{background:#142233;padding:18px 22px;border:1px solid #2b425b;border-radius:12px;margin:18px 0}.label{color:#8be5c9;letter-spacing:2px;font-size:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.7 ui-monospace,monospace}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:11px;border-bottom:1px solid #355069;text-align:left;vertical-align:top;max-width:550px;overflow-wrap:anywhere}th{color:#a3dfce}input{width:100%;padding:12px;color:#e2ecf7;background:#0e1b2b;border:1px solid #57758d;border-radius:7px}input:focus{outline:2px solid #8be5c9}footer{color:#a5b7ca;font-size:12px}.note{border-left:3px solid #dbb878;padding-left:14px;color:#e1cfab}
.summary{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}.summary div{background:#142233;border:1px solid #2b425b;border-radius:10px;padding:12px 18px;flex:1 1 130px;min-width:0}.summary span{display:block;font-size:12px;color:#abc0d6;text-transform:capitalize}.summary strong{display:block;font-size:20px;overflow-wrap:anywhere}</style><main><header><div class="label">OFFLINE REPORT / ALPHA</div><h1>"""
        + display(title)
        + """</h1><p>Read-only SQLite schema inventory and comparison.</p><p class="note">Reports can contain sensitive names or text. Review before sharing. This is not a certification.</p></header><label for="search">Filter table rows</label><input id="search" placeholder="Type to filter visible table rows..."><p id="count" aria-live="polite"></p>"""
        + '<div class="summary">' + "".join(summary) + "</div>"
        + "".join(sections)
        + """<footer>Generated locally. Inputs are not uploaded or modified. Technical output is not proof of real-world correctness.</footer></main><script>
const search=document.getElementById('search');search.addEventListener('input',()=>{let visible=0,total=0;for(const row of document.querySelectorAll('tbody tr')){row.hidden=!row.textContent.toLowerCase().includes(search.value.toLowerCase());total++;if(!row.hidden)visible++;}document.getElementById('count').textContent=visible+' / '+total+' preview rows';});
</script></html>"""
    )


def main(core, title):
    parser = argparse.ArgumentParser(description=title)
    parser.add_argument(
        "--demo", action="store_true", help="Use synthetic inputs, not files"
    )
    parser.add_argument("--html", help="Write NEW standalone HTML, never overwrite")
    parser.add_argument("--json", help="Write NEW JSON, never overwrite")
    parser.add_argument(
        "--fail-on-findings", action="store_true", help="Exit 1 if finding_count > 0"
    )
    core.configure(parser)
    args = parser.parse_args()
    try:
        outputs = [Path(p).resolve() for p in (args.html, args.json) if p]
        if len(set(outputs)) != len(outputs) or any(
            p.exists() or p.is_symlink() for p in outputs
        ):
            raise ValueError("Output paths must be distinct NEW files")
        result = core.demo() if args.demo else core.run(args)
        result = {"schema_version": 1, "synthetic_demo": bool(args.demo), **result}
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.html:
            with Path(args.html).open("x", encoding="utf-8") as f:
                f.write(render(result, title))
        if args.json:
            with Path(args.json).open("x", encoding="utf-8") as f:
                f.write(encoded + "\n")
        if not args.html and not args.json:
            print(encoded)
        return 1 if args.fail_on_findings and result.get("finding_count", 0) else 0
    except (ValueError, OSError, RecursionError, UnicodeError) as exc:
        print(
            "Input/output rejected ("
            + type(exc).__name__
            + "). Check format, limits and paths; no complete report produced.",
            file=sys.stderr,
        )
        return 2
