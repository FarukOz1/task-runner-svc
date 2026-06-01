"""
NebulaLive V1 - X (Twitter) Publisher

Bu modül X API v2 üzerinden video + metin paylaşımı yapar.
Kullanmadan önce:

  1) X Developer Portal'dan bir proje/app oluştur (uygun erişim seviyesiyle,
     medya yüklemek için en az "Elevated" / ücretli bir tier gerekebilir -
     X'in güncel dokümantasyonunu kontrol et, sık değişiyor).
  2) API Key, API Secret, Access Token, Access Secret bilgilerini al.
  3) Bunları KODA YAZMA - ortam değişkeni olarak ayarla:

       export X_API_KEY="..."
       export X_API_SECRET="..."
       export X_ACCESS_TOKEN="..."
       export X_ACCESS_SECRET="..."

  4) pip install tweepy

Bu dosya tweepy kullanıyor çünkü medya yükleme (video) + tweet atma
işini birlikte destekliyor.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    import tweepy
except ImportError:
    tweepy = None  # tweepy kurulana kadar import hatası vermesin


class XPublisherError(Exception):
    pass


def _get_client() -> "tweepy.Client":
    if tweepy is None:
        raise XPublisherError("tweepy kurulu değil. `pip install tweepy` çalıştır.")

    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise XPublisherError(
            f"Eksik ortam değişkenleri: {', '.join(missing)}. "
            "Bunları export edip tekrar dene."
        )

    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )


def _get_api_v1() -> "tweepy.API":
    """Medya yükleme için v1.1 API'ye ihtiyaç var (tweepy'de medya v2'de yok)."""
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
    )
    return tweepy.API(auth)


def publish_goal_post(text: str, video_path: Optional[str] = None) -> str:
    """
    Tweet'i (opsiyonel video ile) paylaşır. Başarılı olursa tweet id döner.
    Bu fonksiyon GERÇEKTEN X'e paylaşım yapar - dikkatli test et
    (önce kendi test hesabınla dene).
    """
    client = _get_client()

    media_ids = None
    if video_path:
        api_v1 = _get_api_v1()
        media = api_v1.media_upload(filename=video_path, media_category="tweet_video")
        media_ids = [media.media_id]

    response = client.create_tweet(text=text, media_ids=media_ids)
    tweet_id = response.data.get("id")
    return str(tweet_id)
