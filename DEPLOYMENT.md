# Deployment Guide — Analista Tools

## Menjalankan via Docker (Direkomendasikan untuk Server)

### Prasyarat
- Docker & Docker Compose terpasang
- Port 8501 bebas di localhost (default; tidak di-expose ke LAN/internet langsung)

### Build & Jalankan

```bash
docker compose up -d --build
```

Ini akan:
1. Build image dari `Dockerfile`
2. Membuat volume Docker `analista_data` (persisten — survive container rebuild/redeploy)
3. Menjalankan `scripts/seed_users.py` (idempotent — skip user yang sudah ada)
4. Menjalankan Streamlit di `127.0.0.1:8501` (HANYA localhost, bukan `0.0.0.0`)

### Melihat Password Akun Awal (Seed)

Password di-generate acak setiap kali `seed_users.py` jalan pertama kali (tidak ter-hardcode di kode/git):

```bash
docker logs analista-tools 2>&1 | grep -A 10 "SEEDING"
```

**PENTING**: Password hanya tercetak sekali di log. Segera minta tiap anggota tim login & ganti password (lewat halaman *Manajemen User*, tombol Reset Password oleh admin/superadmin — user biasa saat ini reset password lewat admin, bukan self-service).

### Role & Akun Default

| Username | Role | Nama |
|---|---|---|
| rifky | superadmin | Rifky Dwi Rahmat Prakoso |
| yufi | admin | Yufi |
| reivan | staff | Reivan |
| d | staff | D |

**Hierarki hak akses:**
- **superadmin**: kelola semua user (termasuk admin lain), lihat semua audit log, hapus/reset apa pun.
- **admin**: kelola user staff (bukan sesama admin/superadmin), assign tugas analisis, lihat audit log, kelola dataset.
- **staff**: hanya kerjakan tugas yang di-assign ke dirinya (isi kesimpulan analisis, lihat rekomendasi chart), tidak bisa kelola user.

### Data Persisten

Semua data (database SQLite `data/app.db`, dataset upload, cache) tersimpan di Docker volume `analista_data`, terpisah dari image container. Rebuild image (`docker compose up -d --build`) TIDAK menghapus data ini.

Untuk backup manual:
```bash
docker run --rm -v work_analista_analista_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/analista_data_backup_$(date +%Y%m%d).tar.gz -C /data .
```

### Expose ke Internet (Subdomain)

Container HANYA bind ke `127.0.0.1:8501` (aman, tidak exposed ke LAN/internet). Untuk akses via subdomain publik, gunakan Cloudflare Tunnel (`cloudflared`) — jangan ubah binding ke `0.0.0.0`.

### Melihat Log & Status

```bash
docker compose ps
docker logs analista-tools --tail 100 -f
```

### Menghentikan / Restart

```bash
docker compose down       # hentikan & hapus container (data tetap aman di volume)
docker compose up -d      # jalankan lagi (tanpa rebuild)
docker compose restart    # restart cepat
```
