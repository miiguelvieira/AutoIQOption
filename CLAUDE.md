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

## Regras de Economia de Tokens
- NUNCA repetir código já existente — referenciar pelo caminho e linha
- SEMPRE referenciar arquivos pelo caminho (`src/data/labeler.py:42`) ao invés de copiar conteúdo
- Comentários curtos e objetivos — sem explicar o óbvio
- Sem docstrings longas — uma linha basta se o nome já é descritivo
- Preferir edições cirúrgicas (Edit) a reescritas completas (Write)
- NUNCA mostrar o arquivo inteiro se só uma parte mudou

## Métricas Mínimas para Conta Real
- Taxa de acerto >= 65%
- Drawdown máximo <= 15%
- Mínimo 1000 trades demo avaliados

@CONTEXT.md

# Regras de Orquestração do Time

## Agentes disponíveis
- backend-engineer → APIs, banco de dados, autenticação
- ux-designer → interfaces, fluxos, prototipagem
- ai-specialist → LLMs, RAG, integração de IA
- frontend-engineer → React, componentes, estado
- qa-engineer → testes, validação, cobertura

## Quando rodar em PARALELO
Dispare múltiplos agentes ao mesmo tempo quando:
- As tarefas são independentes (sem shared state)
- Pertencem a domínios separados (UI, backend, testes)
- Têm arquivos claramente distintos

Exemplo:
→ Backend criando API + UX Designer criando protótipo = PARALELO

## Quando rodar em SEQUÊNCIA
Rode um depois do outro quando:
- A tarefa B depende do output da tarefa A
- Compartilham os mesmos arquivos (risco de conflito)
- O escopo está indefinido (entender antes de agir)

Exemplo:
→ UX Designer define fluxo → Backend cria a API necessária = SEQUÊNCIA

## Invocação obrigatória de agentes
Sempre que um agente for invocado, forneça no prompt:
1. Contexto: o que já foi feito no projeto
2. Escopo: exatamente o que este agente deve fazer
3. Arquivos: quais arquivos ler/criar/modificar
4. Entregável: o que deve estar no progress.md ao terminar

## Ao terminar cada tarefa
Todo agente deve atualizar o progress.md com:
- O que foi feito
- Quais arquivos foram criados/modificados
- Qual agente deve agir a seguir (se houver)