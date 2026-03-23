/**
 * 文章编辑器页面
 * 支持 Markdown 在线写作，保存草稿和发布
 */
import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import MDEditor from '@uiw/react-md-editor'
import {
    createOriginalArticle,
    updateOriginalArticle,
    publishArticle,
    getArticle,
    getColumns,
    uploadImage
} from '../services/api'
import type { Column } from '../types'
import './article-editor.css'

interface EditorFormData {
    title: string
    content: string
    summary: string
    columnId: string | null
    tagInput: string
    tags: string[]
    coverImage: string
}

const ArticleEditor: React.FC = () => {
    const navigate = useNavigate()
    const { id: articleId } = useParams<{ id: string }>()
    const isEditing = Boolean(articleId)

    const [formData, setFormData] = useState<EditorFormData>({
        title: '',
        content: '',
        summary: '',
        columnId: null,
        tagInput: '',
        tags: [],
        coverImage: ''
    })

    const [columns, setColumns] = useState<Column[]>([])
    const [saving, setSaving] = useState(false)
    const [publishing, setPublishing] = useState(false)
    const [showPublishModal, setShowPublishModal] = useState(false)
    const [publishColumnId, setPublishColumnId] = useState<string | null>(null)
    const [lastSaved, setLastSaved] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)
    const [uploading, setUploading] = useState(false)
    const imageInputRef = React.useRef<HTMLInputElement>(null)
    const coverInputRef = React.useRef<HTMLInputElement>(null)

    // 加载专栏列表
    useEffect(() => {
        const loadColumns = async () => {
            try {
                const res = await getColumns()
                setColumns(res.items || res as unknown as Column[])
            } catch (err) {
                console.error('加载专栏失败:', err)
            }
        }
        loadColumns()
    }, [])

    // 编辑模式：加载文章内容
    useEffect(() => {
        if (!articleId) return
        const loadArticle = async () => {
            setLoading(true)
            try {
                const article = await getArticle(articleId)
                // NOTE: 原创文章内容以 markdown block 形式存储
                const markdownContent = article.content
                    ?.find(b => b.type === 'markdown')?.content || ''

                setFormData({
                    title: article.title,
                    content: markdownContent,
                    summary: article.summary || '',
                    columnId: article.column_id,
                    tagInput: '',
                    tags: article.tags?.map((t: any) => t.name) || [],
                    coverImage: article.cover_image || ''
                })
                setPublishColumnId(article.column_id)
            } catch (err) {
                console.error('加载文章失败:', err)
                alert('文章加载失败')
            } finally {
                setLoading(false)
            }
        }
        loadArticle()
    }, [articleId])

    /**
     * 添加标签
     */
    const handleAddTag = useCallback(() => {
        const tag = formData.tagInput.trim()
        if (tag && !formData.tags.includes(tag)) {
            setFormData(prev => ({
                ...prev,
                tags: [...prev.tags, tag],
                tagInput: ''
            }))
        }
    }, [formData.tagInput, formData.tags])

    /**
     * 移除标签
     */
    const handleRemoveTag = useCallback((tagToRemove: string) => {
        setFormData(prev => ({
            ...prev,
            tags: prev.tags.filter(t => t !== tagToRemove)
        }))
    }, [])

    /**
     * 上传图片并插入到 Markdown 内容中
     */
    const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        setUploading(true)
        try {
            const result = await uploadImage(file)
            // 插入 Markdown 图片语法到编辑器内容
            const imageMarkdown = `\n![${file.name}](${result.url})\n`
            setFormData(prev => ({
                ...prev,
                content: prev.content + imageMarkdown
            }))
        } catch (err: any) {
            alert(err.response?.data?.detail || '图片上传失败')
        } finally {
            setUploading(false)
            // 重置 input 以便再次选择同一文件
            if (imageInputRef.current) {
                imageInputRef.current.value = ''
            }
        }
    }

    /**
     * 上传封面图
     */
    const handleCoverUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        try {
            const result = await uploadImage(file)
            setFormData(prev => ({ ...prev, coverImage: result.url }))
        } catch (err: any) {
            alert(err.response?.data?.detail || '封面图上传失败')
        } finally {
            if (coverInputRef.current) {
                coverInputRef.current.value = ''
            }
        }
    }

    /**
     * 保存草稿
     */
    const handleSaveDraft = async () => {
        if (!formData.title.trim()) {
            alert('请输入文章标题')
            return
        }
        if (!formData.content.trim()) {
            alert('请输入文章内容')
            return
        }

        setSaving(true)
        try {
            const payload = {
                title: formData.title,
                content: formData.content,
                summary: formData.summary || undefined,
                column_id: formData.columnId || undefined,
                tag_names: formData.tags.length > 0 ? formData.tags : undefined,
                cover_image: formData.coverImage || undefined,
                status: 'DRAFT'
            }

            if (isEditing && articleId) {
                await updateOriginalArticle(articleId, payload)
            } else {
                const article = await createOriginalArticle(payload)
                // NOTE: 创建成功后跳转到编辑模式，避免重复创建
                navigate(`/creator/edit-article/${article.id}`, { replace: true })
            }

            setLastSaved(new Date().toLocaleTimeString())
        } catch (err: any) {
            console.error('保存失败:', err)
            alert(err.response?.data?.detail || '保存失败，请重试')
        } finally {
            setSaving(false)
        }
    }

    /**
     * 打开发布确认弹窗
     */
    const handleOpenPublish = () => {
        if (!formData.title.trim()) {
            alert('请输入文章标题')
            return
        }
        if (!formData.content.trim()) {
            alert('请输入文章内容')
            return
        }
        setPublishColumnId(formData.columnId)
        setShowPublishModal(true)
    }

    /**
     * 确认发布
     */
    const handleConfirmPublish = async () => {
        setPublishing(true)
        try {
            // 先保存内容
            const payload = {
                title: formData.title,
                content: formData.content,
                summary: formData.summary || undefined,
                column_id: publishColumnId || undefined,
                tag_names: formData.tags.length > 0 ? formData.tags : undefined,
                cover_image: formData.coverImage || undefined,
                status: 'PUBLISHED'
            }

            let targetId = articleId
            if (isEditing && articleId) {
                await updateOriginalArticle(articleId, payload)
            } else {
                const article = await createOriginalArticle({ ...payload, status: 'DRAFT' })
                targetId = article.id
            }

            // 发布
            if (targetId) {
                await publishArticle(targetId, publishColumnId || undefined)
            }

            setShowPublishModal(false)
            alert('文章发布成功！')
            navigate('/creator-center')
        } catch (err: any) {
            console.error('发布失败:', err)
            alert(err.response?.data?.detail || '发布失败，请重试')
        } finally {
            setPublishing(false)
        }
    }

    if (loading) {
        return (
            <div className="editor-page">
                <div className="editor-loading">
                    <div className="spinner"></div>
                    <p>加载文章中...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="editor-page">
            {/* 顶部工具栏 */}
            <div className="editor-toolbar">
                <div className="toolbar-left">
                    <Link to="/creator-center" className="toolbar-back">
                        ← 返回创作中心
                    </Link>
                    <span className="toolbar-title">
                        {isEditing ? '编辑文章' : '新建文章'}
                    </span>
                </div>
                <div className="toolbar-right">
                    {lastSaved && (
                        <span className="save-hint">
                            上次保存: {lastSaved}
                        </span>
                    )}
                    <button
                        className="btn-draft"
                        onClick={handleSaveDraft}
                        disabled={saving}
                    >
                        {saving ? '保存中...' : '💾 保存草稿'}
                    </button>
                    <button
                        className="btn-publish"
                        onClick={handleOpenPublish}
                        disabled={publishing}
                    >
                        🚀 发布
                    </button>
                </div>
            </div>

            {/* 编辑器主区域 */}
            <div className="editor-main">
                <div className="editor-content-area">
                    {/* 标题输入 */}
                    <input
                        type="text"
                        className="editor-title-input"
                        placeholder="请输入文章标题..."
                        value={formData.title}
                        onChange={e => setFormData(prev => ({ ...prev, title: e.target.value }))}
                    />

                    {/* Markdown 编辑器 */}
                    <div className="markdown-editor-wrapper" data-color-mode="light">
                        {/* 图片上传按钮 */}
                        <div className="editor-image-upload">
                            <input
                                ref={imageInputRef}
                                type="file"
                                accept="image/*"
                                style={{ display: 'none' }}
                                onChange={handleImageUpload}
                            />
                            <button
                                className="btn-upload-image"
                                onClick={() => imageInputRef.current?.click()}
                                disabled={uploading}
                                title="上传图片到文章中"
                            >
                                {uploading ? '⬆️ 上传中...' : '🖼️ 插入图片'}
                            </button>
                        </div>
                        <MDEditor
                            value={formData.content}
                            onChange={(val) => setFormData(prev => ({ ...prev, content: val || '' }))}
                            height={600}
                            preview="live"
                            visibleDragbar={true}
                        />
                    </div>
                </div>

                {/* 侧栏设置 */}
                <div className="editor-sidebar">
                    <div className="sidebar-section">
                        <h3>📝 文章摘要</h3>
                        <textarea
                            className="sidebar-textarea"
                            placeholder="输入文章摘要（可选）..."
                            value={formData.summary}
                            onChange={e => setFormData(prev => ({ ...prev, summary: e.target.value }))}
                            rows={4}
                        />
                    </div>

                    <div className="sidebar-section">
                        <h3>📁 关联专栏</h3>
                        <select
                            className="sidebar-select"
                            value={formData.columnId || ''}
                            onChange={e => setFormData(prev => ({
                                ...prev,
                                columnId: e.target.value || null
                            }))}
                        >
                            <option value="">不关联专栏（发布到首页）</option>
                            {columns.map(col => (
                                <option key={col.id} value={col.id}>
                                    {col.name}
                                </option>
                            ))}
                        </select>
                        <p className="sidebar-hint">
                            {formData.columnId
                                ? '⚡ 发布后将关联到所选专栏'
                                : '✨ 发布后将展示在首页'}
                        </p>
                    </div>

                    <div className="sidebar-section">
                        <h3>🏷️ 标签</h3>
                        <div className="tag-input-row">
                            <input
                                type="text"
                                className="tag-input"
                                placeholder="输入标签..."
                                value={formData.tagInput}
                                onChange={e => setFormData(prev => ({ ...prev, tagInput: e.target.value }))}
                                onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                            />
                            <button className="tag-add-btn" onClick={handleAddTag}>
                                添加
                            </button>
                        </div>
                        <div className="tag-list">
                            {formData.tags.map(tag => (
                                <span key={tag} className="tag-item">
                                    {tag}
                                    <button
                                        className="tag-remove"
                                        onClick={() => handleRemoveTag(tag)}
                                    >×</button>
                                </span>
                            ))}
                        </div>
                    </div>

                    <div className="sidebar-section">
                        <h3>🖼️ 封面图</h3>
                        <div className="cover-upload-area">
                            <input
                                type="text"
                                className="sidebar-input"
                                placeholder="封面图 URL（可选）"
                                value={formData.coverImage}
                                onChange={e => setFormData(prev => ({ ...prev, coverImage: e.target.value }))}
                            />
                            <input
                                ref={coverInputRef}
                                type="file"
                                accept="image/*"
                                style={{ display: 'none' }}
                                onChange={handleCoverUpload}
                            />
                            <button
                                className="btn-cover-upload"
                                onClick={() => coverInputRef.current?.click()}
                            >
                                ⬆ 本地上传
                            </button>
                        </div>
                        {formData.coverImage && (
                            <div className="cover-preview">
                                <img src={formData.coverImage} alt="封面预览" />
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* 发布确认弹窗 */}
            {showPublishModal && (
                <div className="publish-modal-overlay" onClick={() => setShowPublishModal(false)}>
                    <div className="publish-modal" onClick={e => e.stopPropagation()}>
                        <h2>📢 确认发布</h2>
                        <p className="modal-desc">发布后文章将对读者可见</p>

                        <div className="modal-section">
                            <label>选择专栏（可选）</label>
                            <select
                                className="modal-select"
                                value={publishColumnId || ''}
                                onChange={e => setPublishColumnId(e.target.value || null)}
                            >
                                <option value="">不关联专栏（免费公开）</option>
                                {columns.map(col => (
                                    <option key={col.id} value={col.id}>
                                        {col.name} {col.is_free ? '(免费)' : `(¥${col.price})`}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="modal-info">
                            {publishColumnId ? (
                                <p>📌 文章将关联到所选专栏，并设为<strong>专栏私有</strong>内容</p>
                            ) : (
                                <p>🌐 文章将作为<strong>免费公开</strong>内容发布到首页</p>
                            )}
                        </div>

                        <div className="modal-actions">
                            <button
                                className="btn-cancel"
                                onClick={() => setShowPublishModal(false)}
                            >
                                取消
                            </button>
                            <button
                                className="btn-confirm-publish"
                                onClick={handleConfirmPublish}
                                disabled={publishing}
                            >
                                {publishing ? '发布中...' : '确认发布'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

export default ArticleEditor
