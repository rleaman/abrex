"""Bootstrap tests for package import and the public logging helper."""

import logging

import abbr_resolver


def test_package_is_importable() -> None:
    assert callable(abbr_resolver.configure_logging)


def test_configure_logging_accepts_named_level() -> None:
    abbr_resolver.configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG
