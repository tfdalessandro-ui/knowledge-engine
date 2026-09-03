from kg.resolution import EntityResolver, MergeReviewQueue, canonical_id, normalize


def test_normalize_lowercases_and_strips_punctuation():
    assert normalize("BM-25") == "bm 25"
    assert normalize("BM25") == "bm25"


def test_canonical_id_includes_label():
    assert canonical_id("BM25", "TECHNOLOGY") == "TECHNOLOGY:bm25"


def test_exact_match_reuses_canonical_id(tmp_path):
    resolver = EntityResolver(MergeReviewQueue(tmp_path / "queue.db"))
    a = resolver.resolve("BM25", "TECHNOLOGY")
    b = resolver.resolve("bm25", "TECHNOLOGY")  # different case, same normalized form
    assert a == b


def test_different_entities_get_different_ids(tmp_path):
    resolver = EntityResolver(MergeReviewQueue(tmp_path / "queue.db"))
    a = resolver.resolve("BM25", "TECHNOLOGY")
    b = resolver.resolve("FAISS", "TECHNOLOGY")
    assert a != b


def test_fuzzy_near_duplicate_is_queued_not_merged(tmp_path):
    queue = MergeReviewQueue(tmp_path / "queue.db")
    resolver = EntityResolver(queue)
    a = resolver.resolve("CCX23", "PRODUCT")
    b = resolver.resolve("CX23", "PRODUCT")  # similar but genuinely different product

    assert a != b  # NOT auto-merged
    pending = queue.list_pending()
    assert len(pending) == 1
    assert {pending[0].entity_a, pending[0].entity_b} == {"CCX23", "CX23"}


def test_merge_review_queue_resolve_updates_status(tmp_path):
    queue = MergeReviewQueue(tmp_path / "queue.db")
    queue.add_candidate("CCX23", "CX23", "PRODUCT", 88.9)
    candidate = queue.list_pending()[0]
    queue.resolve(candidate.candidate_id, merge=False)
    assert queue.list_pending() == []


def test_merge_review_queue_dedups_regardless_of_order(tmp_path):
    queue = MergeReviewQueue(tmp_path / "queue.db")
    queue.add_candidate("A", "B", "PRODUCT", 90.0)
    queue.add_candidate("B", "A", "PRODUCT", 90.0)
    assert len(queue.list_pending()) == 1
