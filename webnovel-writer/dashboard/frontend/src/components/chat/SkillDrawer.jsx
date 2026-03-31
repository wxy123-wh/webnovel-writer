import { useCallback, useEffect, useRef, useState } from 'react'
import { getChatSkills, listSkills, updateChatSkills } from '../../api/chat.js'

export default function SkillDrawer({ chatId, open, onClose, onSkillsChanged }) {
    const [allSkills, setAllSkills] = useState([])
    const [chatSkills, setChatSkills] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [retryKey, setRetryKey] = useState(0)
    const cancelledRef = useRef(false)

    const loadDrawerData = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const [all, mounted] = await Promise.all([
                listSkills(),
                chatId ? getChatSkills(chatId) : Promise.resolve([]),
            ])

            if (!cancelledRef.current) {
                setAllSkills(all.filter(skill => skill?.skill_id === 'webnovel-write'))
                setChatSkills(mounted)
            }
        } catch (err) {
            if (!cancelledRef.current) {
                setError(err?.message || '加载 Skill 列表失败')
            }
        } finally {
            if (!cancelledRef.current) {
                setLoading(false)
            }
        }
    }, [chatId])

    useEffect(() => {
        if (!open) return undefined

        cancelledRef.current = false
        void loadDrawerData()

        return () => {
            cancelledRef.current = true
        }
    }, [loadDrawerData, open, retryKey])

    const toggleSkill = useCallback(async (skill, enable) => {
        if (!chatId) return
        await updateChatSkills(chatId, [{ skill_id: skill.skill_id, source: skill.source, enabled: enable }])
        const nextSkills = await getChatSkills(chatId)
        setChatSkills(nextSkills)
        onSkillsChanged?.(nextSkills)
    }, [chatId, onSkillsChanged])

    if (!open) return null

    return (
        <div className="skill-drawer">
            <div className="skill-drawer-header">
                <h3>Skill 库</h3>
                <button className="skill-drawer-close" onClick={onClose} type="button">✕</button>
            </div>
            <div className="skill-drawer-body">
                <p className="skill-drawer-note">当前界面只保留已经接入并验证过的写作技能，避免把未完成能力暴露给你。</p>
                {loading ? (
                    <div className="loading">加载中...</div>
                ) : error ? (
                    <div className="skill-error" style={{ display: 'grid', gap: '12px' }}>
                        <p style={{ margin: 0 }}>⚠️ Skill 加载失败: {error}</p>
                        <div>
                            <button onClick={() => setRetryKey(key => key + 1)} type="button">重试</button>
                        </div>
                    </div>
                ) : (
                    allSkills.map(skill => {
                        const mounted = chatSkills.find(
                            item => item.skill_id === skill.skill_id && item.source === skill.source,
                        )
                        const isOn = mounted?.enabled ?? false

                        return (
                            <div key={`${skill.source}:${skill.skill_id}`} className={`skill-card ${isOn ? 'active' : ''}`}>
                                <div className="skill-card-info">
                                    <div className="skill-card-name">{skill.name}</div>
                                    <div className="skill-card-desc">{skill.description}</div>
                                    <div className="skill-card-source">{skill.source}</div>
                                </div>
                                <button
                                    className={`skill-toggle ${isOn ? 'on' : 'off'}`}
                                    onClick={() => {
                                        void toggleSkill(skill, !isOn)
                                    }}
                                    type="button"
                                >
                                    {isOn ? '已启用' : '启用'}
                                </button>
                            </div>
                        )
                    })
                )}
            </div>
        </div>
    )
}
