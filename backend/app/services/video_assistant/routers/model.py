from fastapi import APIRouter
from pydantic import BaseModel

from app.services.video_assistant.model import ModelService
from app.services.video_assistant.utils.response import ResponseWrapper as R
router = APIRouter()
modelService = ModelService()
class CreateModelRequest(BaseModel):
    provider_id: str
    model_name: str

class ModelFetchRequest(BaseModel):
    api_key: str
    base_url: str
    provider_id: str

# 返回体：模型信息
class ModelItem(BaseModel):
    id: int
    model_name: str
@router.get("/model_list")
def model_list():
    try:
        return R.success(modelService.get_all_models(True),msg="获取模型列表成功")
    except Exception as e:
        return R.error(e)
@router.get("/models/delete/{model_id}")
def delete_model(model_id: int):
    try:
        success = modelService.delete_model_by_id(model_id)
        if success:
            return R.success(msg="模型删除成功")
        else:
            return R.error("模型不存在或删除失败")
    except Exception as e:
        return R.error(f"删除模型失败: {e}")
@router.get("/model_list/{provider_id}")
def model_list(provider_id):
    return R.success(modelService.get_all_models_by_id(provider_id))

@router.post("/model_list_v2")
def post_model_list(data: ModelFetchRequest):
    """
    通过 POST 实时获取模型列表，支持在未保存设置前预览模型库
    """
    try:
        models = modelService.get_models_remote_v2(data.api_key, data.base_url, data.provider_id)
        return R.success(models)
    except Exception as e:
        return R.error(f"拉取实时模型列表失败: {e}")


@router.post("/models")
def create_model(data: CreateModelRequest):
    success = ModelService.add_new_model(data.provider_id, data.model_name)
    if not success:
        return R.error("模型添加失败")
    return R.success(msg="模型添加成功")

@router.get("/model_enable/{provider_id}")
def get_enabled_models_by_provider(provider_id: str):
    try:
        models = modelService.get_enabled_models_by_provider(provider_id)
        return R.success(models, msg="获取启用模型成功")
    except Exception as e:
        return R.error(f"获取启用模型失败: {e}")