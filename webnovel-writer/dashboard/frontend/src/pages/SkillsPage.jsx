import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    classifySkillsError,
    createSkill,
    deleteSkill,
    generateSkillDraft,
    listSkills,
} from '../api/skills.js'
import { fetchRuntimeProfile } from '../api/runtime.js'

const DEFAULT_SKILL_FORM = {
    skill_id: '',
    name: '',
    description: '',
    instruction_template: '',
}

const CHAT_STEPS = [
    {
        field: 'skill_id',
        label: 'Skill ID',
        prompt: '先给这个技能一个稳定的 Skill ID（推荐小写连字符，例如 scene-beats）。',
    },
    {
        field: 'name',
        label: '名称',
        prompt: '接着填写用户在 Skills Registry 里会看到的名称。',
    },
    {
        field: 'description',
        label: '描述',
        prompt: '再补一行描述，说明这个技能负责什么。',
    },
    {
        field: 'instruction_template',
        label: '模板指令',
        prompt: '最后粘贴模板指令，可以直接输入多行内容。',
    },
]

const INITIAL_CHAT_MESSAGES = [
    {
        role: 'assistant',
        content: '这是一个技能草稿助手。你可以让模型直接生成结构化草稿，也可以继续手动逐项写入；整个过程不会创建真实 Chat 会话。',
    },
    {
        role: 'assistant',
        content: '可以直接描述你想做的 skill，例如“帮我做一个擅长拆章节节拍的技能”；如果你更想手动填字段，也可以继续按顺序输入。',
    },
]

const STRUCTURED_FIELD_PATTERNS = [
    {
        field: 'skill_id',
        pattern: /^\s*(?:skill[\s_-]*id|skill_id|id)\s*:\s*(.+)$/i,
    },
    {
        field: 'name',
        pattern: /^\s*(?:name|名称)\s*:\s*(.+)$/i,
    },
    {
        field: 'description',
        pattern: /^\s*(?:description|描述)\s*:\s*(.+)$/i,
    },
    {
        field: 'instruction_template',
        pattern: /^\s*(?:instruction[\s_-]*template|instruction_template|模板指令)\s*:\s*([\s\S]+)$/i,
    },
]

function getErrorMessage(error, fallback = '请求失败') {
    const type = classifySkillsError(error)
    const code = error?.errorCode || error?.error_code || ''
    const codeSuffix = code ? ` (${code})` : ''

    if (type === 'network') {
        return `网络连接失败，请检查服务状态后重试${codeSuffix}`
    }
    if (type === 'permission') {
        return `权限不足或工作区不匹配，请确认当前工作区配置${codeSuffix}`
    }
    if (type === 'conflict') {
        return `存在资源冲突，请刷新后重试${codeSuffix}`
    }
    if (type === 'validation') {
        return `${error?.message || '请求参数不合法'}${codeSuffix}`
    }
    return `${error?.message || fallback}${codeSuffix}`
}

function getErrorBadge(error) {
    const type = classifySkillsError(error)
    if (type === 'network') return '网络错误'
    if (type === 'permission') return '权限错误'
    if (type === 'conflict') return '冲突错误'
    if (type === 'validation') return '参数错误'
    return '请求错误'
}

function formatDateTime(value) {
    if (!value) return '-'
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return String(value)
    return parsed.toLocaleString()
}

function getNextChatStep(form) {
    return CHAT_STEPS.find(step => !String(form?.[step.field] || '').trim()) || null
}

function extractStructuredDraft(rawValue) {
    const normalizedValue = String(rawValue || '').trim()
    if (!normalizedValue) {
        return {}
    }

    return STRUCTURED_FIELD_PATTERNS.reduce((draft, entry) => {
        const match = normalizedValue.match(entry.pattern)
        if (!match) {
            return draft
        }
        return {
            ...draft,
            [entry.field]: match[1].trim(),
        }
    }, {})
}

function resolveChatDraftUpdate(rawValue, form) {
    const normalizedValue = String(rawValue || '').trim()
    if (!normalizedValue) {
        return {}
    }

    const structuredUpdate = extractStructuredDraft(normalizedValue)
    if (Object.keys(structuredUpdate).length > 0) {
        return structuredUpdate
    }

    const nextStep = getNextChatStep(form)
    if (!nextStep) {
        return { instruction_template: normalizedValue }
    }

    return {
        [nextStep.field]: normalizedValue,
    }
}

function getDraftPreview(form) {
    return JSON.stringify({
        skill_id: form.skill_id,
        name: form.name,
        description: form.description,
        instruction_template: form.instruction_template,
    }, null, 2)
}

function normalizeSkillDraft(form) {
    return {
        skill_id: String(form?.skill_id || '').trim(),
        name: String(form?.name || '').trim(),
        description: String(form?.description || '').trim(),
        instruction_template: String(form?.instruction_template || '').trim(),
    }
}

function buildAssistantReply(update, nextForm) {
    const changedFields = CHAT_STEPS.filter(step => Object.prototype.hasOwnProperty.call(update, step.field))
    if (changedFields.length === 0) {
        const nextStep = getNextChatStep(nextForm) || CHAT_STEPS[CHAT_STEPS.length - 1]
        return `还没有写入任何字段，请先提供${nextStep.label}。`
    }

    const changedLabels = changedFields.map(step => step.label).join('、')
    const nextStep = getNextChatStep(nextForm)
    if (!nextStep) {
        return `已更新 ${changedLabels}。右侧结构化草稿已经齐全，现在可以直接保存，或继续覆盖后重新创建。`
    }

    return `已更新 ${changedLabels}。下一步请提供${nextStep.label}。`
}

export default function SkillsPage() {
    const [skills, setSkills] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [successMessage, setSuccessMessage] = useState('')
    const [submitting, setSubmitting] = useState(false)
    const [generatingDraft, setGeneratingDraft] = useState(false)
    const [deletingSkillId, setDeletingSkillId] = useState('')
    const [form, setForm] = useState(DEFAULT_SKILL_FORM)
    const [chatInput, setChatInput] = useState('')
    const [chatMessages, setChatMessages] = useState(INITIAL_CHAT_MESSAGES)
    const [runtimeGeneration, setRuntimeGeneration] = useState({ skillDraftAvailable: false, provider: '', model: '' })

    const refresh = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await listSkills()
            setSkills(response.items)
        } catch (err) {
            setError(err)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void refresh()
    }, [refresh])

    useEffect(() => {
        let cancelled = false

        async function loadRuntimeProfile() {
            try {
                const profile = await fetchRuntimeProfile()
                if (!cancelled) {
                    setRuntimeGeneration({
                        skillDraftAvailable: Boolean(profile?.generation?.skill_draft_available),
                        provider: String(profile?.generation?.provider || ''),
                        model: String(profile?.generation?.model || ''),
                    })
                }
            } catch {
                if (!cancelled) {
                    setRuntimeGeneration({ skillDraftAvailable: false, provider: '', model: '' })
                }
            }
        }

        void loadRuntimeProfile()
        return () => {
            cancelled = true
        }
    }, [])

    const enabledCount = useMemo(
        () => skills.filter(skill => skill.enabled).length,
        [skills],
    )

    const handleFieldChange = useCallback((field, value) => {
        setForm(current => ({ ...current, [field]: value }))
    }, [])

    const nextChatStep = useMemo(() => getNextChatStep(form), [form])
    const draftPreview = useMemo(() => getDraftPreview(form), [form])
    const hasStructuredChatInput = useMemo(
        () => Object.keys(extractStructuredDraft(chatInput)).length > 0,
        [chatInput],
    )
    const completedFieldCount = useMemo(
        () => CHAT_STEPS.filter(step => String(form[step.field] || '').trim()).length,
        [form],
    )

    const handleLocalDraftWrite = useCallback(event => {
        event.preventDefault()

        const normalizedInput = chatInput.trim()
        if (!normalizedInput) {
            return
        }

        const draftUpdate = resolveChatDraftUpdate(normalizedInput, form)
        const nextForm = { ...form, ...draftUpdate }

        setError(null)
        setSuccessMessage('')
        setForm(nextForm)
        setChatMessages(current => ([
            ...current,
            { role: 'user', content: normalizedInput },
            { role: 'assistant', content: buildAssistantReply(draftUpdate, nextForm) },
        ]))
        setChatInput('')
    }, [chatInput, form])

    const handleGenerateDraft = useCallback(async () => {
        const normalizedInput = chatInput.trim()
        if (!normalizedInput || generatingDraft) {
            return
        }

        if (Object.keys(extractStructuredDraft(normalizedInput)).length > 0) {
            handleLocalDraftWrite({ preventDefault() {} })
            return
        }

        if (!runtimeGeneration.skillDraftAvailable) {
            return
        }

        const currentDraft = normalizeSkillDraft(form)
        setGeneratingDraft(true)
        setError(null)
        setSuccessMessage('')
        setChatMessages(current => ([
            ...current,
            { role: 'user', content: normalizedInput },
        ]))

        try {
            const response = await generateSkillDraft({
                prompt: normalizedInput,
                currentDraft,
            })
            setForm(response.draft)
            setChatMessages(current => ([
                ...current,
                { role: 'assistant', content: response.reply || '已根据你的要求生成新的 skill 草稿。' },
            ]))
            setChatInput('')
        } catch (err) {
            setError(err)
            setChatMessages(current => ([
                ...current,
                { role: 'assistant', content: '这次模型生成失败了。你可以检查运行时配置后重试，或先改用右侧表单和“直接写入草稿”。' },
            ]))
        } finally {
            setGeneratingDraft(false)
        }
    }, [chatInput, form, generatingDraft, handleLocalDraftWrite, runtimeGeneration.skillDraftAvailable])

    const handleResetDraft = useCallback(() => {
        setForm(DEFAULT_SKILL_FORM)
        setChatInput('')
        setChatMessages(INITIAL_CHAT_MESSAGES)
        setError(null)
        setSuccessMessage('')
    }, [])

    const handleCreate = useCallback(async event => {
        event.preventDefault()
        setSubmitting(true)
        setError(null)
        setSuccessMessage('')
        try {
            const normalizedForm = normalizeSkillDraft(form)
            setForm(normalizedForm)
            const created = await createSkill(normalizedForm)
            setSkills(current => [created, ...current.filter(item => item.skill_id !== created.skill_id)])
            setSuccessMessage('技能已创建，现在可以在 Chat 中挂载。当前草稿会保留，便于继续调整后重新创建，或清空后开始下一份。')
        } catch (err) {
            setError(err)
        } finally {
            setSubmitting(false)
        }
    }, [form])

    const handleDelete = useCallback(async skill => {
        setDeletingSkillId(skill.skill_id)
        setError(null)
        setSuccessMessage('')
        try {
            await deleteSkill(skill.skill_id)
            setSkills(current => current.filter(item => item.skill_id !== skill.skill_id))
            setSuccessMessage(`技能 ${skill.name || skill.skill_id} 已删除，并已从相关 Chat 中卸载。`)
        } catch (err) {
            setError(err)
        } finally {
            setDeletingSkillId('')
        }
    }, [])

    return (
        <PageScaffold
            title="技能管理"
            badge={`${enabledCount}/${skills.length} 已启用`}
            description="在当前项目里维护模板技能库。新建后的项目技能会自动出现在 Chat 的 Skills 抽屉中。"
        >
            <div className="card">
                <div className="card-header">
                    <span className="card-title">模板技能库</span>
                    <span className="card-badge badge-purple">Workspace</span>
                </div>
                <p className="settings-panel-copy">
                    Phase 1 只管理模板与元数据，不执行插件逻辑。删除项目技能时，会同步将它从已挂载的 Chat 中移除，避免留下悬空约束。
                </p>
            </div>

            {error ? (
                <div className="card" role="alert">
                    <div className="card-header">
                        <span className="card-title">错误反馈</span>
                        <span className="card-badge badge-red">{getErrorBadge(error)}</span>
                    </div>
                    <p style={{ margin: 0 }}>{getErrorMessage(error, '操作失败')}</p>
                </div>
            ) : null}

            {successMessage ? (
                <div className="settings-notice settings-notice-success" role="status">{successMessage}</div>
            ) : null}

            <div className="card settings-provider-card">
                <div className="card-header">
                    <div>
                        <span className="card-title">创建技能</span>
                        <p className="settings-panel-intro">左侧用本地对话逐步补全字段，右侧随时查看并手动编辑结构化草稿。</p>
                    </div>
                    <span className="card-badge badge-blue">Chat draft</span>
                </div>
                <div className="skills-create-layout">
                    <div className="skills-chat-panel">
                        <div className="skills-chat-log" aria-live="polite">
                            {chatMessages.map((message, index) => (
                                <div key={`${message.role}-${index}`} className={`msg-bubble ${message.role === 'assistant' ? 'assistant' : 'user'}`}>
                                    <span className="msg-role">{message.role === 'assistant' ? 'DRAFT BOT' : 'YOU'}</span>
                                    <div className="msg-content">
                                        <p className="msg-text">{message.content}</p>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <form className="composer skills-chat-composer" onSubmit={event => {
                            event.preventDefault()
                            void handleGenerateDraft()
                        }}>
                            <label className="settings-field">
                                <span className="settings-field-label">技能创建对话输入</span>
                                <textarea
                                    aria-label="技能创建对话输入"
                                    className="composer-input"
                                    value={chatInput}
                                     placeholder={runtimeGeneration.skillDraftAvailable ? '描述你想让模型生成或更新的 skill；输入 field: value 时会直接本地覆盖对应字段。' : (nextChatStep ? nextChatStep.prompt : '草稿已完整；如需修改，请使用 field: value 覆盖，或直接调整右侧表单。')}
                                     onChange={event => setChatInput(event.target.value)}
                                 />
                             </label>
                             <div className="skills-actions-row">
                                <button className="composer-send" type="submit" disabled={generatingDraft || (!runtimeGeneration.skillDraftAvailable && !hasStructuredChatInput)}>
                                    {generatingDraft ? '生成中...' : 'AI 生成草稿'}
                                </button>
                                <button className="page-btn" type="button" onClick={handleLocalDraftWrite} disabled={generatingDraft}>
                                    直接写入草稿
                                </button>
                            </div>
                        </form>

                        <p className="skills-helper-copy">
                            {runtimeGeneration.skillDraftAvailable
                                ? `当前模型：${runtimeGeneration.provider || 'unknown'}${runtimeGeneration.model ? ` / ${runtimeGeneration.model}` : ''}。你可以自然语言描述需求；如果输入 name: Scene Beats 这类字段，提交时会直接本地覆盖。`
                                : '当前未检测到可用的真实生成模型；你仍然可以使用“直接写入草稿”按顺序补全字段。'}
                        </p>
                    </div>

                    <div className="skills-draft-panel">
                        <div className="skill-card skills-draft-preview-card">
                            <div className="card-header skills-draft-preview-header">
                                <span className="card-title">结构化草稿</span>
                                <span className={`card-badge ${completedFieldCount === CHAT_STEPS.length ? 'badge-green' : 'badge-amber'}`}>
                                    {completedFieldCount}/{CHAT_STEPS.length} 已完成
                                </span>
                            </div>
                            <p className="settings-panel-copy">右侧草稿与下方保存表单实时同步。保存后不会清空，便于把它当作下一份 skill 的起点继续调整，或清空后重建。</p>
                            <pre className="skills-draft-code">{draftPreview}</pre>
                        </div>

                        <form className="settings-provider-form" onSubmit={handleCreate}>
                            <div className="settings-form-grid">
                                <label className="settings-field">
                                    <span className="settings-field-label">Skill ID</span>
                                    <input className="settings-input" type="text" value={form.skill_id} onChange={event => handleFieldChange('skill_id', event.target.value)} />
                                </label>
                                <label className="settings-field">
                                    <span className="settings-field-label">名称</span>
                                    <input className="settings-input" type="text" value={form.name} onChange={event => handleFieldChange('name', event.target.value)} />
                                </label>
                                <label className="settings-field settings-field-wide">
                                    <span className="settings-field-label">描述</span>
                                    <input className="settings-input" type="text" value={form.description} onChange={event => handleFieldChange('description', event.target.value)} />
                                </label>
                                <label className="settings-field settings-field-wide">
                                    <span className="settings-field-label">模板指令</span>
                                    <textarea className="settings-input skills-template-input" value={form.instruction_template} onChange={event => handleFieldChange('instruction_template', event.target.value)} />
                                </label>
                            </div>
                            <div className="skills-actions-row">
                                <button className="page-btn" type="submit" disabled={submitting}>{submitting ? '创建中...' : '创建技能'}</button>
                                <button className="page-btn" type="button" onClick={handleResetDraft} disabled={submitting}>清空草稿</button>
                                <span className="skills-helper-copy">使用小写连字符 ID，例如 <code>scene-beats</code>。</span>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <span className="card-title">Skills Registry</span>
                    <button className="page-btn" onClick={() => void refresh()} disabled={loading}>
                        {loading ? '加载中...' : '刷新'}
                    </button>
                </div>
                <div className="table-wrap">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Skill ID</th>
                                <th>名称</th>
                                <th>描述</th>
                                <th>来源</th>
                                <th>更新时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={6}>加载中...</td>
                                </tr>
                            ) : null}
                            {!loading && skills.length === 0 ? (
                                <tr>
                                    <td colSpan={6}>暂无项目技能。</td>
                                </tr>
                            ) : null}
                            {!loading
                                ? skills.map(skill => (
                                      <tr key={skill.skill_id}>
                                          <td>{skill.skill_id}</td>
                                          <td>{skill.name}</td>
                                          <td>{skill.description || '-'}</td>
                                          <td>{skill.source || 'workspace'}</td>
                                          <td>{formatDateTime(skill.updated_at)}</td>
                                          <td>
                                              <button className="page-btn page-btn-danger" type="button" onClick={() => void handleDelete(skill)} disabled={deletingSkillId === skill.skill_id} aria-label={`删除 ${skill.name || skill.skill_id}`}>
                                                  {deletingSkillId === skill.skill_id ? '删除中...' : '删除'}
                                              </button>
                                          </td>
                                      </tr>
                                  ))
                                : null}
                        </tbody>
                    </table>
                </div>
            </div>
        </PageScaffold>
    )
}
