import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './ai-config-page.css';

interface ProviderConfig {
    id: string;
    name: string;
    icon: string;
    color: string;
    enabled: boolean;
    apiKey: string;
    baseUrl: string;
    activeVariantId: string;
    models?: string[]; // 支持的模型列表
    customParams?: { key: string; value: string }[];
}

interface MCPServer {
    id: string;
    name: string;
    icon: string;
    desc: string;
    local?: boolean;
    installed?: boolean;
    enabled?: boolean;
    config?: string;
}

interface Plugin {
    id: string;
    name: string;
    icon: string;
    desc: string;
    github?: string;
    installed?: boolean;
}

const AIConfigPage: React.FC = () => {
    const navigate = useNavigate();
    const [providers, setProviders] = useState<ProviderConfig[]>([
        { id: 'deepseek', name: 'DeepSeek', icon: '🐳', color: '#3b82f6', enabled: true, apiKey: '', baseUrl: 'https://api.deepseek.com/v1', activeVariantId: 'deepseek-chat', models: ['deepseek-chat', 'deepseek-reasoner'] },
        { id: 'volcengine', name: '火山引擎', icon: '🌋', color: '#ef4444', enabled: false, apiKey: '', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', activeVariantId: 'ep-20240521071306-6p4xk', models: ['ep-20240521071306-6p4xk', 'ep-20240521071306-abcde'] },
        { id: 'claude', name: 'Claude', icon: '🎨', color: '#d97757', enabled: false, apiKey: '', baseUrl: '', activeVariantId: 'claude-3-5-sonnet-20240620', models: ['claude-3-5-sonnet-20240620', 'claude-3-5-haiku-20241022'] },
        { id: 'qwen', name: '通义千问', icon: '☁️', color: '#6366f1', enabled: false, apiKey: '', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', activeVariantId: 'qwen-max', models: ['qwen-max', 'qwen-plus', 'qwen-turbo'] },
        { id: 'openai', name: 'OpenAI', icon: '🤖', color: '#10a37f', enabled: false, apiKey: '', baseUrl: 'https://api.openai.com/v1', activeVariantId: 'gpt-4o', models: ['gpt-4o', 'gpt-4o-mini', 'o1-preview'] },
        { id: 'gemini', name: 'Gemini', icon: '💎', color: '#4285f4', enabled: false, apiKey: '', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/models', activeVariantId: 'gemini-1.5-pro', models: ['gemini-1.5-pro', 'gemini-1.5-flash'] },
        { id: 'ollama', name: 'Ollama', icon: '🦙', color: '#333333', enabled: false, apiKey: 'ollama', baseUrl: 'http://localhost:11434/v1', activeVariantId: 'llama3', models: ['llama3', 'qwen2', 'mistral'] },
    ]);

    const [activeTab, setActiveTab] = useState<'ai' | 'rules_skills' | 'context' | 'mcp' | 'plugins' | 'generic'>('ai');
    const [activeSidebarTab, setActiveSidebarTab] = useState<string>('ai');
    
    // AI 模型页面左侧选中的供应商
    const [selectedProviderId, setSelectedProviderId] = useState<string>('deepseek');
    const [isTesting, setIsTesting] = useState(false);
    const [isFetchingModels, setIsFetchingModels] = useState<Record<string, boolean>>({});
    
    // 密码可见性状态
    const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});

    // MCP View Tab State
    const [mcpViewTab, setMcpViewTab] = useState<'market' | 'installed'>('market');
    const [pluginViewTab, setPluginViewTab] = useState<'market' | 'installed'>('market');

    // Modal 状态
    const [modalConfig, setModalConfig] = useState<{ open: boolean; title: string; content: string; placeholder: string; type: 'json' | 'text'; onConfirm?: (val: string) => void }>({
        open: false,
        title: '',
        content: '',
        placeholder: '',
        type: 'text'
    });

    // 规则与技能开关状态
    const [rulesSwitches, setRulesSwitches] = useState({
        includeAgents: true,
        includeClaude: false
    });

    // MCP 状态
    const [mcpSearch, setMcpSearch] = useState('');
    const [mcpServers, setMcpServers] = useState<MCPServer[]>([
        { id: 'github', name: 'github', icon: '🐙', desc: 'Repository management, file operations, and GitHub API integration', installed: false, enabled: true, config: '{\n  "apiKey": ""\n}' },
        { id: 'figma', name: 'Figma', icon: '🎨', desc: '为 Agent 提供 Figma 文件的布局 and 样式信息，增强它们准确生成设计的能力。', local: true, installed: false, enabled: true, config: '{}' },
        { id: 'thinking', name: 'Sequential Thinking', icon: '🧠', desc: 'Dynamic and reflective problem-solving through thought sequences', local: true, installed: true, enabled: true, config: '{}' },
        { id: 'mysql', name: 'MySQL', icon: '🐬', desc: 'MySQL database integration in Python with configurable access controls and schema inspection', local: true, installed: false, enabled: true, config: '{\n  "host": "localhost",\n  "user": "root"\n}' },
        { id: 'context7', name: 'context7', icon: '📄', desc: 'Context7 MCP pulls up-to-date, version-specific documentation and code examples straight from the source.', local: true, installed: false, enabled: true },
        { id: 'blender', name: 'blender', icon: '🟠', desc: '实现MCP 客户端与Blender的直接连接与交互。', local: true, installed: false, enabled: true },
        { id: 'excel', name: 'Excel', icon: '📊', desc: 'A Model Context Protocol (MCP) server that reads and writes MS Excel data.', local: true, installed: false, enabled: true },
        { id: 'fetch', name: 'Fetch', icon: '🌐', desc: 'Web content fetching and conversion for efficient LLM usage', local: true, installed: true, enabled: true },
        { id: 'gitee', name: 'gitee', icon: '🔴', desc: '提供与Gitee API交互的工具。', local: true, installed: false, enabled: true },
        { id: 'memory', name: 'Memory', icon: '💾', desc: 'Knowledge graph-based persistent memory system', local: true, installed: true, enabled: true },
        { id: 'time', name: 'Time', icon: '⏰', desc: 'Time and timezone conversion capabilities', local: true, installed: true, enabled: true }
    ]);

    // 插件状态
    const [pluginSearch, setPluginSearch] = useState('');
    const [plugins, setPlugins] = useState<Plugin[]>([
        { id: 'mindmap', name: '思维导图', icon: '🧠', desc: '将文章一键转为思维导图', installed: false },
        { id: 'evernote', name: '印象笔记', icon: '🐘', desc: '同步内容到印象笔记', installed: false },
        { id: 'obsidian', name: 'Obsidian', icon: '🟣', desc: 'Obsidian 知识库集成插件，支持双向链接笔记同步。', installed: false },
        { id: 'notion', name: 'Notion', icon: '📓', desc: '连接 Notion 工作区，实现页面数据快速导入与管理。', installed: false },
        { id: 'mark-sharp', name: 'mark-sharp 插件', icon: '🖋️', desc: '高性能 Markdown 解析器，提供卓越的渲染体验。', installed: false },
        { id: 'lim-code', name: 'Lim Code', icon: '💻', desc: '专业代码段管理工具，优化开发者的代码复用流程。', installed: false },
        { id: 'novel-helper', name: 'Andrea Novel Helper (小说助手)', icon: '📖', desc: '为小说创作者提供的全方位辅助工具，涵盖大纲与人物管理。', installed: false },
        { id: 'gen-ai-comp', name: '独立组件（生成式AI组件）', icon: '⚛️', desc: '一套可复用的生成式 AI UI 组件库。', installed: false },
        { id: 'anh-chat', name: 'Anh Chat (小说助手 聊天组件)', icon: '💬', desc: '小说助手的配套聊天组件，提升互动创作体验。', github: 'https://github.com/AndreaFrederica/Roo-Code-Chat', installed: false },
        { id: 'md-siyuaner', name: 'Markdown-SiYuaner', icon: '🏺', desc: '将 Markdown 数据高效转换并集成至思源笔记中。', installed: false },
        { id: 'drawio', name: 'Draw.io Integration', icon: '📐', desc: '在文档中直接嵌入并编辑流程图与图表。', installed: false },
        { id: 'canva', name: 'Canva', icon: '🎨', desc: '集成 Canva 设计工具，快速创建精美的视觉内容。', installed: false },
        { id: 'mutydoc', name: 'MutyDoc – AI Notes', icon: '📓', desc: '智能 AI 笔记增强插件，自动总结、提取核心观点。', installed: false },
        { id: 'md-all-in-one', name: 'markdown-all-in-one', icon: '🚀', desc: 'All-in-one markdown extension for document productivity.', installed: true }
    ]);

    // 从 localStorage 同步插件安装状态
    useEffect(() => {
        const syncPlugins = () => {
            const savedPlugins = localStorage.getItem('installed_plugins')
            if (savedPlugins) {
                try {
                    const installedIds = JSON.parse(savedPlugins)
                    setPlugins(prev => prev.map(p => ({
                        ...p,
                        installed: p.installed || installedIds.includes(p.id)
                    })))
                } catch (e) {
                    console.error('Failed to parse installed plugins', e)
                }
            }
        }
        syncPlugins()
        
        // 监听其他页面的 localStorage 变化
        window.addEventListener('storage', syncPlugins)
        return () => window.removeEventListener('storage', syncPlugins)
    }, [])

    useEffect(() => {
        // Load AI Providers
        const savedProviders = localStorage.getItem('ai_models_config_v2');
        if (savedProviders) {
            try {
                const parsed = JSON.parse(savedProviders);
                if (Array.isArray(parsed)) setProviders(parsed);
            } catch (e) {
                console.error('Failed to parse AI providers config', e);
            }
        }

        // 尝试从后端接口拉取模型列表来更新各供应商的可用模型
        fetch('http://localhost:8000/api/video-model/model_list')
            .then(res => res.json())
            .then(data => {
                if (data && data.data && Array.isArray(data.data)) {
                    // data.data 的结构类似 [{ id: 'xxx', provider_id: 'openai', model_name: 'gpt-4o' }]
                    const modelsByProvider: Record<string, string[]> = {};
                    
                    data.data.forEach((m: any) => {
                        const pid = String(m.provider_id).toLowerCase();
                        if (!modelsByProvider[pid]) {
                            modelsByProvider[pid] = [];
                        }
                        // 避免重复
                        if (!modelsByProvider[pid].includes(m.model_name)) {
                            modelsByProvider[pid].push(m.model_name);
                        }
                    });

                    // 更新 providers 列表
                    setProviders(prevProviders => prevProviders.map(provider => {
                        const pid = provider.id.toLowerCase();
                        if (modelsByProvider[pid] && modelsByProvider[pid].length > 0) {
                            return {
                                ...provider,
                                models: modelsByProvider[pid]
                            };
                        }
                        return provider;
                    }));
                }
            })
            .catch(err => console.error('Failed to fetch models from backend', err));

        // Load MCP Servers
        const savedMCP = localStorage.getItem('mcp_servers_config_v2');
        if (savedMCP) {
            try {
                const parsed = JSON.parse(savedMCP);
                if (Array.isArray(parsed)) setMcpServers(parsed);
            } catch (e) {
                console.error('Failed to parse MCP config', e);
            }
        }

        // Load Plugins
        const savedPlugins = localStorage.getItem('plugins_config_v2');
        if (savedPlugins) {
            try {
                const parsed = JSON.parse(savedPlugins);
                if (Array.isArray(parsed)) setPlugins(parsed);
            } catch (e) {
                console.error('Failed to parse plugins config', e);
            }
        }
    }, []);

    const handleSave = () => {
        localStorage.setItem('ai_models_config_v2', JSON.stringify(providers));
        localStorage.setItem('mcp_servers_config_v2', JSON.stringify(mcpServers));
        localStorage.setItem('plugins_config_v2', JSON.stringify(plugins));
        alert('配置已保存！');
        navigate('/');
    };

    const handleInstallMcp = (id: string) => {
        setMcpServers(prev => prev.map(s => s.id === id ? { ...s, installed: true } : s));
    };

    const handleToggleMcp = (id: string) => {
        setMcpServers(prev => prev.map(s => s.id === id ? { ...s, enabled: !s.enabled } : s));
    };

    const handleUpdateMcpConfig = (id: string, newConfig: string) => {
        setMcpServers(prev => prev.map(s => s.id === id ? { ...s, config: newConfig } : s));
    };

    const fetchModelsForProvider = async (provider: ProviderConfig) => {
        if (!provider.apiKey) return;
        
        setIsFetchingModels(prev => ({ ...prev, [provider.id]: true }));
        try {
            const modelsRes = await fetch('http://localhost:8000/api/video-model/model_list_v2', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: provider.apiKey,
                    base_url: provider.baseUrl,
                    provider_id: provider.id
                })
            });
            const modelsData = await modelsRes.json();
            
            if (modelsData.code === 200 && modelsData.data?.models) {
                const newModels = modelsData.data.models.map((m: any) => m.model_name);
                
                if (newModels.length > 0) {
                    setProviders(prev => prev.map(p => {
                        if (p.id === provider.id) {
                            return {
                                ...p,
                                models: newModels,
                                // 如果当前没有选中的模型，或者选中的模型不在新列表中，则默认选中第一个
                                activeVariantId: (!p.activeVariantId || !newModels.includes(p.activeVariantId)) ? newModels[0] : p.activeVariantId
                            };
                        }
                        return p;
                    }));
                }
            }
        } catch (error) {
            console.error(`Failed to fetch models for ${provider.name}:`, error);
        } finally {
            setIsFetchingModels(prev => ({ ...prev, [provider.id]: false }));
        }
    };

    const handleTestConnection = async (providerId: string) => {
        const provider = providers.find(p => p.id === providerId);
        if (!provider) return;

        setIsTesting(true);
        try {
            // 先测试连通性
            const testRes = await fetch('http://localhost:8000/api/video-provider/test_connectivity_v2', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: provider.apiKey,
                    base_url: provider.baseUrl
                })
            });
            const testData = await testRes.json();
            
            if (testData.code === 200) {
                // 连接成功，自动拉取最新模型列表
                const modelsRes = await fetch('http://localhost:8000/api/video-model/model_list_v2', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        api_key: provider.apiKey,
                        base_url: provider.baseUrl,
                        provider_id: provider.id
                    })
                });
                const modelsData = await modelsRes.json();
                
                if (modelsData.code === 200 && modelsData.data?.models) {
                    const newModels = modelsData.data.models.map((m: any) => m.model_name);
                    
                    setProviders(prev => prev.map(p => {
                        if (p.id === providerId) {
                            return {
                                ...p,
                                models: newModels.length > 0 ? newModels : p.models,
                                activeVariantId: newModels.length > 0 ? newModels[0] : p.activeVariantId
                            };
                        }
                        return p;
                    }));
                    alert(`连接成功！已获取 ${newModels.length} 个模型。`);
                } else {
                    alert('连接成功，但获取模型列表失败。');
                }
            } else {
                alert(`连接失败: ${testData.msg || '未知错误'}`);
            }
        } catch (error) {
            console.error('Test connection error:', error);
            alert('连接测试失败，请检查配置或网络。');
        } finally {
            setIsTesting(false);
        }
    };

    const handleManualAddMCP = (jsonStr: string) => {
        try {
            const parsed = JSON.parse(jsonStr);
            const mcpServersObj = parsed.mcpServers;

            if (!mcpServersObj || typeof mcpServersObj !== 'object') {
                alert('无效的 MCP 配置格式。请确保包含 "mcpServers" 对象。');
                return;
            }

            const newServers: MCPServer[] = [];
            Object.keys(mcpServersObj).forEach(key => {
                const config = mcpServersObj[key];
                // Check if already exists to avoid duplicates
                if (mcpServers.find(s => s.id === key)) return;

                newServers.push({
                    id: key,
                    name: key,
                    icon: '🛠️', // Default icon for manual servers
                    desc: `Manual added: ${config.command || 'unknown'}`,
                    local: true,
                    installed: true,
                    enabled: true,
                    config: JSON.stringify({ [key]: config }, null, 2)
                });
            });

            if (newServers.length > 0) {
                setMcpServers(prev => [...prev, ...newServers]);
                alert(`成功添加 ${newServers.length} 个 MCP 服务器！`);
                setMcpViewTab('installed');
            } else {
                alert('未发现新的服务器或所有服务器已存在。');
            }
        } catch (e) {
            alert('JSON 解析失败，请检查格式。');
            console.error(e);
        }
    };

    const handleInstallPlugin = (id: string) => {
        setPlugins(prev => {
            const newPlugins = prev.map(p => p.id === id ? { ...p, installed: true } : p)
            const installedIds = newPlugins.filter(p => p.installed).map(p => p.id)
            localStorage.setItem('installed_plugins', JSON.stringify(installedIds))
            return newPlugins
        });
    };

    const openCreateModal = (title: string, placeholder: string, type: 'json' | 'text' = 'text', initialContent?: string, onConfirm?: (val: string) => void) => {
        setModalConfig({
            open: true,
            title,
            content: initialContent || (type === 'json' ? '{\n  "mcpServers": {\n    "my-server": {\n      "command": "node",\n      "args": ["path/to/server.js"]\n    }\n  }\n}' : ''),
            placeholder,
            type,
            onConfirm
        });
    };

    const closeModal = () => setModalConfig({ ...modalConfig, open: false });

    return (
        <div className="ai-config-page">
            <div className="config-container">
                {/* 1. 左侧：Sidebar (Refined) */}
                <div className="config-sidebar">
                    <div className="sidebar-brand">
                        <div className="brand-logo">⚙️</div>
                        <div className="brand-text"><h3>系统设置</h3></div>
                    </div>

                    <div className="sidebar-group">
                        <div className="sidebar-section-title">PREFERENCES</div>
                        <div className="sidebar-section-subtitle">偏好与环境配置</div>

                        <div className="sidebar-menu">
                            <button className={`menu-item ${activeSidebarTab === 'mcp' ? 'active' : ''}`} onClick={() => {
                                setActiveSidebarTab('mcp');
                                setActiveTab('mcp');
                            }}>
                                <span className="menu-icon">📁</span> MCP
                            </button>
                            <button className={`menu-item ${activeSidebarTab === 'ai' ? 'active' : ''}`} onClick={() => {
                                setActiveSidebarTab('ai');
                                setActiveTab('ai');
                            }}>
                                <span className="menu-icon">🤖</span> AI 模型
                            </button>
                            <button className={`menu-item ${activeSidebarTab === 'context' ? 'active' : ''}`} onClick={() => {
                                setActiveSidebarTab('context');
                                setActiveTab('context');
                            }}>
                                <span className="menu-icon">📖</span> 上下文
                            </button>
                            <button className={`menu-item ${activeSidebarTab === 'rules_skills' ? 'active' : ''}`} onClick={() => {
                                setActiveSidebarTab('rules_skills');
                                setActiveTab('rules_skills');
                            }}>
                                <span className="menu-icon">✒️</span> 规则和技能
                            </button>
                            <button className={`menu-item ${activeSidebarTab === 'plugins' ? 'active' : ''}`} onClick={() => {
                                setActiveSidebarTab('plugins');
                                setActiveTab('plugins');
                            }}>
                                <span className="menu-icon">🔌</span> 插件市场
                            </button>
                        </div>
                    </div>

                    <div className="sidebar-user-footer">
                        <div className="user-profile">
                            <div className="user-avatar">U</div>
                            <div className="user-info">User Center</div>
                        </div>
                        <div className="footer-home-btn" onClick={() => navigate('/')}>
                            <span>🏠</span> 返回首页
                        </div>
                    </div>
                </div>

                {/* 2. 中间：List Pane */}
                {(activeTab === 'mcp' || activeTab === 'plugins') && (
                    <div className="config-list-pane">
                        <div className="pane-header">
                            <div className="btn-add-provider" style={{ visibility: 'hidden' }}>Dummy</div>
                        </div>
                        <div className="list-scroll-area">
                            <div className="pane-subtitle">{activeTab === 'mcp' ? 'MCP 服务' : '插件库'}</div>
                            <div className="provider-list-cards">
                                <div className={`provider-card-item ${((activeTab === 'mcp' && mcpViewTab === 'market') || (activeTab === 'plugins' && pluginViewTab === 'market')) ? 'active' : ''}`}
                                    onClick={() => {
                                        if (activeTab === 'mcp') setMcpViewTab('market');
                                        if (activeTab === 'plugins') setPluginViewTab('market');
                                    }}>
                                    <div className="provider-card-content">
                                        <div className="provider-card-icon">{activeTab === 'mcp' ? '🏗️' : '🛒'}</div>
                                        <div className="provider-card-title">{activeTab === 'mcp' ? 'MCP 市场' : '官方市场'}</div>
                                    </div>
                                </div>
                                <div className={`provider-card-item ${((activeTab === 'mcp' && mcpViewTab === 'installed') || (activeTab === 'plugins' && pluginViewTab === 'installed')) ? 'active' : ''}`}
                                    onClick={() => {
                                        if (activeTab === 'mcp') setMcpViewTab('installed');
                                        if (activeTab === 'plugins') setPluginViewTab('installed');
                                    }}>
                                    <div className="provider-card-content">
                                        <div className="provider-card-icon">✅</div>
                                        <div className="provider-card-title">已安装</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* 3. 右侧：Detail Pane */}
                <div className="config-detail-pane">
                    <div className="detail-header">
                        <div className="header-info">
                            <h1>
                                {activeTab === 'mcp' ? (mcpViewTab === 'market' ? 'MCP 市场' : '已安装 MCP') :
                                    activeTab === 'rules_skills' ? '规则和技能' :
                                        activeTab === 'context' ? '上下文' :
                                            activeTab === 'plugins' ? '插件市场' : '设置'}
                            </h1>
                        </div>
                        {activeTab === 'mcp' && (
                            <button className="btn-mcp-add" onClick={() => openCreateModal('手动添加 MCP 服务器', '输入 JSON 配置...', 'json', undefined, handleManualAddMCP)}>+ 手动添加</button>
                        )}
                    </div>

                    <div className="detail-scroll-area">
                        <div className="detail-content">
                            {activeTab === 'ai' ? (
                                <div className="ai-models-section" style={{ display: 'flex', height: '100%' }}>
                                    {/* 左侧供应商列表 */}
                                    <div className="provider-sidebar" style={{ width: '240px', borderRight: '1px solid #e2e8f0', padding: '16px 0', overflowY: 'auto' }}>
                                        {providers.map(provider => (
                                            <div 
                                                key={provider.id} 
                                                className={`provider-list-item ${selectedProviderId === provider.id ? 'active' : ''}`}
                                                onClick={() => setSelectedProviderId(provider.id)}
                                                style={{ 
                                                    display: 'flex', 
                                                    alignItems: 'center', 
                                                    gap: '12px', 
                                                    padding: '12px 20px', 
                                                    cursor: 'pointer',
                                                    background: selectedProviderId === provider.id ? '#f1f5f9' : 'transparent',
                                                    borderLeft: selectedProviderId === provider.id ? '3px solid #3b82f6' : '3px solid transparent'
                                                }}
                                            >
                                                <span style={{ fontSize: '20px' }}>{provider.icon}</span>
                                                <span style={{ flex: 1, fontWeight: 500, color: '#334155' }}>{provider.name}</span>
                                                {provider.enabled && <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }}></div>}
                                            </div>
                                        ))}
                                    </div>
                                    
                                    {/* 右侧配置详情 */}
                                    <div className="provider-detail" style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
                                        {providers.filter(p => p.id === selectedProviderId).map(provider => (
                                            <div key={provider.id} className="provider-config-container">
                                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '32px' }}>
                                                    <h2 style={{ margin: 0, fontSize: '24px', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                        {provider.name}
                                                        <a href="#" style={{ color: '#94a3b8', fontSize: '16px' }}>🔗</a>
                                                    </h2>
                                                    <div className={`ui-switch ${provider.enabled ? 'on' : ''}`} onClick={() => {
                                                        setProviders(prev => prev.map(p => p.id === provider.id ? { ...p, enabled: !p.enabled } : p));
                                                    }}>
                                                        <div className="switch-dot"></div>
                                                    </div>
                                                </div>

                                                <div className="config-group" style={{ marginBottom: '32px' }}>
                                                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#1e293b', marginBottom: '16px' }}>Base URL</h3>
                                                    <input 
                                                        type="text" 
                                                        placeholder={`自定义 Base URL (例如: ${provider.baseUrl})`}
                                                        value={provider.baseUrl}
                                                        onChange={e => {
                                                            setProviders(prev => prev.map(p => p.id === provider.id ? { ...p, baseUrl: e.target.value } : p));
                                                        }}
                                                        style={{ width: '100%', padding: '10px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', outline: 'none' }}
                                                    />
                                                    <p style={{ fontSize: '13px', color: '#64748b', marginTop: '8px' }}>如果您使用代理，请在此处填写代理地址。</p>
                                                </div>

                                                <div className="config-group" style={{ marginBottom: '32px' }}>
                                                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#1e293b', marginBottom: '16px' }}>API 密钥</h3>
                                                    <div style={{ display: 'flex', gap: '12px' }}>
                                                        <div style={{ position: 'relative', flex: 1 }}>
                                                            <input 
                                                                type={showPassword[provider.id] ? "text" : "password"}
                                                                placeholder={`输入 ${provider.name} API Key`}
                                                                value={provider.apiKey}
                                                                onChange={e => {
                                                                    setProviders(prev => prev.map(p => p.id === provider.id ? { ...p, apiKey: e.target.value } : p));
                                                                }}
                                                                onBlur={() => {
                                                                    // 当用户填完 API 密钥并离开输入框时，自动触发拉取模型列表
                                                                    if (provider.apiKey) {
                                                                        fetchModelsForProvider(provider);
                                                                    }
                                                                }}
                                                                style={{ width: '100%', padding: '10px 36px 10px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', outline: 'none' }}
                                                            />
                                                            <span 
                                                                style={{ position: 'absolute', right: '12px', top: '10px', color: '#94a3b8', cursor: 'pointer' }}
                                                                onClick={() => setShowPassword(prev => ({ ...prev, [provider.id]: !prev[provider.id] }))}
                                                            >
                                                                {showPassword[provider.id] ? '🙈' : '👁️'}
                                                            </span>
                                                        </div>
                                                        <button 
                                                            className="btn-primary" 
                                                            onClick={() => handleTestConnection(provider.id)}
                                                            disabled={isTesting || !provider.apiKey}
                                                            style={{ padding: '0 20px', borderRadius: '6px', background: '#3b82f6', color: 'white', border: 'none', cursor: 'pointer', opacity: isTesting || !provider.apiKey ? 0.7 : 1 }}
                                                        >
                                                            {isTesting ? '检查中...' : '检查'}
                                                        </button>
                                                    </div>
                                                </div>

                                                <div className="config-group" style={{ marginBottom: '32px' }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                                                        <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#1e293b', margin: 0 }}>
                                                            模型名称
                                                            {isFetchingModels[provider.id] && <span style={{ fontSize: '12px', color: '#3b82f6', marginLeft: '12px', fontWeight: 'normal' }}>正在获取模型列表...</span>}
                                                        </h3>
                                                    </div>
                                                    <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' }}>
                                                        <select 
                                                            value={provider.activeVariantId}
                                                            onChange={e => {
                                                                setProviders(prev => prev.map(p => p.id === provider.id ? { ...p, activeVariantId: e.target.value } : p));
                                                            }}
                                                            disabled={isFetchingModels[provider.id]}
                                                            style={{ width: '100%', padding: '12px 16px', border: 'none', outline: 'none', background: isFetchingModels[provider.id] ? '#f8fafc' : 'white', appearance: 'none', cursor: isFetchingModels[provider.id] ? 'not-allowed' : 'pointer' }}
                                                        >
                                                            <option value="" disabled>请选择模型名称</option>
                                                            {provider.models?.map(model => (
                                                                <option key={model} value={model}>{model}</option>
                                                            ))}
                                                        </select>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : activeTab === 'mcp' ? (
                                <div className="mcp-section">
                                    <div className="mcp-market-header">
                                        <span className={`mcp-tab ${mcpViewTab === 'market' ? 'active' : ''}`} onClick={() => setMcpViewTab('market')}>MCP 市场</span>
                                        <span className={`mcp-tab ${mcpViewTab === 'installed' ? 'active' : ''}`} onClick={() => setMcpViewTab('installed')}>已安装</span>
                                    </div>
                                    <div className="mcp-search-bar">
                                        <span className="search-icon">🔍</span>
                                        <input type="text" placeholder="搜索 MCP 服务" value={mcpSearch} onChange={e => setMcpSearch(e.target.value)} />
                                    </div>
                                    <div className="mcp-list">
                                        {mcpServers
                                            .filter(s => mcpViewTab === 'market' ? true : s.installed)
                                            .filter(s => s.name.toLowerCase().includes(mcpSearch.toLowerCase()))
                                            .map(server => (
                                                <div key={server.id} className="mcp-item">
                                                    <div className="mcp-item-icon">{server.icon}</div>
                                                    <div className="mcp-item-info">
                                                        <div className="mcp-item-name">
                                                            {server.name}
                                                            {server.local && <span className="mcp-tag">Local</span>}
                                                        </div>
                                                        <div className="mcp-item-desc">{server.desc}</div>
                                                    </div>
                                                    <div className="mcp-item-actions">
                                                        {mcpViewTab === 'market' ? (
                                                            <button
                                                                className={`btn-install ${server.installed ? 'installed' : ''}`}
                                                                onClick={() => !server.installed && handleInstallMcp(server.id)}
                                                            >
                                                                {server.installed ? '已安装' : '安装'}
                                                            </button>
                                                        ) : (
                                                            <>
                                                                <button className="btn-mcp-config" onClick={() => openCreateModal(`配置 ${server.name}`, '输入配置 JSON...', 'json', server.config, (val) => handleUpdateMcpConfig(server.id, val))}>
                                                                    配置
                                                                </button>
                                                                <div className={`ui-switch mini ${server.enabled ? 'on' : ''}`} onClick={() => handleToggleMcp(server.id)}>
                                                                    <div className="switch-dot"></div>
                                                                </div>
                                                            </>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                    </div>
                                </div>
                            ) : activeTab === 'plugins' ? (
                                <div className="mcp-section">
                                    <div className="mcp-market-header">
                                        <span className={`mcp-tab ${pluginViewTab === 'market' ? 'active' : ''}`} onClick={() => setPluginViewTab('market')}>商店</span>
                                        <span className={`mcp-tab ${pluginViewTab === 'installed' ? 'active' : ''}`} onClick={() => setPluginViewTab('installed')}>已安装</span>
                                    </div>
                                    <div className="mcp-search-bar">
                                        <span className="search-icon">🔍</span>
                                        <input type="text" placeholder="搜索插件..." value={pluginSearch} onChange={e => setPluginSearch(e.target.value)} />
                                    </div>
                                    <div className="mcp-list">
                                        {plugins
                                            .filter(p => pluginViewTab === 'market' ? true : p.installed)
                                            .filter(p => p.name.toLowerCase().includes(pluginSearch.toLowerCase()))
                                            .map(plugin => (
                                                <div key={plugin.id} className="mcp-item">
                                                    <div className="mcp-item-icon">{plugin.icon}</div>
                                                    <div className="mcp-item-info">
                                                        <div className="mcp-item-name">
                                                            {plugin.name}
                                                            {plugin.github && (
                                                                <a href={plugin.github} target="_blank" rel="noopener noreferrer" className="mcp-tag github-link" title="View on GitHub">
                                                                    GitHub 🔗
                                                                </a>
                                                            )}
                                                        </div>
                                                        <div className="mcp-item-desc">{plugin.desc}</div>
                                                    </div>
                                                    <button
                                                        className={`btn-install ${plugin.installed ? 'installed' : ''}`}
                                                        onClick={() => !plugin.installed && handleInstallPlugin(plugin.id)}
                                                    >
                                                        {plugin.installed ? '已安装' : '安装'}
                                                    </button>
                                                </div>
                                            ))}
                                    </div>
                                </div>
                            ) : activeTab === 'rules_skills' ? (
                                <div className="rules-skills-container">
                                    <section className="rs-section">
                                        <h3>导入设置</h3>
                                        <div className="rs-card toggles-card">
                                            <div className="rs-toggle-item">
                                                <div className="toggle-text">
                                                    <div className="toggle-title">将 AGENTS.md 包含在上下文中</div>
                                                    <div className="toggle-desc">智能体将读取根目录中的 AGENTS.md 文件并将其添加到上下文中。</div>
                                                </div>
                                                <div className={`ui-switch ${rulesSwitches.includeAgents ? 'on' : ''}`} onClick={() => setRulesSwitches({ ...rulesSwitches, includeAgents: !rulesSwitches.includeAgents })}>
                                                    <div className="switch-dot"></div>
                                                </div>
                                            </div>
                                            <div className="rs-toggle-item">
                                                <div className="toggle-text">
                                                    <div className="toggle-title">将 CLAUDE.md 包含在上下文中</div>
                                                    <div className="toggle-desc">智能体将读取根目录中的 CLAUDE.md 和 CLAUDE.local.md 文件并将其添加到上下文中。</div>
                                                </div>
                                                <div className={`ui-switch ${rulesSwitches.includeClaude ? 'on' : ''}`} onClick={() => setRulesSwitches({ ...rulesSwitches, includeClaude: !rulesSwitches.includeClaude })}>
                                                    <div className="switch-dot"></div>
                                                </div>
                                            </div>
                                        </div>
                                    </section>

                                    <section className="rs-section">
                                        <h3>个人规则 <span className="refresh-icon">🔄</span></h3>
                                        <div className="rs-card empty-card">
                                            <div className="card-center-icon">👤</div>
                                            <div className="card-title">个人规则</div>
                                            <div className="card-desc">创建及管理用户自定义规则，TRAE 会在聊天过程中遵循这些... <span className="link">了解更多</span></div>
                                            <button className="btn-rs-create" onClick={() => openCreateModal('创建个人规则', '输入规则描述...')}>+ 创建</button>
                                        </div>
                                    </section>

                                    <section className="rs-section">
                                        <h3>项目规则 <span className="refresh-icon">🔄</span></h3>
                                        <div className="rs-card empty-card">
                                            <div className="card-center-icon">📜</div>
                                            <div className="card-title">项目规则</div>
                                            <div className="card-desc">创建专用于此项目的规则 <span className="link">了解更多</span></div>
                                            <button className="btn-rs-create" onClick={() => openCreateModal('创建项目规则', '输入项目规则...')}>+ 创建</button>
                                        </div>
                                    </section>

                                    <section className="rs-section">
                                        <h3>技能 <span className="refresh-icon">🔄</span></h3>
                                        <p className="rs-section-desc">技能是根据场景触发、确保模型按指令执行的知识集。你可以通过对话的方式，让 AI 帮你创建技能。</p>
                                        <div className="rs-tabs">
                                            <span className="rs-tab active">全局</span>
                                            <span className="rs-tab">项目</span>
                                        </div>
                                        <div className="rs-card empty-card">
                                            <div className="card-center-icon" style={{ color: '#f59e0b' }}>📖</div>
                                            <div className="card-title">全局技能</div>
                                            <div className="card-desc">全局技能在你所有 TRAE 会话和项目中都会生效。</div>
                                            <button className="btn-rs-create" onClick={() => openCreateModal('创建全局技能', '描述此技能的功能...')}>+ 创建</button>
                                        </div>
                                    </section>
                                </div>
                            ) : activeTab === 'context' ? (
                                <div className="context-section">
                                    <h2 className="rules-title">记忆</h2>
                                    <p className="rules-desc">对话中被记住的内容会存储在此处，您也可以在此编辑。</p>
                                    <div className="context-btns">
                                        <button className="btn-open-file">🔗 打开 memory.md</button>
                                    </div>
                                    <textarea className="context-textarea" placeholder="请输入记忆..."></textarea>
                                </div>
                            ) : (
                                <div className="placeholder-section">
                                    <h2>即将推出</h2>
                                    <p>该功能正在开发中...</p>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="detail-footer">
                        <button className="btn-secondary" onClick={() => navigate('/')}>取消</button>
                        <button className="btn-primary" onClick={handleSave}>保存当前配置</button>
                    </div>
                </div>
            </div>

            {/* Modal Component */}
            {modalConfig.open && (
                <div className="config-modal-overlay" onClick={closeModal}>
                    <div className="config-modal-container" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>{modalConfig.title}</h3>
                            <button className="close-btn" onClick={closeModal}>✕</button>
                        </div>
                        <div className="modal-body">
                            <textarea
                                className={`modal-textarea ${modalConfig.type === 'json' ? 'code-font' : ''}`}
                                placeholder={modalConfig.placeholder}
                                value={modalConfig.content}
                                onChange={e => setModalConfig({ ...modalConfig, content: e.target.value })}
                            />
                        </div>
                        <div className="modal-footer">
                            <button className="btn-secondary" onClick={closeModal}>取消</button>
                            <button className="btn-primary" onClick={() => {
                                if (modalConfig.onConfirm) {
                                    modalConfig.onConfirm(modalConfig.content);
                                }
                                alert('已提交配置！');
                                closeModal();
                            }}>确认提交</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AIConfigPage;
