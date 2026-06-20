import asyncio

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(scope="session", autouse=True)
def _warm_up_aiodns_resolver_thread():
    """aiodns.DNSResolver() spawns a background pycares thread on first use,
    regardless of what test triggers it (confirmed: happens even with zero
    integration code involved, from aiodns alone). Spawning it here, once,
    before any test's thread-leak baseline is captured, keeps it out of every
    individual test's "new threads since this test started" diff.
    """
    import aiodns

    loop = asyncio.new_event_loop()
    aiodns.DNSResolver(loop=loop)
    loop.close()
