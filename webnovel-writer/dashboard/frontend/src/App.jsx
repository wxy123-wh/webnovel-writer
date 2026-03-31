import { useEffect, useMemo, useState } from 'react'
import { ContextMenuProvider } from './components/ContextMenuProvider.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import ChatPage from './pages/ChatPage.jsx'

const DEFAULT_ROUTE = 'chat'

// P2-E 修复：用内联 SVG 图标替换原来的字母占位符，提升商业产品专业感
const Icons = {
    chat: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <path d="M8 9h8" /><path d="M8 13h5" />
        </svg>
    ),
}

const ROUTES = [
    { id: 'chat', icon: Icons.chat, label: 'Chat', component: ChatPage },
]

const ROUTE_MAP = new Map(ROUTES.map(route => [route.id, route]))

function normalizeRoute(routeId) {
    const safeId = (routeId || '').trim().toLowerCase()
    return ROUTE_MAP.has(safeId) ? safeId : DEFAULT_ROUTE
}

function readRouteFromHash() {
    if (typeof window === 'undefined') return DEFAULT_ROUTE
    const route = window.location.hash.replace(/^#\/?/, '')
    return normalizeRoute(route)
}

function writeRouteToHash(routeId) {
    if (typeof window === 'undefined') return
    const nextHash = `#/${normalizeRoute(routeId)}`
    if (window.location.hash !== nextHash) {
        window.location.hash = nextHash
    }
}

export default function App() {
    const [routeId, setRouteId] = useState(() => readRouteFromHash())

    useEffect(() => {
        if (typeof window === 'undefined') return undefined

        if (!window.location.hash) {
            writeRouteToHash(routeId)
        }

        const handleHashChange = () => {
            setRouteId(readRouteFromHash())
        }

        window.addEventListener('hashchange', handleHashChange)
        return () => {
            window.removeEventListener('hashchange', handleHashChange)
        }
    }, [routeId])

    const activeRoute = useMemo(
        () => ROUTE_MAP.get(routeId) || ROUTE_MAP.get(DEFAULT_ROUTE),
        [routeId],
    )
    const ActivePage = activeRoute.component

    return (
        <ContextMenuProvider>
            <div className="app-layout">
                <aside className="sidebar">
                    {/* P3-A 修复：sidebar 标题改为中文品牌名，去掉硬编码英文 */}
                    <div className="sidebar-header">
                        <h1>网文创作台</h1>
                        <div className="subtitle">Webnovel Dashboard</div>
                    </div>

                    <nav className="sidebar-nav" aria-label="主导航">
                        {ROUTES.map(item => (
                            <button
                                key={item.id}
                                className={`nav-item ${routeId === item.id ? 'active' : ''}`}
                                onClick={() => {
                                    setRouteId(item.id)
                                    writeRouteToHash(item.id)
                                }}
                                type="button"
                                aria-current={routeId === item.id ? 'page' : undefined}
                                title={item.label}
                            >
                                {/* P2-E 修复：使用 SVG 图标替换字母占位符 */}
                                <span className="icon" aria-hidden="true">{item.icon}</span>
                                <span>{item.label}</span>
                            </button>
                        ))}
                    </nav>

                    <div className="sidebar-note">
                        这里只保留一条可直接开始使用的主路径：Chat 创作工作台。
                    </div>

                    <div className="live-indicator">
                        <span className="live-dot" />
                        路由已启用
                    </div>
                </aside>

                <main className="main-content">
                    {/* P1-G 修复：ErrorBoundary 包裹，防止页面组件崩溃导致整个 App 白屏 */}
                    <ErrorBoundary key={routeId}>
                        <ActivePage />
                    </ErrorBoundary>
                </main>
            </div>
        </ContextMenuProvider>
    )
}
