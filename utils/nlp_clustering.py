import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, pairwise_distances_argmin_min
from sklearn.metrics.pairwise import cosine_similarity
from utils.text_analysis import clean_text, remove_stopwords, tokenize

def preprocess_for_clustering(texts, use_stemming=False, extra_stopwords=None):
    """Clean and preprocess a list of texts for clustering."""
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

def get_tfidf_matrix(processed_texts, use_bigram=False, max_features=1000):
    """Generate TF-IDF matrix and vectorizer from processed texts."""
    ngram_range = (1, 2) if use_bigram else (1, 1)
    vectorizer = TfidfVectorizer(
        ngram_range=ngram_range,
        max_features=max_features,
        min_df=2, # Require at least 2 occurrences
        max_df=0.95 # Ignore terms appearing in >95% of docs
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform(processed_texts)
        return tfidf_matrix, vectorizer
    except ValueError:
        # Happens if vocab is empty (e.g. all stopwords)
        return None, None

def find_optimal_k(tfidf_matrix, min_k=2, max_k=10):
    """Find optimal K using Silhouette Score."""
    n_samples = tfidf_matrix.shape[0]
    if n_samples < min_k:
        return 1, []
        
    actual_max_k = min(max_k, n_samples - 1)
    if actual_max_k < min_k:
        return 1, []

    scores = []
    for k in range(min_k, actual_max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(tfidf_matrix)
        if len(set(labels)) > 1:
            score = silhouette_score(tfidf_matrix, labels)
            scores.append((k, score))
    
    if not scores:
        return 1, []
        
    optimal_k = max(scores, key=lambda x: x[1])[0]
    return optimal_k, scores

def run_kmeans(tfidf_matrix, k, random_state=42):
    """Run K-Means clustering."""
    kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    labels = kmeans.fit_predict(tfidf_matrix)
    return kmeans, labels

def get_top_keywords(kmeans, vectorizer, n_words=10):
    """Get top keywords for each cluster based on TF-IDF centroids."""
    centroids = kmeans.cluster_centers_
    terms = vectorizer.get_feature_names_out()
    
    cluster_keywords = {}
    for i, centroid in enumerate(centroids):
        # Sort terms by TF-IDF weight in descending order
        top_indices = centroid.argsort()[:-n_words-1:-1]
        top_terms = [terms[ind] for ind in top_indices if centroid[ind] > 0]
        cluster_keywords[i] = top_terms
        
    return cluster_keywords

def get_representative_docs(tfidf_matrix, kmeans, original_texts, n_docs=3):
    """Find the most representative responses for each cluster."""
    cluster_reps = {}
    
    # Calculate distance from each point to its cluster center
    for i in range(kmeans.n_clusters):
        cluster_reps[i] = []
        
        # Get indices of points in this cluster
        in_cluster = np.where(kmeans.labels_ == i)[0]
        if len(in_cluster) == 0:
            continue
            
        # Get TF-IDF vectors for points in this cluster
        cluster_points = tfidf_matrix[in_cluster]
        
        # Calculate cosine similarity to the cluster centroid
        centroid = kmeans.cluster_centers_[i].reshape(1, -1)
        similarities = cosine_similarity(cluster_points, centroid).flatten()
        
        # Get indices of top N most similar points
        top_n_idx = similarities.argsort()[:-n_docs-1:-1]
        
        # Map back to original indices
        original_idx = in_cluster[top_n_idx]
        
        for idx in original_idx:
            if isinstance(original_texts[idx], str) and original_texts[idx].strip():
                cluster_reps[i].append(original_texts[idx])
                
        # Deduplicate while preserving order
        seen = set()
        unique_reps = []
        for text in cluster_reps[i]:
            if text not in seen:
                seen.add(text)
                unique_reps.append(text)
        cluster_reps[i] = unique_reps
                
    return cluster_reps
