import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import re
import random
from duckduckgo_search import DDGS

st.set_page_config(page_title="Re-Use Fassaden-Generator", layout="wide")
st.title("🧱 Patchwork-Fassaden-Generator V5 (Cluster & Frame)")

# --- SESSION STATE ---
if 'inventory' not in st.session_state: st.session_state['inventory'] = []
if 'custom_windows' not in st.session_state: st.session_state['custom_windows'] = []
if 'is_loaded' not in st.session_state: st.session_state['is_loaded'] = False

# --- FUNKTION: Echte Daten & Links suchen ---
def harvest_materials(land, plz, radius, mix_new):
    materials = []
    queries = [(f"site:ebay.de OR site:kleinanzeigen.de Fenster gebraucht {plz} {land}", "Gebraucht (Re-Use)", '#4682b4')]
    if mix_new: queries.append((f"Fenster neu kaufen {plz} {land}", "Fabrikneu", '#add8e6'))
        
    for query, condition, color in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=25))
                for res in results:
                    text_to_search = res['title'] + " " + res['body']
                    match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', text_to_search)
                    if match:
                        w, h = int(match.group(1)), int(match.group(2))
                        price_match = re.search(r'(\d{1,5})[.,]?\d*\s*[€|EUR]', text_to_search)
                        price = float(price_match.group(1)) if price_match else float(int((w * h) / 20000) + random.randint(10, 50))

                        if 300 <= w <= 12000 and 300 <= h <= 12000:
                            materials.append({
                                'w': w, 'h': h, 'type': 'Fenster', 'color': color, 
                                'label': f"F ({'Neu' if condition == 'Fabrikneu' else 'Alt'})", 
                                'price': price, 'source': res['title'][:30] + '...', 
                                'condition': condition, 'link': res['href']
                            })
        except Exception:
            pass 
            
    if len(materials) < 5:
        fallback = [
            (1200, 1400, "Gebraucht (Re-Use)", "https://ebay.de", 85.0), (2000, 2100, "Fabrikneu", "https://amazon.de", 350.0),
            (800, 600, "Gebraucht (Re-Use)", "https://kleinanzeigen.de", 40.0), (500, 1000, "Gebraucht (Re-Use)", "https://ebay.de", 30.0),
            (1000, 500, "Fabrikneu", "https://amazon.de", 120.0), (600, 600, "Gebraucht (Re-Use)", "https://ebay.de", 25.0)
        ]
        for w, h, cond, lnk, pr in fallback * 6:
            if not mix_new and cond == "Fabrikneu": continue
            col = '#add8e6' if cond == "Fabrikneu" else '#4682b4'
            materials.append({'w': w, 'h': h, 'type': 'Fenster', 'color': col, 'label': f'F ({cond[:3]})', 'price': pr, 'source': 'Notfall-Reserve', 'condition': cond, 'link': lnk})
    return materials

# --- ALGORITHMEN ---
def check_overlap(x, y, w, h, placed):
    for p in placed:
        if not (x + w <= p['x'] or x >= p['x'] + p['w'] or y + h <= p['y'] or y >= p['y'] + p['h']):
            return True
    return False

def pack_shelf(wall_w, wall_h, items):
    placed_items, x, y, shelf_h = [], 0, 0, 0
    for item in sorted(items, key=lambda i: i['h'], reverse=True):
        if x + item['w'] > wall_w:
            y += shelf_h; x = 0; shelf_h = 0
        if y + item['h'] <= wall_h:
            placed_items.append({**item, 'x': x, 'y': y})
            x += item['w']; shelf_h = max(shelf_h, item['h'])
    return placed_items

def pack_columns(wall_w, wall_h, items):
    placed_items, x, y, col_w = [], 0, 0, 0
    for item in sorted(items, key=lambda i: i['w'], reverse=True):
        if y + item['h'] > wall_h:
            x += col_w; y = 0; col_w = 0
        if x + item['w'] <= wall_w:
            placed_items.append({**item, 'x': x, 'y': y})
            y += item['h']; col_w = max(col_w, item['w'])
    return placed_items

def pack_mondrian_cluster(wall_w, wall_h, items):
    placed_items = []
    
    # 1. Mischen und grob nach Größe sortieren (erzeugt den unregelmäßigen Mondrian-Look)
    shuffled_items = list(items)
    random.shuffle(shuffled_items) 
    mixed_items = sorted(shuffled_items, key=lambda i: (i['w'] * i['h']) * random.uniform(0.5, 1.5), reverse=True)
    
    step = 50 if wall_w <= 6000 else 100
    
    # 2. PHASE 1: Dichtes Zusammenpacken ("Bottom-Left-Fill")
    # Zwingt alle Fenster eng aneinander, um innere Lücken zu vermeiden.
    for item in mixed_items: 
        fitted = False
        for y in range(0, wall_h - item['h'] + 1, step):
            for x in range(0, wall_w - item['w'] + 1, step):
                if not check_overlap(x, y, item['w'], item['h'], placed_items):
                    placed_items.append({**item, 'x': x, 'y': y})
                    fitted = True; break
            if fitted: break
            
    # 3. PHASE 2: Zentrieren des Clusters (Der "Rahmen-Effekt")
    if placed_items:
        # Finde die äußersten Kanten des entstandenen Clusters
        max_x = max(p['x'] + p['w'] for p in placed_items)
        max_y = max(p['y'] + p['h'] for p in placed_items)
        
        # Berechne den Abstand, um den Cluster exakt in die Mitte zu schieben
        offset_x = (wall_w - max_x) // 2
        offset_y = (wall_h - max_y) // 2
        
        # Schiebe alle Fenster um diesen Offset
        for p in placed_items:
            p['x'] += offset_x
            p['y'] += offset_y
            
    return placed_items

# --- UI: SIDEBAR ---
with st.sidebar:
    st.header("1. Globale Suche")
    land = st.selectbox("Land", ["Deutschland", "Österreich", "Schweiz", "Liechtenstein"])
    plz = st.text_input("PLZ / Ort", "10115")
    radius = st.slider("Umkreis (km)", 0, 100, 50, 10)
    mix_new = st.checkbox("🔄 Fabrikneue Fenster beimischen", value=True)
    
    if st.button("🔍 Marktplätze durchsuchen", type="primary"):
        with st.spinner(f"Durchsuche Marktplätze in {land} ({plz})..."):
            st.session_state['inventory'] = harvest_materials(land, plz, radius, mix_new)
            st.session_state['is_loaded'] = True
        st.success(f"Bestände geladen!")

    st.divider()
    st.header("2. Eigenbestand")
    colA, colB = st.columns(2)
    with colA: cw_w = st.number_input("Breite (mm)", 300, 12000, 1000, step=50)
    with colB: cw_h = st.number_input("Höhe (mm)", 300, 12000, 1200, step=50)
    if st.button("➕ Hinzufügen"):
        st.session_state['custom_windows'].append({
            'w': int(cw_w), 'h': int(cw_h), 'type': 'Eigenbestand', 
            'color': '#90EE90', 'label': 'EIGEN', 'price': 0.0, 'source': 'Mein Lager',
            'condition': 'Eigenbestand', 'link': 'Lokal vorhanden'
        })
        st.success("Hinzugefügt!")
        
# --- UI: HAUPTBEREICH ---
if st.session_state['is_loaded'] or len(st.session_state['custom_windows']) > 0:
    total_inventory = st.session_state['custom_windows'] + st.session_state['inventory']
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader("Wandöffnung (bis 12m)")
        wall_width = st.slider("Breite (mm)", 1000, 12000, 4000, 100)
        wall_height = st.slider("Höhe (mm)", 1000, 12000, 3000, 100)
        
        st.subheader("Architektur-Stil")
        algo_choice = st.selectbox("Anordnung:", ["Mondrian-Cluster (Zentriert)", "Shelf-Packing (Reihen)", "Säulen-System (Spalten)"])
        
        if algo_choice == "Mondrian-Cluster (Zentriert)":
            if st.button("🎲 Neues Cluster würfeln"):
                pass 

    with col2:
        if algo_choice == "Mondrian-Cluster (Zentriert)": placed = pack_mondrian_cluster(wall_width, wall_height, total_inventory)
        elif algo_choice == "Shelf-Packing (Reihen)": placed = pack_shelf(wall_width, wall_height, total_inventory)
        else: placed = pack_columns(wall_width, wall_height, total_inventory)
            
        fig, ax = plt.subplots(figsize=(12, 8)) 
        ax.add_patch(patches.Rectangle((0, 0), wall_width, wall_height, facecolor='#ffcccc', hatch='//', edgecolor='red'))
        
        line_weight = 4 if algo_choice == "Mondrian-Cluster (Zentriert)" else 2
        used_area = 0
        
        for item in placed:
            ax.add_patch(patches.Rectangle((item['x'], item['y']), item['w'], item['h'], facecolor=item['color'], edgecolor='black', linewidth=line_weight))
            font_size = 6 if wall_width > 6000 else 8
            ax.text(item['x'] + item['w']/2, item['y'] + item['h']/2, f"{item['w']}x{item['h']}\n{item['condition'][:3]}", ha='center', va='center', fontsize=font_size)
            used_area += (item['w'] * item['h'])
            
        ax.set_xlim(0, max(wall_width, 4000) + 200)
        ax.set_ylim(0, max(wall_height, 3000) + 200)
        ax.set_aspect('equal')
        plt.axis('off')
        st.pyplot(fig)
        
        total_area = wall_width * wall_height
        st.info(f"Füllgrad: **{int((used_area/total_area)*100)}%** | Rahmen/Füllmaterial (rot): **{((total_area - used_area)/1000000):.2f} m²**")

    # --- MATRIX ---
    st.subheader("📋 Beschaffungs-Matrix")
    if len(placed) > 0:
        df_data = []
        total_price = 0
        for i, p in enumerate(placed):
            df_data.append({
                "Pos": i+1,
                "Zustand": p['condition'],
                "Maße (BxH)": f"{p['w']} x {p['h']}",
                "Herkunft / Titel": p['source'],
                "Preis (€)": p['price'],
                "Link": p['link']
            })
            total_price += p['price']
            
        df = pd.DataFrame(df_data)
        st.dataframe(
            df, 
            column_config={
                "Link": st.column_config.LinkColumn("🛒 Direkt zum Shop", display_text="Ansehen 🔗"),
                "Preis (€)": st.column_config.NumberColumn("Preis (€)", format="%.2f €")
            },
            hide_index=True,
            use_container_width=True
        )
        st.markdown(f"### 💶 Gesamtpreis der verwendeten Fenster: **{total_price:.2f} €**")

else:
    st.info("👈 Bitte wähle dein Land & PLZ und starte die Marktplatz-Suche!")
