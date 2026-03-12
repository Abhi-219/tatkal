"""
╔══════════════════════════════════════════════════════════════╗
║          IRCTC TATKAL TICKET BOOKING – FAST BOOKER          ║
║                                                              ║
║  Usage:                                                      ║
║    1. Edit config.json (username, password, UPI, journey)    ║
║    2. Run:  python main.py                                   ║
║    3. Approve UPI payment on your phone                      ║
║                                                              ║
║  For instant booking (skip countdown):                       ║
║    python main.py --now                                      ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import os
import json

# Ensure we're in the script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from utils import setup_logging
from booking_engine import TatkalBooker

logger = setup_logging()


def validate_config():
    """Check that the user has filled in their details."""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        print("❌ config.json not found! Copy config.json and fill in your details.")
        sys.exit(1)

    with open(config_path, "r") as f:
        cfg = json.load(f)

    errors = []
    if cfg.get("irctc_username", "").startswith("YOUR_"):
        errors.append("  ⚠️  Set your IRCTC username in config.json")
    if cfg.get("irctc_password", "").startswith("YOUR_"):
        errors.append("  ⚠️  Set your IRCTC password in config.json")
    if cfg.get("upi_id", "").endswith("@upi"):
        errors.append("  ⚠️  Set your real UPI ID in config.json")
    if cfg.get("from_station", "") == "NEW DELHI - NDLS":
        errors.append("  ⚠️  Update from_station in config.json (still default)")
    if cfg.get("passengers", [{}])[0].get("name", "").startswith("Passenger"):
        errors.append("  ⚠️  Update passenger name in config.json")

    if errors:
        print("\n" + "=" * 55)
        print("  ⚡ CONFIG CHECK – Please fix before running:")
        print("=" * 55)
        for e in errors:
            print(e)
        print("=" * 55)
        resp = input("\nContinue anyway? (y/N): ").strip().lower()
        if resp != "y":
            sys.exit(0)

    return cfg


def print_banner(cfg):
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║            🚂 IRCTC TATKAL FAST BOOKER 🚂              ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  User  : {cfg['irctc_username']:<47} ║")
    print(f"║  Route : {cfg['from_station'][:20]} → {cfg['to_station'][:20]:<24} ║")
    print(f"║  Date  : {cfg['journey_date']:<47} ║")
    print(f"║  Train : {cfg['train_number']:<47} ║")
    print(f"║  Class : {cfg['travel_class']:<47} ║")
    booking_type = cfg.get('booking_type', 'TATKAL').upper()
    print(f"║  Type  : {booking_type:<47} ║")
    print(f"║  UPI   : {cfg['upi_id']:<47} ║")
    pax_names = ", ".join([p["name"] for p in cfg["passengers"]])
    print(f"║  Pax   : {pax_names[:47]:<47} ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


def main():
    cfg = validate_config()
    print_banner(cfg)

    instant_mode = "--now" in sys.argv

    if instant_mode:
        logger.info("⚡ INSTANT MODE – skipping tatkal countdown, booking NOW.")

    booker = TatkalBooker("config.json")

    if instant_mode:
        # Skip countdown – login and book immediately
        try:
            booker.login()
            booker.search_train()
            booker.select_train()
            booker.solve_booking_captcha()
            booker.fill_passengers()
            booker.make_payment()
            logger.info("🎉 Booking flow complete!")
            input("\nPress ENTER to close browser...")
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")
            print("The browser is still open. You can complete the booking manually.")
            input("Press ENTER to close browser...")
        finally:
            if booker.driver:
                try:
                    booker.driver.quit()
                except Exception:
                    pass
    else:
        booker.run()


if __name__ == "__main__":
    main()
