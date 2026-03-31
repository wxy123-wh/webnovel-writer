import { useCallback, useEffect, useMemo, useState } from 'react'
import { createChat, listChats } from '../api/chat.js'
import { fetchRuntimeProfile } from '../api/runtime.js'
import PageScaffold from '../components/PageScaffold.jsx'
import ChatShell from '../components/chat/ChatShell.jsx'

function formatChatTime(value) {
    if (!value) return ''
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
        return String(value).slice(5, 16)
    }
    return parsed.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    })
}

export default function ChatPage() {
    const [chats, setChats] = useState([])
    const [activeChatId, setActiveChatId] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [runtimeProfile, setRuntimeProfile] = useState(null)
    const [runtimeLoading, setRuntimeLoading] = useState(true)
    const [runtimeError, setRuntimeError] = useState('')

    const hasChats = chats.length > 0
    const generation = runtimeProfile?.generation || null
    const project = runtimeProfile?.project || null
    const generationConfigured = Boolean(generation?.configured)
    const generationProvider = generation?.provider || ''

    const loadRuntimeProfile = useCallback(async () => {
        setRuntimeLoading(true)
        setRuntimeError('')
        try {
            const profile = await fetchRuntimeProfile()
            setRuntimeProfile(profile)
        } catch (loadError) {
            setRuntimeError(loadError?.message || '读取运行时配置失败')
        } finally {
            setRuntimeLoading(false)
        }
    }, [])

    const loadChats = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const list = await listChats()
            setChats(list)
            setActiveChatId(prev => prev || list[0]?.chat_id || null)
        } catch (loadError) {
            setError(loadError?.message || '加载对话列表失败')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void loadChats()
    }, [loadChats])

    useEffect(() => {
        void loadRuntimeProfile()
    }, [loadRuntimeProfile])

    const handleNewChat = useCallback(async () => {
        if (!generationConfigured) {
            setError('请先完成生成服务配置，再创建对话。')
            return
        }
        try {
            const chat = await createChat({ title: `对话 ${chats.length + 1}` })
            setChats(prev => [chat, ...prev])
            setActiveChatId(chat.chat_id)
        } catch (createError) {
            setError(createError?.message || '创建对话失败')
        }
    }, [chats.length, generationConfigured])

    const badge = useMemo(() => {
        if (runtimeLoading) return '检查运行时'
        if (runtimeError) return '连接异常'
        if (!generationConfigured) return '需要配置'
        if (loading) return '加载中'
        return `${chats.length} 个会话`
    }, [chats.length, generationConfigured, loading, runtimeError, runtimeLoading])

    const runtimeSummary = useMemo(() => {
        if (runtimeError) {
            return {
                badge: '连接异常',
                title: '暂时无法进入 Chat',
                description: '现在无法确认运行时是否已准备好。请确认后端已启动，然后刷新页面重试。',
            }
        }

        if (generationConfigured && generationProvider === 'local') {
            return {
                badge: '本地模式',
                title: '你现在可以直接开始使用 Chat',
                description: '当前运行在内置本地模式，不需要额外的 API key。回复会基于当前项目上下文给出稳定、可继续推进的写作建议。',
                details: [
                    { label: 'Provider', value: 'local' },
                    { label: 'API Key', value: '不需要' },
                    { label: 'Model', value: generation?.model || 'built-in' },
                    { label: 'Base URL', value: '内置本地逻辑' },
                ],
            }
        }

        const provider = generation?.provider || '未设置'
        const model = generation?.model || '未设置'
        const baseUrl = generation?.base_url || '默认地址'
        const apiKey = generation?.api_key_configured ? '已配置' : '未配置'

        return {
            badge: '需要先完成设置',
            title: '先完成生成服务配置，再开始对话',
            description: '当前运行时还不能进行真实生成，所以 Chat 暂时不会开放输入。请先在服务端配置生成 provider 和 API key，然后刷新页面。',
            details: [
                { label: 'Provider', value: provider },
                { label: 'API Key', value: apiKey },
                { label: 'Model', value: model },
                { label: 'Base URL', value: baseUrl },
            ],
        }
    }, [generation, generationConfigured, generationProvider, runtimeError])

    return (
        <PageScaffold
            title="Chat Agent"
            badge={badge}
            description="在同一工作台中管理多轮对话、流式回复和技能挂载。"
        >
            {!runtimeLoading && !runtimeError && generationConfigured && generationProvider === 'local' ? (
                <div className="card" style={{ background: '#eefbf3', borderColor: '#2ec27e' }}>
                    <div className="card-header">
                        <span className="card-title">✅ 本地模式已就绪</span>
                        <span className="card-badge badge-green">Local</span>
                    </div>
                    <p style={{ margin: 0, color: '#215c39' }}>
                        当前无需额外配置即可直接开始对话；如果你之后补充 API key，系统仍然可以切换到外部生成模式。
                    </p>
                    {project?.title || project?.genre || project?.current_chapter ? (
                        <div className="chat-project-brief">
                            {project?.title ? <span>作品：{project.title}</span> : null}
                            {project?.genre ? <span>类型：{project.genre}</span> : null}
                            {project?.current_chapter ? <span>当前章节：{project.current_chapter}</span> : null}
                        </div>
                    ) : null}
                </div>
            ) : null}

            <div className="chat-page">
                <div className="chat-sidebar card">
                    <button className="new-chat-btn" onClick={() => void handleNewChat()} type="button" disabled={!generationConfigured || runtimeLoading}>
                        + 新对话
                    </button>

                    {error ? <div className="chat-error">{error}</div> : null}
                    {loading ? <div className="loading">对话列表加载中...</div> : null}

                    <div className="chat-list">
                        {chats.map(chat => (
                            <button
                                key={chat.chat_id}
                                className={`chat-list-item ${chat.chat_id === activeChatId ? 'active' : ''}`}
                                onClick={() => setActiveChatId(chat.chat_id)}
                                type="button"
                            >
                                <span className="chat-list-title">{chat.title || '未命名'}</span>
                                <span className="chat-list-time">{formatChatTime(chat.updated_at)}</span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="chat-workspace">
                    {runtimeLoading ? (
                        <div className="chat-empty card">
                            <div className="chat-empty-content">
                                <span className="chat-empty-badge">正在检查</span>
                                <h3 className="chat-empty-title">正在检查生成服务</h3>
                                <p className="chat-empty-description">
                                    稍等一下，系统正在确认当前运行时是否已经准备好进行真实生成。
                                </p>
                            </div>
                        </div>
                    ) : runtimeError || !generationConfigured ? (
                        <div className="chat-empty chat-setup-state card">
                            <div className="chat-empty-content">
                                <span className="chat-empty-badge chat-empty-badge-amber">{runtimeSummary.badge}</span>
                                <h3 className="chat-empty-title">{runtimeSummary.title}</h3>
                                <p className="chat-empty-description">{runtimeSummary.description}</p>
                                {Array.isArray(runtimeSummary.details) ? (
                                    <dl className="chat-setup-list">
                                        {runtimeSummary.details.map(item => (
                                            <div className="chat-setup-item" key={item.label}>
                                                <dt>{item.label}</dt>
                                                <dd>{item.value}</dd>
                                            </div>
                                        ))}
                                    </dl>
                                ) : null}
                            </div>
                        </div>
                    ) : activeChatId ? (
                        <ChatShell
                            key={activeChatId}
                            chatId={activeChatId}
                            projectSummary={{
                                title: project?.title || '',
                                genre: project?.genre || '',
                                currentChapter: project?.current_chapter || '',
                            }}
                        />
                    ) : (
                        <div className="chat-empty card">
                            <div className="chat-empty-content">
                                <span className="chat-empty-badge">首次开始</span>
                                <h3 className="chat-empty-title">先创建一个对话，再开始推进你的小说</h3>
                                <p className="chat-empty-description">
                                    这是当前产品的主工作台。先创建第一轮对话，你就可以直接让 Agent 帮你做选题、设定、大纲或章节写作。
                                </p>
                                <button className="new-chat-btn chat-empty-primary" onClick={() => void handleNewChat()} type="button">
                                    创建第一个对话
                                </button>
                                <div className="chat-empty-examples">
                                    <div className="chat-empty-examples-title">你可以直接这样开始：</div>
                                    <ul>
                                        <li>帮我生成这本书的核心卖点和一句话简介</li>
                                        <li>按现在的项目状态，给我一个第一章开头方案</li>
                                        <li>我想先梳理主角设定，帮我列出必须补齐的三项</li>
                                    </ul>
                                </div>
                                {!loading && !hasChats ? (
                                    <p className="chat-empty-hint">
                                        建议直接发送你的目标，例如："帮我生成这本书的核心卖点和一句话简介。"
                                    </p>
                                ) : null}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </PageScaffold>
    )
}
