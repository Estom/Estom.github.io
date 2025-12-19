#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


def _is_markdown(path: Path) -> bool:
	return path.suffix.lower() in {'.md', '.markdown'}


def _read_text_best_effort(path: Path) -> str:
	# Most notes are UTF-8; accept BOM; fall back to replacement to avoid crashing.
	try:
		return path.read_text(encoding='utf-8-sig')
	except UnicodeDecodeError:
		return path.read_text(encoding='utf-8', errors='replace')


def _has_front_matter_prefix(content: str) -> bool:
	# Old style: starts with ---/;;; front-matter block.
	return content.startswith('---\n') or content.startswith(';;;\n') or content.startswith('---\r\n') or content.startswith(';;;\r\n')


def _split_old_style_front_matter(content: str) -> Tuple[str, str]:
	"""Split old-style front-matter (`---` / `;;;`) from body.

	Returns (front_matter_block_or_empty, body).
	"""
	if not _has_front_matter_prefix(content):
		return '', content
	lines = content.splitlines(keepends=True)
	if not lines:
		return '', content
	first = lines[0].strip()
	if first not in {'---', ';;;'}:
		return '', content
	sep = first
	for i in range(1, len(lines)):
		if lines[i].strip() == sep:
			fm = ''.join(lines[:i + 1])
			body = ''.join(lines[i + 1:])
			return fm, body
	return '', content


def _strip_front_matter_if_any(content: str) -> str:
	fm, body = _split_old_style_front_matter(content)
	return body if fm else content


def _should_raw_wrap(body: str, mode: str) -> bool:
	m = (mode or 'auto').lower()
	if m == 'never':
		return False
	if m == 'always':
		return True
	# auto: wrap only when template-like markers exist
	return ('{%' in body) or ('{{' in body) or ('{#' in body)


def _wrap_body_raw(body: str) -> str:
	# Avoid double wrapping if already present.
	if '{% raw %}' in body and '{% endraw %}' in body:
		return body
	return '{% raw %}\n' + body + ('\n' if not body.endswith('\n') else '') + '{% endraw %}\n'


def _escape_nunjucks_curly(content: str) -> str:
	# Escape plain {{ }} to avoid Nunjucks parsing errors.
	return content.replace('{{', '&#123;&#123;').replace('}}', '&#125;&#125;')


def _yaml_list_inline_or_block(values) -> str:
	if not values:
		return '[]'
	lines = ['']
	for v in values:
		lines.append(f"  - {json.dumps(v, ensure_ascii=False)}")
	return '\n'.join(lines)


def _build_front_matter(title: str, epoch_seconds: int, categories) -> str:
	title_json = json.dumps(title, ensure_ascii=False)
	cats = _yaml_list_inline_or_block(categories)
	return (
		"---\n"
		f"title: {title_json}\n"
		f"date: {epoch_seconds}\n"
		f"updated: {epoch_seconds}\n"
		"tags: []\n"
		+ (f"categories: {cats}\n" if cats == '[]' else f"categories:{cats}\n")
		+ "---\n\n"
	)


def _top_level_category(target_root: Path, file_path: Path) -> Optional[str]:
	rel = file_path.relative_to(target_root)
	parts = rel.parts
	if len(parts) >= 2:
		return parts[0]
	return None


@dataclass(frozen=True)
class ProcessConfig:
	target_dir: Path
	raw_wrap: str
	escape_curly: bool
	verbose: bool
	timestamp: Optional[int]


def process_file(cfg: ProcessConfig, path: Path) -> bool:
	if not path.is_file() or not _is_markdown(path):
		return False

	raw = _read_text_best_effort(path)
	body = _strip_front_matter_if_any(raw)

	title = path.stem
	epoch = int(cfg.timestamp if cfg.timestamp is not None else int(time.time()))
	cat = _top_level_category(cfg.target_dir, path)
	categories = [cat] if cat else []

	front_matter = _build_front_matter(title=title, epoch_seconds=epoch, categories=categories)
	if _should_raw_wrap(body, cfg.raw_wrap):
		body = _wrap_body_raw(body)

	content = front_matter + body.lstrip('\ufeff')
	if cfg.escape_curly:
		content = _escape_nunjucks_curly(content)

	path.write_text(content, encoding='utf-8')
	return True


def process_directory(cfg: ProcessConfig) -> int:
	if not cfg.target_dir.exists():
		if cfg.verbose:
			print(f"[skip] target not found: {cfg.target_dir}")
		return 0

	count = 0
	for p in sorted(cfg.target_dir.rglob('*')):
		if p.is_file() and _is_markdown(p):
			if process_file(cfg, p):
				count += 1
				if cfg.verbose:
					print(f"[ok] {p.relative_to(cfg.target_dir).as_posix()}")

	print(f"processed: {count} files, target={cfg.target_dir}")
	return 0


def main(argv=None) -> int:
	parser = argparse.ArgumentParser(
		description="统一处理 Hexo source/_posts 下的 Markdown：生成最小 front-matter，并可选 raw-wrap/花括号转义"
	)
	parser.add_argument('--target', default='source/_posts', help='目标目录（默认：source/_posts）')
	parser.add_argument('--raw-wrap', choices=['auto', 'always', 'never'], default='auto', help='遇到模板语法时用 Nunjucks raw 包裹正文（默认：auto）')
	parser.add_argument('--escape-curly', choices=['true', 'false'], default='true', help='是否转义 {{ }} 以避免 Nunjucks 解析（默认：true）')
	parser.add_argument('--timestamp', type=int, default=None, help='指定 date/updated 的时间戳（秒）。默认使用当前时间')
	parser.add_argument('-v', '--verbose', action='store_true', help='输出更多日志')
	args = parser.parse_args(argv)

	target_dir = Path(args.target).resolve()
	cfg = ProcessConfig(
		target_dir=target_dir,
		raw_wrap=str(args.raw_wrap),
		escape_curly=str(args.escape_curly).lower() == 'true',
		verbose=bool(args.verbose),
		timestamp=args.timestamp,
	)
	return process_directory(cfg)


if __name__ == '__main__':
	raise SystemExit(main())
