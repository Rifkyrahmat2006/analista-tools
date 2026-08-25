"""
Colorscale Hover Preview
==========================
Fitur: saat dropdown "Color Scale" di tab Tugas Saya dibuka, hover di
salah satu opsi langsung mengubah warna chart secara instan (client-side,
tanpa rerun server) — baru permanen kalau opsi itu benar-benar diklik
(yang tetap memicu rerun Streamlit normal seperti biasa).

CARA KERJA (perlu dipahami sebelum diubah, karena agak tidak biasa):
- Dropdown "Color Scale" adalah widget native Streamlit (st.selectbox),
  BUKAN komponen custom — jadi tidak bisa ditambahkan listener langsung
  dari Python. Untuk "menembus" ke situ, kita render komponen HTML kecil
  (lewat st.components.v1.html, height=0, tidak terlihat) yang jalan di
  dalam iframe sendiri, lalu dari JS di iframe itu kita akses
  `window.parent.document` (bisa karena iframe Streamlit componen selalu
  punya sandbox `allow-same-origin`) untuk mencari & memasang listener
  `mouseenter` ke tiap opsi dropdown di halaman utama.
- Target dropdown yang benar diidentifikasi dengan mencocokkan teks opsi
  terhadap daftar nama color scale yang kita tahu (bukan lewat ID/key
  Streamlit yang tidak stabil/tidak accessible dari luar).
- Chart target diidentifikasi sebagai elemen `.js-plotly-plot` TERAKHIR
  di halaman (asumsi: hanya ada 1 chart aktif yang sedang dikonfigurasi
  di tab Tugas Saya pada satu waktu — asumsi ini valid untuk halaman ini,
  JANGAN dipakai di halaman yang render banyak chart sekaligus tanpa
  penyesuaian).
- Update warna dilakukan lewat `Plotly.restyle()` (built-in Plotly.js
  yang sudah otomatis ter-load oleh st.plotly_chart), BUKAN
  re-render ulang figure — makanya instan tanpa nunggu server.
- Kalau user hover lalu batal (mouse keluar dropdown tanpa klik), warna
  dikembalikan ke color scale yang sedang aktif (current_colors).

RAPUH TERHADAP: perubahan struktur DOM internal Streamlit (BaseWeb
Select) di versi Streamlit yang akan datang. Kalau suatu saat hover
preview berhenti berfungsi setelah upgrade Streamlit, cek dulu apakah
selector `[role="listbox"]` / `[role="option"]` masih dipakai BaseWeb.
"""

import json

import streamlit as st
import plotly.colors as pc

from utils.export_helpers import normalize_color


def get_all_scale_preview_colors(n_cats: int, plotly_scale_map: dict) -> dict:
    """
    Precompute warna hex utk SEMUA color scale, utk n_cats kategori.
    Dipanggil sekali per render (n_cats sudah diketahui dari data),
    hasilnya dikirim ke JS sebagai lookup table supaya hover tidak perlu
    hitung ulang / panggil balik ke server.
    """
    out = {}
    for display_name, plotly_name in plotly_scale_map.items():
        try:
            if n_cats < 2:
                colors = [pc.sample_colorscale(plotly_name, [0.6])[0]]
            else:
                colors = pc.sample_colorscale(plotly_name, [i / (n_cats - 1) for i in range(n_cats)])
            out[display_name] = [normalize_color(c) for c in colors]
        except Exception:
            continue
    return out


def render_colorscale_hover_preview(scale_colors: dict, chart_type: str, current_colors: list, key: str):
    """
    Render komponen tak-terlihat yang memasang hover-preview listener ke
    dropdown Color Scale terdekat. Panggil TEPAT SETELAH st.plotly_chart()
    dirender, supaya chart div sudah ada di DOM saat JS mulai polling.
    """
    if chart_type not in ("Bar Chart", "Horizontal Bar", "Pie Chart", "Donut Chart"):
        # Treemap/Area/Line pakai continuous colorscale atau tidak
        # per-kategori — hover-preview di-skip (aman, dropdown tetap
        # berfungsi normal via klik seperti biasa, cuma tanpa efek hover).
        return

    scale_colors_json = json.dumps(scale_colors)
    current_colors_json = json.dumps([normalize_color(c) for c in (current_colors or [])])
    is_pie = chart_type in ("Pie Chart", "Donut Chart")
    safe_key = key.replace(" ", "_").lower()

    html_code = f"""
    <script>
    (function() {{
        const scaleColors = {scale_colors_json};
        const currentColors = {current_colors_json};
        const isPie = {str(is_pie).lower()};
        const scaleNames = Object.keys(scaleColors).sort((a, b) => b.length - a.length);

        function getTargetChart() {{
            try {{
                const plots = window.parent.document.querySelectorAll('.js-plotly-plot');
                return plots.length ? plots[plots.length - 1] : null;
            }} catch (e) {{ return null; }}
        }}

        function applyColors(colors) {{
            const div = getTargetChart();
            if (!div || !window.parent.Plotly) return;
            try {{
                if (isPie) {{
                    window.parent.Plotly.restyle(div, {{'marker.colors': [colors]}}, [0]);
                }} else {{
                    const n = (div.data || []).length;
                    if (n === 0) return;
                    const traceIdx = Array.from({{length: n}}, (_, i) => i);
                    const vals = traceIdx.map((_, i) => colors[i % colors.length]);
                    window.parent.Plotly.restyle(div, {{'marker.color': vals}}, traceIdx);
                }}
            }} catch (e) {{ /* diam-diam gagal — jangan ganggu UI kalau restyle error */ }}
        }}

        function findScaleName(text) {{
            for (const name of scaleNames) {{
                if (text.includes(name)) return name;
            }}
            return null;
        }}

        const bound = new WeakSet();

        function tryBind() {{
            let doc;
            try {{ doc = window.parent.document; }} catch (e) {{ return; }}
            const listbox = doc.querySelector('[role="listbox"]');
            if (!listbox) return;
            const options = Array.from(listbox.querySelectorAll('[role="option"]'));
            if (!options.length) return;
            // Pastikan ini listbox Color Scale (bukan dropdown lain yg kebetulan lagi terbuka)
            const sampleText = options.slice(0, 3).map(o => o.innerText).join(' ');
            if (!scaleNames.some(name => sampleText.includes(name))) return;

            options.forEach(opt => {{
                if (bound.has(opt)) return;
                bound.add(opt);
                opt.addEventListener('mouseenter', () => {{
                    const name = findScaleName(opt.innerText);
                    if (name && scaleColors[name]) applyColors(scaleColors[name]);
                }});
            }});
            listbox.addEventListener('mouseleave', () => applyColors(currentColors), {{once: false}});
        }}

        // Polling ringan (bukan MutationObserver global) — dropdown baru
        // muncul di DOM setelah user klik utk membuka, jadi kita cek
        // berkala. Interval singkat supaya listener terpasang cepat
        // setelah dropdown dibuka, tapi tidak terlalu berat untuk CPU.
        setInterval(tryBind, 250);
    }})();
    </script>
    """
    st.components.v1.html(html_code, height=0)
