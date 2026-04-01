import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import NewBookWizard from './NewBookWizard.jsx'
import {
    createEntity,
    fetchAuthoringWorkspace,
    fetchRevisionDiff,
    formatAuthoringApiError,
    rollbackRevision,
    saveEntityDraft,
} from '../api/authoring.js'
import {
    fetchFilesTree,
    formatApiError,
    readFileContent,
} from '../api/dashboardPages.js'

const TAB_LABELS = {
    editor: '编辑器',
    history: '修订记录',
    preview: '文件预览',
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

const ENTITY_TYPE_LABELS = {
    outline: 'Outline',
    plot: 'Plot',
    event: 'Event',
    scene: 'Scene',
    chapter: 'Chapter',
    setting: 'Setting',
    canon_entry: 'Canon',
}

const ROOT_CREATE_ACTIONS = [
    { entityType: 'outline', label: '新建大纲' },
    { entityType: 'setting', label: '新建设定' },
    { entityType: 'canon_entry', label: '新建 Canon' },
]

const CHILD_CREATE_ACTIONS = {
    outline: { entityType: 'plot', label: '在当前大纲下新建 Plot' },
    plot: { entityType: 'event', label: '在当前 Plot 下新建事件' },
    event: { entityType: 'scene', label: '在当前事件下新建场景' },
    scene: { entityType: 'chapter', label: '在当前场景下新建章节' },
}

function createFormState(entity) {
    return {
        title: entity?.title || '',
        body: entity?.body || '',
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

function collectFirstFilePath(nodes) {
    const stack = Array.isArray(nodes) ? [...nodes] : []
    while (stack.length > 0) {
        const current = stack.shift()
        if (!current) continue
        if (current.type === 'file' && current.path) {
            return current.path
        }
        if (current.type === 'dir' && Array.isArray(current.children)) {
            stack.unshift(...current.children)
        }
    }
    return ''
}

function collectFilePaths(nodes) {
    const result = []
    const stack = Array.isArray(nodes) ? [...nodes] : []
    while (stack.length > 0) {
        const current = stack.shift()
        if (!current) continue
        if (current.type === 'file' && current.path) {
            result.push(current.path)
            continue
        }
        if (current.type === 'dir' && Array.isArray(current.children)) {
            stack.unshift(...current.children)
        }
    }
    return result
}

function TreeNodes({
    nodes,
    selectedPath,
    expandedMap,
    onToggle,
    onSelectFile,
    listClassName = 'creation-desk-file-tree',
}) {
    if (!Array.isArray(nodes) || nodes.length === 0) {
        return null
    }

    return (
        <ul className={listClassName}>
            {nodes.map(node => {
                const nodePath = node.path || node.name
                const isDirectory = node.type === 'dir'
                const isExpanded = expandedMap[nodePath] ?? true
                const isSelected = !isDirectory && selectedPath === node.path

                return (
                    <li key={nodePath}>
                        <div
                            className={`creation-desk-file-tree-item ${isSelected ? 'active' : ''}`}
                            role="button"
                            tabIndex={0}
                            onClick={() => {
                                if (isDirectory) {
                                    onToggle(nodePath)
                                } else {
                                    onSelectFile(node.path)
                                }
                            }}
                            onKeyDown={event => {
                                if (event.key !== 'Enter' && event.key !== ' ') {
                                    return
                                }
                                event.preventDefault()
                                if (isDirectory) {
                                    onToggle(nodePath)
                                } else {
                                    onSelectFile(node.path)
                                }
                            }}
                        >
                            <span className="creation-desk-file-tree-icon">
                                {isDirectory ? (isExpanded ? '📂' : '📁') : '📄'}
                            </span>
                            <span>{node.name}</span>
                        </div>
                        {isDirectory && isExpanded ? (
                            <TreeNodes
                                nodes={node.children}
                                selectedPath={selectedPath}
                                expandedMap={expandedMap}
                                onToggle={onToggle}
                                onSelectFile={onSelectFile}
                                listClassName="creation-desk-file-tree-children"
                            />
                        ) : null}
                    </li>
                )
            })}
        </ul>
    )
}

export default function CreationDeskPage() {
    const [showWizard, setShowWizard] = useState(false)
    const [successNotice, setSuccessNotice] = useState('')
    const [workspace, setWorkspace] = useState(null)
    const [selectedNodeId, setSelectedNodeId] = useState('')
    const [activeTab, setActiveTab] = useState('editor')
    const [formState, setFormState] = useState(createFormState(null))
    const [loading, setLoading] = useState(true)
    const [busyAction, setBusyAction] = useState('')
    const [errorMessage, setErrorMessage] = useState('')
    const [notice, setNotice] = useState({ tone: '', message: '' })
    const [diffState, setDiffState] = useState({ summary: '', diffText: '' })

    const [treeData, setTreeData] = useState({ folders: [], raw: {} })
    const [loadingTree, setLoadingTree] = useState(false)
    const [treeError, setTreeError] = useState('')
    const [expandedMap, setExpandedMap] = useState({})
    const [selectedPath, setSelectedPath] = useState('')
    const [fileContent, setFileContent] = useState('')
    const [loadingFile, setLoadingFile] = useState(false)
    const [fileError, setFileError] = useState('')
    const [hasLoadedPreview, setHasLoadedPreview] = useState(false)

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
    const latestRevision = useMemo(() => getLatestRevision(selectedEntity?.revisions), [selectedEntity])

    const availableCreateActions = useMemo(() => {
        const actions = ROOT_CREATE_ACTIONS.map(action => ({ ...action, parentId: '' }))
        const contextualAction = selectedEntity ? CHILD_CREATE_ACTIONS[selectedEntity.entityType] : null
        if (contextualAction) {
            actions.push({
                ...contextualAction,
                parentId: selectedEntity.entityId,
            })
        }
        return actions
    }, [selectedEntity])

    const hasAnyFile = useMemo(
        () => treeData.folders.some(folder => Boolean(collectFirstFilePath(folder.nodes))),
        [treeData.folders],
    )

    const handleActionFailure = useCallback(error => {
        setNotice({ tone: 'error', message: formatAuthoringApiError(error) })
    }, [])

    const loadFile = useCallback(async path => {
        if (!path) return
        setSelectedPath(path)
        setLoadingFile(true)
        setFileError('')
        try {
            const response = await readFileContent(path)
            setFileContent(response.content || '')
        } catch (error) {
            setFileContent('')
            setFileError(formatApiError(error, '读取文件失败'))
        } finally {
            setLoadingFile(false)
        }
    }, [])

    const loadPreviewTree = useCallback(async () => {
        setLoadingTree(true)
        setTreeError('')
        try {
            const response = await fetchFilesTree()
            setTreeData(response)

            const currentPaths = new Set()
            response.folders.forEach(folder => {
                collectFilePaths(folder.nodes).forEach(path => currentPaths.add(path))
            })

            const fallbackPath = response.folders
                .map(folder => collectFirstFilePath(folder.nodes))
                .find(Boolean) || ''

            const nextPath = selectedPath && currentPaths.has(selectedPath)
                ? selectedPath
                : fallbackPath

            if (nextPath) {
                await loadFile(nextPath)
            } else {
                setSelectedPath('')
                setFileContent('')
                setFileError('')
            }
            setHasLoadedPreview(true)
        } catch (error) {
            setTreeError(formatApiError(error, '加载文件树失败'))
        } finally {
            setLoadingTree(false)
        }
    }, [loadFile, selectedPath])

    useEffect(() => {
        if (activeTab === 'preview' && !hasLoadedPreview && !loadingTree) {
            void loadPreviewTree()
        }
    }, [activeTab, hasLoadedPreview, loadPreviewTree, loadingTree])

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
                metadata: selectedEntity.metadata,
            })
            setNotice({ tone: 'success', message: '内容已保存，工作台已刷新到最新版本。' })
            await loadWorkspace(selectedEntity.entityId)
        } catch (error) {
            handleActionFailure(error)
        } finally {
            setBusyAction('')
        }
    }, [formState.body, formState.title, handleActionFailure, loadWorkspace, selectedEntity, workspace])

    const handleCreate = useCallback(async ({ entityType, parentId = '' }) => {
        if (!workspace?.book?.bookId) return
        setBusyAction(`create:${entityType}`)
        setNotice({ tone: '', message: '' })
        try {
            const result = await createEntity({
                bookId: workspace.book.bookId,
                entityType,
                parentId,
                title: '',
                body: '',
            })
            const newId =
                result?.outline_id ||
                result?.setting_id ||
                result?.canon_id ||
                result?.plot_id ||
                result?.event_id ||
                result?.scene_id ||
                result?.chapter_id ||
                result?.entity_id ||
                ''

            if (newId) {
                await loadWorkspace(newId)
                setSelectedNodeId(newId)
                setActiveTab('editor')
                setNotice({ tone: 'success', message: '新建成功，已选中新条目。' })
            } else {
                await loadWorkspace(selectedEntity?.entityId || '')
            }
        } catch (error) {
            handleActionFailure(error)
        } finally {
            setBusyAction('')
        }
    }, [handleActionFailure, loadWorkspace, selectedEntity?.entityId, workspace])

    const handleViewDiff = useCallback(async revision => {
        if (!workspace?.book?.bookId || !selectedEntity || !revision || !latestRevision) return
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
    }, [handleActionFailure, latestRevision, selectedEntity, workspace])

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

    async function handleWizardSuccess(result) {
        setShowWizard(false)
        await loadWorkspace('')
        setSuccessNotice(`${result?.title || '书籍项目'}创建成功！`)
        setTimeout(() => setSuccessNotice(''), 4000)
    }

    function renderEditor() {
        if (!selectedEntity) {
            return (
                <div className="card empty-state">
                    <p>请从左侧选择一个层级节点进行编辑，或使用下方创建操作补齐内容结构。</p>
                </div>
            )
        }

        return (
            <div className="card">
                <div className="card-header">
                    <span className="card-title">{EDITOR_TITLES[selectedEntity.entityType] || '节点编辑器'}</span>
                    <span className={`card-badge ${selectedEntity.supportsRevisions ? 'badge-blue' : 'badge-amber'}`}>
                        {ENTITY_TYPE_LABELS[selectedEntity.entityType] || selectedEntity.entityType} · v{selectedEntity.version}
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
                        <button
                            className="page-btn"
                            type="button"
                            onClick={() => void loadWorkspace(selectedEntity.entityId)}
                            disabled={loading || busyAction !== ''}
                        >
                            刷新当前节点
                        </button>
                        <button
                            className="new-chat-btn settings-save-btn"
                            type="button"
                            onClick={() => void handleSave()}
                            disabled={busyAction !== ''}
                        >
                            {busyAction === 'save' ? '保存中...' : '保存当前内容'}
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    function renderHistory() {
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
                                        <div className="settings-panel-copy">
                                            实体版本 {revision.entityVersion || revision.revisionNumber}
                                        </div>
                                    </div>
                                    <div className="settings-provider-actions">
                                        <button
                                            className="page-btn"
                                            type="button"
                                            onClick={() => void handleViewDiff(revision)}
                                            disabled={busyAction !== ''}
                                            aria-label={`查看 ${revision.label} 对比`}
                                        >
                                            {busyAction === `diff:${revision.revisionId}` ? '读取中...' : '查看对比'}
                                        </button>
                                        <button
                                            className="page-btn page-btn-danger"
                                            type="button"
                                            onClick={() => void handleRollback(revision)}
                                            disabled={busyAction !== ''}
                                            aria-label={`回滚到 ${revision.label}`}
                                        >
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
                        <span className="card-badge badge-blue">Unified Diff</span>
                    </div>
                    {diffState.summary ? (
                        <div className="settings-notice settings-notice-success">{diffState.summary}</div>
                    ) : null}
                    <pre className="workspace-diff-box">
                        {formatDiffText(diffState.diffText) || '先在左侧选择一个版本并点击“查看对比”。'}
                    </pre>
                </div>
            </div>
        )
    }

    function renderPreview() {
        return (
            <div className="creation-desk-preview-stack">
                <div className="card creation-desk-preview-notice">
                    <div className="card-header">
                        <span className="card-title">只读文件预览</span>
                        <span className="card-badge badge-amber">Read-Only</span>
                    </div>
                    <p className="settings-panel-copy">
                        这里承接原来的文件浏览用途，只用于查看项目文件与配置内容。编辑正文仍在“编辑器”标签内完成，Provider 配置请前往 Settings 页面修改。
                    </p>
                </div>

                {loadingTree ? <div className="loading">文件树加载中...</div> : null}

                {!loadingTree && treeError ? (
                    <div className="card" role="alert">
                        <div className="card-header">
                            <span className="card-title">文件树加载失败</span>
                            <span className="card-badge badge-amber">Error</span>
                        </div>
                        <p className="settings-panel-copy">{treeError}</p>
                        <div className="settings-provider-actions">
                            <button className="page-btn" type="button" onClick={() => void loadPreviewTree()}>
                                重试
                            </button>
                        </div>
                    </div>
                ) : null}

                {!loadingTree && !treeError && !hasAnyFile ? (
                    <div className="card empty-state">
                        <p>当前可浏览目录中暂无文件。</p>
                    </div>
                ) : null}

                {!loadingTree && !treeError && hasAnyFile ? (
                    <div className="creation-desk-preview-layout">
                        <div className="card creation-desk-preview-tree-card">
                            <div className="card-header">
                                <span className="card-title">项目文件树</span>
                                <button className="page-btn" type="button" onClick={() => void loadPreviewTree()} disabled={loadingFile}>
                                    刷新文件树
                                </button>
                            </div>
                            <div className="creation-desk-preview-tree-scroll">
                                {treeData.folders.map(folder => (
                                    <div className="creation-desk-folder-block" key={folder.name}>
                                        <div className="creation-desk-folder-title">📂 {folder.name}</div>
                                        <TreeNodes
                                            nodes={folder.nodes}
                                            selectedPath={selectedPath}
                                            expandedMap={expandedMap}
                                            onToggle={path => setExpandedMap(current => ({ ...current, [path]: !(current[path] ?? true) }))}
                                            onSelectFile={path => {
                                                void loadFile(path)
                                            }}
                                        />
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="card creation-desk-preview-content-card">
                            <div className="card-header">
                                <span className="card-title">文件内容</span>
                                <span className="card-badge badge-blue">Textarea Preview</span>
                            </div>

                            {loadingFile ? <div className="loading">文件内容加载中...</div> : null}

                            {!loadingFile && fileError ? (
                                <div className="settings-notice settings-notice-error" role="alert">{fileError}</div>
                            ) : null}

                            {!loadingFile && !fileError && !selectedPath ? (
                                <div className="empty-state compact">
                                    <p>请选择文件预览内容。</p>
                                </div>
                            ) : null}

                            {!loadingFile && !fileError && selectedPath ? (
                                <div className="creation-desk-preview-content">
                                    <div className="creation-desk-selected-path">{selectedPath}</div>
                                    <textarea
                                        className="settings-input workspace-editor-textarea creation-desk-file-textarea"
                                        value={fileContent || ''}
                                        readOnly
                                        placeholder="[文件为空]"
                                    />
                                    <p className="settings-panel-copy">提示：此处仅作只读预览，文件修改请通过 Codex 或 CLI 完成。</p>
                                </div>
                            ) : null}
                        </div>
                    </div>
                ) : null}
            </div>
        )
    }

    return (
        <PageScaffold
            title="创作台"
            badge={loading ? '加载中' : `${bookTitle} · ${nodeCount} 节点`}
            description="在同一工作台中浏览层级、编辑正文、回看修订，并预览项目文件。"
        >
            {successNotice ? (
                <div className="settings-notice settings-notice-success">{successNotice}</div>
            ) : null}

            <div className="card workspace-summary-card">
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
                <p className="settings-panel-copy">
                    创作台现在直接消费 hierarchy workspace 数据：左侧浏览 outlines / settings / canon 与完整正文链，右侧集中处理编辑、修订回看和文件预览。
                </p>
            </div>

            {errorMessage ? (
                <div className="settings-notice settings-notice-error" role="alert">
                    {errorMessage}
                </div>
            ) : null}

            {notice.message ? (
                <div
                    className={`settings-notice ${notice.tone === 'error' ? 'settings-notice-error' : 'settings-notice-success'}`}
                    role={notice.tone === 'error' ? 'alert' : 'status'}
                >
                    {notice.message}
                </div>
            ) : null}

            {loading ? <div className="loading">工作区加载中...</div> : null}

            {!loading && workspace ? (
                <div className="workspace-layout">
                    <aside className="card workspace-tree-card">
                        <div className="card-header">
                            <span className="card-title">层级导航</span>
                            <button
                                className="page-btn"
                                type="button"
                                onClick={() => void loadWorkspace(selectedNodeId)}
                                disabled={busyAction !== ''}
                            >
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
                                    <span className="workspace-tree-item-meta">
                                        {ENTITY_TYPE_LABELS[node.type] || node.type}
                                    </span>
                                </button>
                            ))}
                        </div>

                        <div className="creation-desk-create-panel">
                            <div className="creation-desk-create-group">
                                <div className="creation-desk-create-heading">顶层内容</div>
                                <div className="creation-desk-create-buttons">
                                    {ROOT_CREATE_ACTIONS.map(action => (
                                        <button
                                            key={action.entityType}
                                            className="page-btn"
                                            type="button"
                                            onClick={() => void handleCreate(action)}
                                            disabled={busyAction !== ''}
                                        >
                                            {busyAction === `create:${action.entityType}` ? '创建中...' : `+ ${action.label}`}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="creation-desk-create-group">
                                <div className="creation-desk-create-heading">当前层级扩展</div>
                                {selectedEntity && CHILD_CREATE_ACTIONS[selectedEntity.entityType] ? (
                                    <div className="creation-desk-create-buttons">
                                        {availableCreateActions
                                            .filter(action => action.parentId)
                                            .map(action => (
                                                <button
                                                    key={`${action.entityType}-${action.parentId}`}
                                                    className="page-btn"
                                                    type="button"
                                                    onClick={() => void handleCreate(action)}
                                                    disabled={busyAction !== ''}
                                                >
                                                    {busyAction === `create:${action.entityType}` ? '创建中...' : `+ ${action.label}`}
                                                </button>
                                            ))}
                                    </div>
                                ) : (
                                    <p className="settings-panel-copy">
                                        选中 Outline / Plot / Event / Scene 节点后，可在这里继续向下创建正文链条目。
                                    </p>
                                )}
                            </div>
                        </div>
                    </aside>

                    <section className="workspace-detail-column">
                        <div className="settings-tabs" role="tablist" aria-label="创作台标签页">
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
                        {activeTab === 'history' ? renderHistory() : null}
                        {activeTab === 'preview' ? renderPreview() : null}
                    </section>
                </div>
            ) : null}

            {showWizard ? (
                <NewBookWizard
                    onClose={() => setShowWizard(false)}
                    onSuccess={handleWizardSuccess}
                />
            ) : null}
        </PageScaffold>
    )
}
