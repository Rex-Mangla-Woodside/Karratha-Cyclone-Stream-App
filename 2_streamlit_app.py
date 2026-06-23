# import streamlit as st
# import folium
# import pandas as pd
# from math import radians, sin, cos, sqrt, atan2
# from streamlit_folium import st_folium

# def haversine(lat1, lon1, lat2, lon2):
#     Ear_Rad = 6371

#     dLat = radians(lat2 - lat1)
#     dLon = radians(lon2 - lon1)

#     lat1 = radians(lat1)
#     lat2 = radians(lat2)

#     a = sin(dLat/2)**2 + cos(lat1) * cos(lat2) * sin(dLon/2)**2
#     return Ear_Rad * 2 * atan2(sqrt(a), sqrt(1 - a))


# pin_lat = -20.591733
# pin_lon = 116.777616

# df = pd.read_csv(r"C:\Users\WA10VM\OneDrive - Woodside Energy Ltd\Desktop\IDCKMSTM0S.csv", header=4)

# df["Distance_km"] = df.apply(
#     lambda row: haversine(pin_lat, pin_lon, row["LAT"], row["LON"]), axis=1
# )

# radius_km = 500  # adjust this value as needed

# within_radius = df[df["Distance_km"] < radius_km]

# # 1) Unique cyclones
# unique_cyclones = within_radius["DISTURBANCE_ID"].unique()
# print("Unique cyclones:", unique_cyclones)
# print("Cyclone count:", len(unique_cyclones))

# # 2) Unique days
# within_radius["DATE_ONLY"] = pd.to_datetime(within_radius["TM"], format="%d/%m/%Y %H:%M").dt.date
# unique_days = within_radius["DATE_ONLY"].unique()
# print("Unique days:", unique_days)
# print("Day count:", len(unique_days))

# def count_passes(df, pin_lat, pin_lon, radius_km):
#     within_radius = df[df["Distance_km"] < radius_km]

#     unique_cyclones = within_radius["DISTURBANCE_ID"].unique()
    
#     within_radius = within_radius.copy()
#     within_radius["DATE_ONLY"] = pd.to_datetime(within_radius["TM"], format="%d/%m/%Y %H:%M").dt.date
#     unique_days = within_radius["DATE_ONLY"].unique()

#     return {
#         "cyclone_count": len(unique_cyclones),
#         "cyclones": unique_cyclones,
#         "day_count": len(unique_days),
#         "days": unique_days
#     }

# # try a few different radius values
# for r in [100, 250, 500, 1000]:
#     result = count_passes(df, pin_lat, pin_lon, r)
#     print(f"Radius {r} km -> Cyclones: {result['cyclone_count']}, Days: {result['day_count']}")
import streamlit as st
import folium
import pandas as pd
import numpy as np
from streamlit_folium import st_folium


def haversine_vectorized(lat1, lon1, lat2, lon2):
    Ear_Rad = 6371
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dLat = np.radians(lat2 - lat1)
    dLon = np.radians(lon2 - lon1)
    a = np.sin(dLat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dLon / 2) ** 2
    return Ear_Rad * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


st.set_page_config(layout="wide")
st.title("Cyclone Pass Counter")

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(r"C:\Users\WA10VM\OneDrive - Woodside Energy Ltd\Desktop\IDCKMSTM0S.csv", header=4)

df["MAX_WIND_SPD"] = pd.to_numeric(df["MAX_WIND_SPD"], errors="coerce")
df["MAX_WIND_GUST"] = pd.to_numeric(df["MAX_WIND_GUST"], errors="coerce")

# ----------------------------
# Pin + radius controls (comes first now)
# ----------------------------
st.subheader("Pin coordinates")
c1, c2, c3 = st.columns(3)
pin_lat = c1.number_input("Pin latitude", value=-20.591733, format="%.6f")
pin_lon = c2.number_input("Pin longitude", value=116.777616, format="%.6f")
radius_km = c3.slider("Radius (km)", min_value=50, max_value=2000, value=500, step=50)

# Distance for every row (vectorized)
df["Distance_km"] = haversine_vectorized(pin_lat, pin_lon, df["LAT"], df["LON"])

# Pre-cleanup: drop cyclones whose closest point is still beyond 2000km (calculation-only, doesn't touch source file)
closest_per_id = df.groupby("DISTURBANCE_ID")["Distance_km"].min()
ids_to_keep = closest_per_id[closest_per_id <= 2000].index
df_full = df[df["DISTURBANCE_ID"].isin(ids_to_keep)].copy()  # keep full tracks for trajectory view later

# Apply the radius cut now — everything downstream is built from this
df = df_full[df_full["Distance_km"] < radius_km].copy()

st.caption(f"{df['DISTURBANCE_ID'].nunique()} cyclones have at least one point within {radius_km}km of the pin.")

# ----------------------------
# Filters — built only from radius-filtered data
# ----------------------------
st.subheader("Filters")
f1, f2, f3 = st.columns(3)

name_options = sorted(df["NAME"].dropna().unique().tolist())
selected_names = f1.multiselect("Name", name_options)

id_options = sorted(df["DISTURBANCE_ID"].dropna().unique().tolist())
selected_ids = f2.multiselect("Disturbance ID", id_options)

type_options = sorted(df["TYPE"].dropna().unique().tolist())
selected_types = f3.multiselect("Type", type_options)

f4, f5 = st.columns(2)
wind_min, wind_max = float(df["MAX_WIND_SPD"].min(skipna=True)), float(df["MAX_WIND_SPD"].max(skipna=True))
wind_range = f4.slider("Max Wind Speed", min_value=wind_min, max_value=wind_max, value=(wind_min, wind_max))

gust_min, gust_max = float(df["MAX_WIND_GUST"].min(skipna=True)), float(df["MAX_WIND_GUST"].max(skipna=True))
gust_range = f5.slider("Max Wind Gust", min_value=gust_min, max_value=gust_max, value=(gust_min, gust_max))

df["TM_parsed"] = pd.to_datetime(df["TM"], format="%d/%m/%Y %H:%M")
tm_min, tm_max = df["TM_parsed"].min().date(), df["TM_parsed"].max().date()
date_range = st.slider("Date range", min_value=tm_min, max_value=tm_max, value=(tm_min, tm_max))

# Apply remaining filters on top of the radius-filtered df
filtered_df = df.copy()
if selected_names:
    filtered_df = filtered_df[filtered_df["NAME"].isin(selected_names)]
if selected_ids:
    filtered_df = filtered_df[filtered_df["DISTURBANCE_ID"].isin(selected_ids)]
if selected_types:
    filtered_df = filtered_df[filtered_df["TYPE"].isin(selected_types)]

filtered_df = filtered_df[
    (filtered_df["MAX_WIND_SPD"] >= wind_range[0]) & (filtered_df["MAX_WIND_SPD"] <= wind_range[1]) &
    (filtered_df["MAX_WIND_GUST"] >= gust_range[0]) & (filtered_df["MAX_WIND_GUST"] <= gust_range[1]) &
    (filtered_df["TM_parsed"].dt.date >= date_range[0]) & (filtered_df["TM_parsed"].dt.date <= date_range[1])
]

within_radius = filtered_df.copy()
within_radius["DATE_ONLY"] = within_radius["TM_parsed"].dt.date

unique_cyclones = within_radius["DISTURBANCE_ID"].unique()
unique_days = within_radius["DATE_ONLY"].unique()

col1, col2 = st.columns(2)
col1.metric("Unique cyclones", len(unique_cyclones))
col2.metric("Unique exposure days", len(unique_days))

# ----------------------------
# Trajectory selection
# ----------------------------
st.subheader("Trajectory view")
selected_cyclones = st.multiselect(
    "Select cyclone(s) to view full trajectory (leave blank or choose '-- Show all --' to see all passes)",
    options=["-- Show all --"] + sorted(unique_cyclones.tolist()),
    default=["-- Show all --"]
)
# ----------------------------
# Map
# ----------------------------
m = folium.Map(location=[pin_lat, pin_lon], zoom_start=5)

folium.Marker(
    location=[pin_lat, pin_lon],
    tooltip="Pin",
    icon=folium.Icon(color="red", icon="star")
).add_to(m)

folium.Circle(
    location=[pin_lat, pin_lon],
    radius=radius_km * 1000,
    color="red",
    fill=True,
    fill_opacity=0.1
).add_to(m)

if (not selected_cyclones) or ("-- Show all --" in selected_cyclones):
    for _, row in within_radius.iterrows():
        folium.CircleMarker(
            location=[row["LAT"], row["LON"]],
            radius=4,
            color="blue",
            fill=True,
            fill_opacity=0.7,
            tooltip=f"{row['DISTURBANCE_ID']} ({row['NAME']}) | {row['Distance_km']:.1f} km",
            popup=row["DISTURBANCE_ID"]
        ).add_to(m)
else:
    # optional: rotate a few colors for clarity
    colors = [
        "#1f78b4", "#33a02c", "#e31a1c", "#ff7f00", "#6a3d9a", "#b15928",
        "#a6cee3", "#b2df8a", "#fb9a99", "#fdbf6f", "#cab2d6", "#ffff99",
        "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462",
        "#b3de69", "#fccde5", "#4daf4a", "#377eb8", "#e41a1c", "#984ea3"
    ]
    # break track if gap > 24h (adjust if needed)
    time_gap = pd.Timedelta(hours=24)

    for i, cycl in enumerate(selected_cyclones):
        # match IDs robustly as strings
        track = df_full[df_full["DISTURBANCE_ID"].astype(str) == str(cycl)].copy()
        if track.empty:
            continue

        # drop missing coordinates and ensure times are parsed & sorted
        track = track.dropna(subset=["LAT", "LON"])
        track["TM_parsed"] = pd.to_datetime(track["TM"], format="%d/%m/%Y %H:%M", errors="coerce")
        track = track.sort_values("TM_parsed").reset_index(drop=True)
        if track.shape[0] < 2:
            continue

        # split into contiguous segments when there's a large time gap
        gap_idx = (track["TM_parsed"].diff() > time_gap).cumsum().fillna(0).astype(int)
        for seg_id, seg in track.groupby(gap_idx):
            coords = seg[["LAT", "LON"]].values.tolist()
            if len(coords) < 2:
                continue
            color = colors[i % len(colors)]
            folium.PolyLine(coords, color=color, weight=3, opacity=0.8).add_to(m)
            for _, row in seg.iterrows():
                folium.CircleMarker(
                    location=[row["LAT"], row["LON"]],
                    radius=5,
                    color=color,
                    fill=True,
                    fill_opacity=0.8,
                    tooltip=f"{row['DISTURBANCE_ID']} ({row.get('NAME','')}) | {row.get('TM','')} | {row.get('Distance_km', np.nan):.1f} km"
                ).add_to(m)

map_data = st_folium(m, width=4000, height=2000)

if map_data and map_data.get("last_object_clicked_popup"):
    clicked_id = map_data["last_object_clicked_popup"]
    if clicked_id in unique_cyclones:
        st.info(f"You clicked on {clicked_id}. Select it from the dropdown above to lock in the trajectory view.")

# ----------------------------
# Table
# ----------------------------
st.subheader("Cyclones within radius")
display_table = within_radius.sort_values("Distance_km").drop_duplicates(subset="DISTURBANCE_ID", keep="first")
st.dataframe(display_table[["DISTURBANCE_ID", "NAME", "TYPE", "TM", "LAT", "LON",
                              "MAX_WIND_SPD", "MAX_WIND_GUST", "Distance_km"]])