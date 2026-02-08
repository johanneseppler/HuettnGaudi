import streamlit as st
import pandas as pd
import plotly.express as px

# --- KONFIGURATION ---
SHEET_ID = "1PD-YueUptrwj9z9hWCo8qq7rQjCU_mouFSbd-H4Vt3I"

# PayPal Mapping
PAYPAL_MAPPING = {
    "Johannes B": "epplerjo",
    "Fiona": "fiona.hahn@googlemail.com",
    "Filippos C": "filippos.chamoulias@googlemail.com"
}

st.set_page_config(page_title="Hüttn Gaudi 2026 Fontanella", layout="wide")
st.title("🏔️ Hüttn Gaudi 2026 Fontanella")

@st.cache_data(ttl=60)
def load_data():
    url_tn = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Teilnehmer"
    url_aus = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Ausgaben"
    return pd.read_csv(url_tn), pd.read_csv(url_aus)

def get_paypal_link(empfaenger_name, betrag):
    handle = PAYPAL_MAPPING.get(empfaenger_name)
    if not handle:
        return None
    betrag_str = f"{betrag:.2f}"
    reason = "Huettn Gaudi 2026"
    if "@" in handle:
        return f"https://www.paypal.com/cgi-bin/webscr?cmd=_xclick&business={handle}&amount={betrag_str}&currency_code=EUR&item_name={reason.replace(' ', '%20')}"
    else:
        clean_handle = handle.replace("@", "")
        return f"https://www.paypal.com/paypalme/{clean_handle}/{betrag_str}EUR"

try:
    df_tn, df_aus = load_data()
    df_tn['Name'] = df_tn['Name'].astype(str).str.strip()
    df_tn['Anzahlung'] = pd.to_numeric(df_tn['An_Filippos_gezahlt'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0) if 'An_Filippos_gezahlt' in df_tn.columns else 0.0

    def get_factor(name):
        return 0.5 if name in ["Anne", "Dani"] else 1.0

    weighted_total_days_unterkunft = sum(row['Tage'] * get_factor(row['Name']) for _, row in df_tn.iterrows())
    normal_total_days = df_tn['Tage'].sum()
    
    res = {n: {"paid_real": 0.0, "soll_t": 0.0, "soll_f": 0.0, "anzahlung": 0.0, "kat": {}} for n in df_tn['Name']}

    total_anzahlungen_an_filippos = sum(row['Anzahlung'] for _, row in df_tn.iterrows() if row['Name'] != "Filippos C")
    for _, row_tn in df_tn.iterrows():
        res[row_tn['Name']]['anzahlung'] = row_tn['Anzahlung']

    for i, row in df_aus.iterrows():
        try:
            val_raw = str(row['Betrag']).strip()
            if '.' in val_raw and ',' in val_raw: val_raw = val_raw.replace('.', '')
            b = float(val_raw.replace(',', '.'))
        except: continue
        zahler = str(row['Bezahlt_von']).strip()
        if zahler not in res: continue
        kat = str(row['Kategorie']).strip() if pd.notna(row['Kategorie']) else "Sonstiges"
        typ = str(row['Typ']).strip()
        res[zahler]['paid_real'] += b
        if typ == 'Tagesabhängig':
            for _, tn in df_tn.iterrows():
                t_name = tn['Name']
                curr_days = weighted_total_days_unterkunft if kat == "Unterkunft" else normal_total_days
                curr_fact = get_factor(t_name) if kat == "Unterkunft" else 1.0
                anteil = (b / curr_days) * (tn['Tage'] * curr_fact)
                res[t_name]['soll_t'] += anteil
                res[t_name]['kat'][kat] = res[t_name]['kat'].get(kat, 0) + anteil
        else:
            btn = df_tn['Name'].tolist() if "Alle" in str(row['Betroffene']) or pd.isna(row['Betroffene']) else [n.strip() for n in str(row['Betroffene']).split(',')]
            valid_btn = [p for p in btn if p in res]
            if valid_btn:
                anteil = b / len(valid_btn)
                for p in valid_btn:
                    res[p]['soll_f'] += anteil
                    res[p]['kat'][kat] = res[p]['kat'].get(kat, 0) + anteil

    summary = pd.DataFrame([{"Name": n, "Bons": d['paid_real'], "Anzahlung": d['anzahlung'] if n != "Filippos C" else 0.0, "Anteil": d['soll_t'] + d['soll_f'], "Saldo": (d['paid_real'] - total_anzahlungen_an_filippos - (d['soll_t'] + d['soll_f'])) if n == "Filippos C" else (d['paid_real'] + d['anzahlung'] - (d['soll_t'] + d['soll_f']))} for n, d in res.items()])
    
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
        grouped_payments = {}
        s_list, g_list = [dict(s) for s in schuldner], [dict(g) for g in glaubiger]
        s_i, g_i = 0, 0
        while s_i < len(s_list) and g_i < len(g_list):
            pay = min(abs(s_list[s_i]['Saldo']), g_list[g_i]['Saldo'])
            s_name = s_list[s_i]['Name']
            if s_name not in grouped_payments: grouped_payments[s_name] = []
            grouped_payments[s_name].append((g_list[g_i]['Name'], pay))
            s_list[s_i]['Saldo'] += pay
            g_list[g_i]['Saldo'] -= pay
            if abs(s_list[s_i]['Saldo']) < 0.01: s_i += 1
            if abs(g_list[g_i]['Saldo']) < 0.01: g_i += 1

        cols = st.columns(2)
        for i, (name, payments) in enumerate(grouped_payments.items()):
            with cols[i % 2]:
                # Start der blauen Kachel
                st.markdown(f"""
                <div style="background-color: #e1f5fe; padding: 20px; border-radius: 12px; border-left: 6px solid #0288d1; margin-bottom: 20px; min-height: 150px;">
                    <h3 style="margin: 0 0 10px 0; color: #01579b;">{name}</h3>
                    <p style="margin: 0 0 15px 0; font-weight: bold; color: #0288d1;">Gesamtschuld: {sum(amt for _, amt in payments):.2f} €</p>
                """, unsafe_allow_html=True)
                
                # Jede einzelne Zahlung innerhalb der Kachel mit Button
                for empf, amt in payments:
                    pp_link = get_paypal_link(empf, amt)
                    st.write(f"👉 **{amt:.2f} €** an **{empf}**")
                    if pp_link:
                        st.link_button(f"💸 PayPal: {amt:.2f}€ an {empf}", pp_link, use_container_width=True)
                    else:
                        st.caption(f"Kein PayPal-Konto für {empf} gefunden.")
                
                st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("📊 Persönliche Auswertung")
    user = st.selectbox("Wähle einen Namen:", summary['Name'].tolist())
    u_row = summary[summary['Name'] == user].iloc[0]
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"Saldo {user}", f"{u_row['Saldo']:.2f} €")
        st.write(f"Bons: {u_row['Bons']:.2f} € | Anzahlung: {u_row['Anzahlung']:.2f} €")
    with col2:
        if res[user]['kat']:
            st.plotly_chart(px.pie(values=list(res[user]['kat'].values()), names=list(res[user]['kat'].keys()), hole=0.4), use_container_width=True)

except Exception as e:
    st.error(f"Fehler: {e}")