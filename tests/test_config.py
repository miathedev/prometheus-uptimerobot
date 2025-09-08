"""Tests for configuration and utility functions."""

import os
import tempfile
from configparser import ConfigParser
from unittest.mock import patch

from ws.prometheus_uptimerobot.web import (DEFAULT_HOST, DEFAULT_PORT,
                                           get_api_key, load_config,
                                           parse_arguments)


class TestConfiguration:
    """Test cases for configuration functions."""

    def test_parse_arguments_defaults(self):
        """Test argument parsing with defaults."""
        with patch("sys.argv", ["script.py"]):
            args = parse_arguments()
            assert args.host == DEFAULT_HOST
            assert args.port == DEFAULT_PORT
            assert args.config is None

    def test_parse_arguments_custom_values(self):
        """Test argument parsing with custom values."""
        test_args = [
            "script.py",
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "--config",
            "/path/to/config.ini",
        ]

        with patch("sys.argv", test_args):
            args = parse_arguments()
            assert args.host == "127.0.0.1"
            assert args.port == 8080
            assert args.config == "/path/to/config.ini"

    def test_parse_arguments_port_validation(self):
        """Test that port argument accepts integers."""
        test_args = ["script.py", "--port", "9999"]

        with patch("sys.argv", test_args):
            args = parse_arguments()
            assert args.port == 9999
            assert isinstance(args.port, int)

    def test_load_config_success(self):
        """Test successful config loading."""
        config_content = """
[default]
api_key = ur12345-test-key
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(config_content)
            f.flush()

            try:
                config = load_config(f.name)
                assert config is not None
                assert isinstance(config, ConfigParser)
                assert config.get("default", "api_key") == "ur12345-test-key"
            finally:
                os.unlink(f.name)

    def test_load_config_file_not_found(self):
        """Test config loading with non-existent file."""
        config = load_config("/non/existent/file.ini")
        assert config is not None  # ConfigParser doesn't fail on missing files

        # But it should be empty
        assert len(config.sections()) == 0

    def test_load_config_with_tilde_expansion(self):
        """Test config loading with tilde expansion."""
        with patch("os.path.expanduser") as mock_expand:
            mock_expand.return_value = "/home/user/config.ini"

            with patch("configparser.ConfigParser.read") as mock_read:
                load_config("~/config.ini")
                mock_expand.assert_called_once_with("~/config.ini")
                mock_read.assert_called_once_with("/home/user/config.ini")

    @patch("ws.prometheus_uptimerobot.web.logger")
    def test_load_config_with_exception(self, mock_logger):
        """Test config loading with exception."""
        with patch(
            "configparser.ConfigParser.read", side_effect=Exception("Config error")
        ):
            config = load_config("/some/path/config.ini")
            assert config is None
            mock_logger.error.assert_called_once()

    def test_get_api_key_from_environment(self):
        """Test getting API key from environment variable."""
        test_key = "ur12345-env-key"

        with patch.dict(os.environ, {"UPTIMEROBOT_API_KEY": test_key}):
            api_key = get_api_key(None)
            assert api_key == test_key

    def test_get_api_key_from_config(self):
        """Test getting API key from config file."""
        config = ConfigParser()
        config.add_section("default")
        config.set("default", "api_key", "ur12345-config-key")

        # Make sure environment variable is not set
        with patch.dict(os.environ, {}, clear=True):
            api_key = get_api_key(config)
            assert api_key == "ur12345-config-key"

    def test_get_api_key_environment_priority(self):
        """Test that environment variable takes priority over config."""
        env_key = "ur12345-env-key"
        config_key = "ur12345-config-key"

        config = ConfigParser()
        config.add_section("default")
        config.set("default", "api_key", config_key)

        with patch.dict(os.environ, {"UPTIMEROBOT_API_KEY": env_key}):
            api_key = get_api_key(config)
            assert api_key == env_key

    def test_get_api_key_no_sources(self):
        """Test getting API key when no sources are available."""
        with patch.dict(os.environ, {}, clear=True):
            api_key = get_api_key(None)
            assert api_key is None

    def test_get_api_key_config_missing_section(self):
        """Test getting API key from config with missing section."""
        config = ConfigParser()
        # No default section

        with patch.dict(os.environ, {}, clear=True):
            api_key = get_api_key(config)
            assert api_key is None

    def test_get_api_key_config_missing_key(self):
        """Test getting API key from config with missing key."""
        config = ConfigParser()
        config.add_section("default")
        # No api_key in default section

        with patch.dict(os.environ, {}, clear=True):
            api_key = get_api_key(config)
            assert api_key is None

    def test_get_api_key_empty_environment_variable(self):
        """Test getting API key with empty environment variable."""
        config = ConfigParser()
        config.add_section("default")
        config.set("default", "api_key", "ur12345-config-key")

        with patch.dict(os.environ, {"UPTIMEROBOT_API_KEY": ""}):
            # Empty string is falsy, should fall back to config
            api_key = get_api_key(config)
            assert api_key == "ur12345-config-key"

    def test_get_api_key_whitespace_only_environment(self):
        """Test getting API key with whitespace-only environment variable."""
        config = ConfigParser()
        config.add_section("default")
        config.set("default", "api_key", "ur12345-config-key")

        with patch.dict(os.environ, {"UPTIMEROBOT_API_KEY": "   "}):
            # Whitespace-only should be considered valid
            api_key = get_api_key(config)
            assert api_key == "   "


class TestConfigFileIntegration:
    """Integration tests for configuration file handling."""

    def test_complete_config_workflow(self):
        """Test complete configuration workflow."""
        config_content = """
[default]
api_key = ur12345-integration-test
timeout = 60

[logging]
level = DEBUG
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(config_content)
            f.flush()

            try:
                # Load config
                config = load_config(f.name)
                assert config is not None

                # Get API key
                with patch.dict(os.environ, {}, clear=True):
                    api_key = get_api_key(config)
                    assert api_key == "ur12345-integration-test"

                # Verify other sections are accessible
                assert config.has_section("logging")
                assert config.get("logging", "level") == "DEBUG"

            finally:
                os.unlink(f.name)

    def test_config_with_comments(self):
        """Test configuration file with comments."""
        config_content = """
# This is a comment
[default]
# API key from UptimeRobot
api_key = ur12345-commented-key
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(config_content)
            f.flush()

            try:
                config = load_config(f.name)
                assert config is not None

                with patch.dict(os.environ, {}, clear=True):
                    api_key = get_api_key(config)
                    assert api_key == "ur12345-commented-key"

            finally:
                os.unlink(f.name)
