import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
from binance.client import Client
import requests
import time
from datetime import datetime
import talib
import threading
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sqlite3

class BitcoinTracker(tk.Tk):
    def __init__(self):
        super().__init__()

        # Dark mode colors
        self.bg_color = '#1e1e1e'
        self.text_color = '#ffffff'


        # Initialize Binance client
        self.client = Client()

        self.title("Bitcoin Real-Time Tracker (EUR)")
        self.geometry("1200x1200")
        self.configure(bg=self.bg_color)

        # Initialize data storage
        self.price_data = []
        self.times_data = []
        self.rsi_data = []
        self.sma20_data = []
        self.sma50_data = []
        self.daily_high = 0
        self.daily_low = float('inf')

        # Create main frame
        self.main_frame = tk.Frame(self, bg=self.bg_color)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create price statistics frame
        self.stats_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.stats_frame.pack(fill=tk.X, padx=10, pady=5)

        # Add price labels
        self.current_price_label = tk.Label(
            self.stats_frame,
            text="Current Price: --- EUR",
            font=('Arial', 14, 'bold'),
            bg=self.bg_color,
            fg=self.text_color
        )
        self.current_price_label.pack(side=tk.LEFT)

        self.high_price_label = tk.Label(
            self.stats_frame,
            text="Daily High: --- EUR",
            font=('Arial', 14, 'bold'),
            bg=self.bg_color,
            fg=self.text_color
        )
        self.high_price_label.pack(side=tk.LEFT, padx=20)

        self.low_price_label = tk.Label(
            self.stats_frame,
            text="Daily Low: --- EUR",
            font=('Arial', 14, 'bold'),
            bg=self.bg_color,
            fg=self.text_color
        )
        self.low_price_label.pack(side=tk.LEFT, padx=20)

        # Create graph frame
        self.graph_frame = tk.Frame(self.main_frame, bg=self.bg_color, height=400)
        self.graph_frame.pack(fill=tk.X, expand=False, padx=10, pady=5)

        # Create matplotlib figure
        self.figure = Figure(figsize=(12, 6), dpi=100, facecolor=self.bg_color)
        self.price_ax = self.figure.add_subplot(211)
        self.rsi_ax = self.figure.add_subplot(212)

        # Configure dark mode for plots
        self.price_ax.set_facecolor(self.bg_color)
        self.rsi_ax.set_facecolor(self.bg_color)

        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.figure, self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Create data display frame
        self.data_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.data_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create text widgets for data display
        self.create_data_displays()

        # Create signal frame
        self.signal_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.signal_frame.pack(fill=tk.X, padx=10, pady=5)

        self.signal_label = tk.Label(
            self.signal_frame,
            text="Analyzing Market...",
            font=('Arial', 24, 'bold'),
            bg=self.bg_color,
            fg=self.text_color
        )
        self.signal_label.pack(pady=10)

        self.add_buttons()

        # Start data collection thread
        self.running = True
        self.data_thread = threading.Thread(target=self.update_data)
        self.data_thread.daemon = True
        self.data_thread.start()
        
        # Start plot update
        self.update_plot()

        # Add after initializing daily_high and daily_low
        self.all_time_high = 0
        self.last_reset = datetime.now().date()

        # Add these lines after other initializations
        self.bind("<F11>", lambda event: self.toggle_fullscreen())
        self.bind("<Escape>", lambda event: self.attributes("-fullscreen", False))


    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width/2) - (width/2)
        y = (screen_height/2) - (height/2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

    def create_data_displays(self):
        # Create frames for each data column
        self.price_frame = tk.LabelFrame(self.data_frame, text="Price History", 
                                       bg=self.bg_color, fg=self.text_color)
        self.rsi_frame = tk.LabelFrame(self.data_frame, text="RSI Values", 
                                      bg=self.bg_color, fg=self.text_color)
        self.sma20_frame = tk.LabelFrame(self.data_frame, text="SMA20 Values", 
                                        bg=self.bg_color, fg=self.text_color)
        self.sma50_frame = tk.LabelFrame(self.data_frame, text="SMA50 Values", 
                                        bg=self.bg_color, fg=self.text_color)

        self.price_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.rsi_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.sma20_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.sma50_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Create text widgets
        self.price_text = tk.Text(self.price_frame, height=10, width=25, 
                                bg=self.bg_color, fg=self.text_color)
        self.rsi_text = tk.Text(self.rsi_frame, height=10, width=25, 
                               bg=self.bg_color, fg=self.text_color)
        self.sma20_text = tk.Text(self.sma20_frame, height=10, width=25, 
                                 bg=self.bg_color, fg=self.text_color)
        self.sma50_text = tk.Text(self.sma50_frame, height=10, width=25, 
                                 bg=self.bg_color, fg=self.text_color)

        self.price_text.pack(padx=5, pady=5)
        self.rsi_text.pack(padx=5, pady=5)
        self.sma20_text.pack(padx=5, pady=5)
        self.sma50_text.pack(padx=5, pady=5)

    def update_text_widgets(self):
        # Get last 20 values
        last_20_prices = self.price_data[-20:]
        last_20_times = self.times_data[-20:]
        last_20_rsi = self.rsi_data[-20:] if len(self.rsi_data) > 0 else []
        last_20_sma20 = self.sma20_data[-20:] if len(self.sma20_data) > 0 else []
        last_20_sma50 = self.sma50_data[-20:] if len(self.sma50_data) > 0 else []

        # Update text widgets
        self.price_text.delete(1.0, tk.END)
        self.rsi_text.delete(1.0, tk.END)
        self.sma20_text.delete(1.0, tk.END)
        self.sma50_text.delete(1.0, tk.END)

        for i in range(len(last_20_prices)):
            time_str = last_20_times[i].strftime("%H:%M:%S")
            self.price_text.insert(tk.END, f"{time_str}: {last_20_prices[i]:.2f}€\n")
            if len(last_20_rsi) > i:
                self.rsi_text.insert(tk.END, f"{time_str}: {last_20_rsi[i]:.2f}\n")
            if len(last_20_sma20) > i:
                self.sma20_text.insert(tk.END, f"{time_str}: {last_20_sma20[i]:.2f}\n")
            if len(last_20_sma50) > i:
                self.sma50_text.insert(tk.END, f"{time_str}: {last_20_sma50[i]:.2f}\n")

    def generate_trading_signal(self, rsi, current_price, sma20, sma50):
        signal = "HOLD"
        color = self.text_color
        
        if (rsi < 30 and sma20 > sma50 and current_price > sma50):
            signal = "🚀 TAS À ESPERA DO QUE MANOOOOH, MELHOR ALTURA PARA COMPRAR! 🚀"
            color = "#00ff00"
        elif (rsi > 70 and sma20 < sma50 and current_price < sma50):
            signal = "💰 TOCA A VENDER BRO, NÃO ARRANJAS MELHOR MANOOOOOOH! 💰"
            color = "#ff4444"
        elif (rsi < 35 and current_price > sma20):
            signal = "TALVEZ DEVESSES COMPRAR, DIGO EU BRO"
            color = "#00cc00"
        elif (rsi > 65 and current_price < sma20):
            signal = "DEVIAS PENSAR EM VENDER ESSA MERDA BRO"
            color = "#cc0000"
        else:
            signal = "AGUENTA AÍ OH MANOOOH"
            color = "#008080"

        return signal, color
    
    def update_plot(self):
        try:
            if len(self.price_data) > 0:
                self.price_ax.clear()
                self.rsi_ax.clear()

                # Set dark mode colors
                self.price_ax.set_facecolor(self.bg_color)
                self.rsi_ax.set_facecolor(self.bg_color)
                self.figure.set_facecolor(self.bg_color)

                # Configure text colors
                self.price_ax.tick_params(colors=self.text_color)
                self.rsi_ax.tick_params(colors=self.text_color)
                
                # Plot data
                self.price_ax.plot(self.times_data, self.price_data, 
                                label='BTC/EUR', color='#17BECF')
                
                if len(self.sma20_data) > 0:
                    self.price_ax.plot(
                        self.times_data[-len(self.sma20_data):],
                        self.sma20_data, label='SMA20', color='#7F7F7F')
                    self.price_ax.plot(
                        self.times_data[-len(self.sma50_data):],
                        self.sma50_data, label='SMA50', color='#FFB6C1')

                if len(self.rsi_data) > 0:
                    self.rsi_ax.plot(
                        self.times_data[-len(self.rsi_data):],
                        self.rsi_data, label='RSI', color='#9467BD')
                    self.rsi_ax.axhline(y=70, color='#ff4444', linestyle='--')
                    self.rsi_ax.axhline(y=30, color='#00ff00', linestyle='--')

                # Customize plots
                self.price_ax.set_title('Bitcoin Price (EUR)', pad=10, color=self.text_color)
                self.price_ax.set_ylabel('Price (EUR)', color=self.text_color)
                self.price_ax.grid(True, alpha=0.3, color=self.text_color)
                self.price_ax.legend(loc='upper left', facecolor=self.bg_color, labelcolor=self.text_color)

                self.rsi_ax.set_title('RSI Indicator', pad=10, color=self.text_color)
                self.rsi_ax.set_ylabel('RSI', color=self.text_color)
                self.rsi_ax.set_ylim(0, 100)
                self.rsi_ax.grid(True, alpha=0.3, color=self.text_color)
                self.rsi_ax.legend(loc='upper left', facecolor=self.bg_color, labelcolor=self.text_color)

                # Update spines colors
                for spine in self.price_ax.spines.values():
                    spine.set_color(self.text_color)
                for spine in self.rsi_ax.spines.values():
                    spine.set_color(self.text_color)

                self.price_ax.tick_params(axis='x', rotation=45)
                self.rsi_ax.tick_params(axis='x', rotation=45)

                self.figure.tight_layout()
                self.canvas.draw()

        except Exception as e:
            print(f"Error in plot update: {e}")

        self.after(1000, self.update_plot)


    def get_bitcoin_data(self):
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCEUR"
            response = requests.get(url, timeout=5)
            data = response.json()
            return float(data['price'])
        except Exception as e:
            try:
                url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
                response = requests.get(url, timeout=5)
                data = response.json()
                price_usdt = float(data['price'])
                return price_usdt * 0.92
            except Exception as e:
                print(f"Error getting price data: {e}")
                return None

    def update_data(self):
        while self.running:
            try:
                current_price = self.get_bitcoin_data()
                
                if current_price:
                    # Check if day has changed
                    current_date = datetime.now().date()
                    if current_date != self.last_reset:
                        self.daily_high = current_price
                        self.daily_low = current_price
                        self.last_reset = current_date

                    # Update daily high/low and append data
                    self.daily_high = max(self.daily_high, current_price)
                    self.daily_low = min(self.daily_low, current_price)
                    self.all_time_high = max(self.all_time_high, current_price)
                    
                    # Append new data
                    self.price_data.append(current_price)
                    self.times_data.append(datetime.now())

                    if len(self.price_data) > 50:
                        prices_array = np.array(self.price_data)
                        rsi = talib.RSI(prices_array, timeperiod=14)[-1]
                        sma20 = talib.SMA(prices_array, timeperiod=20)[-1]
                        sma50 = talib.SMA(prices_array, timeperiod=50)[-1]

                        self.rsi_data.append(rsi)
                        self.sma20_data.append(sma20)
                        self.sma50_data.append(sma50)

                        signal, color = self.generate_trading_signal(
                            rsi, current_price, sma20, sma50
                        )
                        self.signal_label.config(text=signal, fg=color)

                        if len(self.price_data) > 300:
                            self.price_data.pop(0)
                            self.times_data.pop(0)
                            self.rsi_data.pop(0)
                            self.sma20_data.pop(0)
                            self.sma50_data.pop(0)

                    # Update labels
                    self.current_price_label.config(
                        text=f"Current Price: {current_price:,.2f} EUR"
                    )
                    self.high_price_label.config(
                        text=f"Daily High: {self.daily_high:,.2f} EUR | ATH: {self.all_time_high:,.2f} EUR"
                    )
                    self.low_price_label.config(
                        text=f"Daily Low: {self.daily_low:,.2f} EUR"
                    )

                    # Update text displays
                    self.update_text_widgets()

                time.sleep(1)

            except Exception as e:
                print(f"Error in data update: {e}")
                time.sleep(5)

    def add_buttons(self):
        # Create button frame
        self.button_frame = tk.Frame(self.signal_frame, bg=self.bg_color)
        self.button_frame.pack(pady=10)
        
        # Buy button
        self.buy_button = tk.Button(
            self.button_frame,
            text="Buy Now!",
            command=self.open_purchase_window,
            bg='#00cc00',
            fg='white',
            font=('Arial', 14, 'bold'),
            width=15
        )
        self.buy_button.pack(side=tk.LEFT, padx=10)
        
        # View purchases button
        self.view_button = tk.Button(
            self.button_frame,
            text="View Purchases",
            command=lambda: PurchasesListWindow(self),
            bg='#0066cc',
            fg='white',
            font=('Arial', 14, 'bold'),
            width=15
        )
        self.view_button.pack(side=tk.LEFT, padx=10)
        
        # Full screen button
        self.fullscreen_button = tk.Button(
            self.button_frame,
            text="Full Screen",
            command=self.toggle_fullscreen,
            bg='#404040',
            fg='white',
            font=('Arial', 14, 'bold'),
            width=15
        )
        self.fullscreen_button.pack(side=tk.LEFT, padx=10)


    def open_purchase_window(self):
        if len(self.price_data) > 0:
            PurchaseWindow(self, self.price_data[-1])

    def toggle_fullscreen(self):
        if self.attributes('-fullscreen'):
            self.attributes('-fullscreen', False)
            self.fullscreen_button.config(text="Full Screen")
        else:
            self.attributes('-fullscreen', True)
            self.fullscreen_button.config(text="Exit Full Screen")


    def on_closing(self):
        self.running = False
        time.sleep(1)
        self.destroy()

class PurchaseWindow(tk.Toplevel):
    def __init__(self, parent, current_price):
        super().__init__(parent)
        self.title("Purchase Bitcoin")
        self.geometry("500x400")
        self.configure(bg='#1e1e1e')
        self.resizable(True, True)
        
        # Center the window
        self.center_window(500, 400)
        
        # Store parent reference and price
        self.parent = parent
        self.current_price = current_price
        
        # Create labels
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tk.Label(
            self,
            text=f"Date: {current_time}",
            font=('Arial', 12),
            bg='#1e1e1e',
            fg='white'
        ).pack(pady=10)
        
        tk.Label(
            self,
            text=f"Current Bitcoin Price: {current_price:.2f} EUR",
            font=('Arial', 12),
            bg='#1e1e1e',
            fg='white'
        ).pack(pady=10)
        
        # Create input frame
        input_frame = tk.Frame(self, bg='#1e1e1e')
        input_frame.pack(pady=20)
        
        tk.Label(
            input_frame,
            text="Amount (EUR):",
            font=('Arial', 12),
            bg='#1e1e1e',
            fg='white'
        ).pack(side=tk.LEFT, padx=5)
        
        self.amount_entry = tk.Entry(input_frame, font=('Arial', 12))
        self.amount_entry.pack(side=tk.LEFT, padx=5)
        
        # Create Go button
        tk.Button(
            self,
            text="Go Now!",
            command=self.save_purchase,
            bg='#00cc00',
            fg='white',
            font=('Arial', 12, 'bold')
        ).pack(pady=20)

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width/2) - (width/2)
        y = (screen_height/2) - (height/2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

    def save_purchase(self):
        try:
            amount = float(self.amount_entry.get())
            btc_amount = amount / self.current_price
            timestamp = datetime.now()
            
            # Save to database
            conn = sqlite3.connect('bitcoin_purchases.db')
            c = conn.cursor()
            
            # Create table if it doesn't exist
            c.execute('''CREATE TABLE IF NOT EXISTS purchases
                        (timestamp TEXT, price REAL, eur_amount REAL, btc_amount REAL)''')
            
            # Insert purchase data
            c.execute("INSERT INTO purchases VALUES (?, ?, ?, ?)",
                     (timestamp.strftime("%Y-%m-%d %H:%M:%S"), 
                      self.current_price, amount, btc_amount))
            
            conn.commit()
            conn.close()
            
            # Show purchases window
            PurchasesListWindow(self.parent)
            self.destroy()
            
        except ValueError:
            tk.messagebox.showerror("Error", "Please enter a valid amount")

class PurchasesListWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Purchase History")
        self.geometry("1000x600")
        self.configure(bg='#1e1e1e')
        self.resizable(True, True)

        # Center the window
        self.center_window(1200, 600)
        
        # Create and configure style for dark mode
        self.style = ttk.Style()
        self.style.theme_use('default')  # Reset theme
        
        # Configure the main treeview style
        self.style.configure(
            "Custom.Treeview",
            background="#2d2d2d",
            foreground="white",
            fieldbackground="#2d2d2d",
            borderwidth=0,
            font=('Arial', 10)
        )
        
        # Configure the header style
        self.style.configure(
            "Custom.Treeview.Heading",
            background="#1e1e1e",
            foreground="white",
            borderwidth=1,
            font=('Arial', 11, 'bold')
        )
        
        # Remove borders
        self.style.layout("Custom.Treeview", [
            ('Custom.Treeview.treearea', {'sticky': 'nswe'})
        ])
        
        # Configure selection colors
        self.style.map('Custom.Treeview',
            background=[('selected', '#404040')],
            foreground=[('selected', 'white')]
        )

        # Create frame for the treeview
        self.frame = tk.Frame(self, bg='#1e1e1e')
        self.frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)

        # Create scrollbar
        self.scrollbar = ttk.Scrollbar(self.frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create treeview with custom style
        columns = ("Date", "BTC Price", "EUR Amount", "BTC Amount")
        self.tree = ttk.Treeview(
            self.frame, 
            columns=columns, 
            show='headings',
            style="Custom.Treeview",
            yscrollcommand=self.scrollbar.set
        )
        
        # Configure scrollbar
        self.scrollbar.config(command=self.tree.yview)
        
        # Set column headings and widths
        column_widths = {
            "Date": 200,
            "BTC Price": 200,
            "EUR Amount": 200,
            "BTC Amount": 200
        }
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=column_widths[col], anchor='center')

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add a title label
        self.title_label = tk.Label(
            self,
            text="Bitcoin Purchase History",
            font=('Arial', 16, 'bold'),
            bg='#1e1e1e',
            fg='white'
        )
        self.title_label.pack(pady=(20,0))

        # Create a frame for totals
        self.totals_frame = tk.Frame(self, bg='#1e1e1e')
        self.totals_frame.pack(pady=20, padx=20, fill=tk.X)

        # Load purchases and calculate totals
        self.load_purchases()

        # Update cycle
        self.update_pl_values()

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width/2) - (width/2)
        y = (screen_height/2) - (height/2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

    def load_purchases(self, current_btc_price=None):
        try:
            if current_btc_price is None:
                current_btc_price = self.parent.price_data[-1] if len(self.parent.price_data) > 0 else 0

            conn = sqlite3.connect('bitcoin_purchases.db')
            c = conn.cursor()
            
            c.execute("SELECT * FROM purchases ORDER BY timestamp DESC")
            rows = c.fetchall()
            
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            total_eur = 0
            total_btc = 0
            total_current_value = 0
            
            for i, row in enumerate(rows):
                total_eur += row[2]  # EUR amount
                total_btc += row[3]  # BTC amount
                
                # Calculate current value
                current_value = row[3] * current_btc_price
                total_current_value += current_value
                
                tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                self.tree.insert("", tk.END, values=(
                    row[0],
                    f"{row[1]:.2f} EUR",
                    f"{row[2]:.2f} EUR",
                    f"{row[3]:.8f} BTC"
                ), tags=(tag,))
            
            # Configure tag colors
            self.tree.tag_configure('evenrow', background='#2d2d2d')
            self.tree.tag_configure('oddrow', background='#363636')

            # Update totals frame with real-time P/L
            for widget in self.totals_frame.winfo_children():
                widget.destroy()

            # Calculate total profit/loss
            total_pl = total_current_value - total_eur
            pl_percentage = (total_pl / total_eur * 100) if total_eur > 0 else 0
            pl_color = '#00ff00' if total_pl >= 0 else '#ff4444'

            tk.Label(
                self.totals_frame,
                text=f"Total Invested: {total_eur:.2f} EUR",
                font=('Arial', 12, 'bold'),
                bg='#1e1e1e',
                fg='white'
            ).pack(side=tk.LEFT, padx=20)

            tk.Label(
                self.totals_frame,
                text=f"Total BTC: {total_btc:.8f} BTC",
                font=('Arial', 12, 'bold'),
                bg='#1e1e1e',
                fg='white'
            ).pack(side=tk.LEFT, padx=20)

            tk.Label(
                self.totals_frame,
                text=f"Current Value: {total_current_value:.2f} EUR",
                font=('Arial', 12, 'bold'),
                bg='#1e1e1e',
                fg='white'
            ).pack(side=tk.LEFT, padx=20)

            tk.Label(
                self.totals_frame,
                text=f"P/L: {total_pl:+.2f} EUR ({pl_percentage:+.2f}%)",
                font=('Arial', 12, 'bold'),
                bg='#1e1e1e',
                fg=pl_color
            ).pack(side=tk.LEFT, padx=20)
            
            conn.close()
            
        except Exception as e:
            print(f"Error loading purchases: {e}")


    def update_pl_values(self):
        try:
            current_btc_price = self.parent.price_data[-1] if len(self.parent.price_data) > 0 else 0
            self.load_purchases()  # Remove the parameter here
            # Schedule next update in 1 second
            self.after(1000, self.update_pl_values)
        except Exception as e:
            print(f"Error updating P/L: {e}")


if __name__ == "__main__":
    app = BitcoinTracker()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()