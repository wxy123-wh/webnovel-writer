import { useState } from 'react'
import PageScaffold from '../components/PageScaffold.jsx'
import NewBookWizard from './NewBookWizard.jsx'

export default function CreationDeskPage() {
    const [showWizard, setShowWizard] = useState(false)
    const [successNotice, setSuccessNotice] = useState('')

    function handleWizardSuccess() {
        setShowWizard(false)
        setSuccessNotice('书籍项目创建成功！')
        // auto-dismiss after 4s
        setTimeout(() => setSuccessNotice(''), 4000)
    }

    return (
        <PageScaffold title="创作台" badge="Creation Desk">
            {successNotice ? (
                <div className="settings-notice settings-notice-success">{successNotice}</div>
            ) : null}

            <div className="card">
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
                <p style={{ margin: 0, color: '#8b7a5e' }}>
                    点击「新建书籍」开始创建你的小说项目。
                </p>
            </div>

            {showWizard ? (
                <NewBookWizard
                    onClose={() => setShowWizard(false)}
                    onSuccess={handleWizardSuccess}
                />
            ) : null}
        </PageScaffold>
    )
}
