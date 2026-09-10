#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MAX_RUNS = 30
WORKFLOWS = (
    {
        "file": "lambda-tests.yml",
        "name": "Lambda tests",
        "color": "#8250df",
    },
    {
        "file": "deploy-aws.yml",
        "name": "Deploy AWS infrastructure",
        "color": "#0969da",
    },
)


def api_get(path: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        raise RuntimeError("GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    url = f"https://api.github.com/repos/{repository}/{path}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "football-schedule-ci-performance",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned {exc.code}: {body}") from exc


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def duration_seconds(started_at: str | None, completed_at: str | None) -> int | None:
    started = parse_time(started_at)
    completed = parse_time(completed_at)
    if not started or not completed:
        return None
    return max(0, round((completed - started).total_seconds()))


def fetch_recent_successful_runs(workflow_file: str) -> list[dict]:
    selected: list[dict] = []
    for page in range(1, 5):
        query = urllib.parse.urlencode(
            {
                "branch": "main",
                "status": "completed",
                "per_page": 50,
                "page": page,
            }
        )
        payload = api_get(f"actions/workflows/{workflow_file}/runs?{query}")
        runs = payload.get("workflow_runs", [])
        for run in runs:
            if run.get("conclusion") != "success":
                continue
            duration = duration_seconds(run.get("run_started_at"), run.get("updated_at"))
            if duration is None:
                continue
            selected.append(
                {
                    "run": run.get("run_number"),
                    "duration": duration,
                    "url": run.get("html_url"),
                    "completed_at": run.get("updated_at"),
                }
            )
            if len(selected) >= MAX_RUNS:
                return selected
        if len(runs) < 50:
            break
    return selected


def escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_duration(seconds: int) -> str:
    minutes, remainder = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {remainder}s"
    return f"{remainder}s"


def nice_y_max(values: list[int]) -> int:
    maximum = max(values, default=60)
    if maximum <= 60:
        step = 15
    elif maximum <= 180:
        step = 30
    elif maximum <= 600:
        step = 60
    else:
        step = 120
    return max(step * 4, int(math.ceil((maximum * 1.12) / step) * step))


def render_panel(
    points: list[dict],
    *,
    name: str,
    color: str,
    top: int,
    width: int,
) -> list[str]:
    left = 70
    right = 28
    plot_top = top + 66
    plot_height = 185
    plot_width = width - left - right
    values = [point["duration"] for point in points]
    y_max = nice_y_max(values)

    def x_at(index: int) -> float:
        if len(points) <= 1:
            return left + plot_width / 2
        return left + plot_width * index / (len(points) - 1)

    def y_at(value: int) -> float:
        return plot_top + plot_height * (1 - value / y_max)

    chunks = [
        f'<text x="32" y="{top + 26}" font-size="17" font-weight="600" fill="#1f2328" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">{escape(name)}</text>',
    ]

    if points:
        latest = points[-1]
        chunks.append(
            f'<text x="{width - 28}" y="{top + 26}" text-anchor="end" font-size="13" font-weight="600" fill="{color}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">Latest {escape(format_duration(latest["duration"]))} · #{escape(latest["run"])}</text>'
        )

    for tick in range(5):
        value = round(y_max * tick / 4)
        y = y_at(value)
        chunks.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#d8dee4" stroke-width="1"/>'
        )
        chunks.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#656d76" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">{value}s</text>'
        )

    if not points:
        chunks.append(
            f'<text x="{width / 2:.1f}" y="{plot_top + plot_height / 2:.1f}" text-anchor="middle" font-size="13" fill="#656d76" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">No successful main runs yet.</text>'
        )
        return chunks

    label_every = max(1, math.ceil(len(points) / 8))
    for index, point in enumerate(points):
        if index % label_every == 0 or index == len(points) - 1:
            x = x_at(index)
            chunks.append(
                f'<text x="{x:.1f}" y="{plot_top + plot_height + 24}" text-anchor="middle" font-size="10" fill="#656d76" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">#{escape(point["run"])}</text>'
            )

    coords = " ".join(
        f"{x_at(index):.1f},{y_at(point['duration']):.1f}"
        for index, point in enumerate(points)
    )
    chunks.append(
        f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    for index, point in enumerate(points):
        x = x_at(index)
        y = y_at(point["duration"])
        chunks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.3" fill="{color}"/>')

    return chunks


def render_svg(series: list[dict]) -> str:
    width = 900
    height = 650
    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">CI performance history</title>',
        '<desc id="desc">Recent successful main branch durations for Lambda tests and Deploy AWS infrastructure.</desc>',
        '<rect width="100%" height="100%" rx="12" fill="#ffffff" stroke="#d0d7de"/>',
        '<text x="32" y="38" font-size="21" font-weight="600" fill="#1f2328" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">CI performance</text>',
        f'<text x="32" y="61" font-size="12" fill="#656d76" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">Latest up to {MAX_RUNS} successful main runs · workflow duration in seconds</text>',
    ]

    panel_tops = (78, 356)
    for item, top in zip(series, panel_tops):
        chunks.extend(
            render_panel(
                item["points"],
                name=item["name"],
                color=item["color"],
                top=top,
                width=width,
            )
        )

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    chunks.append(
        f'<text x="{width - 24}" y="{height - 16}" text-anchor="end" font-size="10" fill="#8c959f" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">Updated {updated}</text>'
    )
    chunks.append("</svg>")
    return "\n".join(chunks) + "\n"


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "ci-performance.svg")
    series = []
    for workflow in WORKFLOWS:
        runs = fetch_recent_successful_runs(workflow["file"])
        series.append(
            {
                "name": workflow["name"],
                "color": workflow["color"],
                "points": list(reversed(runs)),
            }
        )

    output.write_text(render_svg(series), encoding="utf-8")
    counts = ", ".join(f"{item['name']}={len(item['points'])}" for item in series)
    print(f"wrote {output} ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
