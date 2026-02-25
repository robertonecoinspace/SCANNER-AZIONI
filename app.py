import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Corporate Efficiency Rating & Trend", layout="wide")

st.title("🏆 Rating di Efficienza e Trend di Solidità")
st.markdown("""
Analisi della qualità aziendale con focus sul **Cash Ratio** (Cassa + Investimenti Breve / Debito Totale).
Il sistema confronta i dati annuali con gli ultimi trimestrali per rilevare variazioni nella solvibilità.
""")

def get_val(df, keys, row_idx=0):
    if df is None or df.empty: return 0
    df.index = df.index.str.strip()
    for k in keys:
        if k in df.index:
            val = df.loc[k]
            return val.iloc[row_idx] if hasattr(val, 'iloc') else val
    return 0

def calculate_rating(punteggio):
    if punteggio >= 85: return "A+"
    if punteggio >= 70: return "A"
    if punteggio >= 55: return "B"
    if punteggio >= 40: return "C"
    if punteggio >= 25: return "D"
    return "F (Rischio)"

def analyze_efficiency(symbol):
    try:
        stock = yf.Ticker(symbol.strip().upper().replace('.', '-'))
        info = stock.info
        bs = stock.balance_sheet
        is_stmt = stock.financials
        cf = stock.cashflow
        bs_q = stock.quarterly_balance_sheet
        
        if bs.empty or is_stmt.empty or bs_q.empty: return None

        # --- 1. CASH / DEBT (FORMULA TRADINGVIEW) ---
        def get_cash_ratio(balance_df):
            # Somma Cassa e Investimenti a breve termine
            cash = get_val(balance_df, ['Cash And Cash Equivalents', 'Cash'])
            short_term_inv = get_val(balance_df, ['Short Term Investments', 'Other Short Term Investments', 'Cash Cash Equivalents And Short Term Investments'])
            # Se yfinance ha già la voce aggregata usiamo quella, altrimenti sommiamo
            total_liquidity = max(cash + short_term_inv, get_val(balance_df, ['Cash Cash Equivalents And Short Term Investments']))
            debt = get_val(balance_df, ['Total Debt'])
            return total_liquidity / debt if debt > 0 else 5.0

        cash_debt_ann = get_cash_ratio(bs)
        cash_debt_q = get_cash_ratio(bs_q)
        
        # Calcolo Variazione (Trend)
        trend_val = ((cash_debt_q - cash_debt_ann) / cash_debt_ann) * 100 if cash_debt_ann > 0 else 0
        trend_icon = "📈" if trend_val > 0 else "📉"
        trend_label = f"{trend_icon} {trend_val:+.1f}%"

        # --- 2. PARAMETRI QUALITATIVI ---
        roe = info.get('returnOnEquity', 0) or 0
        margin = info.get('profitMargins', 0) or 0
        debt_equity = (info.get('debtToEquity', 0) or 0) / 100
        div_yield = info.get('dividendYield', 0) or 0

        # Altman Z-Score
        total_assets = get_val(bs, ['Total Assets'])
        working_cap = get_val(bs, ['Working Capital'])
        re = get_val(bs, ['Retained Earnings'])
        ebit = get_val(is_stmt, ['EBIT'])
        mkt_cap = info.get('marketCap', 1)
        total_liab = get_val(bs, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        rev = info.get('totalRevenue', 1)
        
        z_score = (1.2*(working_cap/total_assets) + 1.4*(re/total_assets) + 
                   3.3*(ebit/total_assets) + 0.6*(mkt_cap/total_liab) + 1.0*(rev/total_assets))

        # Piotroski F-Score (5 Criteri)
        f_score = 0
        if get_val(is_stmt, ['Net Income']) > 0: f_score += 1
        if get_val(cf, ['Operating Cash Flow']) > 0: f_score += 1
        if roe > 0.15: f_score += 1
        if cash_debt_q > 1: f_score += 1
        if debt_equity < 1: f_score += 1

        # --- 3. SCORE & RATING ---
        score = 0
        score += min(roe * 150, 25)
        score += 20 if z_score > 3 else (10 if z_score > 1.8 else 0)
        score += 20 if cash_debt_q > 1 else (10 if cash_debt_q > 0.5 else 0)
        score += 15 if margin > 0.15 else 5
        score += 20 * (f_score / 5)
        
        # Bonus/Malus Trend
        if trend_val > 5: score += 5
        if trend_val < -10: score -= 5
        
        rating = calculate_rating(score)

        return {
            "Ticker": symbol,
            "Rating": rating,
            "Trend C/D (Q vs A)": trend_label,
            "Cash/Debt (Q)": round(cash_debt_q, 2),
            "Cash/Debt (A)": round(cash_debt_ann, 2),
            "Altman Z-Score": round(z_score, 2),
            "ROE %": round(roe * 100, 1),
            "Margine %": round(margin * 100, 1),
            "Debt/Equity": round(debt_equity, 2),
            "F-Score": f"{f_score}/5"
        }
    except:
        return None

# --- STREAMLIT UI ---
uploaded_file = st.sidebar.file_uploader("Carica lista_ticker.csv", type="csv")

if uploaded_file:
    df_input = pd.read_csv(uploaded_file)
    ticker_col = 'Ticker' if 'Ticker' in df_input.columns else df_input.columns[0]
    tickers = df_input[ticker_col].dropna().unique().tolist()
    
    if st.sidebar.button("🔍 Analizza Efficienza e Trend"):
        risultati = []
        bar = st.progress(0)
        for i, t in enumerate(tickers):
            res = analyze_efficiency(t)
            if res: risultati.append(res)
            bar.progress((i+1)/len(tickers))
        
        if risultati:
            df_res = pd.DataFrame(risultati)
            
            def color_rating(val):
                colors = {'A+': '#006400', 'A': '#2ecc71', 'B': '#f1c40f', 'C': '#e67e22', 'D': '#e74c3c', 'F': '#8b0000'}
                c = next((col for k, col in colors.items() if k in val), 'white')
                return f'color: {c}; font-weight: bold'

            def color_trend(val):
                if '📉' in val: return 'color: #e74c3c'
                if '📈' in val: return 'color: #2ecc71'
                return ''

            st.subheader("📋 Risultati Scanner di Efficienza")
            st.dataframe(
                df_res.style.applymap(color_rating, subset=['Rating'])
                            .applymap(color_trend, subset=['Trend C/D (Q vs A)'])
            )
            
           # --- PARTE FINALE AGGIORNATA ---
            st.markdown("---")
            st.info(f"""
            ### 🧠 Guida all'interpretazione dei dati
            
            **Indicatori di Rischio e Forza:**
            * **Altman Z-Score:** > 3.0 Sano | < 1.8 Rischio Fallimento elevato.
            * **Piotroski (5pt):** Indica la forza operativa (calcolato su 5 parametri chiave).
            * **Cash/Debt:** > 1 significa che l'azienda può ripagare tutto il debito con la cassa immediata.
            
            **Sistema di Rating:**
            * **A+ / A:** Aziende con alta redditività (ROE), cassa abbondante rispetto ai debiti e Z-score in zona sicurezza.
            * **C / D:** Aziende con margini bassi o debiti che superano di molto la liquidità immediata.
            * **F:** Segnale d'allarme rosso. Bassa cassa, Z-score sotto 1.8 e ROE negativo.
            """)

            # Inserisco uno schema visuale per lo Z-Score di Altman
            

            st.success(f"Analisi completata con successo su {len(df_res)} titoli.")

