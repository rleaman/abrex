"""Bootstrap tests for package import and the public logging helper."""

import logging

import abrex


def test_package_is_importable() -> None:
    assert callable(abrex.configure_logging)


def test_configure_logging_accepts_named_level() -> None:
    abrex.configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG
