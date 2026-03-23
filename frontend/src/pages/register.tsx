/**
 * 注册页面 - 统一注册流程 (用户名、密码、手机验证)
 */
import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { register, sendCode } from '../services/auth'
import './auth.css'

const Register: React.FC = () => {
    const navigate = useNavigate()
    const [form, setForm] = useState({
        username: '',
        email: '',
        password: '',
        confirm_password: '',
        phone: '',
        code: '',
        invitation_code: ''
    })
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)

    React.useEffect(() => {
        const params = new URLSearchParams(window.location.search)
        const code = params.get('invite') || params.get('code')
        if (code) {
            setForm(prev => ({ ...prev, invitation_code: code }))
        }
    }, [])
    const [loading, setLoading] = useState(false)
    const [sendingCode, setSendingCode] = useState(false)
    const [countdown, setCountdown] = useState(0)
    const [error, setError] = useState<string | null>(null)

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)

        if (form.password !== form.confirm_password) {
            setError('两次输入的密码不一致')
            return
        }

        if (form.password.length < 6) {
            setError('密码长度至少为 6 位')
            return
        }

        if (form.phone.length !== 11) {
            setError('请输入正确的 11 位手机号')
            return
        }

        if (form.code.length !== 6) {
            setError('请输入 6 位验证码')
            return
        }

        setLoading(true)

        try {
            await register({
                username: form.username,
                email: form.email || undefined,
                password: form.password,
                confirm_password: form.confirm_password,
                phone: form.phone,
                code: form.code,
                invitation_code: form.invitation_code
            })
            navigate('/')
        } catch (err: any) {
            setError(err.response?.data?.detail || '注册失败，请检查填写内容')
        } finally {
            setLoading(false)
        }
    }

    const handleSendCode = async () => {
        if (!form.phone || form.phone.length !== 11) {
            setError('请输入正确的手机号')
            return
        }

        setSendingCode(true)
        setError(null)

        try {
            await sendCode(form.phone)

            // 开始倒计时
            setCountdown(60)
            const timer = setInterval(() => {
                setCountdown(prev => {
                    if (prev <= 1) {
                        clearInterval(timer)
                        return 0
                    }
                    return prev - 1
                })
            }, 1000)
        } catch (err: any) {
            setError(err.response?.data?.detail || '发送验证码失败，请稍后再试')
        } finally {
            setSendingCode(false)
        }
    }

    const getPasswordStrength = () => {
        if (!form.password) return null
        if (form.password.length < 6) return { text: '弱', color: '#ef4444' }
        if (form.password.length < 10) return { text: '中', color: '#f59e0b' }
        return { text: '强', color: '#10b981' }
    }

    const passwordStrength = getPasswordStrength()

    return (
        <div className="auth-page">
            <div className="auth-container">
                <div className="auth-card">
                    <div className="auth-header">
                        <h1>创建账号</h1>
                        <p>加入大数据启示录，开启您的内容学习之旅</p>
                    </div>

                    {error && (
                        <div className="auth-error">
                            <span>⚠️</span>
                            <p>{error}</p>
                        </div>
                    )}

                    <form onSubmit={handleRegister} className="auth-form">
                        <div className="form-group">
                            <label htmlFor="username">用户名</label>
                            <input
                                type="text"
                                id="username"
                                className="input"
                                placeholder="3-50个字符"
                                value={form.username}
                                onChange={(e) => setForm({ ...form, username: e.target.value })}
                                required
                                minLength={3}
                                maxLength={50}
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="phone">手机号</label>
                            <input
                                type="tel"
                                id="phone"
                                className="input"
                                placeholder="请输入11位手机号"
                                value={form.phone}
                                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                                required
                                maxLength={11}
                                pattern="[0-9]{11}"
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="code">验证码</label>
                            <div className="input-with-button">
                                <input
                                    type="text"
                                    id="code"
                                    className="input"
                                    placeholder="请输入6位验证码"
                                    value={form.code}
                                    onChange={(e) => setForm({ ...form, code: e.target.value })}
                                    required
                                    maxLength={6}
                                    pattern="[0-9]{6}"
                                />
                                <button
                                    type="button"
                                    className="btn btn-secondary btn-sm code-button"
                                    onClick={handleSendCode}
                                    disabled={sendingCode || countdown > 0}
                                >
                                    {countdown > 0 ? `${countdown}s` : sendingCode ? '发送中...' : '发送验证码'}
                                </button>
                            </div>
                        </div>

                        <div className="form-group">
                            <label htmlFor="password">
                                密码
                                {passwordStrength && (
                                    <span
                                        className="password-strength"
                                        style={{ color: passwordStrength.color }}
                                    >
                                        {passwordStrength.text}
                                    </span>
                                )}
                            </label>
                            <div className="input-with-icon">
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    id="password"
                                    className="input"
                                    placeholder="至少 6 位字符"
                                    value={form.password}
                                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                                    required
                                    minLength={6}
                                    maxLength={50}
                                />
                                <button
                                    type="button"
                                    className="input-icon-btn"
                                    onClick={() => setShowPassword(!showPassword)}
                                >
                                    {showPassword ? '👁️' : '👁️‍🗨️'}
                                </button>
                            </div>
                        </div>

                        <div className="form-group">
                            <label htmlFor="confirm_password">确认密码</label>
                            <div className="input-with-icon">
                                <input
                                    type={showConfirmPassword ? 'text' : 'password'}
                                    id="confirm_password"
                                    className="input"
                                    placeholder="再次输入密码"
                                    value={form.confirm_password}
                                    onChange={(e) => setForm({ ...form, confirm_password: e.target.value })}
                                    required
                                    maxLength={50}
                                />
                                <button
                                    type="button"
                                    className="input-icon-btn"
                                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                >
                                    {showConfirmPassword ? '👁️' : '👁️‍🗨️'}
                                </button>
                            </div>
                        </div>

                        <div className="form-group">
                            <label htmlFor="invitation_code">邀请码 (可选)</label>
                            <input
                                type="text"
                                id="invitation_code"
                                className="input"
                                placeholder="填写邀请码可获得初始积分"
                                value={form.invitation_code}
                                onChange={(e) => setForm({ ...form, invitation_code: e.target.value })}
                            />
                        </div>

                        <button
                            type="submit"
                            className="btn btn-primary btn-lg w-full"
                            style={{ marginTop: '1rem' }}
                            disabled={loading}
                        >
                            {loading ? '极速注册中...' : '开启探索'}
                        </button>
                    </form>

                    <div className="auth-footer">
                        <p>
                            已有账号？
                            <Link to="/login" className="auth-link">立即登录</Link>
                        </p>
                    </div>
                </div>

                <Link to="/" className="auth-back">
                    ← 返回首页
                </Link>
            </div>
        </div>
    )
}

export default Register
