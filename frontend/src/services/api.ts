/**
 * API 服务层
 * 封装所有后端接口调用
 */
import axios from 'axios'
import type {
    Article,
    ArticleListResponse,
    Column,
    ColumnListResponse,
    BatchConvertResponse,
    Order,
    OrderCreateResponse,
    Comment
} from '../types'
import { getToken, logout } from './auth'

// 创建 axios 实例
const api = axios.create({
    baseURL: '/api',
    timeout: 600000, // 增加到 10 分钟以支持超大型飞书 Wiki 文档转换（含多张截图）
    headers: {
        'Content-Type': 'application/json',
    },
})

// 请求拦截器：添加 Token
api.interceptors.request.use(
    (config) => {
        const token = getToken()
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => Promise.reject(error)
)

// 响应拦截器：处理 401
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            logout()
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)

// ==================== 文章接口 ====================

/**
 * 单篇文章 URL 转换
 */
export const convertArticle = async (
    url: string,
    columnId?: string,
    cookies?: Record<string, string>,
    password?: string
): Promise<Article> => {
    const response = await api.post('/articles/convert', {
        url,
        column_id: columnId || null,
        cookies: cookies || null,
        password: password || null,
    })
    return response.data
}

/**
 * 批量文章 URL 转换
 */
export const batchConvertArticles = async (
    urls: string[],
    columnId?: string
): Promise<BatchConvertResponse> => {
    const response = await api.post('/articles/batch-convert', {
        urls,
        column_id: columnId || null,
    })
    return response.data
}

/**
 * 获取文章列表
 */
export const getArticles = async (params: {
    page?: number
    size?: number
    column_id?: string
    platform?: string
}): Promise<ArticleListResponse> => {
    const response = await api.get('/articles', { params })
    return response.data
}

/**
 * 获取文章详情
 */
export const getArticle = async (articleId: string): Promise<Article> => {
    const response = await api.get(`/articles/${articleId}`)
    return response.data
}

/**
 * 删除文章 (仅限管理员)
 */
export const deleteArticle = async (articleId: string): Promise<void> => {
    await api.delete(`/admin/articles/${articleId}`)
}

/**
 * 更新文章内容 (仅限管理员)
 */
export const updateArticle = async (articleId: string, data: Partial<Article>): Promise<Article> => {
    const response = await api.put(`/articles/${articleId}`, data)
    return response.data
}

// ==================== 专栏接口 ====================

/**
 * 创建专栏
 */
export const createColumn = async (data: {
    name: string
    description?: string
    cover_image?: string
    price: number
    is_free: boolean
}): Promise<Column> => {
    const response = await api.post('/columns', data)
    return response.data
}

/**
 * 获取所有专栏
 */
export const getColumns = async (): Promise<ColumnListResponse> => {
    const response = await api.get('/columns')
    return response.data
}

/**
 * 获取专栏详情
 */
export const getColumn = async (columnId: string): Promise<Column> => {
    const response = await api.get(`/columns/${columnId}`)
    return response.data
}

/**
 * 获取专栏文章列表
 */
export const getColumnArticles = async (
    columnId: string,
    page = 1,
    size = 20
): Promise<ArticleListResponse> => {
    const response = await api.get(`/columns/${columnId}/articles`, {
        params: { page, size },
    })
    return response.data
}

// ==================== 支付接口 ====================

/**
 * 创建订单
 */
export const createOrder = async (data: {
    column_id: string
    payment_method: 'wechat' | 'alipay'
    user_email?: string
}): Promise<OrderCreateResponse> => {
    const response = await api.post('/orders/create', data)
    return response.data
}

/**
 * 模拟支付确认（开发/演示环境）
 */
export const confirmPayment = async (
    orderId: string
): Promise<{ success: boolean; message: string; user: any }> => {
    const response = await api.post(`/orders/${orderId}/confirm-payment`)
    return response.data
}

/**
 * 查询订单状态
 */
export const getOrderStatus = async (
    orderId: string
): Promise<{ order_id: string; status: string }> => {
    const response = await api.get(`/orders/${orderId}/status`)
    return response.data
}

// ==================== 评论接口 ====================

/**
 * 获取文章评论
 */
export const getComments = async (articleId: string): Promise<Comment[]> => {
    const response = await api.get(`/articles/${articleId}/comments`)
    return response.data
}

/**
 * 发表评论
 */
export const createComment = async (data: {
    article_id: string
    content: string
    user_name?: string
}): Promise<Comment> => {
    const response = await api.post('/articles/comments', data)
    return response.data
}

// ==================== AI 增强接口 ====================

/**
 * 获取 AI 全文总结
 */
export const getAiSummary = async (
    articleId: string,
    params: {
        model?: string
        api_key?: string
        base_url?: string
        provider?: string
        max_tokens?: number
        temperature?: number
    }
): Promise<{ summary: string }> => {
    const response = await api.post(`/articles/${articleId}/ai-summary`, params)
    return response.data
}

/**
 * 基于文章内容进行 AI 对话
 */
export const chatWithArticle = async (
    articleId: string,
    data: {
        message: string
        history: { role: 'user' | 'assistant'; content: string }[]
        model?: string
        api_key?: string
        base_url?: string
        provider?: string
        max_tokens?: number
        temperature?: number
    }
): Promise<{ answer: string; model: string }> => {
    const response = await api.post(`/articles/${articleId}/chat`, data)
    return response.data
}

// ==================== 用户/中心接口 ====================
export const updateProfile = async (data: {
    username?: string
    phone?: string
    role?: string
    permission?: string
    mcp_servers?: any[]
    user_rules?: string
    project_rules?: string
    invitation_code?: string
    bank_card_info?: { card_number: string }
    wechat_info?: { id: string }
    alipay_info?: { account: string; name: string }
}): Promise<any> => {
    const response = await api.put('/users/me', data)
    return response.data
}

/**
 * 上传图片（用于 Markdown 编辑器和封面图）
 */
export const uploadImage = async (file: File): Promise<{ url: string; filename: string }> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/upload/image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
}

/**
 * 获取我的创作列表（支持状态筛选）
 */
export const getMyArticles = async (params: {
    page?: number
    size?: number
    status?: string
}): Promise<ArticleListResponse> => {
    const response = await api.get('/creator/articles', { params })
    return response.data
}

/**
 * 创建原创文章
 */
export const createOriginalArticle = async (data: {
    title: string
    content: string
    summary?: string
    column_id?: string | null
    tag_names?: string[]
    status?: string
    cover_image?: string
}): Promise<Article> => {
    const response = await api.post('/creator/articles/create', data)
    return response.data
}

/**
 * 更新原创文章
 */
export const updateOriginalArticle = async (articleId: string, data: {
    title: string
    content: string
    summary?: string
    column_id?: string | null
    tag_names?: string[]
    cover_image?: string
}): Promise<Article> => {
    const response = await api.put(`/creator/articles/${articleId}`, data)
    return response.data
}

/**
 * 发布文章（草稿 → 已发布）
 */
export const publishArticle = async (articleId: string, columnId?: string): Promise<Article> => {
    const response = await api.post(`/creator/articles/${articleId}/publish`, null, {
        params: columnId ? { column_id: columnId } : undefined
    })
    return response.data
}

/**
 * 删除我的文章
 */
export const deleteMyArticle = async (articleId: string): Promise<void> => {
    await api.delete(`/creator/articles/${articleId}`)
}

/**
 * 获取我的购买记录
 */
export const getMyOrders = async (): Promise<Order[]> => {
    const response = await api.get('/purchase-records')
    return response.data.items
}

/**
 * 获取我已购买的专栏
 */
export const getMyColumns = async (): Promise<Column[]> => {
    const response = await api.get('/columns/mine')
    return response.data
}

/**
 * 获取我的余额和积分
 */
export const getBalance = async (): Promise<{ balance: number; points: number; invitation_code?: string }> => {
    const response = await api.get('/finance/balance')
    return response.data
}

/**
 * 获取交易记录
 */
export const getTransactions = async (params: {
    page?: number
    size?: number
}): Promise<{ items: any[]; total: number }> => {
    const response = await api.get('/finance/transactions', { params })
    return response.data
}

/**
 * 申请提现
 */
export const submitWithdrawal = async (data: {
    amount: number
    method: string
    account_info: string
    account_name: string
}): Promise<any> => {
    const response = await api.post('/finance/withdraw', data)
    return response.data
}

/**
 * 管理员：获取财务统计信息
 */
export const getFinanceStats = async (): Promise<any> => {
    const response = await api.get('/admin/finance/stats')
    return response.data
}

/**
 * 管理员：获取所有待提现申请
 */
export const adminGetWithdrawals = async (): Promise<any[]> => {
    const response = await api.get('/admin/finance/withdrawals')
    return response.data
}

/**
 * 管理员：审核提现申请
 */
export const adminAuditWithdrawal = async (requestId: string, approve: boolean, remark?: string): Promise<any> => {
    const response = await api.post(`/admin/finance/withdrawals/${requestId}/audit`, {
        approve,
        remark
    })
    return response.data
}

export default api
