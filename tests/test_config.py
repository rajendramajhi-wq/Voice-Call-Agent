from app.core.config import Settings


def test_allowed_origins_from_dotenv_csv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALLOWED_ORIGINS=http://localhost:8501,http://127.0.0.1:8501\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.allowed_origins == [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]



def test_allowed_origins_from_dotenv_json_array(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'ALLOWED_ORIGINS=["http://localhost:8501", "http://127.0.0.1:8501"]\n',
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.allowed_origins == [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]
