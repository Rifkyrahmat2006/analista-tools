"""
Open-Ended State Management
=============================
Manajemen session state Streamlit untuk modul analisis pertanyaan terbuka.

Menjamin:
- Clustering tidak dijalankan ulang hanya karena Streamlit rerun
- Perubahan analis (rename/merge/split/move/delete) tidak hilang
- Audit trail tersimpan per sesi
- Analysis run dapat dilacak

STATE KEYS (semua dengan prefix 'oe_' untuk namespace):
    oe_target_col           : kolom yang sedang dianalisis
    oe_validated_df         : DataFrame hasil validasi respons
    oe_preprocessed_df      : DataFrame hasil preprocessing lengkap
    oe_tfidf_matrix         : sparse matrix TF-IDF (scipy)
    oe_vectorizer           : TfidfVectorizer yang sudah fit
    oe_candidate_groups     : dict {group_id: CandidateGroup}
    oe_group_order          : list urutan group_id (untuk UI)
    oe_final_mapping        : dict {response_id: theme_name}
    oe_analysis_runs        : list semua AnalysisRun
    oe_current_run_id       : ID run saat ini
    oe_audit_log            : list semua AuditEntry
    oe_is_finalized         : bool — apakah analisis sudah difinalisasi
    oe_final_theme_summary  : DataFrame ringkasan tema final
    oe_ambiguous_decisions  : dict {response_id: keputusan analis}
    oe_cluster_metrics      : dict {k: {silhouette, davies_bouldin}}
    oe_analysis_step        : step UI saat ini (1-6)
"""

import uuid
import hashlib
from datetime import datetime
from typing import Optional, Any, List, Dict, Tuple
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class CandidateGroup:
    """
    Representasi satu kandidat kelompok (cluster) sebelum divalidasi.
    BUKAN tema final — hanya kandidat yang menunggu keputusan analis.
    """
    group_id: str
    candidate_label: str          # Label otomatis: "Kandidat Kelompok 1"
    final_theme_name: str         # Diisi analis, default kosong
    response_ids: list            # List response_id yang ada di grup ini
    top_keywords: List[str]         # Top TF-IDF keywords
    top_phrases: List[str]           # Top bigram/phrase
    representative_response_ids: list  # 3-5 response_id paling representatif
    cluster_id: int               # ID cluster asli dari algoritma
    status: str                   # "Draft" | "Needs Review" | "Validated"
    is_other: bool = False        # Ditandai sebagai "Other" oleh analis
    silhouette_score: float = 0.0
    size: int = 0
    coherence_warning: Optional[str] = None  # Warning jika indikasi lexical bias/noise
    quality_score: str = ""                  # Traffic light: 🟢 Good | 🟡 Needs Review | 🔴 Low Quality
    quality_reason: str = ""                 # Alasan quality score

    def __post_init__(self):
        self.size = len(self.response_ids)


@dataclass
class AuditEntry:
    """Satu entri dalam audit trail."""
    timestamp: str
    action: str           # rename | merge | split | move | delete | validate | finalize
    entity_type: str      # group | response | theme
    entity_id: str
    old_value: Any
    new_value: Any
    user: str = "analyst"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "old_value": str(self.old_value),
            "new_value": str(self.new_value),
            "user": self.user,
        }


@dataclass
class AnalysisRun:
    """Metadata untuk satu analysis run."""
    run_id: str
    question_column: str
    dataset_id: str
    timestamp: str
    preprocessing_params: dict
    vectorizer_params: dict
    clustering_algorithm: str
    n_clusters: int
    random_state: int
    quality_metrics: dict
    n_valid_responses: int
    n_total_responses: int

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "question_column": self.question_column,
            "dataset_id": self.dataset_id,
            "timestamp": self.timestamp,
            "clustering_algorithm": self.clustering_algorithm,
            "n_clusters": self.n_clusters,
            "random_state": self.random_state,
            "n_valid_responses": self.n_valid_responses,
            "n_total_responses": self.n_total_responses,
            **self.preprocessing_params,
            **self.vectorizer_params,
        }


# ---------------------------------------------------------------------------
# STATE INITIALIZATION
# ---------------------------------------------------------------------------

def init_oe_state():
    """
    Inisialisasi semua state keys yang diperlukan oleh modul OE.
    Aman dipanggil berkali-kali — tidak akan menimpa state yang sudah ada.
    """
    defaults = {
        "oe_target_col": None,
        "oe_validated_df": None,
        "oe_preprocessed_df": None,
        "oe_tfidf_matrix": None,
        "oe_vectorizer": None,
        "oe_candidate_groups": {},      # dict {group_id: CandidateGroup}
        "oe_group_order": [],           # list[str] urutan group_id
        "oe_final_mapping": {},         # dict {response_id: theme_name}
        "oe_analysis_runs": [],         # list[AnalysisRun]
        "oe_current_run_id": None,
        "oe_audit_log": [],             # list[AuditEntry]
        "oe_is_finalized": False,
        "oe_final_theme_summary": None,
        "oe_ambiguous_decisions": {},   # dict {response_id: "valid"|"other"|"ignore"}
        "oe_cluster_metrics": {},       # dict {k: {silhouette, davies_bouldin}}
        "oe_analysis_step": 1,
        "oe_last_params_hash": None,    # Hash parameter untuk deteksi perubahan
        "oe_processing_done": False,    # Flag apakah clustering sudah dijalankan
        "oe_merge_suggestions": [],     # list of dict untuk saran penggabungan
        "oe_merge_threshold": 0.35,     # Threshold cosine similarity untuk saran penggabungan
        # Macro Theme Aggregation
        "oe_macro_themes": [],          # list of MacroTheme dicts setelah aggregasi
        "oe_top_macro_themes": [],      # list 10 macro theme terbesar (untuk human validation)
        # Question-Aware Mode (NEW)
        "oe_question_profiler_result": None,
        "oe_analysis_mode": None,       # Mode yang dipilih (concept, thematic, dll.)
        # Concept/Multi-label Results (NEW)
        "oe_concept_result": None,      # Output dari oe_results_builder
    }

    for key, default_val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


def reset_oe_analysis(reason: str = "manual_reset"):
    """
    Reset state analisis (setelah perubahan kolom/dataset/parameter).
    TIDAK menghapus audit_log dan analysis_runs — keduanya persistent.
    """
    keys_to_reset = [
        "oe_validated_df",
        "oe_preprocessed_df",
        "oe_tfidf_matrix",
        "oe_vectorizer",
        "oe_candidate_groups",
        "oe_group_order",
        "oe_final_mapping",
        "oe_current_run_id",
        "oe_is_finalized",
        "oe_final_theme_summary",
        "oe_ambiguous_decisions",
        "oe_cluster_metrics",
        "oe_last_params_hash",
        "oe_processing_done",
        "oe_merge_suggestions",
        "oe_macro_themes",
        "oe_top_macro_themes",
        "oe_concept_result",
    ]

    for key in keys_to_reset:
        if key in st.session_state:
            if key in ["oe_candidate_groups", "oe_final_mapping",
                       "oe_ambiguous_decisions", "oe_cluster_metrics"]:
                st.session_state[key] = {}
            elif key in ["oe_group_order", "oe_merge_suggestions", "oe_macro_themes", "oe_top_macro_themes"]:
                st.session_state[key] = []
            elif key in ["oe_is_finalized", "oe_processing_done"]:
                st.session_state[key] = False
            else:
                st.session_state[key] = None

    add_audit_entry(
        action="reset",
        entity_type="analysis",
        entity_id="system",
        old_value="previous_state",
        new_value=reason,
    )


def reset_oe_full(reason: str = "column_changed"):
    """Reset penuh termasuk target_col, profiler, dan mode."""
    reset_oe_analysis(reason=reason)
    st.session_state["oe_target_col"] = None
    st.session_state["oe_analysis_step"] = 1
    st.session_state["oe_question_profiler_result"] = None
    st.session_state["oe_analysis_mode"] = None


# ---------------------------------------------------------------------------
# PARAMETER HASH (untuk deteksi perubahan)
# ---------------------------------------------------------------------------

def compute_params_hash(
    col: str,
    use_stemming: bool,
    use_domain_sw: bool,
    extra_sw: str,
    algorithm: str,
    n_clusters: int,
    random_state: int,
    max_features: int,
    min_df: int,
) -> str:
    """Compute MD5 hash dari parameter analisis untuk mendeteksi perubahan."""
    param_str = f"{col}|{use_stemming}|{use_domain_sw}|{extra_sw}|{algorithm}|{n_clusters}|{random_state}|{max_features}|{min_df}"
    return hashlib.md5(param_str.encode()).hexdigest()


# ---------------------------------------------------------------------------
# ANALYSIS RUN MANAGEMENT
# ---------------------------------------------------------------------------

def create_analysis_run(
    question_column: str,
    dataset_id: str,
    preprocessing_params: dict,
    vectorizer_params: dict,
    clustering_algorithm: str,
    n_clusters: int,
    random_state: int,
    quality_metrics: dict,
    n_valid: int,
    n_total: int,
) -> str:
    """
    Buat analysis run baru dan simpan ke state.
    SETIAP kali parameter berubah dan clustering dijalankan ulang → run baru.
    Tidak menimpa run sebelumnya.

    Returns:
        run_id (str)
    """
    init_oe_state()

    run_id = str(uuid.uuid4())[:8].upper()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    run = AnalysisRun(
        run_id=run_id,
        question_column=question_column,
        dataset_id=dataset_id,
        timestamp=timestamp,
        preprocessing_params=preprocessing_params,
        vectorizer_params=vectorizer_params,
        clustering_algorithm=clustering_algorithm,
        n_clusters=n_clusters,
        random_state=random_state,
        quality_metrics=quality_metrics,
        n_valid_responses=n_valid,
        n_total_responses=n_total,
    )

    st.session_state["oe_analysis_runs"].append(run)
    st.session_state["oe_current_run_id"] = run_id

    add_audit_entry(
        action="run_analysis",
        entity_type="run",
        entity_id=run_id,
        old_value=None,
        new_value={
            "algorithm": clustering_algorithm,
            "n_clusters": n_clusters,
            "n_valid": n_valid,
        },
    )

    return run_id


# ---------------------------------------------------------------------------
# CANDIDATE GROUP MANAGEMENT
# ---------------------------------------------------------------------------

def create_candidate_groups_from_clustering(
    cluster_labels: list,
    response_ids: list,
    top_keywords: dict,
    top_phrases: dict,
    representative_ids: dict,
    cluster_metrics: dict = None,
) -> dict:
    """
    Buat CandidateGroup dari hasil clustering.
    Semua group berstatus 'Draft' — belum ada tema final.

    Args:
        cluster_labels: list label cluster per response (dari sklearn)
        response_ids: list response_id yang sesuai urutan
        top_keywords: dict {cluster_id: [keyword1, ...]}
        top_phrases: dict {cluster_id: [phrase1, ...]}
        representative_ids: dict {cluster_id: [resp_id1, ...]}
        cluster_metrics: dict {cluster_id: float silhouette}

    Returns:
        dict {group_id: CandidateGroup}
    """
    groups = {}
    order = []

    unique_clusters = sorted(set(cluster_labels))

    for cluster_id in unique_clusters:
        # Handle DBSCAN noise (-1)
        if cluster_id == -1:
            label = "Unclassified / Noise"
            is_other = True
        else:
            label = f"Kandidat Kelompok {cluster_id + 1}"
            is_other = False

        group_id = f"GRP_{str(uuid.uuid4())[:6].upper()}"

        # Kumpulkan response_id yang ada di cluster ini (deduplikasi jika multi-label)
        resp_ids_in_cluster = list(set([
            response_ids[i]
            for i, lbl in enumerate(cluster_labels)
            if lbl == cluster_id
        ]))

        sil_score = 0.0
        if cluster_metrics and cluster_id in cluster_metrics:
            sil_score = cluster_metrics.get(cluster_id, 0.0)

        group = CandidateGroup(
            group_id=group_id,
            candidate_label=label,
            final_theme_name="",
            response_ids=resp_ids_in_cluster,
            top_keywords=top_keywords.get(cluster_id, []),
            top_phrases=top_phrases.get(cluster_id, []),
            representative_response_ids=representative_ids.get(cluster_id, []),
            cluster_id=cluster_id,
            status="Draft",
            is_other=is_other,
            silhouette_score=sil_score,
        )
        group.size = len(resp_ids_in_cluster)

        groups[group_id] = group
        order.append(group_id)

    return groups, order


def validate_group(group_id: str, theme_name: str):
    """Validasi satu group dengan memberikan nama tema final."""
    groups = st.session_state.get("oe_candidate_groups", {})
    if group_id not in groups:
        return

    group = groups[group_id]
    old_theme = group.final_theme_name
    old_status = group.status

    group.final_theme_name = theme_name.strip()
    group.status = "Validated"

    add_audit_entry(
        action="validate",
        entity_type="group",
        entity_id=group_id,
        old_value={"theme": old_theme, "status": old_status},
        new_value={"theme": theme_name, "status": "Validated"},
    )

    st.session_state["oe_candidate_groups"][group_id] = group

def update_merge_suggestions():
    """Update merge suggestions list di session state berdasarkan state group terkini."""
    from utils.merge_suggestions import calculate_merge_suggestions
    groups = st.session_state.get("oe_candidate_groups", {})
    tfidf_matrix = st.session_state.get("oe_tfidf_matrix")
    resp_ids = st.session_state.get("oe_resp_ids_for_clustering")
    threshold = st.session_state.get("oe_merge_threshold", 0.35)
    
    if tfidf_matrix is not None and resp_ids is not None:
        suggestions = calculate_merge_suggestions(groups, tfidf_matrix, resp_ids, threshold)
        st.session_state["oe_merge_suggestions"] = suggestions
    else:
        st.session_state["oe_merge_suggestions"] = []



def merge_groups(group_ids: List[str], new_theme_name: str):
    """
    Merge beberapa group menjadi satu group baru.
    Semua response dari group-group sumber dipindahkan ke group baru.
    """
    groups = st.session_state.get("oe_candidate_groups", {})
    order = st.session_state.get("oe_group_order", [])

    if len(group_ids) < 2:
        return

    # Kumpulkan semua data dari groups yang akan di-merge
    all_response_ids = []
    all_keywords = []
    all_phrases = []
    all_repr_ids = []

    for gid in group_ids:
        if gid in groups:
            g = groups[gid]
            all_response_ids.extend(g.response_ids)
            all_keywords.extend(g.top_keywords)
            all_phrases.extend(g.top_phrases)
            all_repr_ids.extend(g.representative_response_ids)

    # Deduplicate keywords (pertahankan urutan)
    seen_kw = set()
    unique_keywords = [kw for kw in all_keywords if not (kw in seen_kw or seen_kw.add(kw))]
    seen_ph = set()
    unique_phrases = [ph for ph in all_phrases if not (ph in seen_ph or seen_ph.add(ph))]

    new_group_id = f"GRP_{str(uuid.uuid4())[:6].upper()}"
    # Hitung coherence (rata-rata cosine similarity dari response ke centroid)
    tfidf_matrix = st.session_state.get("oe_tfidf_matrix")
    resp_ids = st.session_state.get("oe_resp_ids_for_clustering")
    is_coherent = True
    if tfidf_matrix is not None and resp_ids is not None:
        resp_id_to_idx = {rid: i for i, rid in enumerate(resp_ids)}
        indices = [resp_id_to_idx[rid] for rid in all_response_ids if rid in resp_id_to_idx]
        if len(indices) > 0:
            group_matrix = tfidf_matrix[indices]
            from sklearn.metrics.pairwise import cosine_similarity
            import scipy.sparse as sp
            import numpy as np
            if sp.issparse(group_matrix):
                centroid = np.array(group_matrix.mean(axis=0))
            else:
                centroid = group_matrix.mean(axis=0)
            
            sims = cosine_similarity(group_matrix, centroid.reshape(1, -1))
            mean_sim = sims.mean()
            if mean_sim < 0.25:  # threshold coherence
                is_coherent = False

    if is_coherent:
        status = "Validated"
        q_score = "🟢 Good"
        q_reason = "Hasil merge (koherensi internal baik)."
    else:
        status = "Needs Review"
        q_score = "🟡 Needs Review"
        q_reason = "⚠️ Coherence internal rendah setelah merge. Pastikan kelompok ini benar-benar membahas tema yang sama."

    new_group = CandidateGroup(
        group_id=new_group_id,
        candidate_label=f"Kandidat Kelompok (Merged)",
        final_theme_name=new_theme_name.strip(),
        response_ids=all_response_ids,
        top_keywords=unique_keywords[:10],
        top_phrases=unique_phrases[:5],
        representative_response_ids=all_repr_ids[:5],
        cluster_id=-99,  # merged group
        status=status,
        is_other=False,
    )
    new_group.size = len(all_response_ids)
    new_group.quality_score = q_score
    new_group.quality_reason = q_reason

    # Hapus group lama
    merge_pos = None
    for i, gid in enumerate(order):
        if gid == group_ids[0]:
            merge_pos = i
            break

    for gid in group_ids:
        if gid in groups:
            del groups[gid]
        if gid in order:
            order.remove(gid)

    # Tambahkan group baru di posisi group pertama yang di-merge
    if merge_pos is not None:
        order.insert(merge_pos, new_group_id)
    else:
        order.append(new_group_id)

    groups[new_group_id] = new_group
    st.session_state["oe_candidate_groups"] = groups
    st.session_state["oe_group_order"] = order

    add_audit_entry(
        action="merge",
        entity_type="group",
        entity_id=new_group_id,
        old_value=group_ids,
        new_value={"theme": new_theme_name, "size": len(all_response_ids)},
    )
    
    update_merge_suggestions()


def split_group(group_id: str, resp_ids_group_a: list, name_a: str, name_b: str):
    """
    Split satu group menjadi dua group baru.
    resp_ids_group_a: response_id yang akan masuk Group A
    Sisa masuk Group B.
    """
    groups = st.session_state.get("oe_candidate_groups", {})
    order = st.session_state.get("oe_group_order", [])

    if group_id not in groups:
        return

    original = groups[group_id]
    resp_ids_group_b = [r for r in original.response_ids if r not in resp_ids_group_a]

    # Group A
    gid_a = f"GRP_{str(uuid.uuid4())[:6].upper()}"
    group_a = CandidateGroup(
        group_id=gid_a,
        candidate_label=f"{original.candidate_label} (Split A)",
        final_theme_name=name_a.strip(),
        response_ids=resp_ids_group_a,
        top_keywords=original.top_keywords,
        top_phrases=original.top_phrases,
        representative_response_ids=[r for r in original.representative_response_ids if r in resp_ids_group_a],
        cluster_id=original.cluster_id,
        status="Needs Review",
        is_other=False,
    )
    group_a.size = len(resp_ids_group_a)

    # Group B
    gid_b = f"GRP_{str(uuid.uuid4())[:6].upper()}"
    group_b = CandidateGroup(
        group_id=gid_b,
        candidate_label=f"{original.candidate_label} (Split B)",
        final_theme_name=name_b.strip(),
        response_ids=resp_ids_group_b,
        top_keywords=original.top_keywords,
        top_phrases=original.top_phrases,
        representative_response_ids=[r for r in original.representative_response_ids if r in resp_ids_group_b],
        cluster_id=original.cluster_id,
        status="Needs Review",
        is_other=False,
    )
    group_b.size = len(resp_ids_group_b)

    # Replace original dengan dua group baru
    pos = order.index(group_id) if group_id in order else len(order)
    order.remove(group_id)
    order.insert(pos, gid_b)
    order.insert(pos, gid_a)
    del groups[group_id]
    groups[gid_a] = group_a
    groups[gid_b] = group_b

    st.session_state["oe_candidate_groups"] = groups
    st.session_state["oe_group_order"] = order

    add_audit_entry(
        action="split",
        entity_type="group",
        entity_id=group_id,
        old_value={"size": original.size},
        new_value={"group_a": gid_a, "size_a": len(resp_ids_group_a),
                   "group_b": gid_b, "size_b": len(resp_ids_group_b)},
    )
    
    update_merge_suggestions()


def move_response(response_id, from_group_id: str, to_group_id: str):
    """Pindahkan satu respons dari satu group ke group lain."""
    groups = st.session_state.get("oe_candidate_groups", {})

    if from_group_id not in groups or to_group_id not in groups:
        return

    source = groups[from_group_id]
    dest = groups[to_group_id]

    if response_id not in source.response_ids:
        return

    source.response_ids.remove(response_id)
    source.size = len(source.response_ids)

    if response_id not in dest.response_ids:
        dest.response_ids.append(response_id)
    dest.size = len(dest.response_ids)

    source.status = "Needs Review"
    dest.status = "Needs Review"

    groups[from_group_id] = source
    groups[to_group_id] = dest
    st.session_state["oe_candidate_groups"] = groups

    add_audit_entry(
        action="move",
        entity_type="response",
        entity_id=str(response_id),
        old_value=from_group_id,
        new_value=to_group_id,
    )
    
    update_merge_suggestions()


def delete_group(group_id: str):
    """Hapus satu group dan pindahkan responsenya ke Unclassified."""
    groups = st.session_state.get("oe_candidate_groups", {})
    order = st.session_state.get("oe_group_order", [])

    if group_id not in groups:
        return

    deleted = groups[group_id]

    # Cari atau buat group "Unclassified"
    unclassified_id = None
    for gid, g in groups.items():
        if g.candidate_label == "Unclassified / Other" and gid != group_id:
            unclassified_id = gid
            break

    if unclassified_id is None and deleted.response_ids:
        unclassified_id = f"GRP_{str(uuid.uuid4())[:6].upper()}"
        unclassified = CandidateGroup(
            group_id=unclassified_id,
            candidate_label="Unclassified / Other",
            final_theme_name="Other",
            response_ids=deleted.response_ids.copy(),
            top_keywords=[],
            top_phrases=[],
            representative_response_ids=[],
            cluster_id=-98,
            status="Validated",
            is_other=True,
        )
        unclassified.size = len(deleted.response_ids)
        groups[unclassified_id] = unclassified
        order.append(unclassified_id)
    elif unclassified_id:
        for rid in deleted.response_ids:
            if rid not in groups[unclassified_id].response_ids:
                groups[unclassified_id].response_ids.append(rid)
        groups[unclassified_id].size = len(groups[unclassified_id].response_ids)

    # Hapus group
    del groups[group_id]
    if group_id in order:
        order.remove(group_id)

    st.session_state["oe_candidate_groups"] = groups
    st.session_state["oe_group_order"] = order

    add_audit_entry(
        action="delete",
        entity_type="group",
        entity_id=group_id,
        old_value=deleted.candidate_label,
        new_value="deleted_to_unclassified",
    )
    
    update_merge_suggestions()


def mark_group_as_other(group_id: str):
    """Tandai seluruh group sebagai 'Other'."""
    groups = st.session_state.get("oe_candidate_groups", {})
    if group_id not in groups:
        return

    group = groups[group_id]
    old_theme = group.final_theme_name
    group.final_theme_name = "Other"
    group.is_other = True
    group.status = "Validated"

    groups[group_id] = group
    st.session_state["oe_candidate_groups"] = groups

    add_audit_entry(
        action="mark_other",
        entity_type="group",
        entity_id=group_id,
        old_value=old_theme,
        new_value="Other",
    )
    
    update_merge_suggestions()


# ---------------------------------------------------------------------------
# FINAL MAPPING
# ---------------------------------------------------------------------------

def build_final_mapping() -> dict:
    """
    Bangun final mapping {response_id: [theme_name_1, theme_name_2]} dari semua validated groups.
    Mendukung multi-label clustering untuk satu response_id.
    Hanya dari groups yang sudah divalidasi.
    SUMBER KEBENARAN FINAL untuk semua statistik dan laporan.
    """
    from collections import defaultdict
    groups = st.session_state.get("oe_candidate_groups", {})
    mapping = defaultdict(list)

    for group_id, group in groups.items():
        theme = group.final_theme_name if group.final_theme_name else "Unclassified"
        for resp_id in group.response_ids:
            if theme not in mapping[resp_id]:
                mapping[resp_id].append(theme)

    final_mapping = dict(mapping)
    st.session_state["oe_final_mapping"] = final_mapping
    return final_mapping


def compute_theme_frequency(final_mapping: dict, total_valid: int) -> pd.DataFrame:
    """
    Hitung frekuensi dan persentase setiap tema dari final_mapping.
    DENOMINATOR: total_valid (jumlah respons valid, bukan total df).
    """
    from collections import Counter
    theme_counts = Counter()
    for themes in final_mapping.values():
        if isinstance(themes, list):
            for t in set(themes):
                theme_counts[t] += 1
        else:
            theme_counts[themes] += 1
            
    rows = []
    for theme, count in sorted(theme_counts.items(), key=lambda x: -x[1]):
        pct = (count / total_valid * 100) if total_valid > 0 else 0
        rows.append({
            "Tema": theme,
            "Jumlah": count,
            "Persentase": round(pct, 1),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# MACRO THEME AGGREGATION (NEW)
# ---------------------------------------------------------------------------

def compute_macro_themes(
    groups: dict,
    tfidf_matrix,
    resp_ids: list,
    similarity_threshold: float = 0.40,
) -> List[Dict]:
    """
    Agregasi CandidateGroups yang saling mirip menjadi MacroTheme candidates.
    Ini BUKAN merge otomatis — hasilnya hanya REKOMENDASI aggregasi.
    Keputusan merge tetap di tangan analis.

    ALGORITMA:
    1. Hitung centroid cosine similarity antar semua non-Other groups
    2. Gunakan Union-Find (disjoint set) untuk mengelompokkan groups yang similar
    3. Setiap kelompok = satu Macro Theme candidate
    4. Hitung total response count per Macro Candidate

    Returns:
        List of dict, masing-masing satu MacroTheme candidate:
        [
            {
                "macro_id": "MC_001",
                "group_ids": [gid1, gid2, ...],
                "candidate_labels": [label1, label2, ...],
                "total_responses": 48,
                "top_keywords": [kw1, kw2, ...],  # union dari keywords
                "representative_group_id": gid,   # group terbesar dalam macro
                "is_single_group": True/False,     # True jika tidak di-aggregate
            },
            ...
        ]
        Diurutkan berdasarkan total_responses descending.
    """
    import scipy.sparse as sp
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    eval_groups = {gid: g for gid, g in groups.items() if not g.is_other and g.size > 0}
    group_ids = list(eval_groups.keys())
    n = len(group_ids)

    if n == 0:
        return []

    if tfidf_matrix is None or not resp_ids:
        # Fallback: setiap group jadi macro tersendiri
        result = []
        for i, gid in enumerate(group_ids):
            g = eval_groups[gid]
            result.append({
                "macro_id": f"MC_{i+1:03d}",
                "group_ids": [gid],
                "candidate_labels": [g.candidate_label],
                "total_responses": g.size,
                "top_keywords": g.top_keywords[:8],
                "top_phrases": g.top_phrases[:4],
                "representative_group_id": gid,
                "is_single_group": True,
            })
        result.sort(key=lambda x: x["total_responses"], reverse=True)
        return result

    # Map response_id → index baris tfidf_matrix
    resp_id_to_idx = {rid: i for i, rid in enumerate(resp_ids)}

    # Hitung centroid per group
    centroids = {}
    for gid, g in eval_groups.items():
        indices = [resp_id_to_idx[rid] for rid in g.response_ids if rid in resp_id_to_idx]
        if not indices:
            centroids[gid] = None
            continue
        sub = tfidf_matrix[indices]
        if sp.issparse(sub):
            c = np.array(sub.mean(axis=0))
        else:
            c = sub.mean(axis=0)
        centroids[gid] = c.reshape(1, -1)

    # Union-Find untuk clustering groups yang similar
    parent = {gid: gid for gid in group_ids}
    sizes = {gid: eval_groups[gid].size for gid in group_ids}
    total_valid = len(resp_ids)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
            sizes[py] += sizes[px]

    # Evaluasi pasangan dan urutkan berdasarkan similarity terbesar
    from utils.merge_suggestions import GENERIC_TERMS, _has_meaningful_overlap
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            gid_a = group_ids[i]
            gid_b = group_ids[j]
            c_a = centroids[gid_a]
            c_b = centroids[gid_b]

            if c_a is None or c_b is None:
                continue

            sim = float(cosine_similarity(c_a, c_b)[0][0])

            if sim >= similarity_threshold:
                # Cek meaningful overlap untuk mencegah false positive
                kw_a = list(eval_groups[gid_a].top_keywords or [])
                kw_b = list(eval_groups[gid_b].top_keywords or [])
                ph_a = list(eval_groups[gid_a].top_phrases or [])
                ph_b = list(eval_groups[gid_b].top_phrases or [])

                if _has_meaningful_overlap(kw_a, kw_b, ph_a, ph_b) or sim >= 0.60:
                    pairs.append((sim, gid_a, gid_b))
                    
    # Urutkan pairs (sim terbesar di-merge lebih dulu)
    pairs.sort(key=lambda x: x[0], reverse=True)
    
    max_merge_ratio = 0.45  # Maksimal 45% dari total data agar tidak ada grup dominan yang menelan semua
    for sim, gid_a, gid_b in pairs:
        root_a = find(gid_a)
        root_b = find(gid_b)
        
        if root_a != root_b:
            new_size = sizes[root_a] + sizes[root_b]
            if (new_size / total_valid) <= max_merge_ratio:
                union(root_a, root_b)

    # Kumpulkan macro groups
    macro_map: Dict[str, List[str]] = {}  # root_id -> list of group_ids
    for gid in group_ids:
        root = find(gid)
        if root not in macro_map:
            macro_map[root] = []
        macro_map[root].append(gid)

    # Bangun result
    result = []
    for mc_idx, (root, gids) in enumerate(macro_map.items()):
        total_resp = sum(eval_groups[gid].size for gid in gids)

        # Ambil group terbesar sebagai representative
        repr_gid = max(gids, key=lambda gid: eval_groups[gid].size)

        # Gabungkan keywords (tanpa duplikat, urutan berdasarkan frekuensi)
        all_kw = []
        for gid in gids:
            all_kw.extend(eval_groups[gid].top_keywords or [])
        # Hitung frekuensi dan ambil top 10
        from collections import Counter
        kw_freq = Counter(all_kw)
        top_kw = [kw for kw, _ in kw_freq.most_common(10)]

        all_ph = []
        for gid in gids:
            all_ph.extend(eval_groups[gid].top_phrases or [])
        ph_freq = Counter(all_ph)
        top_ph = [ph for ph, _ in ph_freq.most_common(5)]

        result.append({
            "macro_id": f"MC_{mc_idx+1:03d}",
            "group_ids": gids,
            "candidate_labels": [eval_groups[gid].candidate_label for gid in gids],
            "total_responses": total_resp,
            "top_keywords": top_kw,
            "top_phrases": top_ph,
            "representative_group_id": repr_gid,
            "is_single_group": len(gids) == 1,
        })

    # Sort berdasarkan total response (descending)
    result.sort(key=lambda x: x["total_responses"], reverse=True)
    return result


def auto_merge_and_purge_candidate_groups(
    groups: dict,
    tfidf_matrix,
    resp_ids: list,
    similarity_threshold: float = 0.65,
) -> Tuple[dict, list]:
    """
    Otomatis menggabungkan kelompok-kelompok yang sangat mirip (berdasarkan macro themes)
    dan mengumpulkan sisa kelompok yang sangat kecil (size <= 2) menjadi satu kelompok Other.
    
    Tujuan: Menghindari pengguna harus me-merge secara manual 40+ kelompok pecahan.
    
    Returns:
        new_groups (dict), new_order (list)
    """
    # 1. Dapatkan rekomendasi penggabungan (Macro Themes)
    macro_candidates = compute_macro_themes(groups, tfidf_matrix, resp_ids, similarity_threshold=similarity_threshold)
    
    new_groups = {}
    new_order = []
    
    other_response_ids = set()
    other_keywords = []
    other_phrases = []
    
    # Kumpulkan grup yang dari awal sudah Other
    for gid, g in groups.items():
        if g.is_other:
            other_response_ids.update(g.response_ids)
            other_keywords.extend(g.top_keywords or [])
            other_phrases.extend(g.top_phrases or [])
            
    # 2. Bangun grup baru berdasarkan Macro Themes
    import uuid
    from collections import Counter
    
    cluster_idx = 1
    for mc in macro_candidates:
        gids = mc["group_ids"]
        
        # Gabungkan semua response_ids
        merged_resp_ids = set()
        for gid in gids:
            merged_resp_ids.update(groups[gid].response_ids)
            
        merged_size = len(merged_resp_ids)
        
        # Jika hasil gabungan tetap <= 2, masukkan ke Other saja
        if merged_size <= 2:
            other_response_ids.update(merged_resp_ids)
            other_keywords.extend(mc["top_keywords"])
            other_phrases.extend(mc["top_phrases"])
            continue
            
        # Jika > 2, buat grup baru
        new_gid = f"GRP_{str(uuid.uuid4())[:6].upper()}"
        
        # Ambil representative_ids dari grup terbesar
        repr_gid = mc["representative_group_id"]
        repr_ids = groups[repr_gid].representative_response_ids
        
        # Kualitas kita recalculate atau ambil max
        q_score, q_reason = "🟢 Good", "Auto-merged (High Similarity ≥ 0.65)"
        if mc.get("is_single_group"):
            q_score, q_reason = groups[repr_gid].quality_score, groups[repr_gid].quality_reason
        
        new_group = CandidateGroup(
            group_id=new_gid,
            candidate_label=f"Kandidat Kelompok {cluster_idx}",
            final_theme_name="",
            response_ids=list(merged_resp_ids),
            top_keywords=mc["top_keywords"],
            top_phrases=mc["top_phrases"],
            representative_response_ids=repr_ids,
            cluster_id=cluster_idx,
            status="Draft",
            is_other=False,
            silhouette_score=groups[repr_gid].silhouette_score,  # estimasi
            quality_score=q_score,
            quality_reason=q_reason
        )
        new_group.size = merged_size
        
        new_groups[new_gid] = new_group
        new_order.append(new_gid)
        cluster_idx += 1

    # 3. Sub-clustering Otomatis untuk Unclassified / Noise (Second-Pass Clustering)
    if len(other_response_ids) >= 5:
        try:
            from sklearn.cluster import KMeans
            # Cari indeks dari other_response_ids di dalam resp_ids
            other_indices = [i for i, rid in enumerate(resp_ids) if rid in other_response_ids]
            
            if other_indices:
                mat_other = tfidf_matrix[other_indices]
                k_other = min(5, len(other_indices) // 4)
                k_other = max(2, k_other)
                
                km_other = KMeans(n_clusters=k_other, random_state=42)
                lbls_other = km_other.fit_predict(mat_other)
                
                # Coba ambil vectorizer dari session_state untuk penamaan keyword
                vectorizer = st.session_state.get("oe_vectorizer")
                vocab_other = vectorizer.get_feature_names_out() if vectorizer else None

                new_other_ids = set()
                # Proses setiap sub-cluster
                for i in range(k_other):
                    c_mask = (lbls_other == i)
                    size = c_mask.sum()
                    c_resp_ids = [resp_ids[other_indices[idx]] for idx, val in enumerate(c_mask) if val]
                    
                    if size >= 3:
                        # Ekstrak Keyword
                        c_top_kw = []
                        c_top_phrases = []
                        if vocab_other is not None:
                            center = km_other.cluster_centers_[i]
                            top_indices = center.argsort()[::-1][:15]
                            extracted = [vocab_other[idx] for idx in top_indices if center[idx] > 0]
                            c_top_phrases = [kw for kw in extracted if ' ' in kw][:5]
                            c_top_kw = [kw for kw in extracted if ' ' not in kw][:10]

                        # Layak menjadi grup kandidat baru!
                        new_gid = f"GRP_{str(uuid.uuid4())[:6].upper()}"
                        
                        new_group = CandidateGroup(
                            group_id=new_gid,
                            candidate_label=f"Kandidat Kelompok {cluster_idx} (Auto-Recovered)",
                            final_theme_name="",
                            response_ids=c_resp_ids,
                            top_keywords=c_top_kw,
                            top_phrases=c_top_phrases,
                            representative_response_ids=c_resp_ids[:5],
                            cluster_id=cluster_idx,
                            status="Draft",
                            is_other=False,
                            silhouette_score=0.0,
                            quality_score="🟡 Needs Review",
                            quality_reason="Sub-tema berhasil ditarik otomatis dari tumpukan Unclassified"
                        )
                        new_group.size = size
                        new_groups[new_gid] = new_group
                        new_order.append(new_gid)
                        cluster_idx += 1
                    else:
                        # Tetap buang ke Other sejati
                        new_other_ids.update(c_resp_ids)
                        
                other_response_ids = new_other_ids

        except Exception:
            pass

    # 4. Buat satu grup besar sisa Other / Unclassified sejati
    if other_response_ids:
        other_gid = f"GRP_{str(uuid.uuid4())[:6].upper()}"
        
        # Dapatkan top keywords
        kw_freq = Counter(other_keywords)
        top_kw = [kw for kw, _ in kw_freq.most_common(10)]
        ph_freq = Counter(other_phrases)
        top_ph = [ph for ph, _ in ph_freq.most_common(5)]
        
        other_group = CandidateGroup(
            group_id=other_gid,
            candidate_label="Unclassified / Noise",
            final_theme_name="Tema Lainnya",
            response_ids=list(other_response_ids),
            top_keywords=top_kw,
            top_phrases=top_ph,
            representative_response_ids=list(other_response_ids)[:5],
            cluster_id=-1,
            status="Validated",
            is_other=True,
            silhouette_score=-1.0,
            quality_score="🔴 Low Quality",
            quality_reason="Sisa pecahan gabungan yang tidak membentuk sub-tema solid"
        )
        other_group.size = len(other_response_ids)
        new_groups[other_gid] = other_group
        new_order.append(other_gid)
        
    return new_groups, new_order



def get_top_macro_themes(macro_themes: List[Dict], n: int = 10) -> List[Dict]:
    """
    Ambil top-N macro themes berdasarkan jumlah respons.
    Jika total macro themes < N, kembalikan semua yang ada.

    Returns:
        List of macro theme dicts (max N), sorted descending by total_responses.
    """
    return macro_themes[:n]



# ---------------------------------------------------------------------------
# QUALITY CHECKS
# ---------------------------------------------------------------------------

def run_quality_checks() -> Tuple[List[str], List[str]]:
    """
    Jalankan semua quality checks sebelum finalisasi.
    Returns:
        (errors, warnings)
        errors: masalah kritis yang mencegah finalisasi
        warnings: peringatan informatif
    """
    errors = []
    warnings = []

    groups = st.session_state.get("oe_candidate_groups", {})
    preprocessed_df = st.session_state.get("oe_preprocessed_df")
    ambiguous_decisions = st.session_state.get("oe_ambiguous_decisions", {})

    if not groups:
        errors.append("Belum ada kandidat kelompok yang dibuat.")
        return errors, warnings

    # Check 1: Ada group yang belum divalidasi?
    unvalidated = [g for g in groups.values() if g.status != "Validated"]
    if unvalidated:
        errors.append(f"{len(unvalidated)} kandidat kelompok belum divalidasi: {', '.join(g.candidate_label for g in unvalidated)}")

    # Check 2: Ada group tanpa nama tema?
    no_theme = [g for g in groups.values() if not g.final_theme_name.strip()]
    if no_theme:
        errors.append(f"{len(no_theme)} group belum memiliki nama tema final.")

    # Check 3: Cek double-assignment (response di lebih dari satu group)
    all_resp_ids = []
    for g in groups.values():
        all_resp_ids.extend(g.response_ids)
    if len(all_resp_ids) != len(set(all_resp_ids)):
        from collections import Counter
        dup_ids = [rid for rid, cnt in Counter(all_resp_ids).items() if cnt > 1]
        errors.append(f"{len(dup_ids)} respons terhitung lebih dari satu kali (double-assignment).")

    # Check 4: Semua valid responses sudah ter-mapping?
    if preprocessed_df is not None:
        valid_count = (preprocessed_df["validation_status"] == "valid").sum()
        mapped_count = len(all_resp_ids)
        unmapped = valid_count - mapped_count
        if unmapped > 0:
            errors.append(f"{unmapped} respons valid belum memiliki kategori final.")

    # Check 5: Ada theme yang terlalu kecil (< 3 respons)?
    tiny_groups = [g for g in groups.values() if g.size < 3 and not g.is_other]
    if tiny_groups:
        for g in tiny_groups:
            warnings.append(f"Tema '{g.final_theme_name or g.candidate_label}' sangat kecil ({g.size} respons). Pertimbangkan merge atau Other.")

    # Check 6: Ada theme terlalu besar (> 60% total)?
    if all_resp_ids:
        for g in groups.values():
            if g.size / len(set(all_resp_ids)) > 0.6 and not g.is_other:
                warnings.append(f"Tema '{g.final_theme_name or g.candidate_label}' sangat besar ({g.size} respons, {g.size/len(set(all_resp_ids))*100:.0f}%). Pertimbangkan split.")

    # Check 7: Ada theme tanpa respons sama sekali? (Error)
    empty_groups = [g for g in groups.values() if g.size == 0]
    if empty_groups:
        errors.append(f"{len(empty_groups)} kelompok tidak memiliki respons (size=0). Hapus atau isi respons.")

    # Check 8: Ada kelompok dengan quality score Low Quality yang belum divalidasi?
    low_quality_groups = [g for g in groups.values() if g.quality_score == "🔴 Low Quality" and g.status != "Validated"]
    if low_quality_groups:
        warnings.append(
            f"{len(low_quality_groups)} kelompok memiliki quality score 🔴 Low Quality "
            f"dan belum divalidasi. ⚠️ Kualitas kelompok rendah. Respons belum menunjukkan "
            f"kemiripan tekstual yang kuat. Periksa representative responses dan "
            f"pertimbangkan merge, split, atau Other."
        )

    # Check 9: Ambiguous responses yang belum diputuskan?
    if preprocessed_df is not None:
        ambiguous_ids = preprocessed_df[preprocessed_df["validation_status"] == "ambiguous"]["response_id"].tolist()
        undecided = [rid for rid in ambiguous_ids if rid not in ambiguous_decisions]
        if undecided:
            warnings.append(
                f"{len(undecided)} respons ambigu belum ada keputusan (akan diabaikan dalam analisis)."
            )

    # Check 10: Unclassified valid responses
    if preprocessed_df is not None:
        valid_count = (preprocessed_df["validation_status"] == "valid").sum()
        classified_count = len(set(all_resp_ids))
        unclassified_valid = valid_count - classified_count
        if unclassified_valid > 0:
            warnings.append(
                f"{unclassified_valid} respons valid belum memiliki kandidat kelompok "
                f"(Unclassified Valid). Coverage: {classified_count}/{valid_count} "
                f"({classified_count/valid_count*100:.1f}%)."
            )

    return errors, warnings


# ---------------------------------------------------------------------------
# FINALIZATION
# ---------------------------------------------------------------------------

def finalize_analysis(final_mapping: dict, preprocessed_df: pd.DataFrame) -> pd.DataFrame:
    """
    Bekukan analisis dan hitung statistik final.
    Setelah dipanggil, is_finalized = True dan export diaktifkan.

    Returns:
        DataFrame ringkasan tema final
    """
    valid_count = (preprocessed_df["validation_status"] == "valid").sum()
    summary_df = compute_theme_frequency(final_mapping, total_valid=valid_count)

    # Tambahkan Top Keywords ke summary_df
    groups = st.session_state.get("oe_candidate_groups", {})
    
    # Map final_theme_name -> gabungan 5 keywords teratas
    theme_to_keywords = {}
    for g in groups.values():
        if g.final_theme_name and g.status == "Validated":
            if g.top_keywords:
                theme_to_keywords[g.final_theme_name] = ", ".join(g.top_keywords[:5])
            else:
                theme_to_keywords[g.final_theme_name] = "-"
                
    # Tambahkan kolom Top Keywords ke summary_df berdasarkan Tema
    summary_df["Top Keywords"] = summary_df["Tema"].map(lambda t: theme_to_keywords.get(t, "-"))

    st.session_state["oe_final_mapping"] = final_mapping
    st.session_state["oe_final_theme_summary"] = summary_df
    st.session_state["oe_is_finalized"] = True

    add_audit_entry(
        action="finalize",
        entity_type="analysis",
        entity_id=st.session_state.get("oe_current_run_id", "unknown"),
        old_value="in_progress",
        new_value="finalized",
    )

    return summary_df


# ---------------------------------------------------------------------------
# AUDIT TRAIL
# ---------------------------------------------------------------------------

def add_audit_entry(
    action: str,
    entity_type: str,
    entity_id: str,
    old_value: Any,
    new_value: Any,
    user: str = "analyst",
):
    """Tambahkan satu entri ke audit log."""
    entry = AuditEntry(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        old_value=old_value,
        new_value=new_value,
        user=user,
    )

    if "oe_audit_log" not in st.session_state:
        st.session_state["oe_audit_log"] = []

    st.session_state["oe_audit_log"].append(entry)


def get_audit_log_df() -> pd.DataFrame:
    """Kembalikan audit log sebagai DataFrame."""
    log = st.session_state.get("oe_audit_log", [])
    if not log:
        return pd.DataFrame(columns=["timestamp", "action", "entity_type", "entity_id", "old_value", "new_value", "user"])
    return pd.DataFrame([e.to_dict() for e in log])


# ---------------------------------------------------------------------------
# NARRATIVE GENERATION (Template-based, NO AI)
# ---------------------------------------------------------------------------

def generate_narrative(summary_df: pd.DataFrame, question_col: str = "", mode: str = "thematic") -> str:
    """
    Buat narasi deskriptif dari hasil analisis tema final.
    100% template Python — tidak ada AI/LLM.

    Gunakan bahasa deskriptif (bukan klaim sebab-akibat atau interpretasi subjektif).
    """
    if summary_df is None or summary_df.empty:
        return "Belum ada data yang cukup untuk membuat narasi."

    # Filter Other dari narasi utama
    main_df = summary_df[summary_df["Tema"] != "Other"].reset_index(drop=True)
    other_row = summary_df[summary_df["Tema"] == "Other"]

    if main_df.empty:
        return "Seluruh respons dikategorikan sebagai Other. Tidak ada tema substantif yang dapat dinarasikan."

    total_valid = summary_df["Jumlah"].sum()
    n_themes = len(main_df)

    # Sesuaikan kata kunci berdasar mode
    if mode == "barrier":
        item_label = "hambatan"
        action_label = "menghadapi kendala/hambatan terkait"
    elif mode == "reason":
        item_label = "alasan"
        action_label = "memberikan alasan terkait"
    elif mode == "recommendation":
        item_label = "saran"
        action_label = "memberikan masukan/saran mengenai"
    elif mode == "evaluation":
        item_label = "penilaian"
        action_label = "menyoroti aspek"
    else:
        item_label = "tema"
        action_label = "menyoroti aspek"

    # Baris pertama selalu ada
    t1 = main_df.iloc[0]

    narrative = (
        f"Berdasarkan hasil analisis, "
        f"{item_label} **{t1['Tema']}** menjadi {item_label} dengan frekuensi tertinggi, "
        f"yaitu sebanyak **{t1['Jumlah']} respons** ({t1['Persentase']:.1f}%)"
    )

    if n_themes >= 2:
        t2 = main_df.iloc[1]
        narrative += (
            f", diikuti oleh **{t2['Tema']}** sebanyak **{t2['Jumlah']} respons** "
            f"({t2['Persentase']:.1f}%)"
        )

    if n_themes >= 3:
        t3 = main_df.iloc[2]
        narrative += (
            f", dan **{t3['Tema']}** sebanyak **{t3['Jumlah']} respons** "
            f"({t3['Persentase']:.1f}%)"
        )

    narrative += ". "

    # Kalimat penutup
    top_themes_str = ", ".join(f"**{main_df.iloc[i]['Tema']}**" for i in range(min(3, n_themes)))
    narrative += (
        f"Secara umum, hasil pengelompokan menunjukkan bahwa respons responden "
        f"banyak {action_label} {top_themes_str}."
    )

    # Tambahkan info Other jika ada
    if not other_row.empty:
        other_count = other_row.iloc[0]["Jumlah"]
        narrative += (
            f" Terdapat **{other_count} respons** ({other_row.iloc[0]['Persentase']:.1f}%) "
            f"yang dikategorikan sebagai Other atau tidak dapat dikelompokkan."
        )

    return narrative
