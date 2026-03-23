"""
短信验证码服务
集成阿里云短信服务
"""
import random
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional

from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models

from app.core.config import settings

logger = logging.getLogger(__name__)

# 内存中存储验证码（生产环境应使用 Redis）
_verification_codes: Dict[str, Dict] = {}


class SMSService:
    """短信验证码服务类"""
    
    @staticmethod
    def create_client() -> Optional[Dysmsapi20170525Client]:
        """创建阿里云短信客户端"""
        logger.debug(f"Creating SMS client with Key ID: {settings.ALIBABA_CLOUD_ACCESS_KEY_ID}")
        if not settings.ALIBABA_CLOUD_ACCESS_KEY_ID or not settings.ALIBABA_CLOUD_ACCESS_KEY_SECRET:
            logger.warning("阿里云短信配置缺失，将使用模拟模式")
            return None
            
        config = open_api_models.Config(
            access_key_id=settings.ALIBABA_CLOUD_ACCESS_KEY_ID,
            access_key_secret=settings.ALIBABA_CLOUD_ACCESS_KEY_SECRET
        )
        config.endpoint = f'dysmsapi.aliyuncs.com'
        return Dysmsapi20170525Client(config)

    @staticmethod
    def generate_code() -> str:
        """生成6位数字验证码"""
        return str(random.randint(100000, 999999))
    
    @staticmethod
    async def send_verification_code(phone: str) -> bool:
        """
        发送验证码
        1. 生成验证码并存储
        2. 调用阿里云 API 发送
        """
        try:
            code = SMSService.generate_code()
            
            # 存储验证码，有效期5分钟
            _verification_codes[phone] = {
                'code': code,
                'expires_at': datetime.utcnow() + timedelta(minutes=5),
                'attempts': 0
            }
            
            client = SMSService.create_client()
            if client:
                # 真实发送
                send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
                    phone_numbers=phone,
                    sign_name=settings.ALIBABA_CLOUD_SMS_SIGN_NAME,
                    template_code=settings.ALIBABA_CLOUD_SMS_TEMPLATE_CODE,
                    template_param=json.dumps({"code": code})
                )
                runtime = util_models.RuntimeOptions()
                response = await client.send_sms_with_options_async(send_sms_request, runtime)
                
                if response.body.code == 'OK':
                    logger.info(f"已发送短信验证码到 {phone}, 业务ID(BizId): {response.body.biz_id}")
                    return True, "OK"
                else:
                    # 记录详细错误信息供调试
                    logger.error(f"阿里云短信响应详情: {response.body.to_map()}")
                    msg = f"阿里云短信发送失败: {response.body.message}"
                    logger.error(msg)
                    return False, msg
            else:
                # 模拟发送 (记录日志即可)
                logger.info(f"📱 [Mock SMS] Code {code} sent to {phone}")
                return True, "OK (Mock)"
                
        except Exception as e:
            msg = f"发送验证码失败: {str(e)}"
            logger.error(msg)
            return False, msg
    
    @staticmethod
    def verify_code(phone: str, code: str) -> bool:
        """
        验证验证码
        """
        if phone not in _verification_codes:
            return False
        
        stored = _verification_codes[phone]
        
        # 检查是否过期
        if datetime.utcnow() > stored['expires_at']:
            del _verification_codes[phone]
            return False
        
        # 检查尝试次数（最多3次）
        if stored['attempts'] >= 3:
            del _verification_codes[phone]
            return False
        
        # 验证码错误
        if stored['code'] != code:
            stored['attempts'] += 1
            return False
        
        # 验证成功，删除验证码
        del _verification_codes[phone]
        return True
    
    @staticmethod
    def check_rate_limit(phone: str) -> bool:
        """
        检查频率限制（60秒内只能发送一次）
        """
        if phone in _verification_codes:
            stored = _verification_codes[phone]
            time_diff = datetime.utcnow() - (stored['expires_at'] - timedelta(minutes=5))
            if time_diff < timedelta(seconds=60):
                return False
        return True
