import React, { useState } from 'react'
import './plugin-market.css'

interface Plugin {
    id: string
    name: string
    publisher: string
    description: string
    installs: string
    rating: number
    icon: string
    category: string
}

const PluginMarket: React.FC = () => {
    const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null)

    // 模拟数据
    const plugins: Plugin[] = [
        {
            id: 'dev-containers',
            name: 'Dev Containers',
            publisher: 'Microsoft',
            description: 'Open any folder or repository inside a Docker container and take advantage of Visual Studio Code\'s full feature set.',
            installs: '36.1M',
            rating: 4.5,
            icon: '📦',
            category: 'Other'
        },
        {
            id: 'python',
            name: 'Python',
            publisher: 'Microsoft',
            description: 'A performant, feature-rich language server for Python developers.',
            installs: '110M',
            rating: 4.8,
            icon: '🐍',
            category: 'Programming'
        },
        {
            id: 'gitlens',
            name: 'GitLens — Git supercharged',
            publisher: 'GitKraken',
            description: 'Supercharge Git within VS Code — Visualize code authorship at a glance.',
            installs: '46.8M',
            rating: 3.5,
            icon: '🌿',
            category: 'Other'
        }
    ]

    return (
        <div className="market-page">
            <div className="market-sidebar">
                <div className="market-search">
                    <input type="text" placeholder="在应用商店中搜索扩展" className="input-sm w-full" />
                </div>

                <div className="market-section">
                    <div className="section-header">已安装 <span className="badge">32</span></div>
                    {plugins.slice(0, 1).map(p => (
                        <div key={p.id} className={`plugin-card ${selectedPlugin?.id === p.id ? 'active' : ''}`} onClick={() => setSelectedPlugin(p)}>
                            <div className="plugin-icon-sm">{p.icon}</div>
                            <div className="plugin-info-sm">
                                <strong>{p.name}</strong>
                                <p>{p.publisher}</p>
                            </div>
                        </div>
                    ))}
                </div>

                <div className="market-section">
                    <div className="section-header">推荐 <span className="badge">8</span></div>
                    {plugins.map(p => (
                        <div key={p.id} className={`plugin-card ${selectedPlugin?.id === p.id ? 'active' : ''}`} onClick={() => setSelectedPlugin(p)}>
                            <div className="plugin-icon-sm">{p.icon}</div>
                            <div className="plugin-info-sm">
                                <strong>{p.name}</strong>
                                <p>{p.publisher} · {p.installs}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="market-content">
                {selectedPlugin ? (
                    <div className="plugin-detail">
                        <div className="detail-header">
                            <div className="detail-icon">{selectedPlugin.icon}</div>
                            <div className="detail-main-info">
                                <h1>{selectedPlugin.name}</h1>
                                <p className="publisher-line">
                                    <span className="publisher">{selectedPlugin.publisher}</span>
                                    <span className="verified">✓</span>
                                    <span className="installs">| {selectedPlugin.installs}</span>
                                    <span className="rating">| {selectedPlugin.rating} ⭐</span>
                                </p>
                                <p className="detail-desc">{selectedPlugin.description}</p>
                                <div className="detail-actions">
                                    <button className="btn btn-primary btn-sm">安装</button>
                                    <button className="btn btn-ghost btn-sm">自动更新</button>
                                </div>
                            </div>
                        </div>

                        <div className="detail-tabs">
                            <span className="active">细节</span>
                            <span>功能</span>
                        </div>

                        <div className="detail-body">
                            <h2>Visual Studio Code {selectedPlugin.name}</h2>
                            <p>
                                The {selectedPlugin.name} extension lets you use a specialized environment.
                                Whether you deploy locally or to the cloud, this {selectedPlugin.category} extension provides
                                a great development environment because you can:
                            </p>
                            <ul>
                                <li>Develop with a consistent, easily reproducible toolchain</li>
                                <li>Quickly swap between different, separate development environments</li>
                            </ul>
                        </div>
                    </div>
                ) : (
                    <div className="empty-state">
                        <p>选择一个扩展以查看详细信息</p>
                    </div>
                )}
            </div>
        </div>
    )
}

export default PluginMarket
