import re

path = r'd:\code\webnovel-writer\running\sisyphus-dispatcher.ps1'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '    $result = & git -C $RepoRoot worktree add -b $branchName $worktreePath HEAD 2>&1\n    if ($LASTEXITCODE -ne 0) {\n        throw "git worktree add failed: $($result | Out-String)"\n    }'

new = '''    $prevEA = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $hadNative = $null -ne (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)
    if ($hadNative) { $prevNative = $PSNativeCommandUseErrorActionPreference; $PSNativeCommandUseErrorActionPreference = $false }
    $result = & git -C $RepoRoot worktree add -b $branchName $worktreePath HEAD 2>&1
    $gitExit = $LASTEXITCODE
    if ($hadNative) { $PSNativeCommandUseErrorActionPreference = $prevNative }
    $ErrorActionPreference = $prevEA
    if ($gitExit -ne 0) {
        throw "git worktree add failed (exit $gitExit): " + ($result | Out-String)
    }'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('PATCHED OK')
else:
    idx = content.find('worktree add')
    if idx >= 0:
        print('NOT_FOUND - context around worktree add:')
        print(repr(content[max(0,idx-100):idx+300]))
    else:
        print('worktree add not found in file at all')
