from sector_snapshot import SectorSnapshotStore


def test_store_only_exposes_completed_snapshot(tmp_path):
    store = SectorSnapshotStore(tmp_path)
    store.save_refresh_state({"task_id": "task-1", "status": "running"})

    assert store.load_current() is None

    store.publish({"snapshot_id": "20260811-v1", "status": "completed", "sectors": []})

    assert store.load_current()["snapshot_id"] == "20260811-v1"


def test_store_persists_members_for_the_same_snapshot(tmp_path):
    store = SectorSnapshotStore(tmp_path)
    snapshot = {
        "snapshot_id": "20260811-v1",
        "status": "completed",
        "sectors": [{"kind": "行业", "code": "881101.TI"}],
    }
    members = {("行业", "881101.TI"): [{"code": "600000", "name": "浦发银行"}]}

    store.publish(snapshot, members)

    assert store.load_members("20260811-v1", "行业", "881101.TI") == members[("行业", "881101.TI")]
