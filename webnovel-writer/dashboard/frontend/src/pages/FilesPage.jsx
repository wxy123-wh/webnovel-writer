import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import { useContextMenu } from '../components/ContextMenuProvider.jsx'
import {
    formatCodexBridgeError,
    openCodexFileEditDialog,
} from '../api/codexBridge.js'
import {
    fetchFilesTree,
    formatApiError,
    readFileContent,
} from '../api/dashboardPages.js'

const RETRY_BUTTON_STYLE = {
    border: '2px solid var(--border-main)',
    background: '#fff8e6',
    color: 'var(--text-main)',
    fontFamily: 'var(--font-body)',
    fontSize: 13,
    fontWeight: 700,
    padding: '6px 12px',
    cursor: 'pointer',
}
const PREVIEW_EDITOR_STYLE = {
    width: '100%',
    border: '2px solid var(--border-soft)',
    background: '#fff',
    padding: 12,
    minHeight: 260,
    overflow: 'auto',
    lineHeight: 1.75,
    wordBreak: 'break-word',
    fontSize: 14,
    fontFamily: 'var(--font-body)',
    resize: 'vertical',
    boxSizing: 'border-box',
}
const CODEX_FILES_FILE_EDIT_PROMPT = '请直接修改选中的文件文本，保持设定连续性并优化表达。'

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
    listClassName = 'file-tree',
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
                            className={`tree-item ${isSelected ? 'active' : ''}`}
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
                            <span className="tree-icon">{isDirectory ? (isExpanded ? '📂' : '📁') : '📄'}</span>
                            <span>{node.name}</span>
                        </div>
                        {isDirectory && isExpanded ? (
                            <TreeNodes
                                nodes={node.children}
                                selectedPath={selectedPath}
                                expandedMap={expandedMap}
                                onToggle={onToggle}
                                onSelectFile={onSelectFile}
                                listClassName="tree-children"
                            />
                        ) : null}
                    </li>
                )
            })}
        </ul>
    )
}

export default function FilesPage() {
    const { openForEvent } = useContextMenu()
    const previewRef = useRef(null)
    const [treeData, setTreeData] = useState({ folders: [], raw: {} })
    const [loadingTree, setLoadingTree] = useState(true)
    const [treeError, setTreeError] = useState('')
    const [expandedMap, setExpandedMap] = useState({})

    const [selectedPath, setSelectedPath] = useState('')
    const [fileContent, setFileContent] = useState('')
    const [loadingFile, setLoadingFile] = useState(false)
    const [fileError, setFileError] = useState('')
    const [launchingCodexFileEdit, setLaunchingCodexFileEdit] = useState(false)

    const loadFile = useCallback(async path => {
        if (!path) return
        setSelectedPath(path)
        setLoadingFile(true)
        setFileError('')
        try {
            const response = await readFileContent(path)
            setFileContent(response.content || '')
        } catch (err) {
            setFileContent('')
            setFileError(formatApiError(err, '读取文件失败'))
        } finally {
            setLoadingFile(false)
        }
    }, [])

    const refreshTree = useCallback(async () => {
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
        } catch (err) {
            setTreeError(formatApiError(err, '加载文件树失败'))
        } finally {
            setLoadingTree(false)
        }
    }, [loadFile, selectedPath])

    useEffect(() => {
        void refreshTree()
    }, [refreshTree])

    const hasAnyFile = useMemo(
        () => treeData.folders.some(folder => Boolean(collectFirstFilePath(folder.nodes))),
        [treeData.folders],
    )

    const runCodexFileEdit = useCallback(async () => {
        if (!selectedPath) {
            return
        }
        const element = previewRef.current
        const selectionStart = element?.selectionStart ?? 0
        const selectionEnd = element?.selectionEnd ?? 0
        const selectionText = selectionEnd > selectionStart
            ? (element?.value || '').slice(selectionStart, selectionEnd)
            : ''
        if (!selectionText) {
            setFileError('请先在文件预览区选中有效文本后再启动 Codex。')
            return
        }

        setLaunchingCodexFileEdit(true)
        setFileError('')
        try {
            await openCodexFileEditDialog({
                filePath: selectedPath,
                selectionStart,
                selectionEnd,
                selectionText,
                instruction: CODEX_FILES_FILE_EDIT_PROMPT,
                sourceId: 'files.preview.textarea',
            })
        } catch (error) {
            setFileError(formatCodexBridgeError(error, 'CODEX_FILE_EDIT_DIALOG_OPEN_FAILED'))
        } finally {
            setLaunchingCodexFileEdit(false)
        }
    }, [selectedPath])

    const openFilePreviewMenu = useCallback(event => {
        const element = previewRef.current
        const selectionStart = element?.selectionStart ?? 0
        const selectionEnd = element?.selectionEnd ?? 0
        const selectionText = selectionEnd > selectionStart
            ? (element?.value || '').slice(selectionStart, selectionEnd)
            : ''
        openForEvent(event, {
            sourceId: 'files.preview.textarea',
            onAction: payload => {
                if (payload.actionId === 'codex-file-edit') {
                    void runCodexFileEdit()
                }
            },
            items: [
                {
                    id: 'codex-file-edit',
                    actionId: 'codex-file-edit',
                    label: 'Codex直接改文件',
                    shortcut: 'C',
                    disabled: !selectedPath || !selectionText,
                },
            ],
        })
    }, [openForEvent, runCodexFileEdit, selectedPath])

    return (
        <PageScaffold
            title="文档浏览"
            badge={loadingTree ? '加载中' : `${treeData.folders.length} 个目录`}
            description="目录树来自 /api/files/tree，文件内容来自 /api/files/read。选中文本后右键可直接拉起 Codex 改文件。"
        >
            {loadingTree ? (
                <div className="loading">文件树加载中...</div>
            ) : null}

            {!loadingTree && treeError ? (
                <div className="card" role="alert">
                    <div className="card-header">
                        <span className="card-title">文件树加载失败</span>
                        <span className="card-badge badge-red">Error</span>
                    </div>
                    <p style={{ marginTop: 0 }}>{treeError}</p>
                    <button type="button" style={RETRY_BUTTON_STYLE} onClick={() => void refreshTree()}>
                        重试
                    </button>
                </div>
            ) : null}

            {!loadingTree && !treeError && !hasAnyFile ? (
                <div className="card empty-state">
                    <div className="empty-icon">F</div>
                    <p>可浏览目录中暂无文件。</p>
                </div>
            ) : null}

            {!loadingTree && !treeError && hasAnyFile ? (
                <div className="file-layout">
                    <div className="file-tree-pane">
                        {treeData.folders.map(folder => (
                            <div className="folder-block" key={folder.name}>
                                <div className="folder-title">📂 {folder.name}</div>
                                <TreeNodes
                                    nodes={folder.nodes}
                                    selectedPath={selectedPath}
                                    expandedMap={expandedMap}
                                    onToggle={path =>
                                        setExpandedMap(prev => ({ ...prev, [path]: !(prev[path] ?? true) }))}
                                    onSelectFile={path => {
                                        void loadFile(path)
                                    }}
                                />
                            </div>
                        ))}
                    </div>

                    <div className="file-content-pane">
                        {loadingFile ? (
                            <div className="loading">文件内容加载中...</div>
                        ) : null}

                        {!loadingFile && fileError ? (
                            <div className="card" role="alert">
                                <div className="card-header">
                                    <span className="card-title">文件读取失败</span>
                                    <span className="card-badge badge-red">Error</span>
                                </div>
                                <p style={{ marginTop: 0 }}>{fileError}</p>
                                <button
                                    type="button"
                                    style={RETRY_BUTTON_STYLE}
                                    onClick={() => {
                                        if (selectedPath) {
                                            void loadFile(selectedPath)
                                        }
                                    }}
                                    disabled={!selectedPath}
                                >
                                    重试读取
                                </button>
                            </div>
                        ) : null}

                        {!loadingFile && !fileError && !selectedPath ? (
                            <div className="empty-state">
                                <div className="empty-icon">📄</div>
                                <p>请选择文件预览内容。</p>
                            </div>
                        ) : null}

                        {!loadingFile && !fileError && selectedPath ? (
                            <div>
                                <div className="selected-path">{selectedPath}</div>
                                <textarea
                                    ref={previewRef}
                                    style={PREVIEW_EDITOR_STYLE}
                                    value={fileContent || ''}
                                    onContextMenu={openFilePreviewMenu}
                                    readOnly
                                    placeholder="[文件为空]"
                                />
                                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-sub)' }}>
                                    {launchingCodexFileEdit
                                        ? 'Codex 启动中...'
                                        : '操作提示: 选中文本后右键，选择“Codex直接改文件”。'}
                                </div>
                            </div>
                        ) : null}
                    </div>
                </div>
            ) : null}
        </PageScaffold>
    )
}
