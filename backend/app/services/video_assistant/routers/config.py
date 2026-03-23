from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.video_assistant.utils.response import ResponseWrapper as R

from app.services.video_assistant.cookie_manager import CookieConfigManager
from app.services.video_assistant.utils.ffmpeg_helper import ensure_ffmpeg_or_raise

router = APIRouter()
cookie_manager = CookieConfigManager()


class CookieUpdateRequest(BaseModel):
    platform: str
    cookie: str


@router.get("/get_downloader_cookie/{platform}")
def get_cookie(platform: str):
    cookie = cookie_manager.get(platform)
    if not cookie:
        return R.success(msg='未找到Cookies')
    return R.success(
        data={"platform": platform, "cookie": cookie}
    )


@router.get("/get_all")
def get_all_cookies():
    """
    获取所有平台的 Cookie 配置
    """
    all_cookies = cookie_manager.list_all()
    # 转换为前端期望的数组格式或对象格式
    # 前端代码 axios.get('/api/video-config/get_all') 处理的是数组 [{key, value}, ...]
    data = [{"key": f"{k}_cookie", "value": v} for k, v in all_cookies.items()]
    return data


class CookieUpdateItem(BaseModel):
    key: str
    value: str


@router.post("/update")
def update_cookie_v2(item: CookieUpdateItem):
    """
    更新指定平台的 Cookie (兼容新版前端)
    """
    # 前端传过来的 key 可能是 "bilibili_cookie"
    platform = item.key.replace("_cookie", "")
    cookie_manager.set(platform, item.value)
    return R.success()


@router.post("/update_downloader_cookie")
def update_cookie(data: CookieUpdateRequest):
    cookie_manager.set(data.platform, data.cookie)
    return R.success(

    )

@router.get("/sys_health")
async def sys_health():
    try:
        ensure_ffmpeg_or_raise()
        return R.success()
    except EnvironmentError:
        return R.error(msg="系统未安装 ffmpeg 请先进行安装")

@router.get("/sys_check")
async def sys_check():
    return R.success()