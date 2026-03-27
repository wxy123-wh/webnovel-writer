import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import { useContextMenu } from '../components/ContextMenuProvider.jsx'
import {
    formatCodexBridgeError,
    openCodexFileEditDialog,
} from '../api/codexBridge.js'
import {
    extractSettingDictionary,
    fetchSettingsFileTree,
    getConflictIdFromEntry,
    isMockResponse,
    listSettingDictionary,
    readSettingsFile,
    resolveDictionaryConflict,
    writeSettingsFile,
} from '../api/settings.js'

const LAYOUT_STYLE = {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
    gap: 14,
}

const LIST_STYLE = {
    margin: 0,
    padding: 0,
    listStyle: 'none',
}

const TREE_ROW_STYLE = {
    width: '100%',
    border: '2px solid transparent',
    borderRadius: 6,
    background: 'transparent',
    textAlign: 'left',
    padding: '6px 8px',
    cursor: 'pointer',
    fontSize: 13,
    color: '#5d5035',
}

const PREVIEW_STYLE = {
    border: '2px solid #8f7f5c',
    background: '#fff',
    padding: 10,
    minHeight: 180,
    whiteSpace: 'pre-wrap',
    lineHeight: 1.7,
    fontSize: 13,
    overflow: 'auto',
}

const TOOLBAR_STYLE = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    marginBottom: 10,
}

const BUTTON_STYLE = {
    border: '2px solid #2a220f',
    background: '#fff8e6',
    color: '#2a220f',
    fontSize: 13,
    fontWeight: 600,
    padding: '4px 10px',
    cursor: 'pointer',
}

const EDITOR_STYLE = {
    ...PREVIEW_STYLE,
    width: '100%',
    resize: 'vertical',
    fontFamily: 'inherit',
}
const CODEX_SETTINGS_FILE_EDIT_PROMPT = '请直接修改选中的设定文本，保持术语与属性键一致并提升表达清晰度。'

function collectFirstFilePath(nodes) {
    const stack = Array.isArray(nodes) ? [...nodes] : []
    while (stack.length > 0) {
        const node = stack.shift()
        if (!node) continue
        if (node.type === 'file') {
            return node.path
        }
        if (Array.isArray(node.children)) {
            stack.unshift(...node.children)
        }
    }
    return ''
}

function buildSelectionPayload(textareaRef) {
    const element = textareaRef.current
    if (!element) {
        return { selectionStart: 0, selectionEnd: 0, selectionText: '' }
    }
    const selectionStart = element.selectionStart ?? 0
    const selectionEnd = element.selectionEnd ?? 0
    const value = typeof element.value === 'string' ? element.value : ''
    return {
        selectionStart,
        selectionEnd,
        selectionText: value.slice(selectionStart, selectionEnd),
    }
}

function hasValidSelection(selection) {
    if (!selection || typeof selection !== 'object') {
        return false
    }
    if (selection.selectionEnd <= selection.selectionStart) {
        return false
    }
    return Boolean(selection.selectionText)
}

function TreeNodeList({ nodes, selectedPath, onSelect, depth = 0 }) {
    if (!Array.isArray(nodes) || nodes.length === 0) {
        return null
    }

    return (
        <ul style={LIST_STYLE}>
            {nodes.map(node => {
                const isFile = node.type === 'file'
                const isSelected = isFile && node.path === selectedPath
                return (
                    <li key={node.path} style={{ marginBottom: 2 }}>
                        <button
                            type="button"
                            style={{
                                ...TREE_ROW_STYLE,
                                paddingLeft: 8 + depth * 14,
                                background: isSelected ? '#e6f7ff' : 'transparent',
                                borderColor: isSelected ? '#26a8ff' : 'transparent',
                                fontWeight: isFile ? 600 : 700,
                                cursor: isFile ? 'pointer' : 'default',
                            }}
                            onClick={() => {
                                if (isFile) {
                                    onSelect(node.path)
                                }
                            }}
                        >
                            {isFile ? 'FILE ' : 'DIR '}
                            {node.name}
                        </button>
                        {!isFile ? (
                            <TreeNodeList
                                nodes={node.children || []}
                                selectedPath={selectedPath}
                                onSelect={onSelect}
                                depth={depth + 1}
                            />
                        ) : null}
                    </li>
                )
            })}
        </ul>
    )
}

export default function SettingsPage() {
    const { openForEvent } = useContextMenu()
    const editorRef = useRef(null)
    const [lastAction, setLastAction] = useState('尚未触发')
    const [errorMessage, setErrorMessage] = useState('')
    const [fileNodes, setFileNodes] = useState([])
    const [dictionaryItems, setDictionaryItems] = useState([])
    const [selectedPath, setSelectedPath] = useState('')
    const [selectedContent, setSelectedContent] = useState('')
    const [draftContent, setDraftContent] = useState('')
    const [loadingTree, setLoadingTree] = useState(true)
    const [loadingDictionary, setLoadingDictionary] = useState(true)
    const [loadingContent, setLoadingContent] = useState(false)
    const [savingContent, setSavingContent] = useState(false)
    const [extracting, setExtracting] = useState(false)
    const [launchingCodexFileEdit, setLaunchingCodexFileEdit] = useState(false)
    const [modeTag, setModeTag] = useState('api')

    const setPageError = useCallback(error => {
        setModeTag('error')
        setErrorMessage(error?.message || '请求失败，请稍后重试')
    }, [])

    const refreshDictionary = useCallback(async () => {
        setLoadingDictionary(true)
        try {
            const response = await listSettingDictionary({ limit: 200, offset: 0 })
            setDictionaryItems(Array.isArray(response.items) ? response.items : [])
            setErrorMessage('')
            setModeTag(isMockResponse(response) ? 'mock' : 'api')
        } catch (error) {
            setPageError(error)
        } finally {
            setLoadingDictionary(false)
        }
    }, [setPageError])

    const readFile = useCallback(async path => {
        if (!path) {
            setSelectedContent('')
            setDraftContent('')
            return
        }

        setLoadingContent(true)
        try {
            const response = await readSettingsFile({ path })
            setSelectedPath(path)
            setSelectedContent(response.content || '')
            setDraftContent(response.content || '')
            setErrorMessage('')
            setModeTag(isMockResponse(response) ? 'mock' : 'api')
        } catch (error) {
            setPageError(error)
        } finally {
            setLoadingContent(false)
        }
    }, [setPageError])

    const saveFile = useCallback(async () => {
        if (!selectedPath) {
            return
        }

        setSavingContent(true)
        try {
            const response = await writeSettingsFile({ path: selectedPath, content: draftContent })
            setSelectedContent(draftContent)
            setErrorMessage('')
            setModeTag(isMockResponse(response) ? 'mock' : 'api')
            setLastAction(`settings.write -> ${selectedPath}`)
        } catch (error) {
            setPageError(error)
            setLastAction(`settings.write -> error(${error?.errorCode || 'unknown_error'})`)
        } finally {
            setSavingContent(false)
        }
    }, [draftContent, selectedPath, setPageError])

    const refreshTree = useCallback(async () => {
        setLoadingTree(true)
        try {
            const response = await fetchSettingsFileTree()
            const nodes = Array.isArray(response.nodes) ? response.nodes : []
            setFileNodes(nodes)
            setErrorMessage('')
            setModeTag(isMockResponse(response) ? 'mock' : 'api')
            const initialPath = selectedPath || collectFirstFilePath(nodes)
            if (initialPath) {
                await readFile(initialPath)
            }
        } catch (error) {
            setPageError(error)
        } finally {
            setLoadingTree(false)
        }
    }, [readFile, selectedPath, setPageError])

    useEffect(() => {
        void Promise.all([refreshTree(), refreshDictionary()])
    }, [refreshDictionary, refreshTree])

    const applyLocalStatus = useCallback((entryId, status) => {
        setDictionaryItems(prev => {
            return prev.map(item => {
                if (item.id !== entryId) {
                    return item
                }
                return { ...item, status }
            })
        })
    }, [])

    const handleDictionaryAction = useCallback(async payload => {
        const actionId = payload.actionId
        const entryId = payload.meta?.entryId || ''
        const sourceFile = payload.meta?.sourceFile || ''
        const conflictId = payload.meta?.conflictId || ''

        try {
            if (actionId === 'view-source') {
                await readFile(sourceFile)
                setLastAction(`${actionId} -> ${sourceFile}`)
                return
            }

            if (actionId === 'mark-confirmed') {
                if (conflictId) {
                    const response = await resolveDictionaryConflict({
                        id: conflictId,
                        decision: 'confirm',
                        attrs: {},
                    })
                    setModeTag(isMockResponse(response) ? 'mock' : 'api')
                    setErrorMessage('')
                }
                applyLocalStatus(entryId, 'confirmed')
                setLastAction(`${actionId} -> ${entryId}`)
                return
            }

            if (actionId === 'resolve-conflict') {
                if (!conflictId) {
                    const error = new Error('缺少 conflict_id，无法处理冲突')
                    error.errorCode = 'conflict_id_required'
                    throw error
                }
                const response = await resolveDictionaryConflict({
                    id: conflictId,
                    decision: 'confirm',
                    attrs: {},
                })
                setModeTag(isMockResponse(response) ? 'mock' : 'api')
                setErrorMessage('')
                await refreshDictionary()
                setLastAction(`${actionId} -> ${conflictId}`)
                return
            }

            setLastAction(`${actionId} -> ${entryId || 'unknown'}`)
        } catch (error) {
            setPageError(error)
            setLastAction(`${actionId} -> error(${error?.errorCode || 'unknown_error'})`)
        }
    }, [applyLocalStatus, readFile, refreshDictionary, setPageError])

    const openDictionaryMenu = useCallback((event, item) => {
        const conflictId = getConflictIdFromEntry(item)
        openForEvent(event, {
            sourceId: 'settings.dictionary.entry',
            meta: {
                entryId: item.id,
                sourceFile: item.source_file,
                conflictId,
            },
            onAction: payload => {
                void handleDictionaryAction(payload)
            },
            items: [
                {
                    id: 'view-source',
                    actionId: 'view-source',
                    label: '定位源文件',
                    shortcut: 'V',
                },
                {
                    id: 'mark-confirmed',
                    actionId: 'mark-confirmed',
                    label: '标记为已确认',
                    disabled: item.status === 'confirmed',
                    shortcut: 'C',
                },
                {
                    id: 'resolve-conflict',
                    actionId: 'resolve-conflict',
                    label: '处理冲突',
                    disabled: item.status !== 'conflict',
                    shortcut: 'R',
                },
            ],
        })
    }, [handleDictionaryAction, openForEvent])

    const runCodexFileEdit = useCallback(async selection => {
        if (!selectedPath) {
            setLastAction('codex-file-edit -> 请先选择目标文件')
            return
        }
        if (draftContent !== selectedContent) {
            setLastAction('codex-file-edit -> 请先保存本地改动，再启动 Codex 文件编辑')
            return
        }
        if (!hasValidSelection(selection)) {
            setLastAction('codex-file-edit -> 请先选中有效文本')
            return
        }

        setLaunchingCodexFileEdit(true)
        setErrorMessage('')
        try {
            const response = await openCodexFileEditDialog({
                filePath: selectedPath,
                selectionStart: selection.selectionStart,
                selectionEnd: selection.selectionEnd,
                selectionText: selection.selectionText,
                instruction: CODEX_SETTINGS_FILE_EDIT_PROMPT,
                sourceId: 'settings.editor.textarea',
            })
            setLastAction(
                `codex-file-edit -> ${response.target_file || selectedPath} (${response.prompt_file || 'no-prompt-file'}), 完成后请重新读取文件`,
            )
        } catch (error) {
            setPageError(error)
            setLastAction(`codex-file-edit -> error(${error?.errorCode || 'unknown_error'})`)
            setErrorMessage(formatCodexBridgeError(error, 'CODEX_FILE_EDIT_DIALOG_OPEN_FAILED'))
        } finally {
            setLaunchingCodexFileEdit(false)
        }
    }, [draftContent, selectedContent, selectedPath, setPageError])

    const openSettingsEditorMenu = useCallback(event => {
        const selection = buildSelectionPayload(editorRef)
        const hasUnsavedChanges = draftContent !== selectedContent
        openForEvent(event, {
            sourceId: 'settings.editor.textarea',
            meta: {
                selection,
            },
            onAction: payload => {
                if (payload.actionId === 'codex-file-edit') {
                    void runCodexFileEdit(payload.meta?.selection || selection)
                }
            },
            items: [
                {
                    id: 'codex-file-edit',
                    actionId: 'codex-file-edit',
                    label: 'Codex直接改文件',
                    shortcut: 'C',
                    disabled: !selectedPath || hasUnsavedChanges || !hasValidSelection(selection),
                },
            ],
        })
    }, [draftContent, openForEvent, runCodexFileEdit, selectedContent, selectedPath])

    const runExtract = useCallback(async () => {
        setExtracting(true)
        try {
            const response = await extractSettingDictionary({ incremental: true })
            setErrorMessage('')
            setModeTag(isMockResponse(response) ? 'mock' : 'api')
            setLastAction(`dictionary.extract -> +${response.extracted} / conflicts ${response.conflicts}`)
            await refreshDictionary()
        } catch (error) {
            setPageError(error)
            setLastAction(`dictionary.extract -> error(${error?.errorCode || 'unknown_error'})`)
        } finally {
            setExtracting(false)
        }
    }, [refreshDictionary, setPageError])

    const dictionaryBadge = useMemo(() => {
        if (loadingDictionary) {
            return '词典加载中'
        }
        return `${dictionaryItems.length} 条`
    }, [dictionaryItems.length, loadingDictionary])

    return (
        <PageScaffold
            title="设定集"
            badge="Settings & Dictionary"
            description="双栏同屏：左侧设定文件树，右侧词典条目。选中设定文本后右键可直接拉起 Codex 改文件。"
        >
            <div style={LAYOUT_STYLE}>
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">设定文件树</span>
                        <span className="card-badge badge-green">mode: {modeTag.toUpperCase()}</span>
                        <span className="card-badge badge-purple">
                            {launchingCodexFileEdit ? 'codex: launching' : 'codex: ready'}
                        </span>
                    </div>
                    {loadingTree ? <p style={{ margin: 0 }}>文件树加载中...</p> : null}
                    {!loadingTree && fileNodes.length === 0 ? <p style={{ margin: 0 }}>未发现设定集文件。</p> : null}
                    <TreeNodeList nodes={fileNodes} selectedPath={selectedPath} onSelect={readFile} />
                    <div style={{ marginTop: 10 }}>
                        <div style={{ fontSize: 12, color: '#8f7f5c', marginBottom: 6 }}>
                            当前文件: {selectedPath || '未选择'}
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                            <button
                                type="button"
                                style={BUTTON_STYLE}
                                disabled={!selectedPath || loadingContent || savingContent || draftContent === selectedContent}
                                onClick={() => {
                                    void saveFile()
                                }}
                            >
                                {savingContent ? '保存中...' : '保存文件'}
                            </button>
                            <button
                                type="button"
                                style={BUTTON_STYLE}
                                disabled={!selectedPath || loadingContent || savingContent || draftContent === selectedContent}
                                onClick={() => setDraftContent(selectedContent)}
                            >
                                撤销改动
                            </button>
                        </div>
                        <textarea
                            ref={editorRef}
                            style={EDITOR_STYLE}
                            value={loadingContent ? '' : draftContent}
                            onChange={event => setDraftContent(event.target.value)}
                            onContextMenu={openSettingsEditorMenu}
                            readOnly={loadingContent || !selectedPath}
                            placeholder={loadingContent ? '文件读取中...' : '请选择文件进行预览。'}
                        />
                        <p style={{ margin: '8px 0 0 0', fontSize: 12, color: '#8f7f5c' }}>
                            操作提示: 先保存本地改动，再选中文本并右键，选择“Codex直接改文件”。
                        </p>
                    </div>
                </div>

                <div className="card">
                    <div className="card-header">
                        <span className="card-title">设定词典</span>
                        <span className="card-badge badge-blue">{dictionaryBadge}</span>
                    </div>
                    <div style={TOOLBAR_STYLE}>
                        <button type="button" style={BUTTON_STYLE} disabled={extracting} onClick={runExtract}>
                            {extracting ? '抽离中...' : '抽离词典（增量）'}
                        </button>
                        <button type="button" style={BUTTON_STYLE} disabled={loadingDictionary} onClick={refreshDictionary}>
                            刷新词典
                        </button>
                    </div>
                    <div className="table-wrap">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>term</th>
                                    <th>type</th>
                                    <th>status</th>
                                    <th>source</th>
                                    <th>span</th>
                                </tr>
                            </thead>
                            <tbody>
                                {dictionaryItems.map(item => (
                                    <tr
                                        key={item.id}
                                        onContextMenu={event => openDictionaryMenu(event, item)}
                                        style={{ cursor: 'context-menu' }}
                                    >
                                        <td>{item.term}</td>
                                        <td>{item.type}</td>
                                        <td>{item.status}</td>
                                        <td>{item.source_file}</td>
                                        <td>{item.source_span}</td>
                                    </tr>
                                ))}
                                {!loadingDictionary && dictionaryItems.length === 0 ? (
                                    <tr>
                                        <td colSpan={5} style={{ color: '#8f7f5c' }}>
                                            词典暂无数据，点击“抽离词典（增量）”开始构建。
                                        </td>
                                    </tr>
                                ) : null}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <span className="card-title">协议回执</span>
                    <span className="card-badge badge-blue">sourceId: settings.dictionary.entry / settings.editor.textarea</span>
                </div>
                <p style={{ margin: 0 }}>最近动作: {lastAction}</p>
                {errorMessage ? <p style={{ margin: '8px 0 0', color: '#b40000' }}>错误: {errorMessage}</p> : null}
            </div>
        </PageScaffold>
    )
}
