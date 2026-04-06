"""Coleta candles de todos os ativos e timeframes do config.yaml."""

import logging
import time

from src.connection.iq_client import IQClient
from src.data.storage import CandleStorage

logger = logging.getLogger(__name__)

API_MAX_PER_REQUEST = 1000  # limite real da API por chamada


class CandleCollector:
    def __init__(self, config: dict, client: IQClient, storage: CandleStorage):
        self.config = config
        self.client = client
        self.storage = storage
        self.target_candles = config["data"].get("candles_per_request", 5000)

    def _all_assets(self) -> list[str]:
        """Retorna lista plana de todos os ativos de todas as categorias."""
        assets = []
        for category in self.config["assets"].values():
            assets.extend(category)
        return assets

    def collect(self, asset: str, timeframe: int) -> int:
        """Coleta candles paginando em blocos de 1000 até atingir o alvo.

        Usa o timestamp do candle mais antigo de cada bloco para buscar
        o próximo bloco mais atrás no tempo.
        """
        total_collected = []
        remaining = self.target_candles
        end_time = time.time()

        while remaining > 0:
            batch_size = min(remaining, API_MAX_PER_REQUEST)
            candles = self.client.api.get_candles(
                asset, timeframe * 60, batch_size, end_time
            )
            if not candles:
                break

            total_collected.extend(candles)
            remaining -= len(candles)

            # Próximo bloco: antes do candle mais antigo deste bloco
            end_time = candles[0]["from"] - 1

            if len(candles) < batch_size:
                break  # não há mais dados históricos

            time.sleep(0.3)

        if not total_collected:
            logger.warning(f"Nenhum candle retornado para {asset} M{timeframe}")
            return 0

        logger.info(f"{len(total_collected)} candles coletados via API — {asset} M{timeframe}")
        inserted = self.storage.save_candles(asset, timeframe, total_collected)
        return inserted

    def collect_all(self) -> dict:
        """Percorre todos os ativos e timeframes do config.

        Retorna resumo: {(asset, timeframe): candles_inseridos}
        """
        assets = self._all_assets()
        timeframes = self.config["timeframes"]
        results = {}

        total_combos = len(assets) * len(timeframes)
        logger.info(
            f"Iniciando coleta: {len(assets)} ativos x {len(timeframes)} timeframes "
            f"= {total_combos} combinacoes ({self.target_candles} candles/combo)"
        )

        for asset in assets:
            for tf in timeframes:
                key = (asset, tf)
                try:
                    inserted = self.collect(asset, tf)
                    results[key] = inserted
                    logger.info(f"  {asset} M{tf}: {inserted} candles novos")
                except Exception:
                    results[key] = -1
                    logger.exception(f"  {asset} M{tf}: ERRO na coleta")

                time.sleep(0.5)

        total_inserted = sum(v for v in results.values() if v > 0)
        errors = sum(1 for v in results.values() if v < 0)
        logger.info(f"Coleta finalizada: {total_inserted} candles salvos, {errors} erros")

        return results


def run_collector(config: dict) -> dict:
    """Atalho: conecta, coleta tudo e retorna o resumo."""
    client = IQClient()
    if not client.connect():
        raise ConnectionError("Falha ao conectar na IQ Option")

    db_path = config["data"].get("storage_path", "data/candles") + "/candles.db"
    storage = CandleStorage(db_path=db_path)

    collector = CandleCollector(config, client, storage)
    return collector.collect_all()
