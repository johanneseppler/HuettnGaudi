import streamlit as st
import pandas as pd
import plotly.express as px

# --- KONFIGURATION ---
# Deine Sheet ID (hast du ja bereits eingetragen)
SHEET_ID = "1PD-YueUptrwj9z9hWCo8qq7rQjCU_mouFSbd-H4Vt3I"

st.set_page_config(page_title="Hüttn Gaudi 2026 Fontanella", layout="wide")
st.title("🏔️ Hüttn Gaudi 2026 Fontanella")

@st.cache_data(ttl=60) # Aktualisiert alle 60 Sekunden bei Refresh
def load_data():
    url_tn = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Teilnehmer"
    url_aus = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Ausgaben"
    return pd.read_csv(url_tn), pd.read_csv(url_aus)

try:
    df_tn, df_aus = load_data()
    
    # --- BERECHNUNG VORBEREITEN ---
    total_days = df_tn['Tage'].sum()
    # Wir erstellen ein Wörterbuch für alle Teilnehmer
    res = {n: {"paid": 0.0, "soll_t": 0.0, "soll_f": 0.0, "kat": {}} for n in df_tn['Name']}

    # --- DATEN VERARBEITEN ---
    for _, row in df_aus.iterrows():
        # ROBUST: Betrag umwandeln (Komma zu Punkt, falls nötig)
        try:
            val_str = str(row['Betrag']).replace(',', '.')
            b = float(val_str)
        except:
            continue # Zeile überspringen, wenn kein gültiger Betrag da ist

        zahler = row['Bezahlt_von']
        kat = row['Kategorie'] if pd.notna(row['Kategorie']) else "Sonstiges"
        typ = row['Typ']
        
        # 1. Wer hat gezahlt? (Nur addieren, wenn Name in Teilnehmerliste existiert)
        if zahler in res:
            res[zahler]['paid'] += b
        
        # 2. Wer muss dafür bezahlen? (Schulden verteilen)
        if typ == 'Tagesabhängig':
            for _, tn in df_tn.iterrows():
                anteil = (b / total_days) * tn['Tage']
                res[tn['Name']]['soll_t'] += anteil
                res[tn['Name']]['kat'][kat] = res[tn['Name']]['kat'].get(kat, 0) + anteil
        else: # Fixkosten
            betroffene_raw = str(row['Betroffene'])
            if "Alle" in betroffene_raw or pd.isna(row['Betroffene']):
                btn = df_tn['Name'].tolist()
            else:
                btn = [n.strip() for n in betroffene_raw.split(',')]
            
            # Nur Teilnehmer zählen, die auch wirklich in der Liste stehen
            valid_btn = [p for p in btn if p in res]
            if valid_btn:
                anteil = b / len(valid_btn)
                for p in valid_btn:
                    res[p]['soll_f'] += anteil
                    res[p]['kat'][kat] = res[p]['kat'].get(kat, 0) + anteil

    # --- ANZEIGE: SALDEN-TABELLE ---
    summary_data = []
    for n, d in res.items():
        gezahlt = d['paid']
        soll = d['soll_t'] + d['soll_f']
        summary_data.append({
            "Name": n, 
            "Gezahlt": gezahlt, 
            "Anteil": soll, 
            "Saldo": gezahlt - soll
        })
    
    summary = pd.DataFrame(summary_data)
    
    st.subheader("💰 Wer schuldet wem was?")
    st.dataframe(
        summary.style.format(precision=2)
        .applymap(lambda x: 'color:red' if x < -0.01 else 'color:green' if x > 0.01 else 'color:gray', subset=['Saldo']), 
        use_container_width=True
    )

    st.divider()

    # --- DETAILS PRO PERSON ---
    user = st.selectbox("Persönliche Abrechnung für:", df_tn['Name'])
    u = res[user]
    
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"### Übersicht: {user}")
        saldo = u['paid'] - (u['soll_t'] + u['soll_f'])
        st.metric("Dein Saldo", f"{saldo:.2f} €")
        
        if u['kat']:
            fig = px.pie(
                values=list(u['kat'].values()), 
                names=list(u['kat'].keys()), 
                hole=0.4, 
                title="Wofür du bezahlst (Anteilig)"
            )
            st.plotly_chart(fig)
        else:
            st.info("Noch keine Ausgaben für diesen Nutzer gefunden.")

    with c2:
        st.write("#### Aufschlüsselung der Kosten")
        st.write(f"**Gesamt-Anteil:** {(u['soll_t'] + u['soll_f']):.2f} €")
        st.write(f"- Davon tagesabhängig (Essen/Strom): {u['soll_t']:.2f} €")
        st.write(f"- Davon Fixkosten (Miete/Sonstiges): {u['soll_f']:.2f} €")
        st.progress(min(1.0, u['soll_t'] / (u['soll_t'] + u['soll_f'] + 0.1)), text="Verhältnis Tageskosten zu Fixkosten")

except Exception as e:
    st.error(f"Fehler beim Laden der Daten: {e}")
    st.info("Checkliste:\n1. Google Sheet ist auf 'Jeder mit dem Link kann lesen' gestellt.\n2. Reiter heißen 'Teilnehmer' und 'Ausgaben'.\n3. Spaltennamen sind korrekt.")