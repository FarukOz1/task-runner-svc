"""
NebulaLive V2 - X (Twitter) Publisher (OAuth 2.0)

NEDEN OAuth 2.0? OAuth 1.0a, X'in "Pay-Per-Use" hesaplarında backend
tarafında düzgün enroll edilmemiş bir platform hatası yüzünden sürekli
401 (code 32) veriyordu - bu, X'in kendi bilinen/dokümante edilmemiş bir
sorunu (devcommunity.x.com'da çok sayıda benzer şikayet var). OAuth 2.0 +
doğru scope (media.write dahil) ile bu sorun tamamen atlatıldı.

Kullanmadan önce:
  1) console.x.com'da App'in "User authentication settings"ında OAuth 2.0
     aktif olmalı, "Confidential client" ve bir Callback URI (örn.
     https://x.com) ayarlı olmalı.
  2) Bir kerelik OAuth 2.0 PKCE yetkilendirme akışıyla (tarayıcıda giriş +
     onay) ilk access_token + refresh_token çifti alınır (scope: tweet.read
     tweet.write users.read media.write offline.access).
  3) Şu ortam değişkenleri ayarlanmalı (koda ASLA yazılmaz):
       X_OAUTH2_CLIENT_ID
       X_OAUTH2_CLIENT_SECRET
       X_OAUTH2_REFRESH_TOKEN   (ilk seferde elle alınan, sonrası otomatik döner)
       SECRETS_MANAGER_PAT      (GitHub repo secrets'ı güncellemek için,
                                  SADECE "Secrets: Read and write" izinli)
       GITHUB_REPOSITORY        (GitHub Actions'ta otomatik gelir, "owner/repo")

ÖNEMLİ - Token yenileme: X'in OAuth 2.0 access_token'ı 2 saatte bir sona
eriyor, refresh_token ise TEK KULLANIMLIKTIR (her yenilemede hem yeni
access_token hem yeni refresh_token gelir, eskisi geçersiz olur). Bu yüzden
her çalıştırmada refresh_access_token() çağrılıp SONUÇTAKİ yeni
refresh_token GitHub Actions secret'ına geri yazılıyor - aksi halde bir
sonraki çalıştırma eski (artık geçersiz) refresh_token ile başarısız olurdu.
"""

from __future__ import annotations

import base64
import os
import time
from typing import Optional

import requests

TOKEN_URL = "https://api.x.com/2/oauth2/token"
MEDIA_UPLOAD_BASE = "https://api.x.com/2/media/upload"
TWEETS_URL = "https://api.x.com/2/tweets"
APPEND_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB (limit 5MB, güvenli marj)


class XPublisherError(Exception):
    pass


def _require_env(*names: str) -> dict:
    values = {n: os.environ.get(n) for n in names}
    missing = [n for n, v in values.items() if not v]
    if missing:
        raise XPublisherError(f"Eksik ortam değişkenleri: {', '.join(missing)}")
    return values


def refresh_access_token() -> tuple[str, str]:
    """
    X_OAUTH2_REFRESH_TOKEN'ı kullanarak yeni bir (access_token, refresh_token)
    çifti alır. Dönen refresh_token bir SONRAKİ çağrı için gereklidir -
    çağıran taraf bunu kalıcı bir yere (GitHub secret) yazmalı.
    """
    env = _require_env("X_OAUTH2_CLIENT_ID", "X_OAUTH2_CLIENT_SECRET", "X_OAUTH2_REFRESH_TOKEN")
    try:
        resp = requests.post(
            TOKEN_URL,
            auth=(env["X_OAUTH2_CLIENT_ID"], env["X_OAUTH2_CLIENT_SECRET"]),
            data={
                "grant_type": "refresh_token",
                "refresh_token": env["X_OAUTH2_REFRESH_TOKEN"],
            },
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        raise XPublisherError(f"Token yenileme isteği başarısız (ağ hatası): {e}") from e

    if resp.status_code != 200:
        raise XPublisherError(f"Token yenileme başarısız: {resp.status_code} - {resp.text[:300]}")

    data = resp.json()
    access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token")
    if not access_token or not new_refresh_token:
        raise XPublisherError(f"Token yenileme yanıtı eksik: {data}")
    return access_token, new_refresh_token


def update_github_secret(secret_name: str, secret_value: str) -> None:
    """
    GitHub Actions repo secret'ını API üzerinden günceller (libsodium sealed
    box ile şifreleyerek - GitHub'ın istediği format budur). SECRETS_MANAGER_PAT
    ve GITHUB_REPOSITORY ortam değişkenleri gerekir.
    """
    from nacl import encoding, public

    env = _require_env("SECRETS_MANAGER_PAT", "GITHUB_REPOSITORY")
    repo = env["GITHUB_REPOSITORY"]
    pat = env["SECRETS_MANAGER_PAT"]
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
    }

    try:
        key_resp = requests.get(
            f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
            headers=headers,
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        raise XPublisherError(f"GitHub public key alınamadı (ağ hatası): {e}") from e

    if key_resp.status_code != 200:
        raise XPublisherError(f"GitHub public key alınamadı: {key_resp.status_code} - {key_resp.text[:300]}")

    key_data = key_resp.json()
    public_key = public.PublicKey(key_data["key"].encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

    put_resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_b64, "key_id": key_data["key_id"]},
        timeout=15,
    )
    if put_resp.status_code not in (201, 204):
        raise XPublisherError(f"GitHub secret güncellenemedi: {put_resp.status_code} - {put_resp.text[:300]}")


def get_fresh_access_token() -> str:
    """
    Token'ı yeniler ve yeni refresh_token'ı GitHub secret'ına geri yazar.
    Her cloud_runner.py çalıştırmasında BİR KEZ çağrılmalı (goal başına değil -
    refresh_token tek kullanımlık, gereksiz yenileme onu boşa harcar).
    """
    access_token, new_refresh_token = refresh_access_token()
    update_github_secret("X_OAUTH2_REFRESH_TOKEN", new_refresh_token)
    return access_token


def _media_upload_init(access_token: str, total_bytes: int, media_type: str, media_category: str) -> str:
    resp = requests.post(
        f"{MEDIA_UPLOAD_BASE}/initialize",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"media_type": media_type, "total_bytes": total_bytes, "media_category": media_category},
        timeout=30,
    )
    if resp.status_code != 200:
        raise XPublisherError(f"Medya init başarısız: {resp.status_code} - {resp.text[:300]}")
    return resp.json()["data"]["id"]


def _media_upload_append(access_token: str, media_id: str, video_path: str) -> None:
    with open(video_path, "rb") as f:
        segment_index = 0
        while True:
            chunk = f.read(APPEND_CHUNK_SIZE)
            if not chunk:
                break
            resp = requests.post(
                f"{MEDIA_UPLOAD_BASE}/{media_id}/append",
                headers={"Authorization": f"Bearer {access_token}"},
                data={"segment_index": str(segment_index)},
                files={"media": ("video.mp4", chunk, "video/mp4")},
                timeout=60,
            )
            if resp.status_code != 200:
                raise XPublisherError(f"Medya append başarısız (segment {segment_index}): {resp.status_code} - {resp.text[:300]}")
            segment_index += 1


def _media_upload_finalize(access_token: str, media_id: str) -> dict:
    resp = requests.post(
        f"{MEDIA_UPLOAD_BASE}/{media_id}/finalize",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise XPublisherError(f"Medya finalize başarısız: {resp.status_code} - {resp.text[:300]}")
    return resp.json()["data"]


def _media_upload_wait_processing(access_token: str, media_id: str, max_wait_seconds: int = 60) -> None:
    waited = 0
    while waited < max_wait_seconds:
        resp = requests.get(
            MEDIA_UPLOAD_BASE,
            params={"command": "STATUS", "media_id": media_id},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise XPublisherError(f"Medya durum kontrolü başarısız: {resp.status_code} - {resp.text[:300]}")
        info = resp.json()["data"].get("processing_info")
        if not info:
            return  # işlem gerektirmeyen medya (ör. resim) - zaten hazır
        state = info.get("state")
        if state == "succeeded":
            return
        if state == "failed":
            raise XPublisherError(f"Medya işleme başarısız: {info}")
        check_after = info.get("check_after_secs", 2)
        time.sleep(check_after)
        waited += check_after
    raise XPublisherError("Medya işleme zaman aşımına uğradı.")


def _upload_media(access_token: str, path: str, media_type: str, media_category: str) -> str:
    total_bytes = os.path.getsize(path)
    media_id = _media_upload_init(access_token, total_bytes, media_type, media_category)
    _media_upload_append(access_token, media_id, path)
    _media_upload_finalize(access_token, media_id)
    if media_type.startswith("video/"):
        # STATUS (processing_info) sorgusu sadece video için var - X bunu
        # resimlerde desteklemiyor (400 "Not found" döner). Resimler zaten
        # FINALIZE ile hemen kullanıma hazır, ek bekleme gerekmiyor.
        _media_upload_wait_processing(access_token, media_id)
    return media_id


def _upload_video(access_token: str, video_path: str) -> str:
    return _upload_media(access_token, video_path, "video/mp4", "tweet_video")


def _upload_image(access_token: str, image_path: str) -> str:
    ext = image_path.rsplit(".", 1)[-1].lower()
    media_type = "image/png" if ext == "png" else "image/jpeg"
    return _upload_media(access_token, image_path, media_type, "tweet_image")


def _post_tweet(text: str, media_id: Optional[str], access_token: str) -> str:
    body: dict = {"text": text}
    if media_id:
        body["media"] = {"media_ids": [media_id]}

    resp = requests.post(
        TWEETS_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise XPublisherError(f"Tweet paylaşılamadı: {resp.status_code} - {resp.text[:300]}")

    tweet_id = resp.json().get("data", {}).get("id")
    if not tweet_id:
        raise XPublisherError(f"Tweet paylaşıldı ama id alınamadı: {resp.text[:300]}")
    return str(tweet_id)


def publish_goal_post(text: str, video_path: Optional[str] = None, access_token: Optional[str] = None) -> str:
    """
    Tweet'i (opsiyonel video ile) paylaşır. Başarılı olursa tweet id döner.
    Bu fonksiyon GERÇEKTEN X'e paylaşım yapar - dikkatli test et.

    access_token verilmezse (main.py --once gibi tekil/yerel çalıştırmalarda)
    kendi başına bir tane üretir (ve refresh_token'ı GitHub secret'ına
    yazar). cloud_runner.py gibi bir çalıştırmada birden fazla gol olabileceği
    için access_token'ı DIŞARIDAN, tek seferlik üretilip parametre olarak
    geçirmek daha doğru (gereksiz token yenilemeyi önler).
    """
    if access_token is None:
        access_token = get_fresh_access_token()

    media_id = _upload_video(access_token, video_path) if video_path else None
    return _post_tweet(text, media_id, access_token)


def publish_match_end_post(text: str, image_path: Optional[str] = None, access_token: Optional[str] = None) -> str:
    """
    Maç Sonu tweet'ini (opsiyonel görsel ile) paylaşır. publish_goal_post ile
    aynı mantık, sadece video yerine statik görsel yüklüyor (daha hızlı işlenir,
    processing_info beklemesi genelde hiç gerekmez).
    """
    if access_token is None:
        access_token = get_fresh_access_token()

    media_id = _upload_image(access_token, image_path) if image_path else None
    return _post_tweet(text, media_id, access_token)
