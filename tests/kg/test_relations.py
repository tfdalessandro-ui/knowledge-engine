from kg.ner import extract_entities
from kg.relations import extract_relations


def test_clean_svo_sentence_extracts_a_relation():
    text = "Tantivy uses BM25 for ranking."
    relations = extract_relations(text, extract_entities(text))
    assert len(relations) == 1
    assert relations[0].subject == "Tantivy"
    assert relations[0].relation == "USES"
    assert relations[0].object == "BM25"


def test_sentence_with_three_entities_is_skipped_as_ambiguous():
    text = "BM25 predates modern neural ranking methods, and TF-IDF predates BM25 itself."
    relations = extract_relations(text, extract_entities(text))
    assert relations == []  # 3 entity mentions in one sentence -- ambiguous, correctly not guessed at


def test_sentence_with_no_relation_verb_yields_nothing():
    text = "FastAPI and Starlette are both mentioned here without a connecting verb we recognize."
    relations = extract_relations(text, extract_entities(text))
    assert relations == []


def test_sentence_with_only_one_entity_yields_nothing():
    text = "BM25 is a ranking function."
    relations = extract_relations(text, extract_entities(text))
    assert relations == []


def test_subject_equals_object_is_not_emitted():
    text = "Python runs Python."  # degenerate case, same entity twice
    relations = extract_relations(text, extract_entities(text))
    assert relations == []
