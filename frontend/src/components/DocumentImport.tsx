import React, { useState } from 'react';
import axios from 'axios';

interface DocumentImportProps {
    onSuccess?: () => void;
}

const DocumentImport: React.FC<DocumentImportProps> = ({ onSuccess }) => {
    const [file, setFile] = useState<File | null>(null);
    const [pdfLoading, setPdfLoading] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
    const [shouldRedirect, setShouldRedirect] = useState(false);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleUploadDocument = async () => {
        if (!file) return;
        setPdfLoading(true);
        setMessage(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await axios.post('/api/documents/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            const articleId = response.data.article_id;
            const ext = file.name.split('.').pop()?.toUpperCase() || '文档';
            setMessage({
                type: 'success',
                text: articleId ? `${ext} 转换成功！已生成博客文章。` : `${ext} 转换成功！内容已提取。`
            });
            setShouldRedirect(!!articleId);
            setFile(null);
            if (onSuccess) onSuccess();

            setTimeout(() => {
                if (articleId) {
                    window.location.href = `/article/${articleId}`;
                }
            }, 2000);
        } catch (err) {
            setMessage({ type: 'error', text: '文档转换失败，请检查文件格式或服务器环境。' });
        } finally {
            setPdfLoading(false);
        }
    };

    return (
        <div className="document-import-card card">
            <h3 className="card-title">📄 全能文档转换</h3>
            <div className="tool-section">
                <p className="tool-desc">上传 PDF/Word/PPT/Excel/TXT，自动转换为高保真博客文章</p>
                <div className="upload-box">
                    <input type="file" accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.txt,.md" onChange={handleFileChange} id="doc-upload" />
                    <label htmlFor="doc-upload" className="file-label">
                        {file ? file.name : '选择文档文件'}
                    </label>
                    <button
                        className="btn btn-primary btn-sm"
                        onClick={handleUploadDocument}
                        disabled={!file || pdfLoading}
                    >
                        {pdfLoading ? '正在转换...' : '开始转换'}
                    </button>
                </div>
            </div>

            {message && (
                <div className={`message-toast ${message.type}`}>
                    {message.type === 'success' ? '✅' : '❌'} {message.text}
                    {message.type === 'success' && shouldRedirect && <span style={{ marginLeft: '10px', fontSize: '12px', opacity: 0.8 }}>(正在跳转...)</span>}
                </div>
            )}
        </div>
    );
};

export default DocumentImport;
