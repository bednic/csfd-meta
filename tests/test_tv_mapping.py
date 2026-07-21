import xbmcplugin
from csfd.models import CsfdEpisode, CsfdFilm
from kodi.mapping import episode_to_listitem


def test_episode_maps_numbering_and_title():
    ep = CsfdEpisode(csfd_id="500", url="u", title="Pilot",
                     season=1, episode=1, aired="2001-09-23")
    li = episode_to_listitem(ep)
    tag = li.getVideoInfoTag().data
    assert tag["title"] == "Pilot"
    assert tag["season"] == 1
    assert tag["episode"] == 1
    assert tag["aired"] == "2001-09-23"
    assert tag["mediatype"] == "episode"
    assert tag["uniqueids"] == ({"csfd": "500"}, "csfd")


def test_episode_details_uses_episode_id(monkeypatch):
    from kodi import tv_scraper
    xbmcplugin.reset()
    # film() would derive the SERIES id (263138) from the url; episode_details
    # must override it with the episode's own id (417467), matching
    # getepisodelist's use of episodes._entity_id.
    monkeypatch.setattr(tv_scraper.csfd_film, "film",
                        lambda client, url, **kw: CsfdFilm(
                            csfd_id="263138", url=url, title="Zima se blizi"))
    url = "https://www.csfd.cz/film/263138-hra-o-truny/417467-zima-se-blizi/prehled/"
    tv_scraper.episode_details(1, {"url": url, "season": "1", "episode": "1"})
    _h, ok, li = xbmcplugin._resolved[-1]
    assert ok is True
    assert li.getVideoInfoTag().data["uniqueids"] == ({"csfd": "417467"}, "csfd")
