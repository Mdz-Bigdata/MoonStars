import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import ReactMarkdown from 'react-markdown';
import {
    ChevronLeft, RefreshCw, AlertCircle,
    Monitor, Sparkles,
    Trash2, Brain, Copy, Download, ExternalLink, X
} from 'lucide-react';
import { getTaskStatus, fetchVideoHistory, deleteVideoTask } from '../services/video-assistant';
import MarkmapView from '../components/MarkmapView';
import './VideoNoteDetail.css';

const VideoNoteDetail: React.FC = () => {
    const { taskId } = useParams<{ taskId: string }>();
    const navigate = useNavigate();
    const [result, setResult] = useState<any>(null);
    const [status, setStatus] = useState<string>('PENDING');
    const [message, setMessage] = useState<string>('正在获取状态...');
    const [loading, setLoading] = useState(true);
    const [history, setHistory] = useState<any[]>([]);
    const [searchQuery, setSearchQuery] = useState('');

    // 新增状态
    const [isMindMap, setIsMindMap] = useState(false);
    const [showTranscript, setShowTranscript] = useState(false);

    const loadHistory = async () => {
        try {
            const res = await fetchVideoHistory();
            setHistory(res.data || []);
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    };

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        if (!window.confirm('确定要删除这个任务吗？此操作不可逆。')) return;
        try {
            await deleteVideoTask(id);
            setHistory(history.filter(item => item.task_id !== id));
            if (id === taskId) {
                navigate('/');
            }
        } catch (error) {
            alert('删除任务失败');
        }
    };

    const pollStatus = async () => {
        if (!taskId) return;
        try {
            const response = await getTaskStatus(taskId);
            const data = response.data || response;
            setStatus(data.status);
            setMessage(data.message || '');

            if (data.status === 'SUCCESS' && (data.result || data.data?.result)) {
                setResult(data.result || data.data?.result);
                setLoading(false);
            } else if (data.status === 'FAILED') {
                setLoading(false);
            } else {
                setTimeout(pollStatus, 3000);
            }
        } catch (error) {
            console.error('Failed to poll status:', error);
            setMessage('连接服务器失败，正在重试...');
            setTimeout(pollStatus, 5000);
        }
    };

    useEffect(() => {
        setLoading(true);
        pollStatus();
        loadHistory();
    }, [taskId]);

    const handleCopy = () => {
        const text = result?.markdown || '';
        navigator.clipboard.writeText(text).then(() => {
            alert('内容已复制到剪贴板');
        });
    };

    const handleDownload = () => {
        const text = result?.markdown || '';
        const blob = new Blob([text], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const safeTitle = (result?.audio_meta?.title || 'note').replace(/[\\/:*?"<>|]/g, '_');
        a.download = `${safeTitle}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const filteredHistory = history.filter(item =>
        (item.video_url || '').toLowerCase().includes(searchQuery.toLowerCase())
    );

    // 思维导图解析组件 - 切换至 Markmap 图形引擎
    const MindMapView = ({ markdown }: { markdown: string }) => {
        // 清理 markdown 以适配脑图展示
        const cleanMarkdown = markdown
            .split('\n')
            .map(line => {
                // 移除原片链接和时间戳 [▷ 原片 (00:05)](...) 或 [Title 原片 @ 00:05](...)
                // 不再移除 "AI 总结"，以确保其显示
                return line
                    .replace(/\[(?:▷\s+)?原片\s+(?:\(|@\s+).*?(?:\)|\])\]\(.*?\)/g, '')
                    .trim();
            })
            .filter(line => line.length > 0)
            .join('\n');

        return createPortal(
            <div className="mind-map-fullview-overlay">
                <div className="mind-map-fullview-header">
                    <div className="mm-header-left">
                        <Brain size={20} color="#3b82f6" />
                        <span className="mm-header-title">{result?.audio_meta?.title || '知识脑图'}</span>
                    </div>
                    <button className="mm-exit-btn" onClick={() => setIsMindMap(false)}>
                        <X size={18} /> 退出脑图
                    </button>
                </div>
                <div className="mind-map-graphic-container-v2" onDoubleClick={handleCopy} title="双击复制全部内容">
                    <MarkmapView markdown={cleanMarkdown} style={{ height: '100%', width: '100%' }} />
                </div>
            </div>,
            document.body
        );
    };

    const StepBar: React.FC<{ currentStepKey: string }> = ({ currentStepKey }) => {
        const steps = [
            { label: '任务排队', key: 'PENDING' },
            { label: '解析视频', key: 'PROCESSING' },
            { label: '音频转写', key: 'TRANSCRIBING' },
            { label: 'AI 总结', key: 'SUMMARIZING' },
            { label: '生成预览', key: 'SUCCESS' }
        ];

        // 映射复杂状态到步骤
        let activeKey = currentStepKey;
        if (['DOWNLOADING', 'PROCESSING_AUDIO'].includes(currentStepKey)) activeKey = 'PROCESSING';

        const currentIndex = steps.findIndex(s => s.key === activeKey);

        return (
            <div className="step-bar-container">
                <div className="step-bar">
                    {steps.map((step, index) => {
                        const isCompleted = index < currentIndex;
                        const isCurrent = index === currentIndex;
                        const isActive = isCompleted || isCurrent;
                        const isLast = index === steps.length - 1;

                        return (
                            <div key={step.key} className={`step-item ${isActive ? 'active' : ''}`}>
                                <div className="step-circle-wrapper">
                                    <div className={`step-circle ${isActive ? 'active' : 'inactive'}`}>
                                        {isCompleted ? '✓' : index + 1}
                                    </div>
                                    {isCurrent && (
                                        <div className="step-icon-anim">
                                            <RefreshCw className="animate-spin" size={60} color="#3b82f6" style={{ opacity: 0.2 }} />
                                        </div>
                                    )}
                                </div>
                                <div className="step-label">{step.label}</div>
                                {!isLast && (
                                    <div className={`step-line ${isCompleted ? 'active' : ''}`}></div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    };

    const renderContent = () => {
        if (loading) {
            return (
                <div className="video-note-detail__loading">
                    <Sparkles size={48} color="#3b82f6" />
                    <h2>{message || '正在处理您的视频...'}</h2>
                    <p>这可能需要几分钟时间，请稍候</p>
                    <StepBar currentStepKey={status} />
                </div>
            );
        }

        if (status === 'FAILED') {
            return (
                <div className="video-note-detail__loading">
                    <AlertCircle size={48} color="#ef4444" />
                    <h2>转换失败</h2>
                    <p>{message}</p>
                    <button className="action-submit-btn" onClick={() => window.location.reload()}>重试</button>
                </div>
            );
        }

        const markdown = result?.markdown || '';
        const mainContent = markdown.trim();

        // 提取 TOC
        // 支持格式: 
        // 1. 1. 基本概念 [▷ 原片 (00:05)](url)
        // 2. [1. 基本概念 原片 @ 00:05](#...)
        // 3. AI 总结 (无链接或带链接)
        const tocMatches = Array.from(mainContent.matchAll(/^(?:\d+\.\s+.*?\[(?:▷\s+)?原片\s+(?:\(|@\s+)(.*?)(?:\)|\])\]\(.*?\)|\[(\d+\.\s+.*?)\s+原片\s+@\s+(.*?)\]\(.*?\)|^#+\s+(AI 总结.*))/gm));
        const dynamicTOC = tocMatches.map((match: any) => {
            if (match[3]) {
                // 格式 3: AI 总结
                return {
                    cleanTitle: match[3].trim(),
                    time: '',
                    isAISummary: true
                };
            } else if (match[2]) {
                // 格式 2: [Title 原片 @ hh:mm:ss]
                const anchorMatch = match[0].match(/\(#(.*?)\)/);
                return {
                    cleanTitle: match[2].trim(),
                    time: match[3]?.trim() || '',
                    anchor: anchorMatch ? anchorMatch[1] : ''
                };
            } else {
                // 格式 1: Title [▷ 原片 (hh:mm:ss)]
                const fullLine = match[0].trim();
                const titlePart = fullLine.replace(/\[(?:▷\s+)?原片\s+(?:\(|@\s+).*?(?:\)|\])\]\(.*?\)/, '').replace(/^#+\s+/, '').trim();
                const anchorMatch = fullLine.match(/\(#(.*?)\)/);
                return {
                    cleanTitle: titlePart,
                    time: match[1]?.trim() || '',
                    anchor: anchorMatch ? anchorMatch[1] : ''
                };
            }
        }).filter(item => !item.isAISummary);

        return (
            <div className={`main-with-transcript ${showTranscript ? 'active' : ''}`}>
                <div className="content-scroller">
                    <div className="detail-content-inner">
                        {/* Header V2 */}
                        <div className="note-header-v2">
                            <div className="header-top-row">
                                <div className="header-meta-row">
                                    <div className="meta-item">版本 <span>(4da06a)</span></div>
                                    <div className="meta-tag-purple">deepseek-reasoner</div>
                                    <div className="meta-tag-blue">详细</div>
                                    <div className="meta-item">创建时间：{result?.audio_meta?.created_at || '2026-02-05 04:44'}</div>
                                </div>
                                <div className="header-actions">
                                    <button
                                        className={`header-action-btn ${isMindMap ? 'active' : ''}`}
                                        onClick={() => setIsMindMap(!isMindMap)}
                                    >
                                        <Brain size={14} /> 思维导图
                                    </button>
                                    <button className="header-action-btn" onClick={handleCopy}>
                                        <Copy size={14} /> 复制
                                    </button>
                                    <button className="header-action-btn" onClick={handleDownload}>
                                        <Download size={14} /> 导出 Markdown
                                    </button>
                                    <button
                                        className={`header-action-btn ${showTranscript ? 'active' : ''}`}
                                        onClick={() => setShowTranscript(!showTranscript)}
                                    >
                                        <ExternalLink size={14} /> 原文参照
                                    </button>
                                </div>
                            </div>

                            <h1 className="note-title-blue">{result?.audio_meta?.title || '视频笔记'}</h1>
                        </div>

                        {isMindMap ? (
                            <MindMapView markdown={markdown} />
                        ) : (
                            <>
                                {/* TOC V4 (Matching Snapshot 2) */}
                                <div className="toc-list-v4">
                                    <h2 className="toc-header-v4">目录</h2>
                                    <div className="toc-items-v4">
                                        {dynamicTOC.map((item: any, idx: number) => (
                                            <div key={idx} className={`toc-item-v4 ${item.isAISummary ? 'ai-summary' : ''}`}>
                                                <span className="toc-text-v4">
                                                    {item.isAISummary ? (
                                                        <>
                                                            [{item.cleanTitle} <span className="toc-time-link-v4">▷ 原片 ({item.time})</span> ]
                                                        </>
                                                    ) : (
                                                        <>
                                                            [{item.cleanTitle} <span className="toc-time-link-v4">▷ 原片 ({item.time})</span> ]
                                                            {item.anchor && `(#${item.anchor})`}
                                                        </>
                                                    )}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Main Content */}
                                <div className="markdown-content-v2">
                                    <ReactMarkdown
                                        components={{
                                            h2: ({ node, ...props }: any) => {
                                                const children = props.children;
                                                // Handle case where children might be an array with a link or text
                                                let content = '';
                                                if (Array.isArray(children)) {
                                                    content = children.map(c => (typeof c === 'string' ? c : (c.props?.children || ''))).join('');
                                                } else {
                                                    content = children?.toString() || '';
                                                }

                                                const isAISummary = content.includes('AI 总结');

                                                const linkMatch = content.match(/^\[(.*?)\s+原片\s+@\s+(.*?)\]/);
                                                if (linkMatch) {
                                                    return (
                                                        <h2 className="section-heading-v4">
                                                            {linkMatch[1].trim()} <span className="section-time-v4">▷ 原片 ({linkMatch[2].trim()})</span>
                                                        </h2>
                                                    );
                                                }

                                                const timeMatch = content.match(/\[(?:▷\s+)?原片\s+(?:\(|@\s+)(.*?)(?:\)|\])/);
                                                const cleanTextPart = content.replace(/\[(?:▷\s+)?原片\s+(?:\(|@\s+).*?(?:\)|\])\]\(.*?\)/, '').replace(/^#+\s+/, '').trim();
                                                const displayText = cleanTextPart || content;

                                                return (
                                                    <h2 className={`section-heading-v4 ${isAISummary ? 'ai-summary-header' : ''}`}>
                                                        {displayText} {timeMatch && <span className="section-time-v4">▷ 原片 ({timeMatch[1]})</span>}
                                                    </h2>
                                                );
                                            },
                                            h3: ({ node, ...props }: any) => {
                                                const content = props.children?.[0] || '';
                                                if (typeof content !== 'string') return <h3 className="section-subheading-v4">{content}</h3>;

                                                const timeMatch = content.match(/\[(?:▷\s+)?原片\s+(?:\(|@\s+)(.*?)(?:\)|\])/);
                                                const cleanText = content.replace(/\[(?:▷\s+)?原片\s+(?:\(|@\s+).*?(?:\)|\])\]\(.*?\)/, '').trim();
                                                return (
                                                    <h3 className="section-subheading-v4">
                                                        {cleanText} {timeMatch && <span className="section-time-v4">▷ 原片 ({timeMatch[1]})</span>}
                                                    </h3>
                                                );
                                            },
                                            p: ({ node, ...props }: any) => {
                                                const children = props.children;
                                                if (Array.isArray(children) && typeof children[0] === 'string') {
                                                    const text = children[0];
                                                    if (text.startsWith('Q:')) {
                                                        return (
                                                            <p className="qa-row">
                                                                <span className="qa-question">Q:</span>
                                                                {text.substring(2)}
                                                                {children.slice(1)}
                                                            </p>
                                                        );
                                                    } else if (text.startsWith('A:')) {
                                                        return (
                                                            <p className="qa-row">
                                                                <span className="qa-answer">A:</span>
                                                                {text.substring(2)}
                                                                {children.slice(1)}
                                                            </p>
                                                        );
                                                    }
                                                }
                                                return <p {...props} />;
                                            },
                                            strong: ({ node, ...props }: any) => <strong className="highlight-keyword" {...props} />
                                        }}
                                    >
                                        {mainContent
                                            .replace(/^#\s+.*?\n/g, '') // 移除正文开头的重复 H1 标题
                                            .replace(/^##\s*(目录|目)[\s\S]*?(?=\n##|$)/gi, '') // 移除正文开头的重复目录 (忽略大小写)
                                            .replace(/#{1,3}\s(目录|目)\s*?\n/gi, '') // 再次清理中间可能出现的目录标题
                                            .trim()
                                            .replace(/^##\s*(目录|目)[\s\S]*?(?=\n##|$)/gi, '') // 再次尝试移除
                                            .trim()}
                                    </ReactMarkdown>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {showTranscript && (
                    <div className="transcript-panel">
                        <div className="transcript-header">
                            <h3>转写结果</h3>
                            <button onClick={() => setShowTranscript(false)}><X size={16} /></button>
                        </div>
                        <div className="transcript-list">
                            {result?.transcript?.segments?.map((seg: any, i: number) => (
                                <div key={i} className="transcript-row">
                                    <span className="ts-time">{seg.start_time}</span>
                                    <span className="ts-text">{seg.text}</span>
                                </div>
                            )) || (
                                    <div className="history-empty">暂无转写数据</div>
                                )}
                        </div>
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="video-note-detail">
            <div className="video-note-detail__container">
                {/* Sidebar */}
                <div className="detail-sidebar">
                    <div className="sidebar-header">
                        <Link to="/" className="back-link">
                            <ChevronLeft size={18} /> 返回工作台
                        </Link>

                        <div className="sidebar-title-row">
                            <Sparkles className="sidebar-title-icon" size={18} />
                            <span className="sidebar-title-text">生成历史</span>
                        </div>

                        <div className="sidebar-search-wrapper">
                            <input
                                type="text"
                                className="sidebar-search-input"
                                placeholder="搜索笔记标题..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>
                    </div>

                    <div className="sidebar-content">
                        {filteredHistory.map((item: any) => (
                            <div
                                key={item.task_id}
                                className={`history-item ${item.task_id === taskId ? 'active' : ''}`}
                                onClick={() => navigate(`/video-note-detail/${item.task_id}`)}
                            >
                                <div className="history-item-icon">
                                    <Monitor size={16} color={item.task_id === taskId ? '#fff' : '#64748b'} />
                                </div>
                                <div className="history-item-info">
                                    <div className="history-item-title">{item.video_url || '未知视频'}</div>
                                    <div className="history-item-date">{item.created_at}</div>
                                </div>
                                <button
                                    className="history-item-delete"
                                    onClick={(e) => handleDelete(e, item.task_id)}
                                >
                                    <Trash2 size={12} />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Main Content Area */}
                <div className="detail-main">
                    {renderContent()}
                </div>
            </div>
        </div>
    );
};

export default VideoNoteDetail;
