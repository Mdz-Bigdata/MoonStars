import React, { useState } from 'react';
import MarkmapView from './MarkmapView';

interface QuickSummaryPanelProps {
    summary: string;
    mindmapMarkdown: string;
}

const QuickSummaryPanel: React.FC<QuickSummaryPanelProps> = ({ summary, mindmapMarkdown }) => {
    const [isMindmapExpanded, setIsMindmapExpanded] = useState(true);

    return (
        <section className="widget widget-quick-summary">
            <h3 className="widget-title">文章精华</h3>

            <div className="summary-card">
                <div className="summary-header">
                    <span className="summary-icon">✨</span>
                    <span className="summary-label">核心总结</span>
                </div>
                <p className="summary-text">{summary}</p>
            </div>

            <div className="mindmap-widget-section">
                <div className="summary-header" onClick={() => setIsMindmapExpanded(!isMindmapExpanded)} style={{ cursor: 'pointer' }}>
                    <span className="summary-icon">💎</span>
                    <span className="summary-label">AI 个人知识资产</span>
                    <span className="expand-trigger">{isMindmapExpanded ? '▼' : '▶'}</span>
                </div>

                {isMindmapExpanded && (
                    <div className="mindmap-widget-container asset-view">
                        <div className="asset-tag">AI Powered</div>
                        <MarkmapView markdown={mindmapMarkdown} />
                    </div>
                )}
            </div>
        </section>
    );
};

export default QuickSummaryPanel;
