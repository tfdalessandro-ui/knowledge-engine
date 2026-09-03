"""Graph storage over Memgraph (the P4 tech choice), reached via the Bolt
protocol using the standard `neo4j` Python driver -- Memgraph is
Bolt-compatible, so no Memgraph-specific client library is needed.

Unlike every prior phase's index (Tantivy/FAISS embedded in-process),
Memgraph is a separate server process. This repo does not start it for
you -- see HELP.md for the `docker run` command and why it's bound to
127.0.0.1 only, matching this node's existing container convention.
"""
from __future__ import annotations

from dataclasses import dataclass

from neo4j import GraphDatabase

VALID_LABELS = {"COMPANY", "PERSON", "PRODUCT", "TECHNOLOGY"}
# RELATION_VERBS values (kg/relations.py) are the only source of relation
# types actually written -- a small closed vocabulary, safe to interpolate
# into a Cypher relationship type (which can't be parameterized) since it
# never comes from external/user input.
from kg.relations import RELATION_VERBS

VALID_RELATION_TYPES = set(RELATION_VERBS.values())


@dataclass
class Neighbor:
    name: str
    label: str
    relation: str
    direction: str  # "outgoing" | "incoming"


class MemgraphStore:
    def __init__(self, uri: str = "bolt://127.0.0.1:7687", auth: tuple[str, str] | None = None):
        self._driver = GraphDatabase.driver(uri, auth=auth)

    def upsert_entity(self, canonical_id: str, name: str, label: str, source_doc_id: str) -> None:
        if label not in VALID_LABELS:
            raise ValueError(f"unknown entity label {label!r}, expected one of {VALID_LABELS}")
        with self._driver.session() as session:
            session.run(
                f"""
                MERGE (e:Entity:{label} {{canonical_id: $cid}})
                ON CREATE SET e.name = $name, e.mention_count = 1
                ON MATCH SET e.mention_count = e.mention_count + 1
                MERGE (d:Document {{doc_id: $doc_id}})
                MERGE (e)-[:MENTIONED_IN]->(d)
                """,
                cid=canonical_id, name=name, doc_id=source_doc_id,
            )

    def upsert_relation(self, subject_cid: str, relation_type: str, object_cid: str) -> None:
        if relation_type not in VALID_RELATION_TYPES:
            raise ValueError(f"unknown relation type {relation_type!r}, expected one of {VALID_RELATION_TYPES}")
        with self._driver.session() as session:
            session.run(
                f"""
                MATCH (a:Entity {{canonical_id: $subj}}), (b:Entity {{canonical_id: $obj}})
                MERGE (a)-[r:{relation_type}]->(b)
                ON CREATE SET r.weight = 1
                ON MATCH SET r.weight = r.weight + 1
                """,
                subj=subject_cid, obj=object_cid,
            )

    def get_neighbors(self, canonical_id: str) -> list[Neighbor]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {canonical_id: $cid})-[r]->(n:Entity)
                RETURN n.name AS name, labels(n) AS labels, type(r) AS relation, 'outgoing' AS direction
                UNION
                MATCH (e:Entity {canonical_id: $cid})<-[r]-(n:Entity)
                RETURN n.name AS name, labels(n) AS labels, type(r) AS relation, 'incoming' AS direction
                """,
                cid=canonical_id,
            )
            neighbors = []
            for record in result:
                entity_label = next(l for l in record["labels"] if l in VALID_LABELS)
                neighbors.append(Neighbor(name=record["name"], label=entity_label,
                                           relation=record["relation"], direction=record["direction"]))
            return neighbors

    def entity_count(self) -> int:
        with self._driver.session() as session:
            return session.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]

    def clear(self) -> None:
        """Wipes the whole graph -- used by tests and re-runs, not exposed
        via any CLI flag (destructive by design, opt-in in code only)."""
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "MemgraphStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
