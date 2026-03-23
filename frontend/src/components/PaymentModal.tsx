import React, { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import type { Column } from '../types';
import { createOrder, confirmPayment } from '../services/api';
import './PaymentModal.css';

interface PaymentModalProps {
    column: Column;
    onClose: () => void;
    onSuccess: () => void;
}

/**
 * 支付弹窗组件
 * 支持模拟微信和支付宝支付流程
 */
const PaymentModal: React.FC<PaymentModalProps> = ({ column, onClose, onSuccess }) => {
    const [paymentMethod, setPaymentMethod] = useState<'wechat' | 'alipay'>('wechat');
    const [step, setStep] = useState<'selection' | 'qrcode' | 'confirming'>('selection');
    const [orderId, setOrderId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [qrCodeUrl, setQrCodeUrl] = useState<string>('');

    /**
     * 处理支付点击：创建订单并显示二维码
     */
    const handlePayClick = async () => {
        setLoading(true);
        try {
            const res = await createOrder({
                column_id: column.id,
                payment_method: paymentMethod
            });
            setOrderId(res.id);
            // 这里使用后端返回的预览链接或者模拟一个
            setQrCodeUrl(res.payment_info?.qr_code_url || `https://example.com/pay/${res.id}`);
            setStep('qrcode');
        } catch (error) {
            console.error('创建订单失败:', error);
            alert('创建订单失败，请稍后重试');
        } finally {
            setLoading(false);
        }
    };

    /**
     * 模拟支付成功确认
     */
    const handleConfirmPayment = async () => {
        if (!orderId) return;
        setLoading(true);
        try {
            setStep('confirming');
            const res = await confirmPayment(orderId);
            if (res.success) {
                // 模拟支付成功后的延迟效果
                setTimeout(() => {
                    onSuccess();
                }, 1500);
            } else {
                alert(res.message || '支付确认失败');
                setStep('qrcode');
            }
        } catch (error) {
            console.error('确认支付失败:', error);
            alert('确认支付失败，请重试');
            setStep('qrcode');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="payment-modal-overlay" onClick={onClose}>
            <div className="payment-modal-container" onClick={(e) => e.stopPropagation()}>
                <button className="close-btn" onClick={onClose}>&times;</button>

                <div className="payment-modal-header">
                    <h2>解锁专栏内容</h2>
                    <p>购买《{column.name}》即可永久解锁全部文章</p>
                </div>

                <div className="payment-info-card">
                    <div className="column-preview">
                        {column.cover_image && <img src={column.cover_image} alt={column.name} />}
                        <div className="column-details">
                            <h3>{column.name}</h3>
                            <p>{column.description?.slice(0, 50)}...</p>
                        </div>
                    </div>
                    <div className="price-tag">
                        <span className="currency">¥</span>
                        <span className="amount">{(column.price / 100).toFixed(2)}</span>
                    </div>
                </div>

                {step === 'selection' && (
                    <div className="payment-selection">
                        <p className="section-title">选择支付方式</p>
                        <div className="method-grid">
                            <div
                                className={`method-item ${paymentMethod === 'wechat' ? 'active' : ''}`}
                                data-method="wechat"
                                onClick={() => setPaymentMethod('wechat')}
                            >
                                <div className="method-icon wechat-icon">微信</div>
                                <span>微信支付</span>
                            </div>
                            <div
                                className={`method-item ${paymentMethod === 'alipay' ? 'active' : ''}`}
                                data-method="alipay"
                                onClick={() => setPaymentMethod('alipay')}
                            >
                                <div className="method-icon alipay-icon">支</div>
                                <span>支付宝</span>
                            </div>
                        </div>
                        <button
                            className="pay-submit-btn"
                            disabled={loading}
                            onClick={handlePayClick}
                        >
                            {loading ? '处理中...' : `立即支付 ¥${(column.price / 100).toFixed(2)}`}
                        </button>
                    </div>
                )}

                {step === 'qrcode' && (
                    <div className={`payment-qrcode-section ${paymentMethod}`}>
                        <p className="section-title">请使用{paymentMethod === 'wechat' ? '微信' : '支付宝'}扫码支付</p>
                        <div className="qrcode-wrapper">
                            <QRCodeSVG value={qrCodeUrl} size={180} />
                            {loading && <div className="qrcode-loading-overlay">验证中...</div>}
                        </div>
                        <div className="payment-status-tip">
                            <p>支付成功后点击下方按钮</p>
                        </div>
                        <div className="action-buttons">
                            <button
                                className={`confirm-btn ${paymentMethod}`}
                                disabled={loading}
                                onClick={handleConfirmPayment}
                            >
                                {loading ? '正在验证...' : '我已完成支付'}
                            </button>
                            <button className="back-btn" onClick={() => setStep('selection')}>
                                返回修改
                            </button>
                        </div>
                    </div>
                )}

                {step === 'confirming' && (
                    <div className="payment-success-anim">
                        <div className="success-icon">✓</div>
                        <h3>支付成功</h3>
                        <p>正在为您解锁内容，请稍候...</p>
                    </div>
                )}

                <div className="payment-footer">
                    <p>安全支付保障 | 虚拟物品不支持退款</p>
                </div>
            </div>
        </div>
    );
};

export default PaymentModal;
