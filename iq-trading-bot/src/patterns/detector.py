"""Detecção de padrões técnicos de candlestick e estrutura de preço.

API principal
-------------
detect(df) → dict
    Recebe um DataFrame com colunas open, high, low, close, volume
    (mínimo recomendado: 50 candles para padrões de estrutura).

    Retorna um dicionário com 8 padrões, cada um com:
        detected  (bool)
        direction ('buy' | 'sell' | 'neutral')
        score     (float 0.0 – 1.0)
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos (operam sobre uma Row ou Series de um único candle)
# ──────────────────────────────────────────────────────────────────────────────

def _spread(c) -> float:
    return float(c.high - c.low)

def _body(c) -> float:
    return float(c.close - c.open)

def _body_abs(c) -> float:
    return abs(_body(c))

def _upper_shadow(c) -> float:
    return float(c.high - max(c.open, c.close))

def _lower_shadow(c) -> float:
    return float(min(c.open, c.close) - c.low)

def _result(detected: bool, direction: str, score: float) -> dict:
    return {
        "detected":  bool(detected),
        "direction": direction,
        "score":     round(float(np.clip(score, 0.0, 1.0)), 4),
    }

def _no_pattern() -> dict:
    return _result(False, "neutral", 0.0)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Pin Bar
# ──────────────────────────────────────────────────────────────────────────────

def _pin_bar(df: pd.DataFrame) -> dict:
    """Pin bar: corpo pequeno com uma sombra dominante de um lado.

    Bullish (hammer)    : sombra inferior longa → rejeição de preços baixos → buy
    Bearish (shooting)  : sombra superior longa → rejeição de preços altos  → sell

    Critérios:
        corpo ≤ 35% do spread total
        sombra dominante ≥ 60% do spread
        sombra oposta ≤ 25% do spread
    Score: shadow_ratio × (1 − body_ratio)
    """
    c = df.iloc[-1]
    spread = _spread(c)
    if spread == 0:
        return _no_pattern()

    body_r  = _body_abs(c) / spread
    upper_r = _upper_shadow(c) / spread
    lower_r = _lower_shadow(c) / spread

    BODY_MAX   = 0.35
    SHADOW_MIN = 0.60
    SHADOW_OPP = 0.25

    if body_r <= BODY_MAX and lower_r >= SHADOW_MIN and upper_r <= SHADOW_OPP:
        return _result(True, "buy", lower_r * (1 - body_r))

    if body_r <= BODY_MAX and upper_r >= SHADOW_MIN and lower_r <= SHADOW_OPP:
        return _result(True, "sell", upper_r * (1 - body_r))

    return _no_pattern()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Engolfo (Engulfing)
# ──────────────────────────────────────────────────────────────────────────────

def _engolfo(df: pd.DataFrame) -> dict:
    """Engolfo: corpo da vela atual engloba completamente o corpo da vela anterior.

    Bullish engulfing : vela anterior bearish + vela atual bullish → buy
    Bearish engulfing : vela anterior bullish + vela atual bearish → sell
    Score: min(tamanho_atual / tamanho_anterior / 2, 1.0)
    """
    if len(df) < 2:
        return _no_pattern()

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    prev_body = _body(prev)
    curr_body = _body(curr)
    prev_size = abs(prev_body)

    if prev_size == 0:
        return _no_pattern()

    prev_top = max(prev.open, prev.close)
    prev_bot = min(prev.open, prev.close)
    curr_top = max(curr.open, curr.close)
    curr_bot = min(curr.open, curr.close)

    # Corpo atual deve cobrir o corpo anterior inteiramente
    if not (curr_bot <= prev_bot and curr_top >= prev_top):
        return _no_pattern()

    score = min(abs(curr_body) / prev_size / 2.0, 1.0)

    if prev_body < 0 and curr_body > 0:
        return _result(True, "buy", score)
    if prev_body > 0 and curr_body < 0:
        return _result(True, "sell", score)

    return _no_pattern()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Inside Bar
# ──────────────────────────────────────────────────────────────────────────────

def _inside_bar(df: pd.DataFrame) -> dict:
    """Inside bar: máxima e mínima da vela atual dentro do range da vela-mãe.

    Direção: posição do fechamento dentro do range da vela-mãe
        close no terço superior → buy
        close no terço inferior → sell
        caso contrário          → neutral
    Score: 1 − (range_atual / range_mãe)  — maior compressão = score maior
    """
    if len(df) < 2:
        return _no_pattern()

    mother = df.iloc[-2]
    curr   = df.iloc[-1]

    mother_range = mother.high - mother.low
    if mother_range == 0:
        return _no_pattern()

    if curr.high > mother.high or curr.low < mother.low:
        return _no_pattern()

    compression = 1.0 - ((curr.high - curr.low) / mother_range)
    close_pos   = (curr.close - mother.low) / mother_range  # 0 = fundo, 1 = topo

    if close_pos > 0.60:
        direction = "buy"
    elif close_pos < 0.40:
        direction = "sell"
    else:
        direction = "neutral"

    return _result(True, direction, compression)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Pullback
# ──────────────────────────────────────────────────────────────────────────────

def _pullback(df: pd.DataFrame, trend_window: int = 20, retrace_bars: int = 4) -> dict:
    """Pullback: retração temporária contra a tendência seguida de reversão.

    Bullish: preço > SMA(trend_window) → retrace_bars com closes caindo
             → vela atual com corpo bullish
    Bearish: preço < SMA → closes subindo → vela atual com corpo bearish

    Score: 0.5 × força_da_tendência + 0.5 × proporção_do_corpo
    """
    if len(df) < trend_window + retrace_bars + 1:
        return _no_pattern()

    close = df["close"]
    sma   = close.rolling(trend_window).mean()

    curr_close = float(close.iloc[-1])
    curr_sma   = float(sma.iloc[-1])

    if pd.isna(curr_sma):
        return _no_pattern()

    curr    = df.iloc[-1]
    retrace = df.iloc[-(retrace_bars + 1):-1]  # N candles imediatamente antes do atual
    spread  = _spread(curr)
    body    = _body(curr)

    # Tendência de alta
    if curr_close > curr_sma:
        had_retrace = float(retrace["close"].iloc[-1]) < float(retrace["close"].iloc[0])
        if had_retrace and body > 0:
            trend_str  = min((curr_close - curr_sma) / curr_sma * 20, 1.0)
            body_ratio = body / spread if spread > 0 else 0.0
            return _result(True, "buy", trend_str * 0.5 + body_ratio * 0.5)

    # Tendência de baixa
    elif curr_close < curr_sma:
        had_retrace = float(retrace["close"].iloc[-1]) > float(retrace["close"].iloc[0])
        if had_retrace and body < 0:
            trend_str  = min((curr_sma - curr_close) / curr_sma * 20, 1.0)
            body_ratio = abs(body) / spread if spread > 0 else 0.0
            return _result(True, "sell", trend_str * 0.5 + body_ratio * 0.5)

    return _no_pattern()


# ──────────────────────────────────────────────────────────────────────────────
# 5. Pushback
# ──────────────────────────────────────────────────────────────────────────────

def _pushback(df: pd.DataFrame, impulse_window: int = 5, avg_window: int = 14) -> dict:
    """Pushback: retração parcial após impulso direcional forte.

    Detecta quando o preço recuou parcialmente sobre um impulso anterior sem
    revertê-lo completamente — sinal de continuação na direção do impulso.

    Bullish: impulso de alta N bars atrás → retração sem fechar abaixo
             da abertura do impulso → buy
    Bearish: impulso de baixa → repique sem fechar acima da abertura → sell

    Score: 1 − profundidade_da_retração (retração menor = score maior)
    """
    min_bars = avg_window + impulse_window + 1
    if len(df) < min_bars:
        return _no_pattern()

    avg_body = df["close"].diff().abs().iloc[-(avg_window + 1):-1].mean()
    if avg_body == 0:
        return _no_pattern()

    impulse = df.iloc[-(impulse_window + 1)]
    curr    = df.iloc[-1]

    impulse_move = _body(impulse)
    impulse_size = abs(impulse_move)

    if impulse_size < avg_body * 1.5:
        return _no_pattern()

    if impulse_move > 0:  # impulso bullish
        retraced = curr.close < impulse.close   # houve retração
        held     = curr.close > impulse.open    # não reverteu o impulso
        if retraced and held:
            depth = (impulse.close - curr.close) / impulse_size
            return _result(True, "buy", 1.0 - depth)

    elif impulse_move < 0:  # impulso bearish
        retraced = curr.close > impulse.close
        held     = curr.close < impulse.open
        if retraced and held:
            depth = (curr.close - impulse.close) / impulse_size
            return _result(True, "sell", 1.0 - depth)

    return _no_pattern()


# ──────────────────────────────────────────────────────────────────────────────
# 6. Topo Duplo (Double Top)
# ──────────────────────────────────────────────────────────────────────────────

def _topo_duplo(df: pd.DataFrame, lookback: int = 50, tolerance: float = 0.01) -> dict:
    """Topo duplo: dois picos em níveis similares com rompimento da linha de pescoço.

    Confirmado quando o fechamento atual rompe abaixo do vale (neckline)
    entre os dois topos.

    Score: 0.6 × similaridade_dos_topos + 0.4 × profundidade_do_rompimento
    """
    if len(df) < 20:
        return _no_pattern()

    w      = df.iloc[-lookback:] if len(df) >= lookback else df
    highs  = w["high"].values
    lows   = w["low"].values
    n      = len(highs)

    peaks = [i for i in range(1, n - 1)
             if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]]

    if len(peaks) < 2:
        return _no_pattern()

    top_two = sorted(sorted(peaks, key=lambda i: highs[i], reverse=True)[:2])
    a, b    = top_two[0], top_two[1]

    diff = abs(highs[a] - highs[b]) / max(highs[a], highs[b])
    if diff > tolerance:
        return _no_pattern()

    neckline = lows[a:b + 1].min()
    curr_close = float(df["close"].iloc[-1])

    if curr_close >= neckline:
        return _no_pattern()

    pattern_height = (highs[a] + highs[b]) / 2 - neckline
    if pattern_height <= 0:
        return _no_pattern()

    similarity  = 1.0 - (diff / tolerance)
    break_depth = min((neckline - curr_close) / pattern_height, 1.0)
    score = similarity * 0.6 + break_depth * 0.4

    return _result(True, "sell", score)


# ──────────────────────────────────────────────────────────────────────────────
# 7. Fundo Duplo (Double Bottom)
# ──────────────────────────────────────────────────────────────────────────────

def _fundo_duplo(df: pd.DataFrame, lookback: int = 50, tolerance: float = 0.01) -> dict:
    """Fundo duplo: dois vales em níveis similares com rompimento da linha de pescoço.

    Confirmado quando o fechamento atual rompe acima do pico (neckline)
    entre os dois fundos.

    Score: 0.6 × similaridade_dos_fundos + 0.4 × altura_do_rompimento
    """
    if len(df) < 20:
        return _no_pattern()

    w      = df.iloc[-lookback:] if len(df) >= lookback else df
    lows   = w["low"].values
    highs  = w["high"].values
    n      = len(lows)

    troughs = [i for i in range(1, n - 1)
               if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]]

    if len(troughs) < 2:
        return _no_pattern()

    bot_two = sorted(sorted(troughs, key=lambda i: lows[i])[:2])
    a, b    = bot_two[0], bot_two[1]

    base = max(abs(lows[a]), abs(lows[b]), 1e-10)
    diff = abs(lows[a] - lows[b]) / base
    if diff > tolerance:
        return _no_pattern()

    neckline   = highs[a:b + 1].max()
    curr_close = float(df["close"].iloc[-1])

    if curr_close <= neckline:
        return _no_pattern()

    pattern_height = neckline - (lows[a] + lows[b]) / 2
    if pattern_height <= 0:
        return _no_pattern()

    similarity   = 1.0 - (diff / tolerance)
    break_height = min((curr_close - neckline) / pattern_height, 1.0)
    score = similarity * 0.6 + break_height * 0.4

    return _result(True, "buy", score)


# ──────────────────────────────────────────────────────────────────────────────
# 8. Breakout
# ──────────────────────────────────────────────────────────────────────────────

def _breakout(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Breakout: fechamento acima da máxima ou abaixo da mínima dos últimos N candles.

    Bullish: close > max(high[lookback]) → buy
    Bearish: close < min(low[lookback])  → sell

    Score: 0.7 × extensão_relativa_do_rompimento + 0.3 × proporção_do_corpo
    """
    if len(df) < lookback + 1:
        return _no_pattern()

    history    = df.iloc[-(lookback + 1):-1]
    curr       = df.iloc[-1]
    resistance = float(history["high"].max())
    support    = float(history["low"].min())
    hist_range = resistance - support

    if hist_range == 0:
        return _no_pattern()

    spread = _spread(curr)
    body   = _body(curr)

    if curr.close > resistance:
        break_ext  = min((curr.close - resistance) / hist_range * 2, 1.0)
        body_ratio = (body / spread) if (spread > 0 and body > 0) else 0.0
        return _result(True, "buy", break_ext * 0.7 + body_ratio * 0.3)

    if curr.close < support:
        break_ext  = min((support - curr.close) / hist_range * 2, 1.0)
        body_ratio = (abs(body) / spread) if (spread > 0 and body < 0) else 0.0
        return _result(True, "sell", break_ext * 0.7 + body_ratio * 0.3)

    return _no_pattern()


# ──────────────────────────────────────────────────────────────────────────────
# Função principal
# ──────────────────────────────────────────────────────────────────────────────

_PATTERN_NAMES = (
    "pin_bar", "engolfo", "inside_bar", "pullback",
    "pushback", "topo_duplo", "fundo_duplo", "breakout",
)


# ──────────────────────────────────────────────────────────────────────────────
# Interface orientada a objetos
# ──────────────────────────────────────────────────────────────────────────────

class PatternDetector:
    """Detecta padrões técnicos em um DataFrame de candles OHLCV.

    Cada método individual recebe o mesmo DataFrame que ``detect_all`` e
    retorna ``{"detected": bool, "direction": str, "score": float}``.

    Exemplo::

        detector = PatternDetector()
        result = detector.detect_all(df)
        print(detector.summary(result))
    """

    # ── Padrões individuais ──────────────────────────────────────────────────

    def pin_bar(self, df: pd.DataFrame) -> dict:
        """Detecta pin bar (hammer / shooting star) no último candle."""
        return _pin_bar(df)

    def engolfo(self, df: pd.DataFrame) -> dict:
        """Detecta engolfo bullish ou bearish nos dois últimos candles."""
        return _engolfo(df)

    def inside_bar(self, df: pd.DataFrame) -> dict:
        """Detecta inside bar: último candle dentro do range da vela-mãe."""
        return _inside_bar(df)

    def pullback(self, df: pd.DataFrame) -> dict:
        """Detecta pullback: retração contra a tendência seguida de reversão."""
        return _pullback(df)

    def pushback(self, df: pd.DataFrame) -> dict:
        """Detecta pushback: retração parcial após impulso direcional forte."""
        return _pushback(df)

    def topo_duplo(self, df: pd.DataFrame) -> dict:
        """Detecta topo duplo com rompimento da linha de pescoço."""
        return _topo_duplo(df)

    def fundo_duplo(self, df: pd.DataFrame) -> dict:
        """Detecta fundo duplo com rompimento da linha de pescoço."""
        return _fundo_duplo(df)

    def breakout(self, df: pd.DataFrame) -> dict:
        """Detecta breakout: fechamento fora do range dos últimos N candles."""
        return _breakout(df)

    # ── API consolidada ──────────────────────────────────────────────────────

    def detect_all(self, df: pd.DataFrame) -> dict:
        """Executa todos os padrões e retorna o dicionário completo.

        Equivalente à função de módulo :func:`detect`.
        """
        return detect(df)

    def summary(self, results: dict) -> dict:
        """Consolida o resultado de ``detect_all`` em métricas de alto nível.

        Args:
            results: Dicionário retornado por ``detect_all``.

        Returns::

            {
                "total_detected": int,       # padrões com detected=True
                "buy_signals":    list[str], # nomes dos padrões de compra
                "sell_signals":   list[str], # nomes dos padrões de venda
                "top_score":      float,     # maior score entre os detectados
                "bias":           str,       # "buy" | "sell" | "neutral"
            }
        """
        detected = {k: v for k, v in results.items() if v.get("detected")}
        buy_sigs  = [k for k, v in detected.items() if v["direction"] == "buy"]
        sell_sigs = [k for k, v in detected.items() if v["direction"] == "sell"]
        top_score = max((v["score"] for v in detected.values()), default=0.0)

        if len(buy_sigs) > len(sell_sigs):
            bias = "buy"
        elif len(sell_sigs) > len(buy_sigs):
            bias = "sell"
        else:
            bias = "neutral"

        return {
            "total_detected": len(detected),
            "buy_signals":    buy_sigs,
            "sell_signals":   sell_sigs,
            "top_score":      round(top_score, 4),
            "bias":           bias,
        }


def detect(df: pd.DataFrame) -> dict:
    """Detecta padrões técnicos no DataFrame de candles e retorna scores.

    Args:
        df: DataFrame com colunas open, high, low, close, volume.
            Mínimo recomendado: 50 candles para padrões de estrutura.
            A análise é sempre feita sobre o último candle no contexto
            dos candles anteriores.

    Returns:
        Dicionário com os 8 padrões detectados::

            {
                "pin_bar":    {"detected": bool, "direction": str, "score": float},
                "engolfo":    {"detected": bool, "direction": str, "score": float},
                "inside_bar": {"detected": bool, "direction": str, "score": float},
                "pullback":   {"detected": bool, "direction": str, "score": float},
                "pushback":   {"detected": bool, "direction": str, "score": float},
                "topo_duplo": {"detected": bool, "direction": str, "score": float},
                "fundo_duplo":{"detected": bool, "direction": str, "score": float},
                "breakout":   {"detected": bool, "direction": str, "score": float},
            }

        direction pode ser: 'buy', 'sell' ou 'neutral'.
        score varia de 0.0 (sinal fraco) a 1.0 (sinal forte).

    Raises:
        ValueError: se o DataFrame não contiver as colunas OHLCV obrigatórias.
    """
    required = {"open", "high", "low", "close", "volume"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes no DataFrame: {missing}")

    if df.empty or len(df) < 2:
        logger.warning("detect() requer ao menos 2 candles; retornando padrões sem detecção")
        return {name: _no_pattern() for name in _PATTERN_NAMES}

    return {
        "pin_bar":    _pin_bar(df),
        "engolfo":    _engolfo(df),
        "inside_bar": _inside_bar(df),
        "pullback":   _pullback(df),
        "pushback":   _pushback(df),
        "topo_duplo": _topo_duplo(df),
        "fundo_duplo":_fundo_duplo(df),
        "breakout":   _breakout(df),
    }
