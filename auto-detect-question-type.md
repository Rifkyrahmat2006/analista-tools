You are a senior Python engineer improving an existing Streamlit survey analytics application.

The repository already contains the following architecture:

* app.py
* pages/
  1_upload_data.py
  2_data_cleaning.py
  3_analysis.py
  4_visualization.py
  5_wordcloud.py
* utils/
  data_loader.py
  data_cleaning.py
  pivot_analysis.py
  multi_select_analysis.py
  text_analysis.py
  export_helpers.py

The application allows users to configure question types manually for survey columns:

* single_choice
* multiple_choice
* scale
* open_text
* skip

Currently, there is NO automatic detection of question types.

Your task is to implement an **advanced intelligent question type detection algorithm**.

The detection should be much more robust than simple comma detection.

Do NOT break existing architecture.

---

FEATURE GOAL

Automatically analyze dataset columns and **suggest the most likely question type**.

The algorithm should return:

* single_choice
* multiple_choice
* scale
* open_text
* skip

Users must still be able to manually override the suggestion.

---

IMPLEMENTATION

Create new module:

utils/question_detection.py

Main function:

detect_question_type(series: pd.Series) -> str

---

DETECTION PIPELINE

The detection algorithm must analyze several statistical features of the column.

Compute these metrics:

1. total_values
2. null_ratio
3. unique_count
4. unique_ratio
5. comma_ratio
6. delimiter_ratio
7. avg_text_length
8. numeric_ratio

---

STEP 1 — SKIP DETECTION

If the column is mostly empty:

null_ratio > 0.8

Return:

skip

---

STEP 2 — SCALE DETECTION

Convert column to numeric.

numeric_ratio = count_numeric / total_values

If:

numeric_ratio > 0.8
AND unique_count <= 10
AND value_range <= 20

Return:

scale

Examples:

1 2 3 4 5
1–4 Likert scale

---

STEP 3 — MULTIPLE CHOICE DETECTION

Multiple choice responses usually contain repeated delimiters.

Detect these delimiters:

","
";"
"|"
"/"

delimiter_ratio = percentage of values containing any delimiter.

Also compute:

avg_items_per_response

Example:

"PKM, Essay"
"Debate, Essay"

Rules:

delimiter_ratio > 0.25
AND avg_items_per_response >= 1.5

Return:

multiple_choice

---

STEP 4 — OPEN TEXT DETECTION

Open text responses usually have longer text.

Calculate:

avg_text_length
avg_word_count

Rules:

avg_text_length > 40
OR avg_word_count > 8

Return:

open_text

---

STEP 5 — SINGLE CHOICE DETECTION

If none of the above conditions match:

Check:

unique_count <= 30
AND avg_text_length < 40

Return:

single_choice

Examples:

Faculty
Program Study
City

---

EDGE CASE HANDLING

Avoid false detection of multiple_choice when comma is used inside a single label.

Example:

"Teknik Informatika, S1"

Solution:

Check average number of delimiters per response.

Example rule:

if delimiter_ratio > 0.25
AND average_delimiter_count > 1

---

RETURN FORMAT

Return string representing type:

single_choice
multiple_choice
scale
open_text
skip

---

EXTRA FEATURE

Also implement helper function:

analyze_column_features(series)

Return dictionary:

{
"null_ratio": float,
"unique_ratio": float,
"delimiter_ratio": float,
"numeric_ratio": float,
"avg_text_length": float,
"avg_word_count": float
}

---

INTEGRATION

Modify `pages/3_analysis.py`.

When rendering question type selectboxes:

1. run detect_question_type(df[col])
2. use result as the **default selection**

Display suggestion text:

Suggested: multiple_choice

---

UX IMPROVEMENT

Add tooltip showing column statistics:

Example:

Unique values: 12
Delimiter ratio: 0.42
Avg text length: 12

---

CODE QUALITY

Requirements:

* use type hints
* modular functions
* docstrings
* follow existing utils structure

---

OUTPUT

Return:

1. full implementation of:

utils/question_detection.py

2. modified section of:

pages/3_analysis.py

---
