"""
NebulaLive V1 - Ana Worker

Akış (v2 - key-events tabanlı):
  1) Watchlist'teki her maç için Maçkolik'in key-events endpoint'ini çek.
  2) API'nin döndürdüğü gol event'leri arasından henüz paylaşılmamış
     olanları bul (event_detector.find_new_goals).
  3) Her yeni gol için: tweet metni oluştur, X'e gönder.
  4) Event'i "paylaşıldı" olarak işaretle (dedup).
  5) POLL_INTERVAL_SECONDS kadar bekle, tekrar et.

Çalıştırmadan önce:
  pip install -r requirements.txt
  config.py içindeki WATCHLIST'i gerçek matchId'lerle doldur
  (mackolik.com'da maç sayfasını aç, Network sekmesinde key-events isteğini
  bul, matchId parametresini oradan al).

Not: --dry-run modunda X'e gerçekten paylaşım yapılmaz, sadece konsola basılır.
Gerçek paylaşıma geçmeden önce mutlaka dry-run ile test et.
"""

from __future__ import annotations

import argparse
import sys
import time

# Windows'ta konsol kod sayfası UTF-8 olmayabilir (ör. cp1254); tweet
# metnindeki emoji basılırken UnicodeEncodeError ile çökmemesi için
# stdout'u UTF-8'e zorla (X'e giden metnin kendisini etkilemez).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import WATCHLIST, POLL_INTERVAL_SECONDS, GOAL_VIDEO_PATH
from event_detector import find_new_goals
from tweet_templates import build_goal_tweet
from state_store import init_db, mark_event_published


def run_once(dry_run: bool) -> None:
    for match in WATCHLIST:
        if not match.active:
            continue

        new_goals = find_new_goals(match.match_id, match.home, match.away)

        for event in new_goals:
            tweet_text = build_goal_tweet(event)

            if dry_run:
                print("=" * 50)
                print(f"[DRY-RUN] Şu tweet paylaşılacaktı:\n{tweet_text}")
                print(f"[DRY-RUN] Video: {GOAL_VIDEO_PATH}")
                print("=" * 50)
                mark_event_published(event.event_id, event.match_id, "GOAL", tweet_id=None)
            else:
                from x_publisher import publish_goal_post, XPublisherError

                try:
                    tweet_id = publish_goal_post(tweet_text, video_path=GOAL_VIDEO_PATH)
                    print(f"[BAŞARILI] Tweet paylaşıldı: {tweet_id}")
                    mark_event_published(event.event_id, event.match_id, "GOAL", tweet_id=tweet_id)
                except XPublisherError as e:
                    print(f"[HATA] X'e paylaşılamadı: {e}")
                    # Not: paylaşım başarısız olduysa event'i "paylaşıldı" işaretlemiyoruz,
                    # bir sonraki döngüde tekrar denenecek.


def main() -> None:
    parser = argparse.ArgumentParser(description="NebulaLive Gol Otomasyonu V1")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="X'e gerçekten paylaşım yapmadan sadece konsola bas (test için önerilir)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Sürekli döngü yerine sadece bir kez kontrol et ve çık",
    )
    args = parser.parse_args()

    init_db()

    if args.once:
        run_once(dry_run=args.dry_run)
        return

    print(f"NebulaLive worker başladı. Her {POLL_INTERVAL_SECONDS} saniyede bir kontrol edilecek.")
    print(f"Dry-run modu: {'AÇIK' if args.dry_run else 'KAPALI'}")
    while True:
        try:
            run_once(dry_run=args.dry_run)
        except Exception as e:
            # 7/24 çalışan bir serviste beklenmeyen tek bir hata (ağ kopması,
            # geçici DB kilidi vb.) tüm worker'ı çökertmemeli - logla, devam et.
            print(f"[HATA] Beklenmeyen hata, döngü devam ediyor: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
