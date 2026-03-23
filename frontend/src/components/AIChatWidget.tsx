import React, { useState, useRef, useEffect } from 'react'
import { chatWithArticle } from '../services/api'
import './AIChatWidget.css'

interface Message {
    role: 'user' | 'assistant'
    content: string
}

interface AIChatWidgetProps {
    articleId: string
    onClose?: () => void
}

const MODELS = [
    { id: 'deepseek/deepseek-chat', name: 'DeepSeek V3' },
    { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet' },
    { id: 'openai/gpt-4o-mini', name: 'GPT-4o Mini' },
    { id: 'google/gemini-pro-1.5', name: 'Gemini 1.5 Pro' },
]

const AIChatWidget: React.FC<AIChatWidgetProps> = ({ articleId, onClose }) => {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [selectedModel, setSelectedModel] = useState(MODELS[0].id)
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [messages])

    const handleSend = async () => {
        if (!input.trim() || loading) return

        const userMessage: Message = { role: 'user', content: input }
        setMessages(prev => [...prev, userMessage])
        setInput('')
        setLoading(true)

        try {
            const resp = await chatWithArticle(articleId, {
                message: input,
                history: messages,
                model: selectedModel
            })

            setMessages(prev => [...prev, { role: 'assistant', content: resp.answer }])
        } catch (error) {
            setMessages(prev => [...prev, { role: 'assistant', content: '抱歉，对话服务暂时不可用，请检查网络或 API 配置。' }])
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="ai-chat-widget widget">
            <div className="widget-header">
                <div className="header-title">
                    <span className="icon">💬</span>
                    <h3>AI 助手对话</h3>
                </div>
                <select
                    className="model-selector"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                >
                    {MODELS.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                </select>
                {onClose && (
                    <button className="close-btn" onClick={onClose}>×</button>
                )}
            </div>

            <div className="chat-messages" ref={scrollRef}>
                {messages.length === 0 && (
                    <div className="empty-state">
                        <p>你可以问我关于这篇文章的任何问题，比如：</p>
                        <ul>
                            <li onClick={() => setInput('这篇文章的核心观点是什么？')}>这篇文章的核心观点是什么？</li>
                            <li onClick={() => setInput('作者对这个技术的建议是什么？')}>作者对这个技术的建议是什么？</li>
                        </ul>
                    </div>
                )}
                {messages.map((m, i) => (
                    <div key={i} className={`message-bubble ${m.role}`}>
                        <div className="bubble-content">{m.content}</div>
                    </div>
                ))}
                {loading && (
                    <div className="message-bubble assistant loading">
                        <div className="loading-dots">
                            <span></span><span></span><span></span>
                        </div>
                    </div>
                )}
            </div>

            <div className="chat-input-area">
                <input
                    type="text"
                    placeholder="向 AI 提问..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                />
                <button className="send-btn" onClick={handleSend} disabled={loading || !input.trim()}>
                    发送
                </button>
            </div>
        </div>
    )
}

export default AIChatWidget
