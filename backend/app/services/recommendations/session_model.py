"""
services/recommendations/session_model.py — GRU4Rec Session-Based Model.

Torch is optional. If not installed, SessionModelRegistry falls back to
returning empty predictions, and the hybrid engine uses cold-start/trending
candidates exclusively. The storefront still shows recommendations.

FIXES:
  • _bootstrap_random_model() now uses REAL SKU IDs from the catalog
    instead of fake prod_000 IDs that never matched anything.
  • load() is safe to call at startup — always ends with a usable model.
"""
from __future__ import annotations

import logging
import os

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
except ImportError:
    TORCH_AVAILABLE = False
    DEVICE = None
    torch = None    # type: ignore
    nn = None       # type: ignore
    F = None        # type: ignore

from app.core.config import settings

logger = logging.getLogger(__name__)

if not TORCH_AVAILABLE:
    logger.warning(
        "PyTorch not installed — GRU4Rec disabled. "
        "Recommendations will use cold-start/trending fallback."
    )

# ── Real SKU IDs from the product catalog ─────────────────────────────────────
# These must match the IDs used in engine.py _CATEGORY_TRENDING and
# what the frontend sends as product_id in events.
CATALOG_SKUS: list[str] = [
    # Electronics
    "SKU001000", "SKU006000", "SKU006001", "SKU006002",
    # Gaming
    "SKU003200", "SKU007000", "SKU007001", "SKU007002",
    # Cameras
    "SKU004100", "SKU008000", "SKU008001", "SKU008002",
    # Cookware
    "SKU002100", "SKU009000", "SKU009001",
    # Clothing
    "SKU001500", "SKU010000", "SKU010001", "SKU010002",
    # Beauty & Health
    "SKU005500", "SKU011000", "SKU011001", "SKU011002",
    # Sports
    "SKU012000", "SKU012001", "SKU012002", "SKU012003",
    # Home & Kitchen
    "SKU013000", "SKU013001", "SKU013002",
    # Footwear
    "SKU016000", "SKU016001", "SKU016002",
    # Accessories
    "SKU015000", "SKU015001",
    # Books & Media
    "SKU014000", "SKU014001",
]


class GRU4Rec:
    """Stub class when torch unavailable; real class defined below."""
    pass


if TORCH_AVAILABLE:
    import torch.nn as _nn

    class GRU4Rec(_nn.Module):  # type: ignore[no-redef]
        def __init__(
            self,
            n_items: int,
            embedding_dim: int = 64,
            hidden_size: int = 128,
            num_layers: int = 2,
            dropout: float = 0.3,
            padding_idx: int = 0,
        ):
            super().__init__()
            self.n_items = n_items
            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.item_embedding = _nn.Embedding(
                n_items + 1, embedding_dim, padding_idx=padding_idx
            )
            self.gru = _nn.GRU(
                input_size=embedding_dim,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.output_dropout = _nn.Dropout(p=dropout)
            self.output_layer = _nn.Linear(hidden_size, n_items)
            self._init_weights()

        def _init_weights(self) -> None:
            import torch.nn as nn2
            nn2.init.xavier_uniform_(self.item_embedding.weight[1:])
            nn2.init.xavier_uniform_(self.output_layer.weight)
            nn2.init.zeros_(self.output_layer.bias)
            for name, param in self.gru.named_parameters():
                if "weight" in name:
                    nn2.init.orthogonal_(param)
                elif "bias" in name:
                    nn2.init.zeros_(param)

        def forward(self, item_seq, seq_lengths=None):
            import torch as t
            embedded = self.item_embedding(item_seq)
            if seq_lengths is not None:
                embedded = t.nn.utils.rnn.pack_padded_sequence(
                    embedded, seq_lengths.cpu(), batch_first=True, enforce_sorted=False
                )
            gru_out, hidden = self.gru(embedded)
            if seq_lengths is not None:
                gru_out, _ = t.nn.utils.rnn.pad_packed_sequence(gru_out, batch_first=True)
            session_repr = self._gather_last_valid(gru_out, seq_lengths)
            session_repr = self.output_dropout(session_repr)
            logits = self.output_layer(session_repr)
            return logits, hidden

        def _gather_last_valid(self, gru_out, seq_lengths):
            if seq_lengths is None:
                return gru_out[:, -1, :]
            idx = (seq_lengths - 1).long().clamp(min=0).to(gru_out.device)
            idx = idx.unsqueeze(1).unsqueeze(2).expand(-1, 1, gru_out.size(2))
            return gru_out.gather(1, idx).squeeze(1)

        @torch.no_grad()  # type: ignore[misc]
        def predict_next(
            self, session_items: list[int], top_k: int = 10, exclude_seen: bool = True
        ) -> list[tuple[int, float]]:
            import torch as t
            import torch.nn.functional as ff
            self.eval()
            max_len = settings.MAX_SESSION_LENGTH
            if len(session_items) > max_len:
                session_items = session_items[-max_len:]
            item_tensor = t.tensor([session_items], dtype=t.long, device=DEVICE)
            seq_len = t.tensor([len(session_items)], dtype=t.long)
            logits, _ = self.forward(item_tensor, seq_len)
            scores = ff.softmax(logits[0], dim=-1).cpu().numpy()
            if exclude_seen:
                for item_id in session_items:
                    if 0 < item_id < len(scores):
                        scores[item_id] = 0.0
            top_k_actual = min(top_k, len(scores))
            top_indices = np.argpartition(scores, -top_k_actual)[-top_k_actual:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
            return [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]


# ── Model Registry ────────────────────────────────────────────────────────────

class SessionModelRegistry:
    """Lazy-load model singleton. Gracefully no-ops when torch unavailable."""

    def __init__(self):
        self._model = None
        self._item_to_idx: dict[str, int] = {}
        self._idx_to_item: dict[int, str] = {}
        self._n_items = 0

    def load(self, model_path: str | None = None) -> bool:
        """
        Load model from disk if available, otherwise bootstrap with real SKU IDs.
        Always safe to call — never raises.
        """
        if not TORCH_AVAILABLE:
            logger.info("Skipping GRU4Rec load — torch not installed. Using cold-start only.")
            self._bootstrap_id_map()
            return False

        path = model_path or settings.GRU_MODEL_PATH
        if os.path.exists(path):
            try:
                import torch as t
                checkpoint = t.load(path, map_location=DEVICE, weights_only=False)
                self._item_to_idx = checkpoint["item_to_idx"]
                self._idx_to_item = {v: k for k, v in self._item_to_idx.items()}
                self._n_items = len(self._item_to_idx)
                self._model = GRU4Rec(
                    n_items=self._n_items,
                    hidden_size=settings.GRU_HIDDEN_SIZE,
                    num_layers=settings.GRU_NUM_LAYERS,
                    dropout=settings.GRU_DROPOUT,
                )
                self._model.load_state_dict(checkpoint["model_state"])
                self._model.to(DEVICE)
                self._model.eval()
                logger.info("GRU4Rec loaded from %s (%d items)", path, self._n_items)
                return True
            except Exception as exc:
                logger.warning("Failed to load GRU4Rec weights: %s — bootstrapping", exc)

        # FIX: bootstrap uses REAL catalog SKUs, not fake prod_000 IDs
        self._bootstrap_random_model()
        return False

    def _bootstrap_id_map(self) -> None:
        """Build ID map with real SKUs — no model, cold-start-only mode."""
        skus = CATALOG_SKUS
        self._n_items = len(skus)
        self._item_to_idx = {sku: i + 1 for i, sku in enumerate(skus)}  # 0 = padding
        self._idx_to_item = {v: k for k, v in self._item_to_idx.items()}
        logger.info("SessionModel: ID map built with %d real SKUs (no model)", self._n_items)

    def _bootstrap_random_model(self) -> None:
        """
        Random-weight GRU4Rec using REAL catalog SKU IDs.
        FIX: previously used prod_000 fake IDs — now uses actual SKUs so
        predictions can be mapped back to real products.
        """
        import torch as t
        skus = CATALOG_SKUS
        self._n_items = len(skus)
        # Index 0 reserved for padding
        self._item_to_idx = {sku: i + 1 for i, sku in enumerate(skus)}
        self._idx_to_item = {v: k for k, v in self._item_to_idx.items()}

        self._model = GRU4Rec(
            n_items=self._n_items,
            hidden_size=settings.GRU_HIDDEN_SIZE,
            num_layers=settings.GRU_NUM_LAYERS,
            dropout=settings.GRU_DROPOUT,
        )
        self._model.to(DEVICE)
        self._model.eval()
        logger.info(
            "GRU4Rec bootstrapped with random weights, %d real SKUs", self._n_items
        )

    def predict(self, session_product_ids: list[str], top_k: int = 10) -> list[tuple[str, float]]:
        """
        Returns [(product_id, score)].
        Empty list if torch unavailable or session has no known items.
        """
        if not TORCH_AVAILABLE or self._model is None:
            return []

        item_indices = [
            self._item_to_idx[pid]
            for pid in session_product_ids
            if pid in self._item_to_idx
        ]
        if not item_indices:
            return []

        raw = self._model.predict_next(item_indices, top_k=top_k)
        return [
            (self._idx_to_item[idx], score)
            for idx, score in raw
            if idx in self._idx_to_item
        ]

    @property
    def is_loaded(self) -> bool:
        return self._model is not None


# Module-level singleton — call .load() at app startup
session_model = SessionModelRegistry()