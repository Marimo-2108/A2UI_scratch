"""Tests for repair_surfaces.  Run either way:
    uv run pytest
    uv run python tests/test_repair.py
"""
from a2ui_agent_app.a2ui import repair_surfaces

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


def test_update_for_unknown_surface_gets_createsurface_first():
    # the reported bug: a retry dropped createSurface, so the browser had no such surface
    known: set[str] = set()
    out, notes = repair_surfaces([data("kpi"), comps("kpi")], known, CAT)
    assert kinds(out) == ["createSurface", "updateDataModel", "updateComponents"]
    assert out[0]["createSurface"] == {"surfaceId": "kpi", "catalogId": CAT}
    assert known == {"kpi"} and len(notes) == 1


def test_well_formed_output_is_untouched():
    known: set[str] = set()
    good = [create("a"), comps("a"), data("a")]
    out, notes = repair_surfaces(good, known, CAT)
    assert out == good and notes == [] and known == {"a"}


def test_duplicate_createsurface_is_dropped_on_followup():
    known = {"a"}
    out, notes = repair_surfaces([create("a"), comps("a")], known, CAT)
    assert kinds(out) == ["updateComponents"] and len(notes) == 1


def test_delete_then_recreate_is_allowed():
    known = {"a"}
    out, notes = repair_surfaces([delete("a"), create("a"), comps("a")], known, CAT)
    assert kinds(out) == ["deleteSurface", "createSurface", "updateComponents"] and notes == []


def test_surfaces_are_handled_independently():
    known = {"a"}
    out, _ = repair_surfaces([comps("a"), comps("b")], known, CAT)
    assert kinds(out) == ["updateComponents", "createSurface", "updateComponents"]
    assert known == {"a", "b"}


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"all {len(tests)} repair_surfaces tests passed")
