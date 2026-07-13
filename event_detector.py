"""
NebulaLive V1 - Event Detector (v2 - key-events tabanlı)

key-events endpoint'i maçın başından o ana kadar TÜM olayları döner
(sadece "yeni" olanları değil). Bu yüzden mantık şöyle:

  1) Her poll'de tam listeyi çek.
  2) Listedeki her "goal" tipli olay için benzersiz bir event_id üret
     (match_id + dakika + oyuncu + skor kombinasyonu).
  3) Bu event_id daha önce görülmemişse (state_store'da yoksa) -> yeni gol.
  4) Görülmüşse atla (dedup).

Eski (v1) skor-diff mantığına göre çok daha güvenilir çünkü API bize zaten
"bu bir gol" diyor - biz skor artışından tahmin etmiyoruz.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mackolik_client import KeyEvent, fetch_key_events, MackolikClientError
from state_store import is_event_published


@dataclass
class GoalEvent:
    match_id: str
    home: str
    away: str
    score: str            # "1-0" gibi güncel skor
    minute: str
    scoring_side: str     # "home" veya "away"
    player_name: str
    event_id: str          # dedup için benzersiz kimlik
    sub_type: str = ""     # "goal", "penalty-goal", "own-goal" vb.
    hashtags: str = ""     # "#FBvKNY #FenerinMaçıVar" gibi, maça özel


def _make_event_id(match_id: str, ev: KeyEvent) -> str:
    # NOT: oyuncu adı bilerek event_id'ye dahil edilmiyor - Maçkolik golü
    # ilk gösterdiğinde oyuncu adı birkaç saniye boş kalabiliyor, sonradan
    # doluyor. Ad event_id'nin parçası olsaydı, ad değiştiğinde event_id de
    # değişir ve dedup bunu "yeni gol" sanıp aynı golü iki kez paylaşırdı.
    return f"{match_id}-{ev.time_min}-{ev.score}"


def find_new_goals(match_id: str, home_name: str, away_name: str, hashtags: str = "") -> tuple[list[GoalEvent], str, Optional[int], Optional[str]]:
    """
    Maçın güncel key-events listesini çeker, henüz paylaşılmamış gol
    event'lerini, maçın GÜNCEL SKORUNU, BAŞLAMA SAATİNİ (epoch ms) ve
    DURUMUNU ("liveGame"/"postGame") döner (canlı panelde skor + dakika +
    "Maç Sonu" rozeti göstermek için). Birden fazla yeni gol varsa (ör.
    worker bir süre çalışmadıysa) hepsini sırayla döner. Hiç gol yoksa skor
    "0-0" olarak döner.
    """
    try:
        result = fetch_key_events(match_id)
    except MackolikClientError as e:
        print(f"[HATA] key-events çekilemedi (match_id={match_id}): {e}")
        return [], "0-0", None, None

    events = result.events
    new_goals: list[GoalEvent] = []
    current_score = "0-0"
    for ev in events:
        if not ev.is_goal:
            continue
        if not ev.score or not ev.time_min:
            # Beklenmeyen/eksik veri - güvenli tarafta kal, atla.
            continue

        # Oyuncu adı henüz gelmemiş olsa bile skor güvenilir - canlı skoru
        # her gol event'inde güncelle (döngü sonunda en sonuncusu kalır).
        current_score = ev.score

        event_id = _make_event_id(match_id, ev)
        if is_event_published(event_id):
            continue

        if not ev.player_name:
            # Maçkolik golü ilk anda oyuncu adı olmadan gösterebiliyor, ad
            # birkaç saniye içinde beliriyor. event_id sabit kaldığı için
            # (ada bağlı değil) burada atlamak güvenli - bir sonraki pollde
            # ad gelmişse yakalanır, dedup bozulmaz/çift paylaşım olmaz.
            print(f"[BİLGİ] {home_name} - {away_name}: gol tespit edildi ({ev.time_min}', {ev.score}), oyuncu adı henüz gelmedi - bekleniyor")
            continue

        new_goals.append(
            GoalEvent(
                match_id=match_id,
                home=home_name,
                away=away_name,
                score=ev.score,
                minute=ev.time_min,
                scoring_side=ev.position or "",
                player_name=ev.player_name,
                event_id=event_id,
                sub_type=ev.sub_type or "",
                hashtags=hashtags,
            )
        )

    return new_goals, current_score, result.match_start_time, result.match_state
