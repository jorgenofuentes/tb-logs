"""
export_data_mt5.py — Exporta historico OHLC de MT5 a CSV para backtesting.
=========================================================================
Uso (en el VPS, con MT5 abierto y logueado EN PEPPERSTONE 62133951):
    cd C:\\trading-bot\\logs
    python export_data_mt5.py

Salida: C:\\trading-bot\\logs\\data\\<SIMBOLO_REAL>_<TF>.csv  (ej. XAUUSD_SB_H1.csv)
(la carpeta logs\\ la sube el puente PushLogs a GitHub y Google Drive automaticamente)

v2 (2026-08): resuelve el sufijo del broker (_SB en Pepperstone) y añade indices
(NAS100, US30, US500) + mas temporalidades (M5, M15, M30, H1). Asi los ficheros
llevan el nombre real (XAUUSD_SB) y NO pisan los datos viejos de MetaQuotes.

Notas:
- Tiempos en epoch segundos, HORA DEL SERVIDOR del broker. Conversion a UTC en el analisis.
- Pide los datos por trozos anuales para esquivar el limite "Max bars".
- Si un simbolo no existe en este broker, lo salta y lo dice.
"""
import csv
import os
import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "data")

# Nombres BASE (el script resuelve el sufijo real del broker, p.ej. _SB en Pepperstone)
SYMBOLS = ["XAUUSD", "NAS100", "US30", "US500", "EURUSD", "GBPUSD", "USDJPY"]
YEAR_FROM = 2018


def resolve_symbol(requested):
    """Encuentra el nombre real tradeable a partir del nombre base (maneja _SB, .cash...)."""
    if mt5.symbol_info(requested) is not None:
        return requested
    all_syms = mt5.symbols_get()
    if not all_syms:
        return None
    req = requested.upper()
    names = [s.name for s in all_syms]
    exact = [n for n in names if n.upper() == req]
    starts = [n for n in names if n.upper().startswith(req)]
    contains = [n for n in names if req in n.upper()]
    for group in (exact, starts, contains):
        group.sort(key=len)
        for c in group:
            if mt5.symbol_info(c) is not None:
                return c
    return None


def main():
    if not mt5.initialize():
        sys.exit("[FATAL] mt5.initialize fallo: %s (¿MT5 abierto?)" % str(mt5.last_error()))

    acc = mt5.account_info()
    if acc is not None:
        print("Conectado a cuenta %s (%s)" % (acc.login, acc.server))

    tfs = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
           "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1}
    os.makedirs(OUT_DIR, exist_ok=True)
    year_now = datetime.now(timezone.utc).year
    resumen = []

    for base in SYMBOLS:
        symbol = resolve_symbol(base)
        if symbol is None:
            print("AVISO: simbolo %s no disponible en este broker; lo salto." % base)
            resumen.append((base, "-", 0, "no disponible"))
            continue
        if symbol != base:
            print("Simbolo %s -> %s" % (base, symbol))
        mt5.symbol_select(symbol, True)
        for tf_name, tf in tfs.items():
            rows = {}
            for year in range(YEAR_FROM, year_now + 1):
                d1 = datetime(year, 1, 1, tzinfo=timezone.utc)
                d2 = datetime(year + 1, 1, 10, tzinfo=timezone.utc)
                rates = mt5.copy_rates_range(symbol, tf, d1, d2)
                if rates is None or len(rates) == 0:
                    continue
                for r in rates:
                    rows[int(r[0])] = r
            if not rows:
                print("AVISO: %s %s sin datos." % (symbol, tf_name))
                resumen.append((symbol, tf_name, 0, "sin datos"))
                continue
            ts_sorted = sorted(rows.keys())
            path = os.path.join(OUT_DIR, "%s_%s.csv" % (symbol, tf_name))
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["time", "open", "high", "low", "close", "tick_volume", "spread"])
                for ts in ts_sorted:
                    r = rows[ts]
                    w.writerow([int(r[0]), r[1], r[2], r[3], r[4], int(r[5]), int(r[6])])
            first = datetime.fromtimestamp(ts_sorted[0], tz=timezone.utc).date()
            last = datetime.fromtimestamp(ts_sorted[-1], tz=timezone.utc).date()
            print("%s %s: %d velas (%s -> %s, hora servidor)" % (symbol, tf_name, len(ts_sorted), first, last))
            resumen.append((symbol, tf_name, len(ts_sorted), "%s->%s" % (first, last)))

    man = os.path.join(OUT_DIR, "manifest_pepperstone.csv")
    with open(man, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["symbol", "tf", "bars", "rango"])
        for row in resumen:
            w.writerow(row)

    mt5.shutdown()
    print("\nHecho. Archivos en %s" % OUT_DIR)
    print("Ahora sincroniza (Drive lo sube solo) o: Start-ScheduledTask -TaskName PushLogs")


if __name__ == "__main__":
    main()
