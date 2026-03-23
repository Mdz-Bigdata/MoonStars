"""
系统设置模型
用于存储全局配置，如提现费率、邀请奖励、站点维护状态等
"""
from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class SystemSettings(Base):
    """系统全局设置"""
    __tablename__ = "system_settings"
    
    # 设置键 (e.g., 'withdrawal_config', 'invitation_reward')
    key = Column(String(100), primary_key=True, index=True, comment="配置键")
    
    # 设置值 (JSON 格式支持复杂配置)
    value = Column(JSONB, nullable=False, comment="配置内容")
    
    description = Column(Text, comment="配置描述")

    @classmethod
    def get_default_config(cls, key: str) -> dict:
        """获取默认配置"""
        defaults = {
            "withdrawal_config": {
                "min_amount": 1000,      # 最低 10 元
                "fee_rate": 0.05,       # 5% 手续费
                "enabled": True
            },
            "invitation_config": {
                "reward_amount": 100,    # 邀请一人奖励 1 元 (单位：分)
                "commission_rate": 0.1,  # 10% 充值/购买返佣
                "enabled": True
            }
        }
        return defaults.get(key, {})
