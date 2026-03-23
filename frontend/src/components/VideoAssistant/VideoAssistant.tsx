import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { generateVideoNote, fetchVideoModels, fetchVideoHistory, deleteVideoTask } from '../../services/video-assistant';
import type { VideoNoteConfig } from '../../services/video-assistant';
import {
    Settings, Loader2, Sparkles, ExternalLink,
    History as HistoryIcon, Clock, Info, RotateCcw, Plus,
    AlertCircle, X, MonitorPlay, Trash2
} from 'lucide-react';
import './VideoAssistant.css';

interface VideoAssistantProps {
    onSuccess?: () => void;
}

const VideoAssistant: React.FC<VideoAssistantProps> = ({ onSuccess }) => {
    const navigate = useNavigate();
    // 基础状态
    const [url, setUrl] = useState('');
    const [platform, setPlatform] = useState('bilibili');
    const [style, setStyle] = useState('detailed');
    const [model, setModel] = useState('');
    const [models, setModels] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [taskId, setTaskId] = useState<string | null>(null);
    const [history, setHistory] = useState<any[]>([]);
    const [showHistory, setShowHistory] = useState(false);

    // 高级功能状态
    const [videoUnderstanding, setVideoUnderstanding] = useState(false);
    const [interval, setInterval] = useState(4);
    const [gridSize, setGridSize] = useState<[number, number]>([3, 3]);
    const [formats, setFormats] = useState<string[]>(['toc', 'link', 'summary']);
    const [extras, setExtras] = useState('');
    const [showAlert, setShowAlert] = useState(true);

    useEffect(() => {
        const loadData = async () => {
            try {
                // 加载历史记录
                const historyRes = await fetchVideoHistory();
                setHistory(historyRes.data || []);

                // 从 localStorage 获取统一保存的模型配置
                const savedConfig = localStorage.getItem('ai_models_config_v2');
                let availableModels: any[] = [];

                if (savedConfig) {
                    const configData = JSON.parse(savedConfig);
                    console.log("=== VideoAssistant loadData ===");
                    console.log("Raw configData from localStorage:", configData);
                    
                    // 核心修复：处理所有的存储格式！
                    // AI配置页(ai-config-page)存入的是数组：[ {id: 'deepseek', ...}, {id: 'qwen', ...} ]
                    // AIConfigModal 存入的是字典：{ "deepseek": {enabled: true, ...}, "qwen": {enabled: true, ...} }
                    let providers: any[] = [];
                    if (Array.isArray(configData)) {
                        providers = configData;
                    } else if (typeof configData === 'object') {
                        // 如果是字典，把 key 强行赋给 id 属性（如果内部没有 id 的话）
                        providers = Object.entries(configData).map(([key, val]: [string, any]) => ({
                            id: val.id || key,
                            ...val
                        }));
                    }
                         
                    console.log("Parsed providers array:", providers);

                    // 遍历配置，筛选出 enabled 为 true 的供应商
                    providers.forEach((provider: any) => {
                        console.log(`Checking provider [${provider.id || provider.name}]: enabled=${provider.enabled}`);
                        if (provider.enabled) {
                            // 收集该 provider 下的所有可选模型
                            let collectedModels: string[] = [];
                            
                            // 1. 如果有 models 数组（AI配置页结构），收集它们
                            if (provider.models && Array.isArray(provider.models) && provider.models.length > 0) {
                                collectedModels = [...provider.models];
                            } 
                            // 2. 如果有 variants 数组（AIConfigModal 结构），收集它们的 id
                            else if (provider.variants && Array.isArray(provider.variants) && provider.variants.length > 0) {
                                collectedModels = provider.variants.map((v: any) => v.id);
                            }
                            
                            // 3. 核心兜底：如果它有 activeVariantId (选中的模型名称) 且不在列表中，也强行加进去
                            if (provider.activeVariantId && !collectedModels.includes(provider.activeVariantId)) {
                                collectedModels.push(provider.activeVariantId);
                            }

                            // 统一转换并推入最终列表
                            collectedModels.forEach(mName => {
                                // 避免重复推入
                                if (!availableModels.find(m => m.id === `${provider.id}-${mName}`)) {
                                    availableModels.push({
                                        id: `${provider.id}-${mName}`,
                                        model_name: mName,
                                        provider_id: provider.id,
                                        // 优先显示 name，如果没有则回退显示大写的 ID
                                        provider_name: provider.name || provider.id.toUpperCase()
                                    });
                                }
                            });
                        }
                    });
                    
                    console.log("Final availableModels:", availableModels);
                }

                setModels(availableModels);

                // 自动选择第一个可用模型
                if (availableModels.length > 0) {
                    setModel(availableModels[0].model_name);
                }
            } catch (error) {
                console.error('Failed to load data:', error);
            }
        };
        loadData();
    }, []);

    const handleFormatChange = (value: string) => {
        setFormats(prev =>
            prev.includes(value) ? prev.filter(f => f !== value) : [...prev, value]
        );
    };

    const handleGenerate = async () => {
        if (!url) {
            alert('请输入视频链接');
            return;
        }

        // 查找对应的供应商 ID
        const selectedModelObj = models.find(m => m.model_name === model);
        if (!selectedModelObj) {
            alert('请先在 AI 配置页开启对应的模型供应商');
            return;
        }

        setLoading(true);
        try {
            const config: VideoNoteConfig = {
                video_url: url,
                platform: platform,
                quality: 'medium',
                screenshot: formats.includes('screenshot'),
                link: formats.includes('link'),
                model_name: model,
                provider_id: String(selectedModelObj.provider_id),
                style: style,
                format: formats,
                video_understanding: videoUnderstanding,
                video_interval: interval,
                grid_size: gridSize,
                extras: extras
            };
            const result = await generateVideoNote(config);
            const actualTaskId = result.data?.task_id || result.task_id;
            setTaskId(actualTaskId);
            navigate(`/video-assistant/progress/${actualTaskId}`);

            // 刷新历史
            const historyRes = await fetchVideoHistory();
            setHistory(historyRes.data || []);

            if (onSuccess) onSuccess();
        } catch (error) {
            console.error('Generation failed:', error);
            alert('提交任务失败，请检查配置或后端连接');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        if (!window.confirm('确定要删除这个任务吗？')) return;
        try {
            await deleteVideoTask(id);
            setHistory(prev => prev.filter(item => item.task_id !== id));
        } catch (error) {
            console.error('Delete failed:', error);
            alert('删除任务失败');
        }
    };

    const handleReset = () => {
        setUrl('');
        setExtras('');
        setTaskId(null);
    };

    const platforms = [
        {
            id: 'bilibili',
            name: '哔哩哔哩',
            icon: (
                <svg viewBox="0 0 24 24" width="20" height="20" fill="#fb7299">
                    <path d="M17.1,3.4l1.6,1.6l-2,2h-11l-2-2l1.6-1.6l1.9,1.9h7.9L17.1,3.4z M19,8.4c1.1,0,2,0.9,2,2v8c0,1.1-0.9,2-2,2H5 c-1.1,0-2-0.9-2-2v-8c0-1.1,0.9-2,2-2H19z M12,11.4c-1.1,0-2,0.9-2,2s0.9,2,2,2s2-0.9,2-2S13.1,11.4,12,11.4z M7,11.4 c-0.6,0-1,0.4-1,1s0.4,1,1,1s1-0.4,1-1S7.6,11.4,7,11.4z M17,11.4c-0.6,0-1,0.4-1,1s0.4,1,1,1s1-0.4,1-1S17.6,11.4,17,11.4z" />
                </svg>
            )
        },
        {
            id: 'youtube',
            name: 'YouTube',
            icon: (
                <svg viewBox="0 0 24 24" width="20" height="20" fill="#ff0000">
                    <path d="M22.5,12c0,4.7-0.4,6.4-1.2,7.2C20.6,20,19.2,20,12,20s-8.6,0-9.3-0.8c-0.8-0.8-1.2-2.5-1.2-7.2s0.4-6.4,1.2-7.2C3.4,4,4.8,4,12,4 s8.6,0,9.3,0.8C22.1,5.6,22.5,7.3,22.5,12z M9.5,15.5l6.5-3.5L9.5,8.5V15.5z" />
                </svg>
            )
        },
        {
            id: 'douyin',
            name: '抖音',
            icon: (
                <svg viewBox="0 0 24 24" width="20" height="20" fill="#000000">
                    <path d="M15.4,4.1c0,0.4,0,0.8,0,1.2c1.7,0,3.1,1,3.8,2.4c0.5,1.1,0.6,2.2,0.4,3.4c-0.1,0.9-0.5,1.7-1,2.3L18.4,13.4 c-0.7,0-1.4-0.1-2.1-0.2c-0.1,2.8-2.4,5.1-5.2,5.1c-2.9,0-5.3-2.4-5.3-5.3s2.4-5.3,5.3-5.3c0.3,0,0.5,0,0.8,0.1V11c-0.3-0.1-0.5-0.1-0.8-0.1 c-1.4,0-2.6,1.2-2.6,2.6c0,1.4,1.2,2.6,2.6,2.6c1.3,0,2.4-1,2.6-2.3c0-0.1,0-0.2,0-0.3c0-1.9,0.1-4.7,0.1-7.1C14,6.1,14,5.1,14,4.1 h1.4V4.1z" />
                </svg>
            )
        },
        {
            id: 'kuaishou',
            name: '快手',
            icon: (
                <svg viewBox="0 0 24 24" width="20" height="20" fill="#ff5000">
                    <path d="M12,4c-4.4,0-8,3.6-8,8s3.6,8,8,8s8-3.6,8-8S16.4,4,12,4z M15,13.5l-4,2.5c-0.3,0.2-0.7,0-0.7-0.4V10.4 c0-0.4,0.4-0.6,0.7-0.4l4,2.5C15.3,12.7,15.3,13.3,15,13.5z" />
                </svg>
            )
        },
        {
            id: 'local',
            name: '本地视频',
            icon: <MonitorPlay size={20} color="#ffb11b" />
        }
    ];

    const styles = [
        { id: 'minimal', name: '精简摘要' },
        { id: 'detailed', name: '详细笔记' },
        { id: 'tutorial', name: '教程步骤' },
        { id: 'academic', name: '学术报告' },
        { id: 'xiaohongshu', name: '小红书风' },
        { id: 'life_journal', name: '生活感悟' },
        { id: 'task_oriented', name: '任务导向' },
        { id: 'business', name: '商业简报' },
        { id: 'meeting_minutes', name: '会议纪要' }
    ];

    const formatOptions = [
        { id: 'toc', name: '目录' },
        { id: 'link', name: '原片跳转' },
        { id: 'screenshot', name: '原片截图' },
        { id: 'summary', name: 'AI总结' }
    ];

    return (
        <div className="video-assistant-container">
            {/* Header: 对齐截图 1 */}
            <div className="brand-header">
                <div
                    className="brand-left"
                    onClick={() => {
                        // 如果有上次成功的任务记录，跳转到详情页，否则跳转到最近一个
                        const lastSuccess = history.find(h => h.status === 'SUCCESS');
                        if (lastSuccess) {
                            navigate(`/video-note-detail/${lastSuccess.task_id}`);
                        } else if (history.length > 0) {
                            navigate(`/video-note-detail/${history[0].task_id}`);
                        } else {
                            // 暂时也跳转，如果没有历史则由详情页展示空状态
                            navigate('/video-note-detail/latest');
                        }
                    }}
                    style={{ cursor: 'pointer' }}
                >
                    <Sparkles size={22} className="brand-icon" />
                    <span className="brand-title">AI 视频助手</span>
                </div>
                <div className="header-actions">
                    <div className="header-icon-btn" onClick={() => setShowHistory(!showHistory)} title="查看最近记录">
                        <HistoryIcon size={20} />
                    </div>
                    <div className="header-icon-btn" onClick={() => window.location.href = '/ai-config'} title="配置 AI">
                        <Settings size={20} />
                    </div>
                </div>
            </div>

            <div className="video-assistant-body">
                {/* 顶栏控制按钮 */}
                <div className="top-action-bar">
                    <button className="top-btn" onClick={handleReset}>
                        <RotateCcw size={16} /> 重新生成
                    </button>
                    <button className="top-btn primary" onClick={handleReset}>
                        <Plus size={16} /> 新建笔记
                    </button>
                </div>

                {/* 视频链接 */}
                <div className="config-group">
                    <div className="group-label">
                        <span>视频链接</span>
                        <Info size={14} className="info-icon" />
                    </div>
                    <div className="url-input-card">
                        <div className="platform-btn">
                            <div className="platform-current">
                                {platforms.find(p => p.id === platform)?.icon}
                                <span className="platform-name">{platforms.find(p => p.id === platform)?.name}</span>
                                <span className="chevron-down">▾</span>
                            </div>
                            <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
                                {platforms.map(p => (
                                    <option key={p.id} value={p.id}>{p.name}</option>
                                ))}
                            </select>
                        </div>
                        <input
                            className="video-url-input"
                            placeholder="请输入视频链接..."
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                        />
                    </div>
                </div>

                {/* 模型和风格 */}
                <div className="twin-row">
                    <div className="row-item">
                        <div className="group-label">
                            <span>模型选择</span>
                            <Info size={14} className="info-icon" />
                        </div>
                        <div className="select-wrapper">
                            <select className="standard-select" value={model} onChange={(e) => setModel(e.target.value)}>
                                {models.length > 0 ? models.map(m => (
                                    <option key={m.id} value={m.model_name}>[{m.provider_name}] {m.model_name}</option>
                                )) : (
                                    <option disabled value="">载入中或未配置模型...</option>
                                )}
                            </select>
                        </div>
                    </div>
                    <div className="row-item">
                        <div className="group-label">
                            <span>笔记风格</span>
                            <Info size={14} className="info-icon" />
                        </div>
                        <div className="select-wrapper">
                            <select className="standard-select" value={style} onChange={(e) => setStyle(e.target.value)}>
                                {styles.map(s => (
                                    <option key={s.id} value={s.id}>{s.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>
                </div>

                {/* 视频理解 */}
                <div className="config-group">
                    <div className="group-label">
                        <span>视频理解</span>
                        <Info size={14} className="info-icon" />
                    </div>
                    <div className="vision-card">
                        <div className="vision-toggle-row">
                            <label className="vision-checkbox-label">
                                <input
                                    type="checkbox"
                                    checked={videoUnderstanding}
                                    onChange={(e) => setVideoUnderstanding(e.target.checked)}
                                />
                                <span>启用</span>
                            </label>
                        </div>
                        <div className="vision-params-grid">
                            <div className="vision-param">
                                <label>采样间隔 (秒)</label>
                                <input
                                    type="number"
                                    value={interval}
                                    onChange={(e) => setInterval(parseInt(e.target.value) || 4)}
                                />
                            </div>
                            <div className="vision-param">
                                <label>拼图尺寸 (列 x 行)</label>
                                <div className="size-inputs">
                                    <input
                                        type="number"
                                        value={gridSize[0]}
                                        onChange={(e) => setGridSize([parseInt(e.target.value) || 3, gridSize[1]])}
                                    />
                                    <span>x</span>
                                    <input
                                        type="number"
                                        value={gridSize[1]}
                                        onChange={(e) => setGridSize([gridSize[0], parseInt(e.target.value) || 3])}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {showAlert && (
                    <div className="vision-hint-box">
                        <div className="hint-main">
                            <AlertCircle size={14} className="hint-icon" />
                            <span>提示：视频理解功能必须使用多模态模型。</span>
                        </div>
                        <button className="hint-close" onClick={() => setShowAlert(false)}><X size={14} /></button>
                    </div>
                )}

                {/* 笔记格式 */}
                <div className="config-group">
                    <div className="group-label">
                        <span>笔记格式</span>
                        <Info size={14} className="info-icon" />
                    </div>
                    <div className="format-tags">
                        {formatOptions.map(opt => (
                            <label key={opt.id} className="format-tag-label">
                                <input
                                    type="checkbox"
                                    checked={formats.includes(opt.id)}
                                    onChange={() => handleFormatChange(opt.id)}
                                />
                                <span className="checkbox-box"></span>
                                <span className="tag-text">{opt.name}</span>
                            </label>
                        ))}
                    </div>
                </div>

                {/* 备注 */}
                <div className="config-group">
                    <div className="group-label">
                        <span>备注</span>
                        <Info size={14} className="info-icon" />
                    </div>
                    <textarea
                        className="notes-textarea"
                        placeholder="笔记需要罗列出 xxx 关键点..."
                        value={extras}
                        onChange={(e) => setExtras(e.target.value)}
                    />
                </div>

                {/* 提交按钮 */}
                {!taskId && (
                    <button className="action-submit-btn" onClick={handleGenerate} disabled={loading}>
                        {loading ? <Loader2 className="animate-spin" size={20} /> : <Sparkles size={20} />}
                        <span>{loading ? '正在生成中...' : '立即生成笔记'}</span>
                    </button>
                )}

                {taskId && (
                    <div className="task-running-card">
                        <div className="running-header">
                            <div className="spinner-mini"></div>
                            <span>任务已提交，系统正在极速处理...</span>
                        </div>
                        <button className="view-detail-btn" onClick={() => window.location.href = `/video-note-detail/${taskId}`}>
                            查看笔记详情 <ExternalLink size={14} />
                        </button>
                    </div>
                )}
            </div>

            {showHistory && (
                <div className="history-dropdown visible">
                    <div className="history-header">
                        <span>最近任务</span>
                        <button onClick={() => setShowHistory(false)}><X size={14} /></button>
                    </div>
                    <div className="history-list">
                        {history.length > 0 ? history.slice(0, 5).map((item) => (
                            <div key={item.task_id} className="history-item" onClick={() => window.location.href = `/video-note-detail/${item.task_id}`}>
                                <div className="history-item-icon">
                                    {item.status === 'SUCCESS' ? '✅' : item.status === 'FAILED' ? '❌' : '⏳'}
                                </div>
                                <div className="history-item-info">
                                    <div className="history-item-title">{item.video_url?.substring(0, 30)}...</div>
                                    <div className="history-item-meta">
                                        <Clock size={10} /> {item.created_at}
                                    </div>
                                </div>
                                <button
                                    className="history-item-delete-btn"
                                    onClick={(e) => handleDelete(e, item.task_id)}
                                    title="删除记录"
                                >
                                    <Trash2 size={12} />
                                </button>
                            </div>
                        )) : (
                            <div className="history-empty">暂无历史记录</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default VideoAssistant;
