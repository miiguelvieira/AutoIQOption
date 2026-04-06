# CLAUDE.md

# IQ Option Trading Bot — Contexto do Projeto

## Visão Geral
Bot de trading automatizado com IA para operar na IQ Option.
Usa Reinforcement Learning (PPO) + CNN para reconhecimento
visual de padrões gráficos + Martingale 2 níveis.

## Ativos Operados
- Forex: EUR/USD, GBP/USD
- Crypto: BTC/USD, ETH/USD
- Índices e Commodities: Ouro, Petróleo, algodão

## Timeframes
- M1, M5, M15, M30 (multi-timeframe)

## Stack
- Python 3.10+
- iqoptionapi (conexão IQ Option)
- stable-baselines3 (PPO)
- PyTorch (CNN)
- mplfinance (geração de imagens)
- pandas-ta (indicadores)
- SQLite (armazenamento)

## Estrutura de Pastas

iq-trading-bot/
├── CLAUDE.md
├── SKILLS.md
├── data/
│   ├── candles/        # CSVs com histórico
│   └── images/         # PNGs dos gráficos
├── src/
│   ├── connection/     # Conexão IQ Option API
│   ├── data/           # Coleta e processamento
│   ├── patterns/       # Detecção de padrões (regras)
│   ├── cnn/            # Modelo de visão computacional
│   ├── agent/          # Agente RL (PPO)
│   ├── martingale/     # Engine de gestão de banca
│   └── dashboard/      # Monitor em tempo real
├── models/
│   ├── cnn/            # Pesos treinados da CNN
│   └── rl/             # Checkpoints do agente PPO
├── tests/
├── logs/
└── config.yaml         # Configurações globais

## Regras de Desenvolvimento
- SEMPRE testar na conta demo antes de qualquer mudança
- NUNCA hardcodar credenciais — usar variáveis de ambiente
- NUNCA ultrapassar 2 níveis de Martingale
- NUNCA remover o stop de perda diária
- Todo módulo novo deve ter teste em tests/

## Variáveis de Ambiente Necessárias
- IQ_EMAIL — email da conta IQ Option
- IQ_PASSWORD — senha da conta IQ Option
- IQ_ACCOUNT_TYPE — "PRACTICE" (demo) ou "REAL"

## Fases do Projeto
1. Conexão e coleta de dados ← FASE ATUAL
2. Feature engineering + padrões
3. Geração de imagens + CNN
4. Ambiente RL + fusão de features
5. Martingale engine
6. Validação em demo
7. Produção gradual

## Comando para Rodar
```bash
python src/main.py
```

## Métricas Mínimas para Conta Real
- Taxa de acerto >= 65%
- Drawdown máximo <= 15%
- Mínimo 1000 trades demo avaliados