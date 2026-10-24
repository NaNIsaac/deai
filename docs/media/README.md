# README media

`demo.gif` is recorded with [vhs](https://github.com/charmbracelet/vhs) (0.12.1, with ttyd and
ffmpeg) from this commit's `deai`, on a throwaway repository:

```sh
uv sync
vhs docs/media/demo.tape
```

The hidden part of `demo.tape` puts `.venv/Scripts` first on PATH (the tape uses pwsh), runs
`demo_repo.py` to create `$env:TEMP/my-app` with the three commits of the README's "Before"
example (fixed names and dates, so the same hashes every time), and deletes it at the end. The
visible part types `deai scan`, `deai clean`, `y` and `git log`.

A second recording gives the same commands and output except the time in the backup file name;
vhs's frame timing differs between runs, so the file is not byte-identical.
