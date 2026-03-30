import test from 'node:test';
import * as assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { discoverWorkspaceTree } from '../discovery';

async function makeTempWorkspace(prefix: string): Promise<string> {
    return fs.mkdtemp(path.join(os.tmpdir(), prefix));
}

test('discoverWorkspaceTree prefers fast-index for chapters and scenes', async () => {
    const workspaceRoot = await makeTempWorkspace('webnovel-vscode-fast-index-');
    await fs.mkdir(path.join(workspaceRoot, '.webnovel', 'codex'), { recursive: true });
    await fs.mkdir(path.join(workspaceRoot, '正文'), { recursive: true });
    await fs.writeFile(
        path.join(workspaceRoot, '正文', '第0001章-开场.md'),
        '第 1 章\n【开场】\n内容',
        'utf8',
    );
    await fs.writeFile(
        path.join(workspaceRoot, '.webnovel', 'codex', 'fast-index.json'),
        JSON.stringify({
            chapters: { '1': ['正文/第0001章-开场.md'] },
            scenes: { '开场': ['正文/第0001章-开场.md'] },
            files: {
                '正文/第0001章-开场.md': { chapter: '1', scenes: ['开场'] },
            },
        }),
        'utf8',
    );

    const tree = await discoverWorkspaceTree(workspaceRoot, 'book');
    const chaptersGroup = tree.children?.find(node => node.label === 'Chapters');
    const scenesGroup = tree.children?.find(node => node.label === 'Scenes');

    assert.ok(chaptersGroup);
    assert.equal(chaptersGroup?.description, 'fast-index');
    assert.equal(chaptersGroup?.children?.[0]?.label, 'Chapter 1');
    assert.equal(chaptersGroup?.children?.[0]?.children?.[0]?.relativePath, '正文/第0001章-开场.md');

    assert.ok(scenesGroup);
    assert.equal(scenesGroup?.description, 'fast-index');
    assert.equal(scenesGroup?.children?.[0]?.label, '开场');
});

test('discoverWorkspaceTree falls back to workspace scanning and priority folders', async () => {
    const workspaceRoot = await makeTempWorkspace('webnovel-vscode-scan-');
    await fs.mkdir(path.join(workspaceRoot, '正文'), { recursive: true });
    await fs.mkdir(path.join(workspaceRoot, '设定集'), { recursive: true });
    await fs.mkdir(path.join(workspaceRoot, '大纲'), { recursive: true });

    await fs.writeFile(path.join(workspaceRoot, '正文', '第0002章-风起.md'), '第 2 章\n【夜谈】\n正文', 'utf8');
    await fs.writeFile(path.join(workspaceRoot, '设定集', '世界观.md'), '# 世界观', 'utf8');
    await fs.writeFile(path.join(workspaceRoot, '大纲', '总纲.md'), '# 总纲', 'utf8');

    const tree = await discoverWorkspaceTree(workspaceRoot, 'book');
    const chaptersGroup = tree.children?.find(node => node.label === 'Chapters');
    const scenesGroup = tree.children?.find(node => node.label === 'Scenes');
    const importantFoldersGroup = tree.children?.find(node => node.label === 'Important Text Folders');
    const allFilesGroup = tree.children?.find(node => node.label === 'All Text Files');

    assert.equal(chaptersGroup?.description, 'workspace scan');
    assert.equal(chaptersGroup?.children?.[0]?.label, 'Chapter 2');
    assert.equal(scenesGroup?.children?.[0]?.label, '夜谈');

    const settingsGroup = importantFoldersGroup?.children?.find(node => node.label === 'Settings');
    assert.ok(settingsGroup);
    assert.equal(settingsGroup?.children?.[0]?.label, '设定集');

    assert.ok(allFilesGroup?.children?.some(node => node.label === '大纲'));
    assert.ok(allFilesGroup?.children?.some(node => node.label === '正文'));
});
