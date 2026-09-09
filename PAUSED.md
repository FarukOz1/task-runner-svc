# NebulaLive — Duraklatıldı (2026-09-09)

Proje durduruldu: X'te organik büyüme/monetizasyon zorluğu + komisyon
(pay-per-use) + ToS riski nedeniyle şu an öncelik değil. Kod ve altyapı
silinmedi, hazır bekliyor.

## Şu an ne durdu, ne durmadı

- **GitHub Actions workflow'u (`nebulalive.yml`) devre dışı bırakıldı**
  (`state: disabled_manually`, GitHub API üzerinden). Bu; zamanlanmış
  (`schedule`) tetiklemeyi, self-chaining zincirini (her çalışmanın kendini
  tekrar tetiklemesi) VE cron-job.org'un dış tetiklemesini TEK NOKTADAN
  durdurur — hiçbiri artık yeni bir çalışma başlatamaz.
- `runtime_config.json` → `dry_run: true` yapıldı (ekstra güvenlik katmanı;
  workflow yanlışlıkla tekrar açılsa bile gerçek X paylaşımı yapılmaz).
- Watchlist boş (`watchlist: []`) — sen de bunu panelden az önce temizlemişsin, rebase sırasında bu haliyle korundu.
- Proje **VPS/systemd üzerinde DEĞİL**, tamamen GitHub Actions üzerinde
  bulut tabanlı çalışıyordu — durdurulacak ayrı bir sunucu/servis yok.
- `x_session.json` gibi bir tarayıcı oturum dosyası **hiç var olmadı** —
  bu, değerlendirilip uygulanmayan bir alternatif yöntemdi (bkz. aşağı).
  Projede kontrol ettim, hiçbir session/cookie/.env dosyası yok.
- GitHub Secrets (`X_OAUTH2_CLIENT_ID`, `X_OAUTH2_CLIENT_SECRET`,
  `X_OAUTH2_REFRESH_TOKEN`, `SECRETS_MANAGER_PAT`) **silinmedi**, repo'da
  duruyor — workflow devre dışı olduğu için zararsızlar. İstersen ayrıca
  bunları da silmemi söyleyebilirsin.

## Neredeydik — proje gerçekte hangi aşamadaydı

Bu, ilk taslaktan (browser otomasyonu fikri) çok daha ileri gitti ve
**tam olarak production'da, gerçek paylaşımlarla doğrulanmış** haldeydi:

- ✅ Mackolik v2 `key-events` endpoint'i entegre, isimli alanlarla
  (index tahmini yok), gol/kart/değişiklik ayrıştırılıyor.
- ✅ Dedup sağlam (event_id'den player_name kasıtlı çıkarıldı — geç gelen
  isim yüzünden çift paylaşım riski giderildi).
- ✅ X paylaşımı **OAuth 2.0 + PKCE** ile çalışıyor (OAuth 1.0a, X'in
  Pay-Per-Use hesaplarındaki bilinen bir backend hatası yüzünden hiç
  çalışmamıştı — bu sorun tamamen aşıldı).
- ✅ Token yenileme tam otomatik: her çalışma `refresh_token`'ı yeniler ve
  yenisini GitHub Secrets'a geri yazar (libsodium sealed-box şifrelemesiyle).
- ✅ Video (gol) ve resim (maç sonu) medya yükleme ikisi de test edildi ve
  çalışıyor.
- ✅ **Gerçek golde gerçek tweet atıldığı canlı olarak doğrulandı**
  (2026-09-07'de Elche - Real Sociedad maçında birden fazla gerçek gol
  otomatik paylaşıldı, tweet id'leri log'da mevcut).
- ✅ Self-chaining: her çalışma kendini GitHub'ın dahili `GITHUB_TOKEN`'ıyla
  tekrar tetikliyor, üçüncü parti bir cron servisine (cron-job.org sürekli
  sessizce duruyordu) bağımlılık kaldırıldı.
- ✅ Canlı kontrol paneli (GitHub Pages, `docs/index.html`): izlenen maçlar,
  canlı skor/dakika, "Maç Sonu" rozeti, watchlist yönetimi, çok adımlı
  onaylı "Canlı Paylaşımı Aç/Kapat" anahtarı, marka logosuna göre
  siyah+altın tema. URL: https://farukoz1.github.io/task-runner-svc/
- ⚠️ **Denenmeyen/terk edilen**: Playwright ile tarayıcı otomasyonu
  (`x_login_setup.py` / `x_browser_publisher.py`) — ToS riski nedeniyle
  hiç uygulanmadı, gerçek kod tabanında yok. OAuth 2.0 API yöntemi yeterli
  ve güvenilir çıktığı için gerek kalmadı.
- ⚠️ Bilinen sınırlama: dakika hesaplaması maç başlangıcından bu yana geçen
  gerçek süreye dayanıyor, devre arasını ayırt etmiyor (yaklaşık değer).
- ⚠️ Bilinen edge-case: Mackolik'in canlı verisi bir kez geçici/hatalı bir
  gol gösterip birkaç dakika sonra geri çekti (muhtemelen VAR iptali veya
  veri hatası) — o an otomasyon bunu gerçek gol sanıp paylaştı. Sistem bunu
  kendiliğinden fark edip düzeltme/geri çekme yapmıyor (bilinçli tasarım
  kararı: yanlış pozitif riski, otomatik "düzeltme tweet'i" atmaktan daha
  az riskli görüldü).

## Geri dönmek istersen — sırası

1. GitHub → repo → **Actions** → `NebulaLive Cloud Worker` → **Enable workflow**
   (veya API: `PUT /repos/FarukOz1/task-runner-svc/actions/workflows/nebulalive.yml/enable`).
2. `X_OAUTH2_REFRESH_TOKEN` hâlâ geçerli mi kontrol et — X'in refresh
   token'ları uzun süre (aylarca) geçerli kalıyor ama garantisi yok; ilk
   çalışmada `dry_run: true` iken bir dispatch tetikleyip log'da token
   yenilemenin başarılı olduğunu doğrula. Sorun çıkarsa PKCE akışını
   (console.x.com → yetkilendirme → kod → token exchange) tekrar yapman
   gerekir — bu oturumda nasıl yapıldığı konuşma geçmişinde tam adım adım var.
3. Panelden (veya `runtime_config.json`'dan) izlemek istediğin maçları
   ekle/aktif yap.
4. Her şeyi `dry_run: true` ile bir kez test et (panel log'unda "kontrol
   edildi" mesajlarını gör), sonra panelin "Canlı Paylaşımı Aç" (çok adımlı
   onaylı) anahtarıyla `dry_run: false` yap.

## Maliyet notu

X pay-per-use fiyatlandırması: link içermeyen paylaşım ~$0.015/post,
link içeren ~$0.20/post (bizim tweetlerimizde link yok). Video/resim eki
ekstra ücrete tabi değil.
