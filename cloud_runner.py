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
import os
import time
from datetime import datetime, timezone

import requests

from config import WATCHLIST, POLL_INTERVAL_SECONDS, GOAL_VIDEO_PATH, DRY_RUN_CLOUD
from event_detector import find_new_goals
from tweet_templates import build_goal_tweet
from state_store import init_db, mark_event_published

# Tetikleme artık GitHub'ın native cron'una değil, cron-job.org'un
# workflow_dispatch çağrısına dayanıyor ve workflow'da
# "concurrency: cancel-in-progress: false" var - yani üst üste binen bir
# tetikleme ATLANMIYOR, sıraya giriyor. Bu yüzden süreyi 5 dakikalık
# tetikleme aralığına yakın tutup (checkout/pip/commit ek yüküne ~30sn pay
# bırakarak) çalışmalar arasındaki boş (kontrolsüz) süreyi minimuma
# indiriyoruz - bir golün fark edilmeden geçtiği pencereyi daraltmak için.
RUN_DURATION_SECONDS = 270  # 4.5 dakika
STATUS_PATH = "status.json"
MAX_LOG_ENTRIES = 80


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _compute_minute(match_start_time_ms: int) -> int:
    """
    Maçkolik'te ayrı bir "şu an kaçıncı dakika" alanı yok - sadece maç
    başlama saati var. Devre arası/uzatma dakikalarını ayırt etmeden,
    başlangıçtan bu yana geçen dakikayı hesaplıyoruz (yaklaşık).
    """
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    minute = int((now_ms - match_start_time_ms) // 60000)
    return max(minute, 0)


def _log(log: list, level: str, message: str) -> None:
    log.append({"time": _now_iso(), "level": level, "message": message})
    print(f"[{level.upper()}] {message}", flush=True)


def _get_access_token_cached(cache: dict) -> str:
    """
    Bir çalıştırma (run) boyunca en fazla BİR KEZ token yeniler (refresh_token
    tek kullanımlık olduğu için birden fazla golde tekrar tekrar yenilemek
    onu boşa harcar/bozar). İlk çağrıda yeniler, sonrakilerde önbellekten döner.
    """
    if "token" not in cache:
        from x_publisher import get_fresh_access_token
        cache["token"] = get_fresh_access_token()
    return cache["token"]


def _poll_once(log: list, live_scores: dict, match_start_times: dict, match_states: dict, live_minutes: dict, access_token_cache: dict) -> None:
    for match in WATCHLIST:
        if not match.active:
            continue

        try:
            new_goals, current_score, start_time, match_state = find_new_goals(match.match_id, match.home, match.away, match.hashtags)
        except Exception as e:
            _log(log, "error", f"{match.home} - {match.away}: {type(e).__name__}: {e}")
            continue

        live_scores[match.match_id] = current_score
        if start_time is not None:
            match_start_times[match.match_id] = start_time
            live_minutes[match.match_id] = _compute_minute(start_time)
        if match_state is not None:
            match_states[match.match_id] = match_state

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
                    access_token = _get_access_token_cached(access_token_cache)
                    tweet_id = publish_goal_post(tweet_text, video_path=GOAL_VIDEO_PATH, access_token=access_token)
                    mark_event_published(event.event_id, event.match_id, "GOAL", tweet_id=tweet_id)
                    _log(log, "success", f"Tweet paylaşıldı: {tweet_id}")
                except XPublisherError as e:
                    _log(log, "error", f"X'e paylaşılamadı: {e}")


def _write_status(log: list, poll_count: int, run_started_at: str, live_scores: dict, match_start_times: dict, match_states: dict, live_minutes: dict) -> None:
    status = {
        "last_updated": _now_iso(),
        "run_started_at": run_started_at,
        "poll_interval_seconds": POLL_INTERVAL_SECONDS,
        "poll_count": poll_count,
        "dry_run": DRY_RUN_CLOUD,
        "watchlist": [
            {
                "match_id": m.match_id,
                "home": m.home,
                "away": m.away,
                "active": m.active,
                "hashtags": m.hashtags,
                "score": live_scores.get(m.match_id),
                "match_start_time": match_start_times.get(m.match_id),
                "match_state": match_states.get(m.match_id),
                "minute": live_minutes.get(m.match_id),
            }
            for m in WATCHLIST
        ],
        "recent_log": log[-MAX_LOG_ENTRIES:],
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def _trigger_next_run() -> None:
    """
    Harici bir cron servisine (cron-job.org) bağımlı kalmak yerine, her
    çalışma kendi bitişinde GitHub'ın kendiliğinden sağladığı GITHUB_TOKEN
    ile bir sonraki çalışmayı KENDİSİ tetikler (self-chaining) - böylece
    üçüncü parti bir servisin çökmesi/durması sürekli izlemeyi kesmez.
    Native "schedule" cron'u (*/5 dakika) ise sadece bu zincir bir şekilde
    kırılırsa (ör. bu çalışma beklenmedik şekilde çökerse) devreye giren
    bir yedek/güvenlik ağı olarak workflow'da kalmaya devam ediyor.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("[UYARI] GITHUB_TOKEN/GITHUB_REPOSITORY yok, self-chaining atlandı.", flush=True)
        return
    try:
        resp = requests.post(
            f"https://api.github.com/repos/{repo}/actions/workflows/nebulalive.yml/dispatches",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={"ref": "main"},
            timeout=15,
        )
        if resp.status_code == 204:
            print("[BİLGİ] Bir sonraki çalışma tetiklendi (self-chaining).", flush=True)
        else:
            print(f"[UYARI] Self-chaining tetikleme başarısız: {resp.status_code} - {resp.text[:200]}", flush=True)
    except requests.exceptions.RequestException as e:
        print(f"[UYARI] Self-chaining tetikleme hatası: {e}", flush=True)


def main() -> None:
    init_db()
    log: list = []
    live_scores: dict = {}
    match_start_times: dict = {}
    match_states: dict = {}
    live_minutes: dict = {}
    access_token_cache: dict = {}
    run_started_at = _now_iso()
    start = time.monotonic()
    cycle = 0

    while time.monotonic() - start < RUN_DURATION_SECONDS:
        cycle += 1
        try:
            _poll_once(log, live_scores, match_start_times, match_states, live_minutes, access_token_cache)
        except Exception as e:
            _log(log, "error", f"cloud_runner döngü {cycle}: {type(e).__name__}: {e}")
        _write_status(log, cycle, run_started_at, live_scores, match_start_times, match_states, live_minutes)
        time.sleep(POLL_INTERVAL_SECONDS)

    _write_status(log, cycle, run_started_at, live_scores, match_start_times, match_states, live_minutes)
    print(f"[BILGI] cloud_runner tamamlandi ({cycle} kontrol yapildi).", flush=True)
    _trigger_next_run()


if __name__ == "__main__":
    main()
