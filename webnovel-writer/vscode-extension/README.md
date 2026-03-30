# Webnovel Writer VS Code Extension

Read-only sidebar browser for Webnovel Writer projects. It uses native VS Code tree views and native editor opening.

## What it shows

- Chapters, with `.webnovel/codex/fast-index.json` used when present
- Scenes, with the same fast index preferred and a lightweight file-scan fallback
- Important text folders such as `正文`, `大纲`, `设定集`, `设定`, `content`, `outline`, `outlines`, `docs`, and `references`
- A full workspace text-file tree for common text-like files

The extension does **not** write files, generate content, or replace the CLI. It is a read-only browser for the existing CLI-first workflow.

## Development

```bash
cd webnovel-writer/vscode-extension
npm install
npm run typecheck
npm run test
```

To try it locally in VS Code:

1. Open this `vscode-extension` folder in VS Code.
2. Run `npm install` and `npm run build`.
3. Press `F5` to launch an Extension Development Host.
4. Open a Webnovel Writer project folder in that host.
5. Use the **Webnovel Writer** activity bar icon and the **Refresh** action when project files change.

## Notes

- The browser is intentionally read-only.
- It opens files with VS Code's built-in editor via the normal `vscode.open` flow.
- Fast index support is limited to reading `.webnovel/codex/fast-index.json`; the extension does not create or maintain that file.
- "All text content" currently means common text-like files discovered by extension, including `.md`, `.txt`, `.json`, `.yaml`, `.yml`, `.toml`, `.ini`, `.cfg`, `.csv`, and `.log`.
- When `fast-index.json` is absent, chapter and scene grouping falls back to lightweight workspace scanning and manual refresh.
