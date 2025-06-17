import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import json

# Load data dan preprocessing (sama seperti kode kamu sebelumnya) ...
# df = ...
# gdf = ...
# dominant = ...
# geojson_data = ...
# kategori_warna = ...

# =========================
# 1. Load Data
# =========================
df = pd.read_csv("permohonan_joss_2021-2024.csv", sep=';', encoding='utf-8', on_bad_lines='skip')
gdf = gpd.read_file("jawa_timur_kabkot.geojson.json")

# =========================
# 2. Normalisasi Wilayah
# =========================
gdf['Kode_Wilayah'] = gdf['kabkot'].str.upper().str.strip()
geojson_ids = set(gdf['Kode_Wilayah'])

df['Kode_Wilayah'] = (
    df['lokasi_pemohon']
    .astype(str)
    .str.upper()
    .str.strip()
    .str.replace(r'^(KAB\.|KOTA)\s+', '', regex=True)
)

df = df[df['Kode_Wilayah'].isin(geojson_ids)]

# =========================
# 3. Hitung Durasi Izin
# =========================
df['tanggal_pengajuan'] = pd.to_datetime(df['tanggal_pengajuan'], dayfirst=True, errors='coerce')
df['tanggal_terbit'] = pd.to_datetime(df['tanggal_terbit'], dayfirst=True, errors='coerce')
df = df.dropna(subset=['tanggal_pengajuan', 'tanggal_terbit'])  # tambahan
df['Durasi'] = (df['tanggal_terbit'] - df['tanggal_pengajuan']).dt.days + 1
df = df[df['Durasi'] >= 0]  # pastikan durasi logis

df['TahunBulan'] = df['tanggal_terbit'].dt.to_period('M').astype(str)
df['Sektor'] = df['nama_sektor']

# =========================
# 4. Filter 5 sektor utama
# =========================
SEKTOR_THRESHOLD = {
    'Peternakan': 6,
    'Pendidikan': 30,
    'Perindustrian dan Perdagangan': 12,
    'Kesehatan': 28,
    'Lingkungan Hidup': 74
}
df = df[df['Sektor'].isin(SEKTOR_THRESHOLD.keys())]

# =========================
# 5. Kategorisasi Durasi
# =========================
def kategori_waktu(sektor, durasi):
    batas = SEKTOR_THRESHOLD.get(sektor)
    if pd.isna(batas) or pd.isna(durasi):
        return "Tidak Diketahui"
    if durasi < batas:
        return "Cepat"
    elif durasi == batas:
        return "Tepat"
    else:
        return "Terlambat"

df['Kategori'] = df.apply(lambda x: kategori_waktu(x['Sektor'], x['Durasi']), axis=1)
df = df[df['Kategori'] != "Tidak Diketahui"]

# =========================
# 6. Ambil kategori dominan
# =========================
agg = df.groupby(['Kode_Wilayah', 'TahunBulan', 'Sektor', 'Kategori']).size().reset_index(name='Jumlah')
dominant = agg.sort_values(['Kode_Wilayah', 'TahunBulan', 'Sektor', 'Jumlah'], ascending=[True, True, True, False])
dominant = dominant.drop_duplicates(subset=['Kode_Wilayah', 'TahunBulan', 'Sektor'])
available_sektors = dominant['Sektor'].unique()


# =========================
# 7. Siapkan GeoJSON
# =========================
gdf['id'] = gdf['Kode_Wilayah']
gdf.to_file("jawa_timur_kabkot_fixed.geojson", driver="GeoJSON")
with open("jawa_timur_kabkot_fixed.geojson") as f:
    geojson_data = json.load(f)

# =========================
# 8. Warna kategori
# =========================
kategori_warna = {
    "Cepat": "green",
    "Tepat": "gold",
    "Terlambat": "red"
}

# Streamlit UI
st.title("Visualisasi Durasi Penyelesaian Izin")

selected_sektor = st.selectbox("Pilih Sektor:", list(SEKTOR_THRESHOLD.keys()))
filtered = dominant[dominant['Sektor'] == selected_sektor]

fig = px.choropleth(
    filtered,
    geojson=geojson_data,
    locations='Kode_Wilayah',
    featureidkey='properties.Kode_Wilayah',
    color='Kategori',
    animation_frame='TahunBulan',
    hover_name='Kode_Wilayah',
    color_discrete_map=kategori_warna,
    title=f"Kategori Waktu Penyelesaian Izin per Kabupaten - Sektor: {selected_sektor}"
)

fig.update_geos(fitbounds="locations", visible=False)
st.plotly_chart(fig, use_container_width=True)
