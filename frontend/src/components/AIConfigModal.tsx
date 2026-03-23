import React, { useState, useEffect } from 'react';
import './AIConfigModal.css';

export interface AIConfig {
    apiKey: string;
    baseUrl: string;
    provider?: string;
    model?: string;
    maxTokens?: number;
    temperature?: number;
}

interface ModelVariant {
    id: string;
    name: string;
    description: string;
    tag?: string;
}

interface AIProvider {
    id: string;
    name: string;
    description: string;
    enabled: boolean;
    apiKey: string;
    baseUrl: string;
    icon: string;
    color: string;
    variants: ModelVariant[];
    activeVariantId: string;
}

interface AIConfigModalProps {
    isOpen: boolean;
    onClose: () => void;
}

const AIConfigModal: React.FC<AIConfigModalProps> = ({ isOpen, onClose }) => {
    const [providers, setProviders] = useState<AIProvider[]>([
        {
            id: 'openai',
            name: 'OpenAI',
            description: '业界领先的 GPT 系列模型',
            enabled: false,
            apiKey: '',
            baseUrl: 'https://api.openai.com/v1',
            icon: '🤖',
            color: '#10a37f',
            activeVariantId: 'gpt-4o',
            variants: [
                { id: 'gpt-4o', name: 'GPT-4o', description: '智能与速度的最佳平衡', tag: '推荐' },
                { id: 'gpt-4o-mini', name: 'GPT-4o-Mini', description: '极速且极具性价比', tag: '轻量' },
                { id: 'o1-preview', name: 'O1-Preview', description: '专注逻辑与复杂推理', tag: '强力' },
                { id: 'o1-mini', name: 'O1-Mini', description: '专注逻辑的轻量版本' }
            ]
        },
        {
            id: 'deepseek',
            name: 'DeepSeek',
            description: '国产之光，极致性能与性价比',
            enabled: false,
            apiKey: '',
            baseUrl: 'https://api.deepseek.com',
            icon: '🐳',
            color: '#2b58e6',
            activeVariantId: 'deepseek-chat',
            variants: [
                { id: 'deepseek-chat', name: 'DeepSeek V3', description: '通用对话，语义理解极强', tag: '推荐' },
                { id: 'deepseek-reasoner', name: 'DeepSeek R1', description: '深度推理，媲美 O1', tag: '满血推理' }
            ]
        },
        {
            id: 'claude',
            name: 'Claude',
            description: ' Anthropic 高级推理模型',
            enabled: false,
            apiKey: '',
            baseUrl: 'https://api.anthropic.com/v1',
            icon: '�',
            color: '#d97757',
            activeVariantId: 'claude-3-5-sonnet-latest',
            variants: [
                { id: 'claude-3-5-sonnet-latest', name: 'Claude 3.5 Sonnet', description: '最聪明的模型版本', tag: '推荐' },
                { id: 'claude-3-5-haiku-latest', name: 'Claude 3.5 Haiku', description: '极速响应', tag: '轻量' },
                { id: 'claude-3-opus-latest', name: 'Claude 3 Opus', description: '经典全能版本' }
            ]
        },
        {
            id: 'gemini',
            name: 'Gemini',
            description: 'Google 多模态架构',
            enabled: false,
            apiKey: '',
            baseUrl: '',
            icon: '💎',
            color: '#4a86e8',
            activeVariantId: 'gemini-1.5-flash',
            variants: [
                { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', description: '极速轻量，适合转录', tag: '推荐' },
                { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', description: '超长上下文支持', tag: '超长上下文' }
            ]
        },
        {
            id: '通义千问',
            name: '通义千问',
            description: '阿里通义千问系列',
            enabled: false,
            apiKey: '',
            baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            icon: '🌟',
            color: '#615ced',
            activeVariantId: 'qwen-max',
            variants: [
                { id: 'qwen-max', name: 'Qwen-Max', description: '最强性能', tag: '顶级' },
                { id: 'qwen-plus', name: 'Qwen-Plus', description: '性能与速度平衡', tag: '推荐' },
                { id: 'qwen-turbo', name: 'Qwen-Turbo', description: '超快响应' }
            ]
        },
        {
            id: 'groq',
            name: 'Groq',
            description: '极致低延迟推理',
            enabled: false,
            apiKey: '',
            baseUrl: 'https://api.groq.com/openai/v1',
            icon: '⚡️',
            color: '#f55036',
            activeVariantId: 'llama-3.3-70b-versatile',
            variants: [
                { id: 'llama-3.3-70b-versatile', name: 'Llama 3.3 70B', description: '全能通用', tag: '推荐' },
                { id: 'mixtral-8x7b-32768', name: 'Mixtral 8x7B', description: '混合专家模型' }
            ]
        },
        {
            id: 'ollama',
            name: 'Ollama',
            description: '本地运行开源模型',
            enabled: false,
            apiKey: 'ollama',
            baseUrl: 'http://localhost:11434/v1',
            icon: '🦙',
            color: '#333',
            activeVariantId: 'llama3',
            variants: [
                { id: 'llama3', name: 'Llama 3', description: 'Meta 开源基准', tag: '推荐' },
                { id: 'mistral', name: 'Mistral', description: '高效平衡' },
                { id: 'deepseek-r1:7b', name: 'DeepSeek R1 7B', description: '本地最强推理', tag: '热门' }
            ]
        }
    ]);

    const [selectedId, setSelectedId] = useState<string>('openai');

    useEffect(() => {
        if (isOpen) {
            const saved = localStorage.getItem('ai_models_config_v2'); // Upgrade to v2 config
            if (saved) {
                const parsed = JSON.parse(saved);
                setProviders(prev => prev.map(p => {
                    const savedProvider = parsed[p.id];
                    if (savedProvider) {
                        return {
                            ...p,
                            enabled: savedProvider.enabled,
                            apiKey: savedProvider.apiKey,
                            baseUrl: savedProvider.baseUrl,
                            activeVariantId: savedProvider.activeVariantId || p.activeVariantId
                        };
                    }
                    return p;
                }));
            } else {
                // Fallback to old config if available
                const oldSaved = localStorage.getItem('ai_models_config');
                if (oldSaved) {
                    const parsed = JSON.parse(oldSaved);
                    setProviders(prev => prev.map(p => parsed[p.id] ? { ...p, ...parsed[p.id] } : p));
                }
            }
        }
    }, [isOpen]);

    const handleSave = () => {
        const configToSave = providers.reduce((acc: any, provider) => {
            acc[provider.id] = {
                enabled: provider.enabled,
                apiKey: provider.apiKey,
                baseUrl: provider.baseUrl,
                activeVariantId: provider.activeVariantId
            };
            return acc;
        }, {});
        localStorage.setItem('ai_models_config_v2', JSON.stringify(configToSave));

        onClose();
    };

    const toggleProvider = (id: string) => {
        setProviders(providers.map(p => p.id === id ? { ...p, enabled: !p.enabled } : p));
    };

    const updateProvider = (id: string, updates: Partial<AIProvider>) => {
        setProviders(providers.map(p => p.id === id ? { ...p, ...updates } : p));
    };

    if (!isOpen) return null;

    const currentProvider = providers.find(p => p.id === selectedId)!;

    return (
        <div className="ai-modal-overlay" onClick={onClose}>
            <div className="ai-modal-content" onClick={e => e.stopPropagation()}>
                <div className="ai-modal-sidebar">
                    <div className="sidebar-header">
                        <h4>模型选择</h4>
                    </div>
                    <div className="provider-list">
                        {providers.map(provider => (
                            <div
                                key={provider.id}
                                className={`provider-item ${selectedId === provider.id ? 'active' : ''}`}
                                onClick={() => setSelectedId(provider.id)}
                            >
                                <span className="provider-icon" style={{ backgroundColor: provider.color }}>{provider.icon}</span>
                                <div className="provider-info">
                                    <span className="provider-title">{provider.name}</span>
                                    <span className="provider-status">{provider.enabled ? '已启用' : '未启用'}</span>
                                </div>
                                <div className={`status-dot ${provider.enabled ? 'online' : 'offline'}`}></div>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="ai-modal-main">
                    <div className="ai-modal-header">
                        <div className="header-title">
                            <h3>{currentProvider.name} 配置</h3>
                            <div className={`active-badge ${currentProvider.enabled ? 'enabled' : 'disabled'}`}>
                                {currentProvider.enabled ? '服务运行中' : '服务已禁用'}
                            </div>
                        </div>
                        <button className="ai-modal-close" onClick={onClose}>✕</button>
                    </div>

                    <div className="ai-modal-body">
                        <div className="config-banner" style={{ background: `${currentProvider.color}10`, borderLeft: `4px solid ${currentProvider.color}` }}>
                            <p>{currentProvider.description}</p>
                        </div>

                        <div className="form-section">
                            <h4 className="section-title">详细模型选择</h4>
                            <div className="variant-grid">
                                {currentProvider.variants.map(variant => (
                                    <div
                                        key={variant.id}
                                        className={`variant-card ${currentProvider.activeVariantId === variant.id ? 'active' : ''}`}
                                        onClick={() => updateProvider(currentProvider.id, { activeVariantId: variant.id })}
                                    >
                                        <div className="variant-card-header">
                                            <span className="variant-name">{variant.name}</span>
                                            {variant.tag && <span className="variant-tag">{variant.tag}</span>}
                                        </div>
                                        <p className="variant-desc">{variant.description}</p>
                                        <div className="variant-check">
                                            <div className="check-dot"></div>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <h4 className="section-title">服务接入配置</h4>
                            <div className="toggle-row">
                                <label>启用此服务</label>
                                <div
                                    className={`toggle-switch ${currentProvider.enabled ? 'on' : 'off'}`}
                                    onClick={() => toggleProvider(currentProvider.id)}
                                >
                                    <div className="switch-handle"></div>
                                </div>
                            </div>

                            <div className="input-grid">
                                <div className="ai-form-group">
                                    <label>API Key</label>
                                    <input
                                        type="password"
                                        placeholder="请输入你的 API Key"
                                        value={currentProvider.apiKey}
                                        onChange={e => updateProvider(currentProvider.id, { apiKey: e.target.value })}
                                    />
                                </div>

                                <div className="ai-form-group">
                                    <label>Base URL (API 代理地址)</label>
                                    <input
                                        type="text"
                                        placeholder="https://..."
                                        value={currentProvider.baseUrl}
                                        onChange={e => updateProvider(currentProvider.id, { baseUrl: e.target.value })}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="ai-modal-footer">
                        <div className="footer-info">
                            已选中: <strong>{currentProvider.variants.find(v => v.id === currentProvider.activeVariantId)?.name}</strong>
                        </div>
                        <div className="footer-actions">
                            <button className="ai-btn-cancel" onClick={onClose}>取消</button>
                            <button className="ai-btn-save" onClick={handleSave}>完成配置</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AIConfigModal;
