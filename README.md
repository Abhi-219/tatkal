# 🚂 IRCTC Tatkal Fast Booker

Automated IRCTC Tatkal ticket booking with auto CAPTCHA solving, NTP-synced countdown, and stealth browser to avoid blocking.

---

## 📋 Prerequisites

- **Python 3.9+** — [Download](https://python.org) (check "Add Python to PATH" during install)
- **Google Chrome** — latest version installed on your PC
- **Windows 10/11** — batch scripts are Windows-only (Python scripts work cross-platform)

---

## ⚡ Quick Start (3 Steps)

### Step 1: Install (One Time)
Double-click **`setup.bat`** or run:
```
pip install -r requirements.txt
```

### Step 2: Configure
Open **`config.json`** and fill in your details:
```json
"irctc_username": "your_actual_username",
"irctc_password": "your_actual_password",
"upi_id": "yourname@paytm",
```

Also update journey details — stations, date, train number, and passengers.

### Step 3: Run
Double-click **`run_booking.bat`** or run:
```
python main.py
```

For **instant booking** (skip tatkal countdown):
```
python main.py --now
```

> **Tip:** Use `--now` for testing or when you want to book immediately without waiting for the 10:00 AM tatkal window.

---

## 📁 File Structure

| File | Purpose |
|---|---|
| `config.json` | Your booking details (username, password, UPI, journey) |
| `main.py` | Entry point – run this |
| `booking_engine.py` | Core Selenium automation engine |
| `captcha_solver.py` | Auto CAPTCHA solving with ddddocr + PIL preprocessing |
| `utils.py` | NTP clock sync, human-like delays, logging setup |
| `setup.bat` | One-click dependency installer (Windows) |
| `run_booking.bat` | One-click launcher (Windows) |
| `requirements.txt` | Python packages needed |
| `tatkal_bot.log` | Log file (auto-created on each run) |

---

## 🛡️ Anti-Detection Features

| Feature | How |
|---|---|
| **Stealth Browser** | Uses `undetected-chromedriver` to bypass Cloudflare/bot checks |
| **Human-like Typing** | Random delays between keystrokes (30–90ms per char) |
| **Random Delays** | Small pauses between actions (80–250ms) |
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
| `from_station` | `NDLS` or `NEW DELHI - NDLS` | Station code (or full name with code) |
| `to_station` | `PNBE` or `PATNA JN - PNBE` | Station code (or full name with code) |
| `journey_date` | `25/03/2026` | DD/MM/YYYY format |
| `train_number` | `12301` | Train number |
| `travel_class` | `SL` | SL, 3A, 2A, 1A, 3E, CC, 2S, EV |
| `quota` | `TQ` | TQ = Tatkal |
| `passengers` | *(see below)* | Array of passenger objects |
| `mobile_number` | `9999999999` | 10-digit mobile number |

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
- **Food**: `No Food`, `Veg`, `Non Veg` (applicable for select trains only)

### Optional Fields
| Field | Default | Description |
|---|---|---|
| `tatkal_type` | `NON_AC` | `AC` or `NON_AC` |
| `auto_upgrade` | `true` | Accept class upgrade if available |
| `travel_insurance` | `false` | Skip travel insurance |
| `headless` | `false` | Run browser hidden (not recommended for debugging) |
| `login_before_minutes` | `10` | Login X minutes before tatkal window |
| `captcha_max_retries` | `10` | Max auto CAPTCHA solve attempts before manual fallback |
| `ntp_server` | `time.google.com` | NTP server for clock sync |

---

## 🕐 How Tatkal Timing Works

1. Bot syncs with NTP for precise IST time
2. Logs in **10 minutes before** tatkal window (configurable via `login_before_minutes`)
3. Pre-fills search form with journey details
4. At **exactly 10:00 AM IST** → instant search + book
5. Auto-fills passengers + payment
6. You just approve UPI on your phone 📱

> Both AC and Non-AC tatkal bookings open at **10:00 AM IST**.

---

## 🔧 Troubleshooting

| Issue | Fix |
|---|---|
| Chrome not found | Install [Google Chrome](https://www.google.com/chrome/) |
| ChromeDriver version mismatch | `undetected-chromedriver` auto-downloads the correct version |
| CAPTCHA fails repeatedly | Bot retries up to 10 times; falls back to manual input in console |
| Login blocked | Try again later; IRCTC may have rate limits |
| Train not found | Verify train number and date in config; ensure the train runs on that day |
| Payment page changed | Complete payment manually — browser stays open |
| NTP sync failed | Ensure internet access; bot falls back to system clock |

---

## 🔒 Security Note

Your `config.json` contains sensitive credentials (IRCTC password, UPI ID). **Do not share or commit this file to version control.** A `.gitignore` file is included to prevent accidental commits.

---

## ⚠️ Disclaimer

This tool is for **personal educational use only**. Use responsibly and in accordance with IRCTC's terms of service. The author is not responsible for any misuse or account-related issues.
