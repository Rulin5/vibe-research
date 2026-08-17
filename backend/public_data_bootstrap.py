"""Deployment gate for the public dashboard snapshot."""

from public_data_refresh import PublicDataRefreshService


def main() -> int:
    service = PublicDataRefreshService()
    if service.readiness().get("ok"):
        return 0
    state = service.run_once("public-data-deploy-bootstrap")
    return 0 if state.get("status") == "completed" and service.readiness().get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
