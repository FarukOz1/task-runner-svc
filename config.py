"""
NebulaLive V1 - Konfigürasyon

Bu dosyada:
- Hangi maçların izleneceği (watchlist)
- Kaç saniyede bir kontrol yapılacağı
- Veritabanı yolu
gibi ayarlar tutulur.

Watchlist ve dry_run bayrağı artık runtime_config.json'dan okunuyor (kod
değil, veri) - böylece docs/index.html panelindeki "Watchlist Yönetimi" ve
"Canlı Paylaşım" bölümleri, GitHub API üzerinden bu dosyayı güncelleyerek
otomasyonu koda dokunmadan yönetebiliyor.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class WatchedMatch:
    match_id: str          # Maçkolik'teki benzersiz kod (iddaa kodu vb.)
    home: str               # Ev sahibi takım adı (görüntüleme amaçlı)
    away: str               # Deplasman takım adı (görüntüleme amaçlı)
    active: bool = True     # False ise worker bu maçı atlar
    hashtags: str = ""      # "#FBvKNY #FenerinMaçıVar" gibi, tweet sonuna eklenir


_RUNTIME_CONFIG_PATH = Path(__file__).resolve().parent / "runtime_config.json"

with open(_RUNTIME_CONFIG_PATH, encoding="utf-8") as _f:
    _runtime = json.load(_f)

WATCHLIST: List[WatchedMatch] = [WatchedMatch(**m) for m in _runtime["watchlist"]]

# Bulut otomasyonunun (GitHub Actions) gerçekten X'e paylaşım yapıp yapmayacağı.
# Panel üzerinden "Canlı Paylaşımı Aç" (çok adımlı onaylı) butonuyla değiştirilir.
DRY_RUN_CLOUD: bool = _runtime["dry_run"]

# Kaç saniyede bir Maçkolik kontrol edilecek
POLL_INTERVAL_SECONDS = 15

# Dedup / state veritabanı (SQLite dosyası)
DB_PATH = "nebulalive.db"

# Sabit gol animasyonu (her golde aynı dosya kullanılacak).
# X'e yüklenmeden önce prepare_video.py ile bir kez hazırlanmış (1080p, H.264)
# sürümünü kullan - orijinal 4K dosyayı DOĞRUDAN kullanma.
GOAL_VIDEO_PATH = "assets/NebulaGol_1080p.mp4"

# Maçkolik istek ayarları
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
