from kg.ner import extract_entities


def test_technology_terms_recognized():
    entities = extract_entities("BM25 and TF-IDF are both ranking functions.")
    labels = {e.text: e.label for e in entities}
    assert labels["BM25"] == "TECHNOLOGY"
    assert labels["TF-IDF"] == "TECHNOLOGY"


def test_company_and_product_terms_recognized():
    entities = extract_entities("Hetzner sells the CCX23 instance.")
    labels = {e.text: e.label for e in entities}
    assert labels["Hetzner"] == "COMPANY"
    assert labels["CCX23"] == "PRODUCT"


def test_single_token_person_false_positives_are_filtered():
    # verified live against the real corpus: spaCy tags lowercase "bm25" and
    # the Ubuntu codename "Numbat" as PERSON -- both single-token, both wrong
    entities = extract_entities("the bm25() function ships with Ubuntu 24.04 LTS (Noble Numbat).")
    person_texts = {e.text for e in entities if e.label == "PERSON"}
    assert "bm25" not in person_texts
    assert "Numbat" not in person_texts


def test_multi_token_capitalized_span_not_auto_excluded_from_person():
    # the filter requires 2+ alphabetic tokens -- it should not reject every
    # PERSON candidate outright, just single-token ones
    from kg.ner import _looks_like_a_person_name, get_nlp

    doc = get_nlp()("Jane Smith wrote the report.")
    span = doc[0:2]  # "Jane Smith"
    assert _looks_like_a_person_name(span) is True


def test_entity_has_sentence_context():
    entities = extract_entities("BM25 is a ranking function. It is widely used.")
    assert entities[0].sent_text.strip() == "BM25 is a ranking function."
