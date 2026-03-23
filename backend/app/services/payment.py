"""
支付服务
集成微信支付和支付宝支付
NOTE: 实际使用需要配置商户号和密钥
"""
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from app.core.config import settings
from app.repository.order import OrderRepository
from app.repository.column import ColumnRepository
from app.models.order import PaymentMethod, OrderStatus
from app.models.user import User, UserRole
from app.models.transaction import Transaction, TransactionType
from app.schemas.payment import OrderCreateRequest, OrderCreateResponse, PaymentQRCode

logger = logging.getLogger(__name__)


class PaymentService:
    """支付服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.order_repo = OrderRepository(db)
        self.column_repo = ColumnRepository(db)
    
    async def create_order(self, request: OrderCreateRequest, user_id: Optional[UUID] = None) -> Optional[OrderCreateResponse]:
        """
        创建订单并生成支付二维码
        """
        try:
            # 1. 获取专栏信息
            column = await self.column_repo.get_by_id(request.column_id)
            if not column:
                logger.error(f"专栏不存在: {request.column_id}")
                return None
            
            # 检查是否为免费专栏
            if column.is_free:
                logger.warning(f"尝试为免费专栏创建订单: {request.column_id}")
                return None
            
            # 2. 创建订单 (会员享有 8 折优惠)
            actual_amount = column.price
            if user_id:
                from sqlalchemy import select
                user_res = await self.db.execute(select(User).where(User.id == user_id))
                user = user_res.scalar_one_or_none()
                if user and user.role == UserRole.MEMBER:
                    actual_amount = int(column.price * 0.8)
                    logger.info(f"会员 {user.username} 享有 8 折优惠: {column.price} -> {actual_amount}")

            order = await self.order_repo.create(
                order_data=request,
                amount=actual_amount,
                user_id=user_id
            )
            
            # 3. 生成支付二维码
            qr_code_url = None
            payment_info = None
            
            if request.payment_method == PaymentMethod.WECHAT:
                qr_code_url = await self._create_wechat_payment(order.id, column.price)
            elif request.payment_method == PaymentMethod.ALIPAY:
                qr_code_url = await self._create_alipay_payment(order.id, column.price)
            
            # 更新订单的二维码
            if qr_code_url:
                order.qr_code_url = qr_code_url
                order.expires_at = datetime.utcnow() + timedelta(minutes=15)  # 15 分钟过期
                await self.db.flush()
                
                payment_info = PaymentQRCode(
                    qr_code_url=qr_code_url,
                    amount=column.price,
                    expires_in=900  # 15 分钟 = 900 秒
                )
            
            await self.db.commit()
            
            # 4. 构造响应
            response = OrderCreateResponse(
                id=order.id,
                column_id=order.column_id,
                amount=order.amount,
                payment_method=order.payment_method,
                status=order.status,
                qr_code_url=order.qr_code_url,
                created_at=order.created_at,
                paid_at=order.paid_at,
                payment_info=payment_info
            )
            
            return response
        
        except Exception as e:
            logger.error(f"创建订单失败: {str(e)}")
            await self.db.rollback()
            return None
    
    async def _create_wechat_payment(self, order_id: UUID, amount: int) -> Optional[str]:
        """
        创建微信支付二维码
        NOTE: 实际实现需要使用 wechatpy 库调用微信支付 API
        """
        # FIXME: 这里是模拟实现，实际需要配置微信商户号
        if not settings.WECHAT_APP_ID or not settings.WECHAT_MCH_ID:
            logger.warning("微信支付未配置，使用模拟二维码")
            return f"https://example.com/qrcode/wechat/{order_id}"
        
        try:
            # TODO: 实际实现
            # from wechatpy.pay import WeChatPay
            # wechat_pay = WeChatPay(...)
            # result = wechat_pay.order.create(...)
            # return result['code_url']
            
            logger.info(f"生成微信支付二维码: 订单 {order_id}, 金额 {amount}")
            return f"https://example.com/qrcode/wechat/{order_id}"
        
        except Exception as e:
            logger.error(f"创建微信支付失败: {str(e)}")
            return None
    
    async def _create_alipay_payment(self, order_id: UUID, amount: int) -> Optional[str]:
        """
        创建支付宝支付二维码
        NOTE: 实际实现需要使用 python-alipay-sdk 库
        """
        # FIXME: 这里是模拟实现，实际需要配置支付宝商户
        if not settings.ALIPAY_APP_ID:
            logger.warning("支付宝支付未配置，使用模拟二维码")
            return f"https://example.com/qrcode/alipay/{order_id}"
        
        try:
            # TODO: 实际实现
            # from alipay import AliPay
            # alipay = AliPay(...)
            # result = alipay.api_alipay_trade_precreate(...)
            # return result['qr_code']
            
            logger.info(f"生成支付宝支付二维码: 订单 {order_id}, 金额 {amount}")
            return f"https://example.com/qrcode/alipay/{order_id}"
        
        except Exception as e:
            logger.error(f"创建支付宝支付失败: {str(e)}")
            return None
    
    async def handle_payment_callback(
        self, 
        payment_method: PaymentMethod,
        transaction_id: str,
        order_id: str
    ) -> bool:
        """
        处理支付回调
        NOTE: 实际实现需要验证签名等安全措施
        """
        try:
            # TODO: 验证签名
            
            # 更新订单状态
            order_uuid = UUID(order_id)
            order = await self.order_repo.update_status(
                order_id=order_uuid,
                status=OrderStatus.PAID,
                transaction_id=transaction_id
            )
            
            if not order:
                return False
            
            # 1. 业务逻辑：升级用户角色和有效期
            user = None
            if order.user_id:
                from sqlalchemy import select
                user_result = await self.db.execute(select(User).where(User.id == order.user_id))
                user = user_result.scalar_one_or_none()
                
            if user:
                # 升级角色
                user.role = UserRole.MEMBER
                # 会员和管理员默认应为 PRIVATE 权限
                user.permission = "PRIVATE"
                
                # 更新有效期 (如果是续费，在原基础上累加，否则从现在开始)
                now = datetime.utcnow()
                if user.membership_expires_at and user.membership_expires_at > now:
                    user.membership_expires_at += timedelta(days=365)
                else:
                    user.membership_expires_at = now + timedelta(days=365)
                    
                    # 2. 邀请奖励逻辑 (邀请一个人成为会员可获得200积分)
                    if user.invited_by_id:
                        inviter_stmt = select(User).where(User.id == user.invited_by_id)
                        inviter_res = await self.db.execute(inviter_stmt)
                        inviter = inviter_res.scalar_one_or_none()
                        
                        if inviter:
                            reward_points = 200
                            inviter.points += reward_points
                            
                            # 记录积分变化
                            inviter_tx = Transaction(
                                user_id=inviter.id,
                                type=TransactionType.COMMISSION,
                                amount=0,
                                balance_after=inviter.balance,
                                detail=f"好友 {user.username} 成为会员，奖励 {reward_points} 积分"
                            )
                            self.db.add(inviter_tx)

            # 3. 增加专栏订阅数
            await self.column_repo.increment_subscriber_count(order.column_id)
            await self.db.commit()
            logger.info(f"订单支付成功: {order_id}, 用户 {order.user_id} 已升级为会员")
            return True
        
        except Exception as e:
            logger.error(f"处理支付回调失败: {str(e)}")
            await self.db.rollback()
            return False
    
    async def check_order_status(self, order_id: UUID) -> Optional[OrderStatus]:
        """查询订单状态"""
        order = await self.order_repo.get_by_id(order_id)
        return order.status if order else None
