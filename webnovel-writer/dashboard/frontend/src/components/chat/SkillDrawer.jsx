import { useCallback, useEffect, useState } from 'react'
import { getChatSkills, listSkills, updateChatSkills } from '../../api/chat.js'

export default function SkillDrawer({ chatId, open, onClose }) {
    const [allSkills, setAllSkills] = useState([])
    const [chatSkills, setChatSkills] = useState([])
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        if (!open) return undefined

        let cancelled = false

        async function loadDrawerData() {
            setLoading(true)
            try {
                const [all, mounted] = await Promise.all([
                    listSkills(),
                    chatId ? getChatSkills(chatId) : Promise.resolve([]),
                ])

                if (!cancelled) {
                    setAllSkills(all)
                    setChatSkills(mounted)
                }
            } catch {
                if (!cancelled) {
                    setAllSkills([])
                    setChatSkills([])
                }
            } finally {
                if (!cancelled) {
                    setLoading(false)
                }
            }
        }

        void loadDrawerData()

        return () => {
            cancelled = true
        }
    }, [chatId, open])

    const toggleSkill = useCallback(async (skillId, enable) => {
        if (!chatId) return
        await updateChatSkills(chatId, [{ skill_id: skillId, enabled: enable }])
        const nextSkills = await getChatSkills(chatId)
        setChatSkills(nextSkills)
    }, [chatId])

    if (!open) return null

    return (
        <div className="skill-drawer">
            <div className="skill-drawer-header">
                <h3>Skill 库</h3>
                <button className="skill-drawer-close" onClick={onClose} type="button">✕</button>
            </div>
            <div className="skill-drawer-body">
                {loading ? (
                    <div className="loading">加载中...</div>
                ) : (
                    allSkills.map(skill => {
                        const mounted = chatSkills.find(item => item.skill_id === skill.skill_id)
                        const isOn = mounted?.enabled ?? false

                        return (
                            <div key={skill.skill_id} className={`skill-card ${isOn ? 'active' : ''}`}>
                                <div className="skill-card-info">
                                    <div className="skill-card-name">{skill.name}</div>
                                    <div className="skill-card-desc">{skill.description}</div>
                                    <div className="skill-card-source">{skill.source}</div>
                                </div>
                                <button
                                    className={`skill-toggle ${isOn ? 'on' : 'off'}`}
                                    onClick={() => {
                                        void toggleSkill(skill.skill_id, !isOn)
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
