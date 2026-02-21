import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import re
from duckduckgo_search import DDGS

# --- SEITEN-SETUP ---
st.set_page_config(page_title="Re-Use Fassaden-Generator", layout="wide")
st.title("🧱 Patchwork-Fassaden-Generator")
st.markdown("Zieh am Schieberegler, um die Wandgröße zu ändern. Das Tool füllt die Lücke automatisch mit gesammelten Materialien!")

# --- SESSION STATE (Speicher) ---
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = []
if 'is_loaded' not in st.session_state:
    st.session_state['is_loaded'] = False

# --- FUNKTION: Daten im Web suchen ---
def harvest_materials():
    materials = []
    
    # 1. Wir simulieren hier eine Suche mit DuckDuckGo
    # (Eingebauter Fallschirm: Wenn DDG blockiert, generieren wir realistische Re-Use Daten)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text("Fenster Restposten mm gebraucht", max_results=20))
            # Simpler Regex, um Maße wie "1200x1400" zu finden
            for res in results:
                match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', res['title'] + " " + res['body'])
                if match:
                    w, h = int(match.group(1)), int(match.group(2))
                    if 300 <= w <= 2500 and 300 <= h <= 2500: # Filter für realistische Maße
                        materials.append({'w': w, 'h': h, 'type': 'Fenster', 'color': '#add8e6', 'label': f'F (DDG)'})
    except Exception as e:
        pass # Falls DDG blockt, geht es nahtlos mit den Fallschirm-Daten weiter

    # 2. Fallschirm / Basis-Datenbestand (damit das Tool immer was zum Puzzeln hat)
    fallback_data = [
        (1200, 1400, 'Fenster', '#add8e6'), (800, 600, 'Kellerfenster', '#add8e6'),
        (2000, 2100, 'Terrassentür', '#add8e6'), (1000, 1000, 'Fenster', '#add8e6'),
        (500, 500, 'Fenster', '#add8e6'), (1000, 2000, 'Sandwichpaneel', '#808080'),
        (1250, 2500, 'Holzplatte', '#8b4513'), (600, 1200, 'HPL Platte', '#696969')
    ]
    # Wir vervielfältigen die Basis-Daten etwas, damit wir ein volles Lager haben
    for i in range(5): 
        for w, h, typ, color in fallback_data:
            materials.append({'w': w, 'h': h, 'type': typ, 'color': color, 'label': f'{typ[0]}'})
            
    return materials

# --- FUNKTION: Der Packing Algorithmus (Shelf Packing) ---
def pack_items(wall_w, wall_h, items):
    # Sortiere größte Objekte (Höhe) zuerst
    sorted_items = sorted(items, key=lambda x: x['h'], reverse=True)
    placed_items = []
    x, y, shelf_h = 0, 0, 0
    
    for item in sorted_items:
        # Prüfen, ob wir eine neue "Reihe" (Shelf) anfangen müssen
        if x + item['w'] > wall_w:
            y += shelf_h
            x = 0
            shelf_h = 0
            
        # Prüfen, ob es in der Höhe noch in die Wand passt
        if y + item['h'] <= wall_h:
            placed_items.append({
                'x': x, 'y': y, 'w': item['w'], 'h': item['h'], 
                'color': item['color'], 'label': item['label'], 'type': item['type']
            })
            x += item['w']
            shelf_h = max(shelf_h, item['h'])
            
    return placed_items

# --- UI: Such-Button ---
if not st.session_state['is_loaded']:
    if st.button("🔍 Internet nach Baumaterial durchsuchen (Lager füllen)", type="primary"):
        with st.spinner("Suche auf Marktplätzen..."):
            st.session_state['inventory'] = harvest_materials()
            st.session_state['is_loaded'] = True
        st.rerun()

# --- UI: Der Live-Designer (erscheint erst nach der Suche) ---
if st.session_state['is_loaded']:
    st.success(f"Lager gefüllt! {len(st.session_state['inventory'])} Bauteile gefunden. Zieh jetzt an den Reglern!")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Wandöffnung")
        wall_width = st.slider("Breite (mm)", min_value=1000, max_value=6000, value=3000, step=100)
        wall_height = st.slider("Höhe (mm)", min_value=1000, max_value=4000, value=2500, step=100)
        
        if st.button("Lager leeren & Neu suchen"):
            st.session_state['is_loaded'] = False
            st.rerun()

    with col2:
        # Puzzeln berechnen
        placed = pack_items(wall_width, wall_height, st.session_state['inventory'])
        
        # Zeichnen (Matplotlib)
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Hintergrund (Die Wand / Rote Lücken)
        ax.add_patch(patches.Rectangle((0, 0), wall_width, wall_height, facecolor='#ffcccc', hatch='//', edgecolor='red'))
        
        used_area = 0
        # Die platzierten Fenster zeichnen
        for item in placed:
            ax.add_patch(patches.Rectangle((item['x'], item['y']), item['w'], item['h'], facecolor=item['color'], edgecolor='black', linewidth=2))
            ax.text(item['x'] + item['w']/2, item['y'] + item['h']/2, item['label'], ha='center', va='center', fontsize=8, color='black')
            used_area += (item['w'] * item['h'])
            
        ax.set_xlim(0, max(wall_width + 200, 4000))
        ax.set_ylim(0, max(wall_height + 200, 3000))
        ax.set_aspect('equal')
        plt.axis('off')
        
        st.pyplot(fig)
        
        # Statistik
        total_area = wall_width * wall_height
        st.info(f"Füllgrad: **{int((used_area/total_area)*100)}%** | Benötigtes Füllmaterial (rote Schraffur): **{((total_area - used_area)/1000000):.2f} m²**")
