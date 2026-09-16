from instance_sync import (
    compare_tests,
    decide_promotion,
    is_instance_owned,
    load_junit,
    parse_eval_report,
    shared_paths,
)

SENSALIS_PATHS = ["data/corpus", "data/sensalis_raw", "scripts/ingest_sensalis_pricing.py",
                  "scripts/bench_vs_scraper.py", "instance.env", "INSTANCE.md"]


def test_instance_owned_matches_dirs_and_exact_files_only():
    assert is_instance_owned("data/corpus/sensalis_100001.txt", SENSALIS_PATHS)
    assert is_instance_owned("scripts/bench_vs_scraper.py", SENSALIS_PATHS)
    assert is_instance_owned("instance.env", [])
    assert not is_instance_owned("data/corpus_extra/x.txt", SENSALIS_PATHS)
    assert not is_instance_owned("scripts/bench_vs_scraper.py.orig", SENSALIS_PATHS)
    assert not is_instance_owned("src/eval/hybrid_index.py", SENSALIS_PATHS)


def test_shared_paths_filters_out_instance_content():
    changed = ["data/corpus/sensalis_1.txt", "src/eval/hybrid_index.py", "INSTANCE.md", "tests/test_x.py"]
    assert shared_paths(changed, SENSALIS_PATHS) == ["src/eval/hybrid_index.py", "tests/test_x.py"]


def test_load_junit_classifies_outcomes(tmp_path):
    xml = tmp_path / "r.xml"
    xml.write_text(
        '<testsuites><testsuite>'
        '<testcase classname="tests.a" name="ok"/>'
        '<testcase classname="tests.a" name="bad"><failure message="x"/></testcase>'
        '<testcase classname="tests.a" name="err"><error message="x"/></testcase>'
        '<testcase classname="tests.a" name="skip"><skipped message="x"/></testcase>'
        '</testsuite></testsuites>'
    )
    assert load_junit(xml) == {"tests.a::ok": "passed", "tests.a::bad": "failed",
                               "tests.a::err": "failed", "tests.a::skip": "skipped"}


def test_compare_tests_flags_only_real_regressions():
    before = {"t1": "passed", "t2": "failed", "t3": "passed", "t4": "skipped"}
    after = {"t1": "failed", "t2": "passed", "t4": "passed", "t5": "passed", "t6": "failed"}
    d = compare_tests(before, after)
    assert d.newly_failing == ["t1"]
    assert d.new_failing == ["t6"]
    assert d.vanished_passing == ["t3"]
    assert d.fixed == ["t2"]
    assert d.new_passing == ["t5"]
    assert d.regressed


def test_pre_existing_failures_are_not_a_regression():
    before = {"kg::hetzner": "failed", "api::ok": "passed"}
    assert not compare_tests(before, dict(before)).regressed


def test_parse_eval_report_reads_the_real_eval_run_format():
    text = ("=== Eval report (index: hybrid) ===\nqueries judged : 126\n"
            "nDCG@10     : 0.9278\nMRR         : 0.9513\nrecall@20   : 0.9696\n")
    assert parse_eval_report(text) == {"nDCG@10": 0.9278, "MRR": 0.9513, "recall@20": 0.9696}


def test_promotion_rejects_metric_drop_and_test_regressions():
    base = {"nDCG@10": 0.9278}
    no_change = compare_tests({"a": "passed"}, {"a": "passed"})
    assert decide_promotion(no_change, base, {"nDCG@10": 0.9101}).verdict == "REJECT"
    broken = compare_tests({"a": "passed"}, {"a": "failed"})
    assert decide_promotion(broken, base, {"nDCG@10": 0.95}).verdict == "REJECT"
    assert decide_promotion(no_change, base, {}).verdict == "REJECT"


def test_promotion_accepts_improvement_and_neutral_change():
    base = {"nDCG@10": 0.9278}
    same = compare_tests({"a": "passed"}, {"a": "passed"})
    better = decide_promotion(same, base, {"nDCG@10": 0.9301})
    assert better.verdict == "PROMOTE" and "0.9278 -> 0.9301" in better.reasons[0]
    assert decide_promotion(same, base, dict(base)).verdict == "PROMOTE"
