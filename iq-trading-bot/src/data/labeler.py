"""Rotulagem de imagens de gráficos para treino da CNN.

Para cada janela de candles verifica o resultado N candles à frente e
classifica como: buy_win, buy_loss, sell_win, sell_loss ou neutral.

Usa o PatternDetector para obter a direção sugerida e calcula o resultado
real pelo preço de fechamento futuro.

CSV gerado em data/images/labels.csv com colunas:
    filepath, label, direction, pattern_score, asset, timeframe, timestamp
"""

import csv
import logging
from pathlib import Path

import pandas as pd

from src.patterns.detector import PatternDetector

logger = logging.getLogger(__name__)

LABELS = ("buy_win", "buy_loss", "sell_win", "sell_loss", "neutral")
CSV_COLUMNS = ("filepath", "label", "direction", "pattern_score", "asset", "timeframe", "timestamp")


class Labeler:
    """Rotula janelas de candles combinando sinal do PatternDetector com resultado real."""

    def __init__(self, n_future: int = 5, min_score: float = 0.0):
        """
        Args:
            n_future: Número de candles à frente para avaliar o resultado.
            min_score: Score mínimo do padrão para considerar direção válida.
                       Abaixo disso, retorna 'neutral'.
        """
        self.n_future = n_future
        self.min_score = min_score
        self._detector = PatternDetector()

    # ──────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────

    def label_window(
        self,
        window_df: pd.DataFrame,
        future_df: pd.DataFrame,
        asset: str,
        timeframe: int,
        filepath: str | Path,
    ) -> dict:
        """Rotula uma única janela de candles.

        Args:
            window_df: DataFrame de candles da janela de análise (mínimo 50).
            future_df: DataFrame com N candles após a janela (para calcular resultado).
            asset: Nome do ativo (ex: EURUSD).
            timeframe: Timeframe em minutos.
            filepath: Path da imagem PNG correspondente à janela.

        Returns:
            Dicionário com colunas do CSV:
            filepath, label, direction, pattern_score, asset, timeframe, timestamp.
        """
        # Timestamp do último candle da janela
        ts = window_df["timestamp"].iloc[-1] if "timestamp" in window_df.columns else None

        # Detectar padrão
        try:
            patterns = self._detector.detect_all(window_df)
            summary = self._detector.summary(patterns)
        except Exception:
            logger.exception("Erro ao detectar padrões")
            return self._row(filepath, "neutral", "neutral", 0.0, asset, timeframe, ts)

        direction = summary["bias"]       # "buy" | "sell" | "neutral"
        score = summary["top_score"]

        # Sem padrão relevante → neutral
        if direction == "neutral" or score < self.min_score:
            return self._row(filepath, "neutral", direction, score, asset, timeframe, ts)

        # Sem candles futuros suficientes → neutral
        if future_df is None or len(future_df) < 1:
            return self._row(filepath, "neutral", direction, score, asset, timeframe, ts)

        # Preço de entrada = fechamento do último candle da janela
        entry_price = float(window_df["close"].iloc[-1])
        # Preço alvo = fechamento do último candle futuro disponível
        future_close = float(future_df["close"].iloc[min(self.n_future, len(future_df)) - 1])

        label = self._classify(direction, entry_price, future_close)
        return self._row(filepath, label, direction, score, asset, timeframe, ts)

    def label_batch(
        self,
        full_df: pd.DataFrame,
        asset: str,
        timeframe: int,
        image_paths: list,
        window_size: int = 50,
        step: int = 1,
    ) -> list[dict]:
        """Rotula múltiplas janelas deslizando sobre o DataFrame completo.

        Args:
            full_df: DataFrame completo de candles (ordem cronológica).
            asset: Nome do ativo.
            timeframe: Timeframe em minutos.
            image_paths: Lista de paths das imagens já geradas (mesma ordem das janelas).
            window_size: Tamanho de cada janela.
            step: Passo entre janelas.

        Returns:
            Lista de dicionários com rótulos (um por imagem).
        """
        labels = []
        total = len(full_df)
        path_idx = 0

        for start in range(0, total - window_size - self.n_future + 1, step):
            end = start + window_size
            window = full_df.iloc[start:end].reset_index(drop=True)
            future = full_df.iloc[end:end + self.n_future].reset_index(drop=True)

            filepath = image_paths[path_idx] if path_idx < len(image_paths) else ""
            path_idx += 1

            row = self.label_window(window, future, asset, timeframe, filepath)
            labels.append(row)

        logger.info(
            f"{len(labels)} janelas rotuladas — {asset} M{timeframe}  "
            f"(window={window_size}, step={step}, n_future={self.n_future})"
        )
        return labels

    @staticmethod
    def save_csv(labels: list[dict], output_path: str | Path = "data/images/labels.csv") -> Path:
        """Salva (ou acrescenta) rótulos no CSV.

        Se o arquivo não existir, cria com cabeçalho.
        Se existir, acrescenta sem duplicar o cabeçalho.

        Returns:
            Path do arquivo CSV.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        file_exists = out.exists()
        with open(out, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(CSV_COLUMNS))
            if not file_exists:
                writer.writeheader()
            writer.writerows(labels)

        logger.info(f"{len(labels)} rótulos salvos em {out}")
        return out

    @staticmethod
    def load_csv(path: str | Path = "data/images/labels.csv") -> pd.DataFrame:
        """Carrega o CSV de labels como DataFrame."""
        p = Path(path)
        if not p.exists():
            return pd.DataFrame(columns=list(CSV_COLUMNS))
        return pd.read_csv(p)

    # ──────────────────────────────────────────────────────────────────────
    # Helpers internos
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _classify(direction: str, entry: float, future_close: float) -> str:
        """Determina o label a partir da direção e do preço futuro."""
        if direction == "buy":
            return "buy_win" if future_close > entry else "buy_loss"
        if direction == "sell":
            return "sell_win" if future_close < entry else "sell_loss"
        return "neutral"

    @staticmethod
    def _row(
        filepath,
        label: str,
        direction: str,
        score: float,
        asset: str,
        timeframe: int,
        timestamp,
    ) -> dict:
        return {
            "filepath":      str(filepath),
            "label":         label,
            "direction":     direction,
            "pattern_score": round(float(score), 4),
            "asset":         asset,
            "timeframe":     int(timeframe),
            "timestamp":     str(timestamp) if timestamp is not None else "",
        }
