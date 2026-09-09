from __future__ import annotations

from games_intel.adapters.youtube.captions import parse_caption_payload, select_caption_track
from games_intel.adapters.youtube.duration import coerce_duration_seconds, parse_iso8601_duration


def test_parses_hours_minutes_seconds() -> None:
    assert parse_iso8601_duration("PT1H2M3S") == 3723
    assert parse_iso8601_duration("PT3M") == 180
    assert parse_iso8601_duration("PT180S") == 180
    assert parse_iso8601_duration("PT1M30S") == 90


def test_invalid_duration_is_none() -> None:
    assert parse_iso8601_duration("not-a-duration") is None
    assert parse_iso8601_duration("") is None


def test_coerce_duration_from_extractor() -> None:
    assert coerce_duration_seconds(2400) == 2400
    assert coerce_duration_seconds(90.9) == 90
    assert coerce_duration_seconds("PT3M") == 180
    assert coerce_duration_seconds(True) is None


def test_select_caption_prefers_manual_english_json3() -> None:
    chosen = select_caption_track(
        {
            "subtitles": {
                "ru": [{"ext": "vtt", "url": "https://example.test/ru.vtt"}],
                "en": [
                    {"ext": "srv1", "url": "https://example.test/en.srv1"},
                    {"ext": "json3", "url": "https://example.test/en.json3"},
                ],
            },
            "automatic_captions": {
                "en": [{"ext": "json3", "url": "https://example.test/auto.json3"}],
            },
        }
    )
    assert chosen == ("en", "json3", "https://example.test/en.json3")


def test_select_caption_skips_live_chat_html() -> None:
    chosen = select_caption_track(
        {
            "subtitles": {
                "live_chat": [{"ext": "html", "url": "https://example.test/live.html"}],
            },
            "automatic_captions": {
                "en": [{"ext": "vtt", "url": "https://example.test/en.vtt"}],
            },
        }
    )
    assert chosen == ("en", "vtt", "https://example.test/en.vtt")


def test_select_caption_none_when_only_live_chat() -> None:
    chosen = select_caption_track(
        {
            "subtitles": {
                "live_chat": [{"ext": "html", "url": "https://example.test/live.html"}],
            }
        }
    )
    assert chosen is None


def test_parse_html_payload_is_empty() -> None:
    html = b"<!DOCTYPE html><html><body>not captions</body></html>"
    assert parse_caption_payload("html", html) == ""
    assert parse_caption_payload("json3", html) == ""


def test_parse_json3_and_vtt() -> None:
    json3 = b'{"events":[{"segs":[{"utf8":"hello "},{"utf8":"world"}]}]}'
    assert parse_caption_payload("json3", json3) == "hello world"
    vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n<c>hi</c> there\n"
    assert parse_caption_payload("vtt", vtt) == "hi there"
