"""Deterministically migrate the legacy Markdown authority catalog to YAML."""

from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cn_web_search_mcp.core.knowledge.loader import load_authority_entries  # noqa: E402


BUILTIN_DISCOVERY_SOURCES = (
    ("search-360", "360 搜索", "so.com", "discovery-360", "360"),
    ("search-sogou", "搜狗搜索", "sogou.com", "discovery-sogou", "sogou"),
    ("search-bing-rss", "Bing RSS", "cn.bing.com", "discovery-bing-rss", "bing_rss"),
    ("search-web", "Web Search", "duckduckgo.com", "discovery-web-search", "web_search"),
)


def _clean_category(value: str) -> str:
    return re.sub(r"^[^\w\u4e00-\u9fff]+", "", value).strip()


def _base_id(url: str) -> str:
    host = (urlsplit(url).hostname or "source").casefold().removeprefix("www.")
    parts = [part for part in host.split(".") if part]
    candidates = [part for part in parts if part not in {"com", "org", "net", "gov", "edu", "cn", "io", "co"}]
    value = candidates[-1] if candidates else parts[0] if parts else "source"
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-") or "source"
    return value


def build_catalog(markdown_path: Path) -> dict:
    entries = load_authority_entries(markdown_path)
    counts: Counter[str] = Counter()
    sources = [
        {
            "id": source_id,
            "name": name,
            "legacy_entity": name,
            "legacy_category": "系统内置搜索渠道",
            "categories": ["开放网页搜索"],
            "keywords": [],
            "domains": [domain],
            "source_role": "search_channel",
            "authority": 1,
            "reliability": "unknown",
            "languages": ["zh-CN"],
            "capabilities": ["web_search"],
            "enabled": True,
            "fallback_source_ids": [],
            "rate_policy": {
                "serial_only": False,
                "minimum_interval_seconds": 0,
                "max_concurrency": 1,
                "timeout_seconds": 10,
            },
            "endpoints": [
                {
                    "id": endpoint_id,
                    "method": "web_search",
                    "query_template": "{query}",
                    "discovery_only": True,
                    "evidence_eligible": False,
                    "adapter": adapter,
                }
            ],
            "provenance": "built-in mandatory discovery channel",
        }
        for source_id, name, domain, endpoint_id, adapter in BUILTIN_DISCOVERY_SOURCES
    ]
    for index, entry in enumerate(entries, 1):
        base = _base_id(entry.urls[0]) if entry.urls else f"source-{index:03d}"
        counts[base] += 1
        source_id = base if counts[base] == 1 else f"{base}-{counts[base]}"
        domains = list(
            dict.fromkeys(
                (urlsplit(url).hostname or "").casefold().removeprefix("www.")
                for url in entry.urls
                if urlsplit(url).hostname
            )
        )
        endpoints = [
            {
                "id": f"{source_id}-entry-{url_index}",
                "method": "homepage",
                "url": url,
                "discovery_only": True,
                "evidence_eligible": False,
            }
            for url_index, url in enumerate(entry.urls, 1)
        ]
        sources.append(
            {
                "id": source_id,
                "name": entry.entity,
                "legacy_entity": entry.entity,
                "legacy_category": entry.category,
                "categories": [_clean_category(entry.category)],
                "keywords": entry.keywords,
                "domains": domains,
                "source_role": "curated_reference",
                "authority": 3,
                "reliability": "unknown",
                "languages": ["zh-CN"],
                "capabilities": ["authority_discovery"],
                "enabled": True,
                "fallback_source_ids": [],
                "rate_policy": {
                    "serial_only": False,
                    "minimum_interval_seconds": 0,
                    "max_concurrency": 1,
                    "timeout_seconds": 15,
                },
                "endpoints": endpoints,
                "provenance": "migrated from authoritative-sites.md",
            }
        )
    raw = markdown_path.read_bytes()
    return {
        "version": 2,
        "declared_sources": len(sources),
        "provenance": {
            "source_file": "authoritative-sites.md",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "migration": "scripts/migrate_authorities_to_yaml.py",
        },
        "sources": sources,
    }


def main() -> None:
    markdown_path = SRC / "cn_web_search_mcp" / "data" / "authoritative-sites.md"
    output_path = SRC / "cn_web_search_mcp" / "data" / "sources.yaml"
    payload = build_catalog(markdown_path)
    output_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"wrote {payload['declared_sources']} sources to {output_path}")


if __name__ == "__main__":
    main()
