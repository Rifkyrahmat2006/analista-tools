"""
AI Generate — Draft Kesimpulan Otomatis (via 9Router)
========================================================
Generate draft narasi analisis dari data chart, meniru pola kalimat
laporan resmi tim (lihat SYSTEM_PROMPT_CHOICE/SYSTEM_PROMPT_OPENTEXT).
Selalu berupa DRAFT yang harus direview manusia sebelum disimpan
permanen -- TIDAK PERNAH auto-save langsung ke kolom kesimpulan.

BACKEND: 9Router (gateway AI lokal, endpoint OpenAI-compatible) yang
jalan di HOST server (bukan di dalam container Docker), listen di
127.0.0.1:20128. Container analista-tools mengaksesnya lewat
`host.docker.internal` (lihat extra_hosts di docker-compose.yml --
WAJIB, karena di Linux host.docker.internal TIDAK otomatis ter-resolve
seperti di Docker Desktop macOS/Windows).

Kalau 9Router down/belum jalan, generate_conclusion_draft() akan gagal
dengan pesan error yang jelas (BUKAN crash) -- lihat penanganan
exceptions di bawah.
"""

import os
import requests

NINEROUTER_URL = os.environ.get("NINEROUTER_URL", "http://host.docker.internal:20128/v1/chat/completions")
NINEROUTER_API_KEY = os.environ.get("NINEROUTER_API_KEY", "")
# cc/ = akun Claude Code OAuth yg sudah terhubung di 9Router. Haiku dipilih
# krn task ini (narasi ringkas dari data agregat) tidak butuh reasoning berat
# -- lebih cepat & jauh lebih murah drpd Opus/Sonnet utk tugas sesimpel ini.
MODEL = "cc/claude-haiku-4-5-20251001"

SYSTEM_PROMPT_CHOICE = """Kamu adalah asisten penulisan laporan survei untuk tim
Direktorat Jenderal Analisis Data, BEM Universitas Jenderal Soedirman.
Tulis narasi kesimpulan HASIL SURVEI mengikuti pola kalimat berikut
PERSIS gayanya (bahasa Indonesia formal, gaya laporan resmi):

CONTOH GAYA (dari laporan resmi tim, JADIKAN ACUAN GAYA BAHASA):
"Berdasarkan hasil survei, badminton menjadi bidang yang paling diminati
oleh mahasiswa baru 2026 dengan jumlah pilihan (34,63%), diikuti oleh
musik sebanyak pilihan (27,76%), serta fotografi/vidiografi sebanyak 79
pilihan (23,58%). Secara umum, hasil tersebut menunjukkan bahwa minat
utama mahasiswa baru dalam bidang olahraga pada cabang olahraga
badminton, sedangkan bidang seni didominasi pertunjukan musik dan media
visual kreatif seperti fotografi/videografi."

POLA YANG HARUS DIIKUTI:
"Berdasarkan hasil survei, {opsi_teratas} menjadi pilihan yang paling
banyak dipilih dengan jumlah {count} responden/pilihan ({percent}%),
diikuti oleh {opsi_kedua} sebanyak {count2} ({percent2}%)... Secara
umum, hasil tersebut menunjukkan bahwa {interpretasi singkat, 1-2
kalimat, tarik makna/insight dari pola jawaban, JANGAN cuma ulang
angka}."

ATURAN KETAT:
- HANYA gunakan angka yang diberikan di data user, JANGAN mengarang
  angka atau menambah opsi yang tidak ada di data.
- Panjang 3-5 kalimat, tidak bertele-tele.
- JANGAN tambahkan pembuka/penutup basa-basi ("Berikut adalah draft
  kesimpulannya:", dst) -- langsung tulis narasinya saja, siap
  copy-paste ke laporan.
- JANGAN gunakan format markdown (**bold** dst) -- tulis plain text
  seperti isi dokumen laporan resmi.
"""

SYSTEM_PROMPT_OPENTEXT = """Kamu adalah asisten penulisan laporan survei untuk tim
Direktorat Jenderal Analisis Data, BEM Universitas Jenderal Soedirman.
Tulis narasi kesimpulan dari HASIL ANALISIS JAWABAN TERBUKA (open-text)
mengikuti pola kalimat berikut PERSIS gayanya (bahasa Indonesia formal):

CONTOH GAYA (dari laporan resmi tim, JADIKAN ACUAN GAYA BAHASA):
"Berdasarkan hasil analisis respons, public speaking & kepercayaan diri
menjadi hal yang paling sering muncul dalam jawaban responden, dengan
disebutkan dalam 188 respons. Hal ini diikuti oleh manajemen waktu
dalam 42 respons dan pengembangan soft skill & komunikasi dalam 32
respons. Temuan tersebut menunjukkan bahwa mayoritas mahasiswa baru
sangat memprioritaskan keterampilan komunikasi lisan dan keberanian
berekspresi sebagai bekal utama untuk menghadapi interaksi sosial dan
akademik di kampus."

POLA YANG HARUS DIIKUTI:
"Berdasarkan hasil analisis respons, {tema_utama} menjadi hal yang
paling sering muncul dalam jawaban responden, dengan disebutkan dalam
{N} respons, diikuti oleh {tema_2} dalam {N2} respons. Temuan tersebut
menunjukkan bahwa {interpretasi}."

ATURAN KETAT:
- Kamu akan diberi DAFTAR KATA KUNCI/TEMA TERBANYAK (sudah hasil
  agregasi/ekstraksi kata kunci dari jawaban asli) -- BUKAN jawaban
  mentah individual mahasiswa. HANYA gunakan tema & angka yang
  diberikan, JANGAN mengarang atau menebak isi jawaban asli yang tidak
  kamu lihat.
- Panjang 3-5 kalimat, tidak bertele-tele.
- JANGAN tambahkan pembuka/penutup basa-basi -- langsung tulis
  narasinya saja.
- JANGAN gunakan format markdown.
"""


def generate_conclusion_draft(question_text: str, data_summary: str, question_type: str) -> tuple:
    """
    Return (success: bool, text_or_error: str).
    data_summary: teks ringkas HASIL AGREGAT (value+count+percent, atau
    daftar tema+frekuensi utk open_text) -- BUKAN dataframe mentah,
    BUKAN jawaban individual mahasiswa (lihat build_data_summary()).
    """
    if not NINEROUTER_API_KEY:
        return False, "AI belum dikonfigurasi di server (NINEROUTER_API_KEY kosong). Hubungi admin server."

    system_prompt = SYSTEM_PROMPT_OPENTEXT if question_type == "open_text" else SYSTEM_PROMPT_CHOICE
    user_prompt = f"""Pertanyaan: {question_text}
Tipe: {question_type}
Data hasil (SUDAH agregat, gunakan HANYA angka ini):
{data_summary}

Tulis narasi kesimpulannya sesuai pola & gaya di atas."""

    try:
        resp = requests.post(
            NINEROUTER_URL,
            headers={"Authorization": f"Bearer {NINEROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 400,
                "temperature": 0.4,
                "stream": False,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        if not text:
            return False, "AI mengembalikan respons kosong. Coba lagi."
        return True, text
    except requests.exceptions.Timeout:
        return False, "Timeout — server AI tidak merespons dalam 30 detik. Coba lagi."
    except requests.exceptions.ConnectionError:
        return False, "Tidak bisa terhubung ke server AI (9Router). Kemungkinan sedang tidak aktif — hubungi admin server."
    except requests.exceptions.HTTPError as e:
        return False, f"Server AI menolak permintaan (HTTP {e.response.status_code}). Detail: {e.response.text[:200]}"
    except requests.exceptions.RequestException as e:
        return False, f"Gagal menghubungi layanan AI: {e}"
    except (KeyError, IndexError):
        return False, "Respons AI tidak valid/tidak terduga (format berubah?)."


def build_data_summary(display_result_df, val_col: str, count_col: str) -> str:
    """
    Format dataframe hasil chart (val_col, count_col) jadi teks ringkas
    siap kirim ke LLM -- urut dari count terbesar, sertakan persentase,
    batasi maks 10 baris teratas (hindari prompt kepanjangan utk
    pertanyaan dgn puluhan opsi/kategori unik, dan supaya AI fokus pada
    pola paling signifikan, bukan tenggelam di data ekor panjang).
    """
    df = display_result_df.copy()
    total = df[count_col].sum()
    df = df.sort_values(count_col, ascending=False).head(10)
    lines = []
    for _, row in df.iterrows():
        pct = (row[count_col] / total * 100) if total else 0
        lines.append(f"- {row[val_col]}: {int(row[count_col])} ({pct:.1f}%)")
    return "\n".join(lines)


def build_opentext_summary(keyword_df, word_col: str = "Keyword", count_col: str = "Frequency") -> str:
    """
    Format hasil Top Keywords (dari analisis wordcloud/text_analysis)
    jadi teks ringkas siap kirim ke LLM utk pertanyaan open_text.
    HANYA mengirim kata kunci + frekuensi teragregasi -- TIDAK PERNAH
    mengirim jawaban mentah individual mahasiswa ke API pihak ketiga
    (pertimbangan privasi, lihat plan risks #5).
    """
    df = keyword_df.copy().sort_values(count_col, ascending=False).head(10)
    lines = [f"- {row[word_col]}: {int(row[count_col])} respons" for _, row in df.iterrows()]
    return "\n".join(lines)
