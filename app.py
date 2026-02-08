import streamlit as st
import pandas as pd
import plotly.express as px

# --- KONFIGURATION ---
SHEET_ID = "1PD-YueUptrwj9z9hWCo8qq7rQjCU_mouFSbd-H4Vt3I"

PAYPAL_MAPPING = {
    "Johannes B": "epplerjo",
    "Fiona": "fiona.hahn@googlemail.com",
    "Filippos C": "filippos.chamoulias@googlemail.com"
}

st.set_page_config(page_title="Hüttn Gaudi 2026 Fontanella", layout="wide")

# CSS für echtes "Hüttn-Blau" und Kachel-Optik
st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] > div[style*="border: 1px solid"] {
        background-color: #e1f5fe !important;
        border-left: 10px solid #0288d1 !important;
        border-radius: 15px !important;
        padding: 20px !important;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
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
    if not handle: return None
    betrag_str = f"{betrag:.2f}"
    reason = "Huettn Gaudi 2026"
    if "@" in handle:
        return f"https://www.paypal.com/cgi-bin/webscr?cmd=_xclick&business={handle}&amount={betrag_str}&currency_code=EUR&item_name={reason.replace(' ', '%20')}"
    else:
        return f"https://www.paypal.com/paypalme/{handle.replace('@', '')}/{betrag_str}EUR"

try:
    df_tn, df_aus = load_data()
    df_tn['Name'] = df_tn['Name'].astype(str).str.strip()
    
    # Anzahlungen
    if 'An_Filippos_gezahlt' in df_tn.columns:
        df_tn['Anzahlung'] = pd.to_numeric(df_tn['An_Filippos_gezahlt'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
    else:
        df_tn['Anzahlung'] = 0.0

    # Faktoren für Anne & Dani
    def get_factor(name): return 0.5 if name in ["Anne", "Dani"] else 1.0
    
    weighted_days_unterkunft = sum(row['Tage'] * get_factor(row['Name']) for _, row in df_tn.iterrows())
    total_days_normal = df_tn['Tage'].sum()
    
    res = {n: {"paid_real": 0.0, "soll_t": 0.0, "soll_f": 0.0, "anzahlung": 0.0, "kat": {}} for n in df_tn['Name']}
    total_anz_filippos = sum(row['Anzahlung'] for _, row in df_tn.iterrows() if row['Name'] != "Filippos C")

    for _, row in df_aus.iterrows():
        try:
            b = float(str(row['Betrag']).replace('.', '').replace(',', '.'))
        except: continue
        zahler = str(row['Bezahlt_von']).strip()
        if zahler not in res: continue
        kat, typ = str(row['Kategorie']).strip(), str(row['Typ']).strip()
        res[zahler]['paid_real'] += b
        
        if typ == 'Tagesabhängig':
            for _, tn in df_tn.iterrows():
                t_name = tn['Name']
                w_days = weighted_days_unterkunft if kat == "Unterkunft" else total_days_normal
                fact = get_factor(t_name) if kat == "Unterkunft" else 1.0
                anteil = (b / w_days) * (tn['Tage'] * fact)
                res[t_name]['soll_t'] += anteil
                res[t_name]['kat'][kat] = res[t_name]['kat'].get(kat, 0) + anteil
        else:
            btn_raw = str(row['Betroffene'])
            btn = df_tn['Name'].tolist() if "Alle" in btn_raw or pd.isna(row['Betroffene']) else [n.strip() for n in btn_raw.split(',')]
            valid_btn = [p for p in btn if p in res]
            if valid_btn:
                anteil = b / len(valid_btn)
                for p in valid_btn:
                    res[p]['soll_f'] += anteil
                    res[p]['kat'][kat] = res[p]['kat'].get(kat, 0) + anteil

    # Salden Berechnung
    summary_list = []
    for n, d in res.items():
        anteil = d['soll_t'] + d['soll_f']
        saldo = (d['paid_real'] - total_anz_filippos - anteil) if n == "Filippos C" else (d['paid_real'] + d['anzahlung'] - anteil)
        summary_list.append({"Name": n, "Saldo": saldo, "Bons": d['paid_real'], "Anzahlung": d['anzahlung'] if n != "Filippos C" else 0.0, "Anteil": anteil})
    
    summary = pd.DataFrame(summary_list)

    st.subheader("💰 Salden-Übersicht")
    st.dataframe(summary[["Name", "Saldo"]].set_index("Name").style.format(precision=2), use_container_width=True)

    st.divider()
    st.subheader("💳 Wer zahlt an wen?")

    # Settlement Logik
    schuldner = summary[summary['Saldo'] < -0.01].sort_values('Saldo').to_dict('records')
    glaubiger = summary[summary['Saldo'] > 0.01].sort_values('Saldo', ascending=False).to_dict('records')

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

        # Anzeige in einem Grid, das nicht abschneidet
        for name, payments in grouped.items():
            with st.container(border=True):
                col_head, col_total = st.columns([2, 1])
                col_head.markdown(f"### 👤 {name}")
                total_pay = sum(p[1] for p in payments)
                col_total.markdown(f"**Gesamt: {total_pay:.2f} €**")
                
                st.write("Bitte überweise folgende Beträge:")
                for empf, amt in payments:
                    c1, c2 = st.columns([2, 1])
                    c1.write(f"💵 **{amt:.2f} €** an {empf}")
                    pp_url = get_paypal_link(empf, amt)
                    if pp_url:
                        c2.link_button(f"PayPal 💸", pp_url, use_container_width=True)
                    else:
                        c2.caption("Kein PayPal hinterlegt")

    st.divider()
    st.subheader("📊 Details pro Person")
    sel = st.selectbox("Wähle Teilnehmer:", summary['Name'].tolist())
    row = summary[summary['Name'] == sel].iloc[0]
    
    c1, c2 = st.columns(2)
    c1.metric("Dein Saldo", f"{row['Saldo']:.2f} €")
    c1.write(f"Bons: {row['Bons']:.2f} € | Anzahlung: {row['Anzahlung']:.2f} €")
    if res[sel]['kat']:
        with c2:
            st.plotly_chart(px.pie(values=list(res[sel]['kat'].values()), names=list(res[sel]['kat'].keys()), hole=0.4, height=300), use_container_width=True)

except Exception as e:
    st.error(f"Fehler: {e}")