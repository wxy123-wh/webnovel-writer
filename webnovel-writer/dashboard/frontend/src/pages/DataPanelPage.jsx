import { useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import DashboardPage from './DashboardPage.jsx'
import EntitiesPage from './EntitiesPage.jsx'
import GraphPage from './GraphPage.jsx'
import ChaptersPage from './ChaptersPage.jsx'
import ReadingPowerPage from './ReadingPowerPage.jsx'
import FilesPage from './FilesPage.jsx'

const SUB_TABS = [
    { id: 'overview',  label: '总览' },
    { id: 'entities',  label: '实体' },
    { id: 'graph',     label: '关系图' },
    { id: 'chapters',  label: '章节' },
    { id: 'reading',   label: '阅读力' },
    { id: 'files',     label: '文件' },
]

const SUB_TAB_COMPONENTS = {
    overview: DashboardPage,
    entities: EntitiesPage,
    graph: GraphPage,
    chapters: ChaptersPage,
    reading: ReadingPowerPage,
    files: FilesPage,
}

export default function DataPanelPage() {
    const [activeTab, setActiveTab] = useState('overview')

    const ActiveComponent = SUB_TAB_COMPONENTS[activeTab]

    return (
        <PageScaffold title="数据面板">
            <div className="settings-tabs" role="tablist" aria-label="数据面板标签页">
                {SUB_TABS.map(({ id, label }) => (
                    <button
                        key={id}
                        type="button"
                        role="tab"
                        className={`settings-tab ${activeTab === id ? 'active' : ''}`}
                        aria-selected={activeTab === id}
                        onClick={() => setActiveTab(id)}
                    >
                        {label}
                    </button>
                ))}
            </div>

            <div style={{ marginTop: 'var(--space-sm, 8px)' }}>
                <ActiveComponent />
            </div>

            <p style={{
                marginTop: 'var(--space-md, 16px)',
                padding: '8px 12px',
                fontSize: 12,
                color: 'var(--text-muted, #8a7e6b)',
                background: 'var(--bg-subtle, #faf5eb)',
                borderRadius: 'var(--radius-sm, 4px)',
                border: '1px solid var(--border-main, #e0d5c1)',
            }}>
                提示：数据需要通过 Pipeline 生成。运行
                <code style={{
                    margin: '0 4px',
                    padding: '1px 5px',
                    background: 'var(--bg-card, #fff)',
                    border: '1px solid var(--border-main, #e0d5c1)',
                    borderRadius: 3,
                    fontFamily: 'var(--font-mono, monospace)',
                    fontSize: 11,
                }}>
                    python -X utf8 webnovel-writer/scripts/webnovel.py codex index status
                </code>
                查看索引状态。
            </p>
        </PageScaffold>
    )
}
