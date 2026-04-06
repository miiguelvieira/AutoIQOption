"""Geração de imagens 64x64 de gráficos de candles para input da CNN."""

import logging
from pathlib import Path

import mplfinance as mpf
import pandas as pd

logger = logging.getLogger(__name__)

# Style minimalista: fundo preto, sem grid, cores bull/bear
_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#00ff00", down="#ff0000",
        wick={"up": "#00ff00", "down": "#ff0000"},
        edge={"up": "#00ff00", "down": "#ff0000"},
        volume={"up": "#00ff00", "down": "#ff0000"},
    ),
    facecolor="black",
    edgecolor="black",
    figcolor="black",
    gridstyle="",
    gridcolor="black",
)


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Garante que o DataFrame tem DatetimeIndex e colunas OHLCV corretas."""
    out = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    out = out.rename(columns={
        "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
    })
    out.index = pd.DatetimeIndex(out["timestamp"])
    out.drop(columns=["timestamp"], inplace=True)
    return out


def generate_image(
    df: pd.DataFrame,
    asset: str,
    timeframe: int,
    output_dir: str = "data/images",
    size: int = 64,
) -> Path | None:
    """Gera imagem PNG de candles a partir de um DataFrame.

    Args:
        df: DataFrame com colunas timestamp, open, high, low, close, volume.
        asset: Nome do ativo (ex: EURUSD).
        timeframe: Timeframe em minutos.
        output_dir: Diretório de saída.
        size: Tamanho em pixels (quadrado).

    Returns:
        Path da imagem salva ou None se falhar.
    """
    if len(df) < 5:
        logger.warning(f"Poucos candles ({len(df)}) para gerar imagem — {asset} M{timeframe}")
        return None

    ohlcv = _prepare_df(df)
    last_ts = ohlcv.index[-1].strftime("%Y%m%d%H%M%S")
    filename = f"{asset}_{timeframe}_{last_ts}.png"

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filepath = out_path / filename

    dpi = 100
    fig_size = size / dpi  # polegadas

    fig, axes = mpf.plot(
        ohlcv,
        type="candle",
        style=_STYLE,
        figsize=(fig_size, fig_size),
        returnfig=True,
        axisoff=True,
        tight_layout=True,
        scale_padding={"left": 0, "right": 0, "top": 0.1, "bottom": 0.1},
    )

    fig.savefig(
        filepath,
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0,
        facecolor="black",
    )
    fig.clf()
    import matplotlib.pyplot as plt
    plt.close(fig)

    # Forçar tamanho exato via resize
    from PIL import Image
    img = Image.open(filepath)
    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
        img.save(filepath)
        img.close()

    logger.info(f"Imagem salva: {filepath}")
    return filepath


def generate_batch(
    df: pd.DataFrame,
    asset: str,
    timeframe: int,
    window: int = 20,
    step: int = 1,
    output_dir: str = "data/images",
    size: int = 64,
) -> list[Path]:
    """Gera múltiplas imagens deslizando uma janela pelo DataFrame.

    Args:
        df: DataFrame completo de candles.
        window: Quantidade de candles por imagem.
        step: Passo entre janelas.

    Returns:
        Lista de paths das imagens geradas.
    """
    paths = []
    total = len(df)

    for start in range(0, total - window + 1, step):
        chunk = df.iloc[start : start + window].reset_index(drop=True)
        path = generate_image(chunk, asset, timeframe, output_dir, size)
        if path:
            paths.append(path)

    logger.info(f"{len(paths)} imagens geradas — {asset} M{timeframe} (window={window}, step={step})")
    return paths
