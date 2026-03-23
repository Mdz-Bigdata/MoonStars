/**
 * 首页
 * Hero Section + URL 转换入口 + 文章列表
 */
import React, { useState, useEffect } from 'react'
import ArticleCard from '../components/article-card'
import UrlConverter from '../components/url-converter'
import DocumentImport from '../components/DocumentImport'
import VideoAssistant from '../components/VideoAssistant/VideoAssistant'
import { getArticles } from '../services/api'
import { getUserInfo } from '../services/auth'
import type { Article } from '../types'
import './home.css'

const Home: React.FC = () => {
    const [articles, setArticles] = useState<Article[]>([])
    const [loading, setLoading] = useState(true)
    const [page, setPage] = useState(1)
    const [total, setTotal] = useState(0)

    const loadArticles = async () => {
        try {
            setLoading(true)
            const response = await getArticles({ page, size: 9 })
            setArticles(response.items)
            setTotal(response.total)
        } catch (error) {
            console.error('加载文章失败:', error)
        } finally {
            setLoading(false)
        }
    }

    const [jumpPage, setJumpPage] = useState('')

    useEffect(() => {
        loadArticles()
    }, [page])

    const handleJump = () => {
        const target = parseInt(jumpPage)
        const maxPage = Math.ceil(total / 9)
        if (target >= 1 && target <= maxPage) {
            setPage(target)
            setJumpPage('')
        }
    }

    return (
        <div className="home">
            {/* Hero Section */}
            <section className="hero">
                <div className="hero__background"></div>
                <div className="container">
                    <div className="hero__content">
                        <h1 className="hero__title">
                            大数据启示录<br />
                            <span className="gradient-text">技术洞察与实践</span>
                        </h1>
                        <p className="hero__subtitle">
                            支持微信公众号、飞书、语雀文章一键转换
                            <br />
                            智能提取文本、图片、表格，打造专属知识库
                        </p>
                    </div>
                </div>
            </section>

            {getUserInfo()?.role === 'ADMIN' && (
                <section className="tools-section">
                    <div className="container">
                        <div className="tools-center-layout">
                            <div className="tool-card-wrapper">
                                <UrlConverter onSuccess={loadArticles} />
                            </div>
                            <div className="tools-grid">
                                <div className="tool-card-wrapper">
                                    <DocumentImport onSuccess={loadArticles} />
                                </div>
                                <div className="tool-card-wrapper">
                                    <VideoAssistant onSuccess={loadArticles} />
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
            )}

            {/* 文章列表 */}
            <section className="articles-section">
                <div className="container">
                    <div className="section-header">
                        <h2>最新文章</h2>
                    </div>

                    {loading ? (
                        <div className="loading-container">
                            <div className="spinner"></div>
                            <p>加载中...</p>
                        </div>
                    ) : articles.length === 0 ? (
                        <div className="empty-state">
                            <p>还没有文章，快来转换第一篇吧！</p>
                        </div>
                    ) : (
                        <>
                            <div className="grid grid-cols-3">
                                {articles.map((article) => (
                                    <ArticleCard key={article.id} article={article} />
                                ))}
                            </div>

                            {/* 分页 */}
                            {total > 0 && (
                                <div className="pagination">
                                    <div className="pagination__unified">
                                        {/* 第一行：导航 */}
                                        <div className="pagination__nav-row">
                                            <button
                                                className="btn btn-secondary btn-sm"
                                                disabled={page === 1}
                                                onClick={() => setPage(page - 1)}
                                            >
                                                上一页
                                            </button>
                                            <div className="pagination__info">
                                                第 <span className="current-page">{page}</span> 页 / 共 {Math.max(1, Math.ceil(total / 9))} 页
                                            </div>
                                            <button
                                                className="btn btn-secondary btn-sm"
                                                disabled={page >= Math.ceil(total / 9) || total === 0}
                                                onClick={() => setPage(page + 1)}
                                            >
                                                下一页
                                            </button>
                                        </div>

                                        {/* 第二行：统计与跳转 */}
                                        <div className="pagination__stats-row">
                                            <div className="pagination__total-pages">共 {Math.max(1, Math.ceil(total / 9))} 页</div>
                                            <div className="pagination__divider">|</div>
                                            <div className="pagination__jump-section">
                                                <span>跳转第</span>
                                                <input
                                                    type="number"
                                                    className="jump-input"
                                                    value={jumpPage}
                                                    onChange={(e) => setJumpPage(e.target.value)}
                                                    onKeyDown={(e) => e.key === 'Enter' && handleJump()}
                                                    min="1"
                                                    max={Math.ceil(total / 9)}
                                                />
                                                <span>页</span>
                                                <button className="btn btn-primary btn-xs" onClick={handleJump}>确定</button>
                                            </div>
                                            <div className="pagination__divider">|</div>
                                            <div className="pagination__total-articles">共计 {total} 篇文章</div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </section>
        </div>
    )
}

export default Home
