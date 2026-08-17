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


def test_store_loads_all_members_for_same_day_refresh_reuse(tmp_path):
    store = SectorSnapshotStore(tmp_path)
    snapshot = {
        "snapshot_id": "20260811-v1", "status": "completed", "as_of": "20260811",
        "sectors": [{"kind": "行业", "code": "881101.TI"}],
    }
    members = {("行业", "881101.TI"): [{"code": "600000", "name": "浦发银行"}]}
    store.publish(snapshot, members)

    assert store.load_all_members("20260811-v1") == members


def test_store_reclaims_a_lock_left_by_a_dead_process(tmp_path):
    store = SectorSnapshotStore(tmp_path)
    lock = store._path("refresh.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("99999999", encoding="utf-8")

    acquired = store.try_acquire_refresh_lock(stale_after_seconds=3600)

    assert acquired == lock
    store.release_refresh_lock(acquired)
    assert not lock.exists()


def test_refresh_lock_excludes_a_second_process_until_released(tmp_path):
    store = SectorSnapshotStore(tmp_path)

    lock = store.try_acquire_refresh_lock()

    assert lock is not None
    assert store.try_acquire_refresh_lock() is None

    store.release_refresh_lock(lock)

    assert store.try_acquire_refresh_lock() is not None
