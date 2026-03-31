import { useCallback, useEffect, useMemo, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    fetchProviderSettings,
    fetchSettingsFileTree,
    isMockResponse,
    listSettingDictionary,
    readSettingsFile,
    updateProviderSettings,
} from '../api/settings.js'

const DEFAULT_PROVIDER_FORM = {
    provider: '',
    base_url: '',
    model: '',
    api_key: '',
    clear_api_key: false,
}

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

function ProviderSettingsPanel() {
    const [providerState, setProviderState] = useState(null)
    const [formState, setFormState] = useState(DEFAULT_PROVIDER_FORM)
    const [loadingProvider, setLoadingProvider] = useState(true)
    const [savingProvider, setSavingProvider] = useState(false)
    const [providerError, setProviderError] = useState('')
    const [providerNotice, setProviderNotice] = useState('')

    const syncForm = useCallback(payload => {
        setProviderState(payload)
        setFormState({
            provider: payload?.provider || '',
            base_url: payload?.base_url || '',
            model: payload?.model || '',
            api_key: '',
            clear_api_key: false,
        })
    }, [])

    const loadProviderSettings = useCallback(async () => {
        setLoadingProvider(true)
        setProviderError('')
        try {
            const response = await fetchProviderSettings()
            syncForm(response)
        } catch (error) {
            setProviderError(error?.message || '读取 provider 配置失败')
        } finally {
            setLoadingProvider(false)
        }
    }, [syncForm])

    useEffect(() => {
        void loadProviderSettings()
    }, [loadProviderSettings])

    const configuredBadge = providerState?.configured ? '已配置' : '待配置'
    const apiKeyBadge = providerState?.api_key_configured ? 'API Key 已保存' : 'API Key 未保存'

    return (
        <>
            <div className="card settings-provider-card">
                <div className="card-header">
                    <div>
                        <span className="card-title">Provider 配置</span>
                        <p className="settings-panel-intro">在这里配置真实生成服务。Chat 只有在 provider 与密钥都准备好后才会开放。</p>
                    </div>
                    <div className="settings-provider-badges">
                        <span className={`card-badge ${providerState?.configured ? 'badge-green' : 'badge-amber'}`}>{configuredBadge}</span>
                        <span className={`card-badge ${providerState?.api_key_configured ? 'badge-blue' : 'badge-amber'}`}>{apiKeyBadge}</span>
                    </div>
                </div>

                {loadingProvider ? <p className="settings-panel-copy">正在读取当前 provider 配置...</p> : null}

                {!loadingProvider ? (
                    <form
                        className="settings-provider-form"
                        onSubmit={async event => {
                            event.preventDefault()
                            setSavingProvider(true)
                            setProviderError('')
                            setProviderNotice('')
                            try {
                                const response = await updateProviderSettings(formState)
                                syncForm(response)
                                setProviderNotice(response.configured
                                    ? 'Provider 配置已保存，Chat 现在可以重新检查运行时状态。'
                                    : 'Provider 配置已保存，但当前仍未满足 Chat 解锁条件。')
                            } catch (error) {
                                setProviderError(error?.message || '保存 provider 配置失败')
                            } finally {
                                setSavingProvider(false)
                            }
                        }}
                    >
                        <div className="settings-form-grid">
                            <label className="settings-field">
                                <span className="settings-field-label">Provider</span>
                                <input
                                    className="settings-input"
                                    name="provider"
                                    placeholder="例如 openai / openrouter / anthropic"
                                    value={formState.provider}
                                    onChange={event => setFormState(prev => ({ ...prev, provider: event.target.value }))}
                                />
                            </label>

                            <label className="settings-field">
                                <span className="settings-field-label">Model</span>
                                <input
                                    className="settings-input"
                                    name="model"
                                    placeholder="例如 gpt-4.1-mini"
                                    value={formState.model}
                                    onChange={event => setFormState(prev => ({ ...prev, model: event.target.value }))}
                                />
                            </label>

                            <label className="settings-field settings-field-wide">
                                <span className="settings-field-label">Base URL</span>
                                <input
                                    className="settings-input"
                                    name="base_url"
                                    placeholder="https://api.openai.com/v1"
                                    value={formState.base_url}
                                    onChange={event => setFormState(prev => ({ ...prev, base_url: event.target.value }))}
                                />
                            </label>

                            <label className="settings-field settings-field-wide">
                                <span className="settings-field-label">API Key</span>
                                <input
                                    className="settings-input"
                                    name="api_key"
                                    type="password"
                                    placeholder={providerState?.api_key_configured ? '已保存，如需轮换请重新输入' : '输入新的 API Key'}
                                    value={formState.api_key}
                                    onChange={event => setFormState(prev => ({
                                        ...prev,
                                        api_key: event.target.value,
                                        clear_api_key: false,
                                    }))}
                                />
                            </label>
                        </div>

                        <label className="settings-checkbox-row">
                            <input
                                type="checkbox"
                                checked={formState.clear_api_key}
                                onChange={event => setFormState(prev => ({
                                    ...prev,
                                    clear_api_key: event.target.checked,
                                    api_key: event.target.checked ? '' : prev.api_key,
                                }))}
                            />
                            <span>清除当前已保存的 API Key</span>
                        </label>

                        <div className="settings-provider-summary">
                            <div className="settings-provider-summary-item">
                                <span>当前 Provider</span>
                                <strong>{providerState?.provider || '未设置'}</strong>
                            </div>
                            <div className="settings-provider-summary-item">
                                <span>当前 Model</span>
                                <strong>{providerState?.model || '未设置'}</strong>
                            </div>
                            <div className="settings-provider-summary-item">
                                <span>当前 Base URL</span>
                                <strong>{providerState?.base_url || '默认地址'}</strong>
                            </div>
                        </div>

                        {providerNotice ? <div className="settings-notice settings-notice-success">{providerNotice}</div> : null}
                        {providerError ? <div className="settings-notice settings-notice-error">{providerError}</div> : null}

                        <div className="settings-provider-actions">
                            <button className="page-btn" type="button" onClick={() => void loadProviderSettings()} disabled={loadingProvider || savingProvider}>
                                重新读取
                            </button>
                            <button className="new-chat-btn settings-save-btn" type="submit" disabled={savingProvider}>
                                {savingProvider ? '保存中...' : '保存配置'}
                            </button>
                        </div>
                    </form>
                ) : null}
            </div>

            <div className="card settings-provider-card settings-provider-help-card">
                <div className="card-header">
                    <span className="card-title">接入说明</span>
                    <span className="card-badge badge-purple">Provider</span>
                </div>
                <div className="settings-provider-help-grid">
                    <div className="settings-provider-help-item">
                        <strong>1. 选择服务</strong>
                        <p>填写 provider 名称与模型标识，保持与后端实际接入一致。</p>
                    </div>
                    <div className="settings-provider-help-item">
                        <strong>2. 补充地址</strong>
                        <p>如果不是默认官方地址，再补充 Base URL，避免请求落到错误网关。</p>
                    </div>
                    <div className="settings-provider-help-item">
                        <strong>3. 保存后返回 Chat</strong>
                        <p>保存成功后回到 Chat，页面会重新根据运行时配置决定是否解锁输入。</p>
                    </div>
                </div>
            </div>
        </>
    )
}

function ReadOnlySettingsPanel({
    dictionaryBadge,
    dictionaryItems,
    errorMessage,
    fileNodes,
    loadingContent,
    loadingDictionary,
    loadingTree,
    modeTag,
    readFile,
    refreshDictionary,
    selectedContent,
    selectedPath,
}) {
    return (
        <>
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
        </>
    )
}

export default function SettingsPage() {
    const [activeTab, setActiveTab] = useState('provider')
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
            title="Settings"
            badge={activeTab === 'provider' ? 'Provider' : 'Dictionary'}
            description="先配置生成 provider，再按需查看只读设定文件和词典条目。"
        >
            <div className="settings-tabs" role="tablist" aria-label="Settings 标签页">
                <button
                    type="button"
                    role="tab"
                    className={`settings-tab ${activeTab === 'provider' ? 'active' : ''}`}
                    aria-selected={activeTab === 'provider'}
                    onClick={() => setActiveTab('provider')}
                >
                    Provider
                </button>
                <button
                    type="button"
                    role="tab"
                    className={`settings-tab ${activeTab === 'readonly' ? 'active' : ''}`}
                    aria-selected={activeTab === 'readonly'}
                    onClick={() => setActiveTab('readonly')}
                >
                    Read-only 设定
                </button>
            </div>

            {activeTab === 'provider' ? <ProviderSettingsPanel /> : null}
            {activeTab === 'readonly' ? (
                <ReadOnlySettingsPanel
                    dictionaryBadge={dictionaryBadge}
                    dictionaryItems={dictionaryItems}
                    errorMessage={errorMessage}
                    fileNodes={fileNodes}
                    loadingContent={loadingContent}
                    loadingDictionary={loadingDictionary}
                    loadingTree={loadingTree}
                    modeTag={modeTag}
                    readFile={readFile}
                    refreshDictionary={refreshDictionary}
                    selectedContent={selectedContent}
                    selectedPath={selectedPath}
                />
            ) : null}
        </PageScaffold>
    )
}
