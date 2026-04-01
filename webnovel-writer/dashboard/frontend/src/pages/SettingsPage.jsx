import { useCallback, useEffect, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import {
    fetchProviderSettings,
    updateProviderSettings,
} from '../api/settings.js'

const DEFAULT_PROVIDER_FORM = {
    provider: '',
    base_url: '',
    model: '',
    api_key: '',
    clear_api_key: false,
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

export default function SettingsPage() {
    return (
        <PageScaffold
            title="Settings"
            badge="Provider"
            description="配置生成服务的 Provider、Model 与 API Key。"
        >
            <ProviderSettingsPanel />
        </PageScaffold>
    )
}
