import { useEffect, useMemo, useState } from 'react'
import { ContextMenuProvider } from './components/ContextMenuProvider.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import ChatPage from './pages/ChatPage.jsx'
import CreationDeskPage from './pages/CreationDeskPage.jsx'
import DataPanelPage from './pages/DataPanelPage.jsx'
import SkillsPage from './pages/SkillsPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import SkillDetailPage from './pages/SkillDetailPage.jsx'
import SkillLibraryPage from './pages/SkillLibraryPage.jsx'

const DEFAULT_ROUTE = 'chat'

const Icons = {
    chat: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <path d="M8 9h8" /><path d="M8 13h5" />
        </svg>
    ),
    'creation-desk': (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
        </svg>
    ),
    'data-panel': (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="12" width="4" height="9" />
            <rect x="10" y="7" width="4" height="14" />
            <rect x="17" y="3" width="4" height="18" />
        </svg>
    ),
    skills: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 2l2.5 5.5L20 10l-5.5 2.5L12 18l-2.5-5.5L4 10l5.5-2.5L12 2z" />
        </svg>
    ),
    settings: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 8.92 4.6H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c0 .68.4 1.3 1.03 1.57.17.07.35.11.54.11H21a2 2 0 0 1 0 4h-.09c-.19 0-.37.04-.54.11-.63.27-1.03.89-1.03 1.57z" />
        </svg>
    ),
}

const ROUTES = [
    { id: 'chat', icon: Icons.chat, label: 'Chat', component: ChatPage },
    { id: 'creation-desk', icon: Icons['creation-desk'], label: '创作台', component: CreationDeskPage },
    { id: 'data-panel', icon: Icons['data-panel'], label: '数据面板', component: DataPanelPage },
    { id: 'skills', icon: Icons.skills, label: 'Skills', component: SkillsPage },
    { id: 'settings', icon: Icons.settings, label: 'Settings', component: SettingsPage },
]

const ROUTE_MAP = new Map(ROUTES.map(route => [route.id, route]))

function parseHashRoute(hashValue) {
    const rawRoute = String(hashValue || '').replace(/^#\/?/, '').trim()
    const [routeId = '', ...restParts] = rawRoute.split('/').filter(Boolean)
    return {
        routeId: routeId.toLowerCase(),
        subPath: restParts,
    }
}

function normalizeRoute(routeId) {
    const safeId = (routeId || '').trim().toLowerCase()
    return ROUTE_MAP.has(safeId) ? safeId : DEFAULT_ROUTE
}

function readRouteStateFromHash() {
    if (typeof window === 'undefined') {
        return { routeId: DEFAULT_ROUTE, routeParams: {} }
    }

    const { routeId, subPath } = parseHashRoute(window.location.hash)
    const normalizedRouteId = normalizeRoute(routeId)

    if (normalizedRouteId === 'chat' && subPath[0] === 'skills' && subPath.length === 2) {
        return {
            routeId: normalizedRouteId,
            routeParams: {
                view: 'skill-library',
                chatId: subPath[1] || '',
            },
        }
    }

    if (normalizedRouteId === 'chat' && subPath[0] === 'skills' && subPath.length >= 4) {
        return {
            routeId: normalizedRouteId,
            routeParams: {
                view: 'skill-detail',
                chatId: subPath[1] || '',
                skillId: decodeURIComponent(subPath[2] || ''),
                source: decodeURIComponent(subPath[3] || ''),
            },
        }
    }

    return { routeId: normalizedRouteId, routeParams: {} }
}

function writeRouteToHash(routeId, routeParams = {}) {
    if (typeof window === 'undefined') return

    const normalizedRouteId = normalizeRoute(routeId)
    let nextHash = `#/${normalizedRouteId}`

    if (normalizedRouteId === 'chat' && routeParams?.view === 'skill-library') {
        const chatId = String(routeParams.chatId || '').trim()
        nextHash = `#/chat/skills/${chatId}`
    }

    if (normalizedRouteId === 'chat' && routeParams?.view === 'skill-detail') {
        const chatId = String(routeParams.chatId || '').trim()
        const skillId = encodeURIComponent(String(routeParams.skillId || '').trim())
        const source = encodeURIComponent(String(routeParams.source || '').trim())
        nextHash = `#/chat/skills/${chatId}/${skillId}/${source}`
    }

    if (window.location.hash !== nextHash) {
        window.location.hash = nextHash
    }
}

export default function App() {
    const [routeState, setRouteState] = useState(() => readRouteStateFromHash())

    useEffect(() => {
        if (typeof window === 'undefined') return undefined

        if (!window.location.hash) {
            writeRouteToHash(routeState.routeId, routeState.routeParams)
        }

        const handleHashChange = () => {
            setRouteState(readRouteStateFromHash())
        }

        window.addEventListener('hashchange', handleHashChange)
        return () => {
            window.removeEventListener('hashchange', handleHashChange)
        }
    }, [routeState.routeId, routeState.routeParams])

    const activeRoute = useMemo(
        () => ROUTE_MAP.get(routeState.routeId) || ROUTE_MAP.get(DEFAULT_ROUTE),
        [routeState.routeId],
    )

    const pageContent = routeState.routeId === 'chat' && routeState.routeParams?.view === 'skill-library'
        ? <SkillLibraryPage chatId={routeState.routeParams.chatId} />
        : routeState.routeId === 'chat' && routeState.routeParams?.view === 'skill-detail'
            ? <SkillDetailPage chatId={routeState.routeParams.chatId} skillId={routeState.routeParams.skillId} source={routeState.routeParams.source} />
            : (() => {
                const ActivePage = activeRoute.component
                return <ActivePage />
            })()

    return (
        <ContextMenuProvider>
            <div className="app-layout">
                <aside className="sidebar">
                    <div className="sidebar-header">
                        <h1>网文创作台</h1>
                        <div className="subtitle">Webnovel Dashboard</div>
                    </div>

                    <nav className="sidebar-nav" aria-label="主导航">
                        {ROUTES.map(item => (
                            <button
                                key={item.id}
                                className={`nav-item ${routeState.routeId === item.id && !routeState.routeParams?.view ? 'active' : ''}`}
                                onClick={() => {
                                    setRouteState({ routeId: item.id, routeParams: {} })
                                    writeRouteToHash(item.id)
                                }}
                                type="button"
                                aria-current={routeState.routeId === item.id && !routeState.routeParams?.view ? 'page' : undefined}
                                title={item.label}
                            >
                                <span className="icon" aria-hidden="true">{item.icon}</span>
                                <span>{item.label}</span>
                            </button>
                        ))}
                    </nav>

                    <div className="sidebar-note">
                        Chat 负责创作推进，创作台负责层级/章节编辑与评审，数据面板负责统计分析，Skills 负责模板技能库，Settings 负责 provider 配置。
                    </div>

                    <div className="live-indicator">
                        <span className="live-dot" />
                        路由已启用
                    </div>
                </aside>

                <main className="main-content">
                    <ErrorBoundary key={`${routeState.routeId}:${routeState.routeParams?.view || ''}:${routeState.routeParams?.chatId || ''}:${routeState.routeParams?.skillId || ''}:${routeState.routeParams?.source || ''}`}>
                        {pageContent}
                    </ErrorBoundary>
                </main>
            </div>
        </ContextMenuProvider>
    )
}
