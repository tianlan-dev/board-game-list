#!/usr/bin/env python3
"""
Generate a printable, sortable HTML table from data.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MECHANISM_LABELS = {
    "areaControl": "区域控制",
    "workerPlacement": "工人放置",
    "engineBuilding": "引擎构筑",
    "cardDriven": "卡牌驱动",
    "deckBuilding": "牌库构筑",
    "drafting": "轮抽",
    "resourceManagement": "资源管理",
    "tilePlacement": "板块拼放",
    "routeBuilding": "路线建设",
    "economic": "经济系统",
    "actionSelection": "行动选择",
    "dice": "骰子机制",
    "tableauBuilding": "个人版图构筑",
}


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="icon" href="/favicon.png" type="image/png">
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f7f4;
      --panel: #ffffff;
      --text: #20201d;
      --muted: #6f6d66;
      --line: #d9d7cf;
      --line-strong: #b9b6aa;
      --accent: #176b87;
      --accent-soft: #e4f2f4;
      --tag: #ece9df;
      --shadow: 0 10px 28px rgba(35, 34, 29, 0.08);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }}

    .page {{
      max-width: 1480px;
      margin: 0 auto;
      padding: 24px;
    }}

    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 18px;
    }}

    h1 {{
      margin: 0 0 6px;
      font-size: 28px;
      line-height: 1.15;
      font-weight: 760;
      letter-spacing: 0;
    }}

    .meta {{
      color: var(--muted);
      font-size: 13px;
    }}

    .stats {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}

    .stat {{
      display: inline-flex;
      align-items: baseline;
      gap: 6px;
      min-height: 28px;
      padding: 4px 9px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--muted);
      font-size: 13px;
    }}

    .stat strong {{
      color: var(--text);
      font-size: 16px;
      font-weight: 720;
    }}

    .toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 14px;
      padding: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}

    .toolbar-group {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      min-width: 0;
    }}

    .filters {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .filter-menu {{
      position: relative;
    }}

    .filter-menu summary {{
      display: inline-flex;
      align-items: center;
      min-height: 36px;
      padding: 0 12px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
      white-space: nowrap;
      cursor: pointer;
      list-style: none;
    }}

    .filter-menu summary::-webkit-details-marker {{
      display: none;
    }}

    .filter-menu summary::after {{
      content: "▾";
      margin-left: 8px;
      color: var(--muted);
      font-size: 11px;
    }}

    .filter-menu[open] summary {{
      border-color: var(--accent);
      color: var(--accent);
    }}

    .filter-panel {{
      position: absolute;
      top: calc(100% + 6px);
      left: 0;
      z-index: 10;
      display: grid;
      gap: 4px;
      min-width: 210px;
      max-height: 320px;
      overflow: auto;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      box-shadow: var(--shadow);
    }}

    .filter-option {{
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 30px;
      padding: 4px 6px;
      border-radius: 5px;
      color: var(--text);
      font-size: 13px;
      cursor: pointer;
    }}

    .filter-option:hover {{
      background: var(--accent-soft);
    }}

    .filter-option input {{
      margin: 0;
    }}

    label {{
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }}

    input[type="search"] {{
      width: min(420px, 52vw);
      height: 36px;
      padding: 0 12px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
    }}

    button {{
      height: 36px;
      padding: 0 12px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
      cursor: pointer;
    }}

    button:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}

    .table-wrap {{
      overflow: auto;
      max-height: calc(100vh - 158px);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}

    table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      min-width: 1180px;
    }}

    th,
    td {{
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      border-right: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
      white-space: nowrap;
    }}

    th[data-key="gameName"],
    td[data-key="gameName"] {{
      width: clamp(240px, 28vw, 420px);
      max-width: clamp(240px, 28vw, 420px);
      white-space: normal;
    }}

    th[data-key="players"],
    td[data-key="players"] {{
      width: 132px;
      max-width: 132px;
      white-space: normal;
    }}

    th:last-child,
    td:last-child {{
      border-right: 0;
    }}

    thead th {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: #efeee8;
      color: #2b2a27;
      font-size: 12px;
      font-weight: 720;
      user-select: none;
      cursor: pointer;
    }}

    thead th.dragging {{
      opacity: 0.5;
    }}

    thead th.drag-target {{
      outline: 2px solid var(--accent);
      outline-offset: -2px;
    }}

    tbody tr:nth-child(even) {{
      background: #fbfaf7;
    }}

    tbody tr:hover {{
      background: var(--accent-soft);
    }}

    .sort-indicator {{
      display: inline-block;
      width: 1.1em;
      color: var(--accent);
      font-weight: 800;
    }}

    .number {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}

    .muted {{
      color: var(--muted);
    }}

    .name-en {{
      font-weight: 650;
      display: inline;
      overflow-wrap: anywhere;
      line-height: 1.28;
    }}

    .name-size-sm {{
      font-size: 13px;
    }}

    .name-size-xs {{
      font-size: 12px;
    }}

    .name-size-xxs {{
      font-size: 11px;
    }}

    .tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      max-width: 380px;
      white-space: normal;
    }}

    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 7px;
      border-radius: 999px;
      background: var(--tag);
      color: #3f3d36;
      font-size: 12px;
      line-height: 1.2;
      break-inside: avoid;
    }}

    .empty {{
      color: var(--muted);
    }}

    a {{
      color: var(--accent);
      text-decoration: none;
    }}

    a:hover {{
      text-decoration: underline;
    }}

    @media (max-width: 760px) {{
      .page {{
        padding: 14px;
      }}

      header,
      .toolbar {{
        align-items: stretch;
        flex-direction: column;
      }}

      .toolbar-group {{
        width: 100%;
      }}

      input[type="search"] {{
        width: 100%;
      }}

      .table-wrap {{
        max-height: calc(100vh - 214px);
      }}
    }}

    @media print {{
      @page {{
        size: landscape;
        margin: 10mm;
      }}

      body {{
        background: #fff;
        font-size: 10px;
      }}

      .page {{
        max-width: none;
        padding: 0;
      }}

      .toolbar {{
        display: none;
      }}

      header {{
        margin-bottom: 8px;
      }}

      h1 {{
        font-size: 18px;
      }}

      .table-wrap {{
        max-height: none;
        overflow: visible;
        border: 0;
        box-shadow: none;
      }}

      table {{
        min-width: 0;
        font-size: 9px;
      }}

      th,
      td {{
        padding: 4px 5px;
        white-space: normal;
      }}

      thead th {{
        position: static;
        background: #eee;
      }}

      tbody tr {{
        break-inside: avoid;
      }}

      .tag {{
        border: 1px solid #ccc;
        background: #fff;
        font-size: 8px;
        min-height: 0;
        padding: 1px 4px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <div>
        <h1>{title}</h1>
        <div class="meta" id="summary"></div>
        <div class="stats" id="overallStats" aria-label="整体统计"></div>
      </div>
      <div class="meta">生成时间：{generated_at}</div>
    </header>

    <div class="toolbar">
      <div class="toolbar-group">
        <label for="search">搜索</label>
        <input id="search" type="search" placeholder="名称、机制、状态、年份..." autocomplete="off">
      </div>
      <div class="toolbar-group filters" aria-label="显示过滤器">
        <details class="filter-menu">
          <summary id="collectionFilterSummary">In Collection: Both</summary>
          <div class="filter-panel">
            <label class="filter-option"><input type="checkbox" data-filter="collection-true" checked>In Collection</label>
            <label class="filter-option"><input type="checkbox" data-filter="collection-false" checked>Not in Collection</label>
          </div>
        </details>
        <details class="filter-menu">
          <summary id="bggFilterSummary">In BGG: Both</summary>
          <div class="filter-panel">
            <label class="filter-option"><input type="checkbox" data-filter="bgg-true" checked>In BGG</label>
            <label class="filter-option"><input type="checkbox" data-filter="bgg-false" checked>Not in BGG</label>
          </div>
        </details>
        <details class="filter-menu">
          <summary id="idFilterSummary">ID: Both</summary>
          <div class="filter-panel">
            <label class="filter-option"><input type="checkbox" data-filter="id-present" checked>Has ID</label>
            <label class="filter-option"><input type="checkbox" data-filter="id-null" checked>No ID</label>
          </div>
        </details>
        <details class="filter-menu">
          <summary id="rankFilterSummary">Rank: Both</summary>
          <div class="filter-panel">
            <label class="filter-option"><input type="checkbox" data-filter="rank-present" checked>Has Rank</label>
            <label class="filter-option"><input type="checkbox" data-filter="rank-null" checked>No Rank</label>
          </div>
        </details>
        <details class="filter-menu">
          <summary id="mechanismFilterSummary">机制: All</summary>
          <div class="filter-panel" id="mechanismFilterPanel"></div>
        </details>
        <details class="filter-menu">
          <summary id="columnFilterSummary">列: All</summary>
          <div class="filter-panel" id="columnFilterPanel"></div>
        </details>
      </div>
      <div class="toolbar-group">
        <button type="button" id="resetColumns">重置列顺序</button>
        <button type="button" id="printPage">打印</button>
      </div>
    </div>

    <div class="table-wrap">
      <table id="gamesTable">
        <thead></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <script id="game-data" type="application/json">{payload}</script>
  <script>
    const payload = JSON.parse(document.getElementById("game-data").textContent);
    const games = Array.isArray(payload.games) ? payload.games : [];
    const mechanismLabels = payload.mechanismLabels || {{}};
    const storageKey = "board-game-list-columns";
    const table = document.getElementById("gamesTable");
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    const searchInput = document.getElementById("search");
    const summary = document.getElementById("summary");
    const overallStats = document.getElementById("overallStats");
    const mechanismFilterPanel = document.getElementById("mechanismFilterPanel");
    const columnFilterPanel = document.getElementById("columnFilterPanel");

    const columns = [
      {{ key: "bggRank", label: "排名", type: "number", value: game => game.bggRank }},
      {{ key: "id", label: "ID", type: "number", value: game => game.id, render: renderId, locked: true }},
      {{ key: "gameName", label: "游戏名", type: "text", value: gameNameText, render: (value, game) => renderName(value, game, "name-en") }},
      {{ key: "year", label: "年份", type: "number", value: game => game.year }},
      {{ key: "weight", label: "重度", type: "number", value: game => game.weight }},
      {{ key: "players", label: "人数", type: "text", value: game => playerText(game.players) }},
      {{ key: "playingTime", label: "时长", type: "number", value: game => timeText(game.playingTime) }},
      {{ key: "age", label: "年龄", type: "number", value: game => ageText(game.age) }},
      {{ key: "userRating", label: "我的评分", type: "number", value: game => game.userRating }},
      {{ key: "bggRating", label: "BGG评分", type: "number", value: game => game.bggRating }},
      {{ key: "bggAverageRating", label: "平均评分", type: "number", value: game => game.bggAverageRating }},
      {{ key: "status", label: "状态", type: "text", value: game => statusText(game.status), render: value => tags(value.split("、").filter(Boolean)) }},
      {{ key: "mechanisms", label: "机制", type: "text", value: game => mechanismText(game.mechanisms), render: value => tags(value.split("、").filter(Boolean)) }},
      {{ key: "bggMechanics", label: "BGG机制", type: "text", value: game => listText(game.bggMechanics), render: value => tags(value.split("、").filter(Boolean)) }},
      {{ key: "bggCategories", label: "BGG分类", type: "text", value: game => listText(game.bggCategories), render: value => tags(value.split("、").filter(Boolean)) }}
    ];

    let columnOrder = loadColumnOrder();
    let sortState = {{ key: "bggRank", direction: "asc" }};
    let dragKey = null;
    let dragStarted = false;

    buildMechanismFilters();
    buildColumnFilters();
    const filterInputs = [...document.querySelectorAll("[data-filter], [data-mechanism-filter], [data-column-filter]")];

    document.getElementById("printPage").addEventListener("click", () => window.print());
    document.getElementById("resetColumns").addEventListener("click", () => {{
      columnOrder = columns.map(column => column.key);
      localStorage.removeItem(storageKey);
      render();
    }});
    searchInput.addEventListener("input", render);
    filterInputs.forEach(input => input.addEventListener("change", () => {{
      updateFilterSummaries();
      updateColumnFilterAvailability();
      render();
    }}));
    updateFilterSummaries();
    updateColumnFilterAvailability();
    renderOverallStats();

    render();

    function loadColumnOrder() {{
      const fallback = columns.map(column => column.key);
      try {{
        const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
        const known = new Set(fallback);
        const validSaved = saved.filter(key => known.has(key));
        const missing = fallback.filter(key => !validSaved.includes(key));
        return [...validSaved, ...missing];
      }} catch {{
        return fallback;
      }}
    }}

    function saveColumnOrder() {{
      localStorage.setItem(storageKey, JSON.stringify(columnOrder));
    }}

    function buildMechanismFilters() {{
      mechanismFilterPanel.replaceChildren(...Object.entries(mechanismLabels).map(([key, label]) => {{
        const option = document.createElement("label");
        option.className = "filter-option";
        option.innerHTML = `<input type="checkbox" data-mechanism-filter value="${{escapeHtml(key)}}">${{escapeHtml(label)}}`;
        return option;
      }}));
    }}

    function buildColumnFilters() {{
      columnFilterPanel.replaceChildren(...columns.map(column => {{
        const option = document.createElement("label");
        option.className = "filter-option";
        option.innerHTML = `<input type="checkbox" data-column-filter="${{escapeHtml(column.key)}}" value="${{escapeHtml(column.key)}}" checked ${{column.locked ? "disabled" : ""}}>${{escapeHtml(column.label)}}`;
        return option;
      }}));
    }}

    function updateFilterSummaries() {{
      updatePairSummary("collectionFilterSummary", "In Collection", "collection-true", "In Collection", "collection-false", "Not in Collection");
      updatePairSummary("bggFilterSummary", "In BGG", "bgg-true", "In BGG", "bgg-false", "Not in BGG");
      updatePairSummary("idFilterSummary", "ID", "id-present", "Has ID", "id-null", "No ID");
      updatePairSummary("rankFilterSummary", "Rank", "rank-present", "Has Rank", "rank-null", "No Rank");

      const selected = selectedMechanisms().map(key => mechanismLabels[key] || key);
      const mechanismSummary = document.getElementById("mechanismFilterSummary");
      mechanismSummary.textContent = selected.length ? `机制: ${{selected.length}}` : "机制: All";
      mechanismSummary.title = selected.join("、") || "All mechanisms";

      const visibleOptional = [...document.querySelectorAll("[data-column-filter]:not(:disabled):checked")].length;
      const totalOptional = [...document.querySelectorAll("[data-column-filter]:not(:disabled)")].length;
      const columnSummary = document.getElementById("columnFilterSummary");
      columnSummary.textContent = visibleOptional === totalOptional ? "列: All" : `列: ${{visibleOptional + 1}}`;
    }}

    function updatePairSummary(summaryId, label, trueKey, trueLabel, falseKey, falseLabel) {{
      const trueChecked = document.querySelector(`[data-filter="${{trueKey}}"]`).checked;
      const falseChecked = document.querySelector(`[data-filter="${{falseKey}}"]`).checked;
      let value = "None";
      if (trueChecked && falseChecked) value = "Both";
      else if (trueChecked) value = trueLabel;
      else if (falseChecked) value = falseLabel;
      document.getElementById(summaryId).textContent = `${{label}}: ${{value}}`;
    }}

    function orderedColumns() {{
      const byKey = new Map(columns.map(column => [column.key, column]));
      return columnOrder.map(key => byKey.get(key)).filter(Boolean);
    }}

    function visibleColumnKeys() {{
      return new Set([...document.querySelectorAll("[data-column-filter]:checked")].map(input => input.value));
    }}

    function updateColumnFilterAvailability() {{
      const dataColumns = new Set(columns.filter(column => hasColumnData(column)).map(column => column.key));
      document.querySelectorAll("[data-column-filter]").forEach(input => {{
        const column = columns.find(item => item.key === input.value);
        if (column && !column.locked) {{
          input.disabled = !dataColumns.has(input.value);
          input.closest(".filter-option").classList.toggle("muted", input.disabled);
        }}
      }});
    }}

    function render() {{
      const visibleKeys = visibleColumnKeys();
      const visibleColumns = orderedColumns().filter(column => hasColumnData(column) && (column.locked || visibleKeys.has(column.key)));
      const rows = filteredGames();
      rows.sort(compareBy(sortState.key, sortState.direction));
      renderHead(visibleColumns);
      renderBody(rows, visibleColumns);
      summary.textContent = `共 ${{rows.length}} / ${{games.length}} 个游戏` + (payload.lastUpdated ? `，数据更新时间：${{payload.lastUpdated}}` : "");
    }}

    function hasColumnData(column) {{
      if (["id", "gameName", "bggRank", "year", "mechanisms"].includes(column.key)) {{
        return true;
      }}
      return games.some(game => present(column.value(game)));
    }}

    function filteredGames() {{
      const query = searchInput.value.trim().toLowerCase();
      const filters = activeFilters();
      return games.filter(game => matchesFilters(game, filters) && (!query || searchableText(game).includes(query)));
    }}

    function activeFilters() {{
      return Object.fromEntries([...document.querySelectorAll("[data-filter]")].map(input => [input.dataset.filter, input.checked]));
    }}

    function selectedMechanisms() {{
      return [...document.querySelectorAll("[data-mechanism-filter]:checked")].map(input => input.value);
    }}

    function matchesFilters(game, filters) {{
      const inCollection = game.collection === true;
      if (inCollection && !filters["collection-true"]) return false;
      if (!inCollection && !filters["collection-false"]) return false;

      const bggFound = game.bgg === true;
      if (bggFound && !filters["bgg-true"]) return false;
      if (!bggFound && !filters["bgg-false"]) return false;

      const hasId = present(game.id);
      if (hasId && !filters["id-present"]) return false;
      if (!hasId && !filters["id-null"]) return false;

      const hasRank = present(game.bggRank);
      if (hasRank && !filters["rank-present"]) return false;
      if (!hasRank && !filters["rank-null"]) return false;

      const mechanisms = selectedMechanisms();
      if (mechanisms.length && !mechanisms.every(key => game.mechanisms && game.mechanisms[key] === true)) {{
        return false;
      }}

      return true;
    }}

    function searchableText(game) {{
      const parts = orderedColumns().map(column => column.value(game));
      parts.push(...Object.values(game).filter(value => typeof value === "string"));
      return parts.filter(present).join(" ").toLowerCase();
    }}

    function renderHead(visibleColumns) {{
      const row = document.createElement("tr");
      visibleColumns.forEach(column => {{
        const th = document.createElement("th");
        th.draggable = true;
        th.dataset.key = column.key;
        th.title = "点击排序，拖拽调整列位置";
        th.innerHTML = `<span class="sort-indicator">${{sortMark(column.key)}}</span>${{escapeHtml(column.label)}}`;
        th.addEventListener("click", () => {{
          if (dragStarted) {{
            dragStarted = false;
            return;
          }}
          if (sortState.key === column.key) {{
            sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
          }} else {{
            sortState = {{ key: column.key, direction: "asc" }};
          }}
          render();
        }});
        th.addEventListener("dragstart", event => {{
          dragKey = column.key;
          dragStarted = true;
          th.classList.add("dragging");
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", column.key);
        }});
        th.addEventListener("dragend", () => {{
          dragKey = null;
          document.querySelectorAll(".dragging, .drag-target").forEach(el => el.classList.remove("dragging", "drag-target"));
          setTimeout(() => {{
            dragStarted = false;
          }}, 0);
        }});
        th.addEventListener("dragover", event => {{
          event.preventDefault();
          if (dragKey && dragKey !== column.key) {{
            th.classList.add("drag-target");
          }}
        }});
        th.addEventListener("dragleave", () => th.classList.remove("drag-target"));
        th.addEventListener("drop", event => {{
          event.preventDefault();
          th.classList.remove("drag-target");
          const sourceKey = event.dataTransfer.getData("text/plain") || dragKey;
          moveColumn(sourceKey, column.key);
        }});
        row.appendChild(th);
      }});
      thead.replaceChildren(row);
    }}

    function renderBody(rows, visibleColumns) {{
      const fragment = document.createDocumentFragment();
      rows.forEach(game => {{
        const row = document.createElement("tr");
        visibleColumns.forEach(column => {{
          const value = column.value(game);
          const td = document.createElement("td");
          td.dataset.key = column.key;
          if (column.type === "number") {{
            td.classList.add("number");
          }}
          td.innerHTML = column.render ? column.render(value, game) : renderValue(value);
          row.appendChild(td);
        }});
        fragment.appendChild(row);
      }});
      tbody.replaceChildren(fragment);
    }}

    function moveColumn(sourceKey, targetKey) {{
      if (!sourceKey || sourceKey === targetKey) {{
        return;
      }}
      const next = columnOrder.filter(key => key !== sourceKey);
      const targetIndex = next.indexOf(targetKey);
      next.splice(targetIndex, 0, sourceKey);
      columnOrder = next;
      saveColumnOrder();
      render();
    }}

    function compareBy(key, direction) {{
      const column = columns.find(item => item.key === key) || columns[0];
      const multiplier = direction === "asc" ? 1 : -1;
      return (left, right) => {{
        const a = column.value(left);
        const b = column.value(right);
        if (!present(a) && !present(b)) return 0;
        if (!present(a)) return 1;
        if (!present(b)) return -1;
        if (column.type === "number") {{
          return (Number(a) - Number(b)) * multiplier;
        }}
        return String(a).localeCompare(String(b), "zh-Hans-CN", {{ numeric: true, sensitivity: "base" }}) * multiplier;
      }};
    }}

    function sortMark(key) {{
      if (sortState.key !== key) return "";
      return sortState.direction === "asc" ? "▲" : "▼";
    }}

    function present(value) {{
      return value !== null && value !== undefined && value !== "" && !(Array.isArray(value) && value.length === 0);
    }}

    function hasUserRating(game) {{
      return present(game.userRating);
    }}

    function renderOverallStats() {{
      const collectionGames = games.filter(game => game.collection === true);
      const playedCollectionGames = collectionGames.filter(hasUserRating);
      overallStats.innerHTML = `
        <span class="stat">记录的桌游总数 <strong>${{games.length}}</strong></span>
        <span class="stat">BGG collection 已玩/总数 <strong>${{playedCollectionGames.length}} / ${{collectionGames.length}}</strong></span>
      `;
    }}

    function renderValue(value) {{
      if (!present(value)) {{
        return '<span class="empty">-</span>';
      }}
      return escapeHtml(String(value));
    }}

    function renderId(value) {{
      if (!present(value)) {{
        return '<span class="empty">-</span>';
      }}
      return `<a href="https://boardgamegeek.com/boardgame/${{encodeURIComponent(value)}}" target="_blank" rel="noopener">${{escapeHtml(String(value))}}</a>`;
    }}

    function gameNameText(game) {{
      const en = String(game.nameEn || "").trim();
      const zh = String(game.nameZh || "").trim();
      const alias = String(game.alias || "").trim();
      const displayName = alias || zh;
      if (displayName) return `${{en}} (${{displayName}})`;
      return en;
    }}

    function renderName(value, game, className) {{
      if (!present(value)) {{
        return '<span class="empty">-</span>';
      }}
      const content = `<span class="${{className}} ${{nameSizeClass(value)}}">${{escapeHtml(String(value))}}</span>`;
      if (!isBggLinkable(game)) {{
        return content;
      }}
      return `<a href="${{bggUrl(game.id)}}" target="_blank" rel="noopener">${{content}}</a>`;
    }}

    function nameSizeClass(value) {{
      const length = String(value).length;
      if (length > 90) return "name-size-xxs";
      if (length > 64) return "name-size-xs";
      if (length > 42) return "name-size-sm";
      return "";
    }}

    function isBggLinkable(game) {{
      return present(game.id) && game.bgg !== false;
    }}

    function bggUrl(id) {{
      return `https://boardgamegeek.com/boardgame/${{encodeURIComponent(id)}}`;
    }}

    function tags(values) {{
      if (!values.length) {{
        return '<span class="empty">-</span>';
      }}
      return `<div class="tags">${{values.map(value => `<span class="tag">${{escapeHtml(value)}}</span>`).join("")}}</div>`;
    }}

    function playerText(players) {{
      if (!players || typeof players !== "object") return "";
      const min = players.min;
      const max = players.max;
      const range = present(min) && present(max) ? (min === max ? String(min) : `${{min}}-${{max}}`) : "";
      const best = Array.isArray(players.best) && players.best.length ? `最佳 ${{players.best.join("/")}}` : "";
      const recommended = Array.isArray(players.recommended) && players.recommended.length ? `推荐 ${{players.recommended.join("/")}}` : "";
      return [range, best, recommended].filter(Boolean).join("；");
    }}

    function timeText(time) {{
      if (!time || typeof time !== "object") return "";
      const min = time.min;
      const max = time.max;
      if (!present(min) || !present(max)) return "";
      return min === max ? `${{min}} 分钟` : `${{min}}-${{max}} 分钟`;
    }}

    function ageText(age) {{
      if (!age || typeof age !== "object") return "";
      const base = present(age.min) ? `${{age.min}}+` : "";
      const recommended = present(age.recommended) ? `推荐 ${{age.recommended}}+` : "";
      return [base, recommended].filter(Boolean).join("；");
    }}

    function statusText(status) {{
      if (!status || typeof status !== "object") return "";
      const labels = {{
        owned: "拥有",
        previouslyOwned: "曾拥有",
        forTrade: "可交易",
        want: "想要",
        wantToPlay: "想玩",
        wantToBuy: "想买",
        wishlist: "愿望单",
        preordered: "已预订"
      }};
      return Object.entries(labels).filter(([key]) => status[key]).map(([, label]) => label).join("、");
    }}

    function mechanismText(mechanisms) {{
      if (!mechanisms || typeof mechanisms !== "object") return "";
      return Object.entries(mechanisms)
        .filter(([, enabled]) => Boolean(enabled))
        .map(([key]) => mechanismLabels[key] || key)
        .join("、");
    }}

    function listText(values) {{
      return Array.isArray(values) ? values.join("、") : "";
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}
  </script>
</body>
</html>
"""


def load_data(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"lastUpdated": None, "games": data}
    if isinstance(data, dict) and isinstance(data.get("games"), list):
        return data
    raise ValueError("data file must be a games array or an object with a games array")


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def build_html(data: dict[str, Any], title: str) -> str:
    payload = {
        "lastUpdated": data.get("lastUpdated"),
        "games": data.get("games", []),
        "mechanismLabels": MECHANISM_LABELS,
    }
    encoded_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return HTML_TEMPLATE.format(
        title=html_escape(title),
        generated_at=html_escape(generated_at),
        payload=encoded_payload,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="根据 data.json 生成可排序、可拖拽列、可打印的 HTML 表格。")
    parser.add_argument("--data", default="data.json", help="输入 JSON 文件，默认 data.json")
    parser.add_argument("--output", default="index.html", help="输出 HTML 文件，默认 index.html")
    parser.add_argument("--title", default="桌游列表", help="网页标题")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    data = load_data(Path(args.data))
    html = build_html(data, args.title)
    output = Path(args.output)
    output.write_text(html, encoding="utf-8")
    print(f"已生成 {output}，共 {len(data.get('games', []))} 个游戏")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
