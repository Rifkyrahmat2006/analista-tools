# Testing Plan — Analista Tools (amertools)

> **Untuk Hermes:** Dokumen ini adalah acuan tetap untuk menjalankan QA/regression test pada project **Analista Tools**. Jalankan skenario di bawah secara berurutan setiap kali diminta "test analista tools" atau setelah deploy perubahan baru. Gunakan browser sungguhan (bukan cuma curl) untuk kasus yang melibatkan cookie/JS — lihat catatan di §0.

**Repo:** `Rifkyrahmat2006/analista-tools` · **Lokasi server:** `/home/lestara/work_analista`
**Live URL:** https://amertools.rifkyprakoso.my.id
**Stack:** Streamlit + PostgreSQL 16 + Docker Compose (3 container: `analista-tools`, `analista-tools-db`, `analista-tools-cloudflared`)

---

## 0. Prinsip Testing di Project Ini

1. **Jangan percaya curl/HTTP 200 saja untuk bug yang melibatkan cookie/JS.** Riwayat project ini punya 2 bug login (`cabaf1c`, `cabe8cb`) yang lolos test curl tapi baru ketemu root cause-nya pakai browser sungguhan (`cbe5ae6`). Untuk semua test terkait **login/session/cookie**, WAJIB pakai `mcp__browser_exec` (Chrome headless via CDP), verifikasi via `document.cookie` dan multi-refresh — bukan cuma cek status code.
2. **Test di server (Docker container), bukan cuma lokal.** Environment produksi = 3 container terpisah; behavior async (postMessage, WebSocket rerun) bisa beda dari `streamlit run` lokal biasa.
3. **Tulis root cause di commit message kalau nemu bug**, ikuti gaya commit history project ini (deskriptif, jujur soal apa yang sudah/belum diverifikasi).
4. **Jangan asal declare "sudah fix"** — kalau tidak sempat verifikasi end-to-end visual, tulis eksplisit "belum diverifikasi visual, perlu konfirmasi user" (lihat gaya commit `cabe8cb`).
5. Tidak ada folder `tests/` otomatis (pytest) di repo ini saat ini — semua testing di dokumen ini adalah **manual/scripted QA**, dijalankan lewat browser_exec atau langsung ke DB Postgres container.

---

## 1. Pre-Test Checklist (Environment)

Jalankan dulu sebelum mulai skenario manapun:

```bash
cd /home/lestara/work_analista
git status                          # pastikan tahu ada perubahan uncommitted apa
sudo docker compose ps              # ke-3 container harus Up & healthy
curl -sI https://amertools.rifkyprakoso.my.id | head -5   # harus 200
sudo docker logs analista-tools --tail 50                 # harus bersih dari Traceback/Error
sudo docker logs analista-tools-db --tail 20
```

Catat versi/commit yang sedang di-test:
```bash
git log -1 --oneline
```

---

## 2. Skenario Test — Auth & Session (PRIORITAS TINGGI)

Area paling rawan bug di project ini (3 fix besar berturut-turut di riwayat commit). Test ini WAJIB pakai browser sungguhan.

### 2.1 Login dasar
| Step | Aksi | Expected |
|---|---|---|
| 1 | `new_tab('https://amertools.rifkyprakoso.my.id')` | Halaman login tampil, tidak crash |
| 2 | Login dengan akun `rifky` (superadmin) — kredensial minta ke user, jangan asumsikan/hardcode | Redirect ke halaman utama, badge user "Rifky Dwi Rahmat Prakoso" muncul di sidebar |
| 3 | `js('document.cookie')` | String mengandung `analista_session_token` |

### 2.2 Persistence cookie lintas refresh (regression test bug cbe5ae6)
| Step | Aksi | Expected |
|---|---|---|
| 1 | Setelah login sukses, `goto_url()` ke URL yang sama 3x berturut-turut, tiap kali `wait_for_load()` | **Tetap login setiap kali** — badge user selalu tampil, TIDAK PERNAH balik ke form login |
| 2 | Cek `js('document.cookie')` tiap refresh | Cookie tetap ada & sama tiap kali |
| 3 | Tunggu >5 detik lalu refresh sekali lagi (cek race condition warm/cold component) | Tetap login |

⚠️ Kalau salah satu langkah gagal (balik ke form login), ini regresi dari fix `cbe5ae6` — root cause kemungkinan besar terkait timing `CookieController.set()` vs `st.rerun()`. Baca commit message `cbe5ae6` dan `cabe8cb` untuk konteks lengkap sebelum debug ulang.

### 2.3 Logout
| Step | Aksi | Expected |
|---|---|---|
| 1 | Klik tombol logout | Kembali ke form login |
| 2 | `js('document.cookie')` | `analista_session_token` sudah hilang/invalid |
| 3 | Coba akses URL langsung tanpa login | Diarahkan ke form login, bukan konten |

### 2.4 Token expiry (7 hari, TTL cookie & DB harus konsisten)
- Cek di DB: `SELECT expires_at FROM sessions ORDER BY created_at DESC LIMIT 1;` via `docker exec analista-tools-db psql -U analista analista_tools -c "..."`
- Pastikan `expires_at` ~7 hari dari `created_at`, dan cookie `max_age` di browser (`document.cookie` tidak expose max_age langsung — cek lewat DevTools Application tab kalau perlu detail).

### 2.5 Role-based access (RBAC)
| Role | Test | Expected |
|---|---|---|
| superadmin (rifky) | Buka halaman "Manajemen User" | Bisa akses, ada tab Permission Matrix |
| superadmin | Ubah permission role `staff` lewat UI (tab Permission Matrix), lalu cek efeknya | Perubahan tersimpan di tabel `role_permissions`, berlaku real-time tanpa perlu redeploy |
| admin (yufi) | Buka halaman "Manajemen User" | Bisa akses (default), tapi TIDAK bisa kelola user lain yang superadmin |
| staff (reivan/d) | Cek sidebar | Halaman "Manajemen User" TIDAK muncul di sidebar sama sekali |
| staff | Coba akses URL halaman admin langsung (bypass sidebar) | Ditolak/redirect, bukan crash |

---

## 3. Skenario Test — Core Feature Pipeline

Urutan alur utama aplikasi: **Upload → Cleaning → Analysis → Visualization**.

### 3.1 Upload Data (`pages/1_upload_data.py`)
- Upload file CSV valid → preview tabel tampil, tidak error
- Upload file Excel (.xlsx) valid → sama seperti CSV
- Upload file format tidak didukung (mis. .txt) → pesan error jelas, bukan crash/traceback ke user
- Upload file kosong / hanya header → tidak crash, pesan informatif

### 3.2 Data Cleaning (`pages/2_data_cleaning.py`)
- Edit cell → perubahan tersimpan di session/cache
- Hapus row → jumlah row berkurang sesuai
- Rename column → nama baru dipakai konsisten di halaman analysis selanjutnya
- Drop column → kolom hilang dari analisis berikutnya

### 3.3 Analysis (`pages/3_analysis.py`)
Cek tiap tipe pertanyaan (baca `utils/question_detection.py` untuk daftar tipe yang didukung saat ini — jangan asumsikan dari `planning_docs.md`, dokumen itu draft awal dan sudah banyak berubah, contoh: fitur validasi NIM & multi-select analysis sudah ditambahkan setelahnya):
- Single choice → frequency table + chart benar (bandingkan manual count vs `value_counts()`)
- Multiple choice / multi-select → split & explode benar, tidak duplikat/hilang data
- Scale/Likert → distribusi terurut benar
- Open text → tokenization & clustering jalan (`utils/nlp_clustering.py`, `utils/oe_question_profiler.py`)
- **Validasi NIM Mahasiswa** (fitur dari commit `b182e86`) → cross-check ke `registrasi.unsoed.ac.id` benar-benar memanggil endpoint asli, bukan mock; test dengan NIM valid & invalid, cek akurasi matching. User historically minta breakdown akurasi & koreksi matching manual — jangan klaim "berfungsi" tanpa angka akurasi konkret dari data test.

### 3.4 Visualization (`pages/4_visualization.py`)
- Tiap jenis chart (bar, pie, donut, treemap) render tanpa error untuk dataset yang sudah dianalisis
- Wordcloud tab tampil untuk kolom open-text
- Export chart (kalau ada tombol export) menghasilkan file valid

### 3.5 Task Assignment (`pages/6_pembagian_tugas.py`)
- Assign tugas ke user tertentu → tersimpan di DB (`assignments` table)
- User yang di-assign bisa lihat tugasnya sendiri
- Audit log mencatat aksi assignment (`audit_log` table)

---

## 4. Skenario Test — Data Persistence & Docker

### 4.1 Rebuild tidak menghapus data
```bash
sudo docker compose up -d --build
sudo docker compose ps   # semua healthy lagi
```
- Login dengan akun yang sama seperti sebelum rebuild → user masih ada (data di volume `analista_pgdata` persist)
- Dataset yang sempat di-upload sebelumnya masih ada (volume `analista_data`)

### 4.2 Cloudflared tetap connect setelah rebuild
⚠️ **Pitfall dari DEPLOYMENT.md**: `cloudflared` pakai `network_mode: service:analista-tools` — kalau container app di-recreate, tunnel WAJIB direstart juga:
```bash
sudo docker compose up -d --force-recreate cloudflared
curl -sI https://amertools.rifkyprakoso.my.id   # harus tetap 200, bukan "network unreachable"
```

### 4.3 Backup & Restore Database
```bash
sudo docker exec analista-tools-db pg_dump -U analista analista_tools > /tmp/test_backup.sql
wc -l /tmp/test_backup.sql   # pastikan tidak kosong
```
(Jangan benar-benar test restore ke DB production kecuali diminta eksplisit — restore = destructive, test di container terpisah/staging kalau perlu verifikasi penuh)

---

## 5. Skenario Test — Security & Network Exposure

- `sudo docker compose ps` → pastikan port binding `analista-tools` dan `analista-tools-db` HANYA `127.0.0.1:xxxx`, BUKAN `0.0.0.0:xxxx`
- `curl http://<server-public-ip>:8501` dari luar (atau `curl` ke IP lokal server bukan localhost) → harus **connection refused**, akses publik cuma lewat Cloudflare Tunnel
- Cek `.env` tidak ter-commit ke git: `git log --all --full-history -- .env` → harus kosong
- Cek password seed tidak hardcoded di kode: `grep -ri "password" scripts/seed_users.py` → pastikan random-generated, bukan string tetap

---

## 6. Regression Checklist Ringkas (jalankan tiap kali ada perubahan di `utils/auth.py`)

Karena `utils/auth.py` adalah area paling rawan (3x fix besar), setiap kali file ini berubah:

- [ ] Login sukses dengan cookie ter-set (§2.1)
- [ ] Refresh 3x berturut-turut tetap login (§2.2) — **via browser sungguhan, bukan curl**
- [ ] Logout benar-benar clear cookie (§2.3)
- [ ] Tidak ada `TypeError` / `NoneType is not iterable` di log container setelah test
- [ ] `git log -1 -- utils/auth.py` dicatat di laporan test, supaya jelas versi apa yang sedang divalidasi

---

## 7. Format Laporan Hasil Test

Setelah menjalankan skenario di atas, laporkan dalam format:

```
## Hasil Test — Analista Tools (<tanggal>, commit <hash>)

✅ Lolos: <daftar skenario>
❌ Gagal: <daftar skenario + detail error/screenshot>
⚠️ Belum sempat/tidak bisa diverifikasi: <daftar + alasan jujur>

Rekomendasi: <lanjut deploy / perlu fix dulu / perlu konfirmasi user>
```

Ikuti gaya jujur seperti commit `cabe8cb`: kalau ada yang tidak bisa diverifikasi penuh (mis. tidak ada akses browser saat itu), **katakan dengan jelas**, jangan mengklaim "sudah fix" tanpa bukti.

---

## 8. Catatan Update Dokumen Ini

Dokumen ini bukan statis — kalau nemu bug/pitfall baru saat testing yang tidak tercakup di atas, **update file ini** (`TESTING_PLAN.md`) supaya jadi acuan yang makin lengkap untuk test berikutnya. Jangan biarkan dokumen jadi basi seperti `planning_docs.md` (draft awal yang sudah jauh dari implementasi aktual).
