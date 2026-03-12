"""
Text Analysis Utility
Handles open text analysis including tokenization, stopword removal,
word frequency, and wordcloud generation.
"""

import re
from collections import Counter

import pandas as pd

try:
    from wordcloud import WordCloud
except ImportError:
    WordCloud = None

# Indonesian stopwords (common words to filter out)
INDONESIAN_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "adalah",
    "ini", "itu", "atau", "juga", "tidak", "akan", "sudah", "ada", "bisa",
    "lebih", "saya", "kami", "kita", "mereka", "anda", "dia", "ia", "nya",
    "se", "ter", "ber", "me", "men", "mem", "meng", "per", "pem", "pen",
    "hal", "oleh", "karena", "seperti", "saat", "bagi", "antara", "lain",
    "dapat", "harus", "menjadi", "telah", "secara", "dalam", "agar",
    "supaya", "maupun", "serta", "namun", "tetapi", "bahwa", "sebagai",
    "belum", "masih", "sangat", "begitu", "hingga", "sampai", "lagi",
    "sering", "selalu", "banyak", "semua", "setiap", "seluruh",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "about", "it", "its",
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his",
    "she", "her", "they", "them", "their", "this", "that", "these", "those",
}


def clean_text(text: str) -> str:
    """Clean a single text string."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> list:
    """Tokenize text into words."""
    return text.split()


def remove_stopwords(words: list, extra_stopwords: set = None) -> list:
    """Remove stopwords from a list of words."""
    stopwords = INDONESIAN_STOPWORDS.copy()
    if extra_stopwords:
        stopwords.update(extra_stopwords)
    return [w for w in words if w not in stopwords and len(w) > 1]


def analyze_text_column(df: pd.DataFrame, column: str, extra_stopwords: set = None) -> dict:
    """
    Full text analysis pipeline for an open text column.
    Returns word frequencies and total stats.
    """
    texts = df[column].dropna().astype(str).tolist()

    all_words = []
    for text in texts:
        cleaned = clean_text(text)
        words = tokenize(cleaned)
        words = remove_stopwords(words, extra_stopwords)
        all_words.extend(words)

    word_freq = Counter(all_words)

    return {
        "word_freq": word_freq,
        "total_words": len(all_words),
        "unique_words": len(word_freq),
        "total_responses": len(texts),
    }


def get_top_keywords(word_freq: Counter, top_n: int = 20) -> pd.DataFrame:
    """Get top N keywords as a DataFrame."""
    top = word_freq.most_common(top_n)
    return pd.DataFrame(top, columns=["Keyword", "Frequency"])


def generate_wordcloud(word_freq: Counter, width: int = 800, height: int = 400,
                       background_color: str = "#0e1117", colormap: str = "Set2",
                       max_words: int = 100) -> "WordCloud":
    """Generate a WordCloud image from word frequencies."""
    if WordCloud is None:
        raise ImportError("wordcloud library is not installed. Run: pip install wordcloud")

    if not word_freq:
        return None

    wc = WordCloud(
        width=width,
        height=height,
        background_color=background_color,
        colormap=colormap,
        max_words=max_words,
        prefer_horizontal=0.7,
        min_font_size=10,
        max_font_size=120,
    ).generate_from_frequencies(dict(word_freq))

    return wc
