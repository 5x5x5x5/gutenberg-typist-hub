"use strict";

const COLUMNS = [
  { key: "user", label: "user" },
  { key: "best_wpm", label: "best wpm" },
  { key: "avg_wpm", label: "avg wpm" },
  { key: "accuracy", label: "accuracy", fmt: (v) => v.toFixed(1) + "%" },
  { key: "hours", label: "hours" },
  { key: "total_chars", label: "chars", fmt: (v) => v.toLocaleString("en-US") },
  { key: "sessions", label: "sessions" },
  { key: "books", label: "books" },
  { key: "machines_count", label: "machines" },
  { key: "exported_at", label: "updated", fmt: relativeTime },
];

let state = {
  rows: [],
  sortKey: "best_wpm",
  dir: -1,
  open: new Set(),
  filter: "",
  total: 0,
};

function relativeTime(epoch) {
  if (!epoch) return "—";
  const s = Math.floor(Date.now() / 1000) - epoch;
  if (s < 90) return "just now";
  const units = [
    [31536000, "y"],
    [2592000, "mo"],
    [604800, "w"],
    [86400, "d"],
    [3600, "h"],
    [60, "m"],
  ];
  for (const [span, label] of units) {
    if (s >= span) return Math.floor(s / span) + label + " ago";
  }
  return s + "s ago";
}

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of children) node.append(child);
  return node;
}

function sortRows() {
  const { sortKey, dir } = state;
  const byUser = (a, b) =>
    a.user.localeCompare(b.user, "en", { sensitivity: "base" });
  state.rows.sort((a, b) => {
    const av = a[sortKey],
      bv = b[sortKey];
    const cmp =
      typeof av === "string"
        ? av.localeCompare(bv, "en", { sensitivity: "base" })
        : av - bv;
    // dir = 1 ascending, -1 descending; equal values tiebreak by username.
    return cmp !== 0 ? cmp * dir : byUser(a, b);
  });
}

function renderHead(thead) {
  const tr = el("tr");
  tr.append(el("th", { className: "rank-col", textContent: "" }));
  tr.append(el("th", { className: "rank-col", textContent: "#" }));
  for (const col of COLUMNS) {
    const arrow =
      state.sortKey === col.key ? (state.dir === -1 ? " ▼" : " ▲") : "";
    const th = el("th", { textContent: col.label + arrow });
    th.dataset.key = col.key;
    if (state.sortKey === col.key) th.classList.add("sorted");
    th.addEventListener("click", () => {
      if (state.sortKey === col.key) state.dir = -state.dir;
      else {
        state.sortKey = col.key;
        state.dir = col.key === "user" ? 1 : -1;
      }
      render();
    });
    tr.append(th);
  }
  thead.replaceChildren(tr);
}

function foldCell(row) {
  const cell = el("td", { colSpan: COLUMNS.length + 2 });
  const machines = el("ul");
  for (const [id, rec] of Object.entries(row.machines)) {
    machines.append(
      el("li", {}, [
        id + " — ",
        el("span", {
          className: "muted",
          textContent:
            `${(rec.total_chars || 0).toLocaleString("en-US")} chars · ` +
            `${Math.round(((rec.total_time_seconds || 0) / 3600) * 10) / 10} h · ` +
            `best ${rec.best_wpm || 0} wpm · ${rec.sessions_count || 0} sessions`,
        }),
      ]),
    );
  }
  const books = el("ul");
  for (const book of row.books_detail) {
    const link = el("a", {
      href: "https://www.gutenberg.org/ebooks/" + book.book_id,
      textContent: "#" + book.book_id,
      target: "_blank",
      rel: "noopener",
    });
    books.append(
      el("li", {}, [
        link,
        el("span", {
          className: "muted",
          textContent:
            ` · ${(book.offset || 0).toLocaleString("en-US")} chars in` +
            (book.last_active ? ` · ${relativeTime(book.last_active)}` : ""),
        }),
      ]),
    );
  }
  const wrap = el("div", { className: "fold" });
  wrap.append(
    el("h4", { textContent: `machines (${Object.keys(row.machines).length})` }),
    machines,
  );
  if (row.books_detail.length)
    wrap.append(
      el("h4", { textContent: `books (${row.books_detail.length})` }),
      books,
    );
  cell.append(wrap);
  return cell;
}

function visibleRows() {
  if (!state.filter) return state.rows;
  const needle = state.filter.toLowerCase();
  return state.rows.filter((row) => row.user.toLowerCase().includes(needle));
}

function renderBody(tbody) {
  tbody.replaceChildren();
  visibleRows().forEach((row, i) => {
    const tr = el("tr", { className: "row" });
    if (
      i === 0 &&
      state.sortKey === "best_wpm" &&
      state.dir === -1 &&
      !state.filter
    )
      tr.classList.add("leader");
    const caret = el("td", {}, [
      el("span", {
        className: "caret",
        textContent: state.open.has(row.user) ? "▾" : "▸",
      }),
    ]);
    tr.append(caret);
    tr.append(el("td", { className: "rank", textContent: String(i + 1) }));
    for (const col of COLUMNS) {
      const td = el("td");
      if (col.key === "user") {
        td.className = "user";
        td.append(
          el("a", {
            href: "https://github.com/" + encodeURIComponent(row.user),
            textContent: row.user,
            target: "_blank",
            rel: "noopener",
          }),
        );
        if (row.suspicious) {
          td.append(
            el("span", {
              className: "badge",
              textContent: "?",
              title: "implausible numbers — honor system",
            }),
          );
        }
      } else {
        const value = row[col.key];
        td.textContent = col.fmt ? col.fmt(value) : String(value);
      }
      tr.append(td);
    }
    tr.addEventListener("click", (event) => {
      if (event.target.closest("a")) return;
      if (state.open.has(row.user)) state.open.delete(row.user);
      else state.open.add(row.user);
      render();
    });
    tbody.append(tr);
    if (state.open.has(row.user)) {
      const fold = el("tr", { className: "fold" });
      fold.append(foldCell(row));
      tbody.append(fold);
    }
  });
}

function render() {
  sortRows();
  const table = document.getElementById("board");
  renderHead(table.querySelector("thead"));
  renderBody(table.querySelector("tbody"));
  const shown = visibleRows().length;
  document.getElementById("count").textContent = state.filter
    ? `${shown}/${state.total} shown`
    : `${state.total} on the board`;
}

function renderModeline(data) {
  const parts = [];
  if (data.skipped.length) {
    // Cap the list: with many users a pile-up of bad bundles must not
    // turn the modeline into a wall of text.
    const shown = data.skipped
      .slice(0, 3)
      .map((s) => `${s.user}: ${s.reason}`)
      .join(", ");
    const more =
      data.skipped.length > 3 ? ` +${data.skipped.length - 3} more` : "";
    parts.push(`${data.skipped.length} skipped (${shown}${more})`);
  }
  parts.push("generated " + relativeTime(data.generated_at));
  document.getElementById("meta").textContent = parts.join(" · ");
}

// Vim-style "/" filter: slash focuses the filter box, Escape clears it.
function initFilter() {
  const input = document.getElementById("filter");
  input.addEventListener("input", () => {
    state.filter = input.value.trim();
    render();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      input.value = "";
      state.filter = "";
      input.blur();
      render();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement !== input) {
      event.preventDefault();
      input.focus();
    }
  });
}

fetch("data.json")
  .then((res) => {
    if (!res.ok) throw new Error(res.status);
    return res.json();
  })
  .then((data) => {
    state.rows = data.users;
    state.total = data.users.length;
    renderModeline(data);
    if (!data.users.length) {
      document.getElementById("empty").hidden = false;
      document.getElementById("count").textContent = "0 on the board";
      return;
    }
    document.getElementById("board").hidden = false;
    document.getElementById("filterwrap").hidden = false;
    initFilter();
    render();
  })
  .catch(() => {
    document.getElementById("error").hidden = false;
    document.getElementById("meta").textContent = "data.json failed to load";
  });
