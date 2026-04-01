import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import { getChatSkills, listSkills, updateChatSkills } from '../api/chat.js'

function openSkillLibrary(chatId) {
    if (typeof window === 'undefined') return
    window.location.hash = `#/chat/skills/${chatId}`
}

export default function SkillDetailPage({ chatId, skillId, source }) {
    const [allSkills, setAllSkills] = useState([])
    const [chatSkills, setChatSkills] = useState([])
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
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
            setError(loadError?.message || '加载技能详情失败')
        } finally {
            setLoading(false)
        }
    }, [chatId])

    useEffect(() => {
        void refresh()
    }, [refresh])

    const skill = useMemo(
        () => allSkills.find(item => item.skill_id === skillId && item.source === source),
        [allSkills, skillId, source],
    )

    const mountedSkill = useMemo(
        () => chatSkills.find(item => item.skill_id === skillId && item.source === source),
        [chatSkills, skillId, source],
    )

    const isEnabled = mountedSkill?.enabled ?? false

    const handleToggle = useCallback(async () => {
        if (!chatId || !skill || saving) return
        setSaving(true)
        setError('')
        try {
            const nextEnabled = !isEnabled
            await updateChatSkills(chatId, [{
                skill_id: skill.skill_id,
                source: skill.source,
                enabled: nextEnabled,
            }])
            const nextSkills = await getChatSkills(chatId)
            setChatSkills(Array.isArray(nextSkills) ? nextSkills : [])
        } catch (saveError) {
            setError(saveError?.message || '更新技能状态失败')
        } finally {
            setSaving(false)
        }
    }, [chatId, isEnabled, saving, skill])

    return (
        <PageScaffold
            title={skill?.name || '技能详情'}
            badge={isEnabled ? '已启用' : '未启用'}
            description="查看单个技能的说明与挂载状态；点击按钮即可为当前 Chat 启用或关闭。"
        >
            <div className="card">
                <div className="card-header">
                    <span className="card-title">技能详情</span>
                    <span className={`card-badge ${isEnabled ? 'badge-green' : 'badge-amber'}`}>{isEnabled ? '当前会话已挂载' : '当前会话未挂载'}</span>
                </div>
                <div className="skill-detail-actions">
                    <button className="page-btn" type="button" onClick={() => openSkillLibrary(chatId)}>
                        返回技能列表
                    </button>
                    <button className={`skill-toggle ${isEnabled ? 'on' : 'off'}`} type="button" onClick={() => void handleToggle()} disabled={!skill || saving || loading}>
                        {saving ? '保存中...' : (isEnabled ? '关闭技能' : '启用技能')}
                    </button>
                </div>
                {loading ? <div className="loading">加载中...</div> : null}
                {error ? <div className="chat-error">{error}</div> : null}
                {!loading && !skill ? (
                    <div className="empty-state">未找到该技能，可能已经被删除或来源参数不匹配。</div>
                ) : null}
                {!loading && skill ? (
                    <div className="skill-detail-layout">
                        <section className="skill-card skill-detail-summary">
                            <div className="skill-card-info">
                                <div className="skill-card-name">{skill.name || skill.skill_id}</div>
                                <div className="skill-card-desc">{skill.description || '暂无描述。'}</div>
                                <div className="skill-card-source">来源：{skill.source || 'workspace'}</div>
                                <div className="skill-card-source">Skill ID：{skill.skill_id}</div>
                            </div>
                        </section>
                        <section className="card skill-detail-panel">
                            <div className="card-header">
                                <span className="card-title">使用说明</span>
                                <span className="card-badge badge-purple">详情页</span>
                            </div>
                            <p className="settings-panel-copy">
                                这个页面用于查看单个技能详情和切换挂载状态，上一层是独立的技能列表页。
                            </p>
                            <div className="skill-detail-description">
                                <p>{skill.description || '暂无描述。'}</p>
                            </div>
                        </section>
                    </div>
                ) : null}
            </div>
        </PageScaffold>
    )
}
