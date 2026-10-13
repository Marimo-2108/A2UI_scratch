"""Plain-assert tests for repair_surfaces (no pytest needed):  uv run python tests/test_repair.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_brain import repair_surfaces  # noqa: E402

CAT = "cat://x"


def create(s):
    return {"version": "v0.9", "createSurface": {"surfaceId": s, "catalogId": CAT}}


def comps(s):
    return {"version": "v0.9", "updateComponents": {"surfaceId": s, "components": []}}


def data(s):
    return {"version": "v0.9", "updateDataModel": {"surfaceId": s, "path": "/", "value": {}}}


def delete(s):
    return {"version": "v0.9", "deleteSurface": {"surfaceId": s}}


def kinds(msgs):
    return [next(k for k in m if k != "version") for m in msgs]


# 1. the reported bug: update for a surface the client never got -> createSurface inserted FIRST
known: set[str] = set()
out, notes = repair_surfaces([data("kpi"), comps("kpi")], known, CAT)
assert kinds(out) == ["createSurface", "updateDataModel", "updateComponents"], kinds(out)
assert out[0]["createSurface"] == {"surfaceId": "kpi", "catalogId": CAT}
assert known == {"kpi"} and len(notes) == 1

# 2. well-formed output is left untouched
known = set()
good = [create("a"), comps("a"), data("a")]
out, notes = repair_surfaces(good, known, CAT)
assert out == good and notes == [] and known == {"a"}

# 3. follow-up turn: createSurface for a surface already on screen is dropped; updates pass through
out, notes = repair_surfaces([create("a"), comps("a")], known, CAT)
assert kinds(out) == ["updateComponents"] and len(notes) == 1

# 4. delete then re-create is allowed
out, notes = repair_surfaces([delete("a"), create("a"), comps("a")], known, CAT)
assert kinds(out) == ["deleteSurface", "createSurface", "updateComponents"] and notes == []

# 5. several surfaces, each handled independently
known = {"a"}
out, notes = repair_surfaces([comps("a"), comps("b")], known, CAT)
assert kinds(out) == ["updateComponents", "createSurface", "updateComponents"]
assert known == {"a", "b"}

print("all repair_surfaces tests passed")
