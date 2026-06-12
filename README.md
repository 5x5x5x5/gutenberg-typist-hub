# gutenberg-typist stats

Typing leaderboard for the [gutenberg-typist](https://github.com/5x5x5x5/gutenberg-typist)
Vim plugin.

**The board: <https://5x5x5x5.github.io/gutenberg-typist-stats/>**

## Join the board

One-time setup:

1. Ask [@5x5x5x5](https://github.com/5x5x5x5) for push access (or fork and submit by PR).
2. Clone:

   ```sh
   git clone git@github.com:5x5x5x5/gutenberg-typist-stats.git ~/.gt-stats
   ```

## Submit your stats

```vim
:GT export
:!~/.gt-stats/submit
```

That's it — live on the board about a minute later. The first run asks for your
GitHub username (cached in git config); your stats live in `bundles/<you>.json`.

Handy mapping for your vimrc:

```vim
nnoremap <leader>gp :GT export<CR>:!~/.gt-stats/submit<CR>
```

Submissions **merge**: counters are combined per machine by field-wise max, so
exporting from your laptop never clobbers your desktop's numbers, and
re-submitting the same export is a no-op. `submit` prints your new rank before
pushing.

## Privacy & honor system

This is a public repo: your stats — and their full git history — are public
and effectively permanent. Machine names appear on the board; set
`g:gt_machine_id` in your vimrc if your hostname is something you'd rather not
share. Nothing prevents creative JSON editing; implausible numbers just get a
`?` badge. It's a beta among friends.

## How it works

```
bundles/*.json  --build.py-->  _site/data.json + static page  --Actions-->  GitHub Pages
```

- `bundles/` is the database: one `:GT export` bundle per user, filename = GitHub username.
- `build.py` (stdlib-only) validates every bundle, derives the comparable
  metrics, and writes `_site/`. Malformed bundles are skipped and listed on
  the page — they never break the board.
- Pushing to `main` triggers `.github/workflows/deploy.yml`, which rebuilds
  and deploys Pages. PRs run `validate.yml`, which fails on invalid bundles.
- Every submission is a commit, so git history is a free time-series for
  future charts.

## Development

```sh
uv run pytest                                    # tests
uv run ruff check . && uv run mypy build.py      # lint + types
python3 build.py && python3 -m http.server -d _site   # local preview
```

New metric = a few lines in `build.py` (derive + tests) and a column entry in
`site/app.js`. PRs welcome — this beta exists to experiment.
