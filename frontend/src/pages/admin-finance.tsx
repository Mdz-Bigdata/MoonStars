import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { adminGetWithdrawals, adminAuditWithdrawal, getFinanceStats } from '../services/api'
import { getUserInfo } from '../services/auth'
import './admin-finance.css'

const AdminFinance: React.FC = () => {
    const navigate = useNavigate()
    const [withdrawals, setWithdrawals] = useState<any[]>([])
    const [stats, setStats] = useState<any>(null)
    const [loading, setLoading] = useState(true)
    const [remark, setRemark] = useState<Record<string, string>>({})

    const fetchData = useCallback(async () => {
        setLoading(true)
        try {
            const [wData, sData] = await Promise.all([
                adminGetWithdrawals(),
                getFinanceStats()
            ])
            setWithdrawals(wData)
            setStats(sData)
        } catch (error) {
            console.error('Failed to fetch withdrawals:', error)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        const user = getUserInfo()
        if (!user || user.role !== 'ADMIN') {
            alert('权限不足')
            navigate('/')
            return
        }
        fetchData()
    }, [navigate, fetchData])

    const handleAudit = async (id: string, approve: boolean) => {
        try {
            await adminAuditWithdrawal(id, approve, remark[id])
            alert(approve ? '已批准' : '已拒绝')
            fetchData()
        } catch (error: any) {
            alert('操作失败: ' + (error.response?.data?.detail || error.message))
        }
    }

    if (loading) return <div className="admin-finance-page">加载中...</div>

    return (
        <div className="admin-finance-page">
            <div className="admin-container">
                <header className="admin-header">
                    <Link to="/user-center" className="back-link">← 返回用户中心</Link>
                    <h1>财务审计控制台</h1>
                </header>

                <div className="admin-stats-grid">
                    <div className="stat-card">
                        <h3>累计总收入</h3>
                        <div className="stat-value">¥ {(stats?.total_income / 100 || 0).toFixed(2)}</div>
                    </div>
                    <div className="stat-card">
                        <h3>待处理提现</h3>
                        <div className="stat-value">¥ {(stats?.total_withdrawals_pending / 100 || 0).toFixed(2)}</div>
                    </div>
                    <div className="stat-card">
                        <h3>已发放奖励</h3>
                        <div className="stat-value">¥ {(stats?.total_withdrawals_completed / 100 || 0).toFixed(2)}</div>
                    </div>
                    <div className="stat-card">
                        <h3>注册访客</h3>
                        <div className="stat-value">{stats?.user_count_visitor || 0}</div>
                    </div>
                    <div className="stat-card">
                        <h3>正式会员</h3>
                        <div className="stat-value">{stats?.user_count_member || 0}</div>
                    </div>
                </div>

                <div className="withdrawal-audit-section">
                    <h2>待审核提取申请</h2>
                    {withdrawals.length === 0 ? (
                        <div className="empty-state">目前没有待处理事项</div>
                    ) : (
                        <div className="audit-table-wrapper">
                            <table className="audit-table">
                                <thead>
                                    <tr>
                                        <th>申请人</th>
                                        <th>金额</th>
                                        <th>提取方式</th>
                                        <th>账号信息</th>
                                        <th>申请时间</th>
                                        <th>备注</th>
                                        <th>操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {withdrawals.map((item) => (
                                        <tr key={item.id}>
                                            <td>{item.account_name}</td>
                                            <td className="amount-col">¥ {(item.amount / 100).toFixed(2)}</td>
                                            <td>{item.method === 'alipay' ? '支付宝' : item.method === 'wechat' ? '微信' : '银行卡'}</td>
                                            <td>{item.account_info}</td>
                                            <td>{new Date(item.created_at).toLocaleString()}</td>
                                            <td>
                                                <input
                                                    type="text"
                                                    className="remark-input"
                                                    placeholder="审核备注..."
                                                    value={remark[item.id] || ''}
                                                    onChange={(e) => setRemark({ ...remark, [item.id]: e.target.value })}
                                                />
                                            </td>
                                            <td className="actions-col">
                                                <button
                                                    className="btn btn-primary btn-sm"
                                                    onClick={() => handleAudit(item.id, true)}
                                                >
                                                    批准
                                                </button>
                                                <button
                                                    className="btn btn-danger btn-sm"
                                                    onClick={() => handleAudit(item.id, false)}
                                                >
                                                    拒绝
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

export default AdminFinance
