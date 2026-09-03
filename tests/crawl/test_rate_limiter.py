import time

from crawl.rate_limiter import PerDomainRateLimiter


def test_first_fetch_to_a_domain_does_not_wait():
    limiter = PerDomainRateLimiter(min_interval_s=1.0)
    slept = limiter.wait_if_needed("https://a.example.com/page")
    assert slept == 0.0


def test_second_fetch_to_same_domain_waits_out_the_interval():
    limiter = PerDomainRateLimiter(min_interval_s=0.2)
    limiter.wait_if_needed("https://a.example.com/page1")
    start = time.monotonic()
    limiter.wait_if_needed("https://a.example.com/page2")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.19  # allow tiny scheduler slack


def test_different_domains_do_not_wait_on_each_other():
    limiter = PerDomainRateLimiter(min_interval_s=5.0)
    limiter.wait_if_needed("https://a.example.com/page")
    start = time.monotonic()
    slept = limiter.wait_if_needed("https://b.example.com/page")
    elapsed = time.monotonic() - start
    assert slept == 0.0
    assert elapsed < 0.5


def test_waiting_long_enough_between_calls_avoids_a_second_wait():
    limiter = PerDomainRateLimiter(min_interval_s=0.1)
    limiter.wait_if_needed("https://a.example.com/page1")
    time.sleep(0.15)
    slept = limiter.wait_if_needed("https://a.example.com/page2")
    assert slept == 0.0
