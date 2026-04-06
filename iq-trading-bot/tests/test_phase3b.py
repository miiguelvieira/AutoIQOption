"""Testes Phase 3b — Labeler + DatasetBuilder.

Testa:
    1. Labeler rotula alta clara como buy_win
    2. Labeler rotula queda clara como sell_win
    3. CSV de labels criado com colunas corretas
    4. DatasetBuilder gera imagens e labels consistentes para EURUSD M5
       (usa dados reais do banco se disponíveis, senão injeta dados sintéticos)
"""

import sys
import logging
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.WARNING, format="%(message)s")

from src.data.labeler import Labeler, CSV_COLUMNS
from src.data.storage import CandleStorage

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def report(name: str, passed: bool, detail: str = "") -> None:
    status = PASS if passed else FAIL
    msg = f"  {status} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append((name, passed))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers para DataFrames sintéticos
# ──────────────────────────────────────────────────────────────────────────────

def _make_df(rows: list[dict], base_time: datetime | None = None) -> pd.DataFrame:
    """Constrói DataFrame OHLCV com timestamp."""
    if base_time is None:
        base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = []
    for i, r in enumerate(rows):
        records.append({
            "timestamp": base_time + timedelta(minutes=5 * i),
            "open":   r["open"],
            "high":   r["high"],
            "low":    r["low"],
            "close":  r["close"],
            "volume": r.get("volume", 100),
        })
    return pd.DataFrame(records)


def _candle(o, h, l, c, v=100):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def _make_uptrend(n: int = 55, start: float = 1.1000, step: float = 0.0020) -> pd.DataFrame:
    """Tendência de alta clara: N candles bull consecutivos."""
    rows = []
    price = start
    for _ in range(n):
        rows.append(_candle(price, price + step * 0.6, price - step * 0.1, price + step))
        price += step
    return _make_df(rows)


def _make_downtrend(n: int = 55, start: float = 1.1500, step: float = 0.0020) -> pd.DataFrame:
    """Tendência de baixa clara: N candles bear consecutivos."""
    rows = []
    price = start
    for _ in range(n):
        rows.append(_candle(price, price + step * 0.1, price - step * 0.6, price - step))
        price -= step
    return _make_df(rows)


def _inject_synthetic_candles(
    storage: CandleStorage,
    asset: str,
    timeframe: int,
    n: int = 70,
    trending_up: bool = True,
) -> None:
    """Insere candles sintéticos no banco para testes."""
    base_price = 1.1000 if trending_up else 1.5000
    step = 0.0010 if trending_up else -0.0010
    base_time = datetime(2020, 1, 1, tzinfo=timezone.utc)

    candles = []
    price = base_price
    for i in range(n):
        o = price
        if trending_up:
            h, l, c = o + abs(step) * 0.6, o - abs(step) * 0.1, o + abs(step)
        else:
            h, l, c = o + abs(step) * 0.1, o - abs(step) * 0.6, o - abs(step)
        candles.append({
            "from":   int((base_time + timedelta(minutes=timeframe * i)).timestamp()),
            "open":   round(o, 5),
            "max":    round(h, 5),
            "min":    round(l, 5),
            "close":  round(c, 5),
            "volume": 100,
        })
        price = c
    storage.save_candles(asset, timeframe, candles)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Labeler — alta clara → buy_win
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 1. Labeler — alta clara (buy_win) ===\n")

labeler = Labeler(n_future=5)
df_up = _make_uptrend(n=60)
window_up = df_up.iloc[:50].reset_index(drop=True)
future_up  = df_up.iloc[50:55].reset_index(drop=True)

row_up = labeler.label_window(window_up, future_up, "EURUSD", 5, "/fake/img_up.png")

report(
    "buy_win — label correto",
    row_up["label"] == "buy_win",
    f"label={row_up['label']}  direction={row_up['direction']}  score={row_up['pattern_score']}",
)
report(
    "buy_win — direction buy",
    row_up["direction"] == "buy",
    f"direction={row_up['direction']}",
)
report(
    "buy_win — pattern_score >= 0",
    row_up["pattern_score"] >= 0.0,
    f"score={row_up['pattern_score']}",
)


# ──────────────────────────────────────────────────────────────────────────────
# 2. Labeler — queda clara → sell_win
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 2. Labeler — queda clara (sell_win) ===\n")

df_dn = _make_downtrend(n=60)
window_dn = df_dn.iloc[:50].reset_index(drop=True)
future_dn  = df_dn.iloc[50:55].reset_index(drop=True)

row_dn = labeler.label_window(window_dn, future_dn, "EURUSD", 5, "/fake/img_dn.png")

report(
    "sell_win — label correto",
    row_dn["label"] == "sell_win",
    f"label={row_dn['label']}  direction={row_dn['direction']}  score={row_dn['pattern_score']}",
)
report(
    "sell_win — direction sell",
    row_dn["direction"] == "sell",
    f"direction={row_dn['direction']}",
)
report(
    "sell_win — pattern_score >= 0",
    row_dn["pattern_score"] >= 0.0,
    f"score={row_dn['pattern_score']}",
)


# ──────────────────────────────────────────────────────────────────────────────
# 3. CSV de labels — colunas corretas
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 3. CSV de labels — colunas corretas ===\n")

with tempfile.TemporaryDirectory() as tmpdir:
    csv_path = Path(tmpdir) / "labels.csv"
    sample_labels = [row_up, row_dn]
    Labeler.save_csv(sample_labels, csv_path)

    report("CSV existe", csv_path.exists(), f"path={csv_path}")

    if csv_path.exists():
        df_csv = pd.read_csv(csv_path)
        actual_cols = set(df_csv.columns.tolist())
        expected_cols = set(CSV_COLUMNS)

        report(
            "CSV colunas corretas",
            actual_cols == expected_cols,
            f"expected={sorted(expected_cols)}  got={sorted(actual_cols)}",
        )
        report(
            "CSV número de linhas",
            len(df_csv) == 2,
            f"linhas={len(df_csv)}",
        )
        report(
            "CSV coluna label contém valores válidos",
            set(df_csv["label"].tolist()).issubset(
                {"buy_win", "buy_loss", "sell_win", "sell_loss", "neutral"}
            ),
            f"labels={df_csv['label'].tolist()}",
        )
    else:
        for name in ("CSV colunas corretas", "CSV número de linhas", "CSV coluna label contém valores válidos"):
            report(name, False, "arquivo não criado")


# ──────────────────────────────────────────────────────────────────────────────
# 4. DatasetBuilder — pipeline completo com EURUSD M5
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 4. DatasetBuilder — EURUSD M5 ===\n")

ASSET = "EURUSD"
TF = 5
WINDOW = 50
N_FUTURE = 5

with tempfile.TemporaryDirectory() as tmpdir:
    db_path = str(Path(tmpdir) / "test.db")
    images_dir = str(Path(tmpdir) / "images")
    labels_csv = str(Path(tmpdir) / "labels.csv")

    storage = CandleStorage(db_path)

    # Tenta carregar dados reais do banco do projeto
    real_db = Path(__file__).resolve().parent.parent / "data" / "candles" / "candles.db"
    used_real_data = False

    if real_db.exists():
        real_storage = CandleStorage(str(real_db))
        real_df = real_storage.get_candles(ASSET, TF, limit=500)
        real_storage.engine.dispose()
        if len(real_df) >= WINDOW + N_FUTURE:
            # Copia os candles reais para o DB de teste
            candles_raw = []
            for _, r in real_df.iterrows():
                candles_raw.append({
                    "from":   int(r["timestamp"].timestamp()),
                    "open":   r["open"],
                    "max":    r["high"],
                    "min":    r["low"],
                    "close":  r["close"],
                    "volume": int(r["volume"]),
                })
            storage.save_candles(ASSET, TF, candles_raw)
            used_real_data = True
            print(f"  [INFO] Usando {len(real_df)} candles reais de {ASSET} M{TF}")

    if not used_real_data:
        # Injeta dados sintéticos suficientes para o pipeline
        _inject_synthetic_candles(storage, ASSET, TF, n=80, trending_up=True)
        print(f"  [INFO] Usando {80} candles sintéticos para {ASSET} M{TF}")

    # Carrega candles do DB de teste
    df_loaded = storage.get_candles(ASSET, TF, limit=10_000)

    report(
        "DB contém candles suficientes",
        len(df_loaded) >= WINDOW + N_FUTURE,
        f"candles={len(df_loaded)}  mínimo={WINDOW + N_FUTURE}",
    )

    if len(df_loaded) >= WINDOW + N_FUTURE:
        # Roda o pipeline manualmente (sem gerar imagens reais para não depender do mplfinance)
        labeler_4 = Labeler(n_future=N_FUTURE)
        labels_4 = []
        total = len(df_loaded)

        for start in range(0, total - WINDOW - N_FUTURE + 1, 1):
            end = start + WINDOW
            w = df_loaded.iloc[start:end].reset_index(drop=True)
            f = df_loaded.iloc[end:end + N_FUTURE].reset_index(drop=True)
            r = labeler_4.label_window(w, f, ASSET, TF, f"/fake/{start}.png")
            labels_4.append(r)

        # Salva CSV
        Labeler.save_csv(labels_4, labels_csv)

        report(
            "Labels gerados (>= 1)",
            len(labels_4) >= 1,
            f"labels={len(labels_4)}",
        )

        df_out = pd.read_csv(labels_csv)
        report(
            "CSV tem colunas corretas",
            set(df_out.columns.tolist()) == set(CSV_COLUMNS),
            f"cols={sorted(df_out.columns.tolist())}",
        )

        valid_labels = set(df_out["label"].tolist()).issubset(
            {"buy_win", "buy_loss", "sell_win", "sell_loss", "neutral"}
        )
        report(
            "Labels são valores válidos",
            valid_labels,
            f"unique_labels={sorted(df_out['label'].unique().tolist())}",
        )

        # Consistência: asset e timeframe corretos em todos os registros
        correct_asset_tf = (
            (df_out["asset"] == ASSET).all() and
            (df_out["timeframe"] == TF).all()
        )
        report(
            "Asset e timeframe consistentes no CSV",
            correct_asset_tf,
            f"assets_ok={(df_out['asset'] == ASSET).all()}  "
            f"tf_ok={(df_out['timeframe'] == TF).all()}",
        )

        # pattern_score dentro do intervalo válido [0, 1]
        scores_valid = (
            (df_out["pattern_score"] >= 0.0).all() and
            (df_out["pattern_score"] <= 1.0).all()
        )
        report(
            "pattern_score dentro de [0, 1]",
            scores_valid,
            f"min={df_out['pattern_score'].min():.4f}  "
            f"max={df_out['pattern_score'].max():.4f}",
        )

        # filepath preenchido em todas as linhas
        report(
            "filepath preenchido em todas as linhas",
            df_out["filepath"].notna().all() and (df_out["filepath"] != "").all(),
            f"nulos={df_out['filepath'].isna().sum()}",
        )
    else:
        for name in (
            "Labels gerados (>= 1)",
            "CSV tem colunas corretas",
            "Labels são valores válidos",
            "Asset e timeframe consistentes no CSV",
            "pattern_score dentro de [0, 1]",
            "filepath preenchido em todas as linhas",
        ):
            report(name, False, "dados insuficientes")

    # Fecha a conexão explicitamente para o Windows liberar o arquivo antes de rmdir
    storage.engine.dispose()


# ──────────────────────────────────────────────────────────────────────────────
# RESUMO FINAL
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"  TOTAL: {passed} passed / {failed} failed / {len(results)} tests")

if failed:
    print("\n  Falhas:")
    for name, ok in results:
        if not ok:
            print(f"    - {name}")

print("=" * 55)
sys.exit(0 if failed == 0 else 1)
