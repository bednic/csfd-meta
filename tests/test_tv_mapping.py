from csfd.models import CsfdEpisode
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
