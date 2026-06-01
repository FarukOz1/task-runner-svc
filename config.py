"""
NebulaLive V1 - Konfigürasyon

Bu dosyada:
- Hangi maçların izleneceği (watchlist)
- Kaç saniyede bir kontrol yapılacağı
- Veritabanı yolu
gibi ayarlar tutulur.

NOT: Maçkolik'in gerçek match_id / iddaa kodu değerlerini kendin doldurmalısın.
Bunları bulmanın en kolay yolu: mackolik.com sitesinde ilgili maça tıkladığında
URL'de veya sayfa kaynağında geçen sayısal kodu almak.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class WatchedMatch:
    match_id: str          # Maçkolik'teki benzersiz kod (iddaa kodu vb.)
    home: str               # Ev sahibi takım adı (görüntüleme amaçlı)
    away: str               # Deplasman takım adı (görüntüleme amaçlı)
    active: bool = True     # False ise worker bu maçı atlar


# --- Buraya izlemek istediğin maçları ekle ---
# NOT: Aşağıdaki kayıtlar SADECE pipeline'ı uçtan uca test etmek için eklendi.
# Gerçek/canlı izleme için bunları kendi gerçek watchlist'inle değiştir.
WATCHLIST: List[WatchedMatch] = [
    # Bitti (0-0, hiç gol olmadı - sistem doğru şekilde hiçbir event üretmedi).
    WatchedMatch(match_id="15l316xw14qu9smdp59e4epsk", home="Botafogo RJ", away="Palmeiras", active=False),
    # Bitmiş test maçı (5 gol içeriyor, dedup zaten devrede - dry-run'da bir şey basmaz).
    WatchedMatch(match_id="ccpfjtmwynfe9w3nko8q4xus4", home="Başakşehir", away="Galatasaray", active=False),
]

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
