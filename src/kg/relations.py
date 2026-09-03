"""Pattern-based relation extraction, per the P4 spec (not a trained ML
relation model). For each sentence containing exactly two recognized
entities and a verb from a fixed relation vocabulary, emits a
(subject_entity, RELATION_TYPE, object_entity) triple using simple word
order as the subject/object heuristic -- the entity appearing before the
verb is the subject, the one after is the object.

This deliberately doesn't attempt a full dependency-parse traversal: with a
small, curated entity vocabulary (see ner.py) and short factual sentences
(the corpus's own writing style), word order around a relation verb already
gets this right for the cases that matter, and a heuristic that's easy to
audit beats a fragile one that's hard to.
"""
from __future__ import annotations

from dataclasses import dataclass

from kg.ner import Entity, get_nlp

# lemma -> relation type. Grounded in verbs that actually connect two
# recognized entities in data/corpus/ sentences (checked before writing).
RELATION_VERBS = {
    "power": "POWERS",
    "run": "RUNS_ON",
    "use": "USES",
    "build": "BUILDS_ON",
    "predate": "PREDATES",
    "offer": "OFFERS",
    "provide": "PROVIDES",
    "extend": "EXTENDS",
    "combine": "COMBINES",
}


@dataclass
class Relation:
    subject: str
    relation: str
    object: str
    sentence: str


def extract_relations(text: str, entities: list[Entity]) -> list[Relation]:
    doc = get_nlp()(text)
    relations = []

    for sent in doc.sents:
        sent_entities = [e for e in entities if sent.start_char <= e.start_char < sent.end_char]
        if len(sent_entities) != 2:
            continue  # ambiguous with 3+, nothing to relate with 0-1

        relation_type = None
        verb_char_offset = None
        for token in sent:
            # Matched by lemma alone, not POS tag: spaCy's tagger is unreliable on
            # short, terse sentences (confirmed directly -- "FastAPI runs on
            # Starlette" tags "runs" as non-VERB). Safe here because RELATION_VERBS
            # is a small closed vocabulary where a false-positive noun reading is
            # implausible in this technical corpus.
            if token.lemma_ in RELATION_VERBS:
                relation_type = RELATION_VERBS[token.lemma_]
                verb_char_offset = token.idx
                break
        if relation_type is None:
            continue

        sent_entities.sort(key=lambda e: e.start_char)
        first, second = sent_entities
        if first.end_char <= verb_char_offset <= second.start_char:
            subject, obj = first, second
        elif second.end_char <= verb_char_offset:
            subject, obj = first, second  # verb after both -- keep textual order
        else:
            continue  # verb before both entities -- word-order heuristic doesn't apply cleanly

        if subject.text == obj.text:
            continue
        relations.append(Relation(subject=subject.text, relation=relation_type, object=obj.text, sentence=sent.text.strip()))

    return relations
