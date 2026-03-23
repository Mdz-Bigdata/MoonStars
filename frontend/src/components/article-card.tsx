/**
 * 文章卡片组件
 * 展示文章预览信息
 */
import React from 'react'
import { Link } from 'react-router-dom'
import { deleteArticle } from '../services/api'
import { getUserInfo } from '../services/auth'
import type { Article } from '../types'
import './article-card.css'

interface ArticleCardProps {
    article: Article
}

const ArticleCard: React.FC<ArticleCardProps> = ({ article }) => {
    // 平台显示名称
    const platformNames = {
        wechat: '微信公众号',
        feishu: '飞书文档',
        yuque: '语雀文档',
        original: '原创文章',
    } as const;

    // 格式化日期
    const formatDate = (dateString: string) => {
        const date = new Date(dateString)
        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        })
    }

    return (
        <article className="article-card card">
            {article.cover_image && (
                <div className="article-card__cover">
                    <img src={article.cover_image} alt={article.title} />
                </div>
            )}

            <div className="article-card__content">
                <div className="article-card__meta">
                    <span className={`badge badge-${article.source_platform}`}>
                        {platformNames[article.source_platform as keyof typeof platformNames]}
                    </span>
                    <span className="article-card__date">
                        {formatDate(article.created_at)}
                    </span>
                </div>

                <h3 className="article-card__title">
                    <Link to={`/articles/${article.id}`}>{article.title}</Link>
                </h3>

                {article.summary && (
                    <p className="article-card__summary">{article.summary}</p>
                )}

                <div className="article-card__footer">
                    <span className="article-card__views">
                        👁️ {article.view_count} 次浏览
                    </span>
                    <div className="article-card__footer-right">
                        {getUserInfo()?.role === 'ADMIN' && (
                            <button
                                className="article-card__delete-btn"
                                onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    if (window.confirm(`确定要删除文章《${article.title}》吗？此操作不可撤销。`)) {
                                        deleteArticle(article.id).then(() => {
                                            window.location.reload();
                                        }).catch((err: any) => {
                                            alert('删除失败: ' + (err.response?.data?.detail || err.message));
                                        });
                                    }
                                }}
                                title="删除文章"
                            >
                                🗑️
                            </button>
                        )}
                        {article.column_category && (
                            <span className={`article-card__category-tag ${!article.column_is_free && !article.is_free ? 'tag-paid' : 'tag-free'}`}>
                                {article.column_is_free ? '免费专栏-' : '付费专栏-'}
                                {article.column_category}
                                {!article.column_is_free && !article.is_free && (getUserInfo()?.role !== 'ADMIN' && getUserInfo()?.role !== 'MEMBER') && ' 🔒'}
                            </span>
                        )}
                        <Link to={`/articles/${article.id}`} className="btn-read">
                            阅读更多 →
                        </Link>
                    </div>
                </div>
            </div>
        </article>
    )
}

export default ArticleCard
