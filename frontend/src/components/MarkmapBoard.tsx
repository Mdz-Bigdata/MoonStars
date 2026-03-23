import React, { useState, useRef } from 'react';
import MarkmapView from './MarkmapView';
import type { MarkmapViewHandle } from './MarkmapView';
import { createPortal } from 'react-dom';

interface MarkmapBoardProps {
    markdown: string;
    title?: string;
}

const MarkmapBoard: React.FC<MarkmapBoardProps> = ({ markdown, title }) => {
    const [isFullscreen, setIsFullscreen] = useState(false);
    const viewRef = useRef<MarkmapViewHandle>(null);
    const fullscreenViewRef = useRef<MarkmapViewHandle>(null);

    const toggleFullscreen = () => {
        const newStatus = !isFullscreen;
        setIsFullscreen(newStatus);
        if (newStatus) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
        // 由于布局变化，可能需要重绘
        setTimeout(() => {
            (newStatus ? fullscreenViewRef : viewRef).current?.fitView();
        }, 300);
    };

    const handleReset = () => {
        (isFullscreen ? fullscreenViewRef : viewRef).current?.fitView();
    };

    return (
        <div className="markmap-board-container">
            <div className="component-header">
                <div className="component-type-tag">
                    💎 AI 个人知识资产
                </div>
                {title && <div className="component-title">{title}</div>}
                <div className="component-actions">
                    <button className="component-action-btn secondary" onClick={handleReset}>
                        居中复位
                    </button>
                    <button className="component-action-btn" onClick={toggleFullscreen}>
                        全屏展示
                    </button>
                </div>
            </div>

            <div className="markmap-board-body">
                <MarkmapView ref={viewRef} markdown={markdown} style={{ height: '400px' }} />
            </div>

            {isFullscreen && createPortal(
                <div className="markmap-fullscreen-overlay" onClick={toggleFullscreen}>
                    <div className="markmap-fullscreen-content" onClick={e => e.stopPropagation()}>
                        <div className="fullscreen-header">
                            <div className="header-left">
                                <span className="header-icon">💎</span>
                                <span className="fullscreen-title">{title || 'AI 个人知识资产'}</span>
                            </div>
                            <div className="header-actions">
                                <button className="component-action-btn secondary mr-sm" onClick={handleReset}>
                                    居中复位
                                </button>
                                <button className="close-btn" onClick={toggleFullscreen}>✕</button>
                            </div>
                        </div>
                        <div className="fullscreen-body">
                            <MarkmapView ref={fullscreenViewRef} markdown={markdown} style={{ height: 'calc(100vh - 120px)' }} />
                        </div>
                        <div className="fullscreen-footer">
                            按 ESC 或点击背景关闭
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </div>
    );
};

export default MarkmapBoard;
