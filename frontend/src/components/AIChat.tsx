import React, { useState, useEffect, useRef } from 'react';
import { chatWithArticle, getAiSummary } from '../services/api';
import ReactMarkdown from 'react-markdown';
import AIConfigModal from './AIConfigModal';
import type { AIConfig } from './AIConfigModal';

interface Message {
    role: 'user' | 'assistant';
    content: string;
}

interface AIChatProps {
    articleId: string;
    articleTitle: string;
}

const AIChat: React.FC<AIChatProps> = ({ articleId, articleTitle }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [isConfigOpen, setIsConfigOpen] = useState(false);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [selectedProvider, setSelectedProvider] = useState('deepseek');
    const [selectedModel, setSelectedModel] = useState('deepseek-chat');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // NOTE: 分层模型结构 - 供应商 -> 模型列表
    const providers = [
        {
            key: 'deepseek',
            name: 'DeepSeek',
            icon: '🔍',
            models: [
                { key: 'deepseek-chat', name: 'deepseek-chat' },
                { key: 'deepseek-reasoner', name: 'deepseek-reasoner' },
                { key: 'deepseek-v3.2', name: 'DeepSeek-V3.2' }
            ]
        },
        {
            key: 'claude',
            name: 'Claude',
            icon: '🧠',
            models: [
                { key: 'claude-opus-4.5', name: 'claude-opus-4-5' },
                { key: 'claude-sonnet-4.5', name: 'claude-sonnet-4-5' },
                { key: 'claude-haiku-4.5', name: 'claude-haiku-4-5' }
            ]
        },
        {
            key: 'openai',
            name: 'OpenAI',
            icon: '⚡',
            models: [
                { key: 'gpt-5.2', name: 'GPT-5.2' },
                { key: 'gpt-4o', name: 'GPT-4o' }
            ]
        },
        {
            key: 'google',
            name: 'Gemini',
            icon: '💎',
            models: [
                { key: 'gemini-3-pro', name: 'Gemini 3 Pro' },
                { key: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' }
            ]
        }
    ];

    const currentProvider = providers.find(p => p.key === selectedProvider) || providers[0];
    const currentModel = currentProvider.models.find(m => m.key === selectedModel) || currentProvider.models[0];

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const getCustomConfig = (): AIConfig | null => {
        const saved = localStorage.getItem(`ai_config_${selectedModel}`);
        return saved ? JSON.parse(saved) : null;
    };

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        if (isOpen) {
            scrollToBottom();
        }
    }, [messages, isOpen]);

    const handleSend = async () => {
        if (!input.trim() || loading) return;

        const userMsg: Message = { role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        const currentInput = input;
        setInput('');
        setLoading(true);

        try {
            const config = getCustomConfig();
            const history = messages.map(m => ({ role: m.role, content: m.content }));
            const data = await chatWithArticle(articleId, {
                message: currentInput,
                history,
                model: selectedModel,
                api_key: config?.apiKey || undefined,
                base_url: config?.baseUrl || undefined,
                provider: config?.provider || undefined,
                max_tokens: config?.maxTokens || undefined,
                temperature: config?.temperature || undefined
            });
            setMessages(prev => [...prev, { role: 'assistant', content: data.answer }]);
        } catch (err) {
            setMessages(prev => [...prev, { role: 'assistant', content: '抱歉，对话出错了，请检查您的 API 配置。' }]);
        } finally {
            setLoading(false);
        }
    };

    const handleSummary = async () => {
        if (loading) return;
        setLoading(true);
        setMessages(prev => [...prev, { role: 'user', content: '请帮我总结这篇文章的核心内容。' }]);
        try {
            const config = getCustomConfig();
            const data = await getAiSummary(articleId, {
                model: selectedModel,
                api_key: config?.apiKey || undefined,
                base_url: config?.baseUrl || undefined,
                provider: config?.provider || undefined,
                max_tokens: config?.maxTokens || undefined,
                temperature: config?.temperature || undefined
            });
            setMessages(prev => [...prev, { role: 'assistant', content: data.summary }]);
        } catch (err) {
            setMessages(prev => [...prev, { role: 'assistant', content: '生成总结失败，请检查您的 API 配置。' }]);
        } finally {
            setLoading(false);
        }
    };

    const handleProviderSelect = (providerKey: string) => {
        setSelectedProvider(providerKey);
        // 切换供应商时，默认选中该供应商的第一个模型
        const provider = providers.find(p => p.key === providerKey);
        if (provider && provider.models.length > 0) {
            setSelectedModel(provider.models[0].key);
        }
    };

    const handleModelSelect = (modelKey: string) => {
        setSelectedModel(modelKey);
        setIsDropdownOpen(false);
        // 选择模型后弹出配置框
        setIsConfigOpen(true);
    };

    const selectedModelName = `${currentProvider.name} / ${currentModel.name}`;

    return (
        <>
            <div className={`ai-chat-container ${isOpen ? 'is-open' : ''}`}>
                {!isOpen ? (
                    <button className="ai-chat-trigger" onClick={() => setIsOpen(true)}>
                        <div className="trigger-pulse"></div>
                        <span className="trigger-icon">🤖</span>
                        <span className="trigger-text">AI 助手</span>
                    </button>
                ) : (
                    <div className="ai-chat-window">
                        <div className="chat-header">
                            <div className="header-info">
                                <div className="header-icon-wrapper">
                                    <span className="header-icon">🤖</span>
                                    <span className="status-dot"></span>
                                </div>
                                <div className="header-text">
                                    <span className="header-title">文章 AI 助手</span>
                                    <span className="header-subtitle" title={articleTitle}>
                                        正在讨论: {articleTitle.length > 15 ? articleTitle.substring(0, 15) + '...' : articleTitle}
                                    </span>
                                </div>
                            </div>
                            <div className="header-ops">
                                <button className="settings-btn" onClick={() => setIsConfigOpen(true)} title="配置当前模型">
                                    ⚙️
                                </button>
                                <button className="close-btn" onClick={() => setIsOpen(false)}>✕</button>
                            </div>
                        </div>

                        <div className="chat-toolbar">
                            <div className="custom-dropdown" ref={dropdownRef}>
                                <div
                                    className={`dropdown-selected ${isDropdownOpen ? 'open' : ''}`}
                                    onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                                >
                                    <span className="model-icon">{currentProvider.icon}</span>
                                    <span className="model-name">{selectedModelName}</span>
                                    <span className="dropdown-arrow">▼</span>
                                </div>
                                {isDropdownOpen && (
                                    <div className="dropdown-options dropdown-layered">
                                        {/* 左侧：供应商列表 */}
                                        <div className="provider-list">
                                            {providers.map(provider => (
                                                <div
                                                    key={provider.key}
                                                    className={`provider-item ${selectedProvider === provider.key ? 'active' : ''}`}
                                                    onClick={() => handleProviderSelect(provider.key)}
                                                >
                                                    <span className="provider-icon">{provider.icon}</span>
                                                    <span className="provider-name">{provider.name}</span>
                                                </div>
                                            ))}
                                        </div>
                                        {/* 右侧：模型列表 */}
                                        <div className="model-list">
                                            <div className="model-list-header">
                                                {currentProvider.name} 模型
                                            </div>
                                            {currentProvider.models.map(model => (
                                                <div
                                                    key={model.key}
                                                    className={`model-item ${selectedModel === model.key ? 'active' : ''}`}
                                                    onClick={() => handleModelSelect(model.key)}
                                                >
                                                    <span className="model-item-name">{model.name}</span>
                                                    {selectedModel === model.key && <span className="current-badge">正在使用</span>}
                                                    <button
                                                        className="option-settings-btn"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setSelectedModel(model.key);
                                                            setIsConfigOpen(true);
                                                            setIsDropdownOpen(false);
                                                        }}
                                                    >
                                                        ⚙️
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                            <button className="summary-btn" onClick={handleSummary} disabled={loading}>
                                ✨ 全文总结
                            </button>
                        </div>

                        <div className="chat-messages">
                            {messages.length === 0 && (
                                <div className="empty-chat">
                                    <div className="empty-icon">👋</div>
                                    <p>您好！我是您的 AI 阅读助手。您可以点击右上角 ⚙️ 为 <b>{selectedModelName}</b> 配置专属的 API Key。</p>
                                    <div className="suggested-actions">
                                        <button onClick={handleSummary}>总结全文关键点</button>
                                        <button onClick={() => setInput('这篇文章主要讲了什么？')}>这篇文章主要讲了什么？</button>
                                    </div>
                                </div>
                            )}
                            {messages.map((m, i) => (
                                <div key={i} className={`message-item ${m.role}`}>
                                    <div className="avatar">{m.role === 'assistant' ? '🤖' : '👤'}</div>
                                    <div className="message-bubble">
                                        <ReactMarkdown>{m.content}</ReactMarkdown>
                                    </div>
                                </div>
                            ))}
                            {loading && (
                                <div className="message-item assistant loading">
                                    <div className="avatar">🤖</div>
                                    <div className="message-bubble">
                                        <div className="typing-indicator">
                                            <span></span><span></span><span></span>
                                        </div>
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        <div className="chat-input-area">
                            <textarea
                                placeholder="想问点什么？(Shift + Enter 换行)"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleSend();
                                    }
                                }}
                            />
                            <button
                                className={`send-btn ${input.trim() ? 'active' : ''}`}
                                onClick={handleSend}
                                disabled={loading || !input.trim()}
                            >
                                <svg viewBox="0 0 24 24" width="20" height="20">
                                    <path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                                </svg>
                            </button>
                        </div>
                    </div>
                )}
            </div>

            <AIConfigModal
                isOpen={isConfigOpen}
                onClose={() => setIsConfigOpen(false)}
            />
        </>
    );
};

export default AIChat;
