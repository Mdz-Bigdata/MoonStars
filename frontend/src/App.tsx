/**
 * 主应用组件
 * 配置路由
 */
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Home from './pages/home'
import ArticleDetail from './pages/article-detail'
import Login from './pages/login'
import Register from './pages/register'
import UserCenter from './pages/UserCenter'
import MembershipCenter from './pages/membership-center'
import CreatorCenter from './pages/creator-center'
import TechnicalColumns from './pages/technical-columns'
import ColumnArticles from './pages/column-articles'
import PluginMarket from './pages/plugin-market'
import AdminFinance from './pages/admin-finance'
import UrlToPpt from './pages/url-to-ppt'
import AIConfigPage from './pages/ai-config-page'
import ArticleEditor from './pages/article-editor'
import VideoNoteDetail from './pages/VideoNoteDetail'
import VideoProgress from './components/VideoAssistant/VideoProgress'
import Navbar from './components/Navbar'
import './styles/index.css'

function App() {
  return (
    <Router>
      <div className="app">
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/articles/:id" element={<ArticleDetail />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/user-center" element={<UserCenter />} />
          <Route path="/membership-center" element={<MembershipCenter />} />
          <Route path="/creator-center" element={<CreatorCenter />} />
          <Route path="/technical-columns" element={<TechnicalColumns />} />
          <Route path="/columns/:columnId/articles" element={<ColumnArticles />} />
          <Route path="/plugin-market" element={<PluginMarket />} />
          <Route path="/admin/finance" element={<AdminFinance />} />
          <Route path="/url-to-ppt" element={<UrlToPpt />} />
          <Route path="/settings" element={<AIConfigPage />} />
          <Route path="/ai-config" element={<AIConfigPage />} />
          <Route path="/video-note-detail/:taskId" element={<VideoNoteDetail />} />
          <Route path="/video-assistant/progress/:taskId" element={<VideoProgress />} />
          <Route path="/creator/new-article" element={<ArticleEditor />} />
          <Route path="/creator/edit-article/:id" element={<ArticleEditor />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App

