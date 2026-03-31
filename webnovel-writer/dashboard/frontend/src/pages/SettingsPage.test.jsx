import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const {
    fetchProviderSettings,
    updateProviderSettings,
    fetchSettingsFileTree,
    listSettingDictionary,
    readSettingsFile,
} = vi.hoisted(() => ({
    fetchProviderSettings: vi.fn(),
    updateProviderSettings: vi.fn(),
    fetchSettingsFileTree: vi.fn(),
    listSettingDictionary: vi.fn(),
    readSettingsFile: vi.fn(),
}))

vi.mock('../api/settings.js', () => ({
    fetchProviderSettings,
    updateProviderSettings,
    fetchSettingsFileTree,
    listSettingDictionary,
    readSettingsFile,
    isMockResponse: () => false,
}))

import SettingsPage from './SettingsPage.jsx'

describe('SettingsPage', () => {
    beforeEach(() => {
        fetchProviderSettings.mockResolvedValue({
            provider: 'openai',
            base_url: 'https://api.openai.com/v1',
            model: 'gpt-4.1-mini',
            api_key_configured: true,
            configured: true,
        })
        updateProviderSettings.mockResolvedValue({
            provider: 'openrouter',
            base_url: 'https://openrouter.ai/api/v1',
            model: 'openai/gpt-4.1-mini',
            api_key_configured: true,
            configured: true,
        })
        fetchSettingsFileTree.mockResolvedValue({
            nodes: [
                {
                    type: 'file',
                    path: 'settings/world.md',
                    name: 'world.md',
                },
            ],
        })
        listSettingDictionary.mockResolvedValue({
            items: [
                {
                    id: 'item-1',
                    term: '天穹城',
                    type: 'location',
                    status: 'active',
                    source_file: 'settings/world.md',
                    source_span: '1-4',
                },
            ],
        })
        readSettingsFile.mockResolvedValue({
            content: '天穹城设定内容',
        })
    })

    afterEach(() => {
        vi.clearAllMocks()
        cleanup()
    })

    it('opens on the Provider tab, loads provider settings, and saves changes through the settings API', async () => {
        render(<SettingsPage />)

        expect(screen.getByRole('tab', { name: 'Provider' }).getAttribute('aria-selected')).toBe('true')

        await waitFor(() => {
            expect(fetchProviderSettings).toHaveBeenCalledTimes(1)
        })

        const providerInput = await screen.findByRole('textbox', { name: 'Provider' })
        fireEvent.change(providerInput, { target: { value: 'openrouter' } })
        fireEvent.change(screen.getByRole('textbox', { name: 'Model' }), { target: { value: 'openai/gpt-4.1-mini' } })
        fireEvent.change(screen.getByRole('textbox', { name: 'Base URL' }), { target: { value: 'https://openrouter.ai/api/v1' } })
        fireEvent.change(screen.getByLabelText('API Key'), { target: { value: 'sk-test' } })

        fireEvent.click(screen.getByRole('button', { name: '保存配置' }))

        await waitFor(() => {
            expect(updateProviderSettings).toHaveBeenCalledWith({
                provider: 'openrouter',
                base_url: 'https://openrouter.ai/api/v1',
                model: 'openai/gpt-4.1-mini',
                api_key: 'sk-test',
                clear_api_key: false,
            })
        })

        expect(await screen.findByText('Provider 配置已保存，Chat 现在可以重新检查运行时状态。')).toBeTruthy()
    })

    it('keeps the read-only settings and dictionary view available under the second tab', async () => {
        render(<SettingsPage />)

        await waitFor(() => {
            expect(fetchSettingsFileTree).toHaveBeenCalledTimes(1)
            expect(listSettingDictionary).toHaveBeenCalledTimes(1)
            expect(readSettingsFile).toHaveBeenCalledWith({ path: 'settings/world.md' })
        })

        fireEvent.click(screen.getByRole('tab', { name: 'Read-only 设定' }))

        expect(screen.getByText('设定文件树')).toBeTruthy()
        expect(screen.getByText('设定词典')).toBeTruthy()
        expect(screen.getByText('天穹城')).toBeTruthy()
        expect(screen.getByText('天穹城设定内容')).toBeTruthy()
    })
})
