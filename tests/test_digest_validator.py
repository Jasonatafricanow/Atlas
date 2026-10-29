import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("v", pathlib.Path(__file__).parents[1] / "experiments/digest/validate.py")
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
DOCS = {"d1": "Alice said the widget price rose 12 percent in March."}

def good():
    return {"sentences": [
        {"section": "what", "text": "Widget is a product.", "evidence": [{"doc_id": "d1", "quote": "the widget price"}]},
        {"section": "view", "stance": "观察", "text": "Price rose 12 percent.", "evidence": [{"doc_id": "d1", "quote": "rose 12 percent"}]},
        {"section": "evolution", "text": "Rise noted.", "evidence": [{"doc_id": "d1", "quote": "in March"}]},
        {"section": "record", "outcome": "unknown", "text": "Unverified.", "evidence": [{"doc_id": "d1", "quote": "Alice said"}]}]}

def test_good_passes():
    errs, per = v.validate_digest(good(), DOCS)
    assert errs == [] and all(ok for _, ok, _ in per)

def test_fake_quote_and_number_fail():
    d = good(); d["sentences"][1]["text"] = "Price rose 40 percent."; d["sentences"][2]["evidence"][0]["quote"] = "in April"
    errs, per = v.validate_digest(d, DOCS)
    assert not per[1][1] and not per[2][1]

def test_view_needs_stance_and_sections():
    d = good(); del d["sentences"][1]["stance"]; d["sentences"].pop()
    errs, per = v.validate_digest(d, DOCS)
    assert "missing section record" in errs and not per[1][1]

def test_merge_partition():
    assert v.validate_merge({"merged": [{"member_line_ids": ["a", "b"]}]}, ["a", "b"]) == []
    assert v.validate_merge({"merged": [{"member_line_ids": ["a"]}]}, ["a", "b"])
