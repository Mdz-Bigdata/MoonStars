/**
 * 认证服务
 * 处理用户注册、登录、Token 管理
 */
import axios from 'axios'

const API_BASE_URL = '/api'

// Token 存储键
const TOKEN_KEY = 'auth_token'
const USER_KEY = 'user_info'

export interface User {
    id: string
    username: string
    email: string | null
    phone: string | null
    is_active: boolean
    role: string
    permission: string
    created_at: string
    last_login_at: string | null
    balance: number
    points: number
    invitation_code: string | null
    invited_by_id: string | null
    membership_expires_at: string | null
}

export interface PhoneLoginRequest {
    phone: string
    code: string
}

export interface PhoneRegisterRequest {
    username: string
    phone: string
    code: string
    invitation_code?: string
}

export interface LoginRequest {
    email: string
    password: string
}

export interface RegisterRequest {
    username: string
    email?: string
    password: string
    confirm_password: string
    phone: string
    code: string
    invitation_code?: string
}

export interface AuthResponse {
    access_token: string
    token_type: string
    user: User
}

/**
 * 用户注册
 */
export const register = async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await axios.post<AuthResponse>(`${API_BASE_URL}/auth/register`, data)
    // 保存 Token 和用户信息
    saveAuth(response.data)
    return response.data
}

/**
 * 用户登录
 */
export const login = async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await axios.post<AuthResponse>(`${API_BASE_URL}/auth/login`, data)
    // 保存 Token 和用户信息
    saveAuth(response.data)
    return response.data
}

/**
 * 发送验证码
 */
export const sendCode = async (phone: string): Promise<void> => {
    await axios.post(`${API_BASE_URL}/auth/send-code`, { phone })
}

/**
 * 手机号登录
 */
export const phoneLogin = async (data: PhoneLoginRequest): Promise<AuthResponse> => {
    const response = await axios.post<AuthResponse>(`${API_BASE_URL}/auth/phone-login`, data)
    saveAuth(response.data)
    return response.data
}

/**
 * 手机号注册
 */
export const phoneRegister = async (data: PhoneRegisterRequest): Promise<AuthResponse> => {
    const response = await axios.post<AuthResponse>(`${API_BASE_URL}/auth/phone-register`, data)
    saveAuth(response.data)
    return response.data
}

/**
 * 积分兑换
 */
export interface RedeemRequest {
    amount: number
}

export interface RedeemResponse {
    points_deducted: number
    balance_added: number
    new_points: number
    new_balance: number
}

export const redeemPoints = async (data: RedeemRequest): Promise<RedeemResponse> => {
    const response = await axios.post<RedeemResponse>(`${API_BASE_URL}/finance/redeem`, data)
    // 更新本地用户信息中的积分和余额
    const user = getUserInfo()
    if (user) {
        user.points = response.data.new_points
        user.balance = response.data.new_balance
        setUserInfo(user)
    }
    return response.data
}

/**
 * 获取当前用户信息
 */
export const getCurrentUser = async (): Promise<User> => {
    const token = getToken()
    if (!token) {
        throw new Error('未登录')
    }

    const response = await axios.get<User>(`${API_BASE_URL}/auth/me`, {
        headers: {
            Authorization: `Bearer ${token}`
        }
    })
    return response.data
}

/**
 * 保存认证信息
 */
const saveAuth = (authData: AuthResponse) => {
    localStorage.setItem(TOKEN_KEY, authData.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(authData.user))
}

/**
 * 获取 Token
 */
export const getToken = (): string | null => {
    return localStorage.getItem(TOKEN_KEY)
}

/**
 * 获取用户信息
 */
export const getUserInfo = (): User | null => {
    const userStr = localStorage.getItem(USER_KEY)
    if (!userStr) return null
    try {
        return JSON.parse(userStr)
    } catch {
        return null
    }
}

/**
 * 设置用户信息（更新本地缓存）
 */
export const setUserInfo = (user: User) => {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
}

/**
 * 退出登录
 */
export const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
}

/**
 * 检查是否已登录
 */
export const isAuthenticated = (): boolean => {
    return !!getToken()
}

// 配置 axios 拦截器，自动添加 Token
axios.interceptors.request.use(
    (config) => {
        const token = getToken()
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// 响应拦截器，处理 401 错误
axios.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // Token 过期或无效，清除认证信息
            logout()
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)
