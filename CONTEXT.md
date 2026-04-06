# CONTEXT.md — Estado do Projeto

## Fase Atual
**Fase 3B concluída** — Dataset CNN gerado e rotulado.
Próxima: **Fase 4 — Modelo CNN (treino + avaliação)**.

## Arquivos Criados (ordem cronológica)
```
src/connection/iq_client.py       # Conexão IQ Option API
src/data/storage.py               # SQLite via SQLAlchemy (CandleStorage)
src/data/collector.py             # Coleta de candles da API
src/data/chart_image.py           # Geração de imagens 64x64 (mplfinance)
src/patterns/detector.py          # PatternDetector — 8 padrões técnicos
src/data/labeler.py               # Rotulagem: buy_win/loss, sell_win/loss, neutral
src/data/dataset_builder.py       # Orquestração do dataset (janela deslizante)
src/models/cnn.py                 # (esqueleto) CNN para classificação
src/models/dataset.py             # (esqueleto) PyTorch Dataset
src/models/trainer.py             # (esqueleto) Loop de treino
scripts/build_dataset.py          # CLI com tqdm para gerar dataset completo
```

## Testes Passando
| Arquivo              | Resultado         |
|----------------------|-------------------|
| tests/test_phase3a.py | 53/53 PASS       |
| tests/test_phase3b.py | 17/17 PASS       |

## Dados no Banco (`data/candles/candles.db`)
- Ativos com dados: EURUSD, GBPUSD, BTCUSD, ETHUSD, XAUUSD, USOUSD
- Timeframes: M1, M5, M15, M30
- Dataset gerado: ~11.880 imagens PNG em `data/images/`
- Labels CSV: `data/images/labels.csv` (colunas: filepath, label, direction, pattern_score, asset, timeframe, timestamp)

## Próximo Passo
Fase 4 — implementar e treinar a CNN:
1. `src/models/cnn.py` — arquitetura (input 64x64x3 → 5 classes)
2. `src/models/dataset.py` — PyTorch Dataset lendo `labels.csv`
3. `src/models/trainer.py` — treino com early stopping + métricas
4. `tests/test_phase4.py` — testes de forward pass e acurácia mínima
