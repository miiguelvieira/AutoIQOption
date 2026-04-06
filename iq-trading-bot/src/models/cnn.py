"""Arquitetura CNN para classificação de imagens de candles.

Input:  (batch, 3, 64, 64) — imagem RGB 64x64
Output: (batch, 2)         — logits [bear, bull]
"""

import torch
import torch.nn as nn


class CandleCNN(nn.Module):
    """CNN leve otimizada para imagens 64x64 de candles.

    Arquitetura:
        3 blocos Conv-BN-ReLU-Pool progressivos (32 → 64 → 128 filtros)
        Dropout antes do classificador
        Head linear 128 → 64 → 2
    """

    def __init__(self, dropout: float = 0.4):
        super().__init__()

        self.features = nn.Sequential(
            # Bloco 1 — 64x64 → 32x32
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Bloco 2 — 32x32 → 16x16
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Bloco 3 — 16x16 → 8x8
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Bloco 4 — 8x8 → 4x4
            nn.Conv2d(128, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )

        # 128 * 4 * 4 = 2048
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(128 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout / 2),
            nn.Linear(256, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        return self.classifier(x)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Retorna probabilidades [P(bear), P(bull)] via softmax."""
        with torch.no_grad():
            logits = self.forward(x)
            return torch.softmax(logits, dim=1)

    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """Retorna classe predita: 0=bear, 1=bull."""
        return self.predict_proba(x).argmax(dim=1)
