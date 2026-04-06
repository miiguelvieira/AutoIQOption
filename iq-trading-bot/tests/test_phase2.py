"""Testes da Phase 2: Storage, Collector e ChartImage."""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(message)s")

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def report(name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    msg = f"  {status} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append((name, passed))


# ===================================================================
# 1. CandleStorage
# ===================================================================
print("\n=== 1. CandleStorage ===\n")

from src.data.storage import CandleStorage

storage = CandleStorage()

# 1a. save_candles com dados sinteticos
fake_candles = [
    {
        "from": 1700000000 + i * 300,
        "open": 1.10 + i * 0.0001,
        "max": 1.1010 + i * 0.0001,
        "min": 1.0990 + i * 0.0001,
        "close": 1.1005 + i * 0.0001,
        "volume": 100 + i,
    }
    for i in range(10)
]

inserted = storage.save_candles("TEST", 5, fake_candles)
report("save_candles (insercao)", inserted == 10, f"{inserted}/10 inseridos")

# 1b. Deduplicacao
inserted2 = storage.save_candles("TEST", 5, fake_candles)
report("save_candles (dedup)", inserted2 == 0, f"{inserted2} duplicatas ignoradas")

# 1c. get_candles
df = storage.get_candles("TEST", 5, 10)
report("get_candles (retorno)", len(df) == 10, f"{len(df)} linhas retornadas")

# 1d. Colunas de price analysis
expected_cols = {"spread", "body", "body_pct", "upper_shadow", "lower_shadow", "direction"}
has_cols = expected_cols.issubset(set(df.columns))
report("get_candles (price cols)", has_cols, f"colunas: {sorted(expected_cols & set(df.columns))}")

# 1e. Valores de price coerentes
row = df.iloc[0]
spread_ok = abs(row["spread"] - (row["high"] - row["low"])) < 1e-8
body_ok = abs(row["body"] - (row["close"] - row["open"])) < 1e-8
report("price analysis (valores)", spread_ok and body_ok, f"spread={row['spread']:.6f} body={row['body']:.6f}")

# 1f. check_if_exists
ts = df.iloc[0]["timestamp"]
exists = storage.check_if_exists("TEST", 5, ts)
report("check_if_exists (True)", exists, f"timestamp={ts}")

fake_ts = datetime(2000, 1, 1, tzinfo=timezone.utc)
not_exists = not storage.check_if_exists("TEST", 5, fake_ts)
report("check_if_exists (False)", not_exists, "data inexistente")

# Limpar dados de teste
from src.data.storage import Candle
session = storage.Session()
session.query(Candle).filter_by(asset="TEST").delete()
session.commit()
session.close()

# ===================================================================
# 2. CandleCollector
# ===================================================================
print("\n=== 2. CandleCollector ===\n")

from src.connection.iq_client import IQClient
from src.data.collector import CandleCollector

client = IQClient()
connected = client.connect()
report("IQClient.connect", connected, f"conta: {client.account_type}")

if connected:
    config = client.config
    config_collect = config.copy()
    config_collect["data"] = {**config["data"], "candles_per_request": 100}

    collector = CandleCollector(config_collect, client, storage)

    n = collector.collect("EURUSD", 5)
    report("collect EURUSD M5", n >= 0, f"{n} candles novos")

    df_check = storage.get_candles("EURUSD", 5, 50)
    report("candles no banco", len(df_check) > 0, f"{len(df_check)} candles disponiveis")
else:
    report("collect EURUSD M5", False, "sem conexao")
    report("candles no banco", False, "sem conexao")

# ===================================================================
# 3. ChartImageGenerator
# ===================================================================
print("\n=== 3. ChartImageGenerator ===\n")

from src.data.chart_image import generate_image, generate_batch

df_img = storage.get_candles("EURUSD", 5, 100)

# 3a. Imagem unica
path = generate_image(df_img.tail(20).reset_index(drop=True), "EURUSD", 5)
report("generate_image (criacao)", path is not None, f"{path}")

if path:
    exists = Path(path).exists()
    report("generate_image (arquivo)", exists, f"existe no disco")

    from PIL import Image
    img = Image.open(path)
    report("generate_image (64x64)", img.size == (64, 64), f"dimensoes={img.size}")
    report("generate_image (PNG)", img.format == "PNG", f"formato={img.format}")
    img.close()

# 3b. Batch
paths = generate_batch(df_img, "EURUSD", 5, window=20, step=5)
report("generate_batch (qtd)", len(paths) >= 10, f"{len(paths)} imagens")

all_exist = all(Path(p).exists() for p in paths)
report("generate_batch (arquivos)", all_exist, "todos existem no disco")

# ===================================================================
# RESUMO
# ===================================================================
print("\n" + "=" * 50)
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"  TOTAL: {passed} passed / {failed} failed / {len(results)} tests")

if failed:
    print("\n  Falhas:")
    for name, ok in results:
        if not ok:
            print(f"    - {name}")

print("=" * 50)
sys.exit(0 if failed == 0 else 1)
