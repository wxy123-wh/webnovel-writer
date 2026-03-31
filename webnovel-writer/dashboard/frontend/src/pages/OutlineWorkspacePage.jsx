import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    confirmProposal,
    fetchAuthoringWorkspace,
    fetchRevisionDiff,
    formatAuthoringApiError,
    markIndexStale,
    rejectProposal,
    rebuildIndex,
    rollbackRevision,
    saveEntityDraft,
} from '../api/authoring.js'

const TAB_LABELS = {
    editor: '编辑器',
    review: '提案评审',
    history: '修订记录',
}

const EDITOR_TITLES = {
    outline: '总纲编辑器',
    plot: 'Plot 编辑器',
    event: '事件编辑器',
    scene: '场景编辑器',
    chapter: '章节编辑器',
    setting: '设定编辑器',
    canon_entry: 'Canon 编辑器',
}

function createFormState(entity) {
    return {
        title: entity?.title || '',
        body: entity?.body || '',
        metadata: entity?.metadata || {},
    }
}

function formatEntityType(entityType) {
    switch (entityType) {
        case 'outline': return 'Outline'
        case 'plot': return 'Plot'
        case 'event': return 'Event'
        case 'scene': return 'Scene'
        case 'chapter': return 'Chapter'
        case 'setting': return 'Setting'
        case 'canon_entry': return 'Canon'
        default: return entityType || 'Unknown'
    }
}

function formatDiffText(diffText) {
    if (!diffText) return ''
    return diffText
        .split('\n')
        .filter(line => line.trim() !== '')
        .join('\n')
}

function getLatestRevision(revisions) {
    if (!Array.isArray(revisions) || revisions.length === 0) {
        return null
    }
    return revisions.reduce((latest, current) => {
        if (!latest) return current
        return (current.revisionNumber || 0) > (latest.revisionNumber || 0) ? current : latest
    }, null)
}

export default function OutlineWorkspacePage() {
    const [workspace, setWorkspace] = useState(null)
    const [selectedNodeId, setSelectedNodeId] = useState('')
    const [activeTab, setActiveTab] = useState('editor')
    const [formState, setFormState] = useState(createFormState(null))
    const [loading, setLoading] = useState(true)
    const [busyAction, setBusyAction] = useState('')
    const [errorMessage, setErrorMessage] = useState('')
    const [notice, setNotice] = useState({ tone: '', message: '' })
    const [diffState, setDiffState] = useState({ summary: '', diffText: '' })

    const loadWorkspace = useCallback(async preferredNodeId => {
        setLoading(true)
        setErrorMessage('')
        try {
            const payload = await fetchAuthoringWorkspace()
            const nextSelectedNodeId = preferredNodeId && payload?.entities?.[preferredNodeId]
                ? preferredNodeId
                : payload?.selectedNodeId || payload?.nodes?.[0]?.id || ''
            setWorkspace(payload)
            setSelectedNodeId(nextSelectedNodeId)
        } catch (error) {
            setErrorMessage(formatAuthoringApiError(error))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void loadWorkspace('')
    }, [loadWorkspace])

    const selectedEntity = useMemo(
        () => workspace?.entities?.[selectedNodeId] || null,
        [selectedNodeId, workspace],
    )

    useEffect(() => {
        setFormState(createFormState(selectedEntity))
        setDiffState({ summary: '', diffText: '' })
        setNotice(current => current.tone === 'error' ? { tone: '', message: '' } : current)
    }, [selectedEntity])

    const bookTitle = workspace?.book?.title || '未加载书籍'
    const nodeCount = workspace?.nodes?.length || 0

    const handleActionFailure = useCallback(error => {
        setNotice({ tone: 'error', message: formatAuthoringApiError(error) })
    }, [])

    const handleSave = useCallback(async () => {
        if (!workspace?.book?.bookId || !selectedEntity) return
        setBusyAction('save')
        setNotice({ tone: '', message: '' })
        try {
            await saveEntityDraft({
                bookId: workspace.book.bookId,
                entityType: selectedEntity.entityType,
                entityId: selectedEntity.entityId,
                version: selectedEntity.version,
                title: formState.title,
                body: formState.body,
                metadata: formState.metadata,
            })
            setNotice({ tone: 'success', message: '内容已保存，工作台已刷新到最新版本。' })
            await loadWorkspace(selectedEntity.entityId)
        } catch (error) {
            handleActionFailure(error)
        } finally {
            setBusyAction('')
        }
    }, [formState.body, formState.metadata, formState.title, handleActionFailure, loadWorkspace, selectedEntity, workspace])

    const handleProposalDecision = useCallback(async (proposalId, action) => {
        if (!workspace?.book?.bookId || !selectedEntity) return
        setBusyAction(`${action}:${proposalId}`)
        setNotice({ tone: '', message: '' })
        try {
            if (action === 'confirm') {
                await confirmProposal({
                    bookId: workspace.book.bookId,
                    entityId: selectedEntity.entityId,
                    entityType: selectedEntity.entityType,
                    proposalId,
                })
            } else {
                await rejectProposal({
                    bookId: workspace.book.bookId,
                    entityId: selectedEntity.entityId,
                    entityType: selectedEntity.entityType,
                    proposalId,
                })
            }
            setNotice({ tone: 'success', message: action === 'confirm' ? '提案已确认并写入当前层级。' : '提案已拒绝，已保持当前正文不变。' })
            await loadWorkspace(selectedEntity.entityId)
        } catch (error) {
            handleActionFailure(error)
        } finally {
            setBusyAction('')
        }
    }, [handleActionFailure, loadWorkspace, selectedEntity, workspace])

    const handleViewDiff = useCallback(async revision => {
        if (!workspace?.book?.bookId || !selectedEntity || !revision) return
        const latestRevision = getLatestRevision(selectedEntity.revisions)
        if (!latestRevision) return
        setBusyAction(`diff:${revision.revisionId}`)
        setNotice({ tone: '', message: '' })
        try {
            const payload = await fetchRevisionDiff({
                bookId: workspace.book.bookId,
                entityType: selectedEntity.entityType,
                entityId: selectedEntity.entityId,
                fromRevision: revision.revisionNumber,
                toRevision: latestRevision.revisionNumber,
            })
            setDiffState({
                summary: payload.summary || '对比已加载',
                diffText: payload.diffText || payload.diff || '',
            })
        } catch (error) {
            handleActionFailure(error)
        } finally {
            setBusyAction('')
        }
    }, [handleActionFailure, selectedEntity, workspace])

    const handleRollback = useCallback(async revision => {
        if (!workspace?.book?.bookId || !selectedEntity || !revision) return
        setBusyAction(`rollback:${revision.revisionId}`)
        setNotice({ tone: '', message: '' })
        try {
            await rollbackRevision({
                bookId: workspace.book.bookId,
                entityType: selectedEntity.entityType,
                entityId: selectedEntity.entityId,
                targetRevision: revision.revisionNumber,
                version: selectedEntity.version,
            })
            setNotice({ tone: 'success', message: `已基于 ${revision.label} 创建新的当前版本。` })
            await loadWorkspace(selectedEntity.entityId)
        } catch (error) {
            handleActionFailure(error)
        } finally {
            setBusyAction('')
        }
    }, [handleActionFailure, loadWorkspace, selectedEntity, workspace])

    const handleMarkStale = useCallback(async () => {
        if (!workspace?.book?.bookId) return
        setBusyAction('mark-stale')
        setNotice({ tone: '', message: '' })
        try {
            const state = await markIndexStale({
                bookId: workspace.book.bookId,
                reason: 'manual_reset',
            })
            setNotice({ tone: 'success', message: `索引状态已更新为 ${state?.status || 'stale'}。` })
            await loadWorkspace(selectedEntity?.entityId || '')
        } catch (error) {
            handleActionFailure(error)
        } finally {
            setBusyAction('')
        }
    }, [handleActionFailure, loadWorkspace, selectedEntity?.entityId, workspace])

    const handleRebuildIndex = useCallback(async () => {
        if (!workspace?.book?.bookId) return
        setBusyAction('rebuild-index')
        setNotice({ tone: '', message: '' })
        try {
            const state = await rebuildIndex({
                bookId: workspace.book.bookId,
            })
            setNotice({ tone: 'success', message: `索引重建完成，当前状态为 ${state?.status || 'fresh'}。` })
            await loadWorkspace(selectedEntity?.entityId || '')
        } catch (error) {
            handleActionFailure(error)
        } finally {
            setBusyAction('')
        }
    }, [handleActionFailure, loadWorkspace, selectedEntity?.entityId, workspace])

    const renderIndexState = () => {
        const indexState = workspace?.indexState
        const details = indexState?.details || {}
        return (
            <div className="card workspace-summary-card">
                <div className="card-header">
                    <span className="card-title">RAG 索引状态</span>
                    <span className={`card-badge ${indexState?.status === 'fresh' ? 'badge-green' : indexState?.status === 'building' ? 'badge-blue' : indexState?.status === 'failed' ? 'badge-amber' : 'badge-purple'}`}>
                        {indexState?.status || 'unknown'}
                    </span>
                </div>
                <div className="settings-panel-copy">
                    generation: {indexState?.generation || 0} · active_generation: {details.activeGeneration ?? 'none'} · published_generation: {details.publishedGeneration ?? 'none'}
                </div>
                <div className="settings-panel-copy">
                    reason: {details.reason || 'n/a'} · artifact: {details.result?.artifact || 'n/a'}
                </div>
                <div className="settings-provider-actions">
                    <button className="page-btn" type="button" onClick={() => void handleMarkStale()} disabled={busyAction !== ''}>
                        {busyAction === 'mark-stale' ? '处理中...' : '标记为 stale'}
                    </button>
                    <button className="new-chat-btn" type="button" onClick={() => void handleRebuildIndex()} disabled={busyAction !== ''}>
                        {busyAction === 'rebuild-index' ? '重建中...' : '重建索引'}
                    </button>
                </div>
            </div>
        )
    }

    const renderEditor = () => {
        if (!selectedEntity) {
            return <div className="card empty-state"><p>请先从左侧选择一个层级节点。</p></div>
        }
        return (
            <div className="card">
                <div className="card-header">
                    <span className="card-title">{EDITOR_TITLES[selectedEntity.entityType] || '节点编辑器'}</span>
                    <span className={`card-badge ${selectedEntity.supportsRevisions ? 'badge-blue' : 'badge-amber'}`}>
                        v{selectedEntity.version}
                    </span>
                </div>
                <div className="settings-provider-form">
                    <label className="settings-field">
                        <span className="settings-field-label">标题</span>
                        <input
                            aria-label="标题"
                            className="settings-input"
                            value={formState.title}
                            onChange={event => setFormState(current => ({ ...current, title: event.target.value }))}
                        />
                    </label>
                    <label className="settings-field">
                        <span className="settings-field-label">{selectedEntity.entityType === 'chapter' ? '章节正文' : '正文'}</span>
                        <textarea
                            aria-label={selectedEntity.entityType === 'chapter' ? '章节正文' : '正文'}
                            className="settings-input workspace-editor-textarea"
                            value={formState.body}
                            onChange={event => setFormState(current => ({ ...current, body: event.target.value }))}
                        />
                    </label>
                    <div className="settings-provider-actions">
                        <button className="page-btn" type="button" onClick={() => void loadWorkspace(selectedEntity.entityId)} disabled={loading || busyAction !== ''}>
                            刷新当前节点
                        </button>
                        <button className="new-chat-btn settings-save-btn" type="button" onClick={() => void handleSave()} disabled={busyAction !== ''}>
                            {busyAction === 'save' ? '保存中...' : '保存当前内容'}
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    const renderReview = () => {
        if (!selectedEntity) {
            return <div className="card empty-state"><p>请先选择一个节点再查看提案。</p></div>
        }
        return (
            <div className="card">
                <div className="card-header">
                    <span className="card-title">待处理提案</span>
                    <span className="card-badge badge-purple">{selectedEntity.proposals.length} 条</span>
                </div>
                {selectedEntity.proposals.length === 0 ? (
                    <p className="settings-panel-copy">当前节点没有待审提案。新的结构拆分或设定候选会在这里出现。</p>
                ) : (
                    <div className="workspace-proposal-list">
                        {selectedEntity.proposals.map(proposal => (
                            <div className="workspace-proposal-card" key={proposal.proposalId}>
                                <div className="card-header">
                                    <span className="card-title">{proposal.title}</span>
                                    <span className={`card-badge ${proposal.status === 'pending' ? 'badge-amber' : 'badge-blue'}`}>{proposal.status}</span>
                                </div>
                                <p className="settings-panel-copy">{proposal.summary || '该提案暂未提供额外摘要。'}</p>
                                {proposal.canReview && proposal.status === 'pending' ? (
                                    <div className="settings-provider-actions">
                                        <button className="page-btn page-btn-danger" type="button" onClick={() => void handleProposalDecision(proposal.proposalId, 'reject')} disabled={busyAction !== ''} aria-label={`拒绝 ${proposal.title}`}>
                                            {busyAction === `reject:${proposal.proposalId}` ? '拒绝中...' : '拒绝'}
                                        </button>
                                        <button className="new-chat-btn" type="button" onClick={() => void handleProposalDecision(proposal.proposalId, 'confirm')} disabled={busyAction !== ''} aria-label={`确认 ${proposal.title}`}>
                                            {busyAction === `confirm:${proposal.proposalId}` ? '确认中...' : '确认'}
                                        </button>
                                    </div>
                                ) : (
                                    <div className="settings-notice settings-notice-error">当前提案不支持在此面板确认，请刷新后检查最新状态。</div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        )
    }

    const renderHistory = () => {
        if (!selectedEntity) {
            return <div className="card empty-state"><p>请先选择一个节点再查看修订记录。</p></div>
        }
        if (!selectedEntity.supportsRevisions) {
            return (
                <div className="card empty-state compact">
                    <p>当前节点类型不支持修订历史。只有 Outline、Plot、Chapter、Setting 可回看 diff 并触发回滚。</p>
                </div>
            )
        }
        return (
            <div className="workspace-history-grid">
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">修订列表</span>
                        <span className="card-badge badge-blue">{selectedEntity.revisions.length} 个版本</span>
                    </div>
                    {selectedEntity.revisions.length === 0 ? (
                        <p className="settings-panel-copy">当前节点还没有可用修订。</p>
                    ) : (
                        <div className="workspace-revision-list">
                            {selectedEntity.revisions.map(revision => (
                                <div className="workspace-revision-card" key={revision.revisionId}>
                                    <div>
                                        <strong>{revision.label}</strong>
                                        <div className="settings-panel-copy">实体版本 {revision.entityVersion || revision.revisionNumber}</div>
                                    </div>
                                    <div className="settings-provider-actions">
                                        <button className="page-btn" type="button" onClick={() => void handleViewDiff(revision)} disabled={busyAction !== ''} aria-label={`查看 ${revision.label} 对比`}>
                                            {busyAction === `diff:${revision.revisionId}` ? '读取中...' : '查看对比'}
                                        </button>
                                        <button className="page-btn page-btn-danger" type="button" onClick={() => void handleRollback(revision)} disabled={busyAction !== ''} aria-label={`回滚到 ${revision.label}`}>
                                            {busyAction === `rollback:${revision.revisionId}` ? '回滚中...' : '回滚到此版本'}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="card">
                    <div className="card-header">
                        <span className="card-title">版本差异</span>
                        <span className="card-badge badge-cyan">Unified Diff</span>
                    </div>
                    {diffState.summary ? <div className="settings-notice settings-notice-success">{diffState.summary}</div> : null}
                    <pre className="workspace-diff-box">{formatDiffText(diffState.diffText) || '先在左侧选择一个版本并点击“查看对比”。'}</pre>
                </div>
            </div>
        )
    }

    return (
        <PageScaffold
            title="Hierarchy Workspace"
            badge={loading ? '加载中' : `${bookTitle} · ${nodeCount} 节点`}
            description="在同一工作台中浏览严格层级、编辑正文、评审提案，并查看可回滚节点的修订历史。"
        >
            <div className="card workspace-summary-card">
                <div className="card-header">
                    <span className="card-title">当前工作区</span>
                    <span className="card-badge badge-green">Single Book</span>
                </div>
                <p className="settings-panel-copy">
                    Workspace 现在直接消费层级 / 提案 / 修订 API。任何保存、确认或回滚都会遵守后端 optimistic locking，遇到 stale/conflict 会在这里直接提示，不再默默失败。
                </p>
            </div>

            {renderIndexState()}

            {errorMessage ? (
                <div className="settings-notice settings-notice-error" role="alert">{errorMessage}</div>
            ) : null}

            {notice.message ? (
                <div className={`settings-notice ${notice.tone === 'error' ? 'settings-notice-error' : 'settings-notice-success'}`} role={notice.tone === 'error' ? 'alert' : 'status'}>
                    {notice.message}
                </div>
            ) : null}

            {loading ? <div className="loading">工作区加载中...</div> : null}

            {!loading && workspace ? (
                <div className="workspace-layout">
                    <aside className="card workspace-tree-card">
                        <div className="card-header">
                            <span className="card-title">层级导航</span>
                            <button className="page-btn" type="button" onClick={() => void loadWorkspace(selectedNodeId)} disabled={busyAction !== ''}>
                                刷新
                            </button>
                        </div>
                        <div className="workspace-tree-list">
                            {workspace.nodes.map(node => (
                                <button
                                    key={node.id}
                                    type="button"
                                    className={`workspace-tree-item ${selectedNodeId === node.id ? 'active' : ''}`}
                                    onClick={() => {
                                        setSelectedNodeId(node.id)
                                        setActiveTab('editor')
                                    }}
                                    style={{ paddingLeft: 14 + (node.depth || 0) * 18 }}
                                >
                                    <span className="workspace-tree-item-label">{node.label}</span>
                                    <span className="workspace-tree-item-meta">{formatEntityType(node.type)}</span>
                                </button>
                            ))}
                        </div>
                    </aside>

                    <section className="workspace-detail-column">
                        <div className="settings-tabs" role="tablist" aria-label="Workspace 面板标签页">
                            {Object.entries(TAB_LABELS).map(([tabId, label]) => (
                                <button
                                    key={tabId}
                                    type="button"
                                    role="tab"
                                    className={`settings-tab ${activeTab === tabId ? 'active' : ''}`}
                                    aria-selected={activeTab === tabId}
                                    onClick={() => setActiveTab(tabId)}
                                >
                                    {label}
                                </button>
                            ))}
                        </div>

                        {activeTab === 'editor' ? renderEditor() : null}
                        {activeTab === 'review' ? renderReview() : null}
                        {activeTab === 'history' ? renderHistory() : null}
                    </section>
                </div>
            ) : null}
        </PageScaffold>
    )
}
