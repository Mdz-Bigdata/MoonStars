/**
 * URL 转换表单组件
 * 支持单篇和批量转换
 */
import React, { useState } from 'react'
import { convertArticle, batchConvertArticles } from '../services/api'
import api from '../services/api'
import type { BatchConvertResponse } from '../types'
import './url-converter.css'

interface UrlConverterProps {
    onSuccess?: () => void
}

const UrlConverter: React.FC<UrlConverterProps> = ({ onSuccess }) => {
    const [mode, setMode] = useState<'single' | 'batch'>('single')
    const [singleUrl, setSingleUrl] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [batchUrls, setBatchUrls] = useState('')
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [columns, setColumns] = useState<any[]>([])
    const [selectedColumn, setSelectedColumn] = useState('')

    React.useEffect(() => {
        const fetchCols = async () => {
            try {
                const res = await api.get('/columns')
                setColumns(res.data.items)
            } catch (err) {
                console.error('Failed to fetch columns', err)
            }
        }
        fetchCols()
    }, [])

    const handleSingleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!singleUrl.trim()) {
            setError('请输入文章 URL')
            return
        }

        setLoading(true)
        setError(null)
        setResult(null)

        try {
            const article = await convertArticle(singleUrl.trim(), selectedColumn || undefined, undefined, password.trim() || undefined)
            setResult(`✅ 转换成功！文章《${article.title}》已创建`)
            setSingleUrl('')
            setPassword('')
            if (onSuccess) onSuccess()
        } catch (err: any) {
            if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
                setError('转换超时：该文档较为庞大（正在后台继续处理），请 5-10 分钟后在文章列表中查看')
            } else {
                setError(err.response?.data?.detail || '转换失败，请检查 URL 是否正确')
            }
        } finally {
            setLoading(false)
        }
    }

    const handleBatchSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        const urls = batchUrls
            .split('\n')
            .map(url => url.trim())
            .filter(url => url.length > 0)

        if (urls.length === 0) {
            setError('请输入至少一个 URL')
            return
        }

        setLoading(true)
        setError(null)
        setResult(null)

        try {
            const response: BatchConvertResponse = await batchConvertArticles(urls)
            setResult(
                `✅ 批量转换完成！\n成功: ${response.success_count} 篇\n失败: ${response.failed_count} 篇`
            )
            setBatchUrls('')
            if (onSuccess) onSuccess()
        } catch (err: any) {
            setError(err.response?.data?.detail || '批量转换失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="url-converter">
            <div className="url-converter__tabs">
                <button
                    className={`url-converter__tab ${mode === 'single' ? 'active' : ''}`}
                    onClick={() => setMode('single')}
                >
                    单篇转换
                </button>
                <button
                    className={`url-converter__tab ${mode === 'batch' ? 'active' : ''}`}
                    onClick={() => setMode('batch')}
                >
                    批量转换
                </button>
            </div>

            {mode === 'single' ? (
                <form onSubmit={handleSingleSubmit} className="url-converter__form">
                    <div className="url-converter__input-group">
                        <input
                            type="text"
                            className="input"
                            placeholder="粘贴文章 URL（支持公众号、飞书、语雀）"
                            value={singleUrl}
                            onChange={(e) => setSingleUrl(e.target.value)}
                            disabled={loading}
                        />
                        <div className="password-input-wrapper">
                            <input
                                type={showPassword ? "text" : "password"}
                                className="input input--password"
                                placeholder="访问密码（可选）"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                disabled={loading}
                            />
                            <button
                                type="button"
                                className="password-toggle-btn"
                                onClick={() => setShowPassword(!showPassword)}
                                title={showPassword ? "隐藏密码" : "显示密码"}
                            >
                                {showPassword ? '🙈' : '👁️'}
                            </button>
                        </div>
                        <select
                            className="input select-column"
                            value={selectedColumn}
                            onChange={(e) => setSelectedColumn(e.target.value)}
                            disabled={loading}
                        >
                            <option value="">-- 选择技术专栏 (可选) --</option>
                            {columns.map(col => (
                                <option key={col.id} value={col.id}>
                                    {col.is_free ? '免费' : '付费'}-{col.name}
                                </option>
                            ))}
                        </select>
                    </div>
                    <button
                        type="submit"
                        className="btn btn-primary btn-lg"
                        disabled={loading}
                    >
                        {loading ? '转换中...' : '立即转换'}
                    </button>
                </form>
            ) : (
                <form onSubmit={handleBatchSubmit} className="url-converter__form">
                    <textarea
                        className="textarea"
                        placeholder="每行输入一个 URL&#10;例如：&#10;https://mp.weixin.qq.com/s/xxxxx&#10;https://xxx.feishu.cn/docs/xxxxx"
                        value={batchUrls}
                        onChange={(e) => setBatchUrls(e.target.value)}
                        disabled={loading}
                        rows={6}
                    />
                    <button
                        type="submit"
                        className="btn btn-primary btn-lg"
                        disabled={loading}
                    >
                        {loading ? '批量转换中...' : '开始批量转换'}
                    </button>
                </form>
            )}

            {result && (
                <div className="url-converter__result url-converter__result--success">
                    {result}
                </div>
            )}

            {error && (
                <div className="url-converter__result url-converter__result--error">
                    ❌ {error}
                </div>
            )}
        </div>
    )
}

export default UrlConverter
