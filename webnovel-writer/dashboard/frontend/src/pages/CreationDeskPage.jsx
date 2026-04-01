import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import NewBookWizard from './NewBookWizard.jsx'
import {
    createEntity,
    fetchAuthoringWorkspace,
    formatAuthoringApiError,
    saveEntityDraft,
} from '../api/authoring.js'

// ---------------------------------------------------------------------------
// Section definitions – the three creative entity groups
// ---------------------------------------------------------------------------

const SECTIONS = [
    { key: 'outline', label: '大纲', entityType: 'outline', icon: '📜' },
    { key: 'setting', label: '设定集', entityType: 'setting', icon: '⚙️' },
    { key: 'canon_entry', label: 'Canon', entityType: 'canon_entry', icon: '📖' },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createFormState(entity) {
    return {
        title: entity?.title || '',
        body: entity?.body || '',
    }
}

export default function CreationDeskPage() {
    // -- wizard state (from T9) -------------------------------------------------
    const [showWizard, setShowWizard] = useState(false)
    const [successNotice, setSuccessNotice] = useState('')

    // -- workspace state --------------------------------------------------------
    const [workspace, setWorkspace] = useState(null)
    const [selectedNodeId, setSelectedNodeId] = useState('')
    const [formState, setFormState] = useState(createFormState(null))
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [creating, setCreating] = useState('')
    const [errorMessage, setErrorMessage] = useState('')
    const [notice, setNotice] = useState({ tone: '', message: '' })
    const [expandedSections, setExpandedSections] = useState({
        outline: true,
        setting: true,
        canon_entry: true,
    })

    // -- data loading -----------------------------------------------------------
    const loadWorkspace = useCallback(async preferredNodeId => {
        setLoading(true)
        setErrorMessage('')
        try {
            const payload = await fetchAuthoringWorkspace()
            const nextId =
                preferredNodeId && payload?.entities?.[preferredNodeId]
                    ? preferredNodeId
                    : payload?.selectedNodeId || payload?.nodes?.[0]?.id || ''
            setWorkspace(payload)
            setSelectedNodeId(nextId)
        } catch (error) {
            setErrorMessage(formatAuthoringApiError(error))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void loadWorkspace('')
    }, [loadWorkspace])

    // -- derived data -----------------------------------------------------------
    const selectedEntity = useMemo(
        () => workspace?.entities?.[selectedNodeId] || null,
        [selectedNodeId, workspace],
    )

    // Reset form when selection changes
    useEffect(() => {
        setFormState(createFormState(selectedEntity))
        setNotice(current =>
            current.tone === 'error' ? { tone: '', message: '' } : current,
        )
    }, [selectedEntity])

    // Group entities by type for tree navigation
    const entitiesByType = useMemo(() => {
        const groups = { outline: [], setting: [], canon_entry: [] }
        if (!workspace?.entities) return groups
        Object.values(workspace.entities).forEach(entity => {
            if (groups[entity.entityType]) {
                groups[entity.entityType].push(entity)
            }
        })
        // Sort each group by position
        Object.values(groups).forEach(list =>
            list.sort((a, b) => (a.position || 0) - (b.position || 0)),
        )
        return groups
    }, [workspace])

    const bookTitle = workspace?.book?.title || '未加载书籍'

    // -- actions ----------------------------------------------------------------

    const handleSave = useCallback(async () => {
        if (!workspace?.book?.bookId || !selectedEntity) return
        setSaving(true)
        setNotice({ tone: '', message: '' })
        try {
            await saveEntityDraft({
                bookId: workspace.book.bookId,
                entityType: selectedEntity.entityType,
                entityId: selectedEntity.entityId,
                version: selectedEntity.version,
                title: formState.title,
                body: formState.body,
                metadata: selectedEntity.metadata,
            })
            setNotice({ tone: 'success', message: '保存成功！' })
            await loadWorkspace(selectedEntity.entityId)
        } catch (error) {
            setNotice({ tone: 'error', message: formatAuthoringApiError(error) })
        } finally {
            setSaving(false)
        }
    }, [formState.body, formState.title, loadWorkspace, selectedEntity, workspace])

    const handleCreate = useCallback(
        async entityType => {
            if (!workspace?.book?.bookId) return
            setCreating(entityType)
            setNotice({ tone: '', message: '' })
            try {
                const result = await createEntity({
                    bookId: workspace.book.bookId,
                    entityType,
                    title: '',
                    body: '',
                })
                const newId =
                    result?.outline_id ||
                    result?.setting_id ||
                    result?.canon_id ||
                    result?.plot_id ||
                    result?.entity_id ||
                    ''
                if (newId) {
                    await loadWorkspace(newId)
                    setNotice({ tone: 'success', message: '新建成功，已选中新条目。' })
                } else {
                    await loadWorkspace('')
                }
            } catch (error) {
                setNotice({ tone: 'error', message: formatAuthoringApiError(error) })
            } finally {
                setCreating('')
            }
        },
        [loadWorkspace, workspace],
    )

    function toggleSection(key) {
        setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }))
    }

    function handleWizardSuccess() {
        setShowWizard(false)
        setSuccessNotice('书籍项目创建成功！')
        setTimeout(() => setSuccessNotice(''), 4000)
    }

    // -- render: tree section ---------------------------------------------------

    function renderSection(section) {
        const items = entitiesByType[section.key] || []
        const expanded = expandedSections[section.key]

        return (
            <div key={section.key} className="creation-desk-section">
                <button
                    type="button"
                    className="creation-desk-section-header"
                    onClick={() => toggleSection(section.key)}
                    aria-expanded={expanded}
                >
                    <span className="creation-desk-section-label">
                        <span className="creation-desk-section-icon">{section.icon}</span>
                        {section.label}
                    </span>
                    <span className="creation-desk-section-count">
                        {items.length}
                        <span className="creation-desk-chevron">{expanded ? '▾' : '▸'}</span>
                    </span>
                </button>
                {expanded ? (
                    <div className="creation-desk-section-list">
                        {items.length === 0 ? (
                            <div className="creation-desk-empty-item">暂无条目</div>
                        ) : (
                            items.map(entity => (
                                <button
                                    key={entity.entityId}
                                    type="button"
                                    className={`workspace-tree-item ${selectedNodeId === entity.entityId ? 'active' : ''}`}
                                    onClick={() => setSelectedNodeId(entity.entityId)}
                                >
                                    <span className="workspace-tree-item-label">
                                        {entity.title || '（无标题）'}
                                    </span>
                                    <span className="workspace-tree-item-meta">
                                        v{entity.version}
                                    </span>
                                </button>
                            ))
                        )}
                    </div>
                ) : null}
            </div>
        )
    }

    // -- render: editor panel ---------------------------------------------------

    function renderEditor() {
        if (!selectedEntity) {
            return (
                <div className="card empty-state">
                    <p>请从左侧选择一个条目进行编辑，或点击「新建」创建新内容。</p>
                </div>
            )
        }

        const sectionLabel =
            SECTIONS.find(s => s.entityType === selectedEntity.entityType)?.label ||
            selectedEntity.entityType

        return (
            <div className="card">
                <div className="card-header">
                    <span className="card-title">
                        {formState.title || '（无标题）'}
                    </span>
                    <span className={`card-badge ${selectedEntity.supportsRevisions ? 'badge-blue' : 'badge-amber'}`}>
                        {sectionLabel} · v{selectedEntity.version}
                    </span>
                </div>
                <div className="settings-provider-form">
                    <label className="settings-field">
                        <span className="settings-field-label">标题</span>
                        <input
                            aria-label="标题"
                            className="settings-input"
                            value={formState.title}
                            onChange={e =>
                                setFormState(prev => ({ ...prev, title: e.target.value }))
                            }
                        />
                    </label>
                    <label className="settings-field">
                        <span className="settings-field-label">正文</span>
                        <textarea
                            aria-label="正文"
                            className="settings-input workspace-editor-textarea"
                            value={formState.body}
                            onChange={e =>
                                setFormState(prev => ({ ...prev, body: e.target.value }))
                            }
                        />
                    </label>
                    <div className="settings-provider-actions">
                        <button
                            className="page-btn"
                            type="button"
                            onClick={() => void loadWorkspace(selectedEntity.entityId)}
                            disabled={loading || saving}
                        >
                            刷新
                        </button>
                        <button
                            className="new-chat-btn settings-save-btn"
                            type="button"
                            onClick={() => void handleSave()}
                            disabled={saving}
                        >
                            {saving ? '保存中...' : '保存'}
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    // -- main render ------------------------------------------------------------

    return (
        <PageScaffold
            title="创作台"
            badge={loading ? '加载中' : bookTitle}
        >
            {/* Wizard success notice */}
            {successNotice ? (
                <div className="settings-notice settings-notice-success">{successNotice}</div>
            ) : null}

            {/* Header actions */}
            <div className="card">
                <div className="card-header">
                    <span className="card-title">书籍管理</span>
                    <button
                        className="new-chat-btn"
                        type="button"
                        onClick={() => setShowWizard(true)}
                    >
                        + 新建书籍
                    </button>
                </div>
            </div>

            {/* API error */}
            {errorMessage ? (
                <div className="settings-notice settings-notice-error" role="alert">
                    {errorMessage}
                </div>
            ) : null}

            {/* Action notice */}
            {notice.message ? (
                <div
                    className={`settings-notice ${notice.tone === 'error' ? 'settings-notice-error' : 'settings-notice-success'}`}
                    role={notice.tone === 'error' ? 'alert' : 'status'}
                >
                    {notice.message}
                </div>
            ) : null}

            {/* Loading */}
            {loading ? <div className="loading">工作区加载中...</div> : null}

            {/* Main workspace */}
            {!loading && workspace ? (
                <div className="workspace-layout">
                    {/* Left panel: tree navigation */}
                    <aside className="card workspace-tree-card">
                        <div className="card-header">
                            <span className="card-title">内容导航</span>
                            <button
                                className="page-btn"
                                type="button"
                                onClick={() => void loadWorkspace(selectedNodeId)}
                                disabled={saving}
                            >
                                刷新
                            </button>
                        </div>

                        {SECTIONS.map(section => renderSection(section))}

                        {/* Create buttons */}
                        <div className="creation-desk-create-buttons">
                            {SECTIONS.map(section => (
                                <button
                                    key={section.key}
                                    className="page-btn"
                                    type="button"
                                    onClick={() => void handleCreate(section.entityType)}
                                    disabled={creating !== ''}
                                >
                                    {creating === section.entityType
                                        ? '创建中...'
                                        : `+ 新建${section.label}`}
                                </button>
                            ))}
                        </div>
                    </aside>

                    {/* Right panel: editor */}
                    <section className="workspace-detail-column">
                        {renderEditor()}
                    </section>
                </div>
            ) : null}

            {/* New book wizard modal */}
            {showWizard ? (
                <NewBookWizard
                    onClose={() => setShowWizard(false)}
                    onSuccess={handleWizardSuccess}
                />
            ) : null}
        </PageScaffold>
    )
}
