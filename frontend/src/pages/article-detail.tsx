/**
 * 文章详情页
 * 展示完整的文章内容
 */
import React, { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { getArticle, getComments, createComment, deleteArticle, updateArticle } from '../services/api'
import api from '../services/api'
import { getUserInfo } from '../services/auth'
import type { Article, ContentBlock, Comment } from '../types'
import QuickSummaryPanel from '../components/QuickSummaryPanel'
import MarkmapBoard from '../components/MarkmapBoard'
import AIChat from '../components/AIChat'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'
import './article-detail.css'

// 独立的 CodeBlock 组件
const CodeBlock: React.FC<{ code: string; language?: string }> = ({ code, language }) => {
    const codeRef = React.useRef<HTMLElement>(null)
    const [copied, setCopied] = React.useState(false)
    const [currentLanguage, setCurrentLanguage] = React.useState(language || 'plaintext')

    const languages = [
        'plaintext', 'python', 'bash', 'shell', 'json', 'sql', 'java', 'javascript',
        'typescript', 'css', 'html', 'cpp', 'go', 'rust', 'yaml', 'dockerfile', 'scala'
    ]

    React.useEffect(() => {
        if (codeRef.current) {
            codeRef.current.removeAttribute('data-highlighted')
            const validLanguage = hljs.getLanguage(currentLanguage) ? currentLanguage : 'plaintext'
            codeRef.current.className = `language-${validLanguage}`
            hljs.highlightElement(codeRef.current)
        }
    }, [code, currentLanguage])

    const handleDoubleClick = (e: React.MouseEvent) => {
        const target = e.target as HTMLElement;
        if (target.tagName === 'SELECT' || target.tagName === 'OPTION') return;

        try {
            navigator.clipboard.writeText(code)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        } catch (err) {
            console.error('Failed to copy code:', err)
        }
    }

    return (
        <div className="content-code-wrapper mac-style" onDoubleClick={handleDoubleClick} title="双击复制代码">
            <div className="code-header">
                <div className="code-dots">
                    <span className="dot-red"></span>
                    <span className="dot-yellow"></span>
                    <span className="dot-green"></span>
                </div>
                <div className="code-actions">
                    {copied && <span className="copy-success-badge">已复制!</span>}
                    <select
                        className="code-language-select"
                        value={currentLanguage}
                        onChange={(e) => setCurrentLanguage(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {languages.map(lang => (
                            <option key={lang} value={lang}>{lang}</option>
                        ))}
                    </select>
                </div>
            </div>
            <pre className="content-code">
                <code ref={codeRef}>{code?.trim()}</code>
            </pre>
        </div>
    )
}

const ArticleDetail: React.FC = () => {
    const { id } = useParams<{ id: string }>()
    const navigate = useNavigate()
    const [article, setArticle] = useState<Article | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [mindmapMarkdown, setMindmapMarkdown] = useState<string>('')
    const [isOutlineExpanded, setIsOutlineExpanded] = useState(true)
    const [outline, setOutline] = useState<{ text: string; level: number; index: number; hasChildren?: boolean }[]>([])
    const [collapsedOutlineIndices, setCollapsedOutlineIndices] = useState<Set<number>>(new Set())
    const [recentArticles, setRecentArticles] = useState<any[]>([])
    const [comments, setComments] = useState<Comment[]>([])
    const [newComment, setNewComment] = useState('')
    const [isSubmittingComment, setIsSubmittingComment] = useState(false)
    const [activeOutlineIndex, setActiveOutlineIndex] = useState<number | null>(null)
    const [viewingImage, setViewingImage] = useState<string | null>(null)
    const [imgZoom, setImgZoom] = useState(1);
    const [imgPos, setImgPos] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
    const [isEditing, setIsEditing] = useState(false);
    const [draftArticle, setDraftArticle] = useState<Article | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [allColumns, setAllColumns] = useState<any[]>([]);

    useEffect(() => {
        const role = getUserInfo()?.role;
        if (role === 'ADMIN' || role === 'MEMBER') {
            const fetchAllCols = async () => {
                try {
                    const res = await api.get('/columns');
                    setAllColumns(res.data.items);
                } catch (e) {
                    console.error('Failed to load columns', e);
                }
            };
            fetchAllCols();
        }
    }, []);

    // ... (other states) ...

    useEffect(() => {
        const loadArticle = async () => {
            if (!id) return
            try {
                setLoading(true)
                const data = await getArticle(id)
                setArticle(data)

                const outlineItems = data.content
                    .map((b: ContentBlock, idx: number) => ({ block: b, index: idx }))
                    .filter((item: any) => item.block.type === 'heading')
                    .map((item: any, idx: number, allHeadings: any[]) => {
                        const currentLevel = item.block.content.level;
                        const nextHeading = allHeadings[idx + 1];
                        const hasChildren = nextHeading && nextHeading.block.content.level > currentLevel;
                        return {
                            text: item.block.content.text,
                            level: currentLevel,
                            index: item.index,
                            hasChildren: !!hasChildren
                        }
                    })
                setOutline(outlineItems)

                const headers = outlineItems
                    .map((b: any) => {
                        const prefix = '#'.repeat(b.level)
                        return `${prefix} ${b.text}`
                    })
                    .join('\n')

                setMindmapMarkdown(headers || `# ${data.title}`)
                document.title = data.title;

                // 更新最近浏览
                updateRecentHistory(data);

                // 加载评论
                const commentList = await getComments(id);
                setComments(commentList);
            } catch (err: any) {
                console.error('Failed to load article:', err)
                if (err.response?.status === 402) {
                    setError('PAYMENT_REQUIRED')
                } else {
                    setError('Failed to load article')
                }
            } finally {
                setLoading(false)
            }
        }
        loadArticle()
    }, [id])

    // 将 CSS 字符串解析为 React style 对象
    const parseStyle = (style: string | any): React.CSSProperties => {
        if (!style) return {};
        if (typeof style === 'object') {
            const styleObj: any = {};
            Object.keys(style).forEach(key => {
                const camelKey = key.replace(/-([a-z])/g, (g: string) => g[1].toUpperCase());
                styleObj[camelKey] = style[key];
            });
            return styleObj;
        }
        const styleObj: any = {};
        style.split(';').forEach((pair: string) => {
            const [prop, val] = pair.split(':');
            if (prop && val) {
                const key = prop.trim().replace(/-([a-z])/g, (g: string) => g[1].toUpperCase());
                styleObj[key] = val.trim();
            }
        });
        return styleObj;
    };

    // 监听滚动位置，更新激活的大纲索引
    useEffect(() => {
        const handleScroll = () => {
            const headings = document.querySelectorAll('.content-heading');
            let currentActiveIndex = null;

            for (let i = 0; i < headings.length; i++) {
                const rect = (headings[i] as HTMLElement).getBoundingClientRect();
                if (rect.top <= 150) {
                    currentActiveIndex = parseInt((headings[i] as HTMLElement).dataset.index || '0');
                } else {
                    break;
                }
            }

            if (currentActiveIndex !== null) {
                setActiveOutlineIndex(currentActiveIndex);
            }
        };

        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, [outline]);

    // 最近浏览历史逻辑
    const updateRecentHistory = (currentArticle: Article) => {
        const historyJson = localStorage.getItem('article_history');
        let history = historyJson ? JSON.parse(historyJson) : [];

        // 过滤掉当前文章，并添加到开头
        history = [
            { id: currentArticle.id, title: currentArticle.title, platform: currentArticle.source_platform, date: new Date().toISOString() },
            ...history.filter((item: any) => item.id !== currentArticle.id)
        ].slice(0, 10); // 只保留最近10条

        localStorage.setItem('article_history', JSON.stringify(history));
        setRecentArticles(history);
    }

    const removeFromRecentHistory = (idToRemove: string) => {
        const historyJson = localStorage.getItem('article_history');
        if (!historyJson) return;

        let history = JSON.parse(historyJson);
        history = history.filter((item: any) => item.id !== idToRemove);

        localStorage.setItem('article_history', JSON.stringify(history));
        setRecentArticles(history);
    }

    const handleDelete = async () => {
        if (!article || !window.confirm('确定要删除这篇文章吗？此操作不可恢复。')) return;
        try {
            await deleteArticle(article.id);
            // 🚀 同步删除：从最近浏览历史中移除
            removeFromRecentHistory(article.id);
            alert('文章已删除');
            navigate('/');
        } catch (err) {
            console.error('删除失败:', err);
            alert('删除失败，请检查权限');
        }
    }

    const handleCommentSubmit = async () => {
        if (!newComment.trim() || !id || isSubmittingComment) return;

        try {
            setIsSubmittingComment(true);
            const comment = await createComment({
                article_id: id,
                content: newComment,
                user_name: '匿名访客' // 暂时硬编码
            });
            setComments([comment, ...comments]);
            setNewComment('');
        } catch (err) {
            console.error('Failed to post comment:', err);
            alert('发表评论失败');
        } finally {
            setIsSubmittingComment(false);
        }
    }

    const scrollToHeading = (index: number) => {
        const element = document.getElementById(`heading-${index}`)
        if (element) {
            const yOffset = -80;
            const y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;
            window.scrollTo({ top: y, behavior: 'smooth' });
        }
    }

    const handleOutlineClick = (item: any) => {
        scrollToHeading(item.index);

        // 如果点击的是已经折叠的项，或者该项有子项，我们同时也触发切换状态
        if (item.hasChildren) {
            const newCollapsed = new Set(collapsedOutlineIndices);
            if (newCollapsed.has(item.index)) {
                newCollapsed.delete(item.index);
            } else {
                newCollapsed.add(item.index);
            }
            setCollapsedOutlineIndices(newCollapsed);
        }
    }

    const toggleFolder = (e: React.MouseEvent, index: number) => {
        e.stopPropagation();
        const newCollapsed = new Set(collapsedOutlineIndices);
        if (newCollapsed.has(index)) {
            newCollapsed.delete(index);
        } else {
            newCollapsed.add(index);
        }
        setCollapsedOutlineIndices(newCollapsed);
    }

    const isVisibleInOutline = (index: number) => {
        const itemIdx = outline.findIndex(o => o.index === index);
        if (itemIdx === -1) return true;

        let currentLevel = outline[itemIdx].level;
        for (let i = itemIdx - 1; i >= 0; i--) {
            if (outline[i].level < currentLevel) {
                // 如果父级被折叠，则当前项不可见
                if (collapsedOutlineIndices.has(outline[i].index)) return false;
                currentLevel = outline[i].level;
            }
        }
        return true;
    }

    const expandAllOutline = () => setCollapsedOutlineIndices(new Set());
    const collapseAllOutline = () => {
        const allParentIndices = outline
            .filter(item => item.hasChildren)
            .map(item => item.index);
        setCollapsedOutlineIndices(new Set(allParentIndices));
    };

    // 图片缩放和平移处理逻辑
    const handleWheel = (e: React.WheelEvent) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        setImgZoom(prev => Math.max(0.5, Math.min(5, prev + delta)));
    };

    const handleMouseDown = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsDragging(true);
        setDragStart({ x: e.clientX - imgPos.x, y: e.clientY - imgPos.y });
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!isDragging) return;
        setImgPos({
            x: e.clientX - dragStart.x,
            y: e.clientY - dragStart.y
        });
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    const resetLightbox = () => {
        setViewingImage(null);
        setImgZoom(1);
        setImgPos({ x: 0, y: 0 });
    };

    const renderContentBlock = (block: ContentBlock, index: number): React.ReactNode => {
        if (!block) return null;
        switch (block.type) {
            case 'text': {
                const styleObj = parseStyle(block.content.style);
                // 针对微信优化：如果内容本身就是块级标签（如 section, div, ol），使用 div 而不是 p 包装，避免嵌套 p 导致的间距过大
                const isBlockHtml = /^\s*<(section|div|ol|ul|blockquote)/i.test(block.content.text);
                if (isBlockHtml) {
                    return <div key={index} className="content-text-wrapper" style={styleObj} dangerouslySetInnerHTML={{ __html: block.content.text }} />
                }
                return <p key={index} className="content-text" style={styleObj} dangerouslySetInnerHTML={{ __html: block.content.text }} />
            }
            case 'heading': {
                const HeadingTag = `h${block.content.level}` as any
                const styleObj = parseStyle(block.content.style);
                return (
                    <HeadingTag
                        key={index}
                        id={`heading-${index}`}
                        className="content-heading"
                        data-index={index}
                        style={styleObj}
                        dangerouslySetInnerHTML={{ __html: block.content.text }}
                    />
                )
            }
            case 'image': {
                const imageStyle: React.CSSProperties = { maxWidth: '100%', height: 'auto', ...parseStyle(block.content.style) }
                if (block.content.width) imageStyle.width = block.content.width
                if (block.content.height) imageStyle.height = block.content.height
                const imageClass = `content-image content-image--${block.content.align || 'left'}`
                return (
                    <div key={index} className={imageClass}>
                        <img src={block.content.url} alt={block.content.alt || ''} style={imageStyle} loading="lazy" decoding="async" />
                        {block.content.caption && <div className="image-caption">{block.content.caption}</div>}
                    </div>
                )
            }
            case 'box': {
                const styleObj = parseStyle(block.content.style);
                return (
                    <div key={index} className="content-box" style={styleObj}>
                        {block.content.blocks?.map((child: any, i: number) => renderContentBlock(child, i))}
                    </div>
                )
            }
            case 'table':
                return (
                    <div key={index} className="content-table-wrapper" style={parseStyle(block.content.style)}>
                        <table className="content-table">
                            <tbody>
                                {block.content.rows.map((row: any, ri: number) => (
                                    <tr key={ri} style={parseStyle(row.style)}>
                                        {row.cells.map((cell: any, ci: number) => {
                                            const cellStyle = parseStyle(cell.style);
                                            // 提取并移出 HTML 属性级的样式
                                            const rowSpan = cell.style?.rowspan || undefined;
                                            const colSpan = cell.style?.colspan || undefined;

                                            // 从 CSS 对象中移除非标准 CSS 属性
                                            const cleanStyle = { ...cellStyle };
                                            delete (cleanStyle as any).rowspan;
                                            delete (cleanStyle as any).colspan;

                                            return (
                                                <td
                                                    key={ci}
                                                    style={cleanStyle}
                                                    className={cell.is_header ? 'is-header' : ''}
                                                    rowSpan={rowSpan}
                                                    colSpan={colSpan}
                                                >
                                                    {cell.content?.map((cb: any, cbi: number) => renderContentBlock(cb, cbi))}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )
            case 'list': {
                const ListTag = block.content.ordered ? 'ol' : 'ul'
                const startAttr = (block.content.ordered && block.content.start) ? { start: block.content.start } : {};
                return (
                    <ListTag key={index} className="content-list" {...startAttr}>
                        {block.content.items.map((item: any, ii: number) => {
                            const isTodo = item.todo;
                            const isDone = item.done;
                            return (
                                <li key={ii} className={isTodo ? 'todo-item' : ''}>
                                    <div className="list-item-content">
                                        {isTodo && (
                                            <input
                                                type="checkbox"
                                                readOnly
                                                checked={isDone}
                                                className="todo-checkbox"
                                            />
                                        )}
                                        <div dangerouslySetInnerHTML={{ __html: typeof item === 'string' ? item : item.text }} />
                                    </div>
                                    {item.children && item.children.length > 0 && (
                                        <div className="list-item-children">
                                            {item.children.map((c: any, ci: number) => renderContentBlock(c, ci))}
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ListTag>
                )
            }
            case 'code':
                return <CodeBlock key={index} code={block.content.code || block.content.text} language={block.content.language} />
            case 'quote':
                return <blockquote key={index} className="content-quote" dangerouslySetInnerHTML={{ __html: block.content.text }} />
            case 'divider':
                return <hr key={index} className="content-divider" />
            case 'sheet':
            case 'whiteboard':
            case 'mindmap':
            case 'diagram': {
                if (!block.content) return null;
                const b_type = block.type;
                const previewUrl = block.content.preview;
                const isMissing = block.content.is_missing;

                const getInfo = (type: string) => {
                    switch (type) {
                        case 'sheet': return { label: '电子表单', icon: '📊' };
                        case 'mindmap': return { label: '思维导图', icon: '🧠' };
                        case 'diagram': return { label: '流程图解', icon: '📐' };
                        case 'whiteboard': return { label: '智能画板', icon: '🎨' };
                        default: return { label: '复杂组件', icon: '📦' };
                    }
                }
                const info = getInfo(b_type);
                const isFrameless = b_type === 'whiteboard' || b_type === 'sheet' || b_type === 'mindmap';

                return (
                    <div key={index} className={`content-complex-component component-${b_type} ${isFrameless ? 'is-frameless' : ''}`}>
                        {!isFrameless && (
                            <div className="component-header">
                                <div className="component-type-tag">
                                    {info.icon} {info.label}
                                </div>
                                {block.content.title && <div className="component-title">{block.content.title}</div>}
                                <div className="component-actions">
                                    {previewUrl && (
                                        <button
                                            className="component-action-btn"
                                            onClick={() => setViewingImage(previewUrl)}
                                        >
                                            全屏查看
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}
                        {isMissing ? (
                            <div className="component-missing-placeholder">
                                <div className="placeholder-icon">🔍</div>
                                <div className="placeholder-text">该组件正在努力加载中或需要原文档权限</div>
                                <a href={block.content.link} target="_blank" className="placeholder-link">点击查看原内容</a>
                            </div>
                        ) : (
                            previewUrl && (
                                <div
                                    className={`component-preview-wrapper preview-${b_type}`}
                                    onDoubleClick={() => setViewingImage(previewUrl)}
                                    title="双击放大查看"
                                >
                                    <img
                                        src={previewUrl}
                                        alt={block.content.title || block.type}
                                        loading="lazy"
                                        decoding="async"
                                    />
                                    <div className="component-zoom-hint">双击预览放大</div>
                                </div>
                            )
                        )}
                    </div>
                )
            }
            case 'html':
                return <div key={index} className="content-raw-html" dangerouslySetInnerHTML={{ __html: block.content.text }} />
            case 'callout':
                return (
                    <div
                        key={index}
                        className={`content-callout callout-bg-${block.content.background_color || 'blue'}`}
                        style={{ backgroundColor: block.content.background_color }}
                    >
                        <div className="callout-emoji">{block.content.emoji}</div>
                        <div className="callout-content">
                            {block.content.children?.map((child: any, i: number) => renderContentBlock(child, i))}
                        </div>
                    </div>
                )
            case 'grid':
                return (
                    <div key={index} className="content-grid">
                        {block.content.children?.map((child: any, i: number) => renderContentBlock(child, i))}
                    </div>
                )
            case 'summary_box':
                return (
                    <div key={index} className="article-essence-container">
                        <div className="essence-header">
                            <span className="essence-icon">┃</span>
                            <span className="essence-title">文章精华</span>
                        </div>
                        <div className="content-summary-box">
                            <div className="summary-header">
                                <span className="summary-emoji">{block.content.emoji || '✨'}</span>
                                <span className="summary-title">{block.content.title || '核心总结'}</span>
                            </div>
                            <div className="summary-content">
                                {block.content.text}
                            </div>
                        </div>
                    </div>
                )
            case 'markdown':
                return (
                    <div key={index} className="content-markdown-wrapper">
                        <ReactMarkdown>{block.content.text}</ReactMarkdown>
                    </div>
                )
            default: return null
        }
    }

    const handleEditToggle = () => {
        if (!isEditing && article) {
            setDraftArticle(JSON.parse(JSON.stringify(article)));
        }
        setIsEditing(!isEditing);
    };

    const handleSave = async () => {
        if (!draftArticle || !id) return;
        try {
            setIsSaving(true);
            const updated = await updateArticle(id, {
                title: draftArticle.title,
                content: draftArticle.content,
                is_free: draftArticle.is_free,
                column_id: draftArticle.column_id || undefined
            });
            setArticle(updated);
            setIsEditing(false);
            alert('保存成功');
            window.location.reload(); // Refresh to catch category/access changes
        } catch (err) {
            console.error('保存失败:', err);
            alert('保存失败，请重试');
        } finally {
            setIsSaving(false);
        }
    };

    const handleBlockChange = (index: number, newContent: any) => {
        if (!draftArticle) return;
        const newBlocks = [...draftArticle.content];
        newBlocks[index] = { ...newBlocks[index], content: { ...newBlocks[index].content, ...newContent } };
        setDraftArticle({ ...draftArticle, content: newBlocks });
    };

    const renderEditableBlock = (block: ContentBlock, index: number): React.ReactNode => {
        if (!block) return null;
        switch (block.type) {
            case 'text':
            case 'heading':
                return (
                    <div className="editable-block" key={index}>
                        <div className="editable-block-type">{block.type === 'heading' ? `H${block.content.level}` : 'T'}</div>
                        <textarea
                            className="editable-textarea"
                            value={block.content.text}
                            onChange={(e) => handleBlockChange(index, { text: e.target.value })}
                            rows={Math.max(1, block.content.text.split('\n').length)}
                        />
                    </div>
                );
            case 'quote':
                return (
                    <div className="editable-block" key={index}>
                        <div className="editable-block-type">Quote</div>
                        <textarea
                            className="editable-textarea quote-style"
                            value={block.content.text}
                            onChange={(e) => handleBlockChange(index, { text: e.target.value })}
                        />
                    </div>
                );
            case 'code':
                return (
                    <div className="editable-block" key={index}>
                        <div className="editable-block-type">Code ({block.content.language})</div>
                        <textarea
                            className="editable-textarea code-style"
                            value={block.content.code || block.content.text}
                            onChange={(e) => handleBlockChange(index, { text: e.target.value, code: e.target.value })}
                        />
                    </div>
                );
            default:
                // 对于复杂的或者暂时不支持编辑的，显示只读预览
                return (
                    <div className="editable-block readonly" key={index}>
                        <div className="editable-block-type">{block.type} (Read only)</div>
                        {renderContentBlock(block, index)}
                    </div>
                );
        }
    };

    if (loading) return <div className="article-detail"><div className="spinner"></div></div>

    if (error === 'PAYMENT_REQUIRED') {
        return (
            <div className="article-detail article-detail--locked">
                <div className="locked-container">
                    <div className="premium-shield">💎</div>
                    <div className="locked-header">
                        <h2>专栏会员专属内容</h2>
                        <p className="locked-subtitle">加入会员，即可解锁全站 20+ 优质技术专栏及 1000+ 深度博文</p>
                    </div>

                    <div className="benefit-grid">
                        <div className="benefit-item">
                            <span className="benefit-icon">🚀</span>
                            <div className="benefit-info">
                                <h4>全站通行</h4>
                                <p>解锁所有付费专栏和文章</p>
                            </div>
                        </div>
                        <div className="benefit-item">
                            <span className="benefit-icon">🤖</span>
                            <div className="benefit-info">
                                <h4>AI 深度助手</h4>
                                <p>文章智能总结与问答</p>
                            </div>
                        </div>
                    </div>

                    <div className="locked-actions">
                        <Link to="/profile" className="btn btn-primary btn-lg join-member-btn">立即加入会员</Link>
                        <Link to="/technical-columns" className="btn btn-outline-secondary ml-4">返回专栏列表</Link>
                    </div>
                    <p className="payment-hint">购买后实时生效，支持所有端访问</p>
                </div>
            </div>
        )
    }

    if (error || !article) return <div className="article-detail"><div className="error">{error || 'Article not found'}</div></div>

    const platformNames = { wechat: '微信公众号', feishu: '飞书文档', yuque: '语雀文档' }

    return (
        <div className={`article-detail ${isOutlineExpanded ? 'outline-expanded' : 'outline-collapsed'} ${isEditing ? 'is-editing' : ''}`}>
            {outline.length > 0 && (
                <aside className={`article-outline dark-mode ${isOutlineExpanded ? 'expanded' : 'collapsed'}`}>
                    <div className="outline-toggle" onClick={() => setIsOutlineExpanded(!isOutlineExpanded)}>
                        {isOutlineExpanded ? '←' : '→'}
                    </div>
                    <div className="outline-content">
                        <div className="outline-header">
                            <span>Navigator</span>
                            <div className="outline-controls">
                                <button onClick={expandAllOutline} title="全部展开">展开</button>
                                <button onClick={collapseAllOutline} title="全部合拢">合拢</button>
                            </div>
                        </div>
                        <ul className="outline-list">
                            {outline.map((item) => {
                                const visible = isVisibleInOutline(item.index);
                                const isCollapsed = collapsedOutlineIndices.has(item.index);
                                if (!visible) return null;
                                return (
                                    <li
                                        key={item.index}
                                        className={`outline-item level-${item.level} ${item.hasChildren ? 'has-parent' : ''} ${isCollapsed ? 'is-collapsed' : 'is-expanded'} ${activeOutlineIndex === item.index ? 'active' : ''}`}
                                        onClick={() => handleOutlineClick(item)}
                                    >
                                        {item.hasChildren && (
                                            <span className="outline-icon-btn" onClick={(e) => toggleFolder(e, item.index)}>
                                                {isCollapsed ? '▶' : '▼'}
                                            </span>
                                        )}
                                        <span className="outline-text">{item.text.replace(/<[^>]*>/g, '')}</span>
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                </aside>
            )}

            <div className="article-detail-container">
                <Link to="/" className="article-detail__back">← Home</Link>
                <header className="article-detail__header">
                    {isEditing ? (
                        <input
                            className="article-detail__title-input"
                            value={draftArticle?.title}
                            onChange={(e) => setDraftArticle(prev => prev ? { ...prev, title: e.target.value } : null)}
                        />
                    ) : (
                        <h1 className="article-detail__title">{article.title}</h1>
                    )}
                    <div className="article-detail__meta">
                        <span className={`badge badge-${article.source_platform}`}>{(platformNames as any)[article.source_platform]}</span>
                        <span className="article-detail__date">{new Date(article.created_at).toLocaleDateString()}</span>
                        {(() => {
                            const role = getUserInfo()?.role;
                            if (role === 'ADMIN' || role === 'MEMBER') {
                                return (
                                    <div className="admin-actions-inline">
                                        {isEditing ? (
                                            <>
                                                <button className="btn btn-xs btn-primary ml-4" onClick={handleSave} disabled={isSaving}>
                                                    {isSaving ? '保存中...' : '保存'}
                                                </button>
                                                <button className="btn btn-xs btn-outline-secondary ml-2" onClick={handleEditToggle}>取消</button>
                                            </>
                                        ) : (
                                            <>
                                                <button className="btn btn-xs btn-outline-warning ml-4" onClick={handleEditToggle}>编辑</button>
                                                <button className="btn btn-xs btn-outline-danger ml-2" onClick={handleDelete}>删除</button>
                                            </>
                                        )}
                                    </div>
                                );
                            }
                            return null;
                        })()}
                    </div>
                </header>

                {isEditing && (
                    <div className="article-management-bar card mb-8">
                        <h3>文章分组与权限 (付费专栏 / 免费专栏)</h3>
                        <div className="management-controls grid grid-cols-2">
                            <div className="control-item">
                                <label>访问权限：</label>
                                <div className="flex items-center gap-sm">
                                    <button
                                        className={`btn btn-sm ${draftArticle?.is_free ? 'btn-primary' : 'btn-secondary'}`}
                                        onClick={() => setDraftArticle(prev => prev ? { ...prev, is_free: true } : null)}
                                    >
                                        免费试读
                                    </button>
                                    <button
                                        className={`btn btn-sm ${!draftArticle?.is_free ? 'btn-primary' : 'btn-secondary'}`}
                                        onClick={() => setDraftArticle(prev => prev ? { ...prev, is_free: false } : null)}
                                    >
                                        仅限会员
                                    </button>
                                </div>
                            </div>
                            <div className="control-item">
                                <label>所属技术专栏：</label>
                                <select
                                    className="input"
                                    value={draftArticle?.column_id || ''}
                                    onChange={(e) => setDraftArticle(prev => prev ? { ...prev, column_id: e.target.value || null } : null)}
                                >
                                    <option value="">-- 未归类 (仅首页展示) --</option>
                                    {allColumns.map(col => (
                                        <option key={col.id} value={col.id}>{col.category} | {col.name}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                    </div>
                )}

                {/* 仅对飞书/语雀/微信平台显示脑图，PDF/Word/PPT 等文档类型不显示 */}
                {mindmapMarkdown && !isEditing && ['feishu', 'yuque', 'wechat'].includes(article.source_platform) && (
                    <MarkmapBoard markdown={mindmapMarkdown} title={`${article.title} - 知识脑图`} />
                )}

                <article
                    className={`article-detail__content platform-${article.source_platform} ${isEditing ? 'editing-mode' : ''}`}
                    style={article.container_style ? parseStyle(article.container_style) : {}}
                >
                    {isEditing ? (
                        draftArticle?.content.map((block, index) => renderEditableBlock(block, index))
                    ) : (
                        // 对 PDF/PPT/Office/Text 类型过滤第一个 H1 标题（避免和页面标题重复）
                        (() => {
                            const isDocType = ['pdf', 'ppt', 'office', 'text'].includes(article.source_platform);
                            let firstH1Skipped = false;
                            return article.content.map((block, index) => {
                                if (isDocType && !firstH1Skipped && block.type === 'heading' && block.content?.level === 1) {
                                    firstH1Skipped = true;
                                    return null; // 跳过第一个 H1
                                }
                                return renderContentBlock(block, index);
                            });
                        })()
                    )}
                </article>
            </div >

            {/* AI 助手悬浮窗 */}
            {!isEditing && <AIChat articleId={article.id} articleTitle={article.title} />}

            {/* 右侧侧边栏：浏览历史与评论区 */}
            < aside className="article-widgets" >
                {/* 最近浏览 */}
                < section className="widget widget-recent" >
                    <h3 className="widget-title">最近浏览</h3>
                    <ul className="recent-list">
                        {recentArticles.length > 0 ? (
                            recentArticles.map(item => (
                                <li key={item.id} className="recent-item">
                                    <Link to={`/article/${item.id}`} className="recent-link">
                                        <span className={`recent-platform-dot ${item.platform}`}></span>
                                        <span className="recent-title">{item.title}</span>
                                    </Link>
                                    <button
                                        className="recent-delete-btn"
                                        onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            removeFromRecentHistory(item.id);
                                        }}
                                        title="移除记录"
                                    >
                                        ✕
                                    </button>
                                </li>
                            ))
                        ) : (
                            <div className="empty-hint">暂无浏览记录</div>
                        )}
                    </ul>
                </section >

                {/* 评论区 */}
                < section className="widget widget-comments" >
                    <h3 className="widget-title">互动评论 ({comments.length})</h3>

                    <div className="comment-input-area">
                        <textarea
                            className="comment-textarea"
                            placeholder="写下你的看法..."
                            value={newComment}
                            onChange={(e) => setNewComment(e.target.value)}
                        />
                        <button
                            className="comment-submit-btn"
                            onClick={handleCommentSubmit}
                            disabled={isSubmittingComment}
                        >
                            {isSubmittingComment ? '发送中...' : '提交'}
                        </button>
                    </div>

                    <div className="comments-list">
                        {comments.length > 0 ? (
                            comments.map(c => (
                                <div key={c.id} className="comment-card">
                                    <div className="comment-header">
                                        <span className="comment-author">{c.user_name}</span>
                                        <span className="comment-date">{new Date(c.created_at).toLocaleDateString()}</span>
                                    </div>
                                    <div className="comment-body">{c.content}</div>
                                </div>
                            ))
                        ) : (
                            <div className="empty-hint">沙发还在，快来抢占~</div>
                        )}
                    </div>
                </section >
                {/* 核心摘要与脑图挂件 - 仅对飞书/语雀/微信平台显示 */}
                {article && mindmapMarkdown && ['feishu', 'yuque', 'wechat'].includes(article.source_platform) && (
                    <QuickSummaryPanel
                        summary={article.summary || article.title}
                        mindmapMarkdown={mindmapMarkdown}
                    />
                )}
            </aside >


            {/* Lightbox Modal */}
            {
                viewingImage && (
                    <div className="image-lightbox-overlay" onClick={resetLightbox}>
                        <div
                            className="image-lightbox-content"
                            onClick={e => e.stopPropagation()}
                            onWheel={handleWheel}
                            onMouseDown={handleMouseDown}
                            onMouseMove={handleMouseMove}
                            onMouseUp={handleMouseUp}
                            onMouseLeave={handleMouseUp}
                            style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
                        >
                            <div className="lightbox-image-container">
                                <img
                                    src={viewingImage}
                                    alt="Zoomed view"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (imgZoom !== 1 || imgPos.x !== 0 || imgPos.y !== 0) {
                                            setImgZoom(1);
                                            setImgPos({ x: 0, y: 0 });
                                        }
                                    }}
                                    style={{
                                        transform: `translate(${imgPos.x}px, ${imgPos.y}px) scale(${imgZoom})`,
                                        transition: isDragging ? 'none' : 'transform 0.1s ease-out',
                                        cursor: (imgZoom !== 1 || imgPos.x !== 0 || imgPos.y !== 0) ? 'zoom-out' : (isDragging ? 'grabbing' : 'grab')
                                    }}
                                    draggable={false}
                                    decoding="async"
                                />
                            </div>
                            <button className="lightbox-close" onClick={resetLightbox}>✕</button>
                            <div className="lightbox-controls">
                                <button className="lightbox-control-btn" onClick={(e) => { e.stopPropagation(); setImgZoom(z => Math.max(0.5, z - 0.2)); }} title="缩小">－</button>
                                <span className="lightbox-zoom-level">{Math.round(imgZoom * 100)}%</span>
                                <button className="lightbox-control-btn" onClick={(e) => { e.stopPropagation(); setImgZoom(z => Math.min(5, z + 0.2)); }} title="放大">＋</button>
                                <button className="lightbox-control-btn download-btn" onClick={(e) => {
                                    e.stopPropagation();
                                    const link = document.createElement('a');
                                    link.href = viewingImage;
                                    link.download = `image-${Date.now()}.png`;
                                    document.body.appendChild(link);
                                    link.click();
                                    document.body.removeChild(link);
                                }} title="下载原图">
                                    ⬇
                                </button>
                                {imgZoom !== 1 && (
                                    <button className="lightbox-control-btn reset-btn" onClick={(e) => { e.stopPropagation(); setImgZoom(1); setImgPos({ x: 0, y: 0 }); }} title="重置">
                                        ↺
                                    </button>
                                )}
                            </div>
                            <div className="lightbox-hint">滚轮缩放 | 鼠标拖拽平移 | 双击还原</div>

                        </div>
                    </div>
                )
            }
        </div >
    )
}

export default ArticleDetail
