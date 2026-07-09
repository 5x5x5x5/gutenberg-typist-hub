# typist guild

The path: learn to touch type with [GNU gtypist](https://www.gnu.org/software/gtypist/),
graduate to typing real books with the
[gutenberg-typist](https://github.com/5x5x5x5/gutenberg-typist) Vim plugin,
then put your stats on the board here.

**The board: <https://5x5x5x5.github.io/typist-guild/>**

The current residents are fictional — seed data, characters typing their own
books (usernames like `mina-harker-1897` link nowhere on purpose). Every seat
is takeable; their bundles get deleted as real typists arrive.

## Join the board

No invite needed — fork, clone your fork, point `upstream` at this repo:

```sh
gh repo fork 5x5x5x5/typist-guild --clone ~/.gt-hub
# or without gh: fork in the GitHub UI, then
git clone git@github.com:<you>/typist-guild.git ~/.gt-hub
cd ~/.gt-hub && git remote add upstream git@github.com:5x5x5x5/typist-guild.git
```

(`gh repo fork --clone` sets `upstream` for you.)

Your submissions go up as pull requests that **merge themselves**: a bot merges
any PR that only updates `bundles/<your-username>.json` and passes validation.
No waiting on a human.

Collaborators with push access can clone this repo directly instead — `submit`
detects which layout you have.

## Submit your stats

```vim
:GT export
:!~/.gt-hub/submit
```

That's it — live on the board a minute or two later. The first run asks for
your GitHub username (cached in git config); your stats live in
`bundles/<you>.json`.

Handy mapping for your vimrc:

```vim
nnoremap <leader>gp :GT export<CR>:!~/.gt-hub/submit<CR>
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
  and deploys Pages. PRs run `validate.yml`, which strict-checks exactly the
  bundles the PR touches.
- `automerge.yml` lands validated PRs automatically when they change only
  the author's own bundle file; anything else waits for human review.
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
