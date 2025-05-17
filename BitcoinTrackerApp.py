import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, date
import talib
import matplotlib.pyplot as plt
import sqlite3
import uuid

# --- Configuration ---
APP_VERSION = "Portovedo | v0.2.1" # Incremented version
PAGE_TITLE = "Bitcoin Real-Time Tracker (EUR)"
PAGE_ICON = "₿"
REFRESH_INTERVAL_SECONDS = 5
MAX_DATA_POINTS = 300    
DB_NAME = 'bitcoin_tracker_streamlit.db'
PLOT_BG_COLOR = '#0E1117' 
PLOT_TEXT_COLOR = '#FAFAFA'

# --- Database Initialization ---
def initialize_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                     (transaction_id TEXT PRIMARY KEY, 
                      timestamp TEXT, 
                      type TEXT, 
                      price REAL, 
                      eur_amount REAL, 
                      btc_amount REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS deposits
                     (deposit_id TEXT PRIMARY KEY,
                      timestamp TEXT,
                      eur_deposited REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS app_state
                     (key TEXT PRIMARY KEY, value REAL)''')
        
        # Initialize essential app_state keys if they don't exist
        initial_states = {
            'all_time_high': 0.0,
            'eur_balance': 0.0,
            'total_eur_deposited': 0.0
        }
        for key, value in initial_states.items():
            c.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

# --- Session State Initialization ---
def initialize_session_state():
    """Initializes the Streamlit session state variables from DB or defaults."""
    if 'initialized' not in st.session_state:
        st.session_state.price_data = []
        st.session_state.times_data = []
        st.session_state.rsi_data = []
        st.session_state.sma20_data = []
        st.session_state.sma50_data = []
        
        st.session_state.daily_high = 0.0
        st.session_state.daily_low = float('inf')
        st.session_state.last_reset_date = date.min
        
        # Load persistent states from DB
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                for key in ['all_time_high', 'eur_balance', 'total_eur_deposited']:
                    c.execute("SELECT value FROM app_state WHERE key = ?", (key,))
                    result = c.fetchone()
                    st.session_state[key] = result[0] if result else 0.0
        except Exception as e:
            st.error(f"Error loading app state from database: {e}")
            st.session_state.all_time_high = 0.0
            st.session_state.eur_balance = 0.0
            st.session_state.total_eur_deposited = 0.0
            
        st.session_state.current_price_eur = 0.0
        st.session_state.trading_signal = "Analyzing Market..."
        st.session_state.signal_color = PLOT_TEXT_COLOR
        st.session_state.log_messages = [] 
        st.session_state.initialized = True

# --- Database Update Functions ---
def update_db_value(key, value):
    """Updates a key-value pair in the app_state table."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("UPDATE app_state SET value = ? WHERE key = ?", (value, key))
            conn.commit()
    except Exception as e:
        st.error(f"Error updating {key} in database: {e}")

# --- Data Fetching and Processing ---
def get_bitcoin_data():
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCEUR"
        response = requests.get(url, timeout=10)
        response.raise_for_status() 
        data = response.json()
        return float(data['price'])
    except requests.exceptions.RequestException: 
        try:
            url_usdt = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            response_usdt = requests.get(url_usdt, timeout=10)
            response_usdt.raise_for_status()
            data_usdt = response_usdt.json()
            return float(data_usdt['price']) * 0.92 
        except Exception as e_usdt:
            st.session_state.log_messages.append(f"BTCUSDT API error: {e_usdt}")
            st.error(f"Failed to fetch Bitcoin price. Last error: {e_usdt}")
            return None
    except Exception as e:
        st.session_state.log_messages.append(f"General error fetching price: {e}")
        return None

def generate_trading_signal(rsi, current_price, sma20, sma50):
    signal = "HOLD"
    color = PLOT_TEXT_COLOR 
    if pd.isna(rsi) or pd.isna(sma20) or pd.isna(sma50):
        return "Data insufficient for signal", color
    if (rsi < 30 and sma20 > sma50 and current_price > sma50):
        signal = "🚀 TAS À ESPERA DO QUE MANOOOOH, MELHOR ALTURA PARA COMPRAR! 🚀"
        color = "#00FF00"
    elif (rsi > 70 and sma20 < sma50 and current_price < sma50):
        signal = "💰 TOCA A VENDER BRO, NÃO ARRANJAS MELHOR MANOOOOOOH! 💰"
        color = "#FF4444"
    elif (rsi < 35 and current_price > sma20):
        signal = "TALVEZ DEVESSES COMPRAR, DIGO EU BRO"
        color = "#00CC00"
    elif (rsi > 65 and current_price < sma20):
        signal = "DEVIAS PENSAR EM VENDER ESSA MERDA BRO"
        color = "#CC0000"
    else:
        signal = "AGUENTA AÍ OH MANOOOH"
        color = "#008080"
    return signal, color

def update_technical_indicators():
    if len(st.session_state.price_data) > 14:
        prices_array = np.array(st.session_state.price_data, dtype=float)
        rsi_values = talib.RSI(prices_array, timeperiod=14)
        st.session_state.rsi_data.append(rsi_values[-1])
        if len(st.session_state.price_data) >= 20:
            st.session_state.sma20_data.append(talib.SMA(prices_array, timeperiod=20)[-1])
        else:
            st.session_state.sma20_data.append(np.nan)
        if len(st.session_state.price_data) >= 50:
            st.session_state.sma50_data.append(talib.SMA(prices_array, timeperiod=50)[-1])
        else:
            st.session_state.sma50_data.append(np.nan)
        
        if not pd.isna(st.session_state.rsi_data[-1]) and \
           not pd.isna(st.session_state.sma20_data[-1]) and \
           not pd.isna(st.session_state.sma50_data[-1]):
            signal, color = generate_trading_signal(
                st.session_state.rsi_data[-1], st.session_state.current_price_eur,
                st.session_state.sma20_data[-1], st.session_state.sma50_data[-1])
            st.session_state.trading_signal = signal
            st.session_state.signal_color = color
        else:
            st.session_state.trading_signal = "Awaiting more data for full analysis..." 
            st.session_state.signal_color = PLOT_TEXT_COLOR
    else: 
        st.session_state.rsi_data.append(np.nan)
        st.session_state.sma20_data.append(np.nan)
        st.session_state.sma50_data.append(np.nan)
        st.session_state.trading_signal = "Collecting initial data..." 
        st.session_state.signal_color = PLOT_TEXT_COLOR

def update_data_storage():
    if len(st.session_state.price_data) > MAX_DATA_POINTS:
        st.session_state.price_data.pop(0)
        st.session_state.times_data.pop(0)
        if st.session_state.rsi_data: st.session_state.rsi_data.pop(0)
        if st.session_state.sma20_data: st.session_state.sma20_data.pop(0)
        if st.session_state.sma50_data: st.session_state.sma50_data.pop(0)

def update_daily_stats(current_price):
    current_d = date.today()
    if current_d != st.session_state.get('last_reset_date', date.min):
        st.session_state.daily_high = current_price
        st.session_state.daily_low = current_price
        st.session_state.last_reset_date = current_d
    st.session_state.daily_high = max(st.session_state.daily_high, current_price)
    st.session_state.daily_low = min(st.session_state.daily_low, current_price)
    if current_price > st.session_state.all_time_high:
        st.session_state.all_time_high = current_price
        update_db_value('all_time_high', st.session_state.all_time_high)


# --- UI Rendering Functions ---
def display_price_statistics():
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Price", f"{st.session_state.current_price_eur:,.2f} EUR")
    col2.metric("Daily High", f"{st.session_state.daily_high:,.2f} EUR")
    col3.metric("Daily Low", f"{st.session_state.daily_low:,.2f} EUR")
    col4.metric("All-Time High", f"{st.session_state.all_time_high:,.2f} EUR")

def display_charts():
    chart_col, _ = st.columns([2,1]) 
    with chart_col:
        if not st.session_state.price_data or len(st.session_state.price_data) < 2: 
            st.info(st.session_state.trading_signal) 
            return

        fig, (price_ax, rsi_ax) = plt.subplots(2, 1, figsize=(4, 2), sharex=True, facecolor=PLOT_BG_COLOR) 
        fig.patch.set_facecolor(PLOT_BG_COLOR)

        price_ax.set_facecolor(PLOT_BG_COLOR)
        price_ax.tick_params(colors=PLOT_TEXT_COLOR, which='both', labelsize=3) 
        for spine in price_ax.spines.values(): spine.set_color(PLOT_TEXT_COLOR)
        price_ax.set_title('Bitcoin Price (EUR)', color=PLOT_TEXT_COLOR, fontsize=5) 
        price_ax.set_ylabel('Price', color=PLOT_TEXT_COLOR, fontsize=4) 
        price_ax.grid(True, alpha=0.15, color=PLOT_TEXT_COLOR, linestyle=':') 
        price_ax.plot(st.session_state.times_data, st.session_state.price_data, label='BTC/EUR', color='#17BECF', linewidth=0.6) 
        if len(st.session_state.sma20_data) == len(st.session_state.times_data):
            price_ax.plot(st.session_state.times_data, st.session_state.sma20_data, label='SMA20', color='#FFA500', linewidth=0.4, linestyle='--') 
        if len(st.session_state.sma50_data) == len(st.session_state.times_data):
            price_ax.plot(st.session_state.times_data, st.session_state.sma50_data, label='SMA50', color='#FF00FF', linewidth=0.4, linestyle='--') 
        leg1 = price_ax.legend(loc='upper left', facecolor=PLOT_BG_COLOR, labelcolor=PLOT_TEXT_COLOR, fontsize=3) 
        for text in leg1.get_texts(): text.set_color(PLOT_TEXT_COLOR)

        rsi_ax.set_facecolor(PLOT_BG_COLOR)
        rsi_ax.tick_params(colors=PLOT_TEXT_COLOR, which='both', labelrotation=10, labelsize=3) 
        for spine in rsi_ax.spines.values(): spine.set_color(PLOT_TEXT_COLOR)
        rsi_ax.set_title('RSI Indicator', color=PLOT_TEXT_COLOR, fontsize=5) 
        rsi_ax.set_ylabel('RSI', color=PLOT_TEXT_COLOR, fontsize=4) 
        rsi_ax.set_ylim(0, 100)
        rsi_ax.grid(True, alpha=0.15, color=PLOT_TEXT_COLOR, linestyle=':') 
        if len(st.session_state.rsi_data) == len(st.session_state.times_data):
            rsi_ax.plot(st.session_state.times_data, st.session_state.rsi_data, label='RSI', color='#9467BD', linewidth=0.6) 
        rsi_ax.axhline(y=70, color='#FF4444', linestyle='--', linewidth=0.4) 
        rsi_ax.axhline(y=30, color='#00FF00', linestyle='--', linewidth=0.4) 
        leg2 = rsi_ax.legend(loc='upper left', facecolor=PLOT_BG_COLOR, labelcolor=PLOT_TEXT_COLOR, fontsize=3) 
        for text in leg2.get_texts(): text.set_color(PLOT_TEXT_COLOR)

        plt.xticks(rotation=10, ha='right') 
        plt.tight_layout(pad=0.3) 
        st.pyplot(fig)
        plt.close(fig)

def display_trading_signal():
    st.markdown(f"<h4 style='text-align: center; color: {st.session_state.signal_color};'>{st.session_state.trading_signal}</h4>", unsafe_allow_html=True)

def get_current_btc_holdings():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            df = pd.read_sql_query("SELECT SUM(btc_amount) as total_btc FROM transactions", conn)
            return df['total_btc'].iloc[0] if not df.empty and not pd.isna(df['total_btc'].iloc[0]) else 0.0
    except Exception as e:
        st.error(f"Error fetching BTC holdings: {e}")
        return 0.0

# --- Wallet Tab Functions ---
def display_wallet_tab():
    st.header("My Bitcoin Wallet")
    current_btc_price = st.session_state.current_price_eur

    st.subheader("💶 EUR Wallet Management")
    with st.form("deposit_form"):
        st.write(f"Current EUR Balance: **{st.session_state.eur_balance:,.2f} EUR**")
        amount_to_deposit = st.number_input("Amount to Deposit (EUR)", min_value=0.01, step=0.01, format="%.2f", key="deposit_eur")
        submit_deposit = st.form_submit_button("Deposit EUR")

        if submit_deposit and amount_to_deposit > 0:
            st.session_state.eur_balance += amount_to_deposit
            st.session_state.total_eur_deposited += amount_to_deposit
            update_db_value('eur_balance', st.session_state.eur_balance)
            update_db_value('total_eur_deposited', st.session_state.total_eur_deposited)
            
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO deposits (deposit_id, timestamp, eur_deposited) VALUES (?, ?, ?)",
                              (str(uuid.uuid4()), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), amount_to_deposit))
                    conn.commit()
                st.success(f"Successfully deposited {amount_to_deposit:,.2f} EUR.")
                st.rerun() # MODIFIED from st.experimental_rerun()
            except Exception as e:
                st.error(f"Error logging deposit: {e}")
    st.markdown("---")

    st.subheader("📈 Portfolio Overview")
    total_btc_held = get_current_btc_holdings()
    current_value_of_btc_holdings = total_btc_held * current_btc_price
    overall_pl = (current_value_of_btc_holdings + st.session_state.eur_balance) - st.session_state.total_eur_deposited

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("EUR Balance", f"{st.session_state.eur_balance:,.2f} EUR")
    col2.metric("Total BTC Value", f"{current_value_of_btc_holdings:,.2f} EUR", f"{total_btc_held:.8f} BTC")
    col3.metric("Total Net Deposited", f"{st.session_state.total_eur_deposited:,.2f} EUR")
    
    pl_color_style = "color: green;" if overall_pl >= 0 else "color: red;"
    col4.markdown(f"""
    <div style="font-weight: bold; font-size: 0.875rem; color: #808495;">OVERALL P/L</div>
    <div style="font-size: 1.25rem; {pl_color_style}">{overall_pl:,.2f} EUR</div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    if current_btc_price <= 0:
        st.warning("Waiting for current price data to enable trading.")
        if st.session_state.price_data: current_btc_price = st.session_state.price_data[-1]
        else: return

    buy_col, sell_col = st.columns(2)
    with buy_col:
        st.subheader("🛒 Buy Bitcoin")
        with st.form("buy_form"):
            st.markdown(f"Current BTC Price: **{current_btc_price:,.2f} EUR**")
            st.markdown(f"Available EUR: **{st.session_state.eur_balance:,.2f} EUR**")
            buy_amount_eur = st.number_input("Amount to Invest (EUR)", min_value=0.01, max_value=st.session_state.eur_balance if st.session_state.eur_balance > 0 else 0.01, step=0.01, format="%.2f", key="buy_eur_val")
            
            can_buy = st.session_state.eur_balance >= buy_amount_eur
            submit_buy = st.form_submit_button("Buy Bitcoin", disabled=not can_buy or buy_amount_eur <=0)

            if submit_buy:
                if not can_buy:
                    st.error("Insufficient EUR balance to make this purchase.")
                elif buy_amount_eur > 0 :
                    btc_bought = buy_amount_eur / current_btc_price
                    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        with sqlite3.connect(DB_NAME) as conn:
                            c = conn.cursor()
                            c.execute("INSERT INTO transactions (transaction_id, timestamp, type, price, eur_amount, btc_amount) VALUES (?, ?, ?, ?, ?, ?)",
                                      (str(uuid.uuid4()), timestamp_str, 'buy', current_btc_price, -buy_amount_eur, btc_bought))
                            conn.commit()
                        st.session_state.eur_balance -= buy_amount_eur
                        update_db_value('eur_balance', st.session_state.eur_balance)
                        st.success(f"Bought {btc_bought:.8f} BTC for {buy_amount_eur:,.2f} EUR.")
                        st.rerun() # MODIFIED from st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Error saving buy transaction: {e}")
    
    with sell_col:
        st.subheader("💸 Sell Bitcoin")
        current_holdings_for_sell = get_current_btc_holdings()
        if current_holdings_for_sell <= 0:
            st.info("No Bitcoin to sell.")
        else:
            with st.form("sell_form"):
                st.markdown(f"Current BTC Price: **{current_btc_price:,.2f} EUR**")
                st.markdown(f"You hold: **{current_holdings_for_sell:.8f} BTC**")
                sell_amount_btc = st.number_input("Amount of BTC to Sell", min_value=0.00000001, max_value=current_holdings_for_sell, step=0.00000001, format="%.8f", key="sell_btc_val")
                submit_sell = st.form_submit_button("Sell Bitcoin", disabled=sell_amount_btc <=0)

                if submit_sell and sell_amount_btc > 0:
                    eur_received = sell_amount_btc * current_btc_price
                    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        with sqlite3.connect(DB_NAME) as conn:
                            c = conn.cursor()
                            c.execute("INSERT INTO transactions (transaction_id, timestamp, type, price, eur_amount, btc_amount) VALUES (?, ?, ?, ?, ?, ?)",
                                      (str(uuid.uuid4()), timestamp_str, 'sell', current_btc_price, eur_received, -sell_amount_btc))
                            conn.commit()
                        st.session_state.eur_balance += eur_received
                        update_db_value('eur_balance', st.session_state.eur_balance)
                        st.success(f"Sold {sell_amount_btc:.8f} BTC for {eur_received:,.2f} EUR.")
                        st.rerun() # MODIFIED from st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Error saving sell transaction: {e}")

# --- History Tab Functions ---
def display_history_tab():
    st.header("📜 Transaction History")
    
    st.subheader("Bitcoin Transactions (Buy/Sell)")
    try:
        with sqlite3.connect(DB_NAME) as conn:
            btc_history_df = pd.read_sql_query("SELECT timestamp, type, price, eur_amount, btc_amount FROM transactions ORDER BY timestamp DESC", conn)
    except Exception as e:
        st.error(f"Error loading BTC transaction history: {e}")
        btc_history_df = pd.DataFrame()

    if btc_history_df.empty:
        st.info("No Bitcoin transaction history found.")
    else:
        display_btc_df = btc_history_df.copy()
        display_btc_df['price'] = display_btc_df['price'].map('{:,.2f} EUR'.format)
        display_btc_df['eur_amount'] = display_btc_df['eur_amount'].map('{:,.2f} EUR'.format) 
        display_btc_df['btc_amount'] = display_btc_df['btc_amount'].map('{:,.8f} BTC'.format)
        display_btc_df['type'] = display_btc_df['type'].str.capitalize()
        st.dataframe(display_btc_df[['timestamp', 'type', 'price', 'eur_amount', 'btc_amount']], use_container_width=True)

    st.markdown("---")
    st.subheader("EUR Deposits")
    try:
        with sqlite3.connect(DB_NAME) as conn:
            deposit_history_df = pd.read_sql_query("SELECT timestamp, eur_deposited FROM deposits ORDER BY timestamp DESC", conn)
    except Exception as e:
        st.error(f"Error loading deposit history: {e}")
        deposit_history_df = pd.DataFrame()
    
    if deposit_history_df.empty:
        st.info("No EUR deposit history found.")
    else:
        display_deposit_df = deposit_history_df.copy()
        display_deposit_df['eur_deposited'] = display_deposit_df['eur_deposited'].map('{:,.2f} EUR'.format)
        st.dataframe(display_deposit_df[['timestamp', 'eur_deposited']], use_container_width=True)


def display_raw_data_log():
    with st.expander("📊 View Recent Raw Data (Last 20 entries)"):
        if not st.session_state.price_data:
            st.caption("No data yet.")
            return
        data_len = len(st.session_state.price_data)
        start_index = max(0, data_len - 20)
        times = [t.strftime("%H:%M:%S") for t in st.session_state.times_data[start_index:]]
        prices_display = [f"{p:,.2f}€" for p in st.session_state.price_data[start_index:]] 
        
        rsi_display = [f"{r:.2f}" if not pd.isna(r) else "N/A" for r in st.session_state.rsi_data[start_index:]] if len(st.session_state.rsi_data) >= data_len else ["N/A"] * len(times)
        sma20_display = [f"{s:,.2f}" if not pd.isna(s) else "N/A" for s in st.session_state.sma20_data[start_index:]] if len(st.session_state.sma20_data) >= data_len else ["N/A"] * len(times)
        sma50_display = [f"{s:,.2f}" if not pd.isna(s) else "N/A" for s in st.session_state.sma50_data[start_index:]] if len(st.session_state.sma50_data) >= data_len else ["N/A"] * len(times)

        min_len = min(len(times), len(prices_display), len(rsi_display), len(sma20_display), len(sma50_display))
        
        df_data = {
            "Time": times[:min_len],
            "Price": prices_display[:min_len],
            "RSI": rsi_display[:min_len],
            "SMA20": sma20_display[:min_len],
            "SMA50": sma50_display[:min_len]
        }
        
        log_df = pd.DataFrame(df_data)
        st.dataframe(log_df.sort_index(ascending=False), use_container_width=True, height=200)


    if st.session_state.log_messages:
        with st.expander("⚙️ System Logs"):
            for msg in reversed(st.session_state.log_messages[-10:]): # Show last 10 messages
                st.caption(f"{datetime.now().strftime('%H:%M:%S')} - {msg}")


# --- Main Application ---
def main():
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")
    st.sidebar.title(f"{PAGE_ICON} Options")
    st.sidebar.caption(APP_VERSION) 

    initialize_db() 
    initialize_session_state()

    new_price = get_bitcoin_data()
    if new_price is not None:
        st.session_state.current_price_eur = new_price
        st.session_state.price_data.append(new_price)
        st.session_state.times_data.append(datetime.now())
        update_daily_stats(new_price)
        update_technical_indicators() 
        update_data_storage()
    elif not st.session_state.price_data: 
        st.session_state.trading_signal = "Could not fetch initial Bitcoin price. Check connection."
    elif st.session_state.price_data: 
         st.session_state.current_price_eur = st.session_state.price_data[-1]
         st.warning("Using last known price due to API fetch error. Data may be stale.")

    st.title(f"{PAGE_ICON} Bitcoin Real-Time Dashboard")

    tab1, tab2, tab3 = st.tabs(["📊 Tracker", "💼 Wallet", "📜 History"])

    with tab1:
        st.header("Market Tracker")
        display_price_statistics()
        st.markdown("---")
        display_charts() 
        st.markdown("---")
        display_trading_signal()
        st.markdown("---")
        display_raw_data_log()

    with tab2:
        display_wallet_tab()

    with tab3:
        display_history_tab()
    
    # The main st.rerun() at the end of the script handles the periodic refresh
    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()

if __name__ == "__main__":
    main()
