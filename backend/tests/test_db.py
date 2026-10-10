import ssl

from app.config import Settings
from app.db import _ssl_context


def test_ssl_disabled():
    assert _ssl_context(Settings(db_ssl="disable")) is None


def test_verify_ca_checks_the_chain_but_not_the_hostname():
    ctx = _ssl_context(Settings(db_ssl="verify-ca"))
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert not ctx.check_hostname
    # Cloud SQL server certificates have no Authority Key Identifier.
    assert not ctx.verify_flags & ssl.VERIFY_X509_STRICT


def test_require_encrypts_without_verifying():
    ctx = _ssl_context(Settings(db_ssl="require"))
    assert ctx.verify_mode == ssl.CERT_NONE
