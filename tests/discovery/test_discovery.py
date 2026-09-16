import pytest

from discovery.blocklist import is_domain_blocked, _parse_hosts_format
from discovery.pipeline import is_sparse


def test_parse_hosts_format_extracts_domains():
    text = """# comment
0.0.0.0 localhost
0.0.0.0 ads.example.com
127.0.0.1 tracker.example.net

"""
    domains = _parse_hosts_format(text)
    assert "ads.example.com" in domains
    assert "tracker.example.net" in domains
    assert "localhost" not in domains  # explicitly excluded, not a real blocked domain


def test_is_domain_blocked():
    blocklist = {"ads.example.com"}
    assert is_domain_blocked("ads.example.com", blocklist) is True
    assert is_domain_blocked("ADS.EXAMPLE.COM", blocklist) is True  # case-insensitive
    assert is_domain_blocked("safe.example.com", blocklist) is False


class _FakeHit:
    def __init__(self, bm25_score):
        self.bm25_score = bm25_score


def test_is_sparse_no_real_bm25_matches_in_top_n():
    all_vector_only = [_FakeHit(None), _FakeHit(None), _FakeHit(4.2)]
    assert is_sparse(all_vector_only, threshold=2) is True  # top 2 are both vector-only padding


def test_is_sparse_false_when_a_real_match_exists_in_top_n():
    has_real_match = [_FakeHit(7.4), _FakeHit(None), _FakeHit(None)]  # 7.4: a real on-topic score seen live this session
    assert is_sparse(has_real_match, threshold=2) is False


def test_is_sparse_true_for_weak_incidental_overlap_below_the_real_threshold():
    # the actual live false-positive this threshold was calibrated to exclude
    weak_incidental_overlap = [_FakeHit(4.29), _FakeHit(None)]
    assert is_sparse(weak_incidental_overlap, threshold=2) is True


def test_is_sparse_empty_hits_is_sparse():
    assert is_sparse([], threshold=2) is True


def test_provenance_store_roundtrip(tmp_path):
    from discovery.provenance import ProvenanceStore

    store = ProvenanceStore(tmp_path / "provenance.db")
    store.record("doc1", "some query", "https://example.com/page")
    record = store.get("doc1")
    assert record is not None
    assert record.source_query == "some query"
    assert record.source_url == "https://example.com/page"
    assert store.get("nonexistent") is None
    store.close()


def test_direct_call_to_log_invocation_is_self_logging(tmp_path):
    """Proves the fix for the 2026-09-06 untraceable-call incident: a
    direct call with no /search API involvement still leaves a row,
    tagged with whatever caller string is passed (or "unknown" if none
    is given -- the whole point being no call goes unlogged, ever)."""
    from discovery.provenance import ProvenanceStore

    store = ProvenanceStore(tmp_path / "provenance.db")
    invocation_id = store.log_invocation("a direct test query", caller="pytest-direct-call")
    assert invocation_id > 0

    invocations = store.all_invocations()
    assert len(invocations) == 1
    assert invocations[0].query == "a direct test query"
    assert invocations[0].caller == "pytest-direct-call"
    assert invocations[0].pid > 0
    store.close()


def test_log_invocation_defaults_caller_to_unknown_not_silent(tmp_path):
    from discovery.provenance import ProvenanceStore

    store = ProvenanceStore(tmp_path / "provenance.db")
    store.log_invocation("no caller specified")
    invocations = store.all_invocations()
    assert invocations[0].caller == "unknown"  # logged, just flagged as untraced -- never silent
    store.close()
