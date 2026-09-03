import pytest
from src.providers.patreon import PatreonProvider
from src.providers.loverslab import LoversLabProvider

def test_patreon_post_id_extraction():
    url1 = "https://www.patreon.com/posts/wickedwhims-v180-102938475"
    assert PatreonProvider.extract_post_id(url1) == "102938475"

    url2 = "https://www.patreon.com/posts/102938475"
    assert PatreonProvider.extract_post_id(url2) == "102938475"

    url3 = "https://patreon.com/posts/12345?extra=param"
    assert PatreonProvider.extract_post_id(url3) == "12345"

def test_loverslab_provider_init():
    provider = LoversLabProvider()
    assert provider.provider_name == "loverslab"
    assert provider.base_url == "https://www.loverslab.com"
    assert "161-the-sims-4" in provider.category_url
