from crawl.canonicalize import canonicalize_url


def test_strips_tracking_params():
    assert canonicalize_url("https://example.com/page?utm_source=x&id=1") == "https://example.com/page?id=1"


def test_sorts_remaining_params_for_stable_dedup():
    a = canonicalize_url("https://example.com/page?b=2&a=1")
    b = canonicalize_url("https://example.com/page?a=1&b=2")
    assert a == b


def test_normalizes_http_to_https():
    assert canonicalize_url("http://example.com/page") == canonicalize_url("https://example.com/page")


def test_strips_www():
    assert canonicalize_url("https://www.example.com/page") == canonicalize_url("https://example.com/page")


def test_strips_trailing_slash():
    assert canonicalize_url("https://example.com/page/") == canonicalize_url("https://example.com/page")


def test_strips_fragment():
    assert canonicalize_url("https://example.com/page#section") == canonicalize_url("https://example.com/page")


def test_lowercases_host():
    assert canonicalize_url("https://EXAMPLE.com/page") == canonicalize_url("https://example.com/page")


def test_different_paths_are_not_conflated():
    assert canonicalize_url("https://example.com/a") != canonicalize_url("https://example.com/b")
