/**
 * TypeScript 类型定义
 */

// 文章内容块类型
export interface ContentBlock {
    id?: string
    type: 'text' | 'heading' | 'image' | 'table' | 'list' | 'code' | 'quote' | 'divider' | 'whiteboard' | 'grid' | 'callout' | 'box' | 'sheet' | 'mindmap' | 'diagram' | 'html' | 'summary_box' | 'markdown'
    content: any
}

// 文章
export interface Article {
    id: string
    title: string
    summary: string | null
    content: ContentBlock[]
    source_url: string | null
    source_platform: 'wechat' | 'feishu' | 'yuque' | 'original'
    cover_image: string | null
    column_id: string | null
    view_count: number
    status?: 'DRAFT' | 'PUBLISHED' | 'PENDING_REVIEW'
    column_category?: string | null
    column_is_free?: boolean | null
    container_style?: string | null
    is_free?: boolean
    tags?: any[]
    language?: string | null
    created_at: string
    updated_at: string
}

// 专栏
export interface Column {
    id: string
    name: string
    description: string | null
    category: string | null
    cover_image: string | null
    price: number
    is_free: boolean
    article_count: number
    subscriber_count: number
    created_at: string
    updated_at: string
}

// 订单
export interface Order {
    id: string
    column_id: string
    amount: number
    payment_method: 'wechat' | 'alipay'
    status: 'pending' | 'paid' | 'failed' | 'cancelled'
    qr_code_url: string | null
    created_at: string
    paid_at: string | null
}

// API 响应类型
export interface ArticleListResponse {
    total: number
    items: Article[]
    page: number
    size: number
}

export interface ColumnListResponse {
    total: number
    items: Column[]
}

export interface ConvertResult {
    url: string
    success: boolean
    article_id?: string
    error?: string
}

export interface BatchConvertResponse {
    total: number
    success_count: number
    failed_count: number
    results: ConvertResult[]
}

export interface PaymentQRCode {
    qr_code_url: string
    amount: number
    expires_in: number
}

export interface OrderCreateResponse extends Order {
    payment_info?: PaymentQRCode
}

// 评论
export interface Comment {
    id: string
    article_id: string
    user_name: string
    content: string
    created_at: string
}
