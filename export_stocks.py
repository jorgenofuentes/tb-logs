"""
export_stocks.py — Exporta histórico de ACCIONES desde MT5 para backtest.
=========================================================================
Uso (en el VPS, con MT5 abierto y logueado en Pepperstone 62133951):
    cd C:\\trading-bot\\logs
    python export_stocks.py

Solo M30 y H1 (rápido; H1 es lo que testeamos). Resuelve el sufijo del broker.
Si una acción no existe en Pepperstone, la salta y lo dice.
Salida: logs\\data\\<SIMBOLO_REAL>_<TF>.csv
"""
import csv
import os
import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "data")

# Acciones grandes y líquidas (el resolvedor busca el nombre real: AAPL.US, #AAPL, etc.)
SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "NFLX", "JPM"]
YEAR_FROM = 2018


def resolve_symbol(requested):
    if mt5.symbol_info(requested) is not None:
        return requested
    all_syms = mt5.symbols_get()
    if not all_syms:
        return None
    req = requested.upper()
    names = [s.name for s in all_syms]
    for group in ([n for n in names if n.upper() == req],
                  [n for n in names if n.upper().startswith(req)],
                  [n for n in names if req in n.upper()]):
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

    tfs = {"M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1}
    os.makedirs(OUT_DIR, exist_ok=True)
    year_now = datetime.now(timezone.utc).year
    resumen = []

    for base in SYMBOLS:
        symbol = resolve_symbol(base)
        if symbol is None:
            print("AVISO: accion %s no disponible en este broker; la salto." % base)
            resumen.append((base, "-", 0, "no disponible"))
            continue
        if symbol != base:
            print("%s -> %s" % (base, symbol))
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
                continue
            ts_sorted = sorted(rows.keys())
            path = os.path.join(OUT_DIR, "%s_%s.csv" % (symbol.replace(".", "_"), tf_name))
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["time", "open", "high", "low", "close", "tick_volume", "spread"])
                for ts in ts_sorted:
                    r = rows[ts]
                    w.writerow([int(r[0]), r[1], r[2], r[3], r[4], int(r[5]), int(r[6])])
            first = datetime.fromtimestamp(ts_sorted[0], tz=timezone.utc).date()
            last = datetime.fromtimestamp(ts_sorted[-1], tz=timezone.utc).date()
            print("%s %s: %d velas (%s -> %s)" % (symbol, tf_name, len(ts_sorted), first, last))
            resumen.append((symbol, tf_name, len(ts_sorted), "%s->%s" % (first, last)))

    mt5.shutdown()
    print("\nHecho. Archivos en %s" % OUT_DIR)
    print("Símbolos con datos:", sorted(set(s for s, tf, n, r in resumen if n > 0)))


if __name__ == "__main__":
    main()
