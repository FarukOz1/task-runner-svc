"""
NebulaLive V1 - Maçkolik İstemcisi (v2 - gerçek endpoint)

Bu dosya www.mackolik.com'un kendi sitesinde kullandığı iç AJAX
endpoint'lerini çağırır (goapi.mackolik.com DEĞİL - o eski/kapalı görünüyor
ve robots.txt tarafından engelleniyor; bu endpoint'ler engellenmiyor).

Kullanılan endpoint'ler (tarayıcı Network sekmesinden bulundu):
  - key-events: https://www.mackolik.com/ajax/football/key-events
                ?ajaxViewName=events&matchId=<MATCH_ID>
    → gol, kart, oyuncu değişikliği gibi olayların listesi (isimli alanlarla,
      index tahmini YOK: type, score, position, timeMin, playerName)

  - gameStats:  https://www.mackolik.com/ajax/soccer/match/gameStats
                ?matchId=<MATCH_ID>
    → şut, top hakimiyeti gibi istatistikler (gol tespiti için gerekli değil,
      ileride istersen kullanılabilir)

DÜRÜST NOT: Bu endpoint'ler de resmi/dokümante değil, sitenin kendi
frontend'inin kullandığı iç API'ler. Herhangi bir zaman değişebilir.
Kullanım şartlarına uyup uymadığını sen değerlendiriyorsun.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT

KEY_EVENTS_URL = "https://www.mackolik.com/ajax/football/key-events"
GAME_STATS_URL = "https://www.mackolik.com/ajax/soccer/match/gameStats"


class MackolikClientError(Exception):
    pass


@dataclass
class KeyEvent:
    """Tek bir maç olayı (gol, kart, değişiklik vb.)."""
    type: str                      # "goal", "yellow_card", "substitution" vb.
    sub_type: Optional[str]
    score: Optional[str]           # "1-0" gibi, sadece gol event'lerinde dolu olur
    position: Optional[str]        # "home" veya "away"
    time_min: Optional[str]
    player_name: Optional[str]
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def is_goal(self) -> bool:
        return self.type == "goal"


@dataclass
class KeyEventsResult:
    events: list[KeyEvent]
    match_start_time: Optional[int]  # epoch ms (maç başlama saati - canlı dakika hesabı için)
    match_state: Optional[str]       # "liveGame", "postGame" vb.


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def fetch_key_events(match_id: str) -> KeyEventsResult:
    """
    Belirtilen maçın olay listesini (gol, kart, değişiklik...) ve maç
    başlama saatini (canlı dakika hesabı için) çeker. Olay listesi, maçın
    başından o ana kadar olan TÜM olayları içerir - yani her çağrıda tam
    liste gelir, sadece "yeni" olanlar değil. Dedup işini event_detector.py
    / state_store.py yapar.
    """
    params = {"ajaxViewName": "events", "matchId": match_id}
    try:
        resp = _session().get(KEY_EVENTS_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as e:
        raise MackolikClientError(f"key-events isteği başarısız (ağ hatası): {e}") from e

    if resp.status_code != 200:
        raise MackolikClientError(
            f"key-events beklenmeyen HTTP durumu: {resp.status_code} - {resp.text[:200]}"
        )

    try:
        payload = resp.json()
    except ValueError as e:
        raise MackolikClientError(f"key-events JSON parse edilemedi: {e}") from e

    if payload.get("status") != "success":
        raise MackolikClientError(f"key-events başarısız durum döndü: {payload}")

    data = payload.get("data", {})
    raw_events = data.get("keyEvents", [])

    events = []
    for e in raw_events:
        events.append(
            KeyEvent(
                type=e.get("type"),
                sub_type=e.get("subType"),
                score=e.get("score"),
                position=e.get("position"),
                time_min=e.get("timeMin"),
                player_name=e.get("playerName"),
                raw=e,
            )
        )
    return KeyEventsResult(
        events=events,
        match_start_time=data.get("matchStartTime"),
        match_state=data.get("matchState"),
    )


def fetch_match_state(match_id: str) -> dict:
    """
    Maçın genel durumunu döner (status: 'Playing'/'Finished' vb, startTime).
    Maç bitince otomasyonun o maçı izlemeyi durdurması için kullanılabilir.
    """
    params = {"matchId": match_id}
    try:
        resp = _session().get(GAME_STATS_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as e:
        raise MackolikClientError(f"gameStats isteği başarısız (ağ hatası): {e}") from e

    if resp.status_code != 200:
        raise MackolikClientError(
            f"gameStats beklenmeyen HTTP durumu: {resp.status_code} - {resp.text[:200]}"
        )

    try:
        payload = resp.json()
    except ValueError as e:
        raise MackolikClientError(f"gameStats JSON parse edilemedi: {e}") from e

    if payload.get("status") != "success":
        raise MackolikClientError(f"gameStats başarısız durum döndü: {payload}")

    return payload.get("data", {})


if __name__ == "__main__":
    # Hızlı manuel test: gerçek bir matchId ile çalıştır.
    # python mackolik_client.py <matchId>
    import sys

    test_match_id = sys.argv[1] if len(sys.argv) > 1 else "996prqhfc4sm6szbpqclc3jmc"
    print(f"key-events testi (matchId={test_match_id}):\n")
    result = fetch_key_events(test_match_id)
    for ev in result.events:
        print(ev)
    print(f"\nmatch_start_time: {result.match_start_time}, match_state: {result.match_state}")
    print("\ngameStats testi:\n")
    print(fetch_match_state(test_match_id))
