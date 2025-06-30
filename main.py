from binance import Client
from binance.exceptions import BinanceAPIException
import time
import os

# --- Inisialisasi API Key dan Secret ---
api_key = os.environ.get("BINANCE_API_KEY")
api_secret = os.environ.get("BINANCE_API_SECRET")

client = Client(api_key, api_secret)

def get_env_or_input(env_key, prompt, default=None):
    """
    Ambil dari environment variable jika ada,
    kalau tidak ada, fallback ke input().
    """
    val = os.environ.get(env_key)
    if val is not None:
        return val
    return input(prompt) if default is None else input(prompt) or default

# --- Input dari Environment atau Input() ---
symbol = get_env_or_input("SYMBOL", "Masukkan simbol koin (contoh: BTCUSDT, ETHUSDT): ").upper()
amount_to_invest_usdt = float(get_env_or_input("AMOUNT_USDT", "Masukkan jumlah USDT yang ingin Anda gunakan untuk membeli: "))
stop_loss_percent = float(get_env_or_input("STOP_LOSS_PERCENT", "Masukkan persentase Stop Loss (misal 1 untuk 1%): ")) / 100
take_profit_percent = float(get_env_or_input("TAKE_PROFIT_PERCENT", "Masukkan persentase Take Profit (misal 2 untuk 2%): ")) / 100

# Variabel global
buy_price = 0
stop_loss = 0
take_profit = 0
auto_buy = False

# --- Fungsi ---
def get_balance(asset):
    try:
        balance = client.get_asset_balance(asset=asset)
        return float(balance['free'])
    except BinanceAPIException as e:
        print(f"Error mendapatkan saldo {asset}: {e}")
        return 0
    except Exception as e:
        print(f"Terjadi error umum saat mendapatkan saldo {asset}: {e}")
        return 0

def get_current_price(symbol):
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except BinanceAPIException as e:
        print(f"Error mendapatkan harga {symbol}: {e}")
        return 0
    except Exception as e:
        print(f"Terjadi error umum saat mendapatkan harga {symbol}: {e}")
        return 0

def get_symbol_filters(symbol):
    filters = {}
    try:
        print(f"[DEBUG] Mencoba mendapatkan info untuk simbol: {symbol}")
        info = client.get_symbol_info(symbol)
        
        if info is None:
            print(f"[ERROR] API mengembalikan None untuk simbol {symbol}")
            return {}
        
        if 'filters' not in info:
            print(f"[ERROR] Info simbol {symbol} tidak memiliki field 'filters'")
            return {}
        
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                filters['stepSize'] = float(f['stepSize'])
            elif f['filterType'] == 'NOTIONAL':
                if 'minNotional' in f:
                    filters['minNotional'] = float(f['minNotional'])
                elif 'minQty' in f:
                    filters['minNotional'] = float(f['minQty'])
            elif f['filterType'] == 'MIN_NOTIONAL':
                filters['minNotional'] = float(f['minNotional'])

        if 'stepSize' not in filters:
            filters['stepSize'] = 0
        if 'minNotional' not in filters:
            filters['minNotional'] = 1.0
            
        return filters
        
    except BinanceAPIException as e:
        print(f"[ERROR] Binance API Error saat mendapatkan info simbol {symbol}: {e}")
        return {}
    except Exception as e:
        print(f"[ERROR] Error umum saat mendapatkan info simbol {symbol}: {e}")
        return {}

def adjust_quantity_to_lot_size(quantity, step_size):
    if step_size == 0:
        return quantity
    num_steps = int(quantity / step_size)
    return num_steps * step_size

def place_buy_order(symbol, quantity, min_notional):
    try:
        current_price = get_current_price(symbol)
        if current_price == 0:
            print("Tidak dapat membeli: Harga saat ini belum didapatkan.")
            return 0

        requested_notional = quantity * current_price

        if requested_notional < min_notional:
            min_quantity_for_notional = min_notional / current_price
            symbol_filters = get_symbol_filters(symbol)
            step_size = symbol_filters.get('stepSize', 0)
            if step_size > 0:
                min_quantity_for_notional = (int(min_quantity_for_notional / step_size) + 1) * step_size
            quantity = min_quantity_for_notional

        symbol_filters = get_symbol_filters(symbol)
        step_size = symbol_filters.get('stepSize', 0)
        adjusted_quantity = adjust_quantity_to_lot_size(quantity, step_size)

        if adjusted_quantity == 0:
            print("Kuantitas yang disesuaikan menjadi nol, tidak dapat melakukan pembelian.")
            return 0

        print(f"Mencoba membeli {adjusted_quantity} {symbol}...")
        order = client.order_market_buy(symbol=symbol, quantity=adjusted_quantity)
        print(f"Order pembelian berhasil: {order}")
        if 'fills' in order and len(order['fills']) > 0:
            total_price = sum(float(fill['price']) * float(fill['qty']) for fill in order['fills'])
            total_qty = sum(float(fill['qty']) for fill in order['fills'])
            return total_price / total_qty if total_qty > 0 else 0
        return 0
    except BinanceAPIException as e:
        print(f"Error saat membeli: {e}")
        return 0
    except Exception as e:
        print(f"Terjadi error umum saat membeli: {e}")
        return 0

def place_sell_order(symbol, quantity, min_notional):
    try:
        current_price = get_current_price(symbol)
        if current_price == 0:
            print("Tidak dapat menjual: Harga saat ini belum didapatkan.")
            return False

        requested_notional = quantity * current_price

        if requested_notional < min_notional:
            print(f"Peringatan: Jumlah penjualan ({requested_notional:.2f} USDT) di bawah MIN_NOTIONAL ({min_notional:.2f} USDT).")
            print("Tidak dapat menjual jumlah ini. Anda mungkin perlu mengumpulkan lebih banyak koin atau mempertimbangkan pasangan perdagangan lain.")
            return False

        symbol_filters = get_symbol_filters(symbol)
        step_size = symbol_filters.get('stepSize', 0)
        adjusted_quantity = adjust_quantity_to_lot_size(quantity, step_size)

        if adjusted_quantity == 0:
            print("Kuantitas yang disesuaikan menjadi nol, tidak dapat melakukan penjualan.")
            return False

        print(f"Mencoba menjual {adjusted_quantity} {symbol}...")
        order = client.order_market_sell(symbol=symbol, quantity=adjusted_quantity)
        print(f"Order penjualan berhasil: {order}")
        return True
    except BinanceAPIException as e:
        print(f"Error saat menjual: {e}")
        return False
    except Exception as e:
        print(f"Terjadi error umum saat menjual: {e}")
        return False

def main():
    global buy_price, stop_loss, take_profit, auto_buy

    print("Memulai bot trading...")
    print(f"Mode Auto Buy: {'Aktif' if auto_buy else 'Nonaktif'}")
    print(f"Persentase Stop Loss: {stop_loss_percent * 100:.2f}%")
    print(f"Persentase Take Profit: {take_profit_percent * 100:.2f}%")

    coin_asset = symbol.replace('USDT', '')

    max_retries = 3
    symbol_filters_data = {}
    for attempt in range(max_retries):
        symbol_filters_data = get_symbol_filters(symbol)
        if symbol_filters_data and 'stepSize' in symbol_filters_data and 'minNotional' in symbol_filters_data:
            break
        time.sleep(5)
    
    coin_step_size = symbol_filters_data.get('stepSize', 0)
    min_notional_value = symbol_filters_data.get('minNotional', 0)

    if coin_step_size == 0 or min_notional_value == 0:
        print(f"\n❌ ERROR: Tidak dapat mendapatkan filter yang lengkap untuk {symbol}")
        return

    while True:
        try:
            usdt_balance = get_balance('USDT')
            coin_balance = get_balance(coin_asset)
            current_price = get_current_price(symbol)

            print(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
            print(f"[Info] Saldo USDT: {usdt_balance:.4f} | Saldo {coin_asset}: {coin_balance:.4f} | Harga {symbol} saat ini: {current_price:.4f}")
            if buy_price > 0:
                print(f"[Info] Harga Beli: {buy_price:.4f} | Stop Loss: {stop_loss:.4f} | Take Profit: {take_profit:.4f}")

            if auto_buy and current_price > 0:
                target_quantity = amount_to_invest_usdt / current_price
                adjusted_quantity = adjust_quantity_to_lot_size(target_quantity, coin_step_size)
                if coin_balance < adjusted_quantity * 0.99:
                    if usdt_balance >= adjusted_quantity * current_price * 1.001 and adjusted_quantity > 0:
                        new_buy_price = place_buy_order(symbol, adjusted_quantity, min_notional_value)
                        if new_buy_price > 0:
                            buy_price = new_buy_price
                            stop_loss = buy_price * (1 - stop_loss_percent)
                            take_profit = buy_price * (1 + take_profit_percent)
            if coin_balance > 0:
                if buy_price == 0 and current_price > 0:
                    buy_price = current_price
                    stop_loss = buy_price * (1 - stop_loss_percent)
                    take_profit = buy_price * (1 + take_profit_percent)
                elif buy_price > 0 and current_price > 0:
                    if current_price <= stop_loss:
                        if place_sell_order(symbol, coin_balance, min_notional_value):
                            buy_price = 0
                    elif current_price >= take_profit:
                        if place_sell_order(symbol, coin_balance, min_notional_value):
                            buy_price = 0

            time.sleep(30)

        except BinanceAPIException as e:
            print(f"Error Binance API: {e}")
            time.sleep(60)
        except Exception as e:
            print(f"Terjadi error umum di main loop: {e}")
            time.sleep(60)

def test_api_connection():
    try:
        print("Mengetes koneksi API Binance...")
        status = client.get_system_status()
        print(f"✓ Status sistem Binance: {status}")
        account_info = client.get_account()
        print("✓ Koneksi API berhasil dan kredensial valid!")
        test_symbol_info = client.get_symbol_info(symbol)
        if test_symbol_info is None:
            print(f"✗ Simbol {symbol} tidak ditemukan atau tidak valid!")
            return False
        else:
            print(f"✓ Simbol {symbol} valid!")
        return True
    except BinanceAPIException as e:
        print(f"✗ Error koneksi API Binance: {e}")
        return False
    except Exception as e:
        print(f"✗ Error umum saat test koneksi: {e}")
        return False

if __name__ == "__main__":
    print("=== BOT TRADING BINANCE ===")
    print("Sebelum memulai, mari kita test koneksi API...")
    if not test_api_connection():
        print("\n❌ Program dihentikan karena masalah koneksi API.")
        exit(1)

    mode_input = get_env_or_input("MODE", "Pilih mode (1: Auto Buy & Sell, 2: Sell Only): ", default="1")
    if mode_input == '2':
        auto_buy = False
        print("Mode: Hanya Jual (Sell Only) diaktifkan. Bot akan menunggu Anda memiliki koin.")
    elif mode_input == '1':
        auto_buy = True
        print("Mode: Beli Otomatis & Jual Otomatis (Auto Buy & Sell) diaktifkan.")
    else:
        print("Pilihan tidak valid. Menggunakan mode default: Auto Buy & Sell.")
        auto_buy = True

    main()
