"""Loop de treino e avaliação da CNN."""

import logging
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split

from src.models.cnn import CandleCNN
from src.models.dataset import CandleImageDataset

logger = logging.getLogger(__name__)


def train(
    config: dict,
    epochs: int = 30,
    batch_size: int = 32,
    lr: float = 1e-3,
    val_split: float = 0.2,
    save_best: bool = True,
) -> CandleCNN:
    """Treina a CNN e salva o melhor modelo.

    Args:
        config: Dicionário do config.yaml.
        epochs: Número de épocas.
        batch_size: Tamanho do batch.
        lr: Learning rate inicial.
        val_split: Proporção do dataset para validação.
        save_best: Salva o checkpoint com melhor val_acc.

    Returns:
        Modelo treinado.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Dispositivo: {device}")

    # Dataset
    data_cfg = config["data"]
    dataset = CandleImageDataset(
        images_dir=data_cfg.get("images_path", "data/images"),
        db_path=data_cfg.get("storage_path", "data/candles") + "/candles.db",
        image_size=data_cfg.get("image_size", 64),
    )

    dist = dataset.label_distribution()
    logger.info(f"Dataset: {dist['total']} amostras — bull={dist['bull']} bear={dist['bear']}")

    if dist["total"] < 20:
        raise ValueError(f"Dataset muito pequeno ({dist['total']} amostras). Gere mais imagens.")

    # Split treino/validação
    val_size = max(1, int(len(dataset) * val_split))
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    # Modelo
    model = CandleCNN(dropout=0.4).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = nn.CrossEntropyLoss()

    # Balanceamento: peso inverso à frequência
    bull_w = dist["total"] / (2 * dist["bull"]) if dist["bull"] > 0 else 1.0
    bear_w = dist["total"] / (2 * dist["bear"]) if dist["bear"] > 0 else 1.0
    class_weights = torch.tensor([bear_w, bull_w], dtype=torch.float32).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    model_dir = Path(config["agent"].get("cnn_model_path", "models/cnn"))
    model_dir.mkdir(parents=True, exist_ok=True)
    best_path = model_dir / "best.pt"

    best_val_acc = 0.0

    for epoch in range(1, epochs + 1):
        # — Treino —
        model.train()
        train_loss, train_correct = 0.0, 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(images)
            train_correct += (logits.argmax(1) == labels).sum().item()

        train_loss /= train_size
        train_acc = train_correct / train_size

        # — Validação —
        model.eval()
        val_loss, val_correct = 0.0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                logits = model(images)
                val_loss += criterion(logits, labels).item() * len(images)
                val_correct += (logits.argmax(1) == labels).sum().item()

        val_loss /= val_size
        val_acc = val_correct / val_size

        scheduler.step(val_loss)

        logger.info(
            f"Epoch {epoch:3d}/{epochs} | "
            f"train loss={train_loss:.4f} acc={train_acc:.3f} | "
            f"val loss={val_loss:.4f} acc={val_acc:.3f}"
        )

        if save_best and val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_path)
            logger.info(f"  -> Melhor modelo salvo (val_acc={val_acc:.3f})")

    logger.info(f"Treino finalizado. Melhor val_acc={best_val_acc:.3f}")
    return model


def load_model(config: dict, device: str | None = None) -> CandleCNN:
    """Carrega o melhor checkpoint salvo."""
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    path = Path(config["agent"].get("cnn_model_path", "models/cnn")) / "best.pt"
    if not path.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {path}. Treine primeiro.")

    model = CandleCNN()
    model.load_state_dict(torch.load(path, map_location=device))
    model.to(device)
    model.eval()
    logger.info(f"Modelo carregado de {path}")
    return model
