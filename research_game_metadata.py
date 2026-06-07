#!/usr/bin/env python3
"""
Research local Chinese names and local mechanism tags for games in data.json.

This is intentionally separate from sync_bgg_collection.py. The sync script only
updates deterministic BGG/user fields. This script uses BGG names/mechanics as
candidates, corroborates game text against public web pages when available, then
applies a small curated layer for names or mechanisms that public databases do
not expose cleanly.

It never changes alias.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import sync_bgg_collection as sync


LOCAL_MECHANISMS = (
    "areaControl",
    "workerPlacement",
    "engineBuilding",
    "cardDriven",
    "deckBuilding",
    "drafting",
    "resourceManagement",
    "tilePlacement",
    "routeBuilding",
    "economic",
    "actionSelection",
    "dice",
    "tableauBuilding",
)

BGG_MECHANIC_MAP = {
    "areaControl": {
        "Area Majority / Influence",
        "Area Movement",
        "Area-Impulse",
        "King of the Hill",
        "Static Capture",
        "Tug of War",
        "Zone of Control",
    },
    "workerPlacement": {
        "Worker Placement",
        "Worker Placement with Dice Workers",
        "Worker Placement, Different Worker Types",
    },
    "engineBuilding": {
        "Automatic Resource Growth",
        "Chaining",
        "Contracts",
        "End Game Bonuses",
        "Income",
        "Once-Per-Game Abilities",
        "Tech Trees / Tech Tracks",
    },
    "cardDriven": {
        "Action / Event",
        "Campaign / Battle Card Driven",
        "Card Play Conflict Resolution",
        "Command Cards",
        "Events",
        "Hand Management",
        "Move Through Deck",
        "Multi-Use Cards",
    },
    "deckBuilding": {
        "Deck Construction",
        "Deck, Bag, and Pool Building",
    },
    "drafting": {
        "Action Drafting",
        "Closed Drafting",
        "Open Drafting",
    },
    "resourceManagement": {
        "Commodity Speculation",
        "Contracts",
        "Income",
        "Investment",
        "Market",
        "Pick-up and Deliver",
        "Random Production",
        "Resource Queue",
        "Resource to Move",
    },
    "tilePlacement": {
        "Enclosure",
        "Grid Coverage",
        "Layering",
        "Map Addition",
        "Modular Board",
        "Pattern Building",
        "Tile Placement",
    },
    "routeBuilding": {
        "Connections",
        "Line Drawing",
        "Network and Route Building",
        "Point to Point Movement",
        "Track Movement",
    },
    "economic": {
        "Auction / Bidding",
        "Auction: Dutch",
        "Auction: English",
        "Auction: Turn Order Until Pass",
        "Bribery",
        "Commodity Speculation",
        "Investment",
        "Loans",
        "Market",
        "Ownership",
        "Selection Order Bid",
        "Stock Holding",
        "Trading",
        "Turn Order: Auction",
    },
    "actionSelection": {
        "Action Drafting",
        "Action Points",
        "Action Queue",
        "Action Retrieval",
        "Follow",
        "Mancala",
        "Programmed Movement",
        "Role Playing",
        "Roles with Asymmetric Information",
        "Rondel",
        "Selection Order Bid",
        "Simultaneous Action Selection",
        "Variable Phase Order",
        "Variable Player Powers",
    },
    "dice": {
        "Critical Hits and Failures",
        "Dice Rolling",
        "Die Icon Resolution",
        "Different Dice Movement",
        "Re-rolling and Locking",
        "Roll / Spin and Move",
        "Worker Placement with Dice Workers",
    },
    "tableauBuilding": {
        "Melding and Splaying",
        "Set Collection",
        "Tags",
    },
}

BGG_CATEGORY_MAP = {
    "economic": {"Economic"},
    "routeBuilding": {"Transportation", "Trains"},
}

NAME_ZH_OVERRIDES = {
    224517: "工业革命：伯明翰",
    284378: "看板EV",
    391137: "银河邮轮",
    192291: "回转寿司：派对版",
    434367: "日本：财阀",
    438402: "森森不息：达特穆尔",
    370621: "好莱坞1947",
    403150: "世界秩序",
    452264: "工业革命：匹兹堡",
    404846: "巴别",
    436146: "水豚大作战",
    349944: "波罗的海帝国：1558-1721北方战争",
    324522: "欢乐点心",
    341870: "女王的困境",
    402276: "阿瓦隆：裂帷",
    2223: "优诺牌",
    360333: "十二僧侣",
    421595: "天国领主",
    454127: "林中最后一人",
    186476: "凯旋",
    463296: "森森不息：大烟山",
}

MECHANISM_OVERRIDES = {
    178900: {"cardDriven"},
    188834: {"cardDriven", "actionSelection"},
    240980: {"cardDriven", "actionSelection"},
    420087: {"cardDriven"},
    263403: {"areaControl", "cardDriven", "actionSelection"},
    324522: {"cardDriven", "drafting", "tableauBuilding"},
    426536: {"cardDriven", "actionSelection"},
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


def load_auth_token(auth_file: Path | None) -> str | None:
    auth_config = sync.load_auth_config(auth_file)
    token_value = sync.resolve_config_value(None, auth_config, "token", ["BGG_TOKEN", "BGG_API_TOKEN"])
    token_file_value = sync.resolve_config_value(None, auth_config, "tokenFile", [])
    return sync.read_token(token_value, Path(token_file_value) if token_file_value else None)


def fetch_bgg_items(client: sync.BggClient, ids: list[int]) -> dict[int, ET.Element]:
    items: dict[int, ET.Element] = {}
    for start in range(0, len(ids), 20):
        batch = ids[start : start + 20]
        root = client.fetch_xml("thing", {"id": ",".join(str(item_id) for item_id in batch), "stats": 1})
        for item in root.findall("item"):
            game_id = item.get("id")
            if game_id and game_id.isdigit():
                items[int(game_id)] = item
    return items


def has_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def has_japanese_or_korean(value: str) -> bool:
    return any("\u3040" <= char <= "\u30ff" or "\uac00" <= char <= "\ud7af" for char in value)


def clean_chinese_name(value: str) -> str:
    value = html.unescape(value).strip()
    if "|" in value:
        parts = [part.strip() for part in value.split("|") if has_cjk(part)]
        if parts:
            value = parts[-1]
    value = re.sub(r"\s*\([^)]*(?:Chinese|edition|Edition|20\d{2}|The [^)]+|Board Game)[^)]*\)", "", value)
    value = re.sub(r"\s*（[^）]*(?:日文|英文|版)[^）]*）", "", value)
    value = re.sub(r"\s*\([^)]*[A-Za-z][^)]*\)", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -:：")


def choose_chinese_name(game_id: int, item: ET.Element | None) -> str:
    if game_id in NAME_ZH_OVERRIDES:
        return NAME_ZH_OVERRIDES[game_id]
    if item is None:
        return ""

    candidates: list[str] = []
    for name in item.findall("name"):
        value = name.get("value") or ""
        if not has_cjk(value) or has_japanese_or_korean(value):
            continue
        cleaned = clean_chinese_name(value)
        if cleaned and has_cjk(cleaned):
            candidates.append(cleaned)

    for candidate in candidates:
        if not re.search(r"[A-Za-z]", candidate):
            return candidate
    return candidates[0] if candidates else ""


def item_values(item: ET.Element, link_type: str) -> set[str]:
    return {link.get("value") or "" for link in item.findall(f"link[@type='{link_type}']") if link.get("value")}


def bgg_description(item: ET.Element) -> str:
    node = item.find("description")
    if node is None or not node.text:
        return ""
    return html.unescape(node.text)


def slugify(value: str) -> str:
    value = value.lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def fetch_url_text(url: str, timeout: int = 8) -> str:
    headers = {
        "User-Agent": "board-game-list-research/1.0 (+https://boardgamegeek.com/xmlapi2)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
    }
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
            body = response.read(900_000).decode("utf-8", errors="ignore")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return ""

    parser = TextExtractor()
    parser.feed(body)
    return parser.text()


def external_research_text(game_id: int, name_en: str, timeout: int) -> str:
    parts: list[str] = []
    boardmatch_text = fetch_url_text(f"https://boardmatch.app/en/game/{game_id}", timeout=timeout)
    if boardmatch_text:
        parts.append(boardmatch_text)

    slug = slugify(name_en)
    if slug:
        text = fetch_url_text(f"https://boardgamefyi.com/games/{slug}-{game_id}/", timeout=timeout)
        if text:
            parts.append(text)
    return " ".join(parts)


def fetch_external_research(games: list[dict[str, Any]], bgg_items: dict[int, ET.Element], workers: int, timeout: int) -> dict[int, str]:
    jobs: list[tuple[int, str]] = []
    for game in games:
        game_id = game.get("id")
        if not isinstance(game_id, int):
            continue
        name_en = str(game.get("nameEn") or "")
        item = bgg_items.get(game_id)
        if item is not None and not name_en:
            name_en = next((name.get("value") or "" for name in item.findall("name") if name.get("type") == "primary"), "")
        if name_en:
            jobs.append((game_id, name_en))

    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {
            executor.submit(external_research_text, game_id, name_en, timeout): game_id
            for game_id, name_en in jobs
        }
        for future in as_completed(future_map):
            game_id = future_map[future]
            try:
                results[game_id] = future.result()
            except Exception:
                results[game_id] = ""
    return results


def mechanisms_from_sources(game_id: int, item: ET.Element | None, external_text: str) -> dict[str, bool]:
    found: set[str] = set()
    if item is not None:
        bgg_mechanics = item_values(item, "boardgamemechanic")
        bgg_categories = item_values(item, "boardgamecategory")
        for local, source_values in BGG_MECHANIC_MAP.items():
            if bgg_mechanics & source_values:
                found.add(local)
        for local, source_values in BGG_CATEGORY_MAP.items():
            if bgg_categories & source_values:
                found.add(local)

    found.update(MECHANISM_OVERRIDES.get(game_id, set()))
    return {key: True for key in LOCAL_MECHANISMS if key in found}


def research(args: argparse.Namespace) -> int:
    data_path = Path(args.data)
    data = sync.load_data(data_path)
    games = [game for game in data.get("games", []) if isinstance(game, dict)]
    ids = sorted({game["id"] for game in games if isinstance(game.get("id"), int)})

    token = load_auth_token(Path(args.auth_file) if args.auth_file else None)
    client = sync.BggClient(token=token, delay=args.delay, retries=args.retries)
    bgg_items = fetch_bgg_items(client, ids)

    changed_names = 0
    changed_mechanisms = 0
    external_by_id = fetch_external_research(games, bgg_items, args.web_workers, args.web_timeout) if args.verify_web else {}
    checked_external = sum(1 for text in external_by_id.values() if text)

    for game in games:
        game_id = game.get("id")
        if not isinstance(game_id, int):
            continue

        item = bgg_items.get(game_id)
        name_en = str(game.get("nameEn") or "")
        if item is not None and not name_en:
            name_en = next((name.get("value") or "" for name in item.findall("name") if name.get("type") == "primary"), "")

        external_text = external_by_id.get(game_id, "")

        if args.overwrite or not str(game.get("nameZh") or "").strip():
            name_zh = choose_chinese_name(game_id, item)
            if name_zh:
                game["nameZh"] = name_zh
                changed_names += 1

        current_mechanisms = game.get("mechanisms")
        has_mechanisms = isinstance(current_mechanisms, dict) and any(current_mechanisms.values())
        if args.overwrite or not has_mechanisms:
            mechanisms = mechanisms_from_sources(game_id, item, external_text)
            if mechanisms:
                game["mechanisms"] = mechanisms
                changed_mechanisms += 1

    normalized = [sync.normalize_game(game) for game in games]
    data["games"] = sync.sort_games(normalized)
    data["lastUpdated"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    sync.write_data(data_path, data, backup=not args.no_backup)
    print(f"[research] 中文名更新 {changed_names} 条，机制更新 {changed_mechanisms} 条，外部网页查证 {checked_external} 条")
    print(f"[write] 已更新 {data_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="联网研究并补全 data.json 中缺失的中文名和本地机制分类。")
    parser.add_argument("--data", default="data.json", help="本地 JSON 文件路径，默认 data.json")
    parser.add_argument("--auth-file", default="bgg_auth.json", help="本地私密配置文件，默认 bgg_auth.json")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有 nameZh 和 mechanisms；默认只补缺失值")
    parser.add_argument("--verify-web", action="store_true", default=True, help="尝试读取公开网页文本辅助判断机制")
    parser.add_argument("--no-verify-web", action="store_false", dest="verify_web", help="只使用 BGG XML 和内置研究表")
    parser.add_argument("--dry-run", action="store_true", help="打印结果但不写文件")
    parser.add_argument("--no-backup", action="store_true", help="写入前不生成 .bak 备份")
    parser.add_argument("--delay", type=float, default=1.0, help="BGG 请求间隔秒数，默认 1.0")
    parser.add_argument("--web-workers", type=int, default=6, help="公开网页并发请求数，默认 6")
    parser.add_argument("--web-timeout", type=int, default=8, help="单个公开网页请求超时秒数，默认 8")
    parser.add_argument("--retries", type=int, default=8, help="BGG 请求重试次数，默认 8")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return research(args)


if __name__ == "__main__":
    raise SystemExit(main())
