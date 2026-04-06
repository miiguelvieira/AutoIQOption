"""Script de construção do dataset CNN com barra de progresso tqdm.

Executa o DatasetBuilder para todos os ativos e timeframes do config.yaml,
exibindo:
  - Barra externa : progresso por combinação ativo × timeframe
  - Barra interna : progresso por janela dentro de cada combinação
  - Resumo final  : total de imagens e distribuição completa de labels

Uso:
    python scripts/build_dataset.py [--step N] [--window N] [--n-future N]

Exemplos:
    python scripts/build_dataset.py
    python scripts/build_dataset.py --step 5 --window 50 --n-future 5
"""

import argparse
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

from tqdm import tqdm

# ── Ajuste de PYTHONPATH para importar src/ a partir da raiz do projeto ──────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.data.chart_image import generate_image           # noqa: E402
from src.data.dataset_builder import DatasetBuilder, _iter_assets  # noqa: E402
from src.data.labeler import Labeler                      # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.WARNING,       # silencia logs de bibliotecas durante o progresso
    format="%(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("build_dataset")


# ─────────────────────────────────────────────────────────────────────────────
# DatasetBuilder com tqdm
# ─────────────────────────────────────────────────────────────────────────────

class TqdmDatasetBuilder(DatasetBuilder):
    """DatasetBuilder com barras de progresso tqdm em dois níveis."""

    def build(self) -> dict:
        assets = _iter_assets(self.cfg)
        timeframes = self.cfg.get("timeframes", [5])

        # Apaga CSV anterior para reinício limpo
        csv_path = Path(self.labels_csv)
        if csv_path.exists():
            csv_path.unlink()

        combos = [(a, tf) for a in assets for tf in timeframes]
        all_labels: list[dict] = []
        start_time = time.perf_counter()

        outer = tqdm(
            combos,
            desc="Ativos × Timeframes",
            unit="combo",
            ncols=80,
            colour="cyan",
        )

        for asset, tf in outer:
            outer.set_postfix_str(f"{asset} M{tf}")
            processed = self._build_asset_tf_tqdm(asset, tf)
            all_labels.extend(processed)

        elapsed = time.perf_counter() - start_time
        dist = Counter(row["label"] for row in all_labels)
        total = len(all_labels)

        self._print_summary_tqdm(total, dist, elapsed)

        return {
            "total_images": total,
            "label_distribution": dict(dist),
        }

    def _build_asset_tf_tqdm(self, asset: str, timeframe: int) -> list[dict]:
        """Processa um ativo/timeframe com barra de progresso interna."""
        min_candles = self.window_size + self.n_future
        df = self.storage.get_candles(asset, timeframe, limit=50_000)

        if df.empty or len(df) < min_candles:
            tqdm.write(
                f"  [SKIP] {asset} M{timeframe} — "
                f"{len(df)} candles disponíveis (mínimo {min_candles})"
            )
            return []

        total = len(df)
        n_windows = max(0, (total - min_candles) // self.step + 1)

        buffer: list[dict] = []
        all_labels: list[dict] = []

        inner = tqdm(
            range(0, total - min_candles + 1, self.step),
            desc=f"  {asset} M{timeframe}",
            unit="img",
            total=n_windows,
            ncols=80,
            leave=False,
            colour="green",
        )

        for start in inner:
            end = start + self.window_size
            window = df.iloc[start:end].reset_index(drop=True)
            future = df.iloc[end:end + self.n_future].reset_index(drop=True)

            img_path = generate_image(
                window,
                asset=asset,
                timeframe=timeframe,
                output_dir=self.images_dir,
                size=self.image_size,
            )
            if img_path is None:
                continue

            row = self.labeler.label_window(window, future, asset, timeframe, img_path)
            buffer.append(row)
            all_labels.append(row)

            # Exibe label atual no postfix da barra interna
            inner.set_postfix(label=row["label"], score=f"{row['pattern_score']:.2f}")

            # Salva progresso a cada save_every imagens
            if len(buffer) >= self.save_every:
                Labeler.save_csv(buffer, self.labels_csv)
                buffer.clear()

        # Flush final
        if buffer:
            Labeler.save_csv(buffer, self.labels_csv)

        tqdm.write(
            f"  [OK]   {asset} M{timeframe} — "
            f"{len(all_labels)} imagens geradas"
        )
        return all_labels

    @staticmethod
    def _print_summary_tqdm(total: int, dist: Counter, elapsed: float) -> None:
        """Imprime o resumo final formatado após a conclusão."""
        rate = total / elapsed if elapsed > 0 else 0.0
        mins, secs = divmod(int(elapsed), 60)

        print()
        print("=" * 60)
        print("  RESUMO DO DATASET")
        print("=" * 60)
        print(f"  Total de imagens geradas : {total:>8}")
        print(f"  Tempo total              : {mins:02d}m{secs:02d}s  ({rate:.1f} img/s)")
        print()
        print("  Distribuição de labels:")
        bar_width = 30
        for lbl in ("buy_win", "buy_loss", "sell_win", "sell_loss", "neutral"):
            count = dist.get(lbl, 0)
            pct = (count / total * 100) if total > 0 else 0.0
            filled = int(pct / 100 * bar_width)
            bar = "#" * filled + "-" * (bar_width - filled)
            print(f"    {lbl:<12} [{bar}]  {count:>6}  ({pct:5.1f}%)")
        print("=" * 60)
        print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Constrói dataset CNN com barra de progresso tqdm.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--window",   type=int, default=50,  help="Candles por janela")
    p.add_argument("--n-future", type=int, default=5,   help="Candles futuros para rotular")
    p.add_argument("--step",     type=int, default=1,   help="Passo entre janelas")
    p.add_argument("--save-every", type=int, default=100, help="Flush do CSV a cada N imagens")
    p.add_argument("--images-dir", default="data/images", help="Diretório de saída das imagens")
    p.add_argument("--labels-csv", default="data/images/labels.csv", help="Path do CSV de labels")
    p.add_argument("--db",       default="data/candles/candles.db",  help="Path do banco SQLite")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    print()
    print("=" * 60)
    print("  BUILD DATASET — IQ Option Trading Bot")
    print("=" * 60)
    print(f"  Janela        : {args.window} candles")
    print(f"  Candles futuros: {args.n_future}")
    print(f"  Passo          : {args.step}")
    print(f"  Salvar a cada  : {args.save_every} imagens")
    print(f"  Imagens        : {args.images_dir}")
    print(f"  Labels CSV     : {args.labels_csv}")
    print(f"  Banco SQLite   : {args.db}")
    print("=" * 60)
    print()

    builder = TqdmDatasetBuilder(
        config_path="config.yaml",
        db_path=args.db,
        images_dir=args.images_dir,
        labels_csv=args.labels_csv,
        window_size=args.window,
        n_future=args.n_future,
        step=args.step,
        save_every=args.save_every,
    )

    metrics = builder.build()

    if metrics["total_images"] == 0:
        print(
            "Nenhuma imagem gerada. Verifique se há candles no banco para os "
            "ativos e timeframes configurados em config.yaml."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
