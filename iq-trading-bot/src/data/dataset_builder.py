"""Orquestração da construção completa do dataset CNN.

Fluxo:
    1. Lê todos os ativos e timeframes do config.yaml
    2. Carrega candles do SQLite via CandleStorage
    3. Para cada janela deslizante de 50 candles:
       - Gera imagem PNG via ChartImageGenerator
       - Rotula com Labeler
    4. Salva progresso a cada 100 imagens
    5. Imprime resumo: total de imagens e distribuição de labels
"""

import logging
from collections import Counter
from pathlib import Path

import yaml

from src.data.chart_image import generate_image
from src.data.labeler import CSV_COLUMNS, Labeler
from src.data.storage import CandleStorage

logger = logging.getLogger(__name__)


def _load_config(config_path: str = "config.yaml") -> dict:
    """Carrega o config.yaml relativo ao diretório do projeto."""
    p = Path(config_path)
    if not p.exists():
        # Tenta localizar o config subindo os diretórios a partir deste módulo
        candidate = Path(__file__).resolve().parent.parent.parent / "config.yaml"
        if candidate.exists():
            p = candidate
        else:
            raise FileNotFoundError(f"config.yaml não encontrado em {config_path} nem em {candidate}")
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _iter_assets(cfg: dict) -> list[str]:
    """Retorna lista plana de todos os ativos configurados."""
    assets_block = cfg.get("assets", {})
    assets = []
    for group in assets_block.values():
        if isinstance(group, list):
            assets.extend(group)
    return assets


class DatasetBuilder:
    """Constrói o dataset de imagens rotuladas para treino da CNN."""

    def __init__(
        self,
        config_path: str = "config.yaml",
        db_path: str = "data/candles/candles.db",
        images_dir: str = "data/images",
        labels_csv: str = "data/images/labels.csv",
        window_size: int = 50,
        n_future: int = 5,
        step: int = 1,
        save_every: int = 100,
        image_size: int = 64,
    ):
        self.cfg = _load_config(config_path)
        self.storage = CandleStorage(db_path)
        self.labeler = Labeler(n_future=n_future)
        self.images_dir = images_dir
        self.labels_csv = labels_csv
        self.window_size = window_size
        self.n_future = n_future
        self.step = step
        self.save_every = save_every
        self.image_size = self.cfg.get("data", {}).get("image_size", image_size)

    # ──────────────────────────────────────────────────────────────────────
    # Construção completa
    # ──────────────────────────────────────────────────────────────────────

    def build(self) -> dict:
        """Executa a construção completa do dataset.

        Returns:
            Dicionário com métricas: total_images, label_distribution.
        """
        assets = _iter_assets(self.cfg)
        timeframes = self.cfg.get("timeframes", [5])

        # Garante CSV vazio (novo build)
        csv_path = Path(self.labels_csv)
        if csv_path.exists():
            csv_path.unlink()

        all_labels = []
        total_images = 0

        for asset in assets:
            for tf in timeframes:
                processed = self._build_asset_tf(asset, tf)
                all_labels.extend(processed)
                total_images += len(processed)

        # Flush final (caso reste menos de save_every)
        # (já foi salvo incrementalmente, não precisa re-salvar)

        dist = Counter(row["label"] for row in all_labels)
        self._print_summary(total_images, dist)

        return {
            "total_images": total_images,
            "label_distribution": dict(dist),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Por ativo / timeframe
    # ──────────────────────────────────────────────────────────────────────

    def _build_asset_tf(self, asset: str, timeframe: int) -> list[dict]:
        """Gera imagens e labels para um único ativo/timeframe."""
        logger.info(f"Iniciando {asset} M{timeframe} ...")

        # Precisa de window_size + n_future candles no mínimo
        min_candles = self.window_size + self.n_future
        df = self.storage.get_candles(asset, timeframe, limit=50_000)

        if df.empty or len(df) < min_candles:
            logger.warning(
                f"Dados insuficientes para {asset} M{timeframe} "
                f"({len(df)} candles, mínimo {min_candles}) — pulando."
            )
            return []

        total = len(df)
        buffer: list[dict] = []
        all_labels: list[dict] = []

        for start in range(0, total - min_candles + 1, self.step):
            end = start + self.window_size
            window = df.iloc[start:end].reset_index(drop=True)
            future = df.iloc[end:end + self.n_future].reset_index(drop=True)

            # Gera imagem
            img_path = generate_image(
                window,
                asset=asset,
                timeframe=timeframe,
                output_dir=self.images_dir,
                size=self.image_size,
            )
            if img_path is None:
                continue

            # Rotula
            row = self.labeler.label_window(window, future, asset, timeframe, img_path)
            buffer.append(row)
            all_labels.append(row)

            # Salva progresso a cada save_every imagens
            if len(buffer) >= self.save_every:
                Labeler.save_csv(buffer, self.labels_csv)
                logger.info(
                    f"  Progresso salvo: {len(all_labels)} imagens "
                    f"({asset} M{timeframe})"
                )
                buffer.clear()

        # Flush final para este ativo/timeframe
        if buffer:
            Labeler.save_csv(buffer, self.labels_csv)

        logger.info(f"Concluído {asset} M{timeframe}: {len(all_labels)} imagens geradas.")
        return all_labels

    # ──────────────────────────────────────────────────────────────────────
    # Resumo
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _print_summary(total: int, dist: Counter) -> None:
        print("\n" + "=" * 55)
        print("  RESUMO DO DATASET")
        print("=" * 55)
        print(f"  Total de imagens geradas : {total}")
        print()
        print("  Distribuição de labels:")
        for lbl in ("buy_win", "buy_loss", "sell_win", "sell_loss", "neutral"):
            count = dist.get(lbl, 0)
            pct = (count / total * 100) if total > 0 else 0.0
            print(f"    {lbl:<12} : {count:>6}  ({pct:5.1f}%)")
        print("=" * 55 + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# CLI rápida
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Muda o CWD para a raiz do projeto (iq-trading-bot/)
    root = Path(__file__).resolve().parent.parent.parent
    os.chdir(root)

    builder = DatasetBuilder()
    metrics = builder.build()
    print(f"Métricas finais: {metrics}")
