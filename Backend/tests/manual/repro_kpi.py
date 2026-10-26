"""Repro helper: send the KPI prompt N times, report whether every surface that gets updated was created.

    set AGENT_URL=http://localhost:10011/   (optional)   uv run python tests/manual/repro_kpi.py [N]
"""
import sys

import try_agent

try_agent.CAPS = try_agent.load_caps()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
bad = 0
for i in range(1, N + 1):
    print(f"===== run {i}")
    _, msgs = try_agent.stream("a KPI dashboard: monthly revenue, active users, churn")
    created, problems = set(), []
    for m in msgs:
        kind = next(k for k in m if k != "version")
        sid = m[kind].get("surfaceId")
        if kind == "createSurface":
            created.add(sid)
        elif kind in ("updateComponents", "updateDataModel") and sid not in created:
            problems.append(f"{kind} for surface {sid!r} BEFORE any createSurface")
    print("   ->", "OK" if not problems else "BROKEN: " + "; ".join(problems))
    bad += bool(problems)
print(f"\n{bad}/{N} runs would show 'Surface not found' in the browser")
