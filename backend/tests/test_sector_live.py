import pytest

from sector_refresh import default_store


@pytest.mark.live
def test_live_snapshot_exposes_only_complete_sectors_with_members():
    store = default_store()
    snapshot = store.load_current()

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["as_of"]
    completeness = snapshot["completeness"]
    assert completeness["candidate_count"] == completeness["published_count"] + completeness["excluded_count"]
    assert {row["kind"] for row in snapshot["sectors"]} == {"行业", "概念"}
    assert all(row["data_status"] == "complete" for row in snapshot["sectors"])
    assert all(row["close"] is not None and row["pct_change"] is not None for row in snapshot["sectors"])
    assert all(store.load_members(snapshot["snapshot_id"], row["kind"], row["code"]) for row in snapshot["sectors"])
