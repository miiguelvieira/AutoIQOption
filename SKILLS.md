# Skills do Projeto

## SKILL: Conexão IQ Option
- Arquivo: src/connection/iq_client.py
- Como usar: IQClient(email, password, account_type)
- Retorna candles: client.get_candles(asset, timeframe, count)
- Status: [ ] Pendente / [x] Implementado / [x] Testado dia 05.04.2026

## SKILL: Geração de Imagem de Gráfico
- Arquivo: src/data/chart_image.py
- Como usar: generate_chart_image(df_candles, output_path)
- Gera PNG 64x64 com mplfinance
- Status: [ ] Pendente [x] Implementado e [x] Testado dia 05.04.2026

## SKILL: Detecção de Padrões por Regras
- Arquivo: src/patterns/detector.py
- Padrões: pullback, pushback, pin bar, engolfo,
  inside bar, topo/fundo duplo, breakout
- Como usar: detect_patterns(df_candles) → dict
- Status: [ ] Pendente [x] Implementado e [x] Testado dia 05.04.2026

## SKILL: CNN — Reconhecimento Visual
- Arquivo: src/cnn/model.py
- Input: imagem PNG 64x64
- Output: score de confiança 0.0 a 1.0
- Status: [ ] Pendente

## SKILL: Agente RL (PPO)
- Arquivo: src/agent/ppo_agent.py
- Input: vetor de features (indicadores + CNN score)
- Output: BUY / SELL / HOLD
- Status: [ ] Pendente

## SKILL: Martingale Engine
- Arquivo: src/martingale/engine.py
- Níveis: 2 (lote x2 após perda)
- Regras: só ativa se confiança >= 70%
- Cooldown após 2 perdas consecutivas
- Status: [ ] Pendente