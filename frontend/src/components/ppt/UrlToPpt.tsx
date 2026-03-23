import React, { useState, useCallback, useEffect } from 'react';
import { Download, Loader2, ArrowLeft, Maximize2, ChevronLeft, ChevronRight, X, Zap, Palette, Layers, FileText, Globe } from 'lucide-react';
import { getToken } from '../../services/auth';
import './UrlToPpt.css';

/**
 * PPT 生成任务状态
 */
interface JobStatus {
    id: string;
    status: 'processing' | 'completed' | 'failed';
    progress: number;
    message: string;
    downloadUrl?: string;
}

/**
 * 幻灯片数据结构
 */
interface SlideData {
    id: number;
    type: 'title' | 'content' | 'conclusion' | 'thankyou';
    title: string;
    subtitle?: string;
    points?: string[];
    table?: string;
    fragment_b64?: string;
    mermaid_b64?: string;  // Mermaid 图表的 base64 图片
    visual_type?: string;  // 'mindmap' | 'flowchart' | 'architecture' | 'image'
    theme: {
        primary: string;
        secondary: string;
        background: string;
        text: string;
        accent: string;
    };
}

/**
 * URL 转 PPT 主组件
 * 支持飞书文档和网页 URL 转换为演示文稿
 */
const UrlToPpt: React.FC = () => {
    // 表单状态
    const [urlInput, setUrlInput] = useState('');
    const [promptInput, setPromptInput] = useState('');
    // NOTE: 输入源切换
    const [inputSource, setInputSource] = useState<'url' | 'prompt'>('url');
    const [mode, setMode] = useState<'summarize' | 'convert'>('convert');
    const [theme, setTheme] = useState<'light' | 'dark' | 'corporate'>('light');
    const [maxSlides, setMaxSlides] = useState(20);
    const [language, setLanguage] = useState('zh-CN');
    const [includeImages, setIncludeImages] = useState(true);
    // NOTE: 新增引擎选择和 SD 配置
    const [engine, setEngine] = useState<'standard' | 'ai_visual' | 'hybrid'>('standard');
    const [sdEnabled, setSdEnabled] = useState(false);
    const [sdModel, setSdModel] = useState('sd_xl_base_1.0.safetensors');
    const [sdSteps, setSdSteps] = useState(20);
    const [sdCfg, setSdCfg] = useState(7.0);

    // 生成状态
    const [job, setJob] = useState<JobStatus | null>(null);
    const [slides, setSlides] = useState<SlideData[]>([]);
    const [error, setError] = useState<string | null>(null);

    // 预览状态
    const [showPreview, setShowPreview] = useState(false);
    const [currentSlide, setCurrentSlide] = useState(0);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // 获取幻灯片数据
    const fetchSlides = async (jobId: string) => {
        try {
            const resp = await fetch(`/api/ppt/slides/${jobId}`);
            if (resp.ok) {
                const data = await resp.json();
                setSlides(data.slides || []);
            }
        } catch (err) {
            console.error('Failed to fetch slides:', err);
        }
    };

    // WebSocket 连接
    const connectWebSocket = useCallback((jobId: string) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/api/ppt/ws?jobId=${jobId}`;

        const socket = new WebSocket(wsUrl);

        socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'progress') {
                setJob(message.data);
                if (message.data.status === 'completed') {
                    fetchSlides(jobId);
                    socket.close();
                }
            }
        };

        socket.onerror = () => {
            // 回退到轮询
            const pollInterval = setInterval(async () => {
                try {
                    const res = await fetch(`/api/ppt/status/${jobId}`);
                    const data = await res.json();
                    setJob(data);
                    if (data.status === 'completed' || data.status === 'failed') {
                        if (data.status === 'completed') {
                            fetchSlides(jobId);
                        }
                        clearInterval(pollInterval);
                    }
                } catch (e) {
                    console.error('Polling error:', e);
                }
            }, 2000);
        };

        socket.onclose = () => { };
    }, []);

    // 提交生成请求
    const handleGenerate = async () => {
        setError(null);
        setJob({ id: '', status: 'processing', progress: 0, message: '提交请求中...' });
        setSlides([]);
        setShowPreview(false);

        // NOTE: 根据输入源构建不同的请求体
        let requestBody: Record<string, unknown>;
        const commonOptions = {
            maxSlides,
            language,
            includeImages,
        };
        const sdConfigPayload = sdEnabled ? {
            enabled: true, model: sdModel, steps: sdSteps, cfg: sdCfg, width: 1024, height: 576
        } : undefined;

        if (inputSource === 'prompt') {
            const trimmed = promptInput.trim();
            if (!trimmed) {
                setError('请输入 PPT 主题或描述');
                setJob(null);
                return;
            }
            requestBody = {
                prompt: trimmed,
                mode: 'summarize',
                theme,
                engine,
                options: commonOptions,
                sd_config: sdConfigPayload,
            };
        } else {
            const urls = urlInput.split(/[\n,]+/).map(u => u.trim()).filter(u => u.length > 0);
            if (urls.length === 0) {
                setError('请输入至少一个有效的 URL 地址');
                setJob(null);
                return;
            }
            for (const u of urls) {
                try { new URL(u); } catch {
                    setError(`无效的 URL 格式: ${u}`);
                    setJob(null);
                    return;
                }
            }
            requestBody = {
                urls,
                mode,
                theme,
                engine,
                options: commonOptions,
                sd_config: sdConfigPayload,
            };
        }

        try {
            const token = getToken();
            const response = await fetch('/api/ppt/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || '生成失败');
            }

            const data = await response.json();
            setJob({ id: data.id, status: 'processing', progress: 0, message: '开始生成...' });
            connectWebSocket(data.id);
        } catch (err: any) {
            setError(err.message);
            setJob(null);
        }
    };

    // 下载 PPT
    const handleDownload = () => {
        if (job?.downloadUrl) {
            window.open(job.downloadUrl, '_blank');
        }
    };

    // 重置
    const handleReset = () => {
        setUrlInput('');
        setJob(null);
        setSlides([]);
        setError(null);
        setShowPreview(false);
        setCurrentSlide(0);
    };

    // 键盘导航
    useEffect(() => {
        function handleKeyDown(e: KeyboardEvent) {
            if (!showPreview) return;
            if (e.key === 'ArrowLeft') {
                setCurrentSlide((prev) => Math.max(0, prev - 1));
            } else if (e.key === 'ArrowRight') {
                setCurrentSlide((prev) => Math.min(slides.length - 1, prev + 1));
            } else if (e.key === 'Escape') {
                if (isFullscreen) {
                    setIsFullscreen(false);
                }
            }
        }
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [showPreview, slides.length, isFullscreen]);

    // 渲染单个幻灯片
    const renderSlide = (slide: SlideData, isThumb = false, isFullscreenMode = false) => {
        const containerClass = isThumb
            ? 'slide-thumb'
            : isFullscreenMode
                ? 'slide-fullscreen'
                : 'slide-main';

        const bgColor = `#${slide.theme.background}`;
        const primaryColor = `#${slide.theme.primary}`;
        const textColor = `#${slide.theme.text}`;
        const accentColor = `#${slide.theme.accent}`;

        switch (slide.type) {
            case 'title':
                return (
                    <div className={containerClass} style={{ backgroundColor: primaryColor }}>
                        <div className="slide-title-content">
                            <h1 style={{ color: 'white' }}>{slide.title}</h1>
                            {slide.subtitle && (
                                <>
                                    <div className="slide-divider" style={{ backgroundColor: accentColor }}></div>
                                    <p style={{ color: 'rgba(255,255,255,0.8)' }}>{slide.subtitle}</p>
                                </>
                            )}
                        </div>
                    </div>
                );

            case 'content':
                const hasVisual = slide.fragment_b64 || slide.mermaid_b64;
                const visualLabel = slide.visual_type === 'mindmap' ? '🧠 思维导图'
                    : slide.visual_type === 'flowchart' ? '📊 流程图'
                        : slide.visual_type === 'architecture' ? '🏗️ 架构图'
                            : null;

                return (
                    <div className={`${containerClass} ${hasVisual ? 'has-visual' : ''}`} style={{ backgroundColor: bgColor }}>
                        <div className="slide-header" style={{
                            background: `linear-gradient(135deg, ${primaryColor}, ${accentColor})`
                        }}>
                            <h2 style={{ color: 'white' }}>{slide.title}</h2>
                            {visualLabel && <span className="visual-badge">{visualLabel}</span>}
                        </div>
                        <div className="slide-body">
                            {/* 优先显示视觉元素 */}
                            {slide.mermaid_b64 ? (
                                <div className="slide-visual-container">
                                    <img
                                        src={`data:image/png;base64,${slide.mermaid_b64}`}
                                        alt={visualLabel || 'Diagram'}
                                        className="slide-mermaid-image"
                                    />
                                </div>
                            ) : slide.fragment_b64 ? (
                                <div className="slide-visual-container">
                                    <img
                                        src={`data:image/png;base64,${slide.fragment_b64}`}
                                        alt="Visual Element"
                                        className="slide-fragment-image"
                                    />
                                </div>
                            ) : (
                                <ul className="slide-points">
                                    {slide.points?.map((point, idx) => (
                                        <li key={idx} style={{ color: textColor }}>
                                            <span className="bullet" style={{
                                                background: `linear-gradient(135deg, ${primaryColor}, ${accentColor})`,
                                                WebkitBackgroundClip: 'text',
                                                WebkitTextFillColor: 'transparent'
                                            }}>●</span>
                                            <span>{point}</span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                            {/* 如果有视觉元素，同时显示要点 */}
                            {hasVisual && slide.points && slide.points.length > 0 && (
                                <div className="slide-points-sidebar">
                                    {slide.points.slice(0, 4).map((point, idx) => (
                                        <div key={idx} className="point-item" style={{ color: textColor }}>
                                            <span className="point-number" style={{ color: primaryColor }}>{idx + 1}</span>
                                            <span className="point-text">{point}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                );

            case 'conclusion':
                return (
                    <div className={containerClass} style={{ backgroundColor: bgColor }}>
                        <div className="slide-accent-bar" style={{ backgroundColor: accentColor }}></div>
                        <div className="slide-conclusion-body">
                            <h2 style={{ color: primaryColor }}>{slide.title}</h2>
                            <ol className="slide-conclusion-points">
                                {slide.points?.map((point, idx) => (
                                    <li key={idx} style={{ color: textColor }}>
                                        <span className="number">{idx + 1}.</span>
                                        <span>{point}</span>
                                    </li>
                                ))}
                            </ol>
                        </div>
                    </div>
                );

            case 'thankyou':
                return (
                    <div className={containerClass} style={{ backgroundColor: primaryColor }}>
                        <div className="slide-thankyou-content">
                            <h1 style={{ color: 'white' }}>{slide.title}</h1>
                            <p style={{ color: 'rgba(255,255,255,0.9)' }}>{slide.subtitle}</p>
                            <div className="slide-divider" style={{ backgroundColor: accentColor }}></div>
                            <small style={{ color: 'rgba(255,255,255,0.6)' }}>Generated by URL-to-PPT</small>
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="url-to-ppt-container">
            {/* 全屏预览模式 */}
            {isFullscreen && slides.length > 0 && (
                <div className="fullscreen-overlay">
                    <button className="fullscreen-close" onClick={() => setIsFullscreen(false)}>
                        <X size={24} />
                    </button>
                    <div className="fullscreen-slide">
                        {renderSlide(slides[currentSlide], false, true)}
                    </div>
                    <div className="fullscreen-nav">
                        <button
                            onClick={() => setCurrentSlide(prev => Math.max(0, prev - 1))}
                            disabled={currentSlide === 0}
                        >
                            <ChevronLeft size={24} />
                        </button>
                        <span>{currentSlide + 1} / {slides.length}</span>
                        <button
                            onClick={() => setCurrentSlide(prev => Math.min(slides.length - 1, prev + 1))}
                            disabled={currentSlide === slides.length - 1}
                        >
                            <ChevronRight size={24} />
                        </button>
                    </div>
                </div>
            )}

            {/* 主内容区 */}
            <div className="ppt-main-content">
                {/* 输入表单卡片 */}
                <div className="ppt-form-card">
                    {/* 输入源切换 Tab */}
                    <div className="input-source-tabs">
                        <button
                            className={`source-tab ${inputSource === 'url' ? 'active' : ''}`}
                            onClick={() => setInputSource('url')}
                            disabled={job?.status === 'processing'}
                        >
                            <Globe size={16} />
                            <span>网页 URL</span>
                        </button>
                        <button
                            className={`source-tab ${inputSource === 'prompt' ? 'active' : ''}`}
                            onClick={() => setInputSource('prompt')}
                            disabled={job?.status === 'processing'}
                        >
                            <FileText size={16} />
                            <span>一句话生成</span>
                        </button>
                    </div>

                    {/* 输入区域 */}
                    <div className="form-group">
                        {inputSource === 'url' ? (
                            <textarea
                                value={urlInput}
                                onChange={(e) => setUrlInput(e.target.value)}
                                placeholder="https://example.com/article&#10;支持多个 URL，换行或逗号分隔"
                                className="url-textarea"
                                disabled={job?.status === 'processing'}
                                rows={4}
                            />
                        ) : (
                            <textarea
                                value={promptInput}
                                onChange={(e) => setPromptInput(e.target.value)}
                                placeholder="输入 PPT 主题，例如：&#10;• 人工智能的发展历程和未来趋势&#10;• 2024年新能源汽车行业分析报告&#10;• 企业数字化转型的最佳实践"
                                className="url-textarea prompt-textarea"
                                disabled={job?.status === 'processing'}
                                rows={4}
                            />
                        )}
                    </div>

                    {/* 选项网格 */}
                    <div className="options-grid">
                        <div className="option-item">
                            <label>转换模式</label>
                            <select
                                value={mode}
                                onChange={(e) => setMode(e.target.value as 'summarize' | 'convert')}
                                disabled={job?.status === 'processing'}
                            >
                                <option value="convert">直接转换 - 保留原文结构</option>
                                <option value="summarize">归纳总结 - 提取核心观点</option>
                            </select>
                        </div>
                        <div className="option-item">
                            <label>PPT主题</label>
                            <select
                                value={theme}
                                onChange={(e) => setTheme(e.target.value as any)}
                                disabled={job?.status === 'processing'}
                            >
                                <optgroup label="经典主题">
                                    <option value="light">☀️ 浅色主题</option>
                                    <option value="dark">🌙 深色主题</option>
                                    <option value="corporate">💼 商务主题</option>
                                </optgroup>
                                <optgroup label="现代风格">
                                    <option value="gradient">🌈 渐变风格</option>
                                    <option value="minimalist">⬜ 极简风格</option>
                                    <option value="tech">🔮 科技风格</option>
                                </optgroup>
                                <optgroup label="特色主题">
                                    <option value="creative">🎨 创意多彩</option>
                                    <option value="nature">🌿 自然清新</option>
                                    <option value="business">📊 商务蓝</option>
                                    <option value="elegant">💜 优雅紫</option>
                                </optgroup>
                            </select>
                        </div>
                        <div className="option-item">
                            <label>最大页数: {maxSlides}</label>
                            <input
                                type="number"
                                min="1"
                                max="100"
                                value={maxSlides}
                                onChange={(e) => setMaxSlides(parseInt(e.target.value) || 20)}
                                disabled={job?.status === 'processing'}
                            />
                        </div>
                        <div className="option-item">
                            <label>输出语言</label>
                            <select
                                value={language}
                                onChange={(e) => setLanguage(e.target.value)}
                                disabled={job?.status === 'processing'}
                            >
                                <option value="zh-CN">中文</option>
                                <option value="en-US">English</option>
                            </select>
                        </div>
                    </div>

                    {/* 生成引擎选择 */}
                    <div className="engine-selector">
                        <label className="engine-label">🚀 生成引擎</label>
                        <div className="engine-options">
                            <button
                                className={`engine-option ${engine === 'standard' ? 'active' : ''}`}
                                onClick={() => setEngine('standard')}
                                disabled={job?.status === 'processing'}
                            >
                                <Layers size={18} />
                                <div>
                                    <strong>标准模式</strong>
                                    <small>结构化PPT + Mermaid图表 + 智能配图</small>
                                </div>
                            </button>
                            <button
                                className={`engine-option ${engine === 'ai_visual' ? 'active' : ''}`}
                                onClick={() => setEngine('ai_visual')}
                                disabled={job?.status === 'processing'}
                            >
                                <Zap size={18} />
                                <div>
                                    <strong>AI 视觉模式</strong>
                                    <small>banana-slides 全图式PPT（需配置）</small>
                                </div>
                            </button>
                            <button
                                className={`engine-option ${engine === 'hybrid' ? 'active' : ''}`}
                                onClick={() => setEngine('hybrid')}
                                disabled={job?.status === 'processing'}
                            >
                                <Palette size={18} />
                                <div>
                                    <strong>混合模式</strong>
                                    <small>AI背景 + 结构化文字，美观且可编辑</small>
                                </div>
                            </button>
                        </div>
                    </div>

                    {/* SD 配置面板 */}
                    <div className="sd-config-panel">
                        <label className="checkbox-label">
                            <input
                                type="checkbox"
                                checked={sdEnabled}
                                onChange={(e) => setSdEnabled(e.target.checked)}
                                disabled={job?.status === 'processing'}
                            />
                            <span>🎨 启用 Stable Diffusion AI 生图</span>
                        </label>
                        {sdEnabled && (
                            <div className="sd-params">
                                <div className="sd-param">
                                    <label>模型</label>
                                    <select
                                        value={sdModel}
                                        onChange={(e) => setSdModel(e.target.value)}
                                        disabled={job?.status === 'processing'}
                                    >
                                        <option value="sd_xl_base_1.0.safetensors">SDXL Base 1.0</option>
                                        <option value="v1-5-pruned.safetensors">SD 1.5</option>
                                        <option value="flux1-dev.safetensors">FLUX.1 Dev</option>
                                    </select>
                                </div>
                                <div className="sd-param">
                                    <label>步数: {sdSteps}</label>
                                    <input
                                        type="range"
                                        min={10}
                                        max={50}
                                        value={sdSteps}
                                        onChange={(e) => setSdSteps(parseInt(e.target.value))}
                                        disabled={job?.status === 'processing'}
                                    />
                                </div>
                                <div className="sd-param">
                                    <label>CFG: {sdCfg}</label>
                                    <input
                                        type="range"
                                        min={1}
                                        max={20}
                                        step={0.5}
                                        value={sdCfg}
                                        onChange={(e) => setSdCfg(parseFloat(e.target.value))}
                                        disabled={job?.status === 'processing'}
                                    />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* 包含图片选项 */}
                    <div className="checkbox-group">
                        <label className="checkbox-label">
                            <input
                                type="checkbox"
                                checked={includeImages}
                                onChange={(e) => setIncludeImages(e.target.checked)}
                                disabled={job?.status === 'processing'}
                            />
                            <span>包含网页图片</span>
                        </label>
                    </div>

                    {/* 错误提示 */}
                    {error && (
                        <div className="error-message">
                            {error}
                        </div>
                    )}

                    {/* 提交按钮 */}
                    <button
                        className="generate-button"
                        onClick={handleGenerate}
                        disabled={job?.status === 'processing' || (inputSource === 'url' ? !urlInput.trim() : !promptInput.trim())}
                    >
                        {job?.status === 'processing' ? (
                            <>生成中... <Loader2 className="spin" size={20} /></>
                        ) : (
                            '生成PPT'
                        )}
                    </button>
                </div>

                {/* 进度显示 */}
                {job && job.status === 'processing' && (
                    <div className="progress-card">
                        <div className="progress-circle">
                            <svg className="progress-svg" viewBox="0 0 128 128">
                                <circle cx="64" cy="64" r="56" stroke="#e5e7eb" strokeWidth="8" fill="none" />
                                <circle
                                    cx="64"
                                    cy="64"
                                    r="56"
                                    stroke="#2563eb"
                                    strokeWidth="8"
                                    fill="none"
                                    strokeLinecap="round"
                                    strokeDasharray={`${job.progress * 3.52} 352`}
                                    className="progress-indicator"
                                />
                            </svg>
                            <div className="progress-text">{job.progress}%</div>
                        </div>
                        <p className="progress-message">{job.message}</p>
                    </div>
                )}

                {/* 完成状态 - 显示预览入口 */}
                {job?.status === 'completed' && !showPreview && (
                    <div className="complete-card">
                        <div className="complete-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <h3>生成完成!</h3>
                        <p>{job.message}</p>
                        <div className="complete-actions">
                            <button className="btn-primary" onClick={() => setShowPreview(true)}>
                                预览PPT
                            </button>
                            <button className="btn-secondary" onClick={handleDownload}>
                                <Download size={18} /> 下载PPT
                            </button>
                            <button className="btn-secondary" onClick={handleReset}>
                                重新生成
                            </button>
                        </div>
                    </div>
                )}

                {/* 失败状态 */}
                {job?.status === 'failed' && (
                    <div className="failed-card">
                        <div className="failed-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </div>
                        <h3>生成失败</h3>
                        <p className="error-text">{job.message}</p>
                        <button className="btn-secondary" onClick={handleReset}>
                            重试
                        </button>
                    </div>
                )}

                {/* 预览区域 */}
                {showPreview && slides.length > 0 && (
                    <div className="preview-section">
                        {/* 工具栏 */}
                        <div className="preview-toolbar">
                            <button className="back-button" onClick={() => setShowPreview(false)}>
                                <ArrowLeft size={20} /> 返回
                            </button>
                            <div className="toolbar-actions">
                                <button className="btn-secondary" onClick={() => setIsFullscreen(true)}>
                                    <Maximize2 size={18} /> 全屏预览
                                </button>
                                <button className="btn-primary" onClick={handleDownload}>
                                    <Download size={18} /> 下载PPT
                                </button>
                            </div>
                        </div>

                        {/* 预览主区域 */}
                        <div className="preview-layout">
                            {/* 缩略图列表 */}
                            <div className="thumbnail-list">
                                {slides.map((slide, index) => (
                                    <button
                                        key={slide.id}
                                        className={`thumbnail-item ${index === currentSlide ? 'active' : ''}`}
                                        onClick={() => setCurrentSlide(index)}
                                    >
                                        {renderSlide(slide, true)}
                                        <span className="thumbnail-number">{index + 1}</span>
                                    </button>
                                ))}
                            </div>

                            {/* 大图预览 */}
                            <div className="main-preview">
                                <div className="main-preview-container">
                                    {renderSlide(slides[currentSlide])}
                                </div>

                                {/* 导航控制 */}
                                <div className="preview-nav">
                                    <button
                                        onClick={() => setCurrentSlide(prev => Math.max(0, prev - 1))}
                                        disabled={currentSlide === 0}
                                    >
                                        <ChevronLeft size={24} />
                                    </button>
                                    <span>{currentSlide + 1} / {slides.length}</span>
                                    <button
                                        onClick={() => setCurrentSlide(prev => Math.min(slides.length - 1, prev + 1))}
                                        disabled={currentSlide === slides.length - 1}
                                    >
                                        <ChevronRight size={24} />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default UrlToPpt;
