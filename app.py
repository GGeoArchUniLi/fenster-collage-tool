import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import re
import random
from duckduckgo_search import DDGS

st.set_page_config(page_title="Re-Use Fassaden-Generator", layout="wide")
st.title("🧱 Patchwork-Fassaden-Generator V3 (Pro)")

# --- SESSION STATE ---
if 'inventory' not in st.session_state: st.session_state['inventory'] = []
if 'custom_windows' not in st.session_state: st.session_state['custom_windows'] = []
if 'is_loaded' not in st.session_state: st.session_state['is_loaded'] = False

# --- FUNKTION: Echte Daten & Links suchen ---
def harvest_materials(land, plz, radius, mix_new):
    materials = []
    
    # Suchanfragen definieren (Gebraucht + optional Neu)
    queries = [
        (f"site:ebay.de OR site:kleinanzeigen.de Fenster gebraucht {plz} {land}", "Gebraucht (Re-Use)", '#4682b4') # Dunkleres Blau für Alt
    ]
    if mix_new:
        queries.append((f"Fenster neu kaufen {plz} {land}", "Fabrikneu", '#add8e6')) # Helles Blau für Neu
        
    # Suche ausführen
    for query, condition, color in queries:
        try:
            with DDGS() as ddgs:
                # Wir holen mehr Ergebnisse (max 25 pro Kategorie)
                results = list(ddgs.text(query, max_results=25))
                for res in results:
                    text_to_search = res['title'] + " " + res['body']
                    
                    # 1. Maße extrahieren (z.B. 1200x1400)
                    match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', text_to_search)
                    if match:
                        w, h = int(match.group(1)), int(match.group(2))
                        
                        # 2. Preis extrahieren (sucht nach Zahlen vor einem € Zeichen)
                        price_match = re.search(r'(\d{1,5})[.,]?\d*\s*[€|EUR]', text_to_search)
                        if price_match:
                            price = float(price_match.group(1))
                        else:
                            # Falls kein Preis im Text steht, schätzen wir realistisch
                            price = float(int((w * h) / 20000) + random.randint(10, 50))

                        # 3. Filter: Passt es in unsere maximalen Dimensionen (bis 12m)?
                        if 300 <= w <= 12000 and 300 <= h <= 12000:
                            materials.append({
                                'w': w, 'h': h, 
                                'type': 'Fenster', 
                                'color': color, 
                                'label': f"F ({'Neu' if condition == 'Fabrikneu' else 'Alt'})", 
                                'price': price, 
                                'source': res['title'][:30] + '...', # Gekürzter Titel
                                'condition': condition,
                                'link': res['href'] # Der ECHTE Shop-Link!
                            })
        except Exception as e:
            pass # Ignorieren bei Such-Fehlern
            
    # --- FALLSCHIRM ---
    # Falls das Internet/API blockiert, laden wir ein paar Dummy-Daten, damit die App nicht abstürzt
    if len(materials) < 5:
        fallback = [
            (1200, 1400, "Gebraucht (Re-Use)", "https://ebay.de", 85.0),
            (2000, 2100, "Fabrikneu", "https://amazon.de", 350.0),
            (800, 600, "Gebraucht (Re-Use)", "https://kleinanzeigen.de", 40.0)
        ]
        for w, h, cond, lnk, pr in fallback * 5:
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

def pack_mondrian(wall_w, wall_h, items):
    placed_items = []
    for item in sorted(items, key=lambda i: i['w']*i['h'], reverse=True): 
        fitted = False
        # Für sehr große Wände (12m) erhöhen wir die Schrittweite auf 100mm für die Performance
        step = 50 if wall_w <= 6000 else 100
        for y in range(0, wall_h - item['h'] + 1, step):
            for x in range(0, wall_w - item['w'] + 1, step):
                if not check_overlap(x, y, item['w'], item['h'], placed_items):
                    placed_items.append({**item, 'x': x, 'y': y})
                    fitted = True
                    break
            if fitted: break
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

# --- UI: SIDEBAR ---
with st.sidebar:
    st.header("1. Globale Suche")
    land = st.selectbox("Land", ["Deutschland", "Österreich", "Schweiz", "Liechtenstein"])
    plz = st.text_input("PLZ / Ort", "10115")
    radius = st.slider("Umkreis (km)", 0, 100, 50, 10)
    
    mix_new = st.checkbox("🔄 Fabrikneue Fenster beimischen", value=True, help="Kombiniert Re-Use mit günstiger Neuware, falls nicht genug Altbestand da ist.")
    
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
        # MAX VALUE auf 12.000 (12 Meter) angehoben!
        wall_width = st.slider("Breite (mm)", 1000, 12000, 4000, 100)
        wall_height = st.slider("Höhe (mm)", 1000, 12000, 3000, 100)
        
        st.subheader("Architektur-Stil")
        algo_choice = st.selectbox("Anordnung:", ["Mondrian-Style (Verschachtelt)", "Shelf-Packing (Reihen)", "Säulen-System (Spalten)"])

    with col2:
        if algo_choice == "Mondrian-Style (Verschachtelt)": placed = pack_mondrian(wall_width, wall_height, total_inventory)
        elif algo_choice == "Shelf-Packing (Reihen)": placed = pack_shelf(wall_width, wall_height, total_inventory)
        else: placed = pack_columns(wall_width, wall_height, total_inventory)
            
        # Zeichnen
        fig, ax = plt.subplots(figsize=(12, 8)) # Größeres Canvas für bis zu 12m
        ax.add_patch(patches.Rectangle((0, 0), wall_width, wall_height, facecolor='#ffcccc', hatch='//', edgecolor='red'))
        
        used_area = 0
        for item in placed:
            ax.add_patch(patches.Rectangle((item['x'], item['y']), item['w'], item['h'], facecolor=item['color'], edgecolor='black', linewidth=2))
            # Text anpassen, damit er bei riesigen Wänden lesbar bleibt
            font_size = 6 if wall_width > 6000 else 8
            ax.text(item['x'] + item['w']/2, item['y'] + item['h']/2, f"{item['w']}x{item['h']}\n{item['condition'][:3]}", ha='center', va='center', fontsize=font_size)
            used_area += (item['w'] * item['h'])
            
        ax.set_xlim(0, max(wall_width, 4000) + 200)
        ax.set_ylim(0, max(wall_height, 3000) + 200)
        ax.set_aspect('equal')
        plt.axis('off')
        st.pyplot(fig)
        
        total_area = wall_width * wall_height
        st.info(f"Füllgrad: **{int((used_area/total_area)*100)}%** | Benötigtes Füllmaterial (rot): **{((total_area - used_area)/1000000):.2f} m²**")

    # --- MATRIX MIT KLICKBAREN LINKS ---
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
        
        # Streamlit Column Config macht die Links klickbar!
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
