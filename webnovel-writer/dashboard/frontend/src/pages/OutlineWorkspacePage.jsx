import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import ResplitDialog from '../components/ResplitDialog.jsx'
import { useContextMenu } from '../components/ContextMenuProvider.jsx'
import {
    formatCodexBridgeError,
    openCodexFileEditDialog,
    openCodexSplitDialog,
} from '../api/codexBridge.js'
import {
    applyOutlineSplit,
    createOutlineWorkspace,
    fetchOutlineBundle,
    fetchOutlineSplitHistory,
    formatOutlineApiError,
} from '../api/outlines.js'

const EDIT_ASSIST_TARGET_FILE = '大纲/总纲.md'
const EDIT_ASSIST_DEFAULT_PROMPT = '请在不改变关键信息的前提下提升叙事节奏和冲突张力。'
const CODEX_OUTLINE_FILE_MAP = {
    master: '大纲/总纲.md',
    detail: '大纲/细纲.md',
}
const CODEX_OUTLINE_FILE_EDIT_PROMPT = '请直接修改选中的大纲文本，保持世界设定一致并增强可写性。'

const DUAL_LAYOUT_STYLE = {
    display: 'grid',
    gap: 14,
    gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
}

const TEXTAREA_STYLE = {
    width: '100%',
    minHeight: 260,
    borderRadius: 8,
    border: '2px solid #8f7f5c',
    background: '#fff',
    color: '#2a220f',
    fontSize: 13,
    lineHeight: 1.6,
    padding: 10,
    resize: 'vertical',
    fontFamily: 'inherit',
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

const PREVIEW_LIST_STYLE = {
    margin: 0,
    paddingLeft: 18,
    lineHeight: 1.7,
    fontSize: 13,
    color: '#5d5035',
}

function buildSelectionPayload(textareaRef) {
    const element = textareaRef.current
    if (!element) {
        return { selectionStart: 0, selectionEnd: 0, selectionText: '' }
    }

    const start = element.selectionStart ?? 0
    const end = element.selectionEnd ?? 0
    const text = element.value?.slice(start, end) || ''
    return {
        selectionStart: start,
        selectionEnd: end,
        selectionText: text,
    }
}

function buildIdempotencyKey(selectionStart, selectionEnd, selectionText) {
    const textHash = Array.from(selectionText || '')
        .reduce((acc, char) => (acc * 31 + char.charCodeAt(0)) % 1000000007, 7)
    return `fe-${selectionStart}-${selectionEnd}-${textHash}`
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

async function requestEditAssistPreview({ workspace, selection, signal }) {
    const response = await fetch('/api/edit-assist/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            workspace,
            file_path: EDIT_ASSIST_TARGET_FILE,
            selection_start: Math.max(0, selection.selectionStart),
            selection_end: Math.max(0, selection.selectionEnd),
            selection_text: selection.selectionText || '',
            prompt: EDIT_ASSIST_DEFAULT_PROMPT,
        }),
        signal,
    })

    const rawText = await response.text()
    let payload = {}
    if (rawText) {
        try {
            payload = JSON.parse(rawText)
        } catch {
            payload = { message: rawText }
        }
    }

    if (!response.ok) {
        const detail = payload?.detail || payload
        const error = new Error(detail?.message || `${response.status} ${response.statusText}`)
        error.status = response.status
        error.errorCode = detail?.error_code || 'api_request_failed'
        error.details = detail?.details || null
        throw error
    }

    return payload
}

export default function OutlineWorkspacePage() {
    const { openForEvent } = useContextMenu()
    const masterRef = useRef(null)
    const detailRef = useRef(null)
    const lastMasterSelectionRef = useRef({ selectionStart: 0, selectionEnd: 0, selectionText: '' })
    const workspace = useMemo(() => createOutlineWorkspace(), [])

    const [lastAction, setLastAction] = useState('尚未触发')
    const [errorMessage, setErrorMessage] = useState('')
    const [totalOutline, setTotalOutline] = useState('')
    const [detailedOutline, setDetailedOutline] = useState('')
    const [previewSegments, setPreviewSegments] = useState([])
    const [splitHistory, setSplitHistory] = useState([])
    const [assistPreview, setAssistPreview] = useState(null)
    const [loadingBundle, setLoadingBundle] = useState(true)
    const [splitting, setSplitting] = useState(false)
    const [assisting, setAssisting] = useState(false)
    const [launchingCodexFileEdit, setLaunchingCodexFileEdit] = useState(false)
    const [resplitDialogOpen, setResplitDialogOpen] = useState(false)
    const [resplitSelection, setResplitSelection] = useState({
        selectionStart: 0,
        selectionEnd: 0,
    })

    const refreshBundle = useCallback(async () => {
        setLoadingBundle(true)
        setErrorMessage('')
        try {
            const [bundle, history] = await Promise.all([
                fetchOutlineBundle({
                    workspaceId: workspace.workspace_id,
                    projectRoot: workspace.project_root,
                }),
                fetchOutlineSplitHistory({
                    workspaceId: workspace.workspace_id,
                    projectRoot: workspace.project_root,
                    limit: 20,
                    offset: 0,
                }),
            ])
            setTotalOutline(bundle.total_outline || '')
            setDetailedOutline(bundle.detailed_outline || '')
            setSplitHistory(Array.isArray(history.items) ? history.items : [])
        } catch (error) {
            setErrorMessage(formatOutlineApiError(error))
            setLastAction('bundle-refresh -> failed')
        } finally {
            setLoadingBundle(false)
        }
    }, [workspace.project_root, workspace.workspace_id])

    useEffect(() => {
        void refreshBundle()
    }, [refreshBundle])

    const runSplitPreview = useCallback(async selection => {
        if (!hasValidSelection(selection)) {
            setLastAction('split-preview -> 未检测到有效选区')
            return
        }
        setSplitting(true)
        setErrorMessage('')
        try {
            const result = await openCodexSplitDialog({
                workspaceId: workspace.workspace_id,
                projectRoot: workspace.project_root,
                selectionStart: selection.selectionStart,
                selectionEnd: selection.selectionEnd,
                selectionText: selection.selectionText,
            })
            setPreviewSegments([])
            setLastAction(`split-preview -> Codex 对话已启动 (${result.prompt_file || 'no-prompt-file'})`)
        } catch (error) {
            setPreviewSegments([])
            setErrorMessage(formatCodexBridgeError(error, 'CODEX_SPLIT_DIALOG_OPEN_FAILED'))
            setLastAction('split-preview -> failed')
        } finally {
            setSplitting(false)
        }
    }, [workspace.project_root, workspace.workspace_id])

    const runSplitApply = useCallback(async selection => {
        if (!hasValidSelection(selection)) {
            setLastAction('split-apply -> 未检测到有效选区')
            return
        }

        setSplitting(true)
        setErrorMessage('')
        const idempotencyKey = buildIdempotencyKey(
            selection.selectionStart,
            selection.selectionEnd,
            selection.selectionText,
        )
        try {
            const result = await applyOutlineSplit({
                ...selection,
                workspaceId: workspace.workspace_id,
                projectRoot: workspace.project_root,
                idempotencyKey,
            })
            const count = result.record?.segments?.length || 0
            const idempotencyStatus = result.idempotency?.status || 'created'
            setLastAction(`split-apply -> ${count} 段, key=${idempotencyKey}, status=${idempotencyStatus}`)
            await refreshBundle()
        } catch (error) {
            setErrorMessage(formatOutlineApiError(error, 'OUTLINE_SPLIT_APPLY_FAILED'))
            setLastAction('split-apply -> failed')
        } finally {
            setSplitting(false)
        }
    }, [refreshBundle, workspace.project_root, workspace.workspace_id])

    const runAssistEdit = useCallback(async selection => {
        if (!hasValidSelection(selection)) {
            setLastAction('assist-edit -> 请先在总纲中选中有效区间')
            return
        }

        setAssisting(true)
        setErrorMessage('')
        try {
            const previewResult = await requestEditAssistPreview({
                workspace,
                selection,
            })
            const proposal = previewResult?.proposal || null
            setAssistPreview(proposal)
            setLastAction(`assist-edit -> preview ready (${proposal?.id || 'proposal-unknown'})`)
        } catch (error) {
            setAssistPreview(null)
            setErrorMessage(formatOutlineApiError(error, 'EDIT_ASSIST_PREVIEW_FAILED'))
            setLastAction('assist-edit -> failed')
        } finally {
            setAssisting(false)
        }
    }, [workspace])

    const runCodexFileEdit = useCallback(async (selection, panel) => {
        if (!hasValidSelection(selection)) {
            setLastAction('codex-file-edit -> 未检测到有效选区')
            return
        }

        const targetFile = CODEX_OUTLINE_FILE_MAP[panel] || CODEX_OUTLINE_FILE_MAP.master
        setLaunchingCodexFileEdit(true)
        setErrorMessage('')
        try {
            const result = await openCodexFileEditDialog({
                workspaceId: workspace.workspace_id,
                projectRoot: workspace.project_root,
                filePath: targetFile,
                selectionStart: selection.selectionStart,
                selectionEnd: selection.selectionEnd,
                selectionText: selection.selectionText,
                instruction: CODEX_OUTLINE_FILE_EDIT_PROMPT,
                sourceId: `outline.${panel}.editor`,
            })
            setLastAction(
                `codex-file-edit -> ${result.target_file || targetFile} (${result.prompt_file || 'no-prompt-file'}), 完成后请刷新双纲`,
            )
        } catch (error) {
            setErrorMessage(formatCodexBridgeError(error, 'CODEX_FILE_EDIT_DIALOG_OPEN_FAILED'))
            setLastAction('codex-file-edit -> failed')
        } finally {
            setLaunchingCodexFileEdit(false)
        }
    }, [workspace.project_root, workspace.workspace_id])

    const handleResplitApplied = useCallback(async result => {
        const status = result?.idempotency?.status || 'created'
        setLastAction(`resplit-apply -> ${result?.record?.id || 'unknown-record'} (${status})`)
        setResplitDialogOpen(false)
        await refreshBundle()
    }, [refreshBundle])

    const handleMenuAction = useCallback(async payload => {
        const actionId = payload.actionId
        const panel = payload.meta?.panel === 'detail' ? 'detail' : 'master'
        const panelSelectionFromMenu = payload.meta?.selection || { selectionStart: 0, selectionEnd: 0, selectionText: '' }
        const masterSelectionFromMenu = payload.meta?.masterSelection || { selectionStart: 0, selectionEnd: 0, selectionText: '' }

        if (panel === 'master' && hasValidSelection(panelSelectionFromMenu)) {
            lastMasterSelectionRef.current = panelSelectionFromMenu
        }

        const masterSelection = hasValidSelection(masterSelectionFromMenu)
            ? masterSelectionFromMenu
            : lastMasterSelectionRef.current
        const panelSelection = hasValidSelection(panelSelectionFromMenu)
            ? panelSelectionFromMenu
            : panel === 'master'
                ? lastMasterSelectionRef.current
                : { selectionStart: 0, selectionEnd: 0, selectionText: '' }

        if (actionId === 'split-preview') {
            await runSplitPreview(masterSelection)
            return
        }
        if (actionId === 'split-apply') {
            await runSplitApply(masterSelection)
            return
        }

        if (actionId === 'resplit-preview') {
            if (!hasValidSelection(masterSelection)) {
                setLastAction('resplit-preview -> 请先在总纲中选中有效区间')
                return
            }
            setErrorMessage('')
            setResplitSelection({
                selectionStart: masterSelection.selectionStart,
                selectionEnd: masterSelection.selectionEnd,
            })
            setResplitDialogOpen(true)
            setLastAction(`resplit-preview -> open [${masterSelection.selectionStart}, ${masterSelection.selectionEnd})`)
            return
        }
        if (actionId === 'assist-edit') {
            await runAssistEdit(masterSelection)
            return
        }
        if (actionId === 'codex-file-edit') {
            await runCodexFileEdit(panelSelection, panel)
            return
        }
        setLastAction(`${actionId} -> no-op`)
    }, [runAssistEdit, runCodexFileEdit, runSplitApply, runSplitPreview])

    const openOutlineMenu = useCallback((event, panel) => {
        const currentMasterSelection = buildSelectionPayload(masterRef)
        if (hasValidSelection(currentMasterSelection)) {
            lastMasterSelectionRef.current = currentMasterSelection
        }
        const currentDetailSelection = buildSelectionPayload(detailRef)
        const panelSelection = panel === 'master'
            ? currentMasterSelection
            : currentDetailSelection
        const masterSelection = hasValidSelection(currentMasterSelection)
            ? currentMasterSelection
            : lastMasterSelectionRef.current

        openForEvent(event, {
            sourceId: `outline.${panel}.editor`,
            meta: {
                panel,
                selection: panelSelection,
                masterSelection,
            },
            onAction: payload => {
                void handleMenuAction(payload)
            },
            items: [
                {
                    id: 'split-preview',
                    actionId: 'split-preview',
                    label: '拆分预览',
                    shortcut: 'P',
                    disabled: panel !== 'master',
                },
                {
                    id: 'split-apply',
                    actionId: 'split-apply',
                    label: '应用拆分',
                    shortcut: 'A',
                    disabled: panel !== 'master',
                },
                {
                    id: 'resplit-preview',
                    actionId: 'resplit-preview',
                    label: '重拆预览',
                    shortcut: 'R',
                    disabled: panel !== 'detail',
                },
                {
                    id: 'assist-edit',
                    actionId: 'assist-edit',
                    label: '协助修改',
                    shortcut: 'G',
                    disabled: panel !== 'master' || !hasValidSelection(masterSelection),
                },
                {
                    id: 'codex-file-edit',
                    actionId: 'codex-file-edit',
                    label: 'Codex直接改文件',
                    shortcut: 'C',
                    disabled: !hasValidSelection(panelSelection),
                },
            ],
        })
    }, [handleMenuAction, openForEvent])

    const splitCountBadge = useMemo(() => {
        if (loadingBundle) {
            return '加载中'
        }
        return `${splitHistory.length} 条拆分记录`
    }, [loadingBundle, splitHistory.length])

    return (
        <PageScaffold
            title="双纲工作台"
            badge="Outline Workspace"
            description="选中文本后右键可直接拉起 Codex；支持拆分对话与直接改写文件。"
        >
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" style={BUTTON_STYLE} disabled={loadingBundle} onClick={refreshBundle}>
                    刷新双纲数据
                </button>
                <span className="card-badge badge-green">mode: API</span>
                <span className="card-badge badge-blue">{splitCountBadge}</span>
                <span className="card-badge badge-purple">{launchingCodexFileEdit ? 'codex: launching' : 'codex: ready'}</span>
            </div>

            {errorMessage ? (
                <div className="card" style={{ borderColor: '#d46a57' }}>
                    <div className="card-header">
                        <span className="card-title">请求失败</span>
                        <span className="card-badge badge-amber">可重试</span>
                    </div>
                    <p style={{ margin: 0, color: '#9a2a1a' }}>{errorMessage}</p>
                </div>
            ) : null}

            <div style={DUAL_LAYOUT_STYLE}>
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">总纲区</span>
                        <span className="card-badge badge-green">sourceId: outline.master.editor</span>
                    </div>
                    <textarea
                        ref={masterRef}
                        value={totalOutline}
                        style={TEXTAREA_STYLE}
                        onChange={event => setTotalOutline(event.target.value)}
                        onContextMenu={event => openOutlineMenu(event, 'master')}
                    />
                    <p style={{ margin: '8px 0 0 0', fontSize: 12, color: '#8f7f5c' }}>
                        操作提示: 选中文本后右键，可选择“拆分预览”或“Codex直接改文件”。
                    </p>
                </div>

                <div className="card">
                    <div className="card-header">
                        <span className="card-title">细纲区</span>
                        <span className="card-badge badge-blue">sourceId: outline.detail.editor</span>
                    </div>
                    <textarea
                        ref={detailRef}
                        value={detailedOutline}
                        onChange={event => setDetailedOutline(event.target.value)}
                        style={TEXTAREA_STYLE}
                        onContextMenu={event => openOutlineMenu(event, 'detail')}
                    />
                    <p style={{ margin: '8px 0 0 0', fontSize: 12, color: '#8f7f5c' }}>
                        重拆预览仍使用总纲选区；细纲区可直接用 Codex 修改当前文件。
                    </p>
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <span className="card-title">拆分预览</span>
                    <span className="card-badge badge-amber">{splitting ? '处理中' : `${previewSegments.length} 段`}</span>
                </div>
                {previewSegments.length === 0 ? (
                    <p style={{ margin: 0, color: '#8f7f5c' }}>暂无预览结果。</p>
                ) : (
                    <ol style={PREVIEW_LIST_STYLE}>
                        {previewSegments.map(segment => (
                            <li key={segment.id}>
                                <strong>{segment.title}</strong> - {segment.content}
                            </li>
                        ))}
                    </ol>
                )}
            </div>

            <div className="card">
                <div className="card-header">
                    <span className="card-title">协助修改预览</span>
                    <span className="card-badge badge-purple">{assisting ? '处理中' : 'edit-assist'}</span>
                </div>
                {!assistPreview ? (
                    <p style={{ margin: 0, color: '#8f7f5c' }}>尚未触发协助修改预览。</p>
                ) : (
                    <div style={{ display: 'grid', gap: 8 }}>
                        <p style={{ margin: 0, fontSize: 12, color: '#8f7f5c' }}>
                            proposal: {assistPreview.id || 'unknown-proposal'}
                        </p>
                        <p style={{ margin: 0, fontSize: 13, color: '#5d5035' }}>
                            {assistPreview.preview || assistPreview.after_text || ''}
                        </p>
                    </div>
                )}
            </div>

            <div className="card">
                <div className="card-header">
                    <span className="card-title">协议回执</span>
                    <span className="card-badge badge-purple">Context Menu Contract Reusable</span>
                </div>
                <p style={{ margin: 0 }}>最近动作: {lastAction}</p>
            </div>

            <ResplitDialog
                isOpen={resplitDialogOpen}
                workspace={workspace}
                selectionStart={resplitSelection.selectionStart}
                selectionEnd={resplitSelection.selectionEnd}
                onClose={() => {
                    setResplitDialogOpen(false)
                }}
                onApplied={result => {
                    void handleResplitApplied(result)
                }}
            />
        </PageScaffold>
    )
}
