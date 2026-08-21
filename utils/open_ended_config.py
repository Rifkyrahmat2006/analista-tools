"""
Open-Ended Config
=================
Konfigurasi untuk analisis pertanyaan terbuka:
- Kamus normalisasi bahasa Indonesia (singkatan, bahasa gaul)
- Domain stopwords untuk konteks survei

EDITABLE: Kamus ini dapat diedit melalui UI atau langsung di file ini.
Simpan dalam format yang konsisten agar mudah diperbarui.
"""
from typing import Dict, Set, List

# ---------------------------------------------------------------------------
# CONCEPT FAMILIES (NORMALISASI KONSEP MULTI-LABEL)
# ---------------------------------------------------------------------------
# Kamus ini digunakan untuk menyatukan variasi kata ke dalam satu konsep utama
# pada analisis mode Concept, Reason, Barrier, dan Recommendation.

CONCEPT_FAMILIES: Dict[str, List[str]] = {
    "Project / Project-Based Learning": [
        "project", "proyek", "projek", "project based", "project-based",
        "pbl", "pembelajaran berbasis proyek", "project based learning",
        "project nyata", "proyek nyata", "project kolaboratif",
    ],
    "Mentoring": [
        "mentoring", "mentor", "pendampingan", "bimbingan", "mentoring langsung",
        "pendampingan mentor", "bimbingan mentor", "peer mentoring",
    ],
    "Workshop": [
        "workshop", "pelatihan", "training", "webinar", "seminar",
        "workshop pelatihan", "training intensif", "workshop intensif",
        "pelatihan intensif", "seminar workshop",
    ],
    "Coaching": [
        "coaching", "coach", "life coaching", "coaching session",
    ],
    "Simulasi / Role Play": [
        "simulasi", "role play", "roleplay", "simulasi nyata",
        "simulasi praktik", "role-play", "simulasi kasus",
    ],
    "Magang / Internship": [
        "magang", "internship", "kerja praktik", "kp", "pkl",
        "kerja lapangan", "praktik kerja", "on the job training",
    ],
    "Diskusi / Forum": [
        "diskusi", "forum", "focus group", "fgd", "diskusi kelompok",
        "forum diskusi", "group discussion",
    ],
    "Studi Kasus": [
        "studi kasus", "case study", "kasus nyata",
        "pembelajaran kasus", "analisis kasus",
    ],
    "Lomba / Kompetisi": [
        "lomba", "kompetisi", "perlombaan", "competition", "contest",
        "kejuaraan", "turnamen",
    ],
    "Organisasi": [
        "organisasi", "berorganisasi", "ikut organisasi",
        "aktif organisasi", "kegiatan organisasi",
    ],
    "Volunteering": [
        "volunteer", "volunteering", "relawan", "sukarela",
        "kegiatan sosial", "pengabdian masyarakat",
    ],
    "Membaca / Riset Mandiri": [
        "membaca", "baca buku", "riset mandiri", "self study",
        "belajar mandiri", "otodidak", "self learning",
    ],
    "Networking": [
        "networking", "jaringan", "koneksi", "relasi",
        "membangun relasi", "membangun koneksi",
    ],
    "Kebersihan": [
        "kebersihan", "bersih", "higienitas", "sanitasi",
        "kebersihan lingkungan",
    ],
    "Wifi / Internet": [
        "wifi", "internet", "koneksi internet", "jaringan internet",
        "akses internet", "hotspot",
    ],
    "Ruang Kelas": [
        "ruang kelas", "kelas", "ruangan", "ruang belajar",
        "classroom", "fasilitas kelas",
    ],
    "Laboratorium": [
        "lab", "laboratorium", "lab komputer", "lab sains",
        "fasilitas lab",
    ],
    "Perpustakaan": [
        "perpustakaan", "library", "pustaka", "koleksi buku",
    ],
    "Parkir": [
        "parkir", "area parkir", "tempat parkir", "lahan parkir",
    ],
    "Kantin": [
        "kantin", "cafetaria", "makanan", "makan siang", "food court",
    ],
    "Transparansi": [
        "transparansi", "transparan", "keterbukaan", "terbuka",
        "open", "informasi terbuka",
    ],
    "Komunikasi": [
        "komunikasi", "koordinasi", "koordinir", "penyampaian informasi",
        "informasi", "penyebaran info",
    ],
    "Kaderisasi": [
        "kaderisasi", "kader", "rekrutmen", "regenerasi", "perekrutan",
    ],
    "Program Kerja": [
        "program kerja", "proker", "program", "kegiatan", "agenda",
    ],
}

# ---------------------------------------------------------------------------
# KAMUS NORMALISASI BAHASA INDONESIA
# ---------------------------------------------------------------------------
# Format: {"singkatan/bahasa_gaul": "bentuk_baku"}
# PENTING: Jangan mengganti kata yang dapat mengubah arti secara salah.
# Contoh: "org" bisa berarti "organisasi" atau "orang" — jangan di-replace otomatis.

NORMALIZATION_DICT: Dict[str, str] = {
    # Singkatan umum
    "yg": "yang",
    "tdk": "tidak",
    "dgn": "dengan",
    "utk": "untuk",
    "krn": "karena",
    "karna": "karena",
    "sdh": "sudah",
    "blm": "belum",
    "msh": "masih",
    "ttg": "tentang",
    "thd": "terhadap",
    "thdp": "terhadap",
    "tsb": "tersebut",
    "spy": "supaya",
    "jgn": "jangan",
    "jg": "juga",
    "tp": "tetapi",
    "tapi": "tetapi",
    "kl": "kalau",
    "klo": "kalau",
    "klu": "kalau",
    "kalo": "kalau",
    "sbg": "sebagai",
    "spt": "seperti",
    "stlh": "setelah",
    "sblm": "sebelum",
    "dlm": "dalam",
    "dr": "dari",
    "pd": "pada",
    "sm": "sama",
    "sama2": "sama-sama",
    "bs": "bisa",
    "bgt": "banget",
    "bngt": "banget",
    "banget": "banget",
    "skrg": "sekarang",
    "skrng": "sekarang",
    "gmn": "bagaimana",
    "gimana": "bagaimana",
    "gimna": "bagaimana",
    "knp": "kenapa",
    "knapa": "kenapa",
    "mhs": "mahasiswa",
    "mhsw": "mahasiswa",
    "mahasisw": "mahasiswa",
    "bem": "bem",
    "prodi": "program studi",
    "proker": "program kerja",
    "progker": "program kerja",
    "lt": "lantai",
    "nggak": "tidak",
    "ngga": "tidak",
    "gak": "tidak",
    "ga": "tidak",
    "enggak": "tidak",
    "ndak": "tidak",
    "nda": "tidak",
    "gapapa": "tidak apa-apa",
    "gatau": "tidak tahu",
    "ga tau": "tidak tahu",
    "gaada": "tidak ada",
    "ga ada": "tidak ada",
    "oke": "oke",
    "ok": "oke",
    "ok.": "oke",
    "sih": "",
    "deh": "",
    "dong": "",
    "nih": "",
    "loh": "",
    "lho": "",
    "deh": "",
    "aja": "saja",
    "ajah": "saja",
    "aja.": "saja",
    "udah": "sudah",
    "udh": "sudah",
    "mau": "mau",
    "trims": "terima kasih",
    "makasih": "terima kasih",
    "makasi": "terima kasih",
    "terimakasih": "terima kasih",
    "tks": "terima kasih",
    "thx": "terima kasih",
    "thanks": "terima kasih",
    "adm": "administrasi",
    "info": "informasi",
    "infonya": "informasinya",
    "kegiatan2": "kegiatan-kegiatan",
    "acara2": "acara-acara",
}

# ---------------------------------------------------------------------------
# DOMAIN STOPWORDS SURVEI
# ---------------------------------------------------------------------------
# TIGA LAPISAN STOPWORDS:
# 1. General: diproses di preprocessing pipeline (INDONESIAN_BASE_STOPWORDS + Sastrawi)
# 2. Survey Filler: diproses di preprocessing DAN diblokir di TF-IDF vocabulary
# 3. Substantive: TIDAK BOLEH dihapus (lihat SUBSTANTIVE_KEYWORDS_WHITELIST)
#
# PENTING: Jangan menghapus kata yang memiliki makna substantif dalam konteks penelitian.
# Contoh: "dampak", "manfaat", "adil", "transparan" BUKAN domain stopwords.

DOMAIN_SURVEY_STOPWORDS: Set[str] = {
    # --- Survey filler: harapan/doa tanpa substansi ---
    "semoga",
    "moga",
    "mudah-mudahan",
    "mudahmudahan",
    "harapannya",
    "harapan",
    "diharapkan",
    "diharap",
    "berharap",
    "mohon",
    "minta",
    "tolong",
    "ingin",
    "keinginan",

    # --- Survey filler: temporal / arah ke depan ---
    "kedepannya",
    "kedepan",
    "ke depannya",
    "ke depan",
    "kedepanya",
    "ke depanya",
    "selanjutnya",
    "nantinya",
    "nanti",
    "suatu saat",
    "suatu",
    "saat",
    "masa depan",
    "masa mendatang",

    # --- Survey filler: kata kerja modalitas tanpa substansi ---
    "jadi",
    "jadikan",
    "menjadi",
    "jadilah",
    "mampu",
    "bisa",
    "dapat",
    "berjalan",
    "terlaksana",
    "terwujud",
    "memberikan",
    "memberi",
    "membawa",
    "menghasilkan",
    "mewujudkan",

    # --- Survey filler: kata sambung/transisi ---
    "terus",
    "lalu",
    "kemudian",
    "setelah itu",
    "dan seterusnya",
    "dst",
    "dsb",
    "dll",
    "sebagainya",
    "seterusnya",
    "agar",
    "supaya",

    # --- Survey filler: penilaian umum generik ---
    "oke",
    "ok",
    "baik",
    "bagus",
    "setuju",
    "iya",
    "ya",

    # --- Survey filler: saran generik ---
    "dipertahankan",
    "ditingkatkan",
    "terus ditingkatkan",
    "diperbaiki",
    "lebih baik",
    "lebih baik lagi",
    "semakin baik",
    "semakin",
    "makin",
    "terus berkembang",
    "berkembang",
    "terus maju",
    "maju",
    "tetap",
    "tetaplah",

    # --- Survey filler: kata ganti/kolektif ---
    "kami",
    "kita",
    "kita semua",
    "bersama",
    "bersama-sama",
    "semua",
    "seluruh",
    "setiap",

    # --- Survey filler: kata umum non-substantif ---
    "berjalan dengan baik",
    "dengan baik",
    "dengan lancar",
    "lancar",
    "baik baik",
    "lebih",

    # --- Survey filler: ekspresi sopan ---
    "terima kasih",
    "terimakasih",
    "makasih",
    "thanks",
    "sukses",
    "semangat",
    "keep up",
    "good luck",
    "mantap",
    "keren",
    "hebat",

    # --- Survey filler: kata pengisi umum ---
    "hal",
    "hal-hal",
    "hal hal",
    "hal tersebut",
    "tersebut",
    "demikian",
    "begitu",
    "seperti itu",
    "seperti ini",
}

# ---------------------------------------------------------------------------
# MEANINGLESS RESPONSE PATTERNS
# ---------------------------------------------------------------------------
# Pola respons yang dianggap tidak bermakna (exact match atau hampir exact).
# Respons ini akan dikategorikan sebagai "meaningless" bukan "valid".

MEANINGLESS_PATTERNS: List[str] = [
    "-",
    "--",
    "---",
    ".",
    "..",
    "...",
    "....",
    "?",
    "??",
    "!",
    "!!",
    "n/a",
    "na",
    "none",
    "nothing",
    "null",
    "nol",
    "0",
    "kosong",
    "strip",
    "/",
    "\\",
    "_",
    "*",
    "#",
    "@",
]

# ---------------------------------------------------------------------------
# MISSING VALUE STRINGS
# ---------------------------------------------------------------------------
# Representasi string untuk nilai kosong (NaN/Null) yang terbaca sebagai teks
# Akan dikategorikan sebagai "missing" bukan "ambiguous".

MISSING_VALUE_STRINGS: List[str] = [
    "nan", "none", "null", "n/a", "na", "-", "kosong", "tidak ada", "tdk ada"
]

# ---------------------------------------------------------------------------
# LOW-INFORMATION RESPONSE PATTERNS
# ---------------------------------------------------------------------------
# Respons yang memiliki makna tetapi terlalu umum/generik untuk menentukan tema.
# Berbeda dari meaningless (tidak bermakna) — ini BERMAKNA tetapi tidak informatif.
# Status: "low_information" (bukan "ambiguous")
# Tampilkan kepada analis untuk diputuskan.

# Backward compat alias — kode lama mungkin masih mengimport ini
AMBIGUOUS_EXACT_MATCHES: List[str] = [
    "baik",
    "bagus",
    "setuju",
    "oke",
    "ok",
    "iya",
    "ya",
    "tidak",
    "no",
    "yes",
    "good",
    "bad",
    "fine",
    "okay",
    "mantap",
    "keren",
    "hebat",
    "lanjutkan",
    "pertahankan",
    "dipertahankan",
    "ditingkatkan",
    "sudah bagus",
    "sudah baik",
    "cukup baik",
    "cukup",
    "lumayan",
    "alhamdulillah",
    "semangat",
    "sukses",
    "terima kasih",
    "terimakasih",
    "makasih",
]

# Nama canonical baru (digunakan di kode baru)
LOW_INFORMATION_EXACT_MATCHES: List[str] = AMBIGUOUS_EXACT_MATCHES

# Panjang minimum kata agar respons dianggap valid (dalam jumlah kata)
# PENTING: Nilai ini HANYA digunakan sebagai fallback tanpa konteks pertanyaan.
# Jika konteks pertanyaan tersedia (question_text), threshold ini diabaikan
# dan digantikan oleh context-aware scoring.
MIN_WORD_COUNT_VALID = 3

# Panjang minimum karakter agar respons dianggap valid (tanpa konteks)
MIN_CHAR_COUNT_VALID = 10

# ---------------------------------------------------------------------------
# KATA SUBSTANTIF YANG TIDAK BOLEH DIHAPUS
# ---------------------------------------------------------------------------
# Whitelist — pastikan kata-kata ini TIDAK pernah dihapus oleh stopword filter.
# Ini untuk proteksi terhadap penghapusan yang tidak disengaja.

SUBSTANTIVE_KEYWORDS_WHITELIST: Set[str] = {
    # --- Governance & Fairness ---
    "dampak", "berdampak", "manfaat", "adil", "keadilan",
    "transparan", "transparansi", "objektif", "objektivitas",
    "bias", "kecurangan", "integritas", "akuntabel", "akuntabilitas",

    # --- Organizational ---
    "peduli", "kaderisasi", "organisasi", "program", "program kerja",
    "mahasiswa", "apresiasi", "evaluasi", "koordinasi", "kolaborasi",
    "sinergi", "inklusif", "representatif", "profesional", "profesionalisme",
    "partisipasi", "keterlibatan", "komunikasi",

    # --- Problem / Solution ---
    "kritik", "saran", "masalah", "solusi", "inovasi", "kreativitas",
    "perbaikan", "peningkatan", "pengembangan",

    # --- Infrastructure & Resources ---
    "fasilitas", "infrastruktur", "anggaran", "dana", "sarana", "prasarana",
    "laboratorium", "lab", "perpustakaan", "wifi", "internet", "parkir",
    "kantin", "gedung", "ruang", "kelas", "toilet",

    # --- Quality ---
    "kualitas", "kuantitas", "efektif", "efektivitas", "efisien", "efisiensi",
    "produktif", "produktivitas", "optimal", "maksimal",

    # --- Learning & Development Methods (PENTING untuk pertanyaan pengembangan diri) ---
    "workshop", "seminar", "pelatihan", "training", "mentoring", "mentorship",
    "coaching", "magang", "internship", "simulasi", "praktek", "praktik",
    "project", "proyek", "studi kasus", "diskusi", "webinar", "bootcamp",
    "kuliah", "perkuliahan", "belajar", "pembelajaran", "pendidikan",
    "riset", "penelitian", "observasi", "lapangan", "kunjungan",
    "sharing", "sharing session", "forum", "lomba", "kompetisi",
    "kepemimpinan", "leadership", "soft skill", "hard skill",
    "networking", "jejaring",

    # --- Common survey substantive adjectives ---
    "transparan", "terbuka", "jujur", "demokratis", "independen",
    "konsisten", "berkelanjutan", "inovatif", "kreatif",

    # --- Specific campus life contexts ---
    "kebersihan", "keamanan", "kenyamanan", "ketersediaan", "keterjangkauan",
    "aksesibilitas", "inklusivitas",
}
