import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getMyOrders, getColumn } from '../services/api'
import type { Order as APIOrder } from '../types'
import './purchase-history.css'

interface DisplayOrder extends APIOrder {
    column_name?: string
}

const PurchaseHistory: React.FC = () => {
    const [orders, setOrders] = useState<DisplayOrder[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchOrders = async () => {
            try {
                const data = await getMyOrders()
                // 为每个订单获取专栏名称
                const ordersWithNames = await Promise.all(data.map(async (order) => {
                    try {
                        const column = await getColumn(order.column_id)
                        return { ...order, column_name: column.name }
                    } catch {
                        return { ...order, column_name: '未知专栏' }
                    }
                }))
                setOrders(ordersWithNames)
            } catch (err) {
                console.error('获取购买记录失败', err)
            } finally {
                setLoading(false)
            }
        }
        fetchOrders()
    }, [])

    const formatPrice = (amount: number) => (amount / 100).toFixed(2)

    return (
        <div className="purchase-history-page">
            <div className="purchase-history-container">
                <div className="purchase-history-card">
                    <div className="purchase-history-header">
                        <Link to="/profile" className="back-link">← 返回个人中心</Link>
                        <h1>购买记录</h1>
                    </div>

                    {loading ? (
                        <div className="loading-state">加载中...</div>
                    ) : orders.length > 0 ? (
                        <div className="purchase-table-container">
                            <table className="purchase-table">
                                <thead>
                                    <tr>
                                        <th>专栏名称</th>
                                        <th>金额</th>
                                        <th>状态</th>
                                        <th>下单时间</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {orders.map(order => (
                                        <tr key={order.id}>
                                            <td>{order.column_name}</td>
                                            <td>¥{formatPrice(order.amount)}</td>
                                            <td>
                                                <span className={`status-badge status-${order.status}`}>
                                                    {order.status === 'paid' ? '已支付' : order.status === 'pending' ? '待支付' : '失败'}
                                                </span>
                                            </td>
                                            <td>{new Date(order.created_at).toLocaleString()}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="empty-state">
                            <p>暂无购买记录</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

export default PurchaseHistory
