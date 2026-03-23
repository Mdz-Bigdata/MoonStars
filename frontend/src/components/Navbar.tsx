/**
 * 导航栏组件
 * 包含 Logo、用户头像和下拉菜单
 */
import React, { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { isAuthenticated, getUserInfo, logout } from '../services/auth'
import './Navbar.css'

const Navbar: React.FC = () => {
    const [isMenuOpen, setIsMenuOpen] = useState(false)
    const menuRef = useRef<HTMLDivElement>(null)
    const navigate = useNavigate()
    const user = getUserInfo()

    const handleLogout = () => {
        logout()
        navigate('/login')
        setIsMenuOpen(false)
    }

    // 点击外部关闭菜单
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    return (
        <nav className="navbar">
            <div className="container">
                <div className="navbar__content">
                    <Link to="/" className="navbar__logo" onClick={() => setIsMenuOpen(false)}>
                        📚 大数据启示录
                    </Link>

                    <div className="navbar__actions">
                        {isAuthenticated() ? (
                            <div className="user-dropdown" ref={menuRef}>
                                <div
                                    className="navbar-user-avatar"
                                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                                >
                                    <div className="navbar-avatar-circle">
                                        {user?.username?.charAt(0).toUpperCase()}
                                    </div>
                                    <span className="navbar-username-text">{user?.username}</span>
                                    <span className={`arrow ${isMenuOpen ? 'up' : 'down'}`}>▾</span>
                                </div>

                                {isMenuOpen && (
                                    <div className="dropdown-menu">
                                        <div className="menu-header">
                                            <p className="menu-name">{user?.username}</p>
                                            <p className="menu-email">{user?.email || user?.phone}</p>
                                        </div>
                                        <div className="menu-divider"></div>
                                        <Link to="/user-center" className="menu-item" onClick={() => setIsMenuOpen(false)}>
                                            <span className="menu-icon">👤</span> 用户中心
                                        </Link>
                                        <Link to="/technical-columns" className="menu-item" onClick={() => setIsMenuOpen(false)}>
                                            <span className="menu-icon">📚</span> 技术专栏
                                        </Link>
                                        <Link to="/creator-center" className="menu-item" onClick={() => setIsMenuOpen(false)}>
                                            <span className="menu-icon">🎨</span> 创作者中心
                                        </Link>
                                        <Link to="/url-to-ppt" className="menu-item" onClick={() => setIsMenuOpen(false)}>
                                            <span className="menu-icon">📊</span> 网页变 PPT
                                        </Link>
                                        <Link to="/membership-center" className="menu-item" onClick={() => setIsMenuOpen(false)}>
                                            <span className="menu-icon">💎</span> 会员中心
                                        </Link>
                                        <Link to="/settings" className="menu-item" onClick={() => setIsMenuOpen(false)}>
                                            <span className="menu-icon">⚙️</span> 系统设置
                                        </Link>
                                        <div className="menu-divider"></div>
                                        <button className="menu-item logout-btn" onClick={handleLogout}>
                                            <span className="menu-icon">🚪</span> 退出登录
                                        </button>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="auth-btns">
                                <Link to="/login" className="btn btn-ghost btn-sm">登录</Link>
                                <Link to="/register" className="btn btn-primary btn-sm">注册</Link>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </nav>
    )
}

export default Navbar
