"""Dataset PyTorch para treino da CNN.

Carrega imagens de data/images e gera labels automaticamente a partir
do banco (candle seguinte à janela: bull=1, bear=0).
"""

import re
from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from src.data.storage import CandleStorage


class CandleImageDataset(Dataset):
    """Dataset que associa imagens de candles ao label do próximo candle.

    Label:
        1 = próximo candle é bullish (close > open)
        0 = próximo candle é bearish (close <= open)
    """

    def __init__(
        self,
        images_dir: str = "data/images",
        db_path: str = "data/candles/candles.db",
        image_size: int = 64,
        assets: list[str] | None = None,
        timeframes: list[int] | None = None,
    ):
        self.storage = CandleStorage(db_path)
        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.0),   # NÃO flip horizontal (inverteria bull/bear)
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.RandomAffine(degrees=0, translate=(0.05, 0.05)),
            transforms.ToTensor(),               # [0,255] -> [0.0, 1.0], shape (C, H, W)
            transforms.Normalize(
                mean=[0.5, 0.5, 0.5],
                std=[0.5, 0.5, 0.5],
            ),
        ])

        self.samples: list[tuple[Path, int]] = []
        self._build_samples(images_dir, assets, timeframes)

    # ------------------------------------------------------------------
    # Parser do nome do arquivo: {ASSET}_{TF}_{YYYYMMDDHHMMSS}.png
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_filename(name: str) -> tuple[str, int, pd.Timestamp] | None:
        m = re.match(r"^([A-Z]+)_(\d+)_(\d{14})\.png$", name)
        if not m:
            return None
        asset = m.group(1)
        tf = int(m.group(2))
        ts = pd.to_datetime(m.group(3), format="%Y%m%d%H%M%S", utc=True)
        return asset, tf, ts

    def _build_samples(
        self,
        images_dir: str,
        assets: list[str] | None,
        timeframes: list[int] | None,
    ) -> None:
        """Constrói a lista (image_path, label) para todos os arquivos válidos."""
        img_dir = Path(images_dir)
        if not img_dir.exists():
            raise FileNotFoundError(f"Diretório de imagens não encontrado: {img_dir}")

        # Cache de candles por (asset, timeframe) para evitar múltiplas queries
        candle_cache: dict[tuple, pd.DataFrame] = {}

        for img_path in sorted(img_dir.glob("*.png")):
            parsed = self._parse_filename(img_path.name)
            if parsed is None:
                continue

            asset, tf, last_ts = parsed

            if assets and asset not in assets:
                continue
            if timeframes and tf not in timeframes:
                continue

            key = (asset, tf)
            if key not in candle_cache:
                raw = self.storage.get_candles(asset, tf, limit=99999)
                # Garantir timestamps UTC (banco armazena naive)
                raw["timestamp"] = pd.to_datetime(raw["timestamp"]).dt.tz_localize("UTC")
                candle_cache[key] = raw

            df = candle_cache[key]
            if df.empty:
                continue

            # Próximo candle após o timestamp da imagem
            future = df[df["timestamp"] > last_ts].head(1)
            if future.empty:
                continue  # sem candle futuro = sem label

            next_candle = future.iloc[0]
            label = 1 if next_candle["close"] > next_candle["open"] else 0
            self.samples.append((img_path, label))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]
        img = Image.open(img_path).convert("RGB")
        tensor = self.transform(img)
        return tensor, label

    def label_distribution(self) -> dict:
        """Retorna contagem de labels para verificar balanceamento."""
        bull = sum(1 for _, l in self.samples if l == 1)
        bear = sum(1 for _, l in self.samples if l == 0)
        return {"bull": bull, "bear": bear, "total": len(self.samples)}
