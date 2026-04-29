from __future__ import annotations

import argparse
import html
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


BASE_URL = "https://everydaysexism.com/country/dk"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "Data" / "everydaysexism_dk.sql"
USER_AGENT = "Mozilla/5.0 (compatible; EDSPDKScraper/1.0; +https://everydaysexism.com/)"
REQUEST_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 3


@dataclass
class PostRecord:
	title: str
	month: str
	year: int
	text: str


def clean_text(value: str) -> str:
	value = html.unescape(value)
	value = value.replace("\xa0", " ")
	value = re.sub(r"\s+", " ", value)
	return value.strip()


def sql_quote(value: str) -> str:
	return "'" + value.replace("'", "''") + "'"


def parse_month_year(raw_date: str) -> tuple[str, int]:
	cleaned = clean_text(raw_date)
	match = re.search(r"([A-Za-zÀ-ÿ]+)\s+(\d{4})$", cleaned)
	if not match:
		raise ValueError(f"Could not parse month/year from date: {raw_date!r}")
	month = match.group(1)
	year = int(match.group(2))
	return month, year


def fetch_html(url: str, timeout_seconds: int = REQUEST_TIMEOUT_SECONDS) -> str:
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
	last_error: Exception | None = None

	for attempt in range(1, MAX_RETRIES + 1):
		try:
			with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
				charset = response.headers.get_content_charset() or "utf-8"
				return response.read().decode(charset, errors="replace")
		except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
			last_error = exc
			if attempt == MAX_RETRIES:
				break
			backoff_seconds = attempt
			print(
				f"Request failed for {url} ({exc}). Retrying in {backoff_seconds}s...",
				file=sys.stderr,
			)
			time.sleep(backoff_seconds)

	assert last_error is not None
	raise last_error


class EDSPCountryParser(HTMLParser):
	def __init__(self) -> None:
		super().__init__(convert_charrefs=True)
		self.posts: list[PostRecord] = []
		self.next_page_url: str | None = None

		self._article_depth = 0
		self._in_target_article = False
		self._current_title: list[str] = []
		self._current_date: list[str] = []
		self._current_text: list[str] = []

		self._capture_title = False
		self._capture_date = False
		self._capture_text = False
		self._summary_depth = 0

		self._capture_older_link_text = False
		self._pending_link_href: str | None = None
		self._pending_link_rel: set[str] = set()
		self._pending_link_text: list[str] = []

	@staticmethod
	def _attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
		return {key: (value or "") for key, value in attrs}

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		attr_map = self._attrs_to_dict(attrs)
		classes = set(attr_map.get("class", "").split())

		if tag == "article":
			self._article_depth += 1
			if "hentry" in classes:
				self._in_target_article = True
				self._current_title = []
				self._current_date = []
				self._current_text = []
				self._capture_title = False
				self._capture_date = False
				self._capture_text = False
				self._summary_depth = 0

		if self._in_target_article:
			if tag == "h2" and "entry-title" in classes:
				self._capture_title = True
			elif tag == "time" and "entry-date" in classes:
				self._capture_date = True
			elif tag == "div" and "entry-summary" in classes:
				self._capture_text = True
				self._summary_depth = 1
			elif self._capture_text and tag == "div":
				self._summary_depth += 1

			if self._capture_text and tag in {"p", "br", "li"}:
				self._current_text.append("\n")

		if tag == "a":
			self._pending_link_href = attr_map.get("href") or None
			self._pending_link_rel = set(attr_map.get("rel", "").split())
			self._pending_link_text = []
			self._capture_older_link_text = True

	def handle_endtag(self, tag: str) -> None:
		if self._in_target_article:
			if tag == "h2" and self._capture_title:
				self._capture_title = False
			elif tag == "time" and self._capture_date:
				self._capture_date = False
			elif tag == "div" and self._capture_text:
				self._summary_depth -= 1
				if self._summary_depth <= 0:
					self._capture_text = False
					self._summary_depth = 0

			if tag == "article":
				title = clean_text("".join(self._current_title))
				raw_date = clean_text("".join(self._current_date))
				text = clean_text(" ".join(self._current_text))
				if title and raw_date and text:
					month, year = parse_month_year(raw_date)
					self.posts.append(PostRecord(title=title, month=month, year=year, text=text))

				self._article_depth -= 1
				if self._article_depth <= 0:
					self._article_depth = 0
					self._in_target_article = False
					self._capture_title = False
					self._capture_date = False
					self._capture_text = False
					self._summary_depth = 0

		if tag == "a" and self._capture_older_link_text:
			link_text = clean_text("".join(self._pending_link_text)).lower()
			href = self._pending_link_href
			if href and (link_text.startswith("← older") or link_text == "older" or "prev" in self._pending_link_rel):
				self.next_page_url = href
			self._capture_older_link_text = False
			self._pending_link_href = None
			self._pending_link_rel = set()
			self._pending_link_text = []

	def handle_data(self, data: str) -> None:
		if self._capture_title:
			self._current_title.append(data)
		if self._capture_date:
			self._current_date.append(data)
		if self._capture_text:
			self._current_text.append(data)
		if self._capture_older_link_text:
			self._pending_link_text.append(data)


def collect_posts(start_url: str, limit: int | None = None) -> list[PostRecord]:
	all_posts: list[PostRecord] = []
	visited_urls: set[str] = set()
	next_url: str | None = start_url

	while next_url:
		if next_url in visited_urls:
			raise RuntimeError(f"Pagination loop detected at {next_url}")

		print(f"Fetching {next_url}", file=sys.stderr)
		visited_urls.add(next_url)
		parser = EDSPCountryParser()
		parser.feed(fetch_html(next_url))
		all_posts.extend(parser.posts)

		if limit is not None and len(all_posts) >= limit:
			return all_posts[:limit]

		if parser.next_page_url:
			next_url = urllib.parse.urljoin(next_url, parser.next_page_url)
			time.sleep(REQUEST_DELAY_SECONDS)
		else:
			next_url = None

	return all_posts


def post_to_dict(record: PostRecord) -> dict[str, str | int]:
	return {
		"title": record.title,
		"month": record.month,
		"year": record.year,
		"text": record.text,
	}


def render_sql(records: list[PostRecord], table_name: str) -> str:
	lines = [
		"BEGIN TRANSACTION;",
		f"DROP TABLE IF EXISTS {table_name};",
		f"CREATE TABLE {table_name} (",
		"    id INTEGER PRIMARY KEY AUTOINCREMENT,",
		"    title TEXT NOT NULL,",
		"    post_month TEXT NOT NULL,",
		"    post_year INTEGER NOT NULL,",
		"    post_text TEXT NOT NULL",
		");",
		"",
	]

	for record in records:
		lines.append(
			f"INSERT INTO {table_name} (title, post_month, post_year, post_text) VALUES ("
			f"{sql_quote(record.title)}, {sql_quote(record.month)}, {record.year}, {sql_quote(record.text)}"
			");"
		)

	lines.extend(["", "COMMIT;"])
	return "\n".join(lines)


def write_output(records: list[PostRecord], output_path: Path, table_name: str) -> None:
	output_path.parent.mkdir(parents=True, exist_ok=True)
	output_path.write_text(render_sql(records, table_name), encoding="utf-8")


def write_json_output(records: list[PostRecord], output_path: Path) -> None:
	output_path.parent.mkdir(parents=True, exist_ok=True)
	payload = [post_to_dict(record) for record in records]
	output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_argument_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Scrape all Everyday Sexism Denmark country pages into a SQL file."
	)
	parser.add_argument("--url", default=BASE_URL, help="Starting country page URL.")
	parser.add_argument(
		"--output",
		type=Path,
		default=DEFAULT_OUTPUT,
		help=f"Output SQL file path (default: {DEFAULT_OUTPUT}).",
	)
	parser.add_argument(
		"--table-name",
		default="everydaysexism_dk_posts",
		help="SQL table name to create and populate.",
	)
	parser.add_argument(
		"--format",
		choices=("sql", "json"),
		default="sql",
		help="Output format.",
	)
	parser.add_argument(
		"--limit",
		type=int,
		default=None,
		help="Maximum number of scraped posts to keep.",
	)
	return parser


def main() -> int:
	parser = build_argument_parser()
	args = parser.parse_args()

	try:
		if args.limit is not None and args.limit < 1:
			raise ValueError("--limit must be greater than 0.")
		records = collect_posts(args.url, limit=args.limit)
		if not records:
			raise RuntimeError("No posts were scraped from the provided URL.")
		if args.format == "json":
			write_json_output(records, args.output)
		else:
			write_output(records, args.output, args.table_name)
	except (urllib.error.URLError, ValueError, RuntimeError) as exc:
		print(f"Error: {exc}", file=sys.stderr)
		return 1

	print(f"Saved {len(records)} posts to {args.output}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
