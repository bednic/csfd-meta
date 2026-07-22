import xbmcaddon
from kodi.settings import Settings


def test_relay_url_reads_setting():
    xbmcaddon.Addon._settings = {"relay_url": "http://nas:9753"}
    assert Settings().relay_url == "http://nas:9753"


def test_relay_url_defaults_to_empty_when_unset():
    xbmcaddon.Addon._settings = {}
    assert Settings().relay_url == ""
