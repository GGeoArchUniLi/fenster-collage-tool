import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import re
import random
from duckduckgo_search import DDGS

st.set_page_config(page_title="Re-Use Fassaden-Generator", layout="wide")
st.title("🧱 Patchwork-Fassaden-Generator V2")

# --- SESSION STATE ---
if 'inventory' not in st.session_state: st.session_state['inventory'] = []
if 'custom_windows' not in st.session_state: st.session_state['custom_windows'] = []
if 'is_loaded' not in st.session_state: st.session_state['is_loaded'] = False

# --- FUNKTION: Daten suchen inkl. Preise ---
def harvest_materials(plz, radius):
    materials = []
    # Fallschirm-Daten mit realistischen Preisen
    fallback_data = [
        (1200, 1400, 'Fenster', '#add8e6'), (800, 600, 'Kellerfenster', '#add8e6'),
        (2000, 2100, 'Terrassentür', '#add8e6'), (1000, 1000, 'Fenster', '#add8e6'),
        (500, 500, 'Fenster', '#add8e6'), (1000, 2000, 'Sandwichpaneel', '#808080')
    ]
    
    # Simuliere Suche (In einem echten Tool würde hier die eBay API mit PLZ/Radius laufen)
    for i in range(8): 
        for w, h, typ, color in fallback_data:
            # Wir würfeln einen realistischen Gebrauchtpreis (zw. 30€ und 250€)
            price = int((w * h) / 20000) + random.randint(10, 50) 
            materials.append({'w': w, 'h': h, 'type': typ, 'color': color, 'label': f'{typ[0]}', 'price': price, 'source': 'Websuche'})
            
    return materials

# --- ALGORITHMEN ---
def check_overlap(x, y, w, h, placed):
    for p in placed:
        # Wenn sich Rechtecke überschneiden, return True
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

def pack_mondrian(wall_w, wall_h, items):
    # Bottom-Left (Tetris) - Schmiegt sich in die kleinsten Lücken ein
    placed_items = []
    for item in sorted(items, key=lambda i: i['w']*i['h'], reverse=True): # Größte zuerst
        fitted = False
        # Scanne das Gitter in 5cm Schritten von unten nach oben, links nach rechts
        for y in range(0, wall_h - item['h'] + 1, 50):
            for x in range(0, wall_w - item['w'] + 1, 50):
                if not check_overlap(x, y, item['w'], item['h'], placed_items):
                    placed_items.append({**item, 'x': x, 'y': y})
                    fitted = True
                    break
            if fitted: break
    return placed_items

def pack_columns(wall_w, wall_h, items):
    # Baut Säulen (Spalten) von links nach rechts
    placed_items, x, y, col_w = [], 0, 0, 0
    for item in sorted(items, key=lambda i: i['w'], reverse=True):
        if y + item['h'] > wall_h:
            x += col_w; y = 0; col_w = 0
        if x + item['w'] <= wall_w:
            placed_items.append({**item, 'x': x, 'y': y})
            y += item['h']; col_w = max(col_w, item['w'])
    return placed_items

# --- UI: SIDEBAR (Einstellungen) ---
with st.sidebar:
    st.header("1. Materialsuche")
    plz = st.text_input("PLZ / Ort", "Berlin")
    radius = st.slider("Umkreis (km)", min_value=0, max_value=100, value=50, step=10)
    
    if st.button("🔍 Marktplätze durchsuchen", type="primary"):
        with st.spinner("Scanne Angebote..."):
            st.session_state['inventory'] = harvest_materials(plz, radius)
            st.session_state['is_loaded'] = True
        st.success(f"Gefunden!")

    st.divider()
    
    st.header("2. Eigene Fenster")
    st.caption("Hast du schon Fenster auf der Baustelle? Füge sie hier hinzu:")
    colA, colB = st.columns(2)
    with colA: cw_w = st.number_input("Breite (mm)", 300, 3000, 1000, step=50)
    with colB: cw_h = st.number_input("Höhe (mm)", 300, 3000, 1200, step=50)
    if st.button("➕ Hinzufügen"):
        st.session_state['custom_windows'].append({
            'w': int(cw_w), 'h': int(cw_h), 'type': 'Eigenbestand', 
            'color': '#90EE90', 'label': 'EIGEN', 'price': 0.0, 'source': 'Mein Lager'
        })
        st.success("Hinzugefügt!")
        
    if len(st.session_state['custom_windows']) > 0:
        st.write(f"Du hast {len(st.session_state['custom_windows'])} eigene(s) Fenster im Lager.")

# --- UI: HAUPTBEREICH (Design) ---
if st.session_state['is_loaded'] or len(st.session_state['custom_windows']) > 0:
    
    # Zusammenführen: Gefundene + Eigene Fenster
    total_inventory = st.session_state['custom_windows'] + st.session_state['inventory']
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader("Wandöffnung")
        wall_width = st.slider("Breite (mm)", 1000, 6000, 3000, 100)
        wall_height = st.slider("Höhe (mm)", 1000, 4000, 2500, 100)
        
        st.subheader("Design-Stil")
        algo_choice = st.selectbox("Wie sollen die Fenster angeordnet werden?", 
                                   ["Mondrian-Style (Verschachtelt)", "Shelf-Packing (Reihen)", "Säulen-System (Spalten)"])

    with col2:
        # Algorithmus auswählen
        if algo_choice == "Mondrian-Style (Verschachtelt)":
            placed = pack_mondrian(wall_width, wall_height, total_inventory)
        elif algo_choice == "Shelf-Packing (Reihen)":
            placed = pack_shelf(wall_width, wall_height, total_inventory)
        else:
            placed = pack_columns(wall_width, wall_height, total_inventory)
            
        # Zeichnen
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.add_patch(patches.Rectangle((0, 0), wall_width, wall_height, facecolor='#ffcccc', hatch='//', edgecolor='red'))
        
        used_area = 0
        for item in placed:
            ax.add_patch(patches.Rectangle((item['x'], item['y']), item['w'], item['h'], facecolor=item['color'], edgecolor='black', linewidth=2))
            # Text in die Mitte des Fensters
            ax.text(item['x'] + item['w']/2, item['y'] + item['h']/2, f"{item['w']}x{item['h']}", ha='center', va='center', fontsize=7)
            used_area += (item['w'] * item['h'])
            
        ax.set_xlim(0, max(wall_width, 4000) + 100)
        ax.set_ylim(0, max(wall_height, 3000) + 100)
        ax.set_aspect('equal')
        plt.axis('off')
        st.pyplot(fig)
        
        total_area = wall_width * wall_height
        st.info(f"Füllgrad: **{int((used_area/total_area)*100)}%** | Benötigtes Füllmaterial (rot): **{((total_area - used_area)/1000000):.2f} m²**")

    # --- TABELLE & PREISE ---
    st.subheader("📋 Stückliste & Kosten")
    if len(placed) > 0:
        # Daten für die Tabelle aufbereiten
        df_data = []
        total_price = 0
        for i, p in enumerate(placed):
            df_data.append({
                "Position": i+1,
                "Typ": p['type'],
                "Maße (BxH)": f"{p['w']} x {p['h']} mm",
                "Herkunft": p['source'],
                "Preis (€)": p['price']
            })
            total_price += p['price']
            
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        st.markdown(f"### 💶 Gesamtpreis der Fenster: **{total_price:.2f} €**")
    else:
        st.warning("Keine Fenster platziert. Mach die Wand größer oder suche nach kleineren Fenstern.")

else:
    st.info("👈 Bitte starte links in der Seitenleiste die Materialsuche oder füge eigene Fenster hinzu!")
