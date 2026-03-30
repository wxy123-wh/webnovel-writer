import { useCallback, useState } from 'react'

export default function Composer({ onSend, disabled }) {
    const [text, setText] = useState('')

    const handleSend = useCallback(() => {
        const trimmed = text.trim()
        if (!trimmed || disabled) return
        onSend(trimmed)
        setText('')
    }, [disabled, onSend, text])

    const handleKeyDown = useCallback(event => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            handleSend()
        }
    }, [handleSend])

    return (
        <div className="composer">
            <textarea
                className="composer-input"
                value={text}
                onChange={event => setText(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
                rows={2}
                disabled={disabled}
            />
            <button
                className="composer-send"
                onClick={handleSend}
                disabled={disabled || !text.trim()}
                type="button"
            >
                发送
            </button>
        </div>
    )
}
