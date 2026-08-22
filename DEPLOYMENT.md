# Deployment Guide — Analista Tools

## Arsitektur

3 container Docker (docker-compose.yml):
- **postgres** — PostgreSQL 16, database utama (users, audit log, RBAC, task assignment, sessions)
- **analista-tools** — aplikasi Streamlit
- **cloudflared** — Cloudflare Tunnel, expose ke `amertools.rifkyprakoso.my.id`

## Menjalankan via Docker (Direkomendasikan untuk Server)

### Prasyarat
- Docker & Docker Compose terpasang
- File `.env` di root project berisi:
  ```
  POSTGRES_PASSWORD=<password acak kuat>
  CF_TUNNEL_TOKEN=<token dari Cloudflare Tunnel>
  ```
  (`.env` sudah di-gitignore — JANGAN commit ke repo)
- Port 8501 & 5432 bebas di localhost (default; tidak di-expose ke LAN/internet langsung)

### Build & Jalankan

```bash
docker compose up -d --build
```

Ini akan:
1. Start Postgres, tunggu sampai `healthy` (healthcheck `pg_isready`)
2. Build image `analista-tools` dari `Dockerfile`, baru start setelah Postgres healthy (`depends_on: condition: service_healthy`)
3. Membuat volume `analista_pgdata` (data Postgres) & `analista_data` (dataset upload + cache) — keduanya persisten lintas rebuild/redeploy
4. Menjalankan `scripts/seed_users.py` (idempotent — skip user yang sudah ada, dengan retry otomatis kalau Postgres belum siap terima koneksi)
5. Menjalankan Streamlit di `127.0.0.1:8501` (HANYA localhost, bukan `0.0.0.0`)
6. Start cloudflared, expose ke subdomain publik

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

**Hierarki hak akses (RBAC dinamis):**
- **superadmin**: akses penuh permanen (wildcard, tidak bisa dibatasi) — termasuk kelola semua user (termasuk admin lain), lihat semua audit log, **mengatur izin role admin & staff lewat UI** (halaman Manajemen User > tab Permission Matrix).
- **admin**: izin default kelola dataset, analisis, assign tugas, kelola user staff, lihat audit log — bisa dikurangi/ditambah superadmin kapan saja lewat UI.
- **staff**: izin default kerjakan dataset & tugas milik sendiri — bisa dikurangi/ditambah superadmin kapan saja lewat UI. Halaman "Manajemen User" otomatis tersembunyi dari sidebar untuk role ini.

Permission matrix disimpan di tabel `role_permissions` (Postgres), bisa diedit real-time tanpa redeploy.

### Data Persisten

- **Database** (users, audit log, RBAC, dataset upload, task assignment, sessions): volume `analista_pgdata`
- **Dataset upload & cache**: volume `analista_data`

Keduanya terpisah dari image container. Rebuild image (`docker compose up -d --build`) TIDAK menghapus data ini.

Untuk backup manual database:
```bash
docker exec analista-tools-db pg_dump -U analista analista_tools > backup_$(date +%Y%m%d).sql
```

Restore:
```bash
cat backup_YYYYMMDD.sql | docker exec -i analista-tools-db psql -U analista analista_tools
```

### Expose ke Internet (Subdomain)

Container `analista-tools` HANYA bind ke `127.0.0.1:8501`, dan Postgres HANYA bind ke `127.0.0.1:5432` (aman, tidak exposed ke LAN/internet). Akses publik lewat Cloudflare Tunnel (`cloudflared`) ke `amertools.rifkyprakoso.my.id` — jangan ubah binding ke `0.0.0.0`.

**PENTING**: `cloudflared` pakai `network_mode: "service:analista-tools"` (share network namespace). Kalau container `analista-tools` di-rebuild/recreate, WAJIB jalankan juga:
```bash
docker compose up -d --force-recreate cloudflared
```
atau tunnel akan kehilangan koneksi ("network is unreachable").

### Melihat Log & Status

```bash
docker compose ps
docker logs analista-tools --tail 100 -f
docker logs analista-tools-db --tail 100 -f
```

### Menghentikan / Restart

```bash
docker compose down       # hentikan & hapus container (data tetap aman di volume)
docker compose up -d      # jalankan lagi (tanpa rebuild)
docker compose restart    # restart cepat
```

