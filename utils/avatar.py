"""
Avatar Helper — Resize & Validasi Foto Profil
================================================
Foto profil disimpan langsung di database (kolom users.avatar_data,
BYTEA) supaya tidak perlu object storage terpisah — ukuran dataset user
kecil, jadi ini pilihan paling sederhana untuk skala aplikasi ini.

Gambar di-resize & re-encode SEBELUM disimpan (bukan simpan file asli
apa adanya) supaya:
1. Ukuran DB tidak membengkak kalau user upload foto 8000x6000px dari HP
2. Format selalu konsisten (JPEG, quality tetap) — tidak perlu handle
   banyak format (HEIC, WEBP, dst) saat render ulang nanti
3. Foto profil di-crop persegi (center-crop) supaya selalu proporsional
   di UI bulat/kotak, tidak gepeng kalau user upload foto landscape
"""

import io

from PIL import Image, ImageOps

MAX_AVATAR_DIM = 512  # px, sisi persegi setelah resize
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB batas upload mentah sebelum diproses
JPEG_QUALITY = 85


def process_avatar_upload(raw_bytes: bytes) -> bytes:
    """
    Terima bytes gambar mentah dari st.file_uploader, return bytes JPEG
    yang sudah di-center-crop persegi + resize ke MAX_AVATAR_DIM.
    Raise ValueError dengan pesan manusiawi kalau file tidak valid.
    """
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Ukuran file terlalu besar (maks {MAX_UPLOAD_BYTES // (1024*1024)}MB).")

    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.load()  # paksa baca penuh sekarang, supaya error format terdeteksi di sini (bukan nanti pas save)
    except Exception:
        raise ValueError("File bukan gambar yang valid (gunakan JPG, PNG, atau WEBP).")

    # Hormati orientasi EXIF (foto dari HP sering ke-flip kalau ini dilewatkan)
    img = ImageOps.exif_transpose(img)

    # Konversi ke RGB (buang alpha channel PNG/transparansi -> putih,
    # karena target akhirnya JPEG yang tidak support transparansi)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    # Center-crop jadi persegi
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # Resize ke ukuran standar (downscale saja, jangan upscale foto kecil)
    if side > MAX_AVATAR_DIM:
        img = img.resize((MAX_AVATAR_DIM, MAX_AVATAR_DIM), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def get_initials(full_name: str) -> str:
    """Fallback avatar berbasis inisial nama, dipakai kalau user belum upload foto."""
    if not full_name or not full_name.strip():
        return "?"
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
