import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getTaskStatus } from '../../services/video-assistant';
import {
    Download,
    FileText,
    Sparkles,
    Image as ImageIcon,
    CheckCircle2,
    Loader2,
    ArrowLeft,
    XCircle
} from 'lucide-react';
import './VideoProgress.css';

const STEPS = [
    { id: 'DOWNLOADING', label: '下载视频/音频', icon: <Download size={20} /> },
    { id: 'TRANSCRIBING', label: '转写为文字', icon: <FileText size={20} /> },
    { id: 'SUMMARIZING', label: 'AI 智能总结', icon: <Sparkles size={20} /> },
    { id: 'POST_PROCESSING', label: '插入原片截图', icon: <ImageIcon size={20} /> },
    { id: 'SUCCESS', label: '完成', icon: <CheckCircle2 size={20} /> }
];

const VideoProgress: React.FC = () => {
    const { taskId } = useParams<{ taskId: string }>();
    const navigate = useNavigate();
    const [status, setStatus] = useState<string>('PARSING');
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!taskId) return;

        const poll = async () => {
            try {
                const response = await getTaskStatus(taskId);
                const data = response.data || response; // 处理 ResponseWrapper 包装
                setStatus(data.status);

                // 根据状态计算进度百分比和当前步骤
                let currentProgress = 0;
                switch (data.status) {
                    case 'PARSING': currentProgress = 5; break;
                    case 'DOWNLOADING': currentProgress = 20; break;
                    case 'TRANSCRIBING': currentProgress = 45; break;
                    case 'SUMMARIZING': currentProgress = 70; break;
                    case 'SAVING':
                    case 'POST_PROCESSING': currentProgress = 90; break;
                    case 'SUCCESS':
                        currentProgress = 100;
                        // 成功后自动跳转到详情页
                        setTimeout(() => {
                            navigate(`/video-note-detail/${taskId}`);
                        }, 1000);
                        break;
                    case 'FAILED':
                        setError(data.message || '生成失败');
                        break;
                }
                setProgress(currentProgress);

                if (data.status !== 'SUCCESS' && data.status !== 'FAILED') {
                    setTimeout(poll, 2000);
                }
            } catch (err) {
                console.error('Polling error:', err);
                setTimeout(poll, 5000);
            }
        };

        poll();
    }, [taskId, navigate]);

    const getCurrentStepIndex = () => {
        if (status === 'SUCCESS') return 5;
        if (status === 'FAILED') return -1;
        if (status === 'PARSING' || status === 'DOWNLOADING') return 0;
        if (status === 'TRANSCRIBING') return 1;
        if (status === 'SUMMARIZING') return 2;
        if (status === 'SAVING' || status === 'POST_PROCESSING') return 3;
        return 0;
    };

    const currentStepIndex = getCurrentStepIndex();

    return (
        <div className="video-progress-page">
            <div className="progress-header">
                <button className="back-btn" onClick={() => navigate('/')}>
                    <ArrowLeft size={20} />
                </button>
                <div className="header-title">
                    <span className="status-dot animate-pulse"></span>
                    生成中...
                </div>
                <div className="brand-badge">AI 视频助手</div>
            </div>

            <div className="progress-container">
                <div className="progress-card">
                    <div className="card-top">
                        <div className="loading-icon-wrapper">
                            {status === 'FAILED' ? (
                                <XCircle size={48} color="#ef4444" />
                            ) : (
                                <Loader2 size={48} className="animate-spin text-blue-500" />
                            )}
                        </div>
                        <h2 className="progress-title">
                            {status === 'FAILED' ? '生成失败' : '正在为您极速生成笔记...'}
                        </h2>
                        {error && <p className="error-message">{error}</p>}
                    </div>

                    <div className="stepper-container">
                        {STEPS.map((step, index) => {
                            const isCompleted = index < currentStepIndex;
                            const isActive = index === currentStepIndex;

                            return (
                                <div key={step.id} className={`step-item ${isCompleted ? 'completed' : ''} ${isActive ? 'active' : ''}`}>
                                    <div className="step-icon-outer">
                                        <div className="step-icon">
                                            {isCompleted ? <CheckCircle2 size={20} /> : step.icon}
                                        </div>
                                        {index < STEPS.length - 1 && <div className="step-line"></div>}
                                    </div>
                                    <span className="step-label">{step.label}</span>
                                </div>
                            );
                        })}
                    </div>

                    <div className="progress-bar-wrapper">
                        <div className="progress-inner">
                            <div
                                className="progress-fill"
                                style={{ width: `${progress}%` }}
                            ></div>
                        </div>
                        <div className="progress-info">
                            <span>已完成 {progress}%</span>
                            <span>预计还需 1-2 分钟</span>
                        </div>
                    </div>

                    <button className="cancel-btn" onClick={() => navigate('/')}>
                        取消生成
                    </button>
                </div>
            </div>
        </div>
    );
};

export default VideoProgress;
