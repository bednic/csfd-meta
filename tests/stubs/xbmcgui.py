class _InfoTag:
    def __init__(self):
        self.data = {}

    def setTitle(self, v): self.data["title"] = v
    def setOriginalTitle(self, v): self.data["originaltitle"] = v
    def setPlot(self, v): self.data["plot"] = v
    def setTagline(self, v): self.data["tagline"] = v
    def setYear(self, v): self.data["year"] = v
    def setDuration(self, v): self.data["duration"] = v
    def setGenres(self, v): self.data["genres"] = v
    def setCountries(self, v): self.data["countries"] = v
    def setRatings(self, v, defaultrating=""): self.data["ratings"] = (v, defaultrating)
    def setUniqueIDs(self, v, defaultuniqueid=""): self.data["uniqueids"] = (v, defaultuniqueid)
    def setCast(self, v): self.data["cast"] = v
    def setDirectors(self, v): self.data["directors"] = v
    def setWriters(self, v): self.data["writers"] = v
    def setSeason(self, v): self.data["season"] = v
    def setEpisode(self, v): self.data["episode"] = v
    def setFirstAired(self, v): self.data["aired"] = v
    def setMediaType(self, v): self.data["mediatype"] = v


class ListItem:
    def __init__(self, label="", offscreen=False):
        self.label = label
        self._tag = _InfoTag()
        self.art = {}
        self.available_art = []

    def getVideoInfoTag(self): return self._tag
    def setArt(self, d): self.art.update(d)
    def addAvailableArtwork(self, url, art_type=""): self.available_art.append((url, art_type))
