import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import { getChatSkills, listSkills } from '../api/chat.js'

function openChatMain() {
    if (typeof window === 'undefined') return
    window.location.hash = '#/chat'
}

function openSkillDetail(chatId, skill) {
    if (typeof window === 'undefined' || !chatId || !skill?.skill_id) return
    const safeSkillId = encodeURIComponent(skill.skill_id)
    const safeSource = encodeURIComponent(skill.source || 'workspace')
    window.location.hash = `#/chat/skills/${chatId}/${safeSkillId}/${safeSource}`
}

export default function SkillLibraryPage({ chatId }) {
    const [allSkills, setAllSkills] = useState([])
    const [chatSkills, setChatSkills] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    const refresh = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
            const [all, mounted] = await Promise.all([
                listSkills(),
                chatId ? getChatSkills(chatId) : Promise.resolve([]),
            ])
            setAllSkills(Array.isArray(all) ? all : [])
            setChatSkills(Array.isArray(mounted) ? mounted : [])
        } catch (loadError) {
            setError(loadError?.message || '加载技能列表失败')
        } finally {
            setLoading(false)
        }
    }, [chatId])

    useEffect(() => {
        void refresh()
    }, [refresh])

    const enrichedSkills = useMemo(() => {
        const mountedMap = new Map(
            chatSkills.map(skill => [`${skill.source}:${skill.skill_id}`, Boolean(skill.enabled)]),
        )
        return allSkills.map(skill => ({
            ...skill,
            enabled: mountedMap.get(`${skill.source}:${skill.skill_id}`) ?? false,
        }))
    }, [allSkills, chatSkills])

    const enabledCount = enrichedSkills.filter(skill => skill.enabled).length

    return (
        <PageScaffold
            title="技能页面"
            badge={`${enabledCount}/${enrichedSkills.length} 已启用`}
            description="这里展示当前 Chat 可用的全部技能。点击任意技能进入独立详情页，再决定是否启用。"
        >
            <div className="card">
                <div className="card-header">
                    <span className="card-title">技能列表</span>
                    <div className="skill-detail-actions">
                        <button className="page-btn" type="button" onClick={openChatMain}>
                            返回 Chat
                        </button>
                        <button className="page-btn" type="button" onClick={() => void refresh()} disabled={loading}>
                            {loading ? '加载中...' : '刷新'}
                        </button>
                    </div>
                </div>
                <p className="settings-panel-copy">
                    不再直接打开抽屉；在这里先看列表，再进入单个技能详情页处理启用状态。
                </p>
                {loading ? <div className="loading">加载中...</div> : null}
                {error ? <div className="chat-error">{error}</div> : null}
                {!loading && !error && enrichedSkills.length === 0 ? (
                    <div className="empty-state">当前没有可用技能。</div>
                ) : null}
                {!loading && !error && enrichedSkills.length > 0 ? (
                    <div className="skill-library-grid">
                        {enrichedSkills.map(skill => (
                            <button
                                key={`${skill.source}:${skill.skill_id}`}
                                className={`skill-card skill-library-card ${skill.enabled ? 'active' : ''}`}
                                onClick={() => openSkillDetail(chatId, skill)}
                                type="button"
                            >
                                <div className="skill-card-info">
                                    <div className="skill-card-name">{skill.name || skill.skill_id}</div>
                                    <div className="skill-card-desc">{skill.description || '暂无描述。'}</div>
                                    <div className="skill-card-source">{skill.source || 'workspace'}</div>
                                </div>
                                <span className={`card-badge ${skill.enabled ? 'badge-green' : 'badge-amber'}`}>
                                    {skill.enabled ? '已启用' : '未启用'}
                                </span>
                            </button>
                        ))}
                    </div>
                ) : null}
            </div>
        </PageScaffold>
    )
}
