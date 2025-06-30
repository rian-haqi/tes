from binance import Client
from binance.exceptions import BinanceAPIException
import time
import os

# --- Inisialisasi API Key dan Secret ---
api_key = 'h60bcJUg263dLk90D1kH0STgNGKkfXaY8OyqMxXmPsev7ftyNquqxSSAa2XEN9NY'
api_secret = '8EwigWu0zaK9V1c3445C8w9z9HpcxMNof6EwjmT2yUAcGxNHMwiABASpi3d4Bbj1'

client = Client(api_key, api_secret)

# --- Input dari User ---
symbol = input("Masukkan simbol koin (contoh: BTCUSDT, ETHUSDT): ").upper()
amount_to_invest_usdt = float(input("Masukkan jumlah USDT yang ingin Anda gunakan untuk membeli: "))
stop_loss_percent = float(input("Masukkan persentase Stop Loss (misal 1 untuk 1%): ")) / 100
take_profit_percent = float(input("Masukkan persentase Take Profit (misal 2 untuk 2%): ")) / 100

# Variabel global
buy_price = 0
stop_loss = 0
take_profit = 0
auto_buy = False

# --- Fungsi ---
def get_balance(asset):
    """Mendapatkan saldo aset tertentu."""
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
    """Mendapatkan harga terkini dari simbol koin."""
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
    """Mendapatkan informasi filter (LOT_SIZE, MIN_NOTIONAL) untuk simbol."""
    filters = {}
    try:
        print(f"[DEBUG] Mencoba mendapatkan info untuk simbol: {symbol}")
        info = client.get_symbol_info(symbol)
        
        if info is None:
            print(f"[ERROR] API mengembalikan None untuk simbol {symbol}")
            return {}
        
        print(f"[DEBUG] Info simbol berhasil didapat. Keys available: {list(info.keys()) if isinstance(info, dict) else 'Not a dict'}")
        
        if 'filters' not in info:
            print(f"[ERROR] Info simbol {symbol} tidak memiliki field 'filters'")
            print(f"[DEBUG] Response structure: {info}")
            return {}
        
        print(f"[DEBUG] Jumlah filters ditemukan: {len(info['filters'])}")
        
        for i, f in enumerate(info['filters']):
            print(f"[DEBUG] Filter {i}: {f['filterType']}")
            if f['filterType'] == 'LOT_SIZE':
                filters['stepSize'] = float(f['stepSize'])
                print(f"[DEBUG] stepSize ditemukan: {f['stepSize']}")
            elif f['filterType'] == 'NOTIONAL':
                # Filter NOTIONAL bisa memiliki minNotional atau minQty
                if 'minNotional' in f:
                    filters['minNotional'] = float(f['minNotional'])
                    print(f"[DEBUG] minNotional ditemukan: {f['minNotional']}")
                elif 'minQty' in f:
                    # Beberapa API menggunakan minQty sebagai gantinya
                    filters['minNotional'] = float(f['minQty'])
                    print(f"[DEBUG] minNotional (dari minQty) ditemukan: {f['minQty']}")
                print(f"[DEBUG] NOTIONAL filter content: {f}")
            elif f['filterType'] == 'MIN_NOTIONAL':
                # Fallback untuk format lama
                filters['minNotional'] = float(f['minNotional'])
                print(f"[DEBUG] minNotional (format lama) ditemukan: {f['minNotional']}")
        
        if 'stepSize' not in filters:
            print("[WARNING] stepSize tidak ditemukan dalam filters")
        if 'minNotional' not in filters:
            print("[WARNING] minNotional tidak ditemukan dalam filters")
            # Jika tidak ada minNotional, gunakan nilai default kecil
            filters['minNotional'] = 1.0  # Default minimal 1 USDT
            print(f"[INFO] Menggunakan minNotional default: {filters['minNotional']}")
            
        print(f"[DEBUG] Filters yang berhasil didapat: {filters}")
        return filters
        
    except BinanceAPIException as e:
        print(f"[ERROR] Binance API Error saat mendapatkan info simbol {symbol}: {e}")
        print("Kemungkinan penyebab: API Key tidak valid, koneksi internet bermasalah, atau simbol tidak ada.")
        return {}
    except Exception as e:
        print(f"[ERROR] Error umum saat mendapatkan info simbol {symbol}: {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return {}

def adjust_quantity_to_lot_size(quantity, step_size):
    """Menyesuaikan kuantitas agar sesuai dengan step size (ukuran lot)."""
    if step_size == 0:
        return quantity
    # Pembulatan ke bawah untuk memastikan tidak melebihi saldo yang ada
    num_steps = int(quantity / step_size)
    return num_steps * step_size

def place_buy_order(symbol, quantity, min_notional):
    """Menempatkan order beli market."""
    try:
        current_price = get_current_price(symbol)
        if current_price == 0:
            print("Tidak dapat membeli: Harga saat ini belum didapatkan.")
            return 0

        # Hitung nilai notional (jumlah USDT) dari kuantitas yang diminta
        requested_notional = quantity * current_price

        # Sesuaikan kuantitas jika kurang dari MIN_NOTIONAL
        if requested_notional < min_notional:
            # Hitung kuantitas minimum yang diperlukan untuk memenuhi MIN_NOTIONAL
            min_quantity_for_notional = min_notional / current_price

            # Ambil step_size untuk memastikan pembulatan yang benar
            symbol_filters = get_symbol_filters(symbol)
            step_size = symbol_filters.get('stepSize', 0)

            # Sesuaikan min_quantity_for_notional ke step_size terdekat ke atas
            if step_size > 0:
                min_quantity_for_notional = (int(min_quantity_for_notional / step_size) + 1) * step_size

            print(f"Peringatan: Jumlah pembelian ({requested_notional:.2f} USDT) di bawah MIN_NOTIONAL ({min_notional:.2f} USDT).")
            print(f"Menyesuaikan kuantitas pembelian dari {quantity:.8f} menjadi {min_quantity_for_notional:.8f} {symbol.replace('USDT', '')} untuk memenuhi MIN_NOTIONAL.")
            quantity = min_quantity_for_notional

            # Jika saldo yang diinput (amount_to_invest_usdt) lebih kecil dari min_notional,
            # kita bisa memberi tahu pengguna bahwa kita membeli lebih dari yang mereka inginkan.
            # Ini adalah bagian yang perlu Anda putuskan apakah ingin otomatis beli lebih atau hentikan.
            # Untuk skenario ini, kita akan tetap mencoba beli MIN_NOTIONAL.


        # Pastikan kuantitas juga sesuai dengan aturan LOT_SIZE
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
    """Menempatkan order jual market."""
    try:
        current_price = get_current_price(symbol)
        if current_price == 0:
            print("Tidak dapat menjual: Harga saat ini belum didapatkan.")
            return False

        requested_notional = quantity * current_price

        if requested_notional < min_notional:
            # Jika saldo koin yang tersisa menghasilkan notional di bawah minimum,
            # Anda tidak akan bisa menjualnya (kecuali untuk beberapa kasus khusus seperti akun kecil).
            # Dalam skenario ini, kita akan memberitahu pengguna.
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

# --- Main Logic ---
def main():
    global buy_price, stop_loss, take_profit, auto_buy

    print("Memulai bot trading...")
    print(f"Mode Auto Buy: {'Aktif' if auto_buy else 'Nonaktif'}")
    print(f"Persentase Stop Loss: {stop_loss_percent * 100:.2f}%")
    print(f"Persentase Take Profit: {take_profit_percent * 100:.2f}%")

    coin_asset = symbol.replace('USDT', '')

    print(f"[INFO] Mendapatkan filter untuk simbol {symbol}...")
    
    # Retry mechanism untuk mendapatkan symbol filters
    max_retries = 3
    symbol_filters_data = {}
    
    for attempt in range(max_retries):
        print(f"[INFO] Percobaan {attempt + 1}/{max_retries} mendapatkan symbol filters...")
        symbol_filters_data = get_symbol_filters(symbol)
        
        if symbol_filters_data and 'stepSize' in symbol_filters_data and 'minNotional' in symbol_filters_data:
            print(f"[SUCCESS] Filter berhasil didapat!")
            break
        else:
            print(f"[WARNING] Percobaan {attempt + 1} gagal. Filter yang didapat: {symbol_filters_data}")
            if attempt < max_retries - 1:
                print(f"[INFO] Menunggu 5 detik sebelum percobaan berikutnya...")
                time.sleep(5)
    
    coin_step_size = symbol_filters_data.get('stepSize', 0)
    min_notional_value = symbol_filters_data.get('minNotional', 0)

    print(f"[INFO] stepSize: {coin_step_size}, minNotional: {min_notional_value}")

    if coin_step_size == 0 or min_notional_value == 0:
        print(f"\n❌ ERROR: Tidak dapat mendapatkan filter yang lengkap untuk {symbol}")
        print(f"stepSize: {coin_step_size}, minNotional: {min_notional_value}")
        print("\n🔧 SOLUSI YANG BISA DICOBA:")
        print("1. Periksa koneksi internet Anda")
        print("2. Coba restart program")
        print("3. Pastikan simbol ditulis dengan benar (contoh: ETHUSDT)")
        print("4. Coba simbol lain seperti BTCUSDT")
        print("5. Periksa status Binance API di https://binance.com/")
        print("\nProgram berhenti...")
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

            # Logic Auto Buy
            if auto_buy and current_price > 0:
                # Kuantitas target berdasarkan input amount_to_invest_usdt
                target_quantity_from_input = amount_to_invest_usdt / current_price
                adjusted_target_quantity = adjust_quantity_to_lot_size(target_quantity_from_input, coin_step_size)

                # Periksa apakah kita sudah memiliki koin dalam jumlah yang mendekati target investasi
                if coin_balance < adjusted_target_quantity * 0.99: # Membeli jika saldo koin jauh di bawah target
                    # Hitung notional yang dibutuhkan
                    required_notional = max(amount_to_invest_usdt, min_notional_value) # Ambil yang lebih besar

                    # Hitung kuantitas berdasarkan required_notional
                    quantity_to_buy = required_notional / current_price
                    adjusted_quantity_to_buy = adjust_quantity_to_lot_size(quantity_to_buy, coin_step_size)

                    # Jika setelah penyesuaian lot size, nilai pembelian kurang dari min_notional,
                    # maka kita harus meningkatkan quantity ke minimum notional yang valid.
                    # Ini penting karena `adjust_quantity_to_lot_size` membulatkan ke bawah.
                    if adjusted_quantity_to_buy * current_price < min_notional_value:
                        adjusted_quantity_to_buy = adjust_quantity_to_lot_size(min_notional_value / current_price + coin_step_size, coin_step_size) # Tambah step_size untuk memastikan pembulatan ke atas

                    if usdt_balance >= adjusted_quantity_to_buy * current_price * 1.001 and adjusted_quantity_to_buy > 0:
                        print(f"Membeli koin sejumlah {adjusted_quantity_to_buy} {coin_asset} (estimasi {adjusted_quantity_to_buy * current_price:.2f} USDT)...")
                        new_buy_price = place_buy_order(symbol, adjusted_quantity_to_buy, min_notional_value)
                        if new_buy_price > 0:
                            buy_price = new_buy_price
                            stop_loss = buy_price * (1 - stop_loss_percent)
                            take_profit = buy_price * (1 + take_profit_percent)
                            print(f"Pembelian berhasil! Harga beli rata-rata: {buy_price:.4f}")
                            print(f"Stop Loss di: {stop_loss:.4f}")
                            print(f"Take Profit di: {take_profit:.4f}")
                        else:
                            print("Gagal melakukan pembelian. Mungkin saldo tidak cukup atau ada batasan minimum.")
                    else:
                        print(f"Saldo USDT tidak cukup ({usdt_balance:.2f}) untuk membeli target {adjusted_quantity_to_buy:.4f} {coin_asset} seharga {adjusted_quantity_to_buy * current_price:.2f} USDT.")
                else:
                    print(f"Sudah memiliki cukup {coin_asset} ({coin_balance:.4f}) mendekati target pembelian ({adjusted_target_quantity:.4f}). Tidak melakukan pembelian.")
            elif auto_buy and current_price == 0:
                print("Harga saat ini belum didapatkan, tidak dapat melakukan pembelian otomatis.")

            # Logic Auto Sell
            if coin_balance > 0:
                if buy_price == 0 and current_price > 0:
                    buy_price = current_price
                    stop_loss = buy_price * (1 - stop_loss_percent)
                    take_profit = buy_price * (1 + take_profit_percent)
                    print(f"Menginisialisasi harga acuan penjualan: {buy_price:.4f}")
                    print(f"Stop Loss: {stop_loss:.4f} | Take Profit: {take_profit:.4f}")
                elif buy_price > 0 and current_price > 0:
                    if current_price <= stop_loss:
                        print(f"Stop loss tercapai ({current_price:.4f} <= {stop_loss:.4f}). Menjual seluruh {coin_asset}...")
                        if place_sell_order(symbol, coin_balance, min_notional_value):
                            buy_price = 0
                    elif current_price >= take_profit:
                        print(f"Take profit tercapai ({current_price:.4f} >= {take_profit:.4f}). Menjual seluruh {coin_asset}...")
                        if place_sell_order(symbol, coin_balance, min_notional_value):
                            buy_price = 0
                    else:
                        print(f"Menunggu kondisi jual: Harga saat ini ({current_price:.4f}) berada di antara SL ({stop_loss:.4f}) dan TP ({take_profit:.4f}).")
                elif current_price == 0:
                    print("Harga saat ini belum didapatkan, tidak dapat mengevaluasi kondisi jual.")
            else:
                if not auto_buy:
                    print(f"Tidak ada {coin_asset} di saldo Anda. Tidak ada yang bisa dijual.")
                else:
                    print(f"Saldo {coin_asset} nol dan bot dalam mode auto buy. Menunggu pembelian.")

            time.sleep(30)

        except BinanceAPIException as e:
            print(f"Error Binance API: {e}")
            time.sleep(60)
        except Exception as e:
            print(f"Terjadi error umum di main loop: {e}")
            time.sleep(60)

# --- Test Koneksi API ---
def test_api_connection():
    """Test koneksi API Binance"""
    try:
        print("Mengetes koneksi API Binance...")
        
        # Test 1: Cek status sistem Binance
        status = client.get_system_status()
        print(f"✓ Status sistem Binance: {status}")
        
        # Test 2: Cek info akun (memvalidasi API key & secret)
        account_info = client.get_account()
        print("✓ Koneksi API berhasil dan kredensial valid!")
        
        # Test 3: Cek apakah simbol yang diinput valid
        test_symbol_info = client.get_symbol_info(symbol)
        if test_symbol_info is None:
            print(f"✗ Simbol {symbol} tidak ditemukan atau tidak valid!")
            return False
        else:
            print(f"✓ Simbol {symbol} valid!")
        
        return True
    except BinanceAPIException as e:
        print(f"✗ Error koneksi API Binance: {e}")
        print("Periksa kembali API Key dan Secret Anda.")
        print("Pastikan juga API Key memiliki izin trading yang diperlukan.")
        return False
    except Exception as e:
        print(f"✗ Error umum saat test koneksi: {e}")
        print("Periksa koneksi internet Anda.")
        return False

# --- Jalankan Program ---
if __name__ == "__main__":
    print("=== BOT TRADING BINANCE ===")
    print("Sebelum memulai, mari kita test koneksi API...")
    
    # Test koneksi API terlebih dahulu
    if not test_api_connection():
        print("\n❌ Program dihentikan karena masalah koneksi API.")
        print("\nSolusi yang bisa dicoba:")
        print("1. Periksa API Key dan Secret di kode")
        print("2. Pastikan API Key memiliki izin trading")
        print("3. Periksa koneksi internet")
        print("4. Pastikan simbol koin ditulis dengan benar (contoh: ETHUSDT)")
        exit(1)
    
    print("\n✅ Semua test berhasil! Lanjut ke konfigurasi bot...\n")
    
    mode_input = input("Pilih mode (1: Auto Buy & Sell, 2: Sell Only): ")
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
