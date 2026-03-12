# 🚂 IRCTC Tatkal Fast Booker

Automated IRCTC Tatkal ticket booking with auto CAPTCHA solving, NTP-synced countdown, and stealth browser to avoid blocking.

---

## ⚡ Quick Start (3 Steps)

### Step 1: Install (One Time)
Double-click **`setup.bat`** or run:
```
pip install -r requirements.txt
```

### Step 2: Configure
Open **`config.json`** and update **ONLY these 3 fields**:
```json
"irctc_username": "your_actual_username",
"irctc_password": "your_actual_password",
"upi_id": "yourname@paytm",
```

Also update journey details (stations, date, train number, passengers).

### Step 3: Run
Double-click **`run_booking.bat`** or run:
```
python main.py
```

For **instant booking** (skip tatkal countdown):
```
python main.py --now
```

---

## 📁 File Structure

| File | Purpose |
|---|---|
| `config.json` | Your booking details (username, password, UPI, journey) |
| `main.py` | Entry point – run this |
| `booking_engine.py` | Core automation engine |
| `captcha_solver.py` | Auto CAPTCHA solving with OCR |
| `utils.py` | NTP clock, human-like delays, logging |
| `setup.bat` | One-click dependency installer |
| `run_booking.bat` | One-click launcher |
| `requirements.txt` | Python packages needed |

---

## 🛡️ Anti-Detection Features

| Feature | How |
|---|---|
| **Stealth Browser** | Uses `undetected-chromedriver` to bypass Cloudflare/bot checks |
| **Human-like Typing** | Random delays between keystrokes (30-90ms per char) |
| **Random Delays** | Small pauses between actions (80-250ms) |
| **Real Browser Profile** | Spoofs `navigator.webdriver`, plugins, languages |
| **NTP Sync** | Precise clock sync with `time.google.com` for exact tatkal window |

---

## ⚙️ Config Reference

### Required Fields
| Field | Example | Description |
|---|---|---|
| `irctc_username` | `myuser123` | IRCTC login username |
| `irctc_password` | `MyP@ss123` | IRCTC login password |
| `upi_id` | `myname@paytm` | Your UPI ID for payment |
| `from_station` | `NEW DELHI - NDLS` | Station name - CODE |
| `to_station` | `PATNA JN - PNBE` | Station name - CODE |
| `journey_date` | `25/03/2026` | DD/MM/YYYY format |
| `train_number` | `12301` | Train number |
| `travel_class` | `SL` | SL, 3A, 2A, 1A, CC, 2S |
| `quota` | `TQ` | TQ = Tatkal |
| `passengers` | (see config) | Array of passenger objects |
| `mobile_number` | `9999999999` | 10-digit mobile |

### Passenger Object
```json
{
    "name": "John Doe",
    "age": "30",
    "gender": "Male",
    "berth_preference": "Lower",
    "food_choice": "No Food"
}
```

- **Gender**: `Male`, `Female`, `Transgender`
- **Berth**: `Lower`, `Middle`, `Upper`, `Side Lower`, `Side Upper`, `No Preference`

### Optional Fields
| Field | Default | Description |
|---|---|---|
| `tatkal_type` | `NON_AC` | `AC` or `NON_AC` |
| `auto_upgrade` | `true` | Accept upgrade if available |
| `travel_insurance` | `false` | Skip travel insurance |
| `headless` | `false` | Run browser hidden (not recommended) |
| `login_before_minutes` | `10` | Login X minutes before tatkal window |
| `captcha_max_retries` | `10` | Max CAPTCHA solve attempts |

---

## 🕐 How Tatkal Timing Works

1. Bot syncs with NTP for precise IST time
2. Logs in **10 minutes before** tatkal window (configurable)
3. Pre-fills search form with journey details
4. At **exactly 10:00 AM IST** → instant search + book
5. Auto-fills passengers + payment
6. You just approve UPI on your phone

---

## 🔧 Troubleshooting

| Issue | Fix |
|---|---|
| Chrome not found | Install Google Chrome |
| CAPTCHA fails repeatedly | Bot retries automatically; falls back to manual input |
| Login blocked | Try again later; IRCTC may have rate limits |
| Train not found | Verify train number and date in config |
| Payment page changed | Complete payment manually (browser stays open) |

---

## ⚠️ Disclaimer

This tool is for **personal educational use only**. Use responsibly and in accordance with IRCTC's terms of service. The author is not responsible for any misuse or account-related issues.
