"""
Open-Ended Preprocessing Pipeline
===================================
Pipeline preprocessing untuk analisis pertanyaan terbuka survei.

Pipeline urutan:
1. validate_responses()       → klasifikasi: valid, empty, meaningless, ambiguous
2. clean_text_enhanced()      → hapus URL, email, karakter berlebihan
3. normalize_text()           → terapkan kamus normalisasi bahasa Indonesia
4. stem_text_properly()       → stemming per kata (bukan seluruh kalimat)
5. remove_stopwords_full()    → Sastrawi + umum + domain stopwords
6. build_processed_record()   → simpan semua tahap dalam satu record

PRINSIP: Tidak ada API eksternal. Semua proses lokal.
"""

import re
import uuid
from typing import Optional, Dict, Set, List, Tuple
from collections import Counter

import pandas as pd

# Import konfigurasi
from utils.open_ended_config import (
    NORMALIZATION_DICT,
    DOMAIN_SURVEY_STOPWORDS,
    MEANINGLESS_PATTERNS,
    AMBIGUOUS_EXACT_MATCHES,
    LOW_INFORMATION_EXACT_MATCHES,
    MIN_WORD_COUNT_VALID,
    MIN_CHAR_COUNT_VALID,
    MISSING_VALUE_STRINGS,
    SUBSTANTIVE_KEYWORDS_WHITELIST,
)

# ---------------------------------------------------------------------------
# LAZY LOADING: Sastrawi (optional dependency)
# ---------------------------------------------------------------------------

_stemmer = None
_sastrawi_stopwords = set()  # type: Set[str]

def _get_stemmer():
    global _stemmer
    if _stemmer is None:
        try:
            from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
            _stemmer = StemmerFactory().create_stemmer()
        except ImportError:
            _stemmer = False  # Tandai sudah dicoba tapi tidak tersedia
    return _stemmer if _stemmer is not False else None


def _get_sastrawi_stopwords() -> Set[str]:
    global _sastrawi_stopwords
    if not _sastrawi_stopwords:
        try:
            from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
            _sastrawi_stopwords = set(StopWordRemoverFactory().get_stop_words())
        except ImportError:
            _sastrawi_stopwords = set()
    return _sastrawi_stopwords


# ---------------------------------------------------------------------------
# INDONESIAN BASE STOPWORDS
# ---------------------------------------------------------------------------

INDONESIAN_BASE_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "adalah",
    "ini", "itu", "atau", "juga", "tidak", "akan", "sudah", "ada", "bisa",
    "lebih", "saya", "kami", "kita", "mereka", "anda", "dia", "ia", "nya",
    "hal", "oleh", "karena", "seperti", "bagi", "antara", "lain",
    "dapat", "harus", "menjadi", "telah", "secara", "dalam", "agar",
    "supaya", "maupun", "serta", "namun", "tetapi", "bahwa", "sebagai",
    "belum", "masih", "sangat", "begitu", "hingga", "sampai", "lagi",
    "sering", "selalu", "banyak", "setiap",
    # Huruf/suku kata tidak bermakna hasil stemming
    "se", "ter", "ber", "me", "men", "mem", "meng", "per", "pem", "pen",
    "an", "kan", "i", "in", "un",
    # English filler (jika ada jawaban campuran)
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "and", "or", "but", "not", "it", "its", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them", "their",
    "this", "that", "these", "those",
}


# ---------------------------------------------------------------------------
# CONTEXT-AWARE QUESTION ANALYSIS
# ---------------------------------------------------------------------------

# Kata-kata penghubung / pertanyaan yang TIDAK boleh dianggap konsep kunci
_QUESTION_FILLER_WORDS = {
    "menurut", "anda", "apa", "yang", "paling", "bagi", "untuk", "bagaimana",
    "adalah", "dari", "ke", "di", "dan", "atau", "ini", "itu", "dalam",
    "sebagai", "sebuah", "suatu", "ada", "dapat", "harus", "akan", "sudah",
    "apakah", "siapa", "kapan", "mengapa", "dimana", "please", "tolong",
    "mohon", "jelaskan", "sebutkan", "tuliskan", "berikan", "ceritakan",
    "bagaimanakah", "apakah", "faktor", "aspek", "hal", "masukan", "saran",
    "lebih", "sangat", "cukup", "sekali", "dengan", "pada", "oleh",
}


def extract_question_concepts(question_text: str) -> Set[str]:
    """
    Ekstrak kata/konsep penting dari pertanyaan untuk digunakan dalam
    context-aware validation.

    Contoh:
        "Menurut Anda, metode pengembangan diri apa yang paling efektif bagi mahasiswa?"
        → {"metode", "pengembangan", "diri", "efektif"}

    Returns:
        Set of concept strings (lowercase, setelah filter filler)
    """
    if not question_text or not isinstance(question_text, str):
        return set()

    text = question_text.lower()
    # Hapus tanda baca
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()

    # Ambil token yang bukan filler pertanyaan dan panjang >= 3 karakter
    concepts = {
        t for t in tokens
        if t not in _QUESTION_FILLER_WORDS
        and len(t) >= 3
    }
    return concepts


def is_substantive_for_context(
    response_text: str,
    question_concepts: Set[str],
    substantive_whitelist: Set[str] = None,
) -> bool:
    """
    Tentukan apakah respons pendek (1-2 kata) substantif dalam konteks pertanyaan.

    Logika:
    1. Jika kata respons ada di SUBSTANTIVE_KEYWORDS_WHITELIST → Valid
    2. Jika kata respons ada/tumpang tindih dengan konsep dalam pertanyaan → Valid
    3. Jika kata respons cukup panjang (>= 5 char) dan bukan di low-info list → Valid
    4. Sebaliknya → Low-information

    Contoh:
        Pertanyaan: "Metode pengembangan diri apa yang paling efektif?"
        Response: "Workshop" → True (di substantive whitelist)
        Response: "Magang" → True (di substantive whitelist)
        Response: "Bagus" → False (ada di low-info list)
        Response: "Iya" → False (ada di low-info list)
    """
    whitelist = substantive_whitelist or SUBSTANTIVE_KEYWORDS_WHITELIST
    low_info_set = {m.lower() for m in LOW_INFORMATION_EXACT_MATCHES}

    response_lower = response_text.lower().strip()
    response_words = set(response_lower.split())

    # --- RULE 1: Cek apakah ada kata di substantive whitelist ---
    for word in response_words:
        if word in whitelist or response_lower in whitelist:
            return True

    # --- RULE 2: Cek apakah ada kata yang overlap dengan konsep pertanyaan ---
    if question_concepts:
        # Cek overlap langsung
        concept_overlap = response_words.intersection(question_concepts)
        if concept_overlap:
            return True

        # Cek apakah kata respons adalah substring dari konsep pertanyaan
        for resp_word in response_words:
            if len(resp_word) >= 4:  # Hindari substring yang terlalu pendek
                for concept in question_concepts:
                    if resp_word in concept or concept in resp_word:
                        return True

    # --- RULE 3: Kata panjang (>= 6 char) yang tidak ada di low-info list → anggap valid ---
    for word in response_words:
        if len(word) >= 6 and word not in low_info_set:
            return True

    return False


# ---------------------------------------------------------------------------
# RESPONSE VALIDATION
# ---------------------------------------------------------------------------

def validate_responses(
    series: pd.Series,
    extra_domain_sw: Set[str] = None,
    question_text: str = "",
) -> pd.DataFrame:
    """
    Klasifikasikan setiap respons ke dalam 4 kategori:
    - 'valid'          : respons cukup informatif untuk dianalisis
    - 'missing'        : kosong, NaN, None, atau placeholder missing value
    - 'meaningless'    : simbol/tanda baca/satu karakter tanpa makna apapun
    - 'low_information': memiliki makna tetapi terlalu umum untuk menentukan tema
                         (sebelumnya disebut 'ambiguous')

    CONTEXT-AWARE:
    Jika question_text diberikan, respons pendek (< MIN_WORD_COUNT_VALID kata)
    dievaluasi berdasarkan relevansi terhadap konteks pertanyaan:
    - "Workshop" pada pertanyaan "metode pengembangan diri" → valid
    - "Bagus" pada pertanyaan yang sama → low_information

    Args:
        series          : pd.Series kolom yang ingin divalidasi
        extra_domain_sw : Set stopwords tambahan dari pengguna
        question_text   : Teks pertanyaan (untuk context-aware scoring)

    Returns:
        DataFrame dengan kolom:
            response_id, original_text, validation_status, validation_note
    """
    # Ekstrak konsep dari pertanyaan (context-aware)
    question_concepts = extract_question_concepts(question_text)
    low_info_set = {m.lower() for m in LOW_INFORMATION_EXACT_MATCHES}

    records = []

    for idx, val in series.items():
        resp_id = idx

        # ── STEP 1: Missing / Empty ──────────────────────────────────────────
        if pd.isna(val) or val is None:
            records.append({
                "response_id": resp_id,
                "original_text": "",
                "validation_status": "missing",
                "validation_note": "Nilai kosong (NaN/None)",
            })
            continue

        text = str(val).strip()
        text_lower = text.lower()

        if text == "":
            records.append({
                "response_id": resp_id,
                "original_text": text,
                "validation_status": "missing",
                "validation_note": "String kosong setelah strip",
            })
            continue

        if text_lower in [m.lower() for m in MISSING_VALUE_STRINGS]:
            records.append({
                "response_id": resp_id,
                "original_text": text,
                "validation_status": "missing",
                "validation_note": "Representasi string missing value",
            })
            continue

        # ── STEP 2: Meaningless ──────────────────────────────────────────────
        if text_lower in [p.lower() for p in MEANINGLESS_PATTERNS]:
            records.append({
                "response_id": resp_id,
                "original_text": text,
                "validation_status": "meaningless",
                "validation_note": f"Respons tidak bermakna: '{text}'",
            })
            continue

        # Hanya simbol/angka
        if re.match(r'^[\W\d_]+$', text_lower):
            records.append({
                "response_id": resp_id,
                "original_text": text,
                "validation_status": "meaningless",
                "validation_note": "Hanya simbol atau angka",
            })
            continue

        # ── STEP 3: Cek low-information exact match ──────────────────────────
        # Lakukan ini SEBELUM substantive check untuk menangkap filler jelas
        # seperti "baik", "oke", "iya" bahkan jika panjang > threshold
        if text_lower in low_info_set:
            records.append({
                "response_id": resp_id,
                "original_text": text,
                "validation_status": "low_information",
                "validation_note": f"Respons sangat generik: '{text}'",
            })
            continue

        # ── STEP 4: Substantive Check (global whitelist) ─────────────────────
        has_substantive = any(
            sub in text_lower for sub in SUBSTANTIVE_KEYWORDS_WHITELIST
        )
        if has_substantive:
            records.append({
                "response_id": resp_id,
                "original_text": text,
                "validation_status": "valid",
                "validation_note": "Mengandung kata substantif (global whitelist)",
            })
            continue

        # ── STEP 5: All-filler check ─────────────────────────────────────────
        words = set(text_lower.split())
        if words and words.issubset(DOMAIN_SURVEY_STOPWORDS):
            records.append({
                "response_id": resp_id,
                "original_text": text,
                "validation_status": "low_information",
                "validation_note": "Respons hanya berisi kata filler umum",
            })
            continue

        # ── STEP 6: Context-Aware Short Response Check ───────────────────────
        word_count = len(text_lower.split())
        char_count = len(text_lower)

        is_short = word_count < MIN_WORD_COUNT_VALID and char_count < MIN_CHAR_COUNT_VALID

        if is_short:
            # Gunakan context scoring jika pertanyaan tersedia
            if is_substantive_for_context(text, question_concepts):
                records.append({
                    "response_id": resp_id,
                    "original_text": text,
                    "validation_status": "valid",
                    "validation_note": (
                        f"Respons pendek ({word_count} kata) tetapi relevan "
                        f"dengan konteks pertanyaan"
                        if question_concepts else
                        f"Respons pendek ({word_count} kata) tetapi mengandung kata substantif"
                    ),
                })
            else:
                records.append({
                    "response_id": resp_id,
                    "original_text": text,
                    "validation_status": "low_information",
                    "validation_note": (
                        f"Respons terlalu pendek ({word_count} kata, {char_count} karakter) "
                        f"dan tidak relevan dengan konteks pertanyaan"
                        if question_concepts else
                        f"Respons terlalu pendek ({word_count} kata, {char_count} karakter)"
                    ),
                })
            continue

        # ── STEP 7: Valid (default) ──────────────────────────────────────────
        records.append({
            "response_id": resp_id,
            "original_text": text,
            "validation_status": "valid",
            "validation_note": "",
        })

    return pd.DataFrame(records)



def get_validation_summary(validated_df: pd.DataFrame) -> dict:
    """Hitung ringkasan statistik validasi respons."""
    total = len(validated_df)
    counts = validated_df["validation_status"].value_counts().to_dict()
    return {
        "total": total,
        "valid": counts.get("valid", 0),
        "missing": counts.get("missing", 0) + counts.get("empty", 0),
        "meaningless": counts.get("meaningless", 0),
        # Support both old (ambiguous) and new (low_information) terminology
        "low_information": counts.get("low_information", 0) + counts.get("ambiguous", 0),
        # Backward compat key
        "ambiguous": counts.get("low_information", 0) + counts.get("ambiguous", 0),
    }


# ---------------------------------------------------------------------------
# TEXT CLEANING
# ---------------------------------------------------------------------------

def clean_text_enhanced(text: str) -> str:
    """
    Pembersihan teks tahap pertama.
    Simpan makna, hapus noise teknis.
    """
    if not isinstance(text, str) or not text.strip():
        return ""

    # Lowercase
    text = text.lower()

    # Hapus URL
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)

    # Hapus email
    text = re.sub(r'\S+@\S+\.\S+', ' ', text)

    # Hapus emoji dan karakter non-ASCII (kecuali huruf beraksara)
    text = re.sub(r'[^\w\s]', ' ', text)

    # Hapus angka standalone (tapi jaga konteks seperti "1. poin")
    text = re.sub(r'\b\d+\b', ' ', text)

    # Hapus karakter berlebihan (3+ karakter sama berturut)
    text = re.sub(r'(.)\1{2,}', r'\1', text)

    # Normalisasi whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


# ---------------------------------------------------------------------------
# NORMALISASI BAHASA INDONESIA
# ---------------------------------------------------------------------------

def normalize_text(text: str, custom_dict: Dict[str, str] = None) -> str:
    """
    Normalisasi singkatan dan bahasa gaul ke bentuk baku.
    Gunakan word-boundary matching untuk menghindari partial replacement.
    """
    if not text:
        return text

    norm_dict = NORMALIZATION_DICT.copy()
    if custom_dict:
        norm_dict.update(custom_dict)

    words = text.split()
    normalized_words = []

    for word in words:
        # Cek apakah kata ini ada di kamus normalisasi
        lower_word = word.lower()
        if lower_word in norm_dict:
            replacement = norm_dict[lower_word]
            if replacement:  # Kosong berarti hapus kata (filler)
                normalized_words.append(replacement)
            # Jika replacement kosong, kata dibuang (kata filler)
        else:
            normalized_words.append(word)

    return " ".join(normalized_words)


# ---------------------------------------------------------------------------
# STEMMING
# ---------------------------------------------------------------------------

def stem_text_properly(text: str) -> str:
    """
    Stemming per kata menggunakan Sastrawi.
    PERBAIKAN dari implementasi lama yang stem seluruh kalimat sekaligus.

    Sebelumnya: _stemmer.stem("saya menyukai organisasi") → hasilnya tidak konsisten
    Sekarang: stem setiap kata secara individual → lebih akurat
    """
    stemmer = _get_stemmer()
    if stemmer is None or not text:
        return text

    words = text.split()
    stemmed_words = []

    for word in words:
        try:
            stemmed = stemmer.stem(word)
            stemmed_words.append(stemmed if stemmed else word)
        except Exception:
            stemmed_words.append(word)

    return " ".join(stemmed_words)


# ---------------------------------------------------------------------------
# STOPWORD REMOVAL
# ---------------------------------------------------------------------------

def build_stopword_set(
    extra_stopwords: Set[str] = None,
    domain_stopwords: Set[str] = None,
    include_sastrawi: bool = True,
) -> Set[str]:
    """
    Bangun set stopwords lengkap dari semua sumber.

    Returns:
        Set of stopword strings (all lowercase)
    """
    stopwords = INDONESIAN_BASE_STOPWORDS.copy()

    if include_sastrawi:
        stopwords.update(_get_sastrawi_stopwords())

    if domain_stopwords is not None:
        stopwords.update({w.lower() for w in domain_stopwords})
    else:
        stopwords.update({w.lower() for w in DOMAIN_SURVEY_STOPWORDS})

    if extra_stopwords:
        stopwords.update({w.lower() for w in extra_stopwords})

    return stopwords


def remove_stopwords_from_text(
    text: str,
    stopword_set,  # type: Set[str]
    min_word_length: int = 2,
) -> str:
    """
    Hapus stopwords dari teks dan filter kata terlalu pendek.
    """
    if not text:
        return ""

    words = text.split()
    filtered = [
        w for w in words
        if w.lower() not in stopword_set and len(w) >= min_word_length
    ]
    return " ".join(filtered)


# ---------------------------------------------------------------------------
# FULL PREPROCESSING PIPELINE
# ---------------------------------------------------------------------------

def preprocess_pipeline(
    validated_df: pd.DataFrame,
    use_stemming: bool = True,
    use_domain_stopwords: bool = True,
    extra_stopwords: Set[str] = None,
    custom_norm_dict: Dict[str, str] = None,
) -> pd.DataFrame:
    """
    Jalankan seluruh pipeline preprocessing pada valid responses.

    Hanya proses respons dengan validation_status == 'valid'.
    Simpan setiap tahap untuk keperluan audit dan debug.

    Returns:
        DataFrame dengan kolom tambahan:
            cleaned_text, normalized_text, stemmed_text, processed_text
    """
    result_df = validated_df.copy()

    domain_sw = DOMAIN_SURVEY_STOPWORDS if use_domain_stopwords else set()
    stopword_set = build_stopword_set(
        extra_stopwords=extra_stopwords,
        domain_stopwords=domain_sw,
        include_sastrawi=True,
    )

    cleaned_texts = []
    normalized_texts = []
    stemmed_texts = []
    processed_texts = []

    for _, row in result_df.iterrows():
        status = row["validation_status"]
        original = row["original_text"]

        # Hanya proses respons valid
        if status != "valid" or not original:
            cleaned_texts.append("")
            normalized_texts.append("")
            stemmed_texts.append("")
            processed_texts.append("")
            continue

        # Step 1: Clean
        cleaned = clean_text_enhanced(original)

        # Step 2: Normalize
        normalized = normalize_text(cleaned, custom_dict=custom_norm_dict)

        # Step 3: Stem (optional)
        if use_stemming:
            stemmed = stem_text_properly(normalized)
        else:
            stemmed = normalized

        # Step 4: Remove stopwords
        processed = remove_stopwords_from_text(stemmed, stopword_set)

        cleaned_texts.append(cleaned)
        normalized_texts.append(normalized)
        stemmed_texts.append(stemmed)
        processed_texts.append(processed)

    result_df["cleaned_text"] = cleaned_texts
    result_df["normalized_text"] = normalized_texts
    result_df["stemmed_text"] = stemmed_texts
    result_df["processed_text"] = processed_texts

    return result_df


# ---------------------------------------------------------------------------
# DUPLICATE DETECTION
# ---------------------------------------------------------------------------

def detect_duplicate_texts(validated_df: pd.DataFrame) -> pd.DataFrame:
    """
    Deteksi respons yang memiliki teks identik (case-insensitive, after strip).
    TIDAK otomatis menghapus — hanya tandai untuk informasi analis.

    Returns:
        DataFrame dengan kolom 'is_duplicate_text' dan 'duplicate_group_id'
    """
    result_df = validated_df.copy()
    result_df["is_duplicate_text"] = False
    result_df["duplicate_group_id"] = None

    # Normalisasi teks untuk perbandingan
    text_col = result_df["original_text"].str.lower().str.strip()

    # Hitung frekuensi setiap teks
    text_counts = text_col.value_counts()
    duplicate_texts = text_counts[text_counts > 1].index.tolist()

    group_id = 1
    for dup_text in duplicate_texts:
        mask = text_col == dup_text
        if mask.sum() > 1:
            result_df.loc[mask, "is_duplicate_text"] = True
            result_df.loc[mask, "duplicate_group_id"] = f"DUP_{group_id:03d}"
            group_id += 1

    return result_df


# ---------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------------

def split_into_subresponses(texts: List[str], response_ids: List[str]) -> Tuple[List[str], List[str]]:
    """
    Memecah teks menjadi sub-respons berdasarkan konjungsi/tanda baca 
    agar satu respons dapat dikelompokkan ke dalam beberapa tema (Multi-label).
    """
    import re
    split_pattern = re.compile(r"[,;]|\bdan\b|\bserta\b|\batau\b|\bkarena\b|\bkemudian\b|\blalu\b", re.IGNORECASE)
    
    new_texts = []
    new_ids = []
    
    for text, rid in zip(texts, response_ids):
        # Split text
        chunks = split_pattern.split(text)
        for chunk in chunks:
            clean_chunk = chunk.strip()
            # Hanya ambil chunk yang punya makna (minimal 2 kata atau panjang > 3 huruf)
            if len(clean_chunk) > 3 or len(clean_chunk.split()) >= 1:
                new_texts.append(clean_chunk)
                new_ids.append(rid)
                
    return new_texts, new_ids


def get_valid_texts_for_clustering(preprocessed_df: pd.DataFrame, is_multilabel: bool = False) -> Tuple[List[str], list]:
    """
    Ekstrak processed_text dan response_id hanya untuk respons valid + non-empty processed.
    Jika is_multilabel=True, teks akan dipecah menjadi sub-respons agar dapat masuk ke beberapa klaster.
    
    Returns:
        (processed_texts_list, response_ids_list)
    """
    valid_mask = (
        (preprocessed_df["validation_status"] == "valid") &
        (preprocessed_df["processed_text"].str.strip() != "")
    )
    subset = preprocessed_df[valid_mask]
    
    texts = subset["processed_text"].tolist()
    rids = subset["response_id"].tolist()
    
    if is_multilabel:
        return split_into_subresponses(texts, rids)
        
    return texts, rids


def get_original_texts_for_display(preprocessed_df: pd.DataFrame, response_ids: list) -> Dict:
    """
    Ambil original_text berdasarkan response_id untuk keperluan display.

    Returns:
        dict {response_id: original_text}
    """
    subset = preprocessed_df[preprocessed_df["response_id"].isin(response_ids)]
    return dict(zip(subset["response_id"], subset["original_text"]))


def count_word_frequencies(preprocessed_df: pd.DataFrame) -> Counter:
    """Hitung frekuensi kata dari semua processed_text yang valid."""
    all_words = []
    for text in preprocessed_df[preprocessed_df["validation_status"] == "valid"]["processed_text"]:
        if isinstance(text, str) and text.strip():
            all_words.extend(text.split())
    return Counter(all_words)
