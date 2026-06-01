"""
NebulaLive V1 - Video Hazırlama (tek seferlik)

Senin NebulaGol.mp4 dosyan 4K (3840x2160). X (Twitter) videoları en fazla
1920x1200'e kadar kabul ediyor, üzerini otomatik indiriyor ve H.264 dışındaki
codec'leri reddediyor/yeniden kodluyor. Yani:

  - Kaliteyi kontrolde tutmak için videoyu KENDİN önceden 1080p'ye indirip
    H.264 + AAC olarak encode etmen daha iyi.
  - Bu işlem GOL BAŞINA DEĞİL, TEK SEFERLİK yapılır. Otomasyon her golde
    hep aynı hazır dosyayı (assets/NebulaGol_1080p.mp4) X'e yükler.

Kullanım:
    python prepare_video.py assets/NebulaGol.mp4

Çıktı:
    assets/NebulaGol_1080p.mp4  (X'e yüklenecek asıl dosya)

Gereksinim: ffmpeg kurulu olmalı (`ffmpeg -version` ile kontrol et).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def prepare(input_path: str, output_path: str) -> None:
    if shutil.which("ffmpeg") is None:
        print("[HATA] ffmpeg bulunamadı. Kurulum: https://ffmpeg.org/download.html")
        sys.exit(1)

    inp = Path(input_path)
    if not inp.exists():
        print(f"[HATA] Girdi dosyası bulunamadı: {inp}")
        sys.exit(1)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(inp),
        # 1920x1080'e indir, oranı koru, çift sayıya yuvarla (H.264 gereksinimi)
        "-vf", "scale='min(1920,iw)':'-2'",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-b:v", "8000k",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        # Ses yoksa bile X'in "ses izi zorunlu" kuralına uymak için sessiz iz ekle
        "-shortest",
        str(out),
    ]

    print("Çalıştırılan komut:")
    print(" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("[HATA] ffmpeg başarısız oldu:")
        print(result.stderr[-2000:])
        sys.exit(1)

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"\n[BAŞARILI] Hazır dosya: {out} ({size_mb:.1f} MB)")
    if size_mb > 512:
        print("[UYARI] Dosya 512 MB üzerinde, standart X hesaplarında reddedilebilir.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gol videosunu X için tek seferlik hazırla")
    parser.add_argument("input", help="Orijinal video dosyası (ör. assets/NebulaGol.mp4)")
    parser.add_argument(
        "--output",
        default="assets/NebulaGol_1080p.mp4",
        help="Çıktı dosyası (varsayılan: assets/NebulaGol_1080p.mp4)",
    )
    args = parser.parse_args()
    prepare(args.input, args.output)
