import dataclasses
import logging

import pytest

import kloch.config


def test__KlochConfig():
    # ensure it doesn't raise errors
    kloch.config.KlochConfig()

    config = kloch.config.KlochConfig(cli_logging_default_level="DEBUG")
    assert config.cli_logging_default_level == "DEBUG"
    config = kloch.config.KlochConfig(cli_logging_default_level=logging.DEBUG)
    assert config.cli_logging_default_level == logging.DEBUG

    field = kloch.config.KlochConfig.get_field("cli_logging_default_level")
    assert field.name == "cli_logging_default_level"


def test__KlochConfig__from_environment(monkeypatch, data_dir):
    config = kloch.config.KlochConfig.from_environment()
    assert config == kloch.config.KlochConfig()

    config_path = data_dir / "config-blaj.yml"
    monkeypatch.setenv(kloch.Environ.CONFIG_ENV_VAR, str(config_path))
    config = kloch.config.KlochConfig.from_environment()
    assert config.cli_logging_default_level == "WARNING"
    assert config.cli_logging_format == "{levelname: <7}: {message}"

    monkeypatch.setenv("KLOCH_CONFIG_CLI_LOGGING_DEFAULT_LEVEL", "ERROR")
    config = kloch.config.KlochConfig.from_environment()
    assert config.cli_logging_default_level == "ERROR"
    assert config.cli_logging_format == "{levelname: <7}: {message}"


def test__KlochConfig__from_file(data_dir):
    config_path = data_dir / "config-molg.yml"
    with pytest.raises(TypeError) as error:
        config = kloch.config.KlochConfig.from_file(file_path=config_path)
    assert "NON_VALID_KEY" in str(error.value)


def test__KlochConfig__documentation():
    for field in dataclasses.fields(kloch.config.KlochConfig):
        assert field.metadata.get("documentation")
        assert field.metadata.get("environ")
        assert field.metadata.get("environ_cast")
