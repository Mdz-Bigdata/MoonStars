/**
 * 登录页面 - 支持账号、邮箱和手机验证码登录
 */
import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { login, sendCode, phoneLogin } from '../services/auth'
import './auth.css'

type LoginMethod = 'account' | 'email' | 'phone'

const Login: React.FC = () => {
    const navigate = useNavigate()
    const [method, setMethod] = useState<LoginMethod>('account')
    const [accountForm, setAccountForm] = useState({
        username: 'admin',
        password: 'admin123'
    })
    const [showPassword, setShowPassword] = useState(false)
    const [emailForm, setEmailForm] = useState({
        email: '',
        password: ''
    })
    const [phoneForm, setPhoneForm] = useState({
        phone: '',
        code: ''
    })
    const [loading, setLoading] = useState(false)
    const [sendingCode, setSendingCode] = useState(false)
    const [countdown, setCountdown] = useState(0)
    const [error, setError] = useState<string | null>(null)

    const handleAccountLogin = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        setLoading(true)

        try {
            // NOTE: 账号登录，使用用户名作为邮箱字段
            await login({ email: accountForm.username, password: accountForm.password })
            navigate('/')
        } catch (err: any) {
            setError(err.response?.data?.detail || '登录失败，请检查账号和密码')
        } finally {
            setLoading(false)
        }
    }

    const handleEmailLogin = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        setLoading(true)

        try {
            await login(emailForm)
            navigate('/')
        } catch (err: any) {
            setError(err.response?.data?.detail || '登录失败，请检查邮箱和密码')
        } finally {
            setLoading(false)
        }
    }

    const handlePhoneLogin = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        setLoading(true)

        try {
            await phoneLogin(phoneForm)
            navigate('/')
        } catch (err: any) {
            setError(err.response?.data?.detail || '登录失败，请检查手机号和验证码')
        } finally {
            setLoading(false)
        }
    }

    const handleSendCode = async () => {
        if (!phoneForm.phone || phoneForm.phone.length !== 11) {
            setError('请输入正确的手机号')
            return
        }

        setSendingCode(true)
        setError(null)

        try {
            await sendCode(phoneForm.phone)

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

    return (
        <div className="auth-page">
            <div className="auth-container">
                <div className="auth-card">
                    <div className="auth-header">
                        <h1>欢迎回来</h1>
                        <p>登录您的账号</p>
                    </div>

                    {/* 登录方式选择 */}
                    <div className="auth-tabs">
                        <button
                            className={`auth-tab ${method === 'account' ? 'auth-tab--active' : ''}`}
                            onClick={() => setMethod('account')}
                        >
                            账号登录
                        </button>
                        <button
                            className={`auth-tab ${method === 'email' ? 'auth-tab--active' : ''}`}
                            onClick={() => setMethod('email')}
                        >
                            邮箱登录
                        </button>
                        <button
                            className={`auth-tab ${method === 'phone' ? 'auth-tab--active' : ''}`}
                            onClick={() => setMethod('phone')}
                        >
                            手机登录
                        </button>
                    </div>

                    {error && (
                        <div className="auth-error">
                            <span>⚠️</span>
                            <p>{error}</p>
                        </div>
                    )}

                    {/* 账号登录表单 */}
                    {method === 'account' && (
                        <form onSubmit={handleAccountLogin} className="auth-form">
                            <div className="form-group">
                                <label htmlFor="username">账号</label>
                                <input
                                    type="text"
                                    id="username"
                                    className="input"
                                    placeholder="请输入账号"
                                    value={accountForm.username}
                                    onChange={(e) => setAccountForm({ ...accountForm, username: e.target.value })}
                                    required
                                />
                            </div>

                            <div className="form-group">
                                <label htmlFor="account-password">密码</label>
                                <div className="input-with-icon">
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        id="account-password"
                                        className="input"
                                        placeholder="••••••••"
                                        value={accountForm.password}
                                        onChange={(e) => setAccountForm({ ...accountForm, password: e.target.value })}
                                        required
                                        minLength={6}
                                        maxLength={50}
                                    />
                                    <button
                                        type="button"
                                        className="input-icon-btn"
                                        onClick={() => setShowPassword(!showPassword)}
                                        tabIndex={-1}
                                    >
                                        {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                                    </button>
                                </div>
                            </div>

                            <button
                                type="submit"
                                className="btn btn-primary btn-lg w-full"
                                disabled={loading}
                            >
                                {loading ? '登录中...' : '登录'}
                            </button>
                        </form>
                    )}

                    {/* 邮箱登录表单 */}
                    {method === 'email' && (
                        <form onSubmit={handleEmailLogin} className="auth-form">
                            <div className="form-group">
                                <label htmlFor="email">邮箱地址</label>
                                <input
                                    type="email"
                                    id="email"
                                    className="input"
                                    placeholder="your@email.com"
                                    value={emailForm.email}
                                    onChange={(e) => setEmailForm({ ...emailForm, email: e.target.value })}
                                    required
                                />
                            </div>

                            <div className="form-group">
                                <label htmlFor="password">密码</label>
                                <input
                                    type="password"
                                    id="password"
                                    className="input"
                                    placeholder="••••••••"
                                    value={emailForm.password}
                                    onChange={(e) => setEmailForm({ ...emailForm, password: e.target.value })}
                                    required
                                    minLength={6}
                                    maxLength={50}
                                />
                            </div>

                            <button
                                type="submit"
                                className="btn btn-primary btn-lg w-full"
                                disabled={loading}
                            >
                                {loading ? '登录中...' : '登录'}
                            </button>
                        </form>
                    )}

                    {/* 手机验证码登录表单 */}
                    {method === 'phone' && (
                        <form onSubmit={handlePhoneLogin} className="auth-form">
                            <div className="form-group">
                                <label htmlFor="phone">手机号</label>
                                <input
                                    type="tel"
                                    id="phone"
                                    className="input"
                                    placeholder="请输入11位手机号"
                                    value={phoneForm.phone}
                                    onChange={(e) => setPhoneForm({ ...phoneForm, phone: e.target.value })}
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
                                        value={phoneForm.code}
                                        onChange={(e) => setPhoneForm({ ...phoneForm, code: e.target.value })}
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
                                        {countdown > 0 ? `${countdown}秒` : sendingCode ? '发送中...' : '获取验证码'}
                                    </button>
                                </div>
                            </div>

                            <button
                                type="submit"
                                className="btn btn-primary btn-lg w-full"
                                disabled={loading}
                            >
                                {loading ? '登录中...' : '登录'}
                            </button>
                        </form>
                    )}

                    <div className="auth-footer">
                        <p>
                            还没有账号？
                            <Link to="/register" className="auth-link">立即注册</Link>
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

export default Login
