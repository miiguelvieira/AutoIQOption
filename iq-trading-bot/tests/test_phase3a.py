"""Testes Phase 3a — PatternDetector: cada padrão individualmente.

Cada bloco constrói um DataFrame sintético que força a detecção do padrão
e verifica detected=True, direction correto e score > 0.
"""

import sys
import logging
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.WARNING, format="%(message)s")

from src.patterns import PatternDetector

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


# ──────────────────────────────────────────────────────────────────────────────
# Helpers para DataFrames sintéticos
# ──────────────────────────────────────────────────────────────────────────────

def candle(open_, high, low, close, volume=100) -> dict:
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


def flat(n: int, base: float = 1.10) -> pd.DataFrame:
    """N candles neutros como contexto base."""
    return pd.DataFrame([candle(base, base + 0.0005, base - 0.0005, base)] * n)


def append_row(df: pd.DataFrame, **kw) -> pd.DataFrame:
    return pd.concat([df, pd.DataFrame([kw])], ignore_index=True)


detector = PatternDetector()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Pin Bar
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 1. Pin Bar ===\n")

# Bullish hammer
# spread=0.0065  body=0.001 (15.4%)  lower=0.005 (76.9%)  upper=0.0005 (7.7%)
df = append_row(flat(5), open=1.1030, close=1.1040, high=1.1045, low=1.0980, volume=200)
r = detector.pin_bar(df)
report("pin_bar buy  detected",  r["detected"] is True,   f"detected={r['detected']}")
report("pin_bar buy  direction", r["direction"] == "buy",  f"direction={r['direction']}")
report("pin_bar buy  score>0",   r["score"] > 0.0,         f"score={r['score']:.4f}")

# Bearish shooting star
# spread=0.0065  body=0.001 (15.4%)  upper=0.005 (76.9%)  lower=0.0005 (7.7%)
df = append_row(flat(5), open=1.1030, close=1.1020, high=1.1080, low=1.1015, volume=200)
r = detector.pin_bar(df)
report("pin_bar sell detected",  r["detected"] is True,    f"detected={r['detected']}")
report("pin_bar sell direction", r["direction"] == "sell",  f"direction={r['direction']}")
report("pin_bar sell score>0",   r["score"] > 0.0,          f"score={r['score']:.4f}")


# ──────────────────────────────────────────────────────────────────────────────
# 2. Engolfo
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 2. Engolfo ===\n")

# Bullish: vela anterior bear (open=1.105 close=1.100)
#          vela atual   bull (open=1.098 close=1.108) — cobre a anterior
df = flat(5)
df = append_row(df, open=1.105, close=1.100, high=1.106, low=1.099, volume=200)
df = append_row(df, open=1.098, close=1.108, high=1.109, low=1.097, volume=300)
r = detector.engolfo(df)
report("engolfo buy  detected",  r["detected"] is True,   f"detected={r['detected']}")
report("engolfo buy  direction", r["direction"] == "buy",  f"direction={r['direction']}")
report("engolfo buy  score>0",   r["score"] > 0.0,         f"score={r['score']:.4f}")

# Bearish: vela anterior bull (open=1.100 close=1.105)
#          vela atual   bear (open=1.108 close=1.098) — cobre a anterior
df = flat(5)
df = append_row(df, open=1.100, close=1.105, high=1.106, low=1.099, volume=200)
df = append_row(df, open=1.108, close=1.098, high=1.109, low=1.097, volume=300)
r = detector.engolfo(df)
report("engolfo sell detected",  r["detected"] is True,    f"detected={r['detected']}")
report("engolfo sell direction", r["direction"] == "sell",  f"direction={r['direction']}")
report("engolfo sell score>0",   r["score"] > 0.0,          f"score={r['score']:.4f}")


# ──────────────────────────────────────────────────────────────────────────────
# 3. Inside Bar
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 3. Inside Bar ===\n")

# Vela-mãe: high=1.115 low=1.095 (range=0.020)
MOTHER = candle(1.097, 1.115, 1.095, 1.113, 300)

# Buy: close_pos = (1.110-1.095)/0.020 = 0.75  →  terço superior  →  buy
df = flat(5)
df = append_row(df, **MOTHER)
df = append_row(df, open=1.103, close=1.110, high=1.112, low=1.102, volume=150)
r = detector.inside_bar(df)
report("inside_bar buy  detected",  r["detected"] is True,   f"detected={r['detected']}")
report("inside_bar buy  direction", r["direction"] == "buy",  f"direction={r['direction']}")
report("inside_bar buy  score>0",   r["score"] > 0.0,         f"score={r['score']:.4f}")

# Sell: close_pos = (1.100-1.095)/0.020 = 0.25  →  terço inferior  →  sell
df = flat(5)
df = append_row(df, **MOTHER)
df = append_row(df, open=1.107, close=1.100, high=1.108, low=1.097, volume=150)
r = detector.inside_bar(df)
report("inside_bar sell detected",  r["detected"] is True,    f"detected={r['detected']}")
report("inside_bar sell direction", r["direction"] == "sell",  f"direction={r['direction']}")
report("inside_bar sell score>0",   r["score"] > 0.0,          f"score={r['score']:.4f}")


# ──────────────────────────────────────────────────────────────────────────────
# 4. Pullback
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 4. Pullback ===\n")

# pullback mínimo requer trend_window(20) + retrace_bars(4) + 1 = 25 candles


def make_pullback_up() -> pd.DataFrame:
    """Uptrend 22 candles → 4 candles de retração → 1 bullish reversal."""
    closes = [1.1000 + i * 0.0015 for i in range(22)]     # 1.1000 .. 1.1315
    for _ in range(4):
        closes.append(closes[-1] - 0.0008)                # retração
    closes.append(closes[-1] + 0.0020)                    # reversão bullish
    rows = [candle(c - 0.0002, c + 0.0003, c - 0.0003, c) for c in closes]
    return pd.DataFrame(rows)


def make_pullback_down() -> pd.DataFrame:
    """Downtrend 22 candles → 4 candles de repique → 1 bearish reversal."""
    closes = [1.1300 - i * 0.0015 for i in range(22)]     # 1.1300 .. 1.0985
    for _ in range(4):
        closes.append(closes[-1] + 0.0008)                # repique
    closes.append(closes[-1] - 0.0020)                    # reversão bearish
    rows = [candle(c + 0.0002, c + 0.0003, c - 0.0003, c) for c in closes]
    return pd.DataFrame(rows)


r = detector.pullback(make_pullback_up())
report("pullback buy  detected",  r["detected"] is True,   f"detected={r['detected']}")
report("pullback buy  direction", r["direction"] == "buy",  f"direction={r['direction']}")
report("pullback buy  score>0",   r["score"] > 0.0,         f"score={r['score']:.4f}")

r = detector.pullback(make_pullback_down())
report("pullback sell detected",  r["detected"] is True,    f"detected={r['detected']}")
report("pullback sell direction", r["direction"] == "sell",  f"direction={r['direction']}")
report("pullback sell score>0",   r["score"] > 0.0,          f"score={r['score']:.4f}")


# ──────────────────────────────────────────────────────────────────────────────
# 5. Pushback
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 5. Pushback ===\n")

# pushback mínimo: avg_window(14) + impulse_window(5) + 1 = 20 candles
# df[-6] = impulso  |  df[-5..-2] = lateral  |  df[-1] = retração parcial


def make_pushback_buy() -> pd.DataFrame:
    """14 candles planos → impulso bullish forte (df[-6]) → 4 laterais → retração parcial."""
    rows = [candle(1.10, 1.1005, 1.0995, 1.10)] * 14
    # Impulso: open=1.100, close=1.115  (move=+0.015  >>  avg_body×1.5)
    rows.append(candle(1.100, 1.116, 1.099, 1.115, volume=500))
    # 4 candles laterais com suave declínio
    for i in range(4):
        c = 1.112 - i * 0.001
        rows.append(candle(c, c + 0.001, c - 0.001, c))
    # Atual: retraiu parcialmente mas close=1.108 > impulse.open=1.100  →  buy
    rows.append(candle(1.109, 1.110, 1.106, 1.108))
    return pd.DataFrame(rows)


def make_pushback_sell() -> pd.DataFrame:
    """14 candles planos → impulso bearish forte (df[-6]) → 4 laterais → repique parcial."""
    rows = [candle(1.10, 1.1005, 1.0995, 1.10)] * 14
    # Impulso: open=1.100, close=1.085  (move=-0.015)
    rows.append(candle(1.100, 1.101, 1.084, 1.085, volume=500))
    # 4 candles laterais com suave alta
    for i in range(4):
        c = 1.088 + i * 0.001
        rows.append(candle(c, c + 0.001, c - 0.001, c))
    # Atual: repicou parcialmente mas close=1.091 < impulse.open=1.100  →  sell
    rows.append(candle(1.092, 1.093, 1.089, 1.091))
    return pd.DataFrame(rows)


r = detector.pushback(make_pushback_buy())
report("pushback buy  detected",  r["detected"] is True,   f"detected={r['detected']}")
report("pushback buy  direction", r["direction"] == "buy",  f"direction={r['direction']}")
report("pushback buy  score>0",   r["score"] > 0.0,         f"score={r['score']:.4f}")

r = detector.pushback(make_pushback_sell())
report("pushback sell detected",  r["detected"] is True,    f"detected={r['detected']}")
report("pushback sell direction", r["direction"] == "sell",  f"direction={r['direction']}")
report("pushback sell score>0",   r["score"] > 0.0,          f"score={r['score']:.4f}")


# ──────────────────────────────────────────────────────────────────────────────
# 6. Topo Duplo
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 6. Topo Duplo ===\n")

# Estrutura: subida → pico 1 (~1.116) → vale (~1.102) → pico 2 (~1.115) → queda → close abaixo do vale


def make_topo_duplo() -> pd.DataFrame:
    rows = []
    # Subida ao primeiro topo (10 candles)
    for i in range(10):
        c = 1.100 + i * 0.0015
        rows.append(candle(c - 0.0005, c + 0.0005, c - 0.0008, c))
    # Primeiro topo
    rows.append(candle(1.113, 1.116, 1.112, 1.114))
    # Vale (8 candles — declínio)
    for i in range(8):
        c = 1.113 - i * 0.0015
        rows.append(candle(c, c + 0.0005, c - 0.0005, c))
    # Segundo topo (similar ao primeiro, dentro da tolerância de 1%)
    rows.append(candle(1.113, 1.115, 1.112, 1.114))
    # Queda abaixo do vale
    for i in range(3):
        c = 1.112 - i * 0.003
        rows.append(candle(c, c + 0.0003, c - 0.001, c - 0.001))
    # Candle atual: abaixo da neckline (~1.102)
    rows.append(candle(1.098, 1.099, 1.096, 1.097))
    return pd.DataFrame(rows)


r = detector.topo_duplo(make_topo_duplo())
report("topo_duplo detected",   r["detected"] is True,    f"detected={r['detected']}")
report("topo_duplo direction",  r["direction"] == "sell",  f"direction={r['direction']}")
report("topo_duplo score>0",    r["score"] > 0.0,          f"score={r['score']:.4f}")


# ──────────────────────────────────────────────────────────────────────────────
# 7. Fundo Duplo
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 7. Fundo Duplo ===\n")

# Estrutura: queda → fundo 1 (~1.084) → pico (~1.099) → fundo 2 (~1.084) → subida → close acima do pico


def make_fundo_duplo() -> pd.DataFrame:
    rows = []
    # Queda ao primeiro fundo (10 candles)
    for i in range(10):
        c = 1.100 - i * 0.0015
        rows.append(candle(c + 0.0005, c + 0.0008, c - 0.0005, c))
    # Primeiro fundo
    rows.append(candle(1.087, 1.088, 1.084, 1.086))
    # Pico entre os fundos (8 candles — subida)
    for i in range(8):
        c = 1.087 + i * 0.0015
        rows.append(candle(c, c + 0.0005, c - 0.0005, c))
    # Segundo fundo (idêntico ao primeiro — diff=0)
    rows.append(candle(1.087, 1.088, 1.084, 1.086))
    # Subida acima do pico (neckline ≈ 1.099)
    for i in range(3):
        c = 1.088 + i * 0.003
        rows.append(candle(c, c + 0.001, c - 0.0003, c + 0.001))
    # Candle atual: acima da neckline
    rows.append(candle(1.101, 1.103, 1.100, 1.102))
    return pd.DataFrame(rows)


r = detector.fundo_duplo(make_fundo_duplo())
report("fundo_duplo detected",   r["detected"] is True,   f"detected={r['detected']}")
report("fundo_duplo direction",  r["direction"] == "buy",  f"direction={r['direction']}")
report("fundo_duplo score>0",    r["score"] > 0.0,         f"score={r['score']:.4f}")


# ──────────────────────────────────────────────────────────────────────────────
# 8. Breakout
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 8. Breakout ===\n")

# 20 candles em range fixo [1.095, 1.105]  →  21º fecha acima/abaixo do range

BASE_RANGE = [candle(1.100, 1.105, 1.095, 1.100)] * 20

# Bullish: close=1.115 > max_high=1.105
df = pd.DataFrame(BASE_RANGE)
df = append_row(df, open=1.104, close=1.115, high=1.116, low=1.103, volume=500)
r = detector.breakout(df)
report("breakout buy  detected",  r["detected"] is True,   f"detected={r['detected']}")
report("breakout buy  direction", r["direction"] == "buy",  f"direction={r['direction']}")
report("breakout buy  score>0",   r["score"] > 0.0,         f"score={r['score']:.4f}")

# Bearish: close=1.085 < min_low=1.095
df = pd.DataFrame(BASE_RANGE)
df = append_row(df, open=1.097, close=1.085, high=1.098, low=1.084, volume=500)
r = detector.breakout(df)
report("breakout sell detected",  r["detected"] is True,    f"detected={r['detected']}")
report("breakout sell direction", r["direction"] == "sell",  f"direction={r['direction']}")
report("breakout sell score>0",   r["score"] > 0.0,          f"score={r['score']:.4f}")


# ──────────────────────────────────────────────────────────────────────────────
# 9. detect_all
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 9. detect_all ===\n")

EXPECTED_KEYS = {"pin_bar", "engolfo", "inside_bar", "pullback",
                 "pushback", "topo_duplo", "fundo_duplo", "breakout"}

result = detector.detect_all(pd.DataFrame(BASE_RANGE * 3))  # 60 candles neutros

report("detect_all chaves corretas",
       set(result.keys()) == EXPECTED_KEYS,
       f"keys={sorted(result.keys())}")

valid = all(
    isinstance(v["detected"], bool)
    and v["direction"] in ("buy", "sell", "neutral")
    and 0.0 <= v["score"] <= 1.0
    for v in result.values()
)
report("detect_all estrutura válida", valid,
       "detected=bool  direction∈{buy,sell,neutral}  score∈[0,1]")

# Breakout forçado via detect_all
df_bk = pd.DataFrame(BASE_RANGE)
df_bk = append_row(df_bk, open=1.104, close=1.115, high=1.116, low=1.103, volume=500)
res = detector.detect_all(df_bk)
report("detect_all breakout buy",
       res["breakout"]["detected"] and res["breakout"]["direction"] == "buy",
       f"breakout={res['breakout']}")


# ──────────────────────────────────────────────────────────────────────────────
# 10. summary
# ──────────────────────────────────────────────────────────────────────────────
print("\n=== 10. summary ===\n")

fake = {
    "pin_bar":    {"detected": True,  "direction": "buy",     "score": 0.85},
    "engolfo":    {"detected": True,  "direction": "buy",     "score": 0.70},
    "inside_bar": {"detected": False, "direction": "neutral", "score": 0.00},
    "pullback":   {"detected": True,  "direction": "sell",    "score": 0.60},
    "pushback":   {"detected": False, "direction": "neutral", "score": 0.00},
    "topo_duplo": {"detected": False, "direction": "neutral", "score": 0.00},
    "fundo_duplo":{"detected": False, "direction": "neutral", "score": 0.00},
    "breakout":   {"detected": True,  "direction": "buy",     "score": 0.90},
}
s = detector.summary(fake)

report("summary total_detected",
       s["total_detected"] == 4,
       f"total_detected={s['total_detected']}")
report("summary buy_signals",
       sorted(s["buy_signals"]) == ["breakout", "engolfo", "pin_bar"],
       f"buy={sorted(s['buy_signals'])}")
report("summary sell_signals",
       s["sell_signals"] == ["pullback"],
       f"sell={s['sell_signals']}")
report("summary top_score",
       s["top_score"] == 0.90,
       f"top_score={s['top_score']}")
report("summary bias buy",
       s["bias"] == "buy",
       f"bias={s['bias']}")

# summary sem nenhuma detecção
empty = {k: {"detected": False, "direction": "neutral", "score": 0.0}
         for k in EXPECTED_KEYS}
s0 = detector.summary(empty)
report("summary vazio top_score",
       s0["top_score"] == 0.0,
       f"top_score={s0['top_score']}")
report("summary vazio bias neutral",
       s0["bias"] == "neutral",
       f"bias={s0['bias']}")

# summary bias sell (1 buy, 2 sell)
fake_sell = {
    "pin_bar":    {"detected": True,  "direction": "sell", "score": 0.80},
    "engolfo":    {"detected": True,  "direction": "sell", "score": 0.75},
    "breakout":   {"detected": True,  "direction": "buy",  "score": 0.65},
    "inside_bar": {"detected": False, "direction": "neutral", "score": 0.0},
    "pullback":   {"detected": False, "direction": "neutral", "score": 0.0},
    "pushback":   {"detected": False, "direction": "neutral", "score": 0.0},
    "topo_duplo": {"detected": False, "direction": "neutral", "score": 0.0},
    "fundo_duplo":{"detected": False, "direction": "neutral", "score": 0.0},
}
s_sell = detector.summary(fake_sell)
report("summary bias sell",
       s_sell["bias"] == "sell",
       f"bias={s_sell['bias']}  buy={s_sell['buy_signals']}  sell={s_sell['sell_signals']}")


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
