import streamlit as st
import pandas as pd
import plotly.express as px

# --- KONFIGURATION ---
# Ersetze den Text unten durch deine ID aus der Browser-Zeile!
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
    
    # --- BERECHNUNG ---
    total_days = df_tn['Tage'].sum()
    res = {n: {"paid": 0.0, "soll_t": 0.0, "soll_f": 0.0, "kat": {}} for n in df_tn['Name']}

    for _, row in df_aus.iterrows():
        b, zahler, kat = row['Betrag'], row['Bezahlt_von'], row['Kategorie']
        if zahler in res: res[zahler]['paid'] += b
        
        if row['Typ'] == 'Tagesabhängig':
            for _, tn in df_tn.iterrows():
                anteil = (b / total_days) * tn['Tage']
                res[tn['Name']]['soll_t'] += anteil
                res[tn['Name']]['kat'][kat] = res[tn['Name']]['kat'].get(kat, 0) + anteil
        else: # Fixkosten
            btn = [n.strip() for n in str(row['Betroffene']).split(',')]
            if "Alle" in btn: btn = df_tn['Name'].tolist()
            anteil = b / len(btn)
            for p in btn:
                if p in res:
                    res[p]['soll_f'] += anteil
                    res[p]['kat'][kat] = res[p]['kat'].get(kat, 0) + anteil

    # --- ANZEIGE ---
    summary = pd.DataFrame([{"Name": n, "Gezahlt": d['paid'], "Anteil": d['soll_t']+d['soll_f'], "Saldo": d['paid']-(d['soll_t']+d['soll_f'])} for n, d in res.items()])
    st.subheader("💰 Salden")
    st.dataframe(summary.style.format(precision=2).applymap(lambda x: 'color:red' if x<0 else 'color:green', subset=['Saldo']), use_container_width=True)

    st.divider()
    user = st.selectbox("Details für:", df_tn['Name'])
    u = res[user]
    
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"### {user}")
        st.metric("Dein Saldo", f"{u['paid']-(u['soll_t']+u['soll_f']):.2f} €")
        fig = px.pie(values=list(u['kat'].values()), names=list(u['kat'].keys()), hole=0.4, title="Ausgaben-Mix")
        st.plotly_chart(fig)
    with c2:
        st.write("#### Aufschlüsselung")
        st.write(f"- Anteil Tage: {u['soll_t']:.2f} €")
        st.write(f"- Fixkosten: {u['soll_f']:.2f} €")

except Exception as e:
    st.error(f"Bitte prüfe dein Google Sheet: {e}")
    st.info("Hast du den Zugriff im Google Sheet auf 'Jeder mit dem Link' gestellt?")