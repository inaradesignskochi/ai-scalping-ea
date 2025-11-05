"""
Model loader utility for AI agents
Handles loading, caching, and hot-swapping of ML models
"""

import asyncio
import logging
import pickle
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Union
import joblib

from ..config import settings


class ModelLoader(ABC):
    """Abstract base class for model loaders"""

    @abstractmethod
    async def load_model(self, model_path: str) -> Any:
        """Load model from path"""
        pass

    @abstractmethod
    def validate_model(self, model: Any) -> bool:
        """Validate loaded model"""
        pass


class PickleModelLoader(ModelLoader):
    """Loader for pickle-serialized models"""

    async def load_model(self, model_path: str) -> Any:
        """Load model from pickle file"""
        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            return model
        except Exception as e:
            raise RuntimeError(f"Failed to load pickle model from {model_path}: {e}")

    def validate_model(self, model: Any) -> bool:
        """Validate pickle model has predict method"""
        return hasattr(model, 'predict')


class JoblibModelLoader(ModelLoader):
    """Loader for joblib-serialized models"""

    async def load_model(self, model_path: str) -> Any:
        """Load model from joblib file"""
        try:
            model = joblib.load(model_path)
            return model
        except Exception as e:
            raise RuntimeError(f"Failed to load joblib model from {model_path}: {e}")

    def validate_model(self, model: Any) -> bool:
        """Validate joblib model has predict method"""
        return hasattr(model, 'predict')


class TensorFlowModelLoader(ModelLoader):
    """Loader for TensorFlow/Keras models"""

    async def load_model(self, model_path: str) -> Any:
        """Load TensorFlow model"""
        try:
            import tensorflow as tf
            model = tf.keras.models.load_model(model_path)
            return model
        except Exception as e:
            raise RuntimeError(f"Failed to load TensorFlow model from {model_path}: {e}")

    def validate_model(self, model: Any) -> bool:
        """Validate TensorFlow model"""
        return hasattr(model, 'predict')


class PyTorchModelLoader(ModelLoader):
    """Loader for PyTorch models"""

    async def load_model(self, model_path: str) -> Any:
        """Load PyTorch model"""
        try:
            import torch
            model = torch.load(model_path, map_location=torch.device('cpu'))
            model.eval()  # Set to evaluation mode
            return model
        except Exception as e:
            raise RuntimeError(f"Failed to load PyTorch model from {model_path}: {e}")

    def validate_model(self, model: Any) -> bool:
        """Validate PyTorch model"""
        return hasattr(model, 'forward') or hasattr(model, '__call__')


class ModelCache:
    """LRU cache for loaded models"""

    def __init__(self, max_size: int = 10):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.access_times: Dict[str, float] = {}

    def get(self, model_path: str) -> Optional[Any]:
        """Get model from cache"""
        if model_path in self.cache:
            self.access_times[model_path] = time.time()
            return self.cache[model_path]['model']
        return None

    def put(self, model_path: str, model: Any, loader: ModelLoader):
        """Put model in cache"""
        if len(self.cache) >= self.max_size:
            # Remove least recently used
            lru_path = min(self.access_times, key=self.access_times.get)
            del self.cache[lru_path]
            del self.access_times[lru_path]

        self.cache[model_path] = {
            'model': model,
            'loader': loader,
            'loaded_at': time.time()
        }
        self.access_times[model_path] = time.time()

    def invalidate(self, model_path: str):
        """Remove model from cache"""
        if model_path in self.cache:
            del self.cache[model_path]
            del self.access_times[model_path]

    def clear(self):
        """Clear all cached models"""
        self.cache.clear()
        self.access_times.clear()


class UnifiedModelLoader:
    """Unified model loader with automatic format detection and caching"""

    def __init__(self):
        self.loaders = {
            '.pkl': PickleModelLoader(),
            '.pickle': PickleModelLoader(),
            '.joblib': JoblibModelLoader(),
            '.h5': TensorFlowModelLoader(),
            '.pb': TensorFlowModelLoader(),  # TensorFlow SavedModel
            '.pt': PyTorchModelLoader(),
            '.pth': PyTorchModelLoader()
        }
        self.cache = ModelCache(max_size=20)
        self.logger = logging.getLogger(__name__)

    async def load_model(self, model_path: str) -> Any:
        """Load model with caching and automatic format detection"""
        # Check cache first
        cached_model = self.cache.get(model_path)
        if cached_model:
            self.logger.debug(f"Loaded model from cache: {model_path}")
            return cached_model

        # Determine loader based on file extension
        path_obj = Path(model_path)
        extension = path_obj.suffix.lower()

        if extension not in self.loaders:
            # Try to detect format from file content
            loader = await self._detect_format(model_path)
        else:
            loader = self.loaders[extension]

        if not loader:
            raise ValueError(f"Unsupported model format for {model_path}")

        # Load model
        self.logger.info(f"Loading model: {model_path}")
        start_time = time.time()

        model = await loader.load_model(model_path)

        # Validate model
        if not loader.validate_model(model):
            raise ValueError(f"Invalid model format: {model_path}")

        load_time = time.time() - start_time
        self.logger.info(f"Model loaded in {load_time:.2f}s: {model_path}")

        # Cache model
        self.cache.put(model_path, model, loader)

        return model

    async def _detect_format(self, model_path: str) -> Optional[ModelLoader]:
        """Detect model format by trying different loaders"""
        for loader in self.loaders.values():
            try:
                # Try loading with this loader
                model = await loader.load_model(model_path)
                if loader.validate_model(model):
                    self.logger.info(f"Detected format for {model_path}: {loader.__class__.__name__}")
                    return loader
            except Exception:
                continue

        return None

    def invalidate_cache(self, model_path: str):
        """Invalidate cached model"""
        self.cache.invalidate(model_path)
        self.logger.info(f"Invalidated cache for: {model_path}")

    def clear_cache(self):
        """Clear all cached models"""
        self.cache.clear()
        self.logger.info("Cleared model cache")

    async def preload_models(self, model_paths: list[str]):
        """Preload multiple models asynchronously"""
        tasks = [self.load_model(path) for path in model_paths]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.info(f"Preloaded {len(model_paths)} models")


# Global model loader instance
model_loader = UnifiedModelLoader()