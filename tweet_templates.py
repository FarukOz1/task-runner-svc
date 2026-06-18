"""
NebulaLive V1 - Tweet Şablonları

AI maliyeti olmadan, hazır şablonlarla Türkçe tweet metni üretiyoruz.
scoring_side artık API'den doğrudan geliyor ("home"/"away"), skor
string'ini parse edip kim önde diye tahmin etmemize gerek yok.
"""

from __future__ import annotations

from event_detector import GoalEvent


def build_goal_tweet(event: GoalEvent) -> str:
    scoring_team = event.home if event.scoring_side == "home" else event.away

    if event.sub_type == "own-goal":
        headline = f"⚽ GOL! {event.player_name} kendi kalesine attı, {scoring_team} öne geçti!"
    else:
        headline = f"⚽ GOOOOOL! {scoring_team} için {event.player_name}!"

    tags = "#NebulaLive"
    if event.hashtags:
        tags = f"{tags} {event.hashtags}"

    tweet = (
        f"{headline}\n\n"
        f"{event.minute}' dakika\n"
        f"{event.home} {event.score} {event.away}\n\n"
        f"{tags}"
    )
    return tweet
