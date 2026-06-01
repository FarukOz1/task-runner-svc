"""
NebulaLive - Bulut Çalıştırıcı (GitHub Actions)

GitHub Actions'ta zamanlanmış (cron) workflow'lar en sık 5 dakikada bir
tetiklenebiliyor. Gerçek 15 saniyelik kontrol aralığını korumak için bu
script, her workflow çalıştığında YAKLAŞIK 4.5 DAKİKA BOYUNCA kendi içinde
POLL_INTERVAL_SECONDS'ta bir main.run_once() çağırıp uyur, sonra bir sonraki
zamanlanmış tetiklemeyle çakışmadan önce çıkar.

main.py'nin --dry-run/--once mantığından farklı olarak burada döngü main.py
içinde değil, bu dosyada - main.py'nin kendi sonsuz döngüsünü (systemd/VM
için tasarlanmış) GitHub Actions'ın "her çalıştırma en fazla X dakika sürsün"
modeline uyarlamak için.
"""
from __future__ import annotations

import time

from config import POLL_INTERVAL_SECONDS
from main import run_once, DRY_RUN_CLOUD

RUN_DURATION_SECONDS = 4.5 * 60  # bir sonraki 5 dakikalık tetiklemeyle çakışmasın


def main() -> None:
    start = time.monotonic()
    cycle = 0
    while time.monotonic() - start < RUN_DURATION_SECONDS:
        cycle += 1
        try:
            run_once(dry_run=DRY_RUN_CLOUD)
        except Exception as e:
            print(f"[HATA] cloud_runner dongu {cycle}: {type(e).__name__}: {e}", flush=True)
        time.sleep(POLL_INTERVAL_SECONDS)
    print(f"[BILGI] cloud_runner tamamlandi ({cycle} kontrol yapildi).", flush=True)


if __name__ == "__main__":
    main()
