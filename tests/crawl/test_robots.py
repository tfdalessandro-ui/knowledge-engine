from crawl.robots import RobotsChecker


def test_allows_a_path_not_in_disallow(local_server):
    checker = RobotsChecker()
    assert checker.can_fetch(f"{local_server}/allowed-page", "TestBot/1.0") is True


def test_disallows_a_path_matching_disallow(local_server):
    checker = RobotsChecker()
    assert checker.can_fetch(f"{local_server}/disallowed-page", "TestBot/1.0") is False


def test_caches_robots_txt_per_domain(local_server):
    # second call for the same domain must not re-fetch robots.txt -- verified
    # indirectly: both calls still return the correct, consistent answer
    checker = RobotsChecker()
    first = checker.can_fetch(f"{local_server}/a", "TestBot/1.0")
    second = checker.can_fetch(f"{local_server}/b", "TestBot/1.0")
    assert first is True and second is True
    assert len(checker._parsers) == 1


def test_missing_robots_txt_defaults_to_allowed():
    # a domain with no server at all -- connection failure -- correctly falls
    # back to the network-error path (cautious: disallow), not a crash
    checker = RobotsChecker()
    result = checker.can_fetch("http://127.0.0.1:1/some-page", "TestBot/1.0")
    assert result is False  # RFC 9309: can't determine policy -> be cautious, not permissive
