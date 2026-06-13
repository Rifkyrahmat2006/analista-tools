
# 📝 PRODUCT REQUIREMENT DOCUMENT (PRD)

## Fitur: Integrated Dropdown Search Component

## 1. Ringkasan Fitur (Feature Overview)

Menambahkan kolom pencarian teks langsung (*inline search box*) secara *real-time* tepat di bagian atas panel menu pilihan (*dropdown*) ketika komponen bertipe seleksi diklik atau dalam keadaan aktif. Fitur ini dirancang khusus untuk mempermudah navigasi pada kolom data survei kuesioner yang memiliki teks opsi sangat panjang atau jumlah pilihan yang banyak, sehingga pengguna tidak perlu menggulir daftar secara manual.

## 2. Tujuan & Lingkup (Goals & Scope)

* **Tujuan:** Meningkatkan efisiensi pengalaman pengguna (UX) dalam memilih opsi survei yang panjang (seperti pertanyaan kuesioner atau nama kolom) dengan menyediakan filter pencarian instan yang terintegrasi di dalam menu dropdown.
* **Lingkup:** Perubahan ini difokuskan penuh pada aspek **interaksi komponen (*behavior*)** dan **penyusunan tata letak internal elemen dropdown**. Komponen ini **wajib mempertahankan tema warna bawaan yang sudah ada** (Streamlit Dark/Navy Blue Theme) dan dilarang mengubah tata letak halaman global (*layout vertical block*).

---

## 3. Spesifikasi Fungsional & Perilaku (Functional Specs & Behavior)

### A. Kondisi Normal (Default/Inactive State)

* Komponen seleksi menampilkan teks opsi yang sedang terpilih saat ini.
* Di sisi kanan kolom input utama, terdapat ikon indikator panah bawah (`v`) minimalis.

### B. Kondisi Aktif (Active/Open State)

Ketika pengguna mengklik atau memberikan fokus pada kolom input utama:

1. **Membuka Panel Menu:** Panel menu melayang (*floating dropdown panel*) muncul tepat di bawah kotak input utama dengan warna latar belakang senada yang sedikit lebih terang atau berbayang halus (*box-shadow*).
2. **Peletakan Kolom Pencarian (*Inline Search Box*):** * Sebuah baris input teks khusus disisipkan **pada baris paling atas di dalam panel dropdown**.
* Kolom pencarian ini memiliki teks petunjuk (*placeholder*) bertuliskan `"Ketik untuk mencari..."`.


3. **Penyaringan Real-Time (*Filtering Behavior*):**
* Ketika pengguna mulai mengetikkan karakter pada kolom pencarian tersebut, daftar opsi yang berada di bawahnya harus langsung tersaring secara dinamis berdasarkan kecocokan string (*case-insensitive*).
* Opsi yang tidak memenuhi kriteria pencarian akan disembunyikan secara otomatis.


4. **Navigasi Konten Luas (*List & Scroll Behavior*):**
* Daftar opsi yang telah tersaring tetap disusun secara vertikal tepat di bawah kolom pencarian.
* Jika daftar opsi melebihi batas tinggi maksimal panel (*max-height*), sebuah *scrollbar* vertikal tipis dan minimalis harus muncul di sisi kanan panel. Teks opsi yang panjang harus dapat terbungkus (*text-wrapping*) dengan rapi agar tidak terpotong ke samping.


5. **Efek Interaksi (*Hover State*):** Setiap opsi yang disorot oleh kursor mouse akan berubah warna latar belakangnya secara halus menjadi warna biru keunguan redup khas Streamlit sebelum dieksekusi klik.

---

## 4. Panduan Desain & Kontras UI (UI Style Guide Consistency)

Untuk menjaga konsistensi mutlak dengan project dashboard yang sedang berjalan, komponen pencarian baru ini harus mematuhi aturan warna berikut:

| Elemen Dropdown | Aturan Warna & Style |
| --- | --- |
| **Latar Belakang Panel** | Mengikuti warna dasar gelap/navy pekat bawaan aplikasi (`var(--secondary-background-color)`). |
| **Kolom Pencarian Baru** | Menggunakan warna input teks yang samar dengan teks *placeholder* abu-abu halus agar tidak merusak hierarki visual utama. |
| **Garis Tepi Aktif (Border)** | Mempertahankan aksen garis tepi tipis berwarna biru muda/cyan lembut saat dalam fokus aktif. |
| **Teks Opsi & Hover** | Teks opsi berwarna putih kontras. Latar belakang opsi saat *hover* menggunakan warna biru keunguan redup Streamlit. |

---

## 5. Rencana Implementasi Teknis (Technical Implementation Plan)

Karena aplikasi ini dibangun menggunakan framework Streamlit, implementasi fitur pencarian di dalam dropdown ini dapat dicapai melalui dua pendekatan utama:

### Opsi 1: Pemanfaatan Library Widget Asli

Memanfaatkan komponen pencarian bawaan yang sudah terintegrasi atau menggunakan alternatif widget dari ekosistem Streamlit seperti `st.selectbox` versi terbaru (yang secara otomatis mengaktifkan fitur ketik-cari jika opsi berupa list teks) atau menggunakan pustaka komponen pihak ketiga seperti `streamlit-searchbox` jika dibutuhkan kontrol kustomisasi tingkat lanjut tanpa mengubah struktur layout.

### Opsi 2: Injeksi Gaya CSS (Style Overrides)

Untuk memastikan daftar opsi teks kuesioner yang panjang di bawah kolom pencarian tidak terpotong horizontal saat panel dropdown membatasi ruang, kode injeksi CSS berikut pada berkas tema atau via `st.markdown` wajib dipertahankan untuk mengontrol perilaku pembungkusan teks (*text-wrap*):

```css
/* Menjamin teks opsi panjang melipat ke bawah di dalam dropdown bertema gelap */
div[data-baseweb="select"] li {
    white-space: normal !important;
    word-break: break-word !important;
    line-height: 1.4 !important;
}

```

---

## 6. Kriteria Penerimaan (Acceptance Criteria)

* [ ] Komponen dropdown pada setiap halaman (terutama halaman analisis data) memiliki kolom input pencarian langsung di bagian atas daftar menu pilihan ketika dibuka.
* [ ] Hasil penyaringan daftar pilihan berfungsi secara instan seiring pengguna mengetik di kolom pencarian.
* [ ] Skema warna, tema gelap (*dark mode*), dan desain *block layout vertical* pada aplikasi tidak mengalami perubahan atau kerusakan visual sedikit pun.
* [ ] Teks pilihan kuesioner yang sangat panjang turun ke bawah (*wrap*) dengan rapi dan dapat digulir menggunakan *scrollbar* vertikal yang responsif.