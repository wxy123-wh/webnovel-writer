import * as fs from 'node:fs/promises';
import * as path from 'node:path';

export interface FileEntry {
    absolutePath: string;
    relativePath: string;
}

export interface TreeNode {
    kind: 'workspace' | 'group' | 'folder' | 'chapter' | 'scene' | 'file' | 'message';
    id: string;
    label: string;
    description?: string;
    absolutePath?: string;
    relativePath?: string;
    children?: TreeNode[];
}

interface FastIndexData {
    chapters?: Record<string, string[]>;
    scenes?: Record<string, string[]>;
}

const TEXT_EXTENSIONS = new Set([
    '.md',
    '.txt',
    '.text',
    '.json',
    '.yaml',
    '.yml',
    '.toml',
    '.ini',
    '.cfg',
    '.csv',
    '.log',
]);

const SKIPPED_DIRECTORIES = new Set([
    '.git',
    '.hg',
    '.svn',
    '.idea',
    '.vscode',
    '.venv',
    'venv',
    'node_modules',
    '__pycache__',
    '.pytest_cache',
    '.ruff_cache',
    'dist',
    'out',
    'coverage',
    '__temp__',
    '.work',
    '.worktrees',
]);

const PRIORITY_FOLDERS: Array<{ label: string; names: string[] }> = [
    { label: 'Chapters & Content', names: ['正文', 'chapters', 'chapter', 'content'] },
    { label: 'Outlines', names: ['大纲', 'outline', 'outlines'] },
    { label: 'Settings', names: ['设定集', '设定', 'settings', 'references', 'reference'] },
    { label: 'Scenes', names: ['scenes', 'scene'] },
    { label: 'Docs', names: ['docs'] },
];

const CHAPTER_PATTERN = /第\s*(\d+)\s*章/;
const SCENE_PATTERN = /【([^\]【】\r\n]+)】/g;
const MAX_SCAN_BYTES = 32 * 1024;
const NATURAL_COMPARE = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

function compareNatural(left: string, right: string): number {
    return NATURAL_COMPARE.compare(left, right);
}

function normalizeRelativePath(filePath: string): string {
    return filePath.split(path.sep).join('/');
}

function isTextLike(filePath: string): boolean {
    return TEXT_EXTENSIONS.has(path.extname(filePath).toLowerCase());
}

function matchesPriorityFolder(folderName: string): { label: string; folderName: string } | undefined {
    const normalized = folderName.toLowerCase();
    for (const group of PRIORITY_FOLDERS) {
        const matchedName = group.names.find(name => name.toLowerCase() === normalized);
        if (matchedName) {
            return { label: group.label, folderName: matchedName };
        }
    }

    return undefined;
}

function ensureChildren(node: TreeNode): TreeNode[] {
    if (!node.children) {
        node.children = [];
    }

    return node.children;
}

function createFileNode(fileEntry: FileEntry): TreeNode {
    return {
        kind: 'file',
        id: `file:${fileEntry.relativePath}`,
        label: path.basename(fileEntry.absolutePath),
        description: fileEntry.relativePath,
        absolutePath: fileEntry.absolutePath,
        relativePath: fileEntry.relativePath,
    };
}

function createMessageNode(parentId: string, label: string): TreeNode {
    return {
        kind: 'message',
        id: `${parentId}:message:${label}`,
        label,
    };
}

function buildFolderTree(rootLabel: string, rootId: string, files: FileEntry[], baseDir?: string): TreeNode {
    const root: TreeNode = {
        kind: 'folder',
        id: rootId,
        label: rootLabel,
        children: [],
    };

    const folderIndex = new Map<string, TreeNode>([[rootId, root]]);

    for (const fileEntry of [...files].sort((left, right) => compareNatural(left.relativePath, right.relativePath))) {
        const pathForTree = baseDir
            ? normalizeRelativePath(path.relative(baseDir, fileEntry.absolutePath))
            : fileEntry.relativePath;
        const segments = pathForTree.split('/').filter(Boolean);
        let current = root;
        let currentId = rootId;

        for (const segment of segments.slice(0, -1)) {
            currentId = `${currentId}/${segment}`;
            let next = folderIndex.get(currentId);
            if (!next) {
                next = {
                    kind: 'folder',
                    id: currentId,
                    label: segment,
                    children: [],
                };
                ensureChildren(current).push(next);
                folderIndex.set(currentId, next);
            }
            current = next;
        }

        ensureChildren(current).push(createFileNode(fileEntry));
    }

    sortTree(root);
    return root;
}

function sortTree(node: TreeNode): void {
    if (!node.children) {
        return;
    }

    node.children.sort((left, right) => {
        const leftFolder = left.kind === 'folder';
        const rightFolder = right.kind === 'folder';
        if (leftFolder !== rightFolder) {
            return leftFolder ? -1 : 1;
        }
        return compareNatural(left.label, right.label);
    });

    for (const child of node.children) {
        sortTree(child);
    }
}

async function safeReadFileSample(filePath: string): Promise<string> {
    const handle = await fs.open(filePath, 'r');
    try {
        const buffer = Buffer.alloc(MAX_SCAN_BYTES);
        const { bytesRead } = await handle.read(buffer, 0, buffer.length, 0);
        return buffer.subarray(0, bytesRead).toString('utf8');
    } finally {
        await handle.close();
    }
}

async function walkTextFiles(
    workspaceRoot: string,
    currentDir: string,
    files: FileEntry[],
    priorityMatches: Map<string, Set<string>>,
): Promise<void> {
    const directoryEntries = await fs.readdir(currentDir, { withFileTypes: true });
    directoryEntries.sort((left, right) => compareNatural(left.name, right.name));

    for (const entry of directoryEntries) {
        const absolutePath = path.join(currentDir, entry.name);
        if (entry.isDirectory()) {
            if (SKIPPED_DIRECTORIES.has(entry.name)) {
                continue;
            }

            const matchedPriority = matchesPriorityFolder(entry.name);
            if (matchedPriority) {
                if (!priorityMatches.has(matchedPriority.label)) {
                    priorityMatches.set(matchedPriority.label, new Set<string>());
                }
                priorityMatches.get(matchedPriority.label)?.add(absolutePath);
            }

            await walkTextFiles(workspaceRoot, absolutePath, files, priorityMatches);
            continue;
        }

        if (!entry.isFile() || !isTextLike(absolutePath)) {
            continue;
        }

        files.push({
            absolutePath,
            relativePath: normalizeRelativePath(path.relative(workspaceRoot, absolutePath)),
        });
    }
}

function addGroupedFile(
    groups: Map<string, Set<string>>,
    groupKey: string,
    relativePath: string,
): void {
    if (!groups.has(groupKey)) {
        groups.set(groupKey, new Set<string>());
    }

    groups.get(groupKey)?.add(normalizeRelativePath(relativePath));
}

async function collectFallbackGroups(files: FileEntry[]): Promise<{ chapters: Map<string, Set<string>>; scenes: Map<string, Set<string>> }> {
    const chapters = new Map<string, Set<string>>();
    const scenes = new Map<string, Set<string>>();

    for (const fileEntry of files) {
        const chapterMatch = CHAPTER_PATTERN.exec(path.basename(fileEntry.absolutePath));
        if (chapterMatch) {
            addGroupedFile(chapters, chapterMatch[1], fileEntry.relativePath);
        }

        const sample = await safeReadFileSample(fileEntry.absolutePath);
        const chapterInContent = sample.match(CHAPTER_PATTERN);
        if (chapterInContent?.[1]) {
            addGroupedFile(chapters, chapterInContent[1], fileEntry.relativePath);
        }

        let sceneMatch = SCENE_PATTERN.exec(sample);
        while (sceneMatch) {
            const sceneName = sceneMatch[1].trim();
            if (sceneName) {
                addGroupedFile(scenes, sceneName, fileEntry.relativePath);
            }
            sceneMatch = SCENE_PATTERN.exec(sample);
        }
        SCENE_PATTERN.lastIndex = 0;
    }

    return { chapters, scenes };
}

async function readFastIndex(workspaceRoot: string): Promise<FastIndexData | undefined> {
    const fastIndexPath = path.join(workspaceRoot, '.webnovel', 'codex', 'fast-index.json');
    try {
        const raw = await fs.readFile(fastIndexPath, 'utf8');
        return JSON.parse(raw) as FastIndexData;
    } catch {
        return undefined;
    }
}

function buildGroupedNodes(
    kind: 'chapter' | 'scene',
    labelPrefix: string,
    sourceGroups: Map<string, Set<string>> | Record<string, string[]> | undefined,
    workspaceRoot: string,
    fileByRelativePath: Map<string, FileEntry>,
): TreeNode[] {
    if (!sourceGroups) {
        return [];
    }

    const entries = sourceGroups instanceof Map
        ? [...sourceGroups.entries()].map(([key, value]) => [key, [...value]] as const)
        : Object.entries(sourceGroups);

    return entries
        .sort(([left], [right]) => compareNatural(left, right))
        .map(([groupKey, filePaths]) => {
            const normalizedGroupLabel = kind === 'chapter' && /^\d+$/.test(groupKey)
                ? String(Number.parseInt(groupKey, 10))
                : groupKey;
            const children = [...new Set(filePaths)]
                .map(relativePath => normalizeRelativePath(relativePath))
                .map(relativePath => fileByRelativePath.get(relativePath) ?? {
                    absolutePath: path.join(workspaceRoot, relativePath),
                    relativePath,
                })
                .sort((left, right) => compareNatural(left.relativePath, right.relativePath))
                .map(fileEntry => createFileNode(fileEntry));

            return {
                kind,
                id: `${kind}:${groupKey}`,
                label: labelPrefix ? `${labelPrefix}${normalizedGroupLabel}` : normalizedGroupLabel,
                description: `${children.length} file${children.length === 1 ? '' : 's'}`,
                children,
            } satisfies TreeNode;
        });
}

export async function discoverWorkspaceTree(workspaceRoot: string, workspaceLabel?: string): Promise<TreeNode> {
    const files: FileEntry[] = [];
    const priorityMatches = new Map<string, Set<string>>();
    await walkTextFiles(workspaceRoot, workspaceRoot, files, priorityMatches);

    const fileByRelativePath = new Map(files.map(fileEntry => [fileEntry.relativePath, fileEntry]));
    const fastIndex = await readFastIndex(workspaceRoot);
    const fallbackGroups = await collectFallbackGroups(files);

    const chapterNodes = buildGroupedNodes(
        'chapter',
        'Chapter ',
        fastIndex?.chapters ?? fallbackGroups.chapters,
        workspaceRoot,
        fileByRelativePath,
    );
    const sceneNodes = buildGroupedNodes(
        'scene',
        '',
        fastIndex?.scenes ?? fallbackGroups.scenes,
        workspaceRoot,
        fileByRelativePath,
    );

    const importantFolderNodes = [...priorityMatches.entries()]
        .sort(([left], [right]) => compareNatural(left, right))
        .map(([groupLabel, directoryPaths]) => {
            const directoryNodes = [...directoryPaths]
                .sort((left, right) => compareNatural(left, right))
                .map(directoryPath => {
                    const nestedFiles = files.filter(fileEntry => {
                        const relativeToDirectory = path.relative(directoryPath, fileEntry.absolutePath);
                        return relativeToDirectory && !relativeToDirectory.startsWith('..') && !path.isAbsolute(relativeToDirectory);
                    });

                    return buildFolderTree(
                        normalizeRelativePath(path.relative(workspaceRoot, directoryPath)) || path.basename(directoryPath),
                        `priority:${groupLabel}:${normalizeRelativePath(path.relative(workspaceRoot, directoryPath))}`,
                        nestedFiles,
                        directoryPath,
                    );
                });

            return {
                kind: 'group',
                id: `group:priority:${groupLabel}`,
                label: groupLabel,
                children: directoryNodes.length > 0
                    ? directoryNodes
                    : [createMessageNode(`group:priority:${groupLabel}`, 'No matching folders found.')],
            } satisfies TreeNode;
        });

    const allFilesNode = buildFolderTree('Workspace', 'group:workspaceFiles', files);

    return {
        kind: 'workspace',
        id: `workspace:${workspaceRoot}`,
        label: workspaceLabel ?? path.basename(workspaceRoot),
        description: normalizeRelativePath(workspaceRoot),
        children: [
            {
                kind: 'group',
                id: 'group:chapters',
                label: 'Chapters',
                description: fastIndex?.chapters ? 'fast-index' : 'workspace scan',
                children: chapterNodes.length > 0
                    ? chapterNodes
                    : [createMessageNode('group:chapters', 'No chapter entries found.')],
            },
            {
                kind: 'group',
                id: 'group:scenes',
                label: 'Scenes',
                description: fastIndex?.scenes ? 'fast-index' : 'workspace scan',
                children: sceneNodes.length > 0
                    ? sceneNodes
                    : [createMessageNode('group:scenes', 'No scene entries found.')],
            },
            {
                kind: 'group',
                id: 'group:importantFolders',
                label: 'Important Text Folders',
                children: importantFolderNodes.length > 0
                    ? importantFolderNodes
                    : [createMessageNode('group:importantFolders', 'No priority text folders found.')],
            },
            {
                kind: 'group',
                id: 'group:allTextFiles',
                label: 'All Text Files',
                description: `${files.length} files`,
                children: allFilesNode.children?.length ? allFilesNode.children : [createMessageNode('group:allTextFiles', 'No text files found.')],
            },
        ],
    };
}
