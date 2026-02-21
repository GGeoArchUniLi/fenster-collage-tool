import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np
import re
import random
import uuid
from duckduckgo_search import DDGS

st.set_page_config(page_title="Patchwork Facade Generator v0.8", layout="wide")

# --- SPRACH-WÖRTERBUCH (KOMPLETT) ---
LANG_DICT = {
    "🇩🇪 DE": {"title": "🧱 Patchwork-Fassaden-Generator v0.8", "search": "🔍 Marktplätze durchsuchen", "wall": "Wandöffnung", "matrix": "📋 Beschaffungs-Matrix & Layout", "fill": "Zuschnitt"},
    "🇬🇧 EN": {"title": "🧱 Patchwork Facade Generator v0.8", "search": "🔍 Search marketplaces", "wall": "Wall Opening", "matrix": "📋 Procurement Matrix & Layout", "fill": "Filler Panel"},
    "🇫🇷 FR": {"title": "🧱 Générateur de Façade v0.8", "search": "🔍 Chercher les marchés", "wall": "Ouverture du mur", "matrix": "📋 Matrice d'approvisionnement", "fill": "Panneau de remplissage"},
    "🇮🇹 IT": {"title": "🧱 Generatore di Facciate v0.8", "search": "🔍 Cerca mercati", "wall": "Apertura del muro", "matrix": "📋 Matrice di approvvigionamento", "fill": "Pannello di riempimento"},
    "🇨🇭 RM": {"title": "🧱 Generatur da Façadas v0.8", "search": "🔍 Tschertgar martgads", "wall": "Avertura da paraid", "matrix": "📋 Matrix da material", "fill": "Panel da rimplazzar"},
    "🇧🇬 BG": {"title": "🧱 Генератор на фасади v0.8", "search": "🔍 Търсене в пазари", "wall": "Отвор на стената", "matrix": "📋 Матрица за доставки", "fill": "Панел за пълнеж"},
    "🇮🇱 HE": {"title": "🧱 מחולל חזיתות טלאים v0.8", "search": "🔍 חפש בשווקים", "wall": "פתח קיר", "matrix": "📋 מטריצת רכש ופריסה", "fill": "פאנל מילוי"},
    "🇯🇵 JA": {"title": "🧱 パッチワークファサードジェネレーター v0.8", "search": "🔍 市場を検索", "wall": "壁の開口部", "matrix": "📋 調達マトリックスとレイアウト", "fill": "フィラーパネル"}
}

lang_choice = st.radio("Sprache / Language:", list(LANG_DICT.keys()), horizontal=True)
T = LANG_DICT[lang_choice]

st.title(T["title"])

# --- SESSION STATE ---
if 'inventory' not in st.session_state: st.session_state['inventory'] = []
if 'custom_windows' not in st.session_state: st.session_state['custom_windows'] = []
if 'is_loaded' not in st.session_state: st.session_state['is_loaded'] = False
if 'item_states' not in st.session_state: st.session_state['item_states'] = {} 

# --- FUNKTION: Daten suchen ---
def harvest_materials(land, plz, use_reuse, use_new):
    materials = []
    queries = []
    if use_reuse: queries.append((f"site:ebay.de OR site:kleinanzeigen.de Fenster gebraucht {plz} {land}", "Re-Use", '#4682b4'))
    if use_new: queries.append((f"Fenster neu kaufen {plz} {land}", "Neu", '#add8e6'))
        
    for query, condition, color in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=20))
                for res in results:
                    match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', res['title'] + " " + res['body'])
                    if match:
                        w, h = int(match.group(1)), int(match.group(2))
                        price_match = re.search(r'(\d{1,5})[.,]?\d*\s*[€|EUR]', res['title'] + " " + res['body'])
                        price = float(price_match.group(1)) if price_match else float(int((w * h) / 20000) + random.randint(10, 50))
                        if 300 <= w <= 12000 and 300 <= h <= 12000:
                            item_id = uuid.uuid4().hex
                            materials.append({
                                'id': item_id, 'w': w, 'h': h, 'type': 'Fenster', 'color': color, 
                                'price': price, 'source': res['title'][:30] + '...', 
                                'condition': condition, 'link': res['href']
                            })
                            st.session_state['item_states'][item_id] = {'visible': True, 'force': False}
        except Exception: pass 
            
    if len(materials) < 3: 
        fallback = [(1200, 1400, "Re-Use", 85.0), (2000, 2100, "Neu", 350.0), (800, 600, "Re-Use", 40.0)]
        for w, h, cond, pr in fallback * 5:
            if not use_new and cond == "Neu": continue
            if not use_reuse and cond == "Re-Use": continue
            col = '#add8e6' if cond == "Neu" else '#4682b4'
            item_id = uuid.uuid4().hex
            materials.append({'id': item_id, 'w': w, 'h': h, 'type': 'Fenster', 'color': col, 'price': pr, 'source': 'Notfall-Reserve', 'condition': cond, 'link': 'https://ebay.de'})
            st.session_state['item_states'][item_id] = {'visible': True, 'force': False}
    return materials

# --- ALGORITHMEN ---
def check_overlap(x, y, w, h, placed):
    for p in placed:
        if not (x + w <= p['x'] or x >= p['x'] + p['w'] or y + h <= p['y'] or y >= p['y'] + p['h']): return True
    return False

def pack_mondrian_cluster(wall_w, wall_h, items):
    placed_items = []
    forced_items = [i for i in items if st.session_state['item_states'][i['id']]['force']]
    normal_items = [i for i in items if not st.session_state['item_states'][i['id']]['force']]
    
    random.shuffle(normal_items) 
    mixed_normal = sorted(normal_items, key=lambda i: (i['w'] * i['h']) * random.uniform(0.5, 1.5), reverse=True)
    
    pack_list = forced_items + mixed_normal
    step = 50 if wall_w <= 6000 else 100
    
    for item in pack_list: 
        fitted = False
        for y in range(0, wall_h - item['h'] + 1, step):
            for x in range(0, wall_w - item['w'] + 1, step):
                if not check_overlap(x, y, item['w'], item['h'], placed_items):
                    placed_items.append({**item, 'x': x, 'y': y})
                    fitted = True; break
            if fitted: break
            
    if placed_items:
        max_x = max(p['x'] + p['w'] for p in placed_items)
        max_y = max(p['y'] + p['h'] for p in placed_items)
        offset_x = (wall_w - max_x) // 2
        offset_y = (wall_h - max_y) // 2
        for p in placed_items: p['x'] += offset_x; p['y'] += offset_y
            
    return placed_items

# --- LÜCKEN/PANEELE BERECHNEN ---
def calculate_gaps(wall_w, wall_h, placed, step=50):
    grid_w, grid_h = int(wall_w // step), int(wall_h // step)
    grid = np.zeros((grid_h, grid_w), dtype=bool)
    
    for p in placed:
        px, py, pw, ph = int(p['x']//step), int(p['y']//step), int(p['w']//step), int(p['h']//step)
        grid[py:py+ph, px:px+pw] = True
        
    gaps = []
    for y in range(grid_h):
        for x in range(grid_w):
            if not grid[y, x]:
                cw = 0
                while x + cw < grid_w and not grid[y, x + cw]: cw += 1
                ch = 0; valid = True
                while y + ch < grid_h and valid:
                    for ix in range(x, x + cw):
                        if grid[y + ch, ix]: valid = False; break
                    if valid: ch += 1
                grid[y:y+ch, x:x+cw] = True
                if cw > 0 and ch > 0:
                    gaps.append({
                        'id': uuid.uuid4().hex, 'x': x*step, 'y': y*step, 'w': cw*step, 'h': ch*step, 
                        'type': T["fill"], 'color': '#ff4d4d', 'price': 0.0,
                        'source': 'Plattenmaterial', 'condition': 'Neu', 'link': ''
                    })
    return gaps

# --- UI: SIDEBAR ---
with st.sidebar:
    st.header(T["search"])
    land = st.selectbox("Land / Country", ["Deutschland", "Österreich", "Schweiz", "Liechtenstein"])
    plz = st.text_input("PLZ / Zip", "10115")
    
    use_reuse = st.checkbox("🔄 Gebrauchte Fenster (Re-Use)", value=True)
    use_new = st.checkbox("🆕 Fabrikneue Fenster", value=False)
    
    if st.button(T["search"], type="primary"):
        with st.spinner("..."):
            st.session_state['inventory'] = harvest_materials(land, plz, use_reuse, use_new)
            st.session_state['is_loaded'] = True
        st.rerun()

    st.divider()
    
    if st.session_state['is_loaded']:
        st.header("📊 Kalkulation")
        stats_container = st.empty()
        st.divider()

    st.header("➕ Eigenbestand")
    colA, colB = st.columns(2)
    with colA: cw_w = st.number_input("Breite", 300, 12000, 1000, step=50)
    with colB: cw_h = st.number_input("Höhe", 300, 12000, 1200, step=50)
    if st.button("Hinzufügen"):
        item_id = uuid.uuid4().hex
        st.session_state['custom_windows'].append({
            'id': item_id, 'w': int(cw_w), 'h': int(cw_h), 'type': 'Fenster', 
            'color': '#90EE90', 'price': 0.0, 'source': 'Mein Lager', 'condition': 'Eigen', 'link': ''
        })
        st.session_state['item_states'][item_id] = {'visible': True, 'force': True}
        st.rerun()
        
# --- UI: HAUPTBEREICH ---
if st.session_state['is_loaded'] or len(st.session_state['custom_windows']) > 0:
    total_inventory = st.session_state['custom_windows'] + st.session_state['inventory']
    
    # Pack-Algorithmus bekommt NUR sichtbare Fenster
    usable_inventory = [item for item in total_inventory if st.session_state['item_states'].get(item['id'], {}).get('visible') == True]
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader(T["wall"])
        wall_width = st.slider("Breite / Width (mm)", 1000, 12000, 4000, 100)
        wall_height = st.slider("Höhe / Height (mm)", 1000, 12000, 3000, 100)
        if st.button("🎲 Neu würfeln / Shuffle"): pass 

    with col2:
        placed = pack_mondrian_cluster(wall_width, wall_height, usable_inventory)
        gaps = calculate_gaps(wall_width, wall_height, placed, step=50 if wall_width <= 6000 else 100)
        
        # Stats berechnen
        total_price = sum(p['price'] for p in placed)
        wall_area_m2 = (wall_width * wall_height) / 1000000
        win_area_m2 = sum((p['w'] * p['h'])/1000000 for p in placed)
        win_pct = (win_area_m2 / wall_area_m2 * 100) if wall_area_m2 > 0 else 0
        
        # Sidebar Stats updaten (Wandfläche hinzugefügt)
        stats_container.markdown(f"### 💶 Fenster: **{total_price:.2f} €**")
        stats_container.markdown(f"**Wandöffnung:** {wall_area_m2:.2f} m²<br>**Fensterfläche:** {win_area_m2:.2f} m²<br>*(Füllgrad: {win_pct:.1f}%)*", unsafe_allow_html=True)
        
        fig, ax = plt.subplots(figsize=(12, 8)) 
        ax.add_patch(patches.Rectangle((0, 0), wall_width, wall_height, facecolor='#ffffff', edgecolor='black', linewidth=3))
        
        placed_ids = [p['id'] for p in placed]
        
        for g in gaps:
            ax.add_patch(patches.Rectangle((g['x'], g['y']), g['w'], g['h'], facecolor=g['color'], edgecolor='darkred', linewidth=1, alpha=0.7))
            g_area = (g['w'] * g['h']) / 1000000
            if g['w'] >= 400 and g['h'] >= 400: 
                ax.text(g['x'] + g['w']/2, g['y'] + g['h']/2, f"{g_area:.2f} m²", ha='center', va='center', fontsize=6, color='white')
            
        for i, item in enumerate(placed):
            ax.add_patch(patches.Rectangle((item['x'], item['y']), item['w'], item['h'], facecolor=item['color'], edgecolor='black', linewidth=4))
            ax.text(item['x'] + item['w']/2, item['y'] + item['h']/2, f"P{i+1}\n{item['w']}x{item['h']}", ha='center', va='center', fontsize=7, fontweight='bold')
            
        ax.set_xlim(0, max(wall_width, 4000) + 100); ax.set_ylim(0, max(wall_height, 3000) + 100)
        ax.set_aspect('equal'); plt.axis('off'); st.pyplot(fig)

    # --- INTERAKTIVE MATRIX ---
    st.subheader(T["matrix"])
    
    df_data = []
    
    # 1. ALLE Fenster zur Matrix (auch die ausgeblendeten!)
    for item in total_inventory:
        state = st.session_state['item_states'].get(item['id'], {'visible': True, 'force': False})
        area_m2 = (item['w'] * item['h']) / 1000000
        
        pos_label, status = "", ""
        if not state['visible']:
            status = "🙈 Versteckt"
            pos_label = "-"
        elif item['id'] in placed_ids:
            pos_label = f"P{placed_ids.index(item['id']) + 1}"
            status = "✅ Platziert"
        else:
            status = "❌ Passt nicht"

        df_data.append({
            "id": item['id'],
            "👁️ Ein/Aus": state['visible'], 
            "⭐ Zwingen": state['force'],
            "Typ": item['type'],
            "Pos": pos_label,
            "Status": status,
            "Maße (BxH)": f"{item['w']} x {item['h']}",
            "Fläche (m²)": f"{area_m2:.2f}",
            "Herkunft": item['source'],
            "Preis": f"{item['price']:.2f} €", 
            "Link": item['link']
        })
        
    for g in gaps:
        area_m2 = (g['w'] * g['h']) / 1000000
        df_data.append({
            "id": g['id'], "👁️ Ein/Aus": True, "⭐ Zwingen": False, "Typ": g['type'], 
            "Pos": "Gap", "Status": "⚠️ Benötigt", "Maße (BxH)": f"{g['w']} x {g['h']}", 
            "Fläche (m²)": f"{area_m2:.2f}", "Herkunft": g['source'], "Preis": "-", "Link": ""
        })
        
    df = pd.DataFrame(df_data)
    
    def highlight_rows(row):
        if '✅' in str(row['Status']): return ['background-color: rgba(40, 167, 69, 0.2)'] * len(row)
        if '⚠️' in str(row['Status']): return ['background-color: rgba(255, 0, 0, 0.15)'] * len(row)
        if '🙈' in str(row['Status']): return ['background-color: rgba(128, 128, 128, 0.2); color: gray'] * len(row)
        return [''] * len(row)
        
    styled_df = df.style.apply(highlight_rows, axis=1)
    
    edited_df = st.data_editor(
        styled_df, 
        column_config={
            "id": None, 
            "👁️ Ein/Aus": st.column_config.CheckboxColumn("👁️ Layer", help="Haken raus = aus dem Bild ausblenden"),
            "⭐ Zwingen": st.column_config.CheckboxColumn("⭐ Priorität"),
            "Link": st.column_config.LinkColumn("🛒 Shop", display_text="Link 🔗")
        },
        disabled=["Typ", "Pos", "Status", "Maße (BxH)", "Fläche (m²)", "Herkunft", "Preis", "Link"], 
        hide_index=True, use_container_width=True, key="matrix_editor"
    )
    
    st.markdown(f"### 💶 Gesamtpreis Fenster: **{total_price:.2f} €**")
    st.markdown(f"**Gesamtfläche Fenster:** {win_area_m2:.2f} m² | **Wandfläche:** {wall_area_m2:.2f} m²")
    
    changes_made = False
    for idx, row in edited_df.iterrows():
        item_id = row['id']
        if item_id in st.session_state['item_states']:
            old_vis = st.session_state['item_states'][item_id]['visible']
            old_frc = st.session_state['item_states'][item_id]['force']
            
            if row['👁️ Ein/Aus'] != old_vis or row['⭐ Zwingen'] != old_frc:
                st.session_state['item_states'][item_id]['visible'] = row['👁️ Ein/Aus']
                st.session_state['item_states'][item_id]['force'] = row['⭐ Zwingen']
                changes_made = True
                
    if changes_made: st.rerun()

else:
    st.info("👈 " + T["search"])
