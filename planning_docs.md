# 1. Project Overview

**Nama Project:**
Survey Insight Dashboard

**Tujuan:**
Membangun aplikasi berbasis **Streamlit** untuk mengolah data survei dari Google Form / CSV / Excel sehingga pengguna dapat:

* upload dataset survei
* melakukan data cleansing
* melakukan analisis berdasarkan tipe pertanyaan
* menghasilkan visualisasi otomatis
* menghasilkan wordcloud untuk pertanyaan terbuka

Aplikasi dijalankan **secara lokal terlebih dahulu**.

---

# 2. System Architecture

Arsitektur sistem sederhana:

```
User
 ↓
Streamlit UI
 ↓
Data Processing Layer
 ↓
Visualization Engine
 ↓
Output (chart / table / wordcloud)
```

Teknologi utama:

```
Frontend + Backend : Streamlit
Data Processing     : Pandas
Visualization       : Plotly / Altair
Wordcloud           : WordCloud
Storage (local)     : SQLite / File
```

---

# 3. Project Folder Structure

Direkomendasikan:

```
survey_dashboard
│
├── app.py
│
├── pages
│   ├── 1_upload_data.py
│   ├── 2_data_cleaning.py
│   ├── 3_analysis.py
│   ├── 4_visualization.py
│   └── 5_wordcloud.py
│
├── utils
│   ├── data_loader.py
│   ├── data_cleaning.py
│   ├── pivot_analysis.py
│   ├── multi_select_analysis.py
│   └── text_analysis.py
│
├── data
│   └── datasets
│
├── database
│   └── db.sqlite
│
└── requirements.txt
```

---

# 4. Core Features

## 4.1 Upload Dataset

User dapat upload:

* CSV
* Excel
* Google Sheet export

Fitur:

```
Upload dataset
Preview dataset
Save dataset
```

Teknologi:

```
pandas.read_csv
pandas.read_excel
```

Output:

```
DataFrame
```

---

# 4.2 Data Preview

Menampilkan dataset dalam tabel interaktif.

Fitur:

```
view dataset
search column
filter row
```

Komponen Streamlit:

```
st.dataframe()
```

---

# 4.3 Data Cleaning Module

User dapat melakukan:

```
edit cell
hapus row
tambah row
rename column
drop column
replace value
```

Library yang disarankan:

```
streamlit-aggrid
```

Contoh operasi:

```
strip whitespace
lowercase normalization
remove null values
```

---

# 4.4 Question Type Configuration

Karena dataset dari Google Form tidak menyimpan tipe pertanyaan, sistem membutuhkan konfigurasi manual.

Contoh struktur konfigurasi:

```
{
 "Fakultas": "single_choice",
 "Angkatan": "single_choice",
 "Minat lomba": "multiple_choice",
 "Ketertarikan program": "scale",
 "Harapan mahasiswa": "open_text"
}
```

Tipe pertanyaan:

```
single_choice
multiple_choice
scale
open_text
```

---

# 5. Analysis Engine

## 5.1 Single Choice Analysis

Digunakan untuk:

```
pilih satu
dropdown
radio
```

Metode:

```
value_counts()
```

Output:

```
frequency table
bar chart
pie chart
```

---

## 5.2 Scale Analysis

Digunakan untuk:

```
Likert scale
rating
1-5 scale
```

Metode:

```
value_counts().sort_index()
```

Output:

```
distribution chart
```

Contoh:

```
1 = sangat setuju
2 = setuju
3 = netral
4 = tidak setuju
```

---

## 5.3 Multiple Choice Analysis

Digunakan untuk pertanyaan:

```
pilih beberapa
checkbox
```

Biasanya data disimpan seperti:

```
PKM, Essay, Debat
PKM, Business Plan
```

Metode:

```
split(',')
explode()
value_counts()
```

Pipeline:

```
column
 ↓
split comma
 ↓
explode row
 ↓
count frequency
```

Output:

```
horizontal bar chart
```

---

## 5.4 Open Text Analysis

Digunakan untuk:

```
jawaban terbuka
opini
harapan
```

Metode analisis:

```
tokenization
stopword removal
word frequency
```

Output:

```
wordcloud
top keywords
```

Library:

```
wordcloud
nltk / re
```

---

# 6. Visualization Engine

Library yang direkomendasikan:

* **Plotly**
* **Altair**

Jenis chart:

```
bar chart
horizontal bar
pie chart
wordcloud
```

---

# 7. Data Storage

Karena sistem dijalankan secara lokal, penyimpanan dapat menggunakan:

### Option 1

Folder dataset

```
/data/datasets/
```

### Option 2

SQLite database

```
dataset metadata
```

Table example:

```
datasets
-------
id
name
filename
created_at
```

---

# 8. Data Processing Pipeline

Pipeline analisis:

```
Upload dataset
     ↓
Preview dataset
     ↓
Cleaning data
     ↓
Define question type
     ↓
Analysis engine
     ↓
Visualization
```

---

# 9. Performance Considerations

Dataset survei biasanya:

```
100 - 2000 rows
20 - 100 columns
```

Pandas cukup untuk ukuran ini.

Optimization:

```
cache dataset
use st.cache_data
```

---

# 10. Security (Local Version)

Untuk versi lokal:

```
no authentication
single user
local dataset only
```

Versi future:

```
login system
multi user
dataset ownership
```

---

# 11. Future Features

Pengembangan berikutnya:

```
automatic question detection
AI summarization for open text
report generator
dashboard export
public share link
```

---

# 12. Development Roadmap

Tahapan pengembangan:

### Phase 1 (MVP)

```
upload dataset
preview dataset
single choice analysis
scale analysis
```

---

### Phase 2

```
multiple choice analysis
visualization
export chart
```

---

### Phase 3

```
text analysis
wordcloud
summary generation
```

---

# 13. Example Workflow

User workflow:

```
1 upload csv
2 preview dataset
3 select column
4 choose question type
5 generate analysis
6 export chart
```

---

# 14. requirements.txt

```
streamlit
pandas
plotly
wordcloud
streamlit-aggrid
openpyxl
nltk
```