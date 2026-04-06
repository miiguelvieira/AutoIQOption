import time
import logging
from iqoptionapi.stable_api import IQ_Option
from dotenv import load_dotenv
import os
import yaml

load_dotenv()
logger = logging.getLogger(__name__)

class IQClient:
    def __init__(self, config_path="config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.email = os.getenv("IQ_EMAIL")
        self.password = os.getenv("IQ_PASSWORD")
        self.account_type = os.getenv("IQ_ACCOUNT_TYPE", "PRACTICE")
        self.api = None

    def connect(self) -> bool:
        """Conecta na IQ Option e retorna True se bem sucedido."""
        try:
            self.api = IQ_Option(self.email, self.password)
            check, reason = self.api.connect()

            if check:
                self.api.change_balance(self.account_type)
                logger.info(f"Conectado com sucesso — conta: {self.account_type}")
                return True
            else:
                logger.error(f"Falha na conexão: {reason}")
                return False

        except Exception as e:
            logger.error(f"Erro ao conectar: {e}")
            return False

    def reconnect(self, retries=3, delay=5) -> bool:
        """Tenta reconectar N vezes com delay entre tentativas."""
        for attempt in range(1, retries + 1):
            logger.info(f"Tentativa de reconexão {attempt}/{retries}...")
            if self.connect():
                return True
            time.sleep(delay)
        logger.error("Todas as tentativas de reconexão falharam.")
        return False

    def get_balance(self) -> float:
        """Retorna o saldo atual da conta."""
        return self.api.get_balance()

    def get_candles(self, asset: str, timeframe: int, count: int) -> list:
        """
        Coleta candles históricos.
        asset: ex 'EURUSD'
        timeframe: em segundos (60=M1, 300=M5, 900=M15)
        count: quantidade de candles
        """
        try:
            candles = self.api.get_candles(asset, timeframe * 60, count, time.time())
            logger.info(f"{len(candles)} candles coletados — {asset} M{timeframe}")
            return candles
        except Exception as e:
            logger.error(f"Erro ao coletar candles de {asset}: {e}")
            return []

    def is_connected(self) -> bool:
        """Verifica se a conexão ainda está ativa."""
        if self.api is None:
            return False
        return self.api.check_connect()