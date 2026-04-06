import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.connection.iq_client import IQClient

logging.basicConfig(level=logging.INFO)


def test_connection():
    client = IQClient()

    print("[*] Testando conexao...")
    connected = client.connect()
    assert connected, "[ERRO] Falha na conexao"
    print("[OK] Conexao estabelecida")

    balance = client.get_balance()
    print(f"[SALDO] Conta demo: ${balance}")

    print("[*] Coletando candles EURUSD M5...")
    candles = client.get_candles("EURUSD", 5, 100)
    assert len(candles) > 0, "[ERRO] Nenhum candle retornado"
    print(f"[OK] {len(candles)} candles coletados")
    print(f"     Exemplo: {candles[0]}")


if __name__ == "__main__":
    test_connection()
