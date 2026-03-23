import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getColumns, getColumnArticles, getMyColumns } from '../services/api';
import { getUserInfo } from '../services/auth';
import PaymentModal from '../components/PaymentModal';
import type { Column, Article } from '../types';
import './technical-columns.css';

/**
 * 技术专栏列表页面
 * 采用双栏布局 (Free & Premium)，支持折叠展示文章预览
 */
const TechnicalColumns: React.FC = () => {
    const navigate = useNavigate();
    const [columns, setColumns] = useState<Column[]>([]);
    const [loading, setLoading] = useState(true);

    // 折叠状态管理
    const [expandedColumnIds, setExpandedColumnIds] = useState<Set<string>>(new Set());
    // 文章缓存 Map: { columnId: Article[] }
    const [columnArticlesMap, setColumnArticlesMap] = useState<Record<string, Article[]>>({});
    // 文章加载状态 Map: { columnId: boolean }
    const [articleLoadingMap, setArticleLoadingMap] = useState<Record<string, boolean>>({});

    // 支付弹窗状态
    const [showPayment, setShowPayment] = useState(false);
    const [selectedColumn, setSelectedColumn] = useState<Column | null>(null);
    const [purchasedColumnIds, setPurchasedColumnIds] = useState<Set<string>>(new Set());

    useEffect(() => {
        const fetchData = async () => {
            try {
                // 并行获取专栏列表和已购列表
                const [allColumns, myPurchased] = await Promise.all([
                    getColumns(),
                    getUserInfo() ? getMyColumns().catch(() => []) : Promise.resolve([])
                ]);

                setColumns(allColumns.items);
                setPurchasedColumnIds(new Set(myPurchased.map(c => c.id)));
            } catch (error) {
                console.error('初始化数据失败:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    /**
     * 展开/收起专栏
     */
    const toggleColumn = async (columnId: string) => {
        const newExpanded = new Set(expandedColumnIds);
        if (newExpanded.has(columnId)) {
            newExpanded.delete(columnId);
        } else {
            newExpanded.add(columnId);
            // 如果还未加载过文章，则请求数据
            if (!columnArticlesMap[columnId] && !articleLoadingMap[columnId]) {
                loadArticles(columnId);
            }
        }
        setExpandedColumnIds(newExpanded);
    };

    /**
     * 加载特定专栏的文章
     */
    const loadArticles = async (columnId: string) => {
        setArticleLoadingMap(prev => ({ ...prev, [columnId]: true }));
        try {
            // NOTE: 使用专栏专用接口，绕过付费内容过滤，允许所有角色预览文章标题
            const res = await getColumnArticles(columnId, 1, 50);
            setColumnArticlesMap(prev => ({ ...prev, [columnId]: res.items }));
        } catch (error) {
            console.error(`加载专栏 ${columnId} 文章失败:`, error);
        } finally {
            setArticleLoadingMap(prev => ({ ...prev, [columnId]: false }));
        }
    };

    /**
     * 处理文章点击
     */
    const handleArticleClick = (e: React.MouseEvent, article: Article, column: Column) => {
        const userInfo = getUserInfo();
        const userRole = userInfo?.role;
        const isPurchased = purchasedColumnIds.has(column.id);
        const canAccess = column.is_free || article.is_free || isPurchased || userRole === 'ADMIN';

        if (!canAccess) {
            e.preventDefault();
            setSelectedColumn(column);
            setShowPayment(true);
        } else {
            navigate(`/articles/${article.id}`);
        }
    };

    const freeColumns = columns.filter(c => c.is_free);
    const premiumColumns = columns.filter(c => !c.is_free);

    const renderColumnList = (title: string, subtitle: string, columnList: Column[], className: string) => (
        <div className={`column-section ${className}`}>
            <div className="section-header-card">
                <h2>{title}</h2>
                <p>{subtitle}</p>
            </div>
            <div className="accordion-list">
                {columnList.length === 0 ? (
                    <div className="empty-hint">暂无内容</div>
                ) : (
                    columnList.map(column => {
                        const isExpanded = expandedColumnIds.has(column.id);
                        const articles = columnArticlesMap[column.id] || [];
                        const isArticleLoading = articleLoadingMap[column.id];

                        return (
                            <div key={column.id} className={`accordion-item ${isExpanded ? 'expanded' : ''}`}>
                                <div className="accordion-trigger" onClick={() => toggleColumn(column.id)}>
                                    <div className="trigger-main">
                                        <span className="column-name">
                                            {column.name}
                                            {(() => {
                                                const userInfo = getUserInfo();
                                                const userRole = userInfo?.role;
                                                const isPurchased = purchasedColumnIds.has(column.id);
                                                const isLocked = !column.is_free && !isPurchased && userRole !== 'ADMIN';
                                                return isLocked && <span className="column-lock-icon">🔒</span>;
                                            })()}
                                            {!column.is_free && (
                                                <span className="price-tag">
                                                    (¥{Number(column.price / 100).toFixed(0)})
                                                </span>
                                            )}
                                        </span>
                                    </div>
                                    <div className="trigger-icon">{isExpanded ? '−' : '+'}</div>
                                </div>
                                {isExpanded && (
                                    <div className="accordion-content">
                                        {isArticleLoading ? (
                                            <div className="inline-loader">加载中...</div>
                                        ) : articles.length === 0 ? (
                                            <div className="no-articles">该专栏暂无文章</div>
                                        ) : (
                                            <ul className="article-preview-list">
                                                {articles.map(article => {
                                                    return (
                                                        <li key={article.id} className="article-preview-item">
                                                            <div
                                                                className="article-link"
                                                                onClick={(e) => handleArticleClick(e, article, column)}
                                                            >
                                                                <div className="item-left">
                                                                    {article.is_free ? (
                                                                        <span className="trial-tag">试读</span>
                                                                    ) : (
                                                                        <span className="bullet"></span>
                                                                    )}
                                                                    <div className="article-text">
                                                                        <span className="title">{article.title}</span>
                                                                        <span className="belong">所属：{column.name}</span>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );

    if (loading) return <div className="full-page-loading">加载中...</div>;

    return (
        <div className="technical-columns-optimized">
            <div className="optimized-container">
                <div className="columns-layout">
                    {renderColumnList("免费专栏 (Free)", "优质技术洞察，助力系统化学习", freeColumns, "free-section")}
                    {renderColumnList("付费专栏 (Premium)", "加入会员后即可解锁全部深度技术专栏", premiumColumns, "premium-section")}
                </div>
            </div>

            {showPayment && selectedColumn && (
                <PaymentModal
                    column={selectedColumn}
                    onClose={() => setShowPayment(false)}
                    onSuccess={() => {
                        // 即时解锁：将该专栏添加到已购集合
                        setPurchasedColumnIds(prev => new Set([...prev, selectedColumn.id]));
                        setShowPayment(false);
                    }}
                />
            )}
        </div>
    );
};

export default TechnicalColumns;
