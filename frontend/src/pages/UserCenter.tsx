import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { logout, getUserInfo, setUserInfo, type User, redeemPoints } from '../services/auth'
import { getBalance, getTransactions, submitWithdrawal, updateProfile } from '../services/api'
import './UserCenter.css'

const UserCenter: React.FC = () => {
    const navigate = useNavigate()
    const [user, setUser] = useState<User | null>(null)
    const [activeSection, setActiveSection] = useState<'overview' | 'membership' | 'wallet' | 'invitation' | 'binding' | 'content'>('overview')

    // Wallet & Points
    const [balance, setBalance] = useState<number>(0)
    const [points, setPoints] = useState<number>(0)
    const [invitationCode, setInvitationCode] = useState<string>('')
    const [transactions, setTransactions] = useState<any[]>([])
    const [loading, setLoading] = useState(false)

    // Forms
    const [withdrawForm, setWithdrawForm] = useState({
        amount: '',
        method: 'alipay',
        account_info: '',
        account_name: '',
        bank_name: ''
    })

    const [bindForm, setBindForm] = useState({
        bank_card: '',
        wechat: '',
        alipay_account: '',
        alipay_name: ''
    })

    const fetchFinanceData = useCallback(async () => {
        setLoading(true)
        try {
            const [balanceRes, transRes] = await Promise.all([
                getBalance(),
                getTransactions({ page: 1, size: 50 })
            ])
            setBalance(balanceRes.balance)
            setPoints(balanceRes.points || 0)
            setInvitationCode(balanceRes.invitation_code || '')
            setTransactions(transRes.items)

            // Sync with local user info
            const localUser = getUserInfo()
            if (localUser) {
                const updated = { ...localUser, balance: balanceRes.balance, points: balanceRes.points || 0 }
                setUser(updated)
                setUserInfo(updated)
            }
        } catch (error) {
            console.error('Failed to fetch finance data:', error)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        const info = getUserInfo()
        if (!info) {
            navigate('/login')
            return
        }
        setUser(info)
        setBindForm({
            bank_card: (info as any).bank_card_info?.card_number || '',
            wechat: (info as any).wechat_info?.openid || '',
            alipay_account: (info as any).alipay_info?.account || '',
            alipay_name: (info as any).alipay_info?.name || ''
        })
        fetchFinanceData()
    }, [navigate, fetchFinanceData])

    const handleRedeem = async (amount: number) => {
        try {
            const res = await redeemPoints({ amount })
            alert(`成功兑换 ${res.balance_added / 100} 元余额！`)
            fetchFinanceData()
        } catch (error: any) {
            alert(error.response?.data?.detail || '兑换失败')
        }
    }

    const handleWithdraw = async (e: React.FormEvent) => {
        e.preventDefault()
        const amountFen = Math.floor(parseFloat(withdrawForm.amount) * 100)
        if (amountFen < 5000) { // 最小 50 元
            alert('起提金额为 50 元')
            return
        }
        if (amountFen > balance) {
            alert('余额不足')
            return
        }

        try {
            await submitWithdrawal({ ...withdrawForm, amount: amountFen })
            alert('申请已提交，请等待管理员审核')
            setWithdrawForm({ amount: '', method: 'alipay', account_info: '', account_name: '', bank_name: '' })
            fetchFinanceData()
        } catch (error: any) {
            alert(error.response?.data?.detail || '提现申请失败')
        }
    }

    const handleBind = async (e: React.FormEvent) => {
        e.preventDefault()
        try {
            const updated = await updateProfile({
                bank_card_info: { card_number: bindForm.bank_card },
                wechat_info: { id: bindForm.wechat },
                alipay_info: { account: bindForm.alipay_account, name: bindForm.alipay_name }
            }) as any
            alert('绑定成功')
            setUser(updated)
            setUserInfo(updated)
        } catch (error) {
            alert('同步失败')
        }
    }

    if (!user) return null

    if (loading && !user.id) {
        return <div className="uc-loading">枢纽数据同步中...</div>
    }

    const registrationDays = Math.ceil((new Date().getTime() - new Date(user.created_at).getTime()) / (1000 * 60 * 60 * 24))

    return (
        <div className="uc-page">
            <Link to="/" className="back-home-link">← 返回首页</Link>
            <div className="uc-sidebar">
                <div className="uc-user-brief">
                    <div className="uc-avatar">{user.username.charAt(0).toUpperCase()}</div>
                    <div className="uc-user-meta">
                        <h4>{user.username}</h4>
                        <span className={`uc-role-badge ${user.role.toLowerCase()}`}>
                            {user.role === 'ADMIN' ? '管理员' : user.role === 'MEMBER' ? '正式会员' : '访客'}
                        </span>
                    </div>
                </div>

                <nav className="uc-nav">
                    <button className={activeSection === 'overview' ? 'active' : ''} onClick={() => setActiveSection('overview')}>枢纽概览</button>
                    <button className={activeSection === 'membership' ? 'active' : ''} onClick={() => setActiveSection('membership')}>会员权益</button>
                    <button className={activeSection === 'wallet' ? 'active' : ''} onClick={() => setActiveSection('wallet')}>我的钱包</button>
                    <button className={activeSection === 'invitation' ? 'active' : ''} onClick={() => setActiveSection('invitation')}>邀请返佣</button>
                    <button className={activeSection === 'content' ? 'active' : ''} onClick={() => setActiveSection('content')}>内容管理</button>
                    <button className={activeSection === 'binding' ? 'active' : ''} onClick={() => setActiveSection('binding')}>账号绑定</button>
                </nav>

                <div className="uc-sidebar-footer">
                    {user.role === 'ADMIN' && (
                        <Link to="/admin/finance" className="uc-admin-link">📊 财务审计</Link>
                    )}
                    <button className="uc-logout-btn" onClick={() => { logout(); navigate('/login'); }}>退出登录</button>
                </div>
            </div>

            <main className="uc-content">
                {activeSection === 'overview' && (
                    <div className="uc-section">
                        <h2 className="section-title">枢纽概览</h2>
                        <div className="uc-grid">
                            <div className="uc-stat-card">
                                <span>注册天数</span>
                                <strong>{registrationDays} 天</strong>
                            </div>
                            <div className="uc-stat-card">
                                <span>当前余额</span>
                                <strong>¥ {(balance / 100).toFixed(2)}</strong>
                            </div>
                            <div className="uc-stat-card">
                                <span>成长积分</span>
                                <strong>{points} Exp</strong>
                            </div>
                        </div>

                        <div className="uc-info-block mt-8">
                            <h3>身份令牌</h3>
                            <div className="token-display">
                                <div className="token-item">
                                    <label>唯一识别码 (UID)</label>
                                    <code>{user.id}</code>
                                </div>
                                <div className="token-item">
                                    <label>账户许可</label>
                                    <code>{user.permission}</code>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {activeSection === 'membership' && (
                    <div className="uc-section">
                        <h2 className="section-title">会员权益</h2>
                        <div className="membership-banner">
                            {user.role === 'MEMBER' || user.role === 'ADMIN' ? (
                                <div className="membership-status active">
                                    <div className="status-top">
                                        <span className="premium-label">PREMIUM</span>
                                        <h3>尊贵会员服务</h3>
                                    </div>
                                    <p>到期时间: {user.membership_expires_at ? new Date(user.membership_expires_at).toLocaleDateString() : '永久'}</p>
                                    <div className="renewal-notice">
                                        <span>💡 会员续费可享 8 折优惠</span>
                                        <Link to="/technical-columns" className="uc-btn-link">立即续费</Link>
                                    </div>
                                </div>
                            ) : (
                                <div className="membership-status inactive">
                                    <h3>尚未开通会员</h3>
                                    <p>购买任意技术专栏即可自动升级为正式会员，解锁全站内容</p>
                                    <Link to="/technical-columns" className="btn btn-primary mt-4">查看技术专栏</Link>
                                </div>
                            )}
                        </div>

                        <div className="benefits-list mt-8">
                            <h3>会员专属特权</h3>
                            <div className="benefit-item">✅ 全站专栏文章免费阅读 (包含所有付费专栏)</div>
                            <div className="benefit-item">✅ 无限制使用 AI 转换、PPT 还原等高级工具</div>
                            <div className="benefit-item">✅ 专属问答评论权限与作者互动</div>
                            <div className="benefit-item">✅ 续费永久享受 8 折特惠</div>
                        </div>
                    </div>
                )}

                {activeSection === 'wallet' && (
                    <div className="uc-section">
                        <h2 className="section-title">我的钱包</h2>
                        <div className="wallet-overview">
                            <div className="balance-display">
                                <span>钱包余额 (RMB)</span>
                                <h1>¥ {(balance / 100).toFixed(2)}</h1>
                            </div>
                            <div className="points-display">
                                <span>可用积分</span>
                                <h2>{points}</h2>
                            </div>
                        </div>

                        <div className="redeem-milestones mt-8">
                            <h3>积分里程碑兑换</h3>
                            <div className="milestone-grid">
                                <div className="milestone-card">
                                    <h4>入门奖励</h4>
                                    <p>1000 积分 → 50 元</p>
                                    <button disabled={points < 1000} onClick={() => handleRedeem(1000)}>立即兑换</button>
                                </div>
                                <div className="milestone-card active">
                                    <h4>精英奖励</h4>
                                    <p>2000 积分 → 150 元</p>
                                    <button disabled={points < 2000} onClick={() => handleRedeem(2000)}>立即兑换</button>
                                </div>
                                <div className="milestone-card">
                                    <h4>荣耀奖励</h4>
                                    <p>5000 积分 → 500 元</p>
                                    <button disabled={points < 5000} onClick={() => handleRedeem(5000)}>立即兑换</button>
                                </div>
                            </div>
                        </div>

                        <div className="withdrawal-box mt-8">
                            <h3>资金提现</h3>
                            <form onSubmit={handleWithdraw} className="uc-form">
                                <div className="form-row">
                                    <input type="number" step="0.01" placeholder="提现金额 (元)" value={withdrawForm.amount} onChange={e => setWithdrawForm({ ...withdrawForm, amount: e.target.value })} />
                                    <select value={withdrawForm.method} onChange={e => setWithdrawForm({ ...withdrawForm, method: e.target.value })}>
                                        <option value="alipay">支付宝</option>
                                        <option value="wechat">微信</option>
                                        <option value="bank">银行卡</option>
                                    </select>
                                </div>
                                {withdrawForm.method === 'bank' && (
                                    <>
                                        <input type="text" placeholder="银行卡号" value={withdrawForm.account_info} onChange={e => setWithdrawForm({ ...withdrawForm, account_info: e.target.value })} />
                                        <input type="text" placeholder="开户银行" value={withdrawForm.bank_name || ''} onChange={e => setWithdrawForm({ ...withdrawForm, bank_name: e.target.value })} />
                                        <input type="text" placeholder="收款人真实姓名" value={withdrawForm.account_name} onChange={e => setWithdrawForm({ ...withdrawForm, account_name: e.target.value })} />
                                    </>
                                )}
                                {(withdrawForm.method === 'alipay' || withdrawForm.method === 'wechat') && (
                                    <>
                                        <input type="text" placeholder="收款账号" value={withdrawForm.account_info} onChange={e => setWithdrawForm({ ...withdrawForm, account_info: e.target.value })} />
                                        <input type="text" placeholder="收款人真实姓名" value={withdrawForm.account_name} onChange={e => setWithdrawForm({ ...withdrawForm, account_name: e.target.value })} />
                                    </>
                                )}
                                <button type="submit" className="btn btn-primary w-full">申请提现</button>
                            </form>
                        </div>
                    </div>
                )}

                {activeSection === 'invitation' && (
                    <div className="uc-section">
                        <h2 className="section-title">邀请奖励</h2>
                        <div className="invitation-hero">
                            <div className="invite-box">
                                <h3>您的专属邀请码</h3>
                                <div className="code-badge">{invitationCode || '---'}</div>
                                <button onClick={async () => {
                                    let code = invitationCode;
                                    if (!code || code === '---') {
                                        // 随机生成 8 位邀请码
                                        code = Math.random().toString(36).substring(2, 10).toUpperCase();
                                        try {
                                            await updateProfile({ invitation_code: code });
                                            setInvitationCode(code);
                                            // 同时同步本地存储的用户信息
                                            const info = getUserInfo();
                                            if (info) {
                                                const updated = { ...info, invitation_code: code };
                                                setUserInfo(updated);
                                                setUser(updated);
                                            }
                                        } catch (err) {
                                            console.error('Failed to generate invitation code:', err);
                                        }
                                    }
                                    const shareLink = `${window.location.origin}/register?code=${code}`;
                                    navigator.clipboard.writeText(shareLink);
                                    alert('邀请链接已复制到剪贴板：' + shareLink);
                                }}>复制分享链接</button>
                            </div>
                            <div className="reward-rules">
                                <ul>
                                    <li>🎁 成功邀请一位访客注册: <strong>+20 积分</strong></li>
                                    <li>💎 成功邀请一位好友开通会员: <strong>+200 积分</strong></li>
                                    <li>🔗 分享专栏链接，每带来一位新用户均有奖励</li>
                                </ul>
                            </div>
                        </div>

                        <div className="transaction-history mt-8">
                            <h3>奖励记录</h3>
                            <div className="uc-table-container">
                                <table className="uc-table">
                                    <thead>
                                        <tr>
                                            <th>事件</th>
                                            <th>金额/积分</th>
                                            <th>时间</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {transactions.map((tx, i) => (
                                            <tr key={i}>
                                                <td>{tx.detail}</td>
                                                <td className={tx.amount >= 0 ? 'text-success' : 'text-danger'}>
                                                    {tx.amount > 0 ? '+' : ''}{(tx.amount / 100).toFixed(2)}
                                                </td>
                                                <td>{new Date(tx.created_at).toLocaleDateString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}

                {activeSection === 'binding' && (
                    <div className="uc-section">
                        <h2 className="section-title">账号绑定</h2>
                        <form onSubmit={handleBind} className="uc-form max-w-md">
                            <div className="form-group-uc">
                                <label>银行卡号 (用于提现)</label>
                                <input type="text" value={bindForm.bank_card} onChange={e => setBindForm({ ...bindForm, bank_card: e.target.value })} placeholder="输入受支持的储蓄卡号" />
                            </div>
                            <div className="form-group-uc">
                                <label>微信已绑定 ID</label>
                                <input type="text" value={bindForm.wechat} onChange={e => setBindForm({ ...bindForm, wechat: e.target.value })} placeholder="微信 OpenID 或绑定的微信号" />
                            </div>
                            <div className="form-group-uc">
                                <label>支付宝账号</label>
                                <input type="text" value={bindForm.alipay_account} onChange={e => setBindForm({ ...bindForm, alipay_account: e.target.value })} placeholder="输入支付宝账号（手机号或邮箱）" />
                            </div>
                            <div className="form-group-uc">
                                <label>支付宝实名</label>
                                <input type="text" value={bindForm.alipay_name} onChange={e => setBindForm({ ...bindForm, alipay_name: e.target.value })} placeholder="支付宝认证姓名" />
                            </div>
                            <button type="submit" className="btn btn-primary">更新绑定信息</button>
                        </form>
                    </div>
                )}

                {activeSection === 'content' && (
                    <div className="uc-section">
                        <h2 className="section-title">内容管理</h2>
                        <div className="uc-content-tabs">
                            <div className="uc-content-empty">
                                <p>管理您的文章资产与专属专栏</p>
                                <div className="uc-action-btns mt-4">
                                    <Link to="/creator-center" className="btn btn-primary">进入创作者中心</Link>
                                    <Link to="/technical-columns" className="btn btn-secondary ml-4">订阅更多内容</Link>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    )
}

export default UserCenter
