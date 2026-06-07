#!/usr/bin/env python3
"""
Sync data.json with BoardGameGeek.

This script has two jobs:

1. Read a user's BGG collection and add/update fields available directly from
   collection entries: id, nameEn, year, userRating, status.
2. For every local game with a non-null id, fetch BGG thing details and update
   weight, players, age, playingTime, bggRank, and bggRating.

Chinese names, aliases, and local mechanism classification are intentionally
left untouched. Games with id=null are never looked up on BGG and always get
collection=false and bgg=false.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BGG_BASE_URL = "https://boardgamegeek.com/xmlapi2"

STATUS_FIELDS = {
    "own": "owned",
    "prevowned": "previouslyOwned",
    "fortrade": "forTrade",
    "want": "want",
    "wanttoplay": "wantToPlay",
    "wanttobuy": "wantToBuy",
    "wishlist": "wishlist",
    "preordered": "preordered",
}

COLLECTION_STATUS_ARGS = {
    "owned": "own",
    "previously-owned": "prevowned",
    "for-trade": "fortrade",
    "want": "want",
    "want-to-play": "wanttoplay",
    "want-to-buy": "wanttobuy",
    "wishlist": "wishlist",
    "preordered": "preordered",
}

GAME_FIELD_DEFAULTS = {
    "id": None,
    "alias": "",
    "nameEn": "",
    "nameZh": "",
    "year": None,
    "weight": None,
    "players": {"min": None, "max": None, "best": [], "recommended": []},
    "age": {"min": None, "recommended": None},
    "playingTime": {"min": None, "max": None},
    "bggRank": None,
    "bggRating": None,
    "userRating": None,
    "collection": False,
    "bgg": False,
    "mechanisms": {},
    "status": {target: False for target in STATUS_FIELDS.values()},
}

GAME_FIELD_ORDER = tuple(GAME_FIELD_DEFAULTS.keys())


@dataclass
class BggClient:
    cookie: str | None = None
    token: str | None = None
    delay: float = 1.0
    retries: int = 8

    def fetch_xml(self, endpoint: str, params: dict[str, Any]) -> ET.Element:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{BGG_BASE_URL}/{endpoint}?{query}"

        headers = {
            "User-Agent": "board-game-list-sync/1.0 (+https://boardgamegeek.com/xmlapi2)",
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.cookie:
            headers["Cookie"] = self.cookie

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    body = response.read()
                    time.sleep(self.delay)
                    return ET.fromstring(body)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 401:
                    raise RuntimeError(
                        "BGG XML API 返回 401。请提供 --token / BGG_TOKEN；"
                        "如果要读取登录后的私人 Collection，也同时提供 --cookie 或 --cookie-file。"
                    ) from exc
                if exc.code in {202, 429, 500, 502, 503, 504}:
                    time.sleep(min(30, self.delay * attempt * 2))
                    continue
                raise RuntimeError(f"BGG request failed with HTTP {exc.code}: {url}") from exc
            except (urllib.error.URLError, ET.ParseError) as exc:
                last_error = exc
                time.sleep(min(30, self.delay * attempt * 2))

        raise RuntimeError(f"BGG request did not complete after {self.retries} attempts: {url}") from last_error


def int_attr(element: ET.Element | None, attr: str = "value") -> int | None:
    if element is None:
        return None
    value = element.get(attr)
    if value in {None, "", "N/A"}:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def float_attr(element: ET.Element | None, attr: str = "value") -> float | None:
    if element is None:
        return None
    value = element.get(attr)
    if value in {None, "", "N/A"}:
        return None
    try:
        return round(float(value), 4)
    except ValueError:
        return None


def load_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"lastUpdated": None, "games": []}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or not isinstance(data.get("games"), list):
        raise ValueError("data.json must be an object with a top-level games array")
    return data


def write_data(path: Path, data: dict[str, Any], backup: bool) -> None:
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        backup_path.write_bytes(path.read_bytes())

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_auth_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("auth config must be a JSON object")
    return data


def resolve_config_value(args_value: str | None, config: dict[str, Any], key: str, env_names: list[str]) -> str | None:
    if args_value:
        return args_value
    for env_name in env_names:
        env_value = os.environ.get(env_name)
        if env_value:
            return env_value
    config_value = config.get(key)
    if isinstance(config_value, str) and config_value.strip():
        return config_value.strip()
    return None


def read_cookie(cookie_arg: str | None, cookie_file: Path | None) -> str | None:
    if cookie_arg:
        return cookie_arg
    if not cookie_file:
        return None

    lines = cookie_file.read_text(encoding="utf-8").splitlines()
    pairs: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#HttpOnly_"):
            line = line.removeprefix("#HttpOnly_")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7 and "boardgamegeek.com" in parts[0]:
            pairs.append(f"{parts[5]}={parts[6]}")
    if pairs:
        return "; ".join(pairs)

    raw = cookie_file.read_text(encoding="utf-8").strip()
    return raw or None


def read_token(token_arg: str | None, token_file: Path | None) -> str | None:
    if token_arg:
        return token_arg.strip()
    if token_file:
        return token_file.read_text(encoding="utf-8").strip()
    return None


def parse_collection_status(item: ET.Element) -> dict[str, bool]:
    status = item.find("status")
    result = {target: False for target in STATUS_FIELDS.values()}
    if status is None:
        return result
    for source, target in STATUS_FIELDS.items():
        result[target] = status.get(source) == "1"
    return result


def parse_user_rating(item: ET.Element) -> float | None:
    rating = item.find("./stats/rating")
    if rating is None:
        return None
    value = rating.get("value")
    if value in {None, "", "N/A"}:
        return None
    try:
        return round(float(value), 2)
    except ValueError:
        return None


def parse_collection_item(item: ET.Element) -> dict[str, Any]:
    object_id = item.get("objectid")
    name_node = item.find("name")
    year_node = item.find("yearpublished")
    return {
        "id": int(object_id) if object_id else None,
        "nameEn": name_node.text.strip() if name_node is not None and name_node.text else None,
        "year": int(year_node.text) if year_node is not None and year_node.text and year_node.text.isdigit() else None,
        "userRating": parse_user_rating(item),
        "status": parse_collection_status(item),
    }


def parse_rank(stats: ET.Element | None) -> tuple[int | None, float | None]:
    if stats is None:
        return None, None
    for rank in stats.findall("./ratings/ranks/rank"):
        if rank.get("name") == "boardgame":
            rank_value = rank.get("value")
            bayes = rank.get("bayesaverage")
            parsed_rank = int(rank_value) if rank_value and rank_value.isdigit() else None
            parsed_bayes = None
            if bayes and bayes not in {"Not Ranked", "N/A"}:
                try:
                    parsed_bayes = round(float(bayes), 4)
                except ValueError:
                    parsed_bayes = None
            return parsed_rank, parsed_bayes
    return None, None


def parse_suggested_players(item: ET.Element) -> dict[str, list[int]]:
    result = {"best": [], "recommended": []}
    poll = item.find("./poll[@name='suggested_numplayers']")
    if poll is None:
        return result

    for results in poll.findall("results"):
        numplayers = results.get("numplayers")
        if not numplayers or not numplayers.isdigit():
            continue
        votes: dict[str, int] = {}
        for vote in results.findall("result"):
            try:
                votes[vote.get("value") or ""] = int(vote.get("numvotes") or 0)
            except ValueError:
                votes[vote.get("value") or ""] = 0
        if not votes:
            continue
        winning_label = max(votes, key=votes.get)
        player_count = int(numplayers)
        if winning_label == "Best":
            result["best"].append(player_count)
            result["recommended"].append(player_count)
        elif winning_label == "Recommended":
            result["recommended"].append(player_count)

    return result


def parse_suggested_age(item: ET.Element) -> int | None:
    poll = item.find("./poll[@name='suggested_playerage']")
    if poll is None:
        return None
    votes: dict[int, int] = {}
    for result in poll.findall("./results/result"):
        value = result.get("value")
        if not value or not value.endswith("+"):
            continue
        try:
            age = int(value[:-1])
            count = int(result.get("numvotes") or 0)
        except ValueError:
            continue
        votes[age] = count
    if not votes:
        return None
    return max(votes, key=votes.get)


def parse_thing_item(item: ET.Element) -> dict[str, Any]:
    stats = item.find("statistics")
    bgg_rank, bgg_rating = parse_rank(stats)
    suggested_players = parse_suggested_players(item)

    return {
        "id": int(item.get("id")) if item.get("id") else None,
        "weight": float_attr(stats.find("./ratings/averageweight") if stats is not None else None),
        "players": {
            "min": int_attr(item.find("minplayers")),
            "max": int_attr(item.find("maxplayers")),
            "best": suggested_players["best"],
            "recommended": suggested_players["recommended"],
        },
        "playingTime": {
            "min": int_attr(item.find("minplaytime")),
            "max": int_attr(item.find("maxplaytime")),
        },
        "age": {
            "min": int_attr(item.find("minage")),
            "recommended": parse_suggested_age(item),
        },
        "bggRank": bgg_rank,
        "bggRating": bgg_rating,
    }


def fetch_collection(client: BggClient, username: str, status_filters: list[str], include_expansions: bool) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "username": username,
        "stats": 1,
        "subtype": "boardgame",
    }
    if not include_expansions:
        params["excludesubtype"] = "boardgameexpansion"
    for status_filter in status_filters:
        params[COLLECTION_STATUS_ARGS[status_filter]] = 1

    root = client.fetch_xml("collection", params)
    return [parse_collection_item(item) for item in root.findall("item")]


def fetch_things(client: BggClient, ids: list[int], batch_size: int = 20) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for start in range(0, len(ids), batch_size):
        batch = ids[start : start + batch_size]
        root = client.fetch_xml("thing", {"id": ",".join(str(item_id) for item_id in batch), "stats": 1})
        for item in root.findall("item"):
            parsed = parse_thing_item(item)
            if parsed["id"] is not None:
                result[parsed["id"]] = parsed
    return result


def update_from_collection(
    games: list[dict[str, Any]], collection_items: list[dict[str, Any]]
) -> tuple[int, int, list[dict[str, Any]]]:
    by_id = {game.get("id"): game for game in games if isinstance(game.get("id"), int)}
    collection_ids = {item["id"] for item in collection_items if isinstance(item.get("id"), int)}
    added = 0
    updated = 0
    added_items: list[dict[str, Any]] = []

    for game in games:
        if isinstance(game.get("id"), int):
            game["collection"] = game["id"] in collection_ids
        else:
            game["collection"] = False
            game["bgg"] = False

    for item in collection_items:
        game_id = item.get("id")
        if not isinstance(game_id, int):
            continue
        game = by_id.get(game_id)
        if game is None:
            game = {"id": game_id, "alias": "", "nameZh": "", "mechanisms": {}}
            games.append(game)
            by_id[game_id] = game
            added += 1
            added_items.append({"id": game_id, "nameEn": item.get("nameEn")})
        else:
            updated += 1

        for field in ("id", "nameEn", "year", "userRating", "status"):
            game[field] = copy.deepcopy(item.get(field))
        game["collection"] = True

    return added, updated, added_items


def update_from_things(games: list[dict[str, Any]], things: dict[int, dict[str, Any]]) -> tuple[int, int]:
    found = 0
    missing = 0
    for game in games:
        game_id = game.get("id")
        if not isinstance(game_id, int):
            game["collection"] = False
            game["bgg"] = False
            continue

        thing = things.get(game_id)
        if thing is None:
            game["bgg"] = False
            missing += 1
            continue

        for field in ("weight", "players", "age", "playingTime", "bggRank", "bggRating"):
            game[field] = copy.deepcopy(thing.get(field))
        game["bgg"] = True
        found += 1

    return found, missing


def sort_games(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(game: dict[str, Any]) -> tuple[int, int, str]:
        rank = game.get("bggRank")
        name = str(game.get("nameEn") or game.get("nameZh") or "")
        return (
            0 if isinstance(rank, int) else 1,
            rank if isinstance(rank, int) else 10_000_000,
            name.casefold(),
        )

    return sorted(games, key=key)


def normalize_game(game: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: copy.deepcopy(GAME_FIELD_DEFAULTS[field]) for field in GAME_FIELD_ORDER}
    for field in GAME_FIELD_ORDER:
        if field in game:
            normalized[field] = copy.deepcopy(game[field])

    if not isinstance(normalized["id"], int):
        normalized["id"] = None
        normalized["collection"] = False
        normalized["bgg"] = False

    return normalized


def sync(args: argparse.Namespace) -> int:
    data_path = Path(args.data)
    auth_config = load_auth_config(Path(args.auth_file) if args.auth_file else None)
    data = load_data(data_path)
    games = data.get("games", [])

    username = resolve_config_value(args.username, auth_config, "username", ["BGG_USERNAME"])
    token_value = resolve_config_value(args.token, auth_config, "token", ["BGG_TOKEN", "BGG_API_TOKEN"])
    cookie_value = resolve_config_value(args.cookie, auth_config, "cookie", ["BGG_COOKIE"])
    token_file_value = resolve_config_value(args.token_file, auth_config, "tokenFile", [])
    cookie_file_value = resolve_config_value(args.cookie_file, auth_config, "cookieFile", [])

    cookie = read_cookie(cookie_value, Path(cookie_file_value) if cookie_file_value else None)
    token = read_token(token_value, Path(token_file_value) if token_file_value else None)
    if not (token or cookie):
        raise RuntimeError("请提供 --token / BGG_TOKEN，或通过 --cookie / BGG_COOKIE 使用已登录 Cookie。")

    client = BggClient(cookie=cookie, token=token, delay=args.delay, retries=args.retries)

    collection_items: list[dict[str, Any]] = []
    if not args.skip_collection:
        if not username:
            raise RuntimeError("同步 Collection 需要 BGG username。请写入 bgg_auth.json 或传 --username。")
        collection_items = fetch_collection(client, username, args.collection_status, args.include_expansions)
        if args.limit:
            collection_items = collection_items[: args.limit]
        if not collection_items and not args.allow_empty_collection:
            known_collection_count = sum(game.get("collection") is True for game in games)
            if known_collection_count:
                raise RuntimeError(
                    "BGG Collection 返回 0 条，但本地已有 "
                    f"{known_collection_count} 条 collection=true。"
                    "这通常是 BGG 还在生成 Collection 缓存。为避免误写，已中止；"
                    "稍后重试，或确认需要清空时使用 --allow-empty-collection。"
                )
        added, updated, added_items = update_from_collection(games, collection_items)
        print(f"[collection] 读取 {len(collection_items)} 条，新增 {added} 条，更新 {updated} 条")
        if added_items:
            print("[collection] 新增条目：")
            for item in added_items:
                print(f"  - {item.get('nameEn') or '(无英文名)'} (id: {item['id']})")
    else:
        for game in games:
            if not isinstance(game.get("id"), int):
                game["collection"] = False
                game["bgg"] = False

    if not args.skip_details:
        ids_to_refresh = sorted({game["id"] for game in games if isinstance(game.get("id"), int)})
        if args.limit:
            ids_to_refresh = ids_to_refresh[: args.limit]
        things = fetch_things(client, ids_to_refresh) if ids_to_refresh else {}
        found, missing = update_from_things(games, things)
        print(f"[details] 找到 {found} 条，未找到 {missing} 条")

    data["lastUpdated"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data["games"] = sort_games([normalize_game(game) for game in games])

    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    write_data(data_path, data, backup=not args.no_backup)
    print(f"[write] 已更新 {data_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从 BGG Collection 和 BGG thing 详情同步本地桌游数据。",
    )
    parser.add_argument("--data", default="data.json", help="本地 JSON 文件路径，默认 data.json")
    parser.add_argument("--auth-file", default="bgg_auth.json", help="本地私密配置文件，默认 bgg_auth.json")
    parser.add_argument("--username", help="BGG 用户名；也可写入 auth file 或用 BGG_USERNAME 环境变量")
    parser.add_argument("--token", help="BGG Application Token；也可用 BGG_TOKEN 或 BGG_API_TOKEN 环境变量")
    parser.add_argument("--token-file", help="只包含 BGG Application Token 的文本文件路径")
    parser.add_argument("--cookie", help="BGG 登录后的 Cookie 字符串；也可用 BGG_COOKIE 环境变量")
    parser.add_argument("--cookie-file", help="Cookie 文件路径，支持 Netscape cookie export 或原始 Cookie 字符串")
    parser.add_argument(
        "--collection-status",
        action="append",
        choices=sorted(COLLECTION_STATUS_ARGS),
        default=[],
        help="只同步某类 Collection 状态；可重复。不填则读取整个 Collection。",
    )
    parser.add_argument("--include-expansions", action="store_true", help="包含 boardgame expansion")
    parser.add_argument("--skip-collection", action="store_true", help="跳过 Collection 同步，只按本地 id 更新 BGG 详情")
    parser.add_argument("--skip-details", action="store_true", help="跳过 BGG thing 详情同步，只更新 Collection 字段")
    parser.add_argument("--allow-empty-collection", action="store_true", help="允许 Collection 返回 0 条时仍然写入")
    parser.add_argument("--dry-run", action="store_true", help="打印结果但不写文件")
    parser.add_argument("--no-backup", action="store_true", help="写入前不生成 .bak 备份")
    parser.add_argument("--delay", type=float, default=1.0, help="BGG 请求间隔秒数，默认 1.0")
    parser.add_argument("--retries", type=int, default=8, help="BGG 请求重试次数，默认 8")
    parser.add_argument("--limit", type=int, help="调试用：限制处理条目数量")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return sync(args)
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
