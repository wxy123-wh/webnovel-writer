import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    fetchSettingsFileTree,
    isMockResponse,
    listSettingDictionary,
    readSettingsFile,
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

const BUTTON_STYLE = {
    border: '2px solid #2a220f',
    background: '#fff8e6',
    color: '#2a220f',
    fontSize: 13,
    fontWeight: 600,
    padding: '4px 10px',
    cursor: 'pointer',
}

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
    const [errorMessage, setErrorMessage] = useState('')
    const [fileNodes, setFileNodes] = useState([])
    const [dictionaryItems, setDictionaryItems] = useState([])
    const [selectedPath, setSelectedPath] = useState('')
    const [selectedContent, setSelectedContent] = useState('')
    const [loadingTree, setLoadingTree] = useState(true)
    const [loadingDictionary, setLoadingDictionary] = useState(true)
    const [loadingContent, setLoadingContent] = useState(false)
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
            return
        }

        setLoadingContent(true)
        try {
            const response = await readSettingsFile({ path })
            setSelectedPath(path)
            setSelectedContent(response.content || '')
            setErrorMessage('')
            setModeTag(isMockResponse(response) ? 'mock' : 'api')
        } catch (error) {
            setPageError(error)
        } finally {
            setLoadingContent(false)
        }
    }, [setPageError])

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
            description="[只读展示模式] 查看设定文件和词典条目。编辑操作请通过 Codex 直接修改文件。"
        >
            <div className="card" style={{ background: '#fff8e6', borderColor: '#d4a574' }}>
                <div className="card-header">
                    <span className="card-title">📋 只读展示模式</span>
                    <span className="card-badge badge-amber">Read-Only</span>
                </div>
                <p style={{ margin: 0, color: '#5d5035' }}>
                    此页面为只读展示。设定文件的编辑、词典的抽离和冲突解决等操作已移至 CLI 命令。
                    请使用 <code>webnovel codex</code> 命令来管理设定。
                </p>
            </div>

            <div style={LAYOUT_STYLE}>
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">设定文件树</span>
                        <span className="card-badge badge-green">mode: {modeTag.toUpperCase()}</span>
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
                                disabled={!selectedPath || loadingContent}
                                onClick={() => {
                                    if (selectedPath) {
                                        void readFile(selectedPath)
                                    }
                                }}
                            >
                                重新读取
                            </button>
                        </div>
                        <div
                            style={{
                                ...PREVIEW_STYLE,
                                width: '100%',
                                fontFamily: 'inherit',
                            }}
                        >
                            {loadingContent ? '文件读取中...' : selectedContent || '请选择文件进行预览。'}
                        </div>
                        <p style={{ margin: '8px 0 0 0', fontSize: 12, color: '#8f7f5c' }}>
                            提示: 编辑设定文件请使用 Codex 直接修改文件。
                        </p>
                    </div>
                </div>

                <div className="card">
                    <div className="card-header">
                        <span className="card-title">设定词典</span>
                        <span className="card-badge badge-blue">{dictionaryBadge}</span>
                    </div>
                    <div style={{ marginBottom: 10 }}>
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
                                    <tr key={item.id}>
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
                                            词典暂无数据。
                                        </td>
                                    </tr>
                                ) : null}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {errorMessage ? (
                <div className="card" style={{ borderColor: '#d46a57' }}>
                    <div className="card-header">
                        <span className="card-title">请求失败</span>
                        <span className="card-badge badge-red">Error</span>
                    </div>
                    <p style={{ margin: 0, color: '#9a2a1a' }}>{errorMessage}</p>
                </div>
            ) : null}
        </PageScaffold>
    )
}
