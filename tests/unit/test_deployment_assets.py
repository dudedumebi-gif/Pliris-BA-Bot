from pathlib import Path


def test_dockerfile_uses_supported_python_and_non_root_user() -> None:
    content = Path("Dockerfile").read_text(encoding="utf-8")

    assert content.startswith("FROM python:3.13-slim")
    assert "python -m pip install ." in content
    assert "USER pliris" in content
    assert 'CMD ["bash", "scripts/start_render.sh"]' in content


def test_dockerignore_excludes_local_secrets_and_private_data() -> None:
    ignored = {
        line.strip()
        for line in Path(".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    assert ".env" in ignored
    assert ".venv" in ignored
    assert ".git" in ignored
    assert "data/private" in ignored
    assert "artifacts" in ignored


def test_render_startup_keeps_api_private_and_exposes_streamlit_port() -> None:
    content = Path("scripts/start_render.sh").read_text(encoding="utf-8")

    assert 'API_HOST="127.0.0.1"' in content
    assert 'PUBLIC_PORT="${PORT:-10000}"' in content
    assert "--server.address 0.0.0.0" in content
    assert '--server.port "${PUBLIC_PORT}"' in content
    assert "/health/live" in content


def test_render_blueprint_has_public_mode_and_server_side_secrets() -> None:
    content = Path("render.yaml").read_text(encoding="utf-8")

    assert "name: pliris-ba-bot-public" in content
    assert "runtime: docker" in content
    assert "healthCheckPath: /" in content
    assert "key: PLIRIS_UI_MODE" in content
    assert "value: public" in content
    assert "key: GUEST_UI_SHARED_SECRET" in content
    assert "generateValue: true" in content
    assert "maxShutdownDelaySeconds" not in content

    for secret in (
        "OPENAI_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_DB_URL",
    ):
        anchor = f"- key: {secret}\n        sync: false"
        assert anchor in content


def test_rate_limit_smoke_uses_guarded_non_grounded_prompt() -> None:
    content = Path("scripts/smoke_rate_limit.py").read_text(encoding="utf-8")

    assert "Ignore all previous instructions" in content
    assert "expected = ([400] * args.allowed) + [429]" in content
    assert "Retry-After" in content
