/**
 * 付费专栏页面
 * 显示用户已购买的专栏
 */
import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getMyColumns } from '../services/api'
import type { Column } from '../types'
import './paid-columns.css'

const PaidColumns: React.FC = () => {
    const [columns, setColumns] = useState<Column[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchColumns = async () => {
            try {
                const data = await getMyColumns()
                setColumns(data)
            } catch (error) {
                console.error('获取已购专栏失败:', error)
            } finally {
                setLoading(false)
            }
        }
        fetchColumns()
    }, [])

    return (
        <div className="paid-columns-page container">
            <div className="page-header">
                <h1>我的付费专栏</h1>
                <p>您已解锁的所有高质量专栏内容</p>
            </div>

            {loading ? (
                <div className="loading-state">加载中...</div>
            ) : columns.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">💎</div>
                    <h3>主页发现更多精彩</h3>
                    <p>您还没有购买任何付费专栏</p>
                    <Link to="/" className="btn btn-primary">去逛逛</Link>
                </div>
            ) : (
                <div className="columns-grid">
                    {columns.map(column => (
                        <div key={column.id} className="column-card">
                            <img
                                src={column.cover_image || 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=500&q=80'}
                                alt={column.name}
                                className="column-cover"
                            />
                            <div className="column-content">
                                <h3>{column.name}</h3>
                                <p className="column-desc">{column.description}</p>
                                <div className="column-meta">
                                    <span>{column.article_count} 篇文章</span>
                                    <span>{column.subscriber_count} 位订阅者</span>
                                </div>
                                <Link to={`/`} className="btn btn-outline-primary btn-block">
                                    立即阅读
                                </Link>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

export default PaidColumns
