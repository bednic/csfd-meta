import os
import xbmcaddon
import xbmcvfs


class Settings:
    def __init__(self):
        self._addon = xbmcaddon.Addon()

    @property
    def prefer_original_title(self):
        return self._addon.getSettingBool("prefer_original_title")

    @property
    def cache_ttl_days(self):
        return max(1, self._addon.getSettingInt("cache_ttl_days") or 7)

    @property
    def max_artwork(self):
        return max(1, self._addon.getSettingInt("max_artwork") or 5)

    @property
    def debug(self):
        return self._addon.getSettingBool("debug")

    @property
    def profile_dir(self):
        path = xbmcvfs.translatePath(self._addon.getAddonInfo("profile"))
        cache = os.path.join(path, "cache")
        if not xbmcvfs.exists(cache):
            xbmcvfs.mkdirs(cache)
        return cache
