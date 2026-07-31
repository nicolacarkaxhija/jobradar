from jobradar.pipeline import _due
from jobradar.store import Store


def test_due_when_never_ran() -> None:
    with Store(":memory:") as store:
        assert _due(store, "llm_sweep", every_days=7)


def test_not_due_right_after_a_run() -> None:
    with Store(":memory:") as store:
        store.record_run("llm_sweep")
        assert not _due(store, "llm_sweep", every_days=7)
        assert _due(store, "llm_sweep", every_days=0)
