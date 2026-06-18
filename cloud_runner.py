"""
NebulaLive - Bulut Çalıştırıcı (GitHub Actions)

GitHub Actions'ta zamanlanmış (cron) workflow'lar en sık 5 dakikada bir
tetiklenebiliyor. Gerçek 15 saniyelik kontrol aralığını korumak için bu
script, her workflow çalıştığında YAKLAŞIK 4.5 DAKİKA BOYUNCA kendi içinde
POLL_INTERVAL_SECONDS'ta bir watchlist'i kontrol edip uyur, sonra bir sonraki
zamanlanmış tetiklemeyle çakışmadan önce çıkar.

Ayrıca her turun sonucunu status.json'a yazar (izlenen maçlar + son kontrol
logları) - docs/index.html bu dosyayı GitHub'dan doğrudan okuyarak canlı
panel gösterir. Bu dosya main.py'nin run_once() mantığını burada kasıtlı
olarak tekrar yazıyor (import edip sarmalamak yerine) çünkü tek tek maç
sonuçlarını status.json için yapılandırılmış şekilde kaydetmemiz gerekiyor -
main.run_once() sadece print() basıyor, yapılandırılmış veri döndürmüyor.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from config import WATCHLIST, POLL_INTERVAL_SECONDS, GOAL_VIDEO_PATH, DRY_RUN_CLOUD
from event_detector import find_new_goals
from tweet_templates import build_goal_tweet
from state_store import init_db, mark_event_published

# 4.5 dakika + checkout/pip/commit ek yükü (~45-60sn) toplamda 5 dakikalık
# tetikleme aralığını AŞIYORDU - bu da GitHub'ın zamanlanmış (cron)
# tetiklemelerinin çakışma (concurrency) yüzünden sürekli atlanmasına neden
# oluyordu. 3 dakikaya indirerek gerçek bir boşluk bırakıyoruz.
RUN_DURATION_SECONDS = 3 * 60
STATUS_PATH = "status.json"
MAX_LOG_ENTRIES = 80


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _log(log: list, level: str, message: str) -> None:
    log.append({"time": _now_iso(), "level": level, "message": message})
    print(f"[{level.upper()}] {message}", flush=True)


def _poll_once(log: list) -> None:
    for match in WATCHLIST:
        if not match.active:
            continue

        try:
            new_goals = find_new_goals(match.match_id, match.home, match.away, match.hashtags)
        except Exception as e:
            _log(log, "error", f"{match.home} - {match.away}: {type(e).__name__}: {e}")
            continue

        if not new_goals:
            _log(log, "info", f"{match.home} - {match.away}: kontrol edildi, değişiklik yok")
            continue

        for event in new_goals:
            tweet_text = build_goal_tweet(event)
            _log(log, "goal", f"GOL! {event.home} {event.score} {event.away} ({event.minute}') - {event.player_name}")

            if DRY_RUN_CLOUD:
                mark_event_published(event.event_id, event.match_id, "GOAL", tweet_id=None)
                _log(log, "info", "[DRY-RUN] X'e gönderilmedi (test modu)")
            else:
                from x_publisher import publish_goal_post, XPublisherError

                try:
                    tweet_id = publish_goal_post(tweet_text, video_path=GOAL_VIDEO_PATH)
                    mark_event_published(event.event_id, event.match_id, "GOAL", tweet_id=tweet_id)
                    _log(log, "success", f"Tweet paylaşıldı: {tweet_id}")
                except XPublisherError as e:
                    _log(log, "error", f"X'e paylaşılamadı: {e}")


def _write_status(log: list, poll_count: int, run_started_at: str) -> None:
    status = {
        "last_updated": _now_iso(),
        "run_started_at": run_started_at,
        "poll_interval_seconds": POLL_INTERVAL_SECONDS,
        "poll_count": poll_count,
        "dry_run": DRY_RUN_CLOUD,
        "watchlist": [
            {"match_id": m.match_id, "home": m.home, "away": m.away, "active": m.active, "hashtags": m.hashtags}
            for m in WATCHLIST
        ],
        "recent_log": log[-MAX_LOG_ENTRIES:],
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def main() -> None:
    init_db()
    log: list = []
    run_started_at = _now_iso()
    start = time.monotonic()
    cycle = 0

    while time.monotonic() - start < RUN_DURATION_SECONDS:
        cycle += 1
        try:
            _poll_once(log)
        except Exception as e:
            _log(log, "error", f"cloud_runner döngü {cycle}: {type(e).__name__}: {e}")
        _write_status(log, cycle, run_started_at)
        time.sleep(POLL_INTERVAL_SECONDS)

    _write_status(log, cycle, run_started_at)
    print(f"[BILGI] cloud_runner tamamlandi ({cycle} kontrol yapildi).", flush=True)


if __name__ == "__main__":
    main()
