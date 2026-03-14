# New Analysis Page Design

## Overview

This document defines the new design and behavior of the **Analysis page** for the survey processing application built with Streamlit.

The goal is to redesign the page to improve usability and match the mental model of users familiar with Google Forms.

The page should present questions in a **single vertical layout**, similar to the Google Forms admin interface.

Each question is displayed as a block containing:

* question text
* question type selector
* optional answer option preview
* column statistics (optional)

This replaces the previous **grid card layout**.

---

# Page Layout

The layout must be **vertical, single column**, ordered by the dataset column order.

Structure:

Question Block
↓
Question Block
↓
Question Block

Each block represents one column in the dataset.

---

# Question Block Structure

Each question block contains:

1. Question Text
2. Question Type Dropdown
3. Suggested Type Label
4. Optional Option Preview (for multiple choice)
5. Optional Column Statistics

Example UI layout:

Question text

[ Question Type Dropdown ]

Suggested: multiple_choice

Options (if multiple choice):

• PKM (120)
• Essay (95)
• Debate (60)
• Other (7)

---

# Question Type Selector

Each question must have a dropdown selector.

Possible types:

* single_choice
* multiple_choice
* scale
* open_text
* skip

The default selected value should come from the **automatic detection algorithm**.

Users must still be able to override the suggestion manually.

---

# Layout Alignment

The question block must use a **two-column layout**:

Left column:

Question text

Right column:

Question type dropdown

Example structure:

| Question Text | Dropdown |

---

# Option Preview (Multiple Choice)

If the selected type is **multiple_choice**, the application must automatically extract answer options from the dataset.

Steps:

1. Split responses by delimiter
2. Explode into individual answers
3. Normalize text
4. Count frequency

Example:

Input responses:

PKM, Essay
PKM
Essay, Debate

Exploded values:

PKM
Essay
Debate

Frequency table:

PKM → 120
Essay → 95
Debate → 60

---

# Automatic Option Detection

The application must detect the **main options** and separate **rare responses** as "Other".

Algorithm:

1. Count frequency of each option
2. Determine threshold:

threshold = max(3, total_responses * 0.02)

3. Options below threshold are classified as OTHER.

Example:

PKM → 120
Essay → 95
Debate → 60
Hackathon → 3
UI UX Competition → 2

Result:

Main options:

PKM
Essay
Debate

Other responses:

Hackathon
UI UX Competition

---

# Display Rules

Main options should appear as:

• PKM (120)
• Essay (95)
• Debate (60)
• Other (5)

Other responses should be displayed below:

Other responses:

* Hackathon
* UI UX Competition

---

# Handling "Other" Responses

If a response does not match any main option, it should be grouped into **Other**.

These responses should be stored separately for text analysis.

Other responses can later be used for:

* wordcloud
* keyword extraction

---

# Column Statistics Section

Each question block may contain a collapsible section called:

Column Stats

Displayed information:

* total responses
* unique values
* null ratio
* detected type metrics

Example:

Unique values: 5
Null ratio: 0.02
Delimiter ratio: 0.34

---

# Behavior Rules

Open Text

Only display the dropdown.

No option preview.

---

Single Choice

Option preview may be displayed but without delimiter splitting.

---

Multiple Choice

Must display automatically detected options.

---

Scale

Display value distribution preview.

Example:

1 → 40
2 → 70
3 → 100
4 → 44

---

# Performance Requirements

If dataset rows > 5000:

Option detection must be cached using:

st.cache_data

---

# Code Organization

The logic should reuse existing modules when possible.

Relevant modules:

utils/multi_select_analysis.py
utils/question_detection.py

New helper functions may be added if necessary.

---

# Expected Result

The analysis page should behave like a **survey configuration panel** similar to Google Forms.

Users should easily review each question and configure the correct analysis type.

The interface should prioritize readability and clarity over density.

---

# Future Extensions

Possible improvements:

* editable option list
* merging similar options
* fuzzy matching for typo detection
* automatic chart recommendation

These features are not required in this implementation.
