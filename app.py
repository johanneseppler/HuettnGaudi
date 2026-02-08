import streamlit as st
import pandas as pd
import plotly.express as px

# --- KONFIGURATION ---
SHEET_ID = "1PD-YueUptrwj9z9hWCo8qq7rQjCU_mouFSbd-H4Vt3I"

# PayPal Mapping (Namen müssen exakt wie im Sheet geschrieben sein)
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
    # Betreff für die Zahlung
    reason = "Huettn Gaudi 2026"
    
    if "@" in handle: # E-Mail Adressen (Klassischer Link)
        return f"https://www.paypal.com/cgi-bin/webscr?cmd=_xclick&business={handle}&amount={betrag_str}&currency_code=EUR&item_name={reason.replace(' ', '%20')}"
    else: # PayPal.me Handles (z.B. @epplerjo)
        clean_handle = handle.replace("@", "")
        return f"https://www.paypal.com/paypalme/{clean_handle}/{betrag_str}EUR"

try:
    df_tn, df_aus = load_data()
    
    # --- VORBEREITUNG ---
    df_tn['Name'] = df_tn['Name'].astype(str).str.strip()
    if 'An_Filippos_gezahlt' in df_tn.columns:
        df_tn['Anzahlung'] = pd.to_numeric(df_tn['An_Filippos_gezahlt'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
    else:
        df_tn['Anzahlung'] = 0.0

    # Sonderregel Anne & Dani (Faktor 0.5)
    def get_factor(name):
        return 0.5 if name in ["Anne", "Dani"] else 1.0

    weighted_total_days_unterkunft = sum(row['Tage'] * get_factor(row['Name']) for _, row in df_tn.iterrows())
    normal_total_days = df_tn['Tage'].sum()
    
    res = {n: {"paid_real": 0.0, "soll_t": 0.0, "soll_f": 0.0, "anzahlung": 0.0, "kat": {}} for n in df_tn['Name']}

    total_anzahlungen_an_filippos = 0.0
    for _, row_tn in df_tn.iterrows():
        name = row_tn['Name']
        res[name]['anzahlung'] = row_tn['Anzahlung']
        if name != "Filippos C":
            total_anzahlungen_an_filippos += row_tn['Anzahlung']

    # --- AUSGABEN VERARBEITEN ---
    for i, row in df_aus.iterrows():
        try:
            val_raw = str(row['Betrag']).strip()
            if '.' in val_raw and ',' in val_raw: val_raw = val_raw.replace('.', '')
            val_str = val_raw.replace(',', '.')
            b = float(val_str)
        except: continue

        zahler = str(row['Bezahlt_von']).strip()
        if zahler not in res: continue
        
        kat = str(row['Kategorie']).strip() if pd.notna(row['Kategorie']) else "Sonstiges"
        typ = str(row['Typ']).strip()
        res[zahler]['paid_real'] += b
        
        if typ == 'Tagesabhängig':
            for _, tn in df_tn.iterrows():
                t_name = tn['Name']
                current_weighted_days = weighted_total_days_unterkunft if kat == "Unterkunft" else normal_total_days
                current_factor = get_factor(t_name) if kat == "Unterkunft" else 1.0
                
                anteil = (b / current_weighted_days) * (tn['Tage'] * current_factor)
                res[t_name]['soll_t'] += anteil
                res[t_name]['kat'][kat] = res[t_name]['kat'].get(kat, 0) + anteil
        else:
            betroffene_raw = str(row['Betroffene'])
            btn = df_tn['Name'].tolist() if "Alle" in betroffene_raw or pd.isna(row['Betroffene']) else [n.strip() for n in betroffene_raw.split(',')]
            valid_btn = [p for p in btn if p in res]
            if valid_btn:
                anteil = b / len(valid_btn)
                for p in valid_btn:
                    res[p]['soll_f'] += anteil
                    res[p]['kat'][kat] = res[p]['kat'].get(kat, 0) + anteil

    summary_data = []
    for n, d in res.items():
        anteil_kosten = d['soll_t'] + d['soll_f']
        saldo = (d['paid_real'] - total_anzahlungen_an_filippos - anteil_kosten) if n == "Filippos C" else (d['paid_real'] + d['anzahlung'] - anteil_kosten)
        summary_data.append({"Name": n, "Bons": d['paid_real'], "Anzahlung": d['anzahlung'] if n != "Filippos C" else 0.0, "Anteil": anteil_kosten, "Saldo": saldo})
    
    summary = pd.DataFrame(summary_data)
    
    # --- UI: SALDEN ---
    st.subheader("💰 Salden-Tabelle")
    st.dataframe(summary.style.format(precision=2).applymap(lambda x: 'color:red' if x < -0.01 else 'color:green' if x > 0.01 else 'color:gray', subset=['Saldo']), use_container_width=True)

    # --- UI: ZAHLUNGS-KACHELN ---
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
        s_list = [dict(s) for s in schuldner]
        g_list = [dict(g) for g in glaubiger]
        s_i, g_i = 0, 0
        while s_i < len(s_list) and g_i < len(g_list):
            s_amt = abs(s_list[s_i]['Saldo'])
            g_amt = g_list[g_i]['Saldo']
            pay = min(s_amt, g_amt)
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
                st.markdown(f"""
                <div style="background-color: #e1f5fe; padding: 20px; border-radius: 12px; border-left: 6px solid #0288d1; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 10px 0; color: #01579b;">{name}</h3>
                    <p style="margin: 0 0 10px 0; font-weight: bold; color: #0288d1;">Gesamtschuld: {sum(amt for _, amt in payments):.2f} €</p>
                """, unsafe_allow_html=True)
                
                for empf, amt in payments:
                    pp_link = get_paypal_link(empf, amt)
                    st.write(f"👉 **{amt:.2f} €** an **{empf}**")
                    if pp_link:
                        st.link_button(f"💸 Jetzt {amt:.2f}€ an {empf} senden", pp_link)
                    else:
                        st.caption(f"(Kein PayPal für {empf} hinterlegt)")
                
                st.markdown("</div>", unsafe_allow_html=True)

    # --- UI: DETAILS ---
    st.divider()
    st.subheader("📊 Persönliche Auswertung")
    user = st.selectbox("Wähle einen Namen:", summary['Name'].tolist())
    u_row = summary[summary['Name'] == user].iloc[0]
    u_data = res[user]
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"Saldo {user}", f"{u_row['Saldo']:.2f} €")
        st.write(f"Bons: {u_row['Bons']:.2f} € | Anzahlung: {u_row['Anzahlung']:.2f} €")
        st.write(f"Anteil Kosten: {u_row['Anteil']:.2f} €")
    with col2:
        if u_data['kat']:
            st.plotly_chart(px.pie(values=list(u_data['kat'].values()), names=list(u_data['kat'].keys()), hole=0.4), use_container_width=True)

except Exception as e:
    st.error(f"Kritischer Fehler: {e}")