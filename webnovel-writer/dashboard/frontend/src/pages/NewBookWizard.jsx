import { useState } from 'react'
import { initBook } from '../api/books.js'

// ---------------------------------------------------------------------------
// Step definitions – field layout per step
// ---------------------------------------------------------------------------

const STEPS = [
    {
        title: '基础信息',
        description: '书名、类型与目录是必填项，其余可选。',
        fields: [
            { name: 'title', label: '书名', required: true, placeholder: '例：斗破苍穹' },
            { name: 'genre', label: '类型', required: true, placeholder: '例：玄幻 / 都市 / 仙侠' },
            { name: 'project_dir', label: '项目目录', required: true, placeholder: '例：./my-novel' },
            { name: 'protagonist_name', label: '主角名', placeholder: '例：萧炎' },
            { name: 'target_words', label: '目标字数', type: 'number', placeholder: '2000000' },
            { name: 'target_chapters', label: '目标章数', type: 'number', placeholder: '600' },
        ],
    },
    {
        title: '世界观',
        description: '定义你的世界底层结构，全部可选。',
        fields: [
            { name: 'world_scale', label: '世界规模', placeholder: '例：多元宇宙 / 单一大陆' },
            { name: 'factions', label: '势力分布', placeholder: '例：三大帝国、五大宗门' },
            { name: 'power_system_type', label: '力量体系类型', placeholder: '例：修炼 / 异能 / 魔法' },
            { name: 'social_class', label: '社会阶层', placeholder: '例：修士-凡人二元制' },
            { name: 'resource_distribution', label: '资源分配', placeholder: '例：灵石矿脉垄断' },
            { name: 'currency_system', label: '货币体系', placeholder: '例：灵石、金币双轨制' },
            { name: 'currency_exchange', label: '货币兑换', placeholder: '例：1 上品灵石 = 100 中品' },
            { name: 'sect_hierarchy', label: '门派等级', placeholder: '例：外门→内门→核心→长老' },
            { name: 'cultivation_chain', label: '修炼境界', placeholder: '例：练气→筑基→金丹→元婴' },
            { name: 'cultivation_subtiers', label: '境界细分', placeholder: '例：每境九层' },
        ],
    },
    {
        title: '角色',
        description: '塑造你的人物体系，全部可选。',
        fields: [
            { name: 'protagonist_desire', label: '主角欲望', placeholder: '例：成为最强，守护家人' },
            { name: 'protagonist_flaw', label: '主角缺陷', placeholder: '例：过于自信，容易冲动' },
            { name: 'protagonist_archetype', label: '主角原型', placeholder: '例：废柴逆袭 / 天才崛起' },
            { name: 'protagonist_structure', label: '主角结构', placeholder: '例：单一主角 / 双主角' },
            { name: 'heroine_config', label: '女主配置', placeholder: '例：单女主 / 多女主 / 无女主' },
            { name: 'heroine_names', label: '女主名字', placeholder: '例：萧薰儿、美杜莎' },
            { name: 'heroine_role', label: '女主定位', placeholder: '例：青梅竹马、神秘贵人' },
            { name: 'co_protagonists', label: '共同主角', placeholder: '例：药老、小医仙' },
            { name: 'co_protagonist_roles', label: '共角定位', placeholder: '例：导师、战友' },
            { name: 'antagonist_tiers', label: '反派层级', placeholder: '例：天才反派→宗主→老怪' },
            { name: 'antagonist_level', label: '反派强度', placeholder: '例：逐渐升级' },
        ],
    },
    {
        title: '金手指',
        description: '定义主角的特殊优势，全部可选。',
        fields: [
            { name: 'golden_finger_name', label: '金手指名称', placeholder: '例：随身老爷爷' },
            { name: 'golden_finger_type', label: '金手指类型', placeholder: '例：系统 / 空间 / 灵魂' },
            { name: 'golden_finger_style', label: '金手指风格', placeholder: '例：辅助型 / 战斗型' },
            { name: 'gf_visibility', label: '可见性', placeholder: '例：隐藏 / 半公开' },
            { name: 'gf_irreversible_cost', label: '不可逆代价', placeholder: '例：消耗寿命 / 消耗灵魂力' },
        ],
    },
    {
        title: '发布',
        description: '核心卖点与目标读者，全部可选。',
        fields: [
            { name: 'core_selling_points', label: '核心卖点', placeholder: '例：升级快、打脸爽、世界观宏大', multiline: true },
            { name: 'target_reader', label: '目标读者', placeholder: '例：18-30 岁男性，喜欢升级流' },
            { name: 'platform', label: '发布平台', placeholder: '例：起点 / 番茄 / 刺猬猫' },
        ],
    },
]

// ---------------------------------------------------------------------------
// Default form state (all fields empty / sensible defaults)
// ---------------------------------------------------------------------------

function buildDefaultFormState() {
    const state = {}
    for (const step of STEPS) {
        for (const field of step.fields) {
            state[field.name] = field.type === 'number' ? '' : ''
        }
    }
    return state
}

// ---------------------------------------------------------------------------
// Step indicator dots
// ---------------------------------------------------------------------------

function StepIndicator({ current, total }) {
    return (
        <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginBottom: 20 }}>
            {Array.from({ length: total }, (_, i) => (
                <div
                    key={i}
                    style={{
                        width: i === current ? 24 : 8,
                        height: 8,
                        borderRadius: 4,
                        background: i === current ? '#d4a74a' : i < current ? '#8b7a4a' : '#3a3526',
                        transition: 'all 0.2s ease',
                    }}
                />
            ))}
        </div>
    )
}

// ---------------------------------------------------------------------------
// The wizard component
// ---------------------------------------------------------------------------

export default function NewBookWizard({ onClose, onSuccess }) {
    const [step, setStep] = useState(0)
    const [form, setForm] = useState(buildDefaultFormState)
    const [errors, setErrors] = useState({})
    const [submitting, setSubmitting] = useState(false)
    const [apiError, setApiError] = useState('')

    const currentStep = STEPS[step]
    const isLast = step === STEPS.length - 1
    const isFirst = step === 0

    // -- field change helper -------------------------------------------------
    function handleChange(name, value) {
        setForm(prev => ({ ...prev, [name]: value }))
        // clear validation error on edit
        if (errors[name]) {
            setErrors(prev => {
                const next = { ...prev }
                delete next[name]
                return next
            })
        }
    }

    // -- validate current step (only step 0 has required fields) -------------
    function validateStep() {
        if (step !== 0) return true
        const newErrors = {}
        for (const field of currentStep.fields) {
            if (field.required && !String(form[field.name]).trim()) {
                newErrors[field.name] = `${field.label}不能为空`
            }
        }
        setErrors(newErrors)
        return Object.keys(newErrors).length === 0
    }

    // -- navigation ----------------------------------------------------------
    function handleNext() {
        if (!validateStep()) return
        setStep(s => s + 1)
    }

    function handlePrev() {
        setStep(s => s - 1)
    }

    // -- submit --------------------------------------------------------------
    async function handleSubmit() {
        if (!validateStep()) return
        setSubmitting(true)
        setApiError('')

        // Build payload — convert number fields, trim strings, omit empties
        const payload = {}
        for (const s of STEPS) {
            for (const field of s.fields) {
                let value = form[field.name]
                if (field.type === 'number') {
                    const num = Number(value)
                    if (Number.isFinite(num) && num > 0) {
                        payload[field.name] = num
                    }
                } else {
                    value = String(value).trim()
                    if (value) payload[field.name] = value
                }
            }
        }

        // Ensure required fields are present
        if (!payload.title || !payload.genre || !payload.project_dir) {
            setApiError('书名、类型和项目目录为必填项。')
            setSubmitting(false)
            return
        }

        try {
            await initBook(payload)
            onSuccess?.()
        } catch (err) {
            const msg = err?.status === 409
                ? '项目目录已存在，请选择其他路径。'
                : err?.message || '创建失败，请稍后重试。'
            setApiError(msg)
        } finally {
            setSubmitting(false)
        }
    }

    // -- render --------------------------------------------------------------
    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                zIndex: 1000,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(0,0,0,0.55)',
                backdropFilter: 'blur(4px)',
            }}
            onClick={e => { if (e.target === e.currentTarget) onClose() }}
        >
            <div
                className="card"
                style={{
                    width: 'min(580px, 92vw)',
                    maxHeight: '85vh',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                }}
            >
                {/* header */}
                <div className="card-header" style={{ flexShrink: 0 }}>
                    <span className="card-title">新建书籍</span>
                    <StepIndicator current={step} total={STEPS.length} />
                </div>

                {/* step info */}
                <div style={{ padding: '0 20px', flexShrink: 0 }}>
                    <h3 style={{ margin: '0 0 4px', fontSize: 16, color: '#e8dcc8' }}>
                        {step + 1}. {currentStep.title}
                    </h3>
                    <p style={{ margin: '0 0 16px', fontSize: 12, color: '#8b7a5e' }}>
                        {currentStep.description}
                    </p>
                </div>

                {/* scrollable form area */}
                <div className="settings-form-grid" style={{ padding: '0 20px', overflowY: 'auto', flex: 1 }}>
                    {currentStep.fields.map(field => (
                        <label key={field.name} className={`settings-field${field.multiline ? ' settings-field-wide' : ''}`}>
                            <span className="settings-field-label">
                                {field.label}
                                {field.required ? <span style={{ color: '#c0392b' }}>*</span> : null}
                            </span>
                            {field.multiline ? (
                                <textarea
                                    className="settings-input"
                                    name={field.name}
                                    placeholder={field.placeholder}
                                    value={form[field.name]}
                                    onChange={e => handleChange(field.name, e.target.value)}
                                    rows={3}
                                    style={{ resize: 'vertical' }}
                                />
                            ) : (
                                <input
                                    className="settings-input"
                                    name={field.name}
                                    type={field.type || 'text'}
                                    placeholder={field.placeholder}
                                    value={form[field.name]}
                                    onChange={e => handleChange(field.name, e.target.value)}
                                />
                            )}
                            {errors[field.name] ? (
                                <span style={{ color: '#c0392b', fontSize: 11, marginTop: 2 }}>{errors[field.name]}</span>
                            ) : null}
                        </label>
                    ))}
                </div>

                {/* error / notice */}
                {apiError ? (
                    <div className="settings-notice settings-notice-error" style={{ margin: '8px 20px 0' }}>{apiError}</div>
                ) : null}

                {/* footer buttons */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '16px 20px 20px', flexShrink: 0 }}>
                    <button className="page-btn" type="button" onClick={onClose} disabled={submitting}>
                        取消
                    </button>
                    {!isFirst ? (
                        <button className="page-btn" type="button" onClick={handlePrev} disabled={submitting}>
                            上一步
                        </button>
                    ) : null}
                    {isLast ? (
                        <button className="new-chat-btn" type="button" onClick={handleSubmit} disabled={submitting}>
                            {submitting ? '创建中...' : '创建'}
                        </button>
                    ) : (
                        <button className="new-chat-btn" type="button" onClick={handleNext}>
                            下一步
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}
