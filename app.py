import streamlit as st
import pandas as pd
import plotly.express as px

# --- KONFIGURATION ---
SHEET_ID = "1PD-YueUptrwj9z9hWCo8qq7rQjCU_mouFSbd-H4Vt3I"

# PAYPAL MAPPING
# Sobald du die Namen hast, trage sie einfach zwischen die "" ein.
PAYPAL_MAPPING = {
    "Johannes B": "epplerjo",
    "Fiona": "",           # Hier später den PayPal.me Namen eintragen
    "Filippos C": ""       # Hier später den PayPal.me Namen eintragen
}

st.set_page_config(page_title="Hüttn Gaudi 2026 Fontanella", layout="wide")

# CSS für die Kacheln
st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] > div[style*="border: 1px solid"] {
        background-color: #e1f5fe !important;
        border-left: 10px solid #0288d1 !important;
        border-radius: 12px !important;
        padding: 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏔️ Hüttn Gaudi 2026 Fontanella")

@st.cache_data(ttl=60)
def load_data():
    url_tn = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Teilnehmer"
    url_aus = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Ausgaben"
    return pd.read_csv(url_tn), pd.read_csv(url_aus)

def get_paypal_link(empfaenger_name, betrag):
    handle = PAYPAL_MAPPING.get(empfaenger_name)
    # Nur Link erstellen, wenn ein Name hinterlegt ist (nicht leer)
    if not handle or handle.strip() == "":
        return None
    return f"https://www.paypal.com/paypalme/{handle}/{betrag:.2f}EUR"

try:
    df_tn, df_aus = load_data()
    df_tn['Name'] = df_tn['Name'].astype(str).str.strip()
    
    if 'An_Filippos_gezahlt' in df_tn.columns:
        df_tn['Anzahlung'] = pd.to_numeric(df_tn['An_Filippos_gezahlt'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
    else:
        df_tn['Anzahlung'] = 0.0

    def get_factor(name): return 0.5 if name in ["Anne", "Dani"] else 1.0
    weighted_days_unterkunft = sum(row['Tage'] * get_factor(row['Name']) for _, row in df_tn.iterrows())
    total_days_normal = df_tn['Tage'].sum()
    
    res = {n: {"paid_real": 0.0, "soll_t": 0.0, "soll_f": 0.0, "anzahlung": 0.0, "kat": {}} for n in df_tn['Name']}
    
    total_anz_filippos = 0.0
    for _, row_tn in df_tn.iterrows():
        n = row_tn['Name']
        res[n]['anzahlung'] = row_tn['Anzahlung']
        if n != "Filippos C":
            total_anz_filippos += row_tn['Anzahlung']

    for _, row in df_aus.iterrows():
        try:
            val_raw = str(row['Betrag']).replace('.', '').replace(',', '.')
            b = float(val_raw)
        except: continue
        zahler = str(row['Bezahlt_von']).strip()
        if zahler not in res: continue
        kat, typ = str(row['Kategorie']).strip(), str(row['Typ']).strip()
        res[zahler]['paid_real'] += b
        if typ == 'Tagesabhängig':
            for _, tn in df_tn.iterrows():
                t_n = tn['Name']
                curr_days = weighted_days_unterkunft if kat == "Unterkunft" else total_days_normal
                curr_fact = get_factor(t_n) if kat == "Unterkunft" else 1.0
                anteil = (b / curr_days) * (tn['Tage'] * curr_fact)
                res[t_n]['soll_t'] += anteil
                res[t_n]['kat'][kat] = res[t_n]['kat'].get(kat, 0) + anteil
        else:
            btn_raw = str(row['Betroffene'])
            btn = df_tn['Name'].tolist() if "Alle" in btn_raw or pd.isna(row['Betroffene']) else [n.strip() for n in btn_raw.split(',')]
            valid_btn = [p for p in btn if p in res]
            if valid_btn:
                anteil = b / len(valid_btn)
                for p in valid_btn:
                    res[p]['soll_f'] += anteil
                    res[p]['kat'][kat] = res[p]['kat'].get(kat, 0) + anteil

    summary_data = []
    for n, d in res.items():
        anteil_kosten = d['soll_t'] + d['soll_f']
        saldo = (d['paid_real'] - total_anz_filippos - anteil_kosten) if n == "Filippos C" else (d['paid_real'] + d['anzahlung'] - anteil_kosten)
        summary_data.append({"Name": n, "Bons": d['paid_real'], "Anzahlung": d['anzahlung'] if n != "Filippos C" else 0.0, "Anteil": anteil_kosten, "Saldo": saldo})
    
    summary = pd.DataFrame(summary_data)

    st.subheader("💰 Salden-Tabelle")
    st.dataframe(summary.style.format(precision=2).applymap(lambda x: 'color:red' if x < -0.01 else 'color:green' if x > 0.01 else 'color:gray', subset=['Saldo']), use_container_width=True)

    st.divider()
    st.subheader("💳 Zahlungsanweisungen")
    
    schuldner = summary[summary['Saldo'] < -0.01].copy().to_dict('records')
    glaubiger = summary[summary['Saldo'] > 0.01].copy().to_dict('records')
    schuldner.sort(key=lambda x: x['Saldo'])
    glaubiger.sort(key=lambda x: x['Saldo'], reverse=True)

    if not schuldner:
        st.success("✅ Alles ausgeglichen!")
    else:
        grouped = {}
        s_list, g_list = [dict(s) for s in schuldner], [dict(g) for g in glaubiger]
        s_i, g_i = 0, 0
        while s_i < len(s_list) and g_i < len(g_list):
            pay = min(abs(s_list[s_i]['Saldo']), g_list[g_i]['Saldo'])
            name = s_list[s_i]['Name']
            if name not in grouped: grouped[name] = []
            grouped[name].append((g_list[g_i]['Name'], pay))
            s_list[s_i]['Saldo'] += pay
            g_list[g_i]['Saldo'] -= pay
            if abs(s_list[s_i]['Saldo']) < 0.01: s_i += 1
            if abs(g_list[g_i]['Saldo']) < 0.01: g_i += 1

        for name, payments in grouped.items():
            with st.container(border=True):
                st.markdown(f"### 👤 {name}")
                st.write(f"Gesamtschuld: **{sum(p[1] for p in payments):.2f} €**")
                for empf, amt in payments:
                    c1, c2 = st.columns([2, 1])
                    c1.write(f"👉 **{amt:.2f} €** an {empf}")
                    pp_url = get_paypal_link(empf, amt)
                    if pp_url:
                        c2.link_button(f"Freunde & Familie 💸", pp_url, use_container_width=True)
                    else:
                        # Wenn kein Link da ist, zeigen wir eine kleine Info an
                        c2.caption("Kein PayPal-Link hinterlegt")

    st.divider()
    st.subheader("📊 Details pro Person")
    sel = st.selectbox("Name auswählen:", summary['Name'].tolist())
    row = summary[summary['Name'] == sel].iloc[0]
    if res[sel]['kat']:
        st.plotly_chart(px.pie(values=list(res[sel]['kat'].values()), names=list(res[sel]['kat'].keys()), hole=0.4, height=300, title=f"Kosten-Mix von {sel}"), use_container_width=True)

except Exception as e:
    st.error(f"Fehler: {e}")