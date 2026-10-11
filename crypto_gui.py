import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from datetime import datetime
import requests

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

# ---------------- SETTINGS ----------------
API_URL = "https://api.coingecko.com/api/v3/simple/price"
CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"

PARAMS = {
    "ids": "bitcoin,ethereum,solana,dogecoin",
    "vs_currencies": "usd",
    "include_24hr_change": "true",
    "include_market_cap": "true",
}

COINS = {
    "bitcoin": {"name": "Bitcoin", "symbol": "BTC"},
    "ethereum": {"name": "Ethereum", "symbol": "ETH"},
    "solana": {"name": "Solana", "symbol": "SOL"},
    "dogecoin": {"name": "Dogecoin", "symbol": "DOGE"},
}
REFRESH_MS = 60_000

BG = "#101820"
PANEL = "#1b2733"
FG = "#f2f5f7"
MUTED = "#aab7c4"
GREEN = "#35d07f"
RED = "#ff6877"
ACCENT = "#55b7ff"


class CryptoTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova Crypto Tracker")
        self.root.geometry("1050x760")
        self.root.minsize(850, 620)
        self.root.configure(bg=BG)

        self.prices = {}
        self.favorites = set()
        self.alerts = {}
        self.busy = False
        self.chart_busy = False
        self.show_favorites = tk.BooleanVar(value=False)
        self.search_text = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready â click Refresh prices to begin.")
        self.auto_refresh = tk.BooleanVar(value=True)
        self.chart_days = tk.StringVar(value="7")

        self._build_ui()
        self.search_text.trace_add("write", lambda *_: self._render_coins())
        self.root.after(500, self.refresh_prices)
        self.root.after(REFRESH_MS, self._auto_refresh_tick)

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 10))
        tk.Label(header, text="â NOVA CRYPTO", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 22, "bold")).pack(side="left")
        tk.Label(header, text="LIVE MARKET DASHBOARD", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=15, pady=(9, 0))

        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=22, pady=8)
        tk.Label(controls, text="Search", bg=BG, fg=FG).pack(side="left")
        tk.Entry(controls, textvariable=self.search_text, width=22,
                 bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                 font=("Segoe UI", 11)).pack(side="left", padx=(8, 14), ipady=7)
        tk.Checkbutton(controls, text="Favorites only", variable=self.show_favorites,
                       command=self._render_coins, bg=BG, fg=FG,
                       selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG).pack(side="left")
        tk.Checkbutton(controls, text="Auto-refresh (60 sec)", variable=self.auto_refresh,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG).pack(side="left", padx=12)
        self.refresh_button = tk.Button(
            controls, text="â» Refresh prices", command=self.refresh_prices,
            bg=ACCENT, fg="#08131d", activebackground="#8bd0ff",
            relief="flat", padx=14, pady=8, font=("Segoe UI", 10, "bold"))
        self.refresh_button.pack(side="right")

        summary = tk.Frame(self.root, bg=PANEL)
        summary.pack(fill="x", padx=22, pady=(8, 12))
        self.summary_price = tk.Label(summary, text="Market prices loadingâ¦",
                                      bg=PANEL, fg=FG, font=("Segoe UI", 15, "bold"))
        self.summary_price.pack(side="left", padx=16, pady=15)
        self.updated_label = tk.Label(summary, text="Not updated yet",
                                      bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.updated_label.pack(side="right", padx=16)

        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=22, pady=(0, 10))
        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(left, text="WATCHLIST", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))
        self.coin_list = tk.Frame(left, bg=BG)
        self.coin_list.pack(fill="both", expand=True)

        right = tk.Frame(content, bg=PANEL)
        right.pack(side="right", fill="both", expand=True)
        chart_header = tk.Frame(right, bg=PANEL)
        chart_header.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(chart_header, text="PRICE HISTORY", bg=PANEL, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        self.chart_coin = tk.StringVar(value="bitcoin")
        coin_menu = ttk.Combobox(chart_header, textvariable=self.chart_coin,
                                 values=list(COINS.keys()), state="readonly", width=12)
        coin_menu.pack(side="right")
        coin_menu.bind("<<ComboboxSelected>>", lambda _e: self.load_chart())
        period = ttk.Combobox(chart_header, textvariable=self.chart_days,
                               values=["1", "7", "30"], state="readonly", width=5)
        period.pack(side="right", padx=8)
        period.bind("<<ComboboxSelected>>", lambda _e: self.load_chart())

        self.chart_frame = tk.Frame(right, bg=PANEL)
        self.chart_frame.pack(fill="both", expand=True, padx=8, pady=8)
        if not CHARTS_AVAILABLE:
            tk.Label(self.chart_frame,
                     text="Charts need Matplotlib.\nInstall it with:\npython -m pip install matplotlib",
                     bg=PANEL, fg=MUTED, justify="center",
                     font=("Segoe UI", 11)).pack(expand=True)
        else:
            self.chart_placeholder = tk.Label(self.chart_frame,
                                              text="Choose a coin to load its chart",
                                              bg=PANEL, fg=MUTED)
            self.chart_placeholder.pack(expand=True)

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=22, pady=(0, 15))
        tk.Label(footer, textvariable=self.status_text, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Button(controls, text="Set price alert", command=self.set_alert,
          bg=PANEL, fg=FG, relief="flat", padx=12, pady=7).pack(side="right", padx=10)

    def _render_coins(self):
        for widget in self.coin_list.winfo_children():
            widget.destroy()
        query = self.search_text.get().strip().lower()
        count = 0
        for coin_id, info in COINS.items():
            if self.show_favorites.get() and coin_id not in self.favorites:
                continue
            if query and query not in coin_id and query not in info["name"].lower() and query not in info["symbol"].lower():
                continue
            count += 1
            data = self.prices.get(coin_id, {})
            price = data.get("usd")
            change = data.get("usd_24h_change")
            cap = data.get("usd_market_cap")
            card = tk.Frame(self.coin_list, bg=PANEL, padx=12, pady=10)
            card.pack(fill="x", pady=5)
            top = tk.Frame(card, bg=PANEL)
            top.pack(fill="x")
            tk.Label(top, text=f'{info["name"]}  ({info["symbol"]})',
                     bg=PANEL, fg=FG, font=("Segoe UI", 11, "bold")).pack(side="left")
            fav_text = "â" if coin_id in self.favorites else "â"
            tk.Button(top, text=fav_text, command=lambda c=coin_id: self.toggle_favorite(c),
                      bg=PANEL, fg="#ffd166", relief="flat",
                      font=("Segoe UI", 15)).pack(side="right")
            price_text = f"${price:,.6f}" if price is not None and price < 1 else (f"${price:,.2f}" if price is not None else "Loadingâ¦")
            tk.Label(card, text=price_text, bg=PANEL, fg=FG,
                     font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(7, 1))
            change_text = "24h: unavailable" if change is None else f"24h: {change:+.2f}%"
            tk.Label(card, text=change_text, bg=PANEL,
                     fg=MUTED if change is None else (GREEN if change >= 0 else RED),
                     font=("Segoe UI", 10)).pack(anchor="w")
            if cap is not None:
                tk.Label(card, text=f"Market cap: ${cap:,.0f}", bg=PANEL,
                         fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
            tk.Button(card, text="View history", command=lambda c=coin_id: self.select_chart_coin(c),
                      bg="#263746", fg=FG, relief="flat", padx=8, pady=4).pack(anchor="e", pady=(5, 0))
        if count == 0:
            tk.Label(self.coin_list, text="No coins match your search.",
                     bg=BG, fg=MUTED).pack(anchor="w", pady=10)

    def toggle_favorite(self, coin_id):
        if coin_id in self.favorites:
            self.favorites.remove(coin_id)
        else:
            self.favorites.add(coin_id)
        self._render_coins()

    def select_chart_coin(self, coin_id):
        self.chart_coin.set(coin_id)
        self.load_chart()

    def refresh_prices(self):
        if self.busy:
            return
        self.busy = True
        self.refresh_button.config(state="disabled", text="Refreshingâ¦")
        self.status_text.set("Fetching latest pricesâ¦")
        threading.Thread(target=self._fetch_prices_worker, daemon=True).start()

    def _fetch_prices_worker(self):
        try:
            response = requests.get(API_URL, params=PARAMS, timeout=15)
            response.raise_for_status()
            data = response.json()
            self.root.after(0, lambda d=data: self._on_prices_success(d))
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): self._on_prices_error(e))

    def _on_prices_success(self, data):
        self.prices = data
        self._render_coins()
        self.summary_price.config(text=f"{len(self.prices)} coins tracked")
        now = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
        self.updated_label.config(text=f"Updated {now}")
        self.status_text.set("Market data updated successfully.")
        self.busy = False
        self.refresh_button.config(state="normal", text="â» Refresh prices")
        self._check_alerts()
        self.load_chart()

    def _on_prices_error(self, error):
        self.busy = False
        self.refresh_button.config(state="normal", text="â» Refresh prices")
        self.status_text.set("Could not update prices. Check your internet connection.")
        messagebox.showerror("Price update failed", f"Unable to retrieve market prices.\n\n{error}")

    def _auto_refresh_tick(self):
        if self.auto_refresh.get():
            self.refresh_prices()
        self.root.after(REFRESH_MS, self._auto_refresh_tick)

    def set_alert(self):
        choices = [f'{v["name"]} ({k})' for k, v in COINS.items()]
        selected = simpledialog.askstring(
            "Price alert", "Enter a coin ID:\nbitcoin, ethereum, solana, or dogecoin",
            parent=self.root)
        if not selected:
            return
        coin_id = selected.strip().lower()
        if coin_id not in COINS:
            messagebox.showinfo("Unknown coin", "Please enter bitcoin, ethereum, solana, or dogecoin.")
            return
        target = simpledialog.askfloat("Price alert", f"Alert me when {COINS[coin_id]['name']} reaches (USD):",
                                       parent=self.root, minvalue=0.00000001)
        if target is None:
            return
        self.alerts[coin_id] = target
        self.status_text.set(f"Alert set: {COINS[coin_id]['name']} at ${target:,.4f}")
        messagebox.showinfo("Alert set", f"You'll be notified when {COINS[coin_id]['name']} reaches ${target:,.4f} or higher.")

    def _check_alerts(self):
        triggered = []
        for coin_id, target in list(self.alerts.items()):
            price = self.prices.get(coin_id, {}).get("usd")
            if price is not None and price >= target:
                triggered.append((coin_id, price, target))
                del self.alerts[coin_id]
        for coin_id, price, target in triggered:
            messagebox.showinfo("Crypto price alert",
                                f'{COINS[coin_id]["name"]} is now ${price:,.4f}.\nYour target was ${target:,.4f}.')

    def load_chart(self):
        if not CHARTS_AVAILABLE or self.chart_busy:
            return
        coin_id = self.chart_coin.get()
        days = self.chart_days.get()
        if coin_id not in COINS:
            return
        self.chart_busy = True
        self.status_text.set(f"Loading {COINS[coin_id]['name']} historyâ¦")
        threading.Thread(target=self._fetch_chart_worker, args=(coin_id, days), daemon=True).start()

    def _fetch_chart_worker(self, coin_id, days):
        try:
            url = CHART_URL.format(coin_id=coin_id)
            response = requests.get(url, params={"vs_currency": "usd", "days": days}, timeout=20)
            response.raise_for_status()
            prices = response.json().get("prices", [])
            self.root.after(0, lambda p=prices, c=coin_id, d=days: self._draw_chart(p, c, d))
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): self._chart_error(e))

    def _draw_chart(self, points, coin_id, days):
        try:
            for widget in self.chart_frame.winfo_children():
                widget.destroy()
            if not points:
                tk.Label(self.chart_frame, text="No chart data available.",
                         bg=PANEL, fg=MUTED).pack(expand=True)
                return
            values = [point[1] for point in points]
            times = list(range(len(values)))
            fig = Figure(figsize=(5.1, 4.0), dpi=100, facecolor=PANEL)
            ax = fig.add_subplot(111)
            ax.set_facecolor(PANEL)
            ax.plot(times, values, linewidth=2, color="#55b7ff")
            ax.set_title(f'{COINS[coin_id]["name"]} â {days} day(s)', color=FG, fontsize=11)
            ax.set_ylabel("Price (USD)", color=MUTED)
            ax.tick_params(colors=MUTED, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color("#536271")
            ax.grid(True, alpha=0.2)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self.status_text.set(f"Loaded {COINS[coin_id]['name']} historical chart.")
        finally:
            self.chart_busy = False

    def _chart_error(self, error):
        self.chart_busy = False
        self.status_text.set("Chart could not be loaded.")
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        tk.Label(self.chart_frame, text=f"Could not load chart.\n{error}",
                 bg=PANEL, fg=MUTED, wraplength=350).pack(expand=True)


if __name__ == "__main__":
    root = tk.Tk()
    app = CryptoTracker(root)
    root.mainloop()