"""
NLP Clustering Utilities
=========================
Algoritma clustering dan feature extraction untuk analisis pertanyaan terbuka.

PRINSIP: Clustering hanya menghasilkan KANDIDAT KELOMPOK.
Manusia menentukan makna dan nama tema final.

Metode yang tersedia:
- K-Means
- Agglomerative Clustering
- DBSCAN (untuk noise/outlier detection)

Evaluasi:
- Silhouette Score
- Davies-Bouldin Index
- Elbow method (inertia untuk K-Means)
"""

import numpy as np
from collections import Counter
from typing import List, Dict, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

import scipy.sparse as sp


# ---------------------------------------------------------------------------
# TF-IDF VECTORIZATION
# ---------------------------------------------------------------------------

def get_tfidf_matrix(
    processed_texts: List[str],
    ngram_range: Tuple = (1, 2),
    max_features: int = 1500,
    min_df: int = None,
    max_df: float = 0.92,
    context_stopwords: Optional[List[str]] = None,
    domain_stopwords: Optional[set] = None,
):
    """
    Generate TF-IDF matrix dari processed texts.

    Default:
    - ngram_range=(1,2): unigram + bigram sesuai spec
    - min_df adaptif: max(2, n_samples // 30) untuk dataset kecil
    - max_df=0.92: abaikan term yang ada di >92% dokumen
    - context_stopwords: kata dari pertanyaan (nusantara, kolektiva, dll.) → diblokir dari vocabulary
    - domain_stopwords: kata filler survei → diblokir dari vocabulary

    Returns:
        (tfidf_matrix, vectorizer) atau (None, None) jika gagal
    """
    n_samples = len([t for t in processed_texts if t.strip()])

    if n_samples == 0:
        return None, None

    # Adaptif min_df: jangan terlalu besar untuk dataset kecil
    if min_df is None:
        min_df = max(2, n_samples // 40)
    min_df = max(1, min(min_df, max(1, n_samples // 5)))

    # Gabungkan context_stopwords + domain_stopwords menjadi satu list stop_words untuk TF-IDF
    # Ini memastikan kata-kata konteks pertanyaan dan filler survei benar-benar
    # tidak masuk vocabulary dan tidak mendominasi clustering.
    all_stop_words = set()
    if context_stopwords:
        all_stop_words.update(w.lower() for w in context_stopwords)
    if domain_stopwords:
        # Hanya tambahkan kata tunggal (TF-IDF stop_words harus token, bukan frasa)
        all_stop_words.update(
            w.lower() for w in domain_stopwords
            if isinstance(w, str) and ' ' not in w
        )

    stop_words_list = list(all_stop_words) if all_stop_words else None

    vectorizer = TfidfVectorizer(
        ngram_range=ngram_range,
        max_features=max_features,
        min_df=min_df,
        max_df=max_df,
        stop_words=stop_words_list,
        sublinear_tf=True,  # Gunakan log(tf) untuk meredam dominasi term frekuensi tinggi
        strip_accents='unicode',
        analyzer='word',
        token_pattern=r'\b[a-zA-Z][a-zA-Z]+\b',  # Hanya kata huruf, min 2 karakter
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(processed_texts)

        # Cek apakah matrix tidak kosong
        if tfidf_matrix.shape[1] == 0:
            return None, None

        return tfidf_matrix, vectorizer
    except ValueError:
        return None, None


# ---------------------------------------------------------------------------
# CLUSTER EVALUATION
# ---------------------------------------------------------------------------

def evaluate_cluster_range(
    tfidf_matrix,
    min_k: int = 2,
    max_k: int = 12,
    random_state: int = 42,
) -> List[Dict]:
    """
    Evaluasi beberapa nilai k untuk K-Means dengan Silhouette Score dan Davies-Bouldin Index.

    Returns:
        List of dicts: [{k, silhouette, davies_bouldin, inertia}, ...]
    """
    n_samples = tfidf_matrix.shape[0]

    # Batasi max_k oleh jumlah sample
    actual_max_k = min(max_k, n_samples - 1)
    actual_max_k = min(actual_max_k, 12)

    if actual_max_k < min_k:
        return []

    results = []

    for k in range(min_k, actual_max_k + 1):
        try:
            kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10, max_iter=300)
            labels = kmeans.fit_predict(tfidf_matrix)

            # Hitung hanya jika lebih dari 1 cluster yang terisi
            if len(set(labels)) < 2:
                continue

            sil = safe_silhouette(tfidf_matrix, labels, metric='cosine')
            if isinstance(sil, float):
                db = davies_bouldin_score(
                    tfidf_matrix.toarray() if sp.issparse(tfidf_matrix) else tfidf_matrix,
                    labels
                )
                inertia = kmeans.inertia_

                results.append({
                    "k": k,
                    "silhouette": round(sil, 4),
                    "davies_bouldin": round(float(db), 4),
                    "inertia": round(float(inertia), 2),
                })
        except Exception:
            continue

    return results


def safe_silhouette(matrix, labels, metric='cosine'):
    """Safe calculation of silhouette score, returns 0.0 on error."""
    if len(set(labels)) > 1 and len(set(labels)) < matrix.shape[0]:
        try:
            return float(silhouette_score(matrix, labels, metric=metric))
        except Exception:
            return 0.0
    return 0.0


def compute_per_cluster_silhouette(matrix, labels, metric='cosine') -> Dict[int, float]:
    """
    Hitung silhouette score per cluster dengan merata-ratakan skor sampel di masing-masing cluster.
    Digunakan untuk mengidentifikasi cluster yang 'lemah' atau 'kuat'.
    
    Returns:
        Dict: {cluster_id: float_score}
    """
    from sklearn.metrics import silhouette_samples
    unique_labels = set(labels)
    # Jika hanya 1 cluster, silhouette tidak bisa dihitung
    if len(unique_labels) <= 1 or len(unique_labels) >= matrix.shape[0]:
        return {label: 0.0 for label in set(labels)}
        
    try:
        sample_silhouettes = silhouette_samples(matrix, labels, metric=metric)
        cluster_scores = {}
        for label in unique_labels:
            if label == -1:  # Abaikan noise
                continue
            # Ambil skor untuk sample yang berada di cluster ini
            cluster_mask = (labels == label)
            avg_score = float(np.mean(sample_silhouettes[cluster_mask]))
            cluster_scores[label] = avg_score
        return cluster_scores
    except Exception:
        return {label: 0.0 for label in set(labels)}


def safe_davies_bouldin(matrix, labels):
    """
    Safe calculation of Davies-Bouldin Index, returns None on error.
    DB index uses euclidean distance internally (sklearn default).
    For sparse TF-IDF matrices we convert to dense first.
    Lower is better; 0 is perfect separation.
    """
    unique_labels = set(labels)
    if len(unique_labels) < 2 or len(unique_labels) >= matrix.shape[0]:
        return None
    try:
        # Convert sparse to dense if needed (DB score needs dense array)
        dense = matrix.toarray() if sp.issparse(matrix) else np.asarray(matrix)
        return float(davies_bouldin_score(dense, labels))
    except Exception:
        return None


def get_recommended_k(evaluation_results: List[Dict]) -> int:
    """
    Beri rekomendasi k berdasarkan gabungan Silhouette dan Davies-Bouldin.
    Silhouette: lebih tinggi lebih baik
    Davies-Bouldin: lebih rendah lebih baik

    PENTING: Ini hanya REKOMENDASI. User tetap menentukan final.

    Returns:
        Recommended k (int)
    """
    if not evaluation_results:
        return 3

    # Normalisasi skor
    sil_scores = [r["silhouette"] for r in evaluation_results]
    db_scores = [r["davies_bouldin"] for r in evaluation_results]

    if max(sil_scores) == min(sil_scores):
        return evaluation_results[0]["k"]

    sil_range = max(sil_scores) - min(sil_scores)
    db_range = max(db_scores) - min(db_scores)

    best_score = -float('inf')
    best_k = evaluation_results[0]["k"]

    for r in evaluation_results:
        # Normalisasi 0-1
        norm_sil = (r["silhouette"] - min(sil_scores)) / sil_range if sil_range > 0 else 0
        norm_db = (max(db_scores) - r["davies_bouldin"]) / db_range if db_range > 0 else 0

        combined = 0.5 * norm_sil + 0.5 * norm_db
        if combined > best_score:
            best_score = combined
            best_k = r["k"]

    return best_k


# ---------------------------------------------------------------------------
# K-MEANS CLUSTERING
# ---------------------------------------------------------------------------

def run_kmeans(tfidf_matrix, k: int, random_state: int = 42):
    """
    Jalankan K-Means clustering.

    Returns:
        (kmeans_model, labels_array)
    """
    # Proteksi edge case
    n_samples = tfidf_matrix.shape[0]
    k = max(2, min(k, n_samples - 1))

    kmeans = KMeans(
        n_clusters=k,
        random_state=random_state,
        n_init=10,
        max_iter=300,
    )
    labels = kmeans.fit_predict(tfidf_matrix)
    return kmeans, labels


# ---------------------------------------------------------------------------
# AGGLOMERATIVE CLUSTERING
# ---------------------------------------------------------------------------

def run_agglomerative(tfidf_matrix, k: int, linkage: str = "ward"):
    """
    Jalankan Agglomerative Clustering.

    Note: Ward linkage memerlukan dense matrix.

    Returns:
        (model, labels_array)
    """
    n_samples = tfidf_matrix.shape[0]
    k = max(2, min(k, n_samples - 1))

    # Convert sparse ke dense untuk ward linkage
    if sp.issparse(tfidf_matrix):
        dense = tfidf_matrix.toarray()
    else:
        dense = tfidf_matrix

    if linkage == "ward":
        model = AgglomerativeClustering(n_clusters=k, linkage="ward")
    else:
        model = AgglomerativeClustering(n_clusters=k, linkage=linkage, metric="cosine")

    labels = model.fit_predict(dense)
    return model, labels


# ---------------------------------------------------------------------------
# DBSCAN CLUSTERING (untuk noise/outlier detection)
# ---------------------------------------------------------------------------

def run_dbscan(tfidf_matrix, eps: float = 0.3, min_samples: int = 3):
    """
    Jalankan DBSCAN untuk noise detection.

    Respons dengan label -1 → noise/outlier → masuk Unclassified.

    Returns:
        (model, labels_array)
        Labels dengan -1 = noise
    """
    if sp.issparse(tfidf_matrix):
        dense = tfidf_matrix.toarray()
    else:
        dense = tfidf_matrix

    # Normalize untuk cosine similarity
    dense_normalized = normalize(dense)

    model = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
    labels = model.fit_predict(dense_normalized)
    return model, labels


# ---------------------------------------------------------------------------
# AUTO-BENCHMARK CLUSTERING (THE NEW ENGINE)
# ---------------------------------------------------------------------------

def filter_zero_vectors(tfidf_matrix, resp_ids: list) -> Tuple[np.ndarray, list, list]:
    """
    Hapus baris yang berisi 0 mutlak di tfidf_matrix.
    Returns:
        filtered_matrix, valid_resp_ids, zero_resp_ids
    """
    if sp.issparse(tfidf_matrix):
        row_norms = np.array(tfidf_matrix.power(2).sum(axis=1)).flatten()
    else:
        row_norms = np.sum(tfidf_matrix**2, axis=1)

    non_zero_idx = row_norms > 0
    zero_idx = ~non_zero_idx

    filtered_matrix = tfidf_matrix[non_zero_idx]
    
    valid_ids = [resp_ids[i] for i in range(len(resp_ids)) if non_zero_idx[i]]
    zero_ids = [resp_ids[i] for i in range(len(resp_ids)) if zero_idx[i]]

    return filtered_matrix, valid_ids, zero_ids


def compute_elbow_data(matrix, k_max: int = 12, random_state: int = 42) -> List[Dict]:
    """
    Hitung inertia K-Means untuk setiap K dari 2 s.d. k_max.
    Digunakan untuk Elbow Method — membantu memilih K yang optimal.

    Returns:
        List of dicts: [{"k": int, "inertia": float}, ...]
    """
    dense = matrix.toarray() if sp.issparse(matrix) else np.asarray(matrix)
    n_samples = dense.shape[0]
    k_max = min(k_max, n_samples - 1)  # K tidak boleh >= n_samples

    results = []
    for k in range(2, k_max + 1):
        try:
            km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
            km.fit(dense)
            results.append({"k": k, "inertia": float(km.inertia_)})
        except Exception:
            break
    return results


def compute_cluster_similarity_matrix(model, matrix) -> Optional[np.ndarray]:
    """
    Hitung matriks cosine similarity antar centroid cluster (hanya K-Means).
    Digunakan untuk Cluster Similarity Heatmap.

    Returns:
        np.ndarray shape (n_clusters, n_clusters), atau None jika tidak tersedia.
    """
    if model is None or not hasattr(model, 'cluster_centers_'):
        return None
    try:
        centers = model.cluster_centers_
        # Normalize agar cosine similarity = dot product
        norms = np.linalg.norm(centers, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normalized = centers / norms
        sim_matrix = np.dot(normalized, normalized.T)
        return sim_matrix
    except Exception:
        return None



def run_clustering_benchmark(tfidf_matrix, resp_ids: list, random_state: int = 42) -> dict:
    """
    Jalankan K-Means, Agglomerative, dan DBSCAN.
    Evaluasi menggunakan Composite Score.
    Jika kualitas sangat buruk, return method_name = "REJECTED".
    """
    # 1. Zero vector filtering
    filtered_matrix, valid_ids, zero_ids = filter_zero_vectors(tfidf_matrix, resp_ids)
    n_valid = filtered_matrix.shape[0]

    # Baseline jika data terlalu sedikit
    if n_valid < 5:
        return {
            "method_name": "REJECTED",
            "reason": "Terlalu sedikit respons valid (tidak cukup untuk clustering).",
            "benchmark_report": [],
            "zero_ids": zero_ids,
            "valid_ids": valid_ids
        }

    benchmark_report = []

    # Helper hitung skor
    def evaluate_result(name, labels, model=None):
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = sum(labels == -1)
        noise_ratio = n_noise / n_valid if n_valid > 0 else 1.0

        if n_clusters < 2:
            return None

        sil = safe_silhouette(filtered_matrix, labels, metric='cosine')
        
        # Penalti jika noise terlalu tinggi (lebih dari 50% = minus poin)
        # Penalti juga jika clusters terlalu banyak (misal > 30% dari n_valid)
        too_many_clusters_penalty = 0.0
        if n_clusters > n_valid * 0.3:
            too_many_clusters_penalty = 0.1

        # Composite score
        composite = sil - (noise_ratio * 0.2) - too_many_clusters_penalty

        return {
            "method_name": name,
            "model": model,
            "labels": labels,
            "n_clusters": n_clusters,
            "n_noise": n_noise,
            "silhouette": sil,
            "noise_ratio": noise_ratio,
            "composite_score": composite,
        }

    # METHOD A: K-Means (K = min(10, n_valid//3))
    k_kmeans = max(2, min(10, n_valid // 3))
    model_km, labels_km = run_kmeans(filtered_matrix, k=k_kmeans, random_state=random_state)
    res_km = evaluate_result(f"K-Means (K={k_kmeans})", labels_km, model_km)
    if res_km: benchmark_report.append(res_km)

    # METHOD B: Agglomerative (distance_threshold = 0.7)
    try:
        model_agg = AgglomerativeClustering(n_clusters=None, distance_threshold=0.7, metric='cosine', linkage='average')
        labels_agg = model_agg.fit_predict(filtered_matrix.toarray() if sp.issparse(filtered_matrix) else filtered_matrix)
        res_agg = evaluate_result("Agglomerative (Thresh 0.7)", labels_agg, model_agg)
        if res_agg: benchmark_report.append(res_agg)
    except Exception as e:
        pass

    # METHOD C: DBSCAN (eps = 0.3, min_samples = 2)
    try:
        model_db, labels_db = run_dbscan(filtered_matrix, eps=0.3, min_samples=2)
        res_db = evaluate_result("DBSCAN (eps 0.3)", labels_db, model_db)
        if res_db: benchmark_report.append(res_db)
    except Exception as e:
        pass

    # Sort berdasarkan composite score terbaik
    benchmark_report.sort(key=lambda x: x["composite_score"], reverse=True)

    if not benchmark_report:
        return {
            "method_name": "REJECTED",
            "reason": "Gagal membentuk minimal 2 kelompok.",
            "benchmark_report": benchmark_report,
            "zero_ids": zero_ids,
            "valid_ids": valid_ids
        }

    best = benchmark_report[0]

    # FAIL-SAFE: Jika metode terbaik pun punya composite_score buruk
    if best["composite_score"] < 0.05 or best["silhouette"] < 0.05:
         return {
            "method_name": "REJECTED",
            "reason": f"Kualitas clustering terlalu rendah (Best Silhouette = {best['silhouette']:.3f}).",
            "benchmark_report": benchmark_report,
            "zero_ids": zero_ids,
            "valid_ids": valid_ids
        }

    # Jika lulus, kembalikan best
    best["zero_ids"] = zero_ids
    best["valid_ids"] = valid_ids
    best["benchmark_report"] = benchmark_report
    best["filtered_matrix"] = filtered_matrix
    return best


# ---------------------------------------------------------------------------
# KEYWORD EXTRACTION & COHERENCE
# ---------------------------------------------------------------------------

def compute_cluster_quality_score(
    top_keywords: List[str],
    top_phrases: List[str],
    context_stopwords: List[str],
    domain_stopwords: set,
    silhouette: float = None,
    size: int = 0,
) -> Tuple[str, str]:
    """
    Hitung kualitas kandidat cluster dan kembalikan traffic light label + alasan.

    Scoring rules (baru):
    - 🟢 Good        : silhouette normal (>=0.05), keyword >= 3, ada top phrase, size >= 5
    - 🟡 Needs Review: silhouette normal tapi (keyword < 3 ATAU top phrase kosong ATAU size 3-5)
    - 🔴 Low Quality : size <= 2 ATAU (keyword <= 1 dan tidak ada top phrase)

    Returns:
        (score_label, reason_str)
        Contoh: ("🔴 Low Quality", "Cluster sangat kecil (2 respons).")
    """
    if size <= 2:
        return "🔴 Low Quality", f"Cluster sangat kecil ({size} respons)."
        
    kw_count = len(top_keywords) if top_keywords else 0
    ph_count = len(top_phrases) if top_phrases else 0
    
    if kw_count <= 1 and ph_count == 0:
        return "🔴 Low Quality", "Hanya ada 1 atau 0 keyword bermakna dan tidak ada frasa."

    context_set = {w.lower() for w in (context_stopwords or [])}
    filler_set = {w.lower() for w in (domain_stopwords or set()) if ' ' not in w}

    context_count = sum(1 for w in top_keywords if w.lower() in context_set)
    filler_count = sum(1 for w in top_keywords if w.lower() in filler_set)
    total_contaminated = context_count + filler_count
    prop_contaminated = total_contaminated / len(top_keywords)

    reasons = []

    # Silhouette assessment
    sil_issue = False
    sil_critical = False
    if silhouette is not None:
        if silhouette < 0.0:
            reasons.append(f"Silhouette negatif ({silhouette:.3f}), batas cluster tumpang tindih.")
            sil_critical = True
        elif silhouette < 0.05:
            reasons.append(f"Silhouette sangat rendah ({silhouette:.3f}).")
            sil_issue = True
        elif silhouette < 0.15:
            reasons.append(f"Silhouette rendah ({silhouette:.3f}).")

    # Context/filler contamination (sebagai faktor tambahan, bukan utama lagi)
    if prop_contaminated > 0.60:
        reasons.append(f"Keywords didominasi filler/konteks ({prop_contaminated*100:.0f}%).")
        sil_critical = True # Anggap critical jika isi hanya filler

    # Cek kriteria Good vs Needs Review
    is_good = True
    if sil_critical:
        is_good = False
    elif sil_issue:
        is_good = False
    
    if kw_count < 3:
        reasons.append(f"Keyword terlalu sedikit ({kw_count}).")
        is_good = False
        
    if ph_count == 0:
        reasons.append("Tidak ada top phrase yang signifikan.")
        is_good = False
        
    if size < 5 and size > 2:
        reasons.append(f"Ukuran kelompok kecil ({size} respons).")
        is_good = False

    # Determine traffic light
    if sil_critical:
        score = "🔴 Low Quality"
    elif is_good:
        score = "🟢 Good"
    else:
        score = "🟡 Needs Review"

    reason = " ".join(reasons) if reasons else "Kualitas keywords dan silhouette dalam batas normal."
    return score, reason


def evaluate_cluster_coherence(
    top_keywords: List[str],
    context_stopwords: List[str],
    domain_stopwords: set,
    silhouette_score: float = None,
) -> Optional[str]:
    """
    Wrapper untuk backward compatibility — gunakan compute_cluster_quality_score() untuk UI baru.
    Mengembalikan warning string jika kualitas dipertanyakan, atau None jika bagus.
    """
    score, reason = compute_cluster_quality_score(
        top_keywords=top_keywords,
        top_phrases=[], # Backward compat fallback
        context_stopwords=context_stopwords,
        domain_stopwords=domain_stopwords,
        silhouette=silhouette_score,
        size=len(top_keywords),  # fallback
    )
    if score != "🟢 Good":
        return f"⚠️ {reason}"
    return None

def get_top_keywords_from_centroids(
    kmeans_model,
    vectorizer,
    n_words: int = 10,
    domain_stopwords: Optional[set] = None,
) -> Dict:
    """
    Ekstrak top keywords per cluster dari centroid K-Means.
    Filter filler words agar tidak mendominasi.

    Returns:
        dict {cluster_id: [keyword1, ...]}
    """
    centroids = kmeans_model.cluster_centers_
    terms = vectorizer.get_feature_names_out()

    # Buat set stopword untuk filter
    filter_words = set()
    if domain_stopwords:
        filter_words.update({w.lower() for w in domain_stopwords})

    cluster_keywords = {}

    for i, centroid in enumerate(centroids):
        # Ambil lebih banyak dulu, lalu filter
        top_indices = centroid.argsort()[::-1]

        keywords = []
        for idx in top_indices:
            if centroid[idx] <= 0:
                break
            term = terms[idx]
            term_lower = term.lower()

            # Skip jika di filter
            if term_lower in filter_words:
                continue

            # Skip kata sangat pendek (hasil noise stemming)
            if len(term) < 2:
                continue

            keywords.append(term)
            if len(keywords) >= n_words:
                break

        cluster_keywords[i] = keywords

    return cluster_keywords


def get_top_keywords_for_labels(
    tfidf_matrix,
    labels: list,
    vectorizer,
    n_words: int = 10,
    domain_stopwords: Optional[set] = None,
) -> Dict:
    """
    Ekstrak top keywords untuk clustering yang tidak berbasis centroid
    (Agglomerative, DBSCAN).
    Gunakan rata-rata TF-IDF per cluster.

    Returns:
        dict {cluster_id: [keyword1, ...]}
    """
    terms = vectorizer.get_feature_names_out()
    filter_words = set()
    if domain_stopwords:
        filter_words.update({w.lower() for w in domain_stopwords})

    unique_labels = sorted(set(labels))
    cluster_keywords = {}

    for cluster_id in unique_labels:
        indices = [i for i, l in enumerate(labels) if l == cluster_id]
        if not indices:
            cluster_keywords[cluster_id] = []
            continue

        # Subset matrix untuk cluster ini
        subset = tfidf_matrix[indices]
        if sp.issparse(subset):
            mean_vec = np.array(subset.mean(axis=0)).flatten()
        else:
            mean_vec = subset.mean(axis=0)

        top_indices = mean_vec.argsort()[::-1]

        keywords = []
        for idx in top_indices:
            if mean_vec[idx] <= 0:
                break
            term = terms[idx]
            if term.lower() in filter_words or len(term) < 2:
                continue
            keywords.append(term)
            if len(keywords) >= n_words:
                break

        cluster_keywords[cluster_id] = keywords

    return cluster_keywords


def get_top_phrases_per_cluster(
    tfidf_matrix,
    labels: list,
    vectorizer,
    n_phrases: int = 5,
    domain_stopwords: Optional[set] = None,
) -> Dict:
    """
    Ekstrak top BIGRAM/PHRASE per cluster (dari feature yang mengandung spasi).

    Returns:
        dict {cluster_id: [phrase1, ...]}
    """
    terms = vectorizer.get_feature_names_out()
    filter_words = set()
    if domain_stopwords:
        filter_words.update({w.lower() for w in domain_stopwords})

    # Filter hanya bigram (mengandung spasi)
    bigram_indices = [i for i, t in enumerate(terms) if ' ' in t]

    if not bigram_indices:
        return {cid: [] for cid in set(labels)}

    unique_labels = sorted(set(labels))
    cluster_phrases = {}

    for cluster_id in unique_labels:
        indices = [i for i, l in enumerate(labels) if l == cluster_id]
        if not indices:
            cluster_phrases[cluster_id] = []
            continue

        subset = tfidf_matrix[indices]
        if sp.issparse(subset):
            mean_vec = np.array(subset.mean(axis=0)).flatten()
        else:
            mean_vec = subset.mean(axis=0)

        # Ambil hanya dari bigram indices
        bigram_scores = [(mean_vec[i], terms[i]) for i in bigram_indices if mean_vec[i] > 0]
        bigram_scores.sort(reverse=True)

        phrases = []
        for score, phrase in bigram_scores:
            # Filter jika semua kata dalam phrase adalah stopword
            phrase_words = phrase.split()
            if all(w.lower() in filter_words for w in phrase_words):
                continue
            phrases.append(phrase)
            if len(phrases) >= n_phrases:
                break

        cluster_phrases[cluster_id] = phrases

    return cluster_phrases


# ---------------------------------------------------------------------------
# REPRESENTATIVE RESPONSES
# ---------------------------------------------------------------------------

def get_representative_responses(
    tfidf_matrix,
    labels: list,
    response_ids: list,
    n_reps: int = 5,
    model=None,
) -> dict:
    """
    Temukan respons paling representatif per cluster.
    Berdasarkan jarak ke centroid (K-Means) atau jarak antar response (lainnya).

    Respons yang ditampilkan HARUS dari data asli — tidak pernah dibuat baru.
    Selalu dapat dilacak ke response_id.

    Returns:
        dict {cluster_id: [response_id1, ...]}
    """
    unique_labels = sorted(set(labels))
    cluster_reps = {}

    # Jika ada centroid (K-Means)
    has_centroids = hasattr(model, 'cluster_centers_') if model else False

    for cluster_id in unique_labels:
        # Kumpulkan indeks dalam cluster ini
        in_cluster = [i for i, l in enumerate(labels) if l == cluster_id]
        if not in_cluster:
            cluster_reps[cluster_id] = []
            continue

        cluster_matrix = tfidf_matrix[in_cluster]

        if has_centroids:
            # Similarity ke centroid
            centroid = model.cluster_centers_[cluster_id].reshape(1, -1)
            if sp.issparse(cluster_matrix):
                cluster_dense = cluster_matrix.toarray()
            else:
                cluster_dense = cluster_matrix
            similarities = cosine_similarity(cluster_dense, centroid).flatten()
        else:
            # Gunakan mean vector sebagai pseudo-centroid
            if sp.issparse(cluster_matrix):
                mean_vec = np.array(cluster_matrix.mean(axis=0))
            else:
                mean_vec = cluster_matrix.mean(axis=0)
            mean_vec = mean_vec.reshape(1, -1)
            if sp.issparse(cluster_matrix):
                cluster_dense = cluster_matrix.toarray()
            else:
                cluster_dense = cluster_matrix
            similarities = cosine_similarity(cluster_dense, mean_vec).flatten()

        # Ambil top-N yang paling similar
        n_to_get = min(n_reps, len(in_cluster))
        top_local_indices = similarities.argsort()[::-1][:n_to_get]

        # Map ke response_id asli
        rep_ids = [response_ids[in_cluster[local_idx]] for local_idx in top_local_indices]
        cluster_reps[cluster_id] = rep_ids

    return cluster_reps


# ---------------------------------------------------------------------------
# BACKWARD COMPATIBILITY
# ---------------------------------------------------------------------------
# Fungsi-fungsi lama yang masih diimpor di tempat lain — dipertahankan
# agar tidak menyebabkan ImportError di modul lain.

def preprocess_for_clustering(texts, use_stemming=False, extra_stopwords=None):
    """
    DEPRECATED: Gunakan open_ended_preprocessing.preprocess_pipeline() untuk analisis baru.
    Dipertahankan untuk backward compatibility dengan tab_basic.
    """
    from utils.text_analysis import clean_text, tokenize, remove_stopwords
    processed = []
    for text in texts:
        if not isinstance(text, str) or not text.strip():
            processed.append("")
            continue
        cleaned = clean_text(text, use_stemming=use_stemming)
        words = tokenize(cleaned)
        words = remove_stopwords(words, extra_stopwords)
        processed.append(" ".join(words))
    return processed


def find_optimal_k(tfidf_matrix, min_k=2, max_k=10):
    """DEPRECATED: Gunakan evaluate_cluster_range(). Dipertahankan untuk backward compat."""
    results = evaluate_cluster_range(tfidf_matrix, min_k=min_k, max_k=max_k)
    if not results:
        return 1, []
    scores = [(r["k"], r["silhouette"]) for r in results]
    optimal_k = max(scores, key=lambda x: x[1])[0]
    return optimal_k, scores


def run_kmeans_legacy(tfidf_matrix, k, random_state=42):
    """Alias untuk backward compat."""
    return run_kmeans(tfidf_matrix, k, random_state)


def get_top_keywords(kmeans, vectorizer, n_words=10):
    """DEPRECATED: Gunakan get_top_keywords_from_centroids(). Dipertahankan untuk backward compat."""
    return get_top_keywords_from_centroids(kmeans, vectorizer, n_words=n_words)


def get_representative_docs(tfidf_matrix, kmeans, original_texts, n_docs=3):
    """DEPRECATED: Gunakan get_representative_responses(). Dipertahankan untuk backward compat."""
    labels = list(kmeans.labels_)
    # Buat pseudo response_ids (index based)
    resp_ids = list(range(len(labels)))
    rep_id_dict = get_representative_responses(tfidf_matrix, labels, resp_ids, n_reps=n_docs, model=kmeans)

    # Convert back ke teks untuk backward compat
    cluster_reps = {}
    for cluster_id, id_list in rep_id_dict.items():
        cluster_reps[cluster_id] = []
        for idx in id_list:
            if 0 <= idx < len(original_texts) and isinstance(original_texts[idx], str):
                cluster_reps[cluster_id].append(original_texts[idx])
    return cluster_reps
