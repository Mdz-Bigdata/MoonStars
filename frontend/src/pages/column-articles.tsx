/**
 * 专栏文章列表页
 * VISITOR 点击付费文章时弹出付费弹窗，MEMBER/ADMIN 可直接阅读
 */
import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getArticles, getColumn } from '../services/api'
import { getUserInfo } from '../services/auth'
import type { Article, Column } from '../types'
import PaymentModal from '../components/PaymentModal'
import './column-articles.css'

const ColumnArticles: React.FC = () => {
    const { columnId } = useParams<{ columnId: string }>()
    const [articles, setArticles] = useState<Article[]>([])
    const [column, setColumn] = useState<Column | null>(null)
    const [loading, setLoading] = useState(true)
    const [showPayment, setShowPayment] = useState(false)

    useEffect(() => {
        const fetchData = async () => {
            if (!columnId) return
            try {
                const [columnRes, articlesRes] = await Promise.all([
                    getColumn(columnId),
                    getArticles({ column_id: columnId, size: 100 })
                ])
                setColumn(columnRes)
                setArticles(articlesRes.items)
            } catch (error) {
                console.error('获取专栏文章失败:', error)
            } finally {
                setLoading(false)
            }
        }
        fetchData()
    }, [columnId])

    /**
     * 处理文章点击：VISITOR 对付费内容弹出付费弹窗
     */
    const handleArticleClick = (e: React.MouseEvent, canAccess: boolean) => {
        if (!canAccess) {
            e.preventDefault()
            setShowPayment(true)
        }
    }

    /**
     * 支付成功后刷新页面（用户已升级为 MEMBER）
     */
    const handlePaymentSuccess = () => {
        setShowPayment(false)
        // 刷新页面以反映新的角色权限
        window.location.reload()
    }

    if (loading) return <div className="loading">加载中...</div>
    if (!column) return <div className="error">专栏不存在</div>

    return (
        <div className="column-articles-page">
            <div className="container">
                <div className="column-header">
                    <Link to="/columns" className="back-link">← 返回专栏列表</Link>
                    <div className="header-content">
                        <div className="badge-wrapper">
                            <span className={`badge ${column.is_free ? 'badge-free' : 'badge-paid'}`}>
                                {column.is_free ? '免费专栏' : '付费专栏'}
                            </span>
                            <span className="category-badge">{column.category}</span>
                        </div>
                        <h1>{column.name}</h1>
                        <p className="description">{column.description}</p>
                        <div className="meta">
                            <span>{articles.length} 篇文章</span>
                            <span>•</span>
                            <span>{column.subscriber_count} 位订阅者</span>
                            {!column.is_free && (
                                <>
                                    <span>•</span>
                                    <span className="price-info">¥{column.price}</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>

                <div className="articles-list">
                    {articles.length === 0 ? (
                        <div className="empty-articles">该专栏暂无文章内容</div>
                    ) : (
                        articles.map((article, index) => {
                            const isFreeArticle = article.is_free;
                            const userRole = getUserInfo()?.role;
                            const canAccess = column.is_free || isFreeArticle || userRole === 'MEMBER' || userRole === 'ADMIN';

                            return (
                                <Link
                                    key={article.id}
                                    to={`/articles/${article.id}`}
                                    className={`article-item-catalog ${!canAccess ? 'item-locked' : ''}`}
                                    onClick={(e) => handleArticleClick(e, canAccess)}
                                >
                                    <div className="item-prefix">
                                        <span className="index">{String(index + 1).padStart(2, '0')}</span>
                                        {isFreeArticle && <span className="free-preview-tag">试读</span>}
                                        {!canAccess && <span className="lock-icon-tag">🔒</span>}
                                    </div>
                                    <div className="article-info">
                                        <h3>
                                            {article.title}
                                            {!canAccess && <span className="premium-only-badge">会员专属</span>}
                                        </h3>
                                        <div className="article-meta">
                                            <span>{new Date(article.created_at).toLocaleDateString()}</span>
                                            <span>•</span>
                                            <span>{article.view_count} 次阅读</span>
                                        </div>
                                    </div>
                                    <div className="item-action">
                                        {(() => {
                                            const role = getUserInfo()?.role;
                                            if (role === 'ADMIN' || role === 'MEMBER') {
                                                return (
                                                    <button
                                                        className="catalog-delete-btn"
                                                        onClick={async (e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            if (window.confirm(`确定要删除并从首页即时移除《${article.title}》吗？`)) {
                                                                try {
                                                                    const { deleteArticle } = await import('../services/api');
                                                                    await deleteArticle(article.id);
                                                                    window.location.reload();
                                                                } catch (err) {
                                                                    alert('删除失败');
                                                                }
                                                            }
                                                        }}
                                                    >
                                                        🗑️
                                                    </button>
                                                );
                                            }
                                            return null;
                                        })()}
                                        {canAccess ? '开始阅读' : '加入会员解锁'}
                                        <span className="arrow">→</span>
                                    </div>
                                </Link>
                            );
                        })
                    )}
                </div>
            </div>

            {/* 付费弹窗 */}
            {showPayment && column && !column.is_free && (
                <PaymentModal
                    column={column}
                    onClose={() => setShowPayment(false)}
                    onSuccess={handlePaymentSuccess}
                />
            )}
        </div>
    )
}

export default ColumnArticles
