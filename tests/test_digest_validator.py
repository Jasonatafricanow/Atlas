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


def test_optional_fields_and_duplicate_quotes():
    d = good()
    d['sentences'][0].update(ts=None, outcome=None, stance=None)
    d['sentences'][1]['evidence'] *= 2
    errs, per = v.validate_digest(d, DOCS)
    assert not errs and all(ok for _, ok, _ in per)


def test_empty_missing_and_malformed_evidence_fail_without_crashing():
    for evidence in (None, [], {}, 'wrong', [None], [{}], [{'doc_id':'d1','quote':'  '}],
                     [{'doc_id':'d1','quote':''}], [{'doc_id':[], 'quote':'the widget'}]):
        d = good()
        d['sentences'][0]['evidence'] = evidence
        assert not v.validate_digest(d, DOCS)[1][0][1]
    d = good()
    del d['sentences'][0]['evidence']
    assert not v.validate_digest(d, DOCS)[1][0][1]
    for out in (None, [], {'sentences':None}, {'sentences':'wrong'}, {'sentences':[None,1]}):
        errs, per = v.validate_digest(out, DOCS)
        assert errs or any(not ok for _,ok,_ in per)


def test_number_formats_preserve_value_scale_sign_and_percent():
    cases = [
        ('3651.43', '3,651.43', True), ('3,651.43', '3651.43', True),
        ('价格：３，６５１．４３；上涨２．１％。', '价格:3651.43;上涨2.1%。', True),
        ('数量2.1万', '数量21000', True), ('数量21000', '数量２．１万', True),
        ('2.10 percent', '２．１％', True), ('0.5%', '.50%', True),
        ('12', '312', False), ('3651.4', '3651.43', False),
        ('21', '2.1万', False), ('2.1', '2.1万', False),
        ('2.1%', '2.1', False), ('2.1', '2.1%', False),
        ('-2.1%', '2.1%', False), ('2.1%', '-2.1%', False),
        ('3651.44', '3,651.43', False), ('34', '12,34', False),
        ('1.2', '1.20', True), ('−2.1%', '-2.1%', True),
        ('2.1%', '−2.1%', False),
    ]
    for claim, quote, expected in cases:
        d = {'sentences':[{'section':'what','text':claim,'evidence':[{'doc_id':'d','quote':quote}]}]}
        assert v.validate_digest(d, {'d':quote})[1][0][1] is expected, (claim,quote)


def test_numbers_cannot_come_from_quote_seams_or_timestamp_extras():
    d = {'sentences':[{'section':'what','text':'虚构价格12', 'evidence':[
        {'doc_id':'d','quote':'虚构1'}, {'doc_id':'d','quote':'2'}]}]}
    assert not v.validate_digest(d, {'d':'虚构1 与 2'})[1][0][1]
    d['sentences'][0]['text'] = '虚构价格2025'
    assert not v.validate_digest(d, {'d':'虚构1 与 2'}, '2025-01-12')[1][0][1]
    d['sentences'][0].update(text='虚构观察',ts='2025-01-12')
    assert v.validate_digest(d, {'d':'虚构1 与 2'}, '2025-01-12')[1][0][1]


def test_quote_matching_remains_grounded_not_number_equivalence():
    d = {'sentences':[{'section':'what','text':'价格3651.43',
        'evidence':[{'doc_id':'d','quote':'价格3651.43'}]}]}
    assert not v.validate_digest(d, {'d':'价格3,651.43'})[1][0][1]


def test_merge_malformed_members_and_empty_graph():
    for out in (None, [], {}, {'merged':None}, {'merged':[None]},
                {'merged':[{}]}, {'merged':[{'member_line_ids':[None]}]}):
        assert v.validate_merge(out, ['fiction-line'])
    assert not v.validate_merge({'merged':[]}, [])
    assert v.validate_merge({'merged':[{'member_line_ids':['fiction-line','fiction-line']}]}, ['fiction-line'])


def test_doubled_function_characters_warn_without_failing_or_rewriting():
    import copy
    d = good()
    d['title'] = '虚构标的的说明'
    d['sentences'][0]['text'] = '虚构计划了了，是是，在在，的的的。'
    before = copy.deepcopy(d)
    warnings = v.lint_digest(d)
    assert len(warnings) == 5
    assert warnings[0] == {'field':'title', 'offset':3, 'code':'doubled_function_character'}
    assert all(w['field'] == 'sentences[0].text' for w in warnings[1:])
    errs, per = v.validate_digest(d, DOCS)
    assert errs == [] and all(ok for _, ok, _ in per)
    assert d == before


def test_lint_ignores_quotes_normal_repetition_and_malformed_fields():
    for out in (None, [], {}, {'title':None, 'sentences':[None, {}, {'text':3}]},
                {'title':'看看虚构花圃', 'sentences':[{'text':'计划是在花圃的边上',
                    'evidence':[{'quote':'的的了了是是在在'}]}]}):
        assert v.lint_digest(out) == []
