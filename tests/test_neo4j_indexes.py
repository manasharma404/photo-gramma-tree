"""The Neo4j loader creates its lookup indexes before it writes (without them one access report took 108 s)."""
from advisor import load


class FakeDriver:
    def __init__(self):
        self.queries = []

    def execute_query(self, query, **kwargs):
        self.queries.append(" ".join(query.split()))

        class R:
            records = []
        return R()


def test_indexes_come_first_and_are_idempotent():
    d = FakeDriver()
    load.ensure_indexes(d)
    created = [q for q in d.queries if q.startswith("CREATE INDEX")]
    assert len(created) == 3 and all("IF NOT EXISTS" in q for q in created)
    assert any("(j.project, j.junction_id)" in q for q in created)
    assert d.queries[-1].startswith("CALL db.awaitIndexes")


def test_loader_ensures_indexes_before_deleting_or_writing(monkeypatch):
    d = FakeDriver()
    calls = []
    monkeypatch.setattr(load, "ensure_indexes", lambda drv: calls.append("indexes"))

    class Topo:
        junctions, segments, places = {}, {}, []
    try:
        load.load_topology_to_neo4j(Topo(), "p", d)
    except Exception:
        pass  # an empty fake topology may not load fully; only the order matters here
    assert calls == ["indexes"] and d.queries and d.queries[0].startswith("MATCH (n {project: $project}) DETACH DELETE")
