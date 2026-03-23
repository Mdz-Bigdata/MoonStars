/**
 * 创作者中心
 * 包含：我的作品、专栏管理、插件市场、您的创作
 */
import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getMyArticles, deleteMyArticle } from '../services/api'
import type { Article } from '../types'
import './creator-center.css'

const CreatorCenter: React.FC = () => {
    const navigate = useNavigate()
    const [articles, setArticles] = useState<Article[]>([])
    const [loading, setLoading] = useState(true)
    const [plugins, setPlugins] = useState([
        { id: 'mindmap', name: '思维导图', desc: '将文章一键转为思维导图', installed: false },
        { id: 'evernote', name: '印象笔记', desc: '同步内容到印象笔记', installed: false }
    ])

    // 从 localStorage 加载插件状态
    useEffect(() => {
        const savedPlugins = localStorage.getItem('installed_plugins')
        if (savedPlugins) {
            try {
                const installedIds = JSON.parse(savedPlugins)
                setPlugins(prev => prev.map(p => ({
                    ...p,
                    installed: installedIds.includes(p.id)
                })))
            } catch (e) {
                console.error('Failed to parse installed plugins', e)
            }
        }
    }, [])

    // 创作 Tab 切换状态
    const [creationTab, setCreationTab] = useState<'published' | 'draft'>('published')
    const [creationArticles, setCreationArticles] = useState<Article[]>([])
    const [creationLoading, setCreationLoading] = useState(false)

    const handleInstall = (id: string) => {
        setPlugins(prevPlugins => {
            const newPlugins = prevPlugins.map(p => p.id === id ? { ...p, installed: true } : p)
            const installedIds = newPlugins.filter(p => p.installed).map(p => p.id)
            localStorage.setItem('installed_plugins', JSON.stringify(installedIds))
            return newPlugins
        })
        alert('插件安装成功，可前往配置页查看')
    }

    useEffect(() => {
        const fetchArticles = async () => {
            try {
                const response = await getMyArticles({ page: 1, size: 20 })
                setArticles(response.items)
            } catch (error) {
                console.error('获取文章失败:', error)
            } finally {
                setLoading(false)
            }
        }
        fetchArticles()
    }, [])

    /**
     * 加载创作列表（按 Tab 筛选）
     */
    useEffect(() => {
        const loadCreationArticles = async () => {
            setCreationLoading(true)
            try {
                const statusFilter = creationTab === 'draft' ? 'DRAFT' : 'PUBLISHED'
                const response = await getMyArticles({ page: 1, size: 5, status: statusFilter })
                setCreationArticles(response.items)
            } catch (error) {
                console.error('获取创作列表失败:', error)
            } finally {
                setCreationLoading(false)
            }
        }
        loadCreationArticles()
    }, [creationTab])

    /**
     * 删除文章（仅草稿）
     */
    const handleDeleteArticle = async (articleId: string) => {
        if (!confirm('确定要删除这篇草稿吗？')) return
        try {
            await deleteMyArticle(articleId)
            setCreationArticles(prev => prev.filter(a => a.id !== articleId))
        } catch (err: any) {
            alert(err.response?.data?.detail || '删除失败')
        }
    }

    /**
     * 格式化日期
     */
    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr)
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
    }

    return (
        <div className="creator-center-page">
            <div className="creator-header">
                <Link to="/profile" className="back-link">← 返回个人中心</Link>
                <h1>创作者中心</h1>
                <p>激发灵感，自由创作，管理您的数字资产</p>
            </div>

            <div className="creator-grid">
                {/* 我的作品模块 */}
                <div className="creator-card">
                    <div className="card-icon">📚</div>
                    <h3 className="card-title">我的作品</h3>
                    <p className="card-desc">管理您已转换的所有文章</p>
                    <div className="article-list-mini">
                        {loading ? (
                            <p>加载中...</p>
                        ) : articles.length === 0 ? (
                            <p className="empty-text">暂无作品</p>
                        ) : (
                            articles.slice(0, 3).map(article => (
                                <div key={article.id} className="mini-item">
                                    <span className="mini-title">{article.title}</span>
                                    <Link to={`/articles/${article.id}`} className="mini-link">查看</Link>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* 专栏管理模块 */}
                <div className="creator-card">
                    <div className="card-icon">📁</div>
                    <h3 className="card-title">专栏管理</h3>
                    <p className="card-desc">创建和维护您的技术专栏</p>
                    <div className="column-management-mini">
                        <div className="empty-state-mini">
                            <p>您还可以创建 5 个自定义专栏</p>
                            {localStorage.getItem('user_info') && JSON.parse(localStorage.getItem('user_info') || '{}').role === 'ADMIN' && (
                                <Link to="/technical-columns" className="btn btn-primary btn-sm mt-2">创建新专栏</Link>
                            )}
                        </div>
                    </div>
                </div>

                {/* 插件市场模块 */}
                <div className="creator-card">
                    <div className="card-icon">🧩</div>
                    <h3 className="card-title">插件市场</h3>
                    <p className="card-desc">扩展您的创作者工具箱</p>
                    <div className="plugin-list">
                        {plugins.map(plugin => (
                            <div key={plugin.id} className="plugin-item">
                                <div className="item-info">
                                    <h4>{plugin.name}</h4>
                                    <p>{plugin.desc}</p>
                                </div>
                                {plugin.installed ? (
                                    <button className="btn btn-outline-success btn-xs" disabled>已安装</button>
                                ) : (
                                    <button className="btn btn-primary btn-xs" onClick={() => handleInstall(plugin.id)}>安装</button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* 您的创作模块 — 截图红框区域 */}
            <div className="creation-section">
                <div className="creator-card creation-card">
                    <div className="creation-header">
                        <div className="creation-title-row">
                            <div className="card-icon">📝</div>
                            <div>
                                <h3 className="card-title">您的创作</h3>
                                <p className="card-desc">在线写文章，管理您的原创内容</p>
                            </div>
                        </div>
                        <button
                            className="btn-new-article"
                            onClick={() => navigate('/creator/new-article')}
                        >
                            ✏️ 新建文章
                        </button>
                    </div>

                    {/* Tab 切换 */}
                    <div className="creation-tabs">
                        <button
                            className={`creation-tab ${creationTab === 'published' ? 'active' : ''}`}
                            onClick={() => setCreationTab('published')}
                        >
                            📋 历史创作
                        </button>
                        <button
                            className={`creation-tab ${creationTab === 'draft' ? 'active' : ''}`}
                            onClick={() => setCreationTab('draft')}
                        >
                            📄 草稿箱
                        </button>
                    </div>

                    {/* 创作列表 */}
                    <div className="creation-list">
                        {creationLoading ? (
                            <div className="creation-empty">
                                <p>加载中...</p>
                            </div>
                        ) : creationArticles.length === 0 ? (
                            <div className="creation-empty">
                                <p className="empty-icon">📭</p>
                                <p>{creationTab === 'draft' ? '暂无草稿' : '暂无创作'}</p>
                                <button
                                    className="btn-start-writing"
                                    onClick={() => navigate('/creator/new-article')}
                                >
                                    开始创作
                                </button>
                            </div>
                        ) : (
                            creationArticles.map(article => (
                                <div key={article.id} className="creation-item">
                                    <div className="creation-item-info">
                                        <h4 className="creation-item-title">{article.title}</h4>
                                        <div className="creation-item-meta">
                                            <span className={`status-badge ${article.status === 'DRAFT' ? 'draft' : 'published'}`}>
                                                {article.status === 'DRAFT' ? '草稿' : '已发布'}
                                            </span>
                                            <span className="creation-date">{formatDate(article.created_at)}</span>
                                        </div>
                                    </div>
                                    <div className="creation-item-actions">
                                        <button
                                            className="action-btn edit"
                                            onClick={() => navigate(`/creator/edit-article/${article.id}`)}
                                        >
                                            编辑
                                        </button>
                                        {article.status === 'DRAFT' && (
                                            <button
                                                className="action-btn delete"
                                                onClick={() => handleDeleteArticle(article.id)}
                                            >
                                                删除
                                            </button>
                                        )}
                                        {article.status === 'PUBLISHED' && (
                                            <Link
                                                to={`/articles/${article.id}`}
                                                className="action-btn view"
                                            >
                                                查看
                                            </Link>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default CreatorCenter
