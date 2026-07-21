class Addon:
    _settings = {}

    def getSettingBool(self, k): return bool(self._settings.get(k, False))
    def getSettingInt(self, k): return int(self._settings.get(k, 0))
    def getSettingString(self, k): return str(self._settings.get(k, ""))
    def getAddonInfo(self, k): return "/tmp/csfd_profile" if k == "profile" else ""
