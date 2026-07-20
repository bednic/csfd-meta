from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Person:
    name: str
    role: Optional[str] = None      # character name, for actors
    thumb: Optional[str] = None


@dataclass
class Artwork:
    url: str
    kind: str                        # "poster" | "fanart"


@dataclass
class SearchResult:
    csfd_id: str
    url: str
    title: str
    year: Optional[int] = None
    is_series: bool = False
    thumb: Optional[str] = None


@dataclass
class CsfdFilm:
    csfd_id: str
    url: str
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    plot: Optional[str] = None
    tagline: Optional[str] = None
    runtime: Optional[int] = None            # minutes
    countries: list = field(default_factory=list)
    genres: list = field(default_factory=list)
    rating: Optional[float] = None           # 0..10
    votes: Optional[int] = None
    cast: list = field(default_factory=list)          # list[Person]
    directors: list = field(default_factory=list)     # list[Person]
    writers: list = field(default_factory=list)       # list[Person]
    artwork: list = field(default_factory=list)       # list[Artwork]
    is_series: bool = False


@dataclass
class CsfdEpisode:
    csfd_id: str
    url: str
    title: str
    season: int
    episode: int
    plot: Optional[str] = None
    aired: Optional[str] = None              # ISO date "YYYY-MM-DD"
