from typing import List, Optional
from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    is_available: bool = True


AVAILABLE_MODELS = [
    ModelInfo(
        id="auto",
        name="自动选择",
        description="根据问题复杂度自动选择合适的模型"
    ),
    ModelInfo(
        id="qwen3-omni",
        name="Qwen3 Omni",
        description="基础模型，适合简单问题，响应速度快"
    ),
    ModelInfo(
        id="deepseek-v3",
        name="DeepSeek V3",
        description="增强模型，适合复杂问题，深度思考"
    ),
]


async def list_models() -> List[ModelInfo]:
    return AVAILABLE_MODELS


async def get_model(model_id: str) -> Optional[ModelInfo]:
    for model in AVAILABLE_MODELS:
        if model.id == model_id:
            return model
    return None
