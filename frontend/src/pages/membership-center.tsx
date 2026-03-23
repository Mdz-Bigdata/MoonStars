/**
 * 会员中心 (原购买记录)
 * 支持高级筛选、搜索、导出和互动
 */
import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import './purchase-history.css' // 后续更新样式

interface PurchaseRecord {
    id: string
    column_name: string
    column_id: string
    amount: number
    status: string
    created_at: string
    paid_at?: string
    evaluation?: string
    rating?: number
    is_favorite: boolean
}

const MembershipCenter: React.FC = () => {
    const [records, setRecords] = useState<PurchaseRecord[]>([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [loading, setLoading] = useState(true)
    const [search, setSearch] = useState('')
    const [statusFilter, setStatusFilter] = useState('')
    const [expandedId, setExpandedId] = useState<string | null>(null)

    const fetchRecords = async (p: number = page) => {
        setLoading(true)
        try {
            const token = localStorage.getItem('token')
            const response = await axios.get('/api/purchase-records', {
                params: {
                    page: p,
                    size: 10,
                    search,
                    status: statusFilter || undefined
                },
                headers: { Authorization: `Bearer ${token}` }
            })
            setRecords(response.data.items)
            setTotal(response.data.total)

            // 首次加载且有数据时，默认展开第一条 (最新的)
            if (p === 1 && response.data.items.length > 0 && !expandedId) {
                setExpandedId(response.data.items[0].id)
            }
        } catch (error) {
            console.error('获取记录失败', error)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchRecords(1)
    }, [statusFilter])

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault()
        fetchRecords(1)
    }

    const exportToPDF = async () => {
        try {
            const token = localStorage.getItem('token')
            const response = await axios.get('/api/purchase-records/export/pdf', {
                headers: { Authorization: `Bearer ${token}` },
                responseType: 'blob'
            })
            const url = window.URL.createObjectURL(new Blob([response.data]))
            const link = document.createElement('a')
            link.href = url
            link.setAttribute('download', 'purchase_records.pdf')
            document.body.appendChild(link)
            link.click()
        } catch (error) {
            alert('导出失败，请稍后重试')
        }
    }

    const toggleFavorite = async (id: string, current: boolean) => {
        try {
            const token = localStorage.getItem('token')
            if (current) {
                await axios.delete(`/api/purchase-records/${id}/favorite`, {
                    headers: { Authorization: `Bearer ${token}` }
                })
            } else {
                await axios.post(`/api/purchase-records/${id}/favorite`, {}, {
                    headers: { Authorization: `Bearer ${token}` }
                })
            }
            fetchRecords()
        } catch (error) {
            console.error('收藏操作失败')
        }
    }

    const formatPrice = (amount: number) => (amount / 100).toFixed(2)

    return (
        <div className="membership-center-page">
            <div className="container py-4">
                <div className="d-flex justify-content-between align-items-center mb-4">
                    <h1>会员中心</h1>
                    <button className="btn btn-outline-secondary" onClick={exportToPDF}>
                        <i className="bi bi-download me-2"></i>导出 PDF
                    </button>
                </div>

                {/* 筛选与搜索 */}
                <div className="card mb-4 shadow-sm">
                    <div className="card-body">
                        <form className="row g-3" onSubmit={handleSearch}>
                            <div className="col-md-4">
                                <input
                                    type="text"
                                    className="form-control"
                                    placeholder="搜索商品名称..."
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                />
                            </div>
                            <div className="col-md-3">
                                <select
                                    className="form-select"
                                    value={statusFilter}
                                    onChange={(e) => setStatusFilter(e.target.value)}
                                >
                                    <option value="">所有状态</option>
                                    <option value="paid">已完成</option>
                                    <option value="pending">待支付</option>
                                    <option value="cancelled">已取消</option>
                                </select>
                            </div>
                            <div className="col-md-2">
                                <button type="submit" className="btn btn-primary w-100">搜索</button>
                            </div>
                        </form>
                    </div>
                </div>

                {/* 加载状态 */}
                {loading ? (
                    <div className="text-center py-5">
                        <div className="spinner-border text-primary" role="status">
                            <span className="visually-hidden">加载中...</span>
                        </div>
                        <p className="mt-3">数据加载中...</p>
                    </div>
                ) : records.length > 0 ? (
                    <div className="purchase-list">
                        {records.map(record => (
                            <div key={record.id} className="card mb-3 shadow-sm border-0">
                                <div
                                    className="card-header bg-white d-flex justify-content-between align-items-center cursor-pointer"
                                    onClick={() => setExpandedId(expandedId === record.id ? null : record.id)}
                                >
                                    <div>
                                        <span className="fw-bold">{record.column_name}</span>
                                        <span className="text-muted ms-3 small">{new Date(record.created_at).toLocaleString()}</span>
                                    </div>
                                    <div className="d-flex align-items-center">
                                        <span className={`badge bg-${record.status === 'paid' ? 'success' : 'warning'} me-3`}>
                                            {record.status === 'paid' ? '已完成' : '待处理'}
                                        </span>
                                        <span className="fw-bold text-primary me-3">¥{formatPrice(record.amount)}</span>
                                        <i className={`bi bi-chevron-${expandedId === record.id ? 'up' : 'down'}`}></i>
                                    </div>
                                </div>
                                {expandedId === record.id && (
                                    <div className="card-body border-top">
                                        <div className="row">
                                            <div className="col-md-6">
                                                <p><strong>订单编号:</strong> {record.id}</p>
                                                <p><strong>支付时间:</strong> {record.paid_at ? new Date(record.paid_at).toLocaleString() : '未支付'}</p>
                                                <p><strong>专栏 ID:</strong> {record.column_id}</p>
                                            </div>
                                            <div className="col-md-6 text-end">
                                                <button
                                                    className={`btn btn-sm ${record.is_favorite ? 'btn-danger' : 'btn-outline-danger'} me-2`}
                                                    onClick={(e) => { e.stopPropagation(); toggleFavorite(record.id, record.is_favorite); }}
                                                >
                                                    <i className={`bi bi-heart${record.is_favorite ? '-fill' : ''}`}></i>
                                                </button>
                                                <Link to={`/`} className="btn btn-sm btn-outline-primary me-2">查看专栏</Link>
                                                <button className="btn btn-sm btn-outline-secondary">
                                                    <i className="bi bi-share"></i>
                                                </button>
                                            </div>
                                        </div>
                                        {record.status === 'paid' && (
                                            <div className="mt-3 pt-3 border-top">
                                                <h6>评价该商品:</h6>
                                                <div className="d-flex gap-2">
                                                    {[1, 2, 3, 4, 5].map(s => (
                                                        <i key={s} className={`bi bi-star${(record.rating || 0) >= s ? '-fill' : ''} cursor-pointer text-warning`}></i>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}

                        {/* 分页 */}
                        <nav className="mt-4">
                            <ul className="pagination justify-content-center">
                                {[...Array(Math.ceil(total / 10))].map((_, i) => (
                                    <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}>
                                        <button className="page-link" onClick={() => { setPage(i + 1); fetchRecords(i + 1); }}>{i + 1}</button>
                                    </li>
                                ))}
                            </ul>
                        </nav>
                    </div>
                ) : (
                    <div className="text-center py-5 bg-light rounded shadow-sm">
                        <i className="bi bi-inboxes display-1 text-muted"></i>
                        <p className="mt-3 lead">暂无购买记录</p>
                        <Link to="/columns" className="btn btn-primary mt-2">去逛逛技术专栏</Link>
                    </div>
                )}
            </div>

            {/* 底部帮助文档链接 */}
            <div className="container text-center mt-5 mb-4 py-3 border-top">
                <a href="/help/orders" className="text-muted text-decoration-none">
                    <i className="bi bi-question-circle me-1"></i>如何使用购买记录功能？查看帮助文档
                </a>
            </div>
        </div>
    )
}

export default MembershipCenter
