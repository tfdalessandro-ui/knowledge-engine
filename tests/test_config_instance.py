from config import Settings


def test_defaults_describe_the_original_instance(monkeypatch):
    for var in ("OSE_INSTANCE_NAME", "OSE_SERVICE_NAME", "OSE_PORT", "OSE_SMOKE_QUERY", "OSE_INSTANCE_BRANCH"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert (s.instance_name, s.service_name, s.port, s.instance_branch) == ("ose", "ose.service", 8000, "main")
    assert s.api_base_url == "http://127.0.0.1:8000"


def test_instance_env_sets_identity_and_env_keeps_tuning(tmp_path, monkeypatch):
    monkeypatch.delenv("OSE_HYBRID_ALPHA", raising=False)
    monkeypatch.delenv("OSE_SERVICE_NAME", raising=False)
    instance = tmp_path / "instance.env"
    instance.write_text("OSE_INSTANCE_NAME=sensalis\nOSE_SERVICE_NAME=ose-sensalis.service\nOSE_PORT=8010\n"
                        "OSE_INSTANCE_BRANCH=instance/sensalis\n")
    tuning = tmp_path / ".env"
    tuning.write_text("OSE_HYBRID_ALPHA=0.61\n")

    s = Settings(_env_file=(instance, tuning))

    assert s.service_name == "ose-sensalis.service"
    assert s.api_base_url == "http://127.0.0.1:8010"
    assert s.instance_branch == "instance/sensalis"
    assert s.hybrid_alpha == 0.61


def test_rewriting_env_does_not_lose_instance_identity(tmp_path, monkeypatch):
    # auto_tune.py overwrites .env wholesale on deploy.
    monkeypatch.delenv("OSE_SERVICE_NAME", raising=False)
    instance = tmp_path / "instance.env"
    instance.write_text("OSE_SERVICE_NAME=ose-sensalis.service\n")
    tuning = tmp_path / ".env"
    tuning.write_text("OSE_HYBRID_FUSION_MODE=weighted\nOSE_HYBRID_ALPHA=0.5\n")

    assert Settings(_env_file=(instance, tuning)).service_name == "ose-sensalis.service"


def test_real_environment_overrides_both_files(tmp_path, monkeypatch):
    instance = tmp_path / "instance.env"
    instance.write_text("OSE_PORT=8010\n")
    monkeypatch.setenv("OSE_PORT", "9999")
    assert Settings(_env_file=(instance, tmp_path / ".env")).port == 9999
