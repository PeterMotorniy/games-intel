from __future__ import annotations

from games_intel.kafka.logging import sanitize_error_message


def test_sanitize_omits_html_tags() -> None:
    assert sanitize_error_message("<script>alert(1)</script>") == "html omitted"
    assert sanitize_error_message("broken <div>page") == "html omitted"


def test_sanitize_redacts_secrets_in_text() -> None:
    cleaned = sanitize_error_message("upstream api_key=sk-live-123 failed")
    assert "sk-live-123" not in cleaned
    assert "[redacted]" in cleaned


def test_sanitize_redacts_query_api_keys() -> None:
    cleaned = sanitize_error_message(
        "GET https://example.test/search?part=snippet&key=secret-query-value"
    )
    assert "secret-query-value" not in cleaned
    assert "key=[redacted]" in cleaned
