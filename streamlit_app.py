import streamlit as st
import pandas as pd
import numpy as np
import json
import streamlit.components.v1 as components

def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1r = np.radians(lat1)
    lat2r = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

st.set_page_config(layout="wide")
st.title("Cyclone Pass Counter")

# ---------- Load CSV (update path if needed) ----------
csv_path = r"C:\Users\WA10VM\OneDrive - Woodside Energy Ltd\Desktop\IDCKMSTM0S.csv"
df = pd.read_csv(csv_path, header=4)
df["MAX_WIND_SPD"] = pd.to_numeric(df["MAX_WIND_SPD"], errors="coerce")
df["MAX_WIND_GUST"] = pd.to_numeric(df["MAX_WIND_GUST"], errors="coerce")

# ---------- Pin & radius ----------
st.subheader("Pin coordinates")
c1, c2, c3 = st.columns(3)
pin_lat = c1.number_input("Pin latitude", value=-20.591733, format="%.6f")
pin_lon = c2.number_input("Pin longitude", value=116.777616, format="%.6f")
radius_km = c3.slider("Radius (km)", min_value=50, max_value=2000, value=200, step=50)

df["Distance_km"] = haversine_vectorized(pin_lat, pin_lon, df["LAT"], df["LON"])

closest = df.groupby("DISTURBANCE_ID")["Distance_km"].min()
keep_ids = closest[closest <= 2000].index
df_full = df[df["DISTURBANCE_ID"].isin(keep_ids)].copy()
df_full["TM_parsed"] = pd.to_datetime(df_full["TM"], format="%d/%m/%Y %H:%M", errors="coerce")

df = df_full[df_full["Distance_km"] < radius_km].copy()
st.caption(f"{df['DISTURBANCE_ID'].nunique()} cyclones have at least one point within {radius_km}km of the pin.")

# ---------- Filters ----------
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

filtered = df.copy()
if selected_names:
    filtered = filtered[filtered["NAME"].isin(selected_names)]
if selected_ids:
    filtered = filtered[filtered["DISTURBANCE_ID"].isin(selected_ids)]
if selected_types:
    filtered = filtered[filtered["TYPE"].isin(selected_types)]

filtered = filtered[
    (filtered["MAX_WIND_SPD"] >= wind_range[0]) & (filtered["MAX_WIND_SPD"] <= wind_range[1]) &
    (filtered["MAX_WIND_GUST"] >= gust_range[0]) & (filtered["MAX_WIND_GUST"] <= gust_range[1]) &
    (filtered["TM_parsed"].dt.date >= date_range[0]) & (filtered["TM_parsed"].dt.date <= date_range[1])
]

within_radius = filtered.copy()
within_radius["DATE_ONLY"] = within_radius["TM_parsed"].dt.date
unique_cyclones = within_radius["DISTURBANCE_ID"].unique()
unique_days = within_radius["DATE_ONLY"].unique()

col1, col2 = st.columns(2)
col1.metric("Unique cyclones", len(unique_cyclones))
col2.metric("Unique exposure days", len(unique_days))

# ---------- Animation controls ----------
st.subheader("Animation")
st.caption("Cyclones play one at a time in chronological order. Each track draws point-by-point.")
a1, a2 = st.columns(2)
point_speed_ms = a1.slider("Time per point (ms)", 1, 1500, 250, step=10)
export_label_map = {"Standard (1300px)": 1300, "High (2600px)": 2600, "Ultra (3900px)": 3900}
export_choice = a2.selectbox("Export resolution", options=list(export_label_map.keys()), index=0)

colors = [
    "#1f78b4", "#33a02c", "#e31a1c", "#ff7f00", "#6a3d9a", "#b15928",
    "#a6cee3", "#b2df8a", "#fb9a99", "#fdbf6f", "#cab2d6", "#999900",
    "#8dd3c7", "#bdb000", "#bebada", "#fb8072", "#80b1d3", "#fdb462",
    "#b3de69", "#fccde5", "#4daf4a", "#377eb8", "#e41a1c", "#984ea3"
]

# ---------- Prepare tracks (use df_full for full tracks) ----------
qualifying_ids = set(within_radius["DISTURBANCE_ID"].unique())
groups = []
for cid, g in df_full.groupby("DISTURBANCE_ID"):
    if cid not in qualifying_ids:
        continue
    g2 = g.dropna(subset=["LAT", "LON", "TM_parsed"]).sort_values("TM_parsed").reset_index(drop=True)
    if len(g2) > 0:
        groups.append((cid, g2))
groups.sort(key=lambda x: x[1]["TM_parsed"].min())

cyclone_tracks = []
for color_i, (cid, track) in enumerate(groups):
    color = colors[color_i % len(colors)]
    name = track["NAME"].iloc[0] if "NAME" in track.columns and pd.notna(track["NAME"].iloc[0]) else ""
    year = int(track["TM_parsed"].iloc[0].year)
    points = []
    for row in track.itertuples(index=False):
        points.append({"lat": float(row.LAT), "lon": float(row.LON), "tm": str(row.TM), "dist": round(float(row.Distance_km), 1)})
    cyclone_tracks.append({"id": str(cid), "name": str(name), "year": year, "color": color, "points": points})

tracks_json = json.dumps(cyclone_tracks)

if cyclone_tracks:
    summary_start_year = min([t["year"] for t in cyclone_tracks])
else:
    summary_start_year = pd.Timestamp.now().year
summary_num_cyclones = len(cyclone_tracks)
summary_num_days = len(unique_days)

if not cyclone_tracks:
    st.info("No cyclones meet the current filters to animate.")

# Debug toggle: server diagnostics + client JS logging
try:
    debug_mode = st.checkbox("Enable debug mode (client console + server diagnostics)", value=False)
except Exception:
    debug_mode = False

if debug_mode:
    st.write("DEBUG (server): tracks=", len(cyclone_tracks), "start_year=", summary_start_year, "cyclones=", summary_num_cyclones, "days=", summary_num_days)
    st.write("DEBUG (server): pin=", pin_lat, pin_lon, "radius_km=", radius_km, "point_speed_ms=", point_speed_ms)

# ---------- Build HTML using placeholder template (avoid f-string brace conflicts) ----------
def build_html(map_h):
    template = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html, body { margin: 0; padding: 0; }
  #map { width: 100%; height: __MAP_H__px; background: #eef3f7; position: relative; }
  #controls {
    position: absolute; top: 10px; right: 10px; z-index: 1100;
    background: white; padding: 8px 12px; border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-family: sans-serif; font-size: 13px;
  }
  #controls button, #controls select { margin-right: 6px; padding: 4px 8px; cursor: pointer; border: 1px solid #888; border-radius: 4px; background: #f7f7f7; font-size:12px; }
  #status { margin-top: 6px; color: #333; font-size:13px; }
  #mapwrap { position: relative; }
  #summary_box {
    position: absolute; right: 8%; top: 50%; transform: translateY(-50%); z-index: 1200;
    background: rgba(255,255,255,0.98); padding: 20px 26px; border-radius: 10px;
    box-shadow: 0 2px 14px rgba(0,0,0,0.32); font-family: sans-serif; font-size: 26px; font-weight: 800;
    max-width: 560px; display: none; text-align: left; line-height:1.15;
  }
  #source_label {
    position: absolute; left: 10px; bottom: 6px; z-index: 1200; background: rgba(255,255,255,0.9);
    padding: 6px 10px; border-radius: 4px; font-size: 13px; font-family: sans-serif; color: #333;
  }
  #regionOverlay { position: absolute; left:0; top:0; right:0; bottom:0; z-index:1150; display:none; }
  .selectionRect { position:absolute; border:3px dashed rgba(0,120,200,0.95); background: rgba(0,120,200,0.06); box-sizing:border-box; }
  #recordCanvas { display:none }
</style>
</head>
<body>
<div id="mapwrap">
  <div id="map"></div>
  <div id="controls">
    <button id="playPauseBtn">Pause</button>
    <button id="restartBtn">Restart</button>
    <label for="captureMode">Capture:</label>
    <select id="captureMode"><option value="browser">Browser tab</option><option value="screen">Entire screen</option><option value="window">Window</option></select>
    <button id="toggleRegionBtn">Select region</button>
    <button id="recordBtn">Record</button>
    <div id="status">Loading...</div>
  </div>
  <div id="summary_box"></div>
  <div id="source_label">Source: Bureau of Meteorology Australia</div>
  <div id="regionOverlay"></div>
  <canvas id="recordCanvas"></canvas>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  var tracks = __TRACKS_JSON__;
  var pinLat = __PIN_LAT__;
  var pinLon = __PIN_LON__;
  var radiusKm = __RADIUS_KM__;
  var pointSpeedMs = __POINT_SPEED_MS__;
  var DEBUG = __DEBUG__;
  if (DEBUG) { console.log('DEBUG (client): tracks count =', tracks.length); console.log('pinLat, pinLon =', pinLat, pinLon, 'radiusKm =', radiusKm, 'pointSpeedMs =', pointSpeedMs); }

  var summaryStartYear = __SUMMARY_START_YEAR__;
  var summaryCyclonesCount = __SUMMARY_NUM_CYCLONES__;
  var summaryUniqueDays = __SUMMARY_NUM_DAYS__;

  var map = L.map('map').setView([pinLat, pinLon], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 12, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);

  var pinMarker = L.marker([pinLat, pinLon]).addTo(map).bindTooltip("Pin");
  var radiusCircle = L.circle([pinLat, pinLon], { radius: radiusKm * 1000, color: 'red', fillColor: 'red', fillOpacity: 0.08, weight: 2 }).addTo(map);

  var statusEl = document.getElementById('status');
  var playPauseBtn = document.getElementById('playPauseBtn');
  var restartBtn = document.getElementById('restartBtn');
  var recordBtn = document.getElementById('recordBtn');
  var toggleRegionBtn = document.getElementById('toggleRegionBtn');
  var captureMode = document.getElementById('captureMode');
  var summaryBox = document.getElementById('summary_box');
  var regionOverlay = document.getElementById('regionOverlay');
  var recordCanvas = document.getElementById('recordCanvas');

  var playing = true; var cycloneIdx = 0; var pointIdx = 0; var currentPolyline = null; var currentCoords = []; var timer = null;

  function fmtStatus() {
    if (tracks.length === 0) { statusEl.textContent = "No cyclones to show."; return; }
    var t = tracks[cycloneIdx];
    statusEl.textContent = "Cyclone " + (cycloneIdx + 1) + "/" + tracks.length + ": " + t.id + (t.name ? " (" + t.name + ")" : "") + " — point " + (pointIdx) + "/" + t.points.length;
  }

  function startCyclone(idx) {
    if (idx >= tracks.length) {
      statusEl.textContent = "Animation complete. " + tracks.length + " cyclone(s) shown.";
      playing = false; playPauseBtn.textContent = "Play";
      summaryBox.style.display = 'block';
      summaryBox.innerHTML = 'From ' + summaryStartYear + ', within ' + radiusKm + ' km of Karratha Gas Plant there have been <br>' +
        '<span style="font-size:34px;color:#c62828;">' + summaryCyclonesCount + '</span>' + ' cyclone' + (summaryCyclonesCount===1? '': 's') + ' across <span style="font-size:34px;color:#1565c0;">' + summaryUniqueDays + '</span>' + ' calendar day' + (summaryUniqueDays===1? '': 's') + '.';
      return;
    }
    cycloneIdx = idx; pointIdx = 0; currentCoords = []; var t = tracks[cycloneIdx];
    currentPolyline = L.polyline([], { color: t.color, weight: 3, opacity: 0.85 }).addTo(map);
    var startP = t.points[0]; var labelText = t.year + (t.name ? " " + t.name : " " + t.id);
    L.marker([startP.lat, startP.lon], { icon: L.divIcon({ className: 'cyclone-label', html: '<div style="background:white;border:1px solid ' + t.color + ';color:' + t.color + ';font-weight:600;font-size:11px;padding:1px 5px;border-radius:3px;white-space:nowrap;box-shadow:0 1px 2px rgba(0,0,0,0.25);">' + labelText + '</div>', iconSize: null, iconAnchor: [-8, 8] }) }).addTo(map);
    scheduleNext();
  }

  function addPoint() { var t = tracks[cycloneIdx]; if (pointIdx >= t.points.length) { startCyclone(cycloneIdx + 1); return; } var p = t.points[pointIdx]; currentCoords.push([p.lat, p.lon]); currentPolyline.setLatLngs(currentCoords); var marker = L.circleMarker([p.lat, p.lon], { radius:5, color: t.color, fillColor: t.color, fillOpacity:0.9, weight:1 }).addTo(map); marker.bindTooltip(t.id + " (" + t.name + ") | " + p.tm + " | " + p.dist + " km"); pointIdx += 1; fmtStatus(); scheduleNext(); }

  function scheduleNext() { if (!playing) return; timer = setTimeout(addPoint, pointSpeedMs); }

  playPauseBtn.addEventListener('click', function() { playing = !playing; playPauseBtn.textContent = playing ? 'Pause' : 'Play'; if (playing) scheduleNext(); else clearTimeout(timer); });
  restartBtn.addEventListener('click', function() { clearTimeout(timer); map.eachLayer(function(layer) { if (layer === pinMarker || layer === radiusCircle) return; if (layer instanceof L.Polyline || layer instanceof L.CircleMarker || layer instanceof L.Marker) map.removeLayer(layer); }); playing = true; playPauseBtn.textContent='Pause'; summaryBox.style.display='none'; startCyclone(0); });

  var selecting = false; var rectEl = null; var startX=0, startY=0, sel={x:0,y:0,w:0,h:0};
  toggleRegionBtn.addEventListener('click', function() {
    selecting = !selecting; regionOverlay.style.display = selecting ? 'block' : 'none';
    toggleRegionBtn.textContent = selecting ? 'Finish selection' : 'Select region';
    if (!selecting && rectEl) { const r = rectEl.getBoundingClientRect(); const m = document.getElementById('map').getBoundingClientRect(); sel.x = r.left - m.left; sel.y = r.top - m.top; sel.w = r.width; sel.h = r.height; }
  });

  regionOverlay.addEventListener('pointerdown', function(ev) {
    if (!selecting) return; if (rectEl) { regionOverlay.removeChild(rectEl); rectEl=null; }
    startX = ev.clientX; startY = ev.clientY; rectEl = document.createElement('div'); rectEl.className='selectionRect'; rectEl.style.left = startX + 'px'; rectEl.style.top = startY + 'px'; rectEl.style.width='0px'; rectEl.style.height='0px'; regionOverlay.appendChild(rectEl);
    function moveFn(e) { const w = Math.abs(e.clientX - startX); const h = Math.abs(e.clientY - startY); rectEl.style.left = Math.min(e.clientX, startX) + 'px'; rectEl.style.top = Math.min(e.clientY, startY) + 'px'; rectEl.style.width = w + 'px'; rectEl.style.height = h + 'px'; }
    function upFn(e) { regionOverlay.removeEventListener('pointermove', moveFn); regionOverlay.removeEventListener('pointerup', upFn); }
    regionOverlay.addEventListener('pointermove', moveFn);
    regionOverlay.addEventListener('pointerup', upFn);
  });

  var mediaRecorder = null; var recordedChunks = [];
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      const video = document.createElement('video'); video.srcObject = stream; video.muted = true; await video.play();
      const mapRect = document.getElementById('map').getBoundingClientRect();
      let crop = { x:0, y:0, w:mapRect.width, h:mapRect.height };
      if (sel.w > 0 && sel.h > 0) { crop = { x: sel.x, y: sel.y, w: sel.w, h: sel.h }; }
      const vW = video.videoWidth || video.getBoundingClientRect().width; const vH = video.videoHeight || video.getBoundingClientRect().height;
      const scaleX = vW / mapRect.width; const scaleY = vH / mapRect.height;
      const sx = Math.max(0, Math.round(crop.x * scaleX)); const sy = Math.max(0, Math.round(crop.y * scaleY));
      const sW = Math.max(1, Math.round(crop.w * scaleX)); const sH = Math.max(1, Math.round(crop.h * scaleY));

      recordCanvas.width = sW; recordCanvas.height = sH; const ctx = recordCanvas.getContext('2d');
      const canvasStream = recordCanvas.captureStream(30);
      let options = { mimeType: 'video/webm; codecs=vp9' };
      if (!MediaRecorder.isTypeSupported(options.mimeType)) { options = { mimeType: 'video/webm; codecs=vp8' }; if (!MediaRecorder.isTypeSupported(options.mimeType)) options = {}; }
      recordedChunks = [];
      mediaRecorder = new MediaRecorder(canvasStream, options);
      mediaRecorder.ondataavailable = function(e) { if (e.data && e.data.size > 0) recordedChunks.push(e.data); };
      mediaRecorder.onstop = function() {
        const blob = new Blob(recordedChunks, { type: 'video/webm' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.style.display='none'; a.href = url;
        a.download = "__DOWNLOAD_FILENAME__";
        document.body.appendChild(a); a.click(); setTimeout(()=>{ document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
        stream.getTracks().forEach(t => t.stop());
      };
      mediaRecorder.start();
      const drawLoop = () => {
        try { ctx.clearRect(0,0,recordCanvas.width, recordCanvas.height); ctx.drawImage(video, sx, sy, sW, sH, 0, 0, recordCanvas.width, recordCanvas.height); } catch(e) {}
        if (mediaRecorder && mediaRecorder.state === 'recording') requestAnimationFrame(drawLoop);
      };
      drawLoop();
    } catch (err) { alert('Recording failed or was cancelled: ' + err); throw err; }
  }

  function stopRecording() { if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop(); mediaRecorder = null; recordedChunks = []; }

  recordBtn.addEventListener('click', async function() { if (recordBtn.dataset.rec !== '1') { try { await startRecording(); recordBtn.textContent = 'Stop recording'; recordBtn.dataset.rec = '1'; } catch(e) {} } else { stopRecording(); recordBtn.textContent='Record'; recordBtn.dataset.rec = '0'; } });

  if (tracks.length > 0) { var allLatLngs = []; tracks.forEach(function(t) { t.points.forEach(function(p) { allLatLngs.push([p.lat,p.lon]); }); }); if (allLatLngs.length>0) map.fitBounds(allLatLngs, { padding:[20,20] }); startCyclone(0); } else { statusEl.textContent='No cyclones to show.'; }
</script>
</body>
</html>
"""
    html = template.replace("__MAP_H__", str(map_h))
    html = html.replace("__TRACKS_JSON__", tracks_json)
    html = html.replace("__PIN_LAT__", str(pin_lat))
    html = html.replace("__PIN_LON__", str(pin_lon))
    html = html.replace("__RADIUS_KM__", str(radius_km))
    html = html.replace("__POINT_SPEED_MS__", str(point_speed_ms))
    html = html.replace("__DEBUG__", str(debug_mode).lower())
    html = html.replace("__SUMMARY_START_YEAR__", str(summary_start_year))
    html = html.replace("__SUMMARY_NUM_CYCLONES__", str(summary_num_cyclones))
    html = html.replace("__SUMMARY_NUM_DAYS__", str(summary_num_days))
    html = html.replace("__DOWNLOAD_FILENAME__", f"cyclone_animation_{summary_start_year}_{radius_km}km.webm")
    return html

map_height = 1300
html_code = build_html(map_height)
components.html(html_code, height=map_height + 10, scrolling=False)

# ---------- HTML download at selected resolution ----------
export_pixels = export_label_map[export_choice]
export_html = build_html(export_pixels)
st.download_button(
    label=f"Download animation HTML ({export_choice})",
    data=export_html.encode("utf-8"),
    file_name=f"cyclone_animation_{export_pixels}px.html",
    mime="text/html"
)

# ---------- Table ----------
st.subheader("Cyclones within radius")
display_table = within_radius.sort_values("Distance_km").drop_duplicates(subset="DISTURBANCE_ID", keep="first")
st.dataframe(display_table[["DISTURBANCE_ID", "NAME", "TYPE", "TM", "LAT", "LON", "MAX_WIND_SPD", "MAX_WIND_GUST", "Distance_km"]])