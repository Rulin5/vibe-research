from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_quick_start_keeps_real_secrets_out_of_git():
    gitignore = read(".gitignore")
    script = read("start-demo.ps1")
    compose = read("compose.demo.yaml")

    assert "deploy/demo.env" in gitignore
    assert "TEAJOIN_API_KEY" in script
    assert "VR_AI_STEPFUN_API_KEY" in script
    assert "RandomNumberGenerator" in script
    assert "deploy/demo.env" in compose


def test_demo_stack_runs_on_local_http_without_production_tls_files():
    compose = read("compose.demo.yaml")
    nginx = read("deploy/nginx/demo.conf")

    assert '"127.0.0.1:5900:80"' in compose
    assert "listen 80" in nginx
    assert "ssl_certificate" not in nginx
    assert "api:8900" in nginx


def test_readme_documents_one_command_demo_start():
    readme = read("README.md")

    assert ".\\start-demo.ps1" in readme
    assert "http://127.0.0.1:5900" in readme
    assert "不要把 deploy/demo.env 上传到 GitHub" in readme
