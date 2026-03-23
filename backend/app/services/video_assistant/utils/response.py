from fastapi.responses import JSONResponse
from app.services.video_assistant.utils.status_code import StatusCode
from pydantic import BaseModel
from typing import Optional, Any


from fastapi.responses import JSONResponse

class ResponseWrapper:
    @staticmethod
    def success(data=None, msg="success"):
        return {
            "code": 200,
            "msg": msg,
            "data": data
        }

    @staticmethod
    def error(msg="error", code=500, data=None):
        return {
            "code": code,
            "msg": msg,
            "data": data
        }