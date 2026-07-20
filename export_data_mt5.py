"""
export_data_mt5.py — Exporta historico OHLC de MT5 a CSV para backtesting.
=========================================================================
Uso (en el VPS, con MT5 abierto y logueado):
    python export_data_mt5.py

Salida: C:\\trading-bot\\logs\\data\\<SIMBOLO>_<TF>.csv
(la carpeta logs\\ la sube el puente PushLogs a GitHub automaticamente)

Notas:
- Los tiempos se exportan en epoch segundos en HORA DEL SERVIDOR del broker
  (MetaQuotes ~UTC+2/+3). La conversion a UTC se hace en el analisis, igual
  que en el backtest v0.2 (validada por aperturas semanales).
- Pide los datos por trozos anuales para esquivar el limite "Max bars".
- Si un simbolo no existe en este broker, lo salta y lo dice.
"""
import csv
import os
import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "data")  # el script vive en logs\ -> salida en logs\data\

SYMBOLS = ["EURUSD", "GBPJPY", "XAUUSD", "EURGBP", "AUDNZD", "USDJPY", "EURNOK", "USDSEK"]
YEAR_FROM = 2018

def main():
    if not mt5.initialize():
        sys.exit("[FATAL] mt5.initialize fallo: %s (¿MT5 abierto?)" % str(mt5.last_error()))

    tfs = {"M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1}
    os.makedirs(OUT_DIR, exist_ok=True)
    year_now = datetime.now(timezone.utc).year
    resumen = []

    for symbol in SYMBOLS:
        if not mt5.symbol_select(symbol, True):
            print("AVISO: simbolo %s no disponible en este broker; lo salto." % symbol)
            resumen.append((symbol, "-", 0, "no disponible"))
            continue
        for tf_name, tf in tfs.items():
            rows = {}
            for year in range(YEAR_FROM, year_now + 1):
                d1 = datetime(year, 1, 1, tzinfo=timezone.utc)
                d2 = datetime(year + 1, 1, 10, tzinfo=timezone.utc)
                rates = mt5.copy_rates_range(symbol, tf, d1, d2)
                if rates is None or len(rates) == 0:
                    continue
                for r in rates:
                    rows[int(r[0])] = r  # dedupe por timestamp
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

    # manifiesto para el analisis
    man = os.path.join(OUT_DIR, "manifest.csv")
    with open(man, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["symbol", "tf", "bars", "rango"])
        for row in resumen:
            w.writerow(row)

    mt5.shutdown()
    print("\nHecho. Archivos en %s" % OUT_DIR)
    print("Ejecuta ahora:  Start-ScheduledTask -TaskName PushLogs   (o espera a la subida horaria)")

if __name__ == "__main__":
    main()
