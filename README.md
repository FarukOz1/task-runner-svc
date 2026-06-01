# NebulaLive Gol Otomasyonu — V1

Seçtiğin maçları Maçkolik üzerinden izleyip, gol geldiğinde hazır
`NebulaGol.mp4` videosu + Türkçe şablon tweet metniyle X'te otomatik
paylaşım yapan basit bir sistem.

## Önce oku — dürüst durum

- Kullanılan endpoint'ler (`www.mackolik.com/ajax/football/key-events`,
  `www.mackolik.com/ajax/soccer/match/gameStats`) **resmî/dokümante bir API
  değil** — sitenin kendi frontend'inin kullandığı iç AJAX çağrıları.
  Her an değişebilir/kapanabilir, garanti yok.
- Kullanım şartlarına uyup uymadığını **sen değerlendirmelisin** — bunu ben
  senin adına onaylayamam.
- X'e otomatik video+metin paylaşımı için uygun bir X Developer erişim
  seviyesi gerekir; bu benim kontrolümde değil, X'in güncel dokümantasyonuna
  bakman lazım.

## Kurulum

```bash
cd nebulalive
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`assets/NebulaGol.mp4` dosyasını (kendi hazır animasyonun) bu klasöre koy.

## 0. Adım: Videoyu X için hazırla (TEK SEFERLİK)

Senin video 4K (3840x2160). X en fazla 1920x1200 kabul ediyor ve üzerini
kendi tarafında sıkıştırıyor - kaliteyi kontrolde tutmak için önce sen indir:

```bash
python prepare_video.py assets/NebulaGol.mp4
```

Bu, `assets/NebulaGol_1080p.mp4` dosyasını üretir (1080p, H.264, AAC -
X'in gereksinimlerine uygun). `config.py` içindeki `GOAL_VIDEO_PATH` zaten
bu dosyayı gösteriyor. Bu adım GOL BAŞINA değil, TEK SEFERLİK yapılır -
otomasyon her golde bu aynı hazır dosyayı X'e yükler, video render/FFmpeg
işlemi gol anında ÇALIŞMAZ (maliyet/hız için bilinçli tercih).

## 1. Adım: matchId'leri bul

Maçkolik `www.mackolik.com` üzerinde şu iç endpoint'leri kullanıyor:

- `https://www.mackolik.com/ajax/football/key-events?ajaxViewName=events&matchId=<ID>`
  → gol/kart/değişiklik listesi. İsimli alanlarla gelir (type, score,
  position, timeMin, playerName) - index tahmini gerekmez.
- `https://www.mackolik.com/ajax/soccer/match/gameStats?matchId=<ID>`
  → şut/top hakimiyeti istatistikleri (opsiyonel, gol tespiti için şart değil).

`matchId` uzun alfanumerik bir kod (ör. `996prqhfc4sm6szbpqclc3jmc`).
Bulmak için:

1. mackolik.com'da ilgili maçın sayfasını aç.
2. Tarayıcı Geliştirici Araçları (F12) → Network sekmesi → Fetch/XHR filtresi.
3. "key-events" isteğini bul, `matchId` parametresini kopyala.

Bulduğun matchId ile hızlı test:

```bash
python mackolik_client.py 996prqhfc4sm6szbpqclc3jmc
```

## 2. Adım: Watchlist'i doldur

`config.py` içinde `WATCHLIST` listesine gerçek `match_id` (yukarıdaki matchId),
`home`, `away` değerlerini gir.

## 3. Adım: Dry-run ile test et

Gerçekten X'e paylaşım yapmadan, sadece konsola ne paylaşılacağını basar:

```bash
python main.py --once --dry-run
```

Sorunsuz çalıştığını gördükten sonra sürekli döngü olarak:

```bash
python main.py --dry-run
```

## 4. Adım: X'e gerçek paylaşım (dikkatli!)

Ortam değişkenlerini ayarla:

```bash
export X_API_KEY="..."
export X_API_SECRET="..."
export X_ACCESS_TOKEN="..."
export X_ACCESS_SECRET="..."
```

Önce bir **test hesabıyla** dene:

```bash
python main.py --once
```

Sorunsuzsa sürekli çalıştır (ör. bir VPS üzerinde `systemd` servisi veya
`tmux`/`screen` içinde):

```bash
python main.py
```

## Genişletme fikirleri (V2+)

- Kırmızı/sarı kart, oyuncu değişikliği gibi ek event tipleri
  (`key-events` zaten bunları da döndürüyor olabilir, `event_detector.py`'ye
  benzer bir `find_new_cards()` fonksiyonu ekle).
- Claude API ile daha doğal tweet metni (`tweet_templates.py`'yi
  opsiyonel bir AI çağrısıyla değiştir — maliyetli olduğu için varsayılan
  kapalı tutulması öneriliyor).
- Basit bir web dashboard (FastAPI + birkaç HTML sayfası) ile watchlist'i
  arayüzden yönetme.
- `gameStats`/`matchHeader`'daki durum bilgisini (`status: "Finished"` vb.)
  kullanarak biten maçları otomatik `active=False` yapma.
