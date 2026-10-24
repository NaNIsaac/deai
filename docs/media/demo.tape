# Run from the repository root after `uv sync`: vhs docs/media/demo.tape
Output docs/media/demo.gif

Set Shell "pwsh"
Set FontSize 15
Set Width 1120
Set Height 560
Set Padding 16
Set TypingSpeed 25ms

Hide
Type "$env:PATH = (Resolve-Path .venv/Scripts).Path + ';' + $env:PATH; $env:GIT_PAGER = 'cat'; $demo = Join-Path $env:TEMP my-app; Remove-Item -Recurse -Force $demo -ErrorAction Ignore; uv run -q python docs/media/demo_repo.py $demo; Set-Location $demo; Clear-Host"
Enter
Sleep 4s
Show

Type "deai scan"
Enter
Sleep 1.5s
Type "deai clean"
Enter
Sleep 1s
Type "y"
Enter
Sleep 2s
Type "git log --format='%h %s%n%w(0,8,8)%b'"
Enter
Sleep 3s

Hide
Type "Set-Location $env:TEMP; Remove-Item -Recurse -Force $demo"
Enter
