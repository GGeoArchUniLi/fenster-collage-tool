import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np
import re
import random
import uuid
from duckduckgo_search import DDGS

st.set_page_config(page_title="Patchwork Facade Generator", layout="wide")

# --- SPRACH-WÖRTERBUCH (WICHTIGSTE BEGRIFFE) ---
LANG_DICT = {
    "🇩🇪 DE": {"title": "🧱 Patchwork-Fassaden-Generator", "search": "🔍 Marktplätze durchsuchen", "wall": "Wandöffnung", "matrix": "📋 Beschaffungs-Matrix & Layout", "layout": "Anordnung", "fill": "Füll-Panel"},
    "🇬🇧 EN": {"title": "🧱 Patchwork Facade Generator", "search": "🔍 Search marketplaces", "wall": "Wall Opening", "matrix": "📋 Procurement Matrix & Layout", "layout": "Layout Style", "fill": "Filler Panel"},
    "🇫🇷 FR": {"title": "🧱 Générateur de Façade", "search": "🔍 Chercher les marchés", "wall": "Ouverture du mur", "matrix": "📋 Matrice d'approvisionnement", "layout": "Disposition", "fill": "Panneau de remplissage"},
    "🇮🇹 IT": {"title": "🧱 Generatore di Facciate", "search": "🔍 Cerca mercati", "wall": "Apertura del muro", "matrix": "📋 Matrice di approvvigionamento", "layout": "Disposizione", "fill": "Pannello di riempimento"},
    "🇨🇭 RM": {"title": "🧱 Generatur da Façadas", "search": "🔍 Tschertgar martgads", "wall": "Avertura da paraid", "matrix": "📋 Matrix da material", "layout": "Disposiziun", "fill": "Panel da rimplazzar"},
    "🇧🇬 BG": {"title": "🧱 Генератор на фасади", "search": "🔍 Търсене в пазари", "wall": "Отвор на стената", "matrix": "📋 Матрица за доставки", "layout": "Подредба", "fill": "Панел за пълнеж"},
    "🇮🇱 HE": {"title": "🧱 מחולל חזיתות טלאים", "search": "🔍 חפש בשווקים", "wall": "פתח קיר", "matrix": "📋 מטריצת רכש ופריסה", "layout": "סגנון פריסה", "fill": "פאנל מילוי"},
    "🇯🇵 JA": {"title": "🧱 パッチワークファサードジェネレーター", "search": "🔍 市場を検索", "wall": "壁の開口部", "matrix": "📋 調達マトリックスとレイアウト", "layout": "レイアウトスタイル", "fill": "フィラーパネル"}
}

# Sprachauswahl oben rechts
lang_choice = st.radio("Sprache / Language:", list(LANG_DICT.keys()), horizontal=True)
T = LANG_DICT[lang_choice]

st.title(T["title"])

# --- SESSION STATE ---
if 'inventory' not in st.session_state: st.session_state['inventory'] = []
if 'custom_windows' not in st.session_state: st.session_state['custom_windows'] = []
if 'is_loaded' not in st.session_state: st.session_state['is_loaded'] = False
if 'item_states' not in st.session_state: st.session_state['item_states'] = {} # Speichert Sichtbarkeit und Priorität

# --- FUNKTION: Daten suchen ---
def harvest_materials(land, plz, radius, mix_new):
    materials = []
    queries = [(f"site:ebay.de OR site:kleinanzeigen.de Fenster gebraucht {plz} {land}", "Re-Use", '#4682b4')]
    if mix_new: queries.append((f"Fenster neu kaufen {plz} {land}", "Neu", '#add8e6'))
        
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
                            st.session_state['item_states'][item_id] = {'visible': "👁️ Anzeigen", 'force': False}
        except Exception: pass 
            
    if len(materials) < 5:
        fallback = [(1200, 1400, "Re-Use", 85.0), (2000, 2100, "Neu", 350.0), (800, 600, "Re-Use", 40.0), (1000, 500, "Neu", 120.0)]
        for w, h, cond, pr in fallback * 5:
            if not mix_new and cond == "Neu": continue
            col = '#add8e6' if cond == "Neu" else '#4682b4'
            item_id = uuid.uuid4().hex
            materials.append({'id': item_id, 'w': w, 'h': h, 'type': 'Fenster', 'color': col, 'price': pr, 'source': 'Notfall-Reserve', 'condition': cond, 'link': 'https://ebay.de'})
            st.session_state['item_states'][item_id] = {'visible': "👁️ Anzeigen", 'force': False}
    return materials

# --- ALGORITHMEN ---
def check_overlap(x, y, w, h, placed):
    for p in placed:
        if not (x + w <= p['x'] or x >= p['x'] + p['w'] or y + h <= p['y'] or y >= p['y'] + p['h']): return True
    return False

def pack_mondrian_cluster(wall_w, wall_h, items):
    placed_items = []
    # Zwingende Fenster (Sterne) ganz nach vorne sortieren!
    forced_items = [i for i in items if st.session_state['item_states'][i['id']]['force']]
    normal_items = [i for i in items if not st.session_state['item_states'][i['id']]['force']]
    
    random.shuffle(normal_items) 
    mixed_normal = sorted(normal_items, key=lambda i: (i['w'] * i['h']) * random.uniform(0.5, 1.5), reverse=True)
    
    # Pack-Reihenfolge: Erst die erzwungenen, dann das gemischte Chaos
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
    
    # Markiere belegte Zellen
    for p in placed:
        px, py, pw, ph = int(p['x']//step), int(p['y']//step), int(p['w']//step), int(p['h']//step)
        grid[py:py+ph, px:px+pw] = True
        
    gaps = []
    # Finde leere Rechtecke
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
                        'type': T["fill"], 'color': '#ff4d4d', 'price': (cw*step/1000)*(ch*step/1000)*45, # ~45€ pro m2
                        'source': 'Zuschnitt', 'condition': 'Neu', 'link': ''
                    })
    return gaps

# --- UI: SIDEBAR ---
with st.sidebar:
    st.header(T["search"])
    land = st.selectbox("Land / Country", ["Deutschland", "Österreich", "Schweiz", "Liechtenstein"])
    plz = st.text_input("PLZ / Zip", "10115")
    mix_new = st.checkbox("🔄 Re-Use + Neu", value=True)
    
    if st.button(T["search"], type="primary"):
        with st.spinner("..."):
            st.session_state['inventory'] = harvest_materials(land, plz, 50, mix_new)
            st.session_state['is_loaded'] = True
        st.rerun()

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
        st.session_state['item_states'][item_id] = {'visible': "👁️ Anzeigen", 'force': True} # Eigene sind automatisch priorisiert
        st.rerun()
        
# --- UI: HAUPTBEREICH ---
if st.session_state['is_loaded'] or len(st.session_state['custom_windows']) > 0:
    total_inventory = st.session_state['custom_windows'] + st.session_state['inventory']
    
    # 1. Filtere versteckte Items VOR dem Berechnen
    usable_inventory = [item for item in total_inventory if st.session_state['item_states'].get(item['id'], {}).get('visible') == "👁️ Anzeigen"]
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader(T["wall"])
        wall_width = st.slider("Breite / Width (mm)", 1000, 12000, 4000, 100)
        wall_height = st.slider("Höhe / Height (mm)", 1000, 12000, 3000, 100)
        st.subheader(T["layout"])
        algo_choice = st.selectbox("", ["Mondrian-Cluster", "Shelf-Packing"])
        if st.button("🎲 Neu würfeln / Shuffle"): pass 

    with col2:
        # Algorithmus ausführen
        placed = pack_mondrian_cluster(wall_width, wall_height, usable_inventory) if "Mondrian" in algo_choice else pack_shelf(wall_width, wall_height, usable_inventory)
        
        # 2. Rote Gaps (Füll-Paneele) berechnen
        gaps = calculate_gaps(wall_width, wall_height, placed, step=50 if wall_width <= 6000 else 100)
        
        # Zeichnen
        fig, ax = plt.subplots(figsize=(12, 8)) 
        ax.add_patch(patches.Rectangle((0, 0), wall_width, wall_height, facecolor='#ffffff', edgecolor='black', linewidth=3))
        
        placed_ids = [p['id'] for p in placed]
        
        # Paneele zeichnen (Rot)
        for g in gaps:
            ax.add_patch(patches.Rectangle((g['x'], g['y']), g['w'], g['h'], facecolor=g['color'], edgecolor='darkred', linewidth=1, alpha=0.7))
            
        # Fenster zeichnen
        for i, item in enumerate(placed):
            line_weight = 4 if "Mondrian" in algo_choice else 2
            ax.add_patch(patches.Rectangle((item['x'], item['y']), item['w'], item['h'], facecolor=item['color'], edgecolor='black', linewidth=line_weight))
            ax.text(item['x'] + item['w']/2, item['y'] + item['h']/2, f"P{i+1}\n{item['w']}x{item['h']}", ha='center', va='center', fontsize=7, fontweight='bold')
            
        ax.set_xlim(0, max(wall_width, 4000) + 100); ax.set_ylim(0, max(wall_height, 3000) + 100)
        ax.set_aspect('equal'); plt.axis('off'); st.pyplot(fig)

    # --- INTERAKTIVE MATRIX MIT FARB-HIGHLIGHTS ---
    st.subheader(T["matrix"])
    
    df_data = []
    
    # Fenster zur Matrix hinzufügen
    for item in total_inventory:
        state = st.session_state['item_states'].get(item['id'], {'visible': "👁️ Anzeigen", 'force': False})
        
        pos_label, status = "", ""
        if item['id'] in placed_ids:
            pos_label = f"P{placed_ids.index(item['id']) + 1}"
            status = "✅ Platziert"
        elif state['visible'] == "🙈 Versteckt":
            status = "🙈 Versteckt"
        else:
            status = "❌ Passt nicht"

        df_data.append({
            "id": item['id'],
            "Sichtbarkeit": state['visible'],
            "⭐ Zwingen": state['force'],
            "Typ": item['type'],
            "Pos": pos_label,
            "Status": status,
            "Zustand": item['condition'],
            "Maße (BxH)": f"{item['w']} x {item['h']}",
            "Herkunft": item['source'],
            "Preis (€)": item['price'],
            "Link": item['link']
        })
        
    # Gaps (Füllmaterial) zur Matrix hinzufügen
    for g in gaps:
        df_data.append({
            "id": g['id'], "Sichtbarkeit": "👁️ Anzeigen", "⭐ Zwingen": False,
            "Typ": g['type'], "Pos": "Gap", "Status": "⚠️ Benötigt", "Zustand": g['condition'],
            "Maße (BxH)": f"{g['w']} x {g['h']}", "Herkunft": g['source'], "Preis (€)": g['price'], "Link": ""
        })
        
    df = pd.DataFrame(df_data)
    
    # HIGHLIGHTING FUNKTION (Dezentes Grün für genutzte Fenster, Rot für fehlende Paneele)
    def highlight_rows(row):
        if '✅' in str(row['Status']): return ['background-color: rgba(40, 167, 69, 0.2)'] * len(row)
        if '⚠️' in str(row['Status']): return ['background-color: rgba(255, 0, 0, 0.15)'] * len(row)
        return [''] * len(row)
        
    styled_df = df.style.apply(highlight_rows, axis=1)
    
    # Interaktiver Editor
    edited_df = st.data_editor(
        styled_df, 
        column_config={
            "id": None, 
            "Sichtbarkeit": st.column_config.SelectboxColumn("Sichtbarkeit", options=["👁️ Anzeigen", "🙈 Versteckt"], help="Auge umschalten, um es auszublenden."),
            "⭐ Zwingen": st.column_config.CheckboxColumn("⭐ Priorität", help="Haken setzen, um das Fenster in die Planung zu zwingen!"),
            "Link": st.column_config.LinkColumn("🛒 Shop", display_text="Link 🔗"),
            "Preis (€)": st.column_config.NumberColumn("Preis (€)", format="%.2f €")
        },
        disabled=["Typ", "Pos", "Status", "Zustand", "Maße (BxH)", "Herkunft", "Preis (€)", "Link"], 
        hide_index=True, use_container_width=True, key="matrix_editor"
    )
    
    # EINGABEN VERARBEITEN (Falls User das Auge oder den Stern klickt)
    changes_made = False
    for idx, row in edited_df.iterrows():
        item_id = row['id']
        if item_id in st.session_state['item_states']:
            old_vis = st.session_state['item_states'][item_id]['visible']
            old_frc = st.session_state['item_states'][item_id]['force']
            if row['Sichtbarkeit'] != old_vis or row['⭐ Zwingen'] != old_frc:
                st.session_state['item_states'][item_id]['visible'] = row['Sichtbarkeit']
                st.session_state['item_states'][item_id]['force'] = row['⭐ Zwingen']
                changes_made = True
                
    if changes_made: st.rerun()

else:
    st.info("👈 " + T["search"])
