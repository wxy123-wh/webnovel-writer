import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
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
    const [treeData, setTreeData] = useState({ folders: [], raw: {} })
    const [loadingTree, setLoadingTree] = useState(true)
    const [treeError, setTreeError] = useState('')
    const [expandedMap, setExpandedMap] = useState({})

    const [selectedPath, setSelectedPath] = useState('')
    const [fileContent, setFileContent] = useState('')
    const [loadingFile, setLoadingFile] = useState(false)
    const [fileError, setFileError] = useState('')

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

    return (
        <PageScaffold
            title="文档浏览"
            badge={loadingTree ? '加载中' : `${treeData.folders.length} 个目录`}
            description="目录树来自 /api/files/tree，文件内容来自 /api/files/read。"
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
                                <div className="file-preview">{fileContent || '[文件为空]'}</div>
                            </div>
                        ) : null}
                    </div>
                </div>
            ) : null}
        </PageScaffold>
    )
}
