#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from typing import Dict, Optional, Set, Tuple


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


_MD_IMAGE_RE = re.compile(
	r"!\[[^\]]*\]\(\s*<?([^\s)>]+)>?(?:\s+['\"]?[^'\"]*['\"]?)?\s*\)",
	flags=re.IGNORECASE,
)
_HTML_IMG_RE = re.compile(r"<img\b[^>]*?\bsrc=['\"]([^'\"]+)['\"][^>]*>", flags=re.IGNORECASE)


_MD_IMAGE_SUB_RE = re.compile(
	r"(!\[[^\]]*\]\(\s*<?)([^\s)>]+)(>?)(\s*(?:['\"][^'\"]*['\"])?\s*\))",
	flags=re.IGNORECASE,
)


def _is_site_absolute(url: str) -> bool:
	u = (url or '').strip()
	return u.startswith('/')


def _rewrite_relative_image_url_for_md(cfg: 'ProcessConfig', md_file: Path, url: str) -> str:
	"""Rewrite a relative image URL to /note_image/<resolved> based on md_file path.

	Example:
	- md_file: <target>/Java/a.md
	- url: ./image/test.jpg
	=> /note_image/Java/image/test.jpg
	"""
	if not url:
		return url
	if _is_remote_or_data_url(url) or _is_site_absolute(url):
		return url

	parts = urlsplit(url)
	path_part = (parts.path or '').strip()
	if not path_part:
		return url

	# Already rewritten or already rooted at note_image.
	if path_part.startswith('note_image/') or path_part.startswith('/note_image/'):
		return url

	# Normalize Windows separators if present.
	path_part = path_part.replace('\\', '/')

	try:
		rel_md = md_file.relative_to(cfg.target_dir).as_posix()
	except ValueError:
		rel_md = md_file.name
	md_dir = posixpath.dirname(rel_md)
	if not md_dir:
		md_dir = '.'

	joined = posixpath.normpath(posixpath.join(md_dir, path_part))
	# Ensure no leading './'
	joined = joined.lstrip('./')
	root = (cfg.image_root_url or '/note_image').rstrip('/')
	rewritten_path = f"{root}/{joined}" if joined else root

	# Preserve query/fragment.
	if parts.query:
		rewritten_path += f"?{parts.query}"
	if parts.fragment:
		rewritten_path += f"#{parts.fragment}"
	return rewritten_path


def _rewrite_relative_image_urls(cfg: 'ProcessConfig', md_file: Path, markdown_body: str) -> str:
	# Markdown image syntax
	def md_repl(m: re.Match) -> str:
		prefix, url, angle, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
		new_url = _rewrite_relative_image_url_for_md(cfg, md_file, url)
		return f"{prefix}{new_url}{angle}{suffix}"

	out = _MD_IMAGE_SUB_RE.sub(md_repl, markdown_body)

	# HTML <img src="...">
	def html_repl(m: re.Match) -> str:
		url = m.group(1)
		new_url = _rewrite_relative_image_url_for_md(cfg, md_file, url)
		return m.group(0).replace(url, new_url, 1)

	out = _HTML_IMG_RE.sub(html_repl, out)
	return out


def _extract_first_image_url(markdown_body: str) -> Optional[str]:
	"""Return the first image URL in the body (Markdown image or HTML <img>)."""
	best_pos: Optional[int] = None
	best_url: Optional[str] = None

	for m in _MD_IMAGE_RE.finditer(markdown_body):
		url = (m.group(1) or '').strip()
		if not url:
			continue
		best_pos = m.start()
		best_url = url
		break

	# If HTML <img> appears earlier than the first Markdown image, prefer it.
	for m in _HTML_IMG_RE.finditer(markdown_body):
		url = (m.group(1) or '').strip()
		if not url:
			continue
		if best_pos is None or m.start() < best_pos:
			best_pos = m.start()
			best_url = url
		break

	return best_url


def _is_remote_or_data_url(url: str) -> bool:
	u = (url or '').strip().lower()
	return u.startswith('http://') or u.startswith('https://') or u.startswith('//') or u.startswith('data:')


def _local_image_exists(repo_root: Path, md_file: Path, url: str) -> bool:
	"""Best-effort check whether a referenced image exists locally.

	Rules:
	- remote/data URLs are treated as existing
	- leading '/' maps to <repo_root>/source/<path>
	- relative path checks (md_file.parent/<path>) then (<repo_root>/source/<path>)
	- ignores query/hash fragments
	"""
	if not url:
		return False
	if _is_remote_or_data_url(url):
		return True

	parts = urlsplit(url)
	path_part = (parts.path or '').strip()
	if not path_part:
		return False

	# Strip wrapping angle brackets, just in case.
	if path_part.startswith('<') and path_part.endswith('>'):
		path_part = path_part[1:-1]

	# Normalize Windows separators if present.
	path_part = path_part.replace('\\\\', '/')

	# Absolute from site root: map to repo_root/source
	if path_part.startswith('/'):
		p = (repo_root / 'source' / path_part.lstrip('/')).resolve()
		return p.exists()

	# Relative: try relative to md file first.
	p1 = (md_file.parent / path_part).resolve()
	if p1.exists():
		return True
	# Also try repo_root/source/<path> as a common Hexo convention.
	p2 = (repo_root / 'source' / path_part).resolve()
	return p2.exists()


def _stable_cover_index(key: str, n: int = 100) -> int:
	"""Return 1..n stable index based on key (file name / relative path)."""
	key_bytes = (key or '').encode('utf-8', errors='surrogatepass')
	digest = hashlib.sha1(key_bytes).digest()
	value = int.from_bytes(digest[:8], 'big', signed=False)
	return (value % n) + 1


def _default_cover_url(repo_root: Path, key: str) -> str:
	"""Pick a deterministic cover from 100 images.

	Prefer an existing file among:
	- /image/cover/cover-{i}.jpg
	- /images/cover/cover-{i}.jpg
	"""
	idx0 = _stable_cover_index(key, 100)
	prefixes = ['/image/cover', '/images/cover']

	# Robustness: if some numbers are missing, probe forward (wrap-around) deterministically.
	for offset in range(0, 100):
		i = ((idx0 - 1 + offset) % 100) + 1
		for prefix in prefixes:
			url = f"{prefix}/cover-{i}.jpg"
			if (repo_root / 'source' / url.lstrip('/')).exists():
				return url

	# Last resort: return the deterministic choice even if files aren't found.
	return f"/images/cover/cover-{idx0}.jpg"


def _format_hexo_datetime(epoch_seconds: int) -> str:
	# Required output example: 2013-7-13 20:46:25 (no leading zeros for M/D).
	dt = datetime.fromtimestamp(epoch_seconds)
	return f"{dt.year}-{dt.month}-{dt.day} {dt:%H:%M:%S}"


def _find_repo_root_from_target(target_dir: Path) -> Optional[Path]:
	# Best-effort: walk up to find typical Hexo repo markers.
	markers = {'package.json', '_config.yml'}
	for p in [target_dir, *target_dir.parents]:
		try:
			if all((p / m).exists() for m in markers):
				return p
		except OSError:
			continue
	return None


def _git_file_times_seconds(repo_dir: Path, rel_file_posix: str, date_kind: str) -> Optional[Tuple[int, int]]:
	# Return (created_ts, updated_ts) for a file in the given git repo.
	# We use --follow so renames are tracked.
	date_kind_norm = (date_kind or 'author').lower()
	fmt = '%at' if date_kind_norm == 'author' else '%ct'

	try:
		cp = subprocess.run(
			['git', '-C', str(repo_dir), 'log', '--follow', f'--format={fmt}', '--', rel_file_posix],
			check=False,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
		)
	except FileNotFoundError:
		raise RuntimeError("未找到 git 命令，请先安装 git")

	if cp.returncode != 0:
		return None
	lines = [ln.strip() for ln in cp.stdout.splitlines() if ln.strip()]
	if not lines:
		return None
	updated = int(lines[0])
	created = int(lines[-1])
	return created, updated


def _build_git_time_index(repo_dir: Path, interest_paths: Set[str], date_kind: str, verbose: bool) -> Dict[str, Tuple[int, int]]:
	"""Build {path -> (created_ts, updated_ts)} for selected paths using one git process.

	Strategy:
	- Stream `git log --name-status` once (newest -> oldest)
	- Track updates at first sight; track created by overwriting as we walk older
	- Handle renames by mapping old names back to the final (current) path
	- Early-stop once all interest paths have seen an 'A' (best-effort creation point)
	"""
	if not interest_paths:
		return {}

	date_kind_norm = (date_kind or 'author').lower()
	fmt = '%at' if date_kind_norm == 'author' else '%ct'
	marker = '__TS__'
	cmd = [
		'git',
		'-C', str(repo_dir),
		'-c', 'core.quotepath=false',
		'log',
		'--name-status',
		'--diff-filter=AMDR',
		f'--format={marker}%{fmt[1:]}',
	]

	try:
		p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
	except FileNotFoundError:
		raise RuntimeError("未找到 git 命令，请先安装 git")

	assert p.stdout is not None
	assert p.stderr is not None

	# Map historical (older) names -> final (current) name we attribute times to.
	back_alias: Dict[str, str] = {}
	updated: Dict[str, int] = {}
	created: Dict[str, int] = {}
	done: Set[str] = set()
	current_ts: Optional[int] = None

	def resolve_final(name: str) -> str:
		# Path compression for back_alias
		chain = []
		cur = name
		while cur in back_alias:
			chain.append(cur)
			cur = back_alias[cur]
		for n in chain:
			back_alias[n] = cur
		return cur

	try:
		for line in p.stdout:
			s = line.rstrip('\n')
			if not s:
				continue
			if s.startswith(marker):
				try:
					current_ts = int(s[len(marker):].strip())
				except ValueError:
					current_ts = None
				continue
			if current_ts is None:
				continue

			parts = s.split('\t')
			status = parts[0]
			# Rename: Rxxx\told\tnew
			if status.startswith('R') and len(parts) >= 3:
				old_name = parts[1]
				new_name = parts[2]
				final = resolve_final(new_name)
				if final in interest_paths:
					# Ensure old history is attributed to the final name.
					back_alias[old_name] = final
					updated.setdefault(final, current_ts)
					created[final] = current_ts
				continue

			if len(parts) < 2:
				continue
			path = parts[1]
			final = resolve_final(path)
			if final not in interest_paths:
				continue

			# First time we see it (from newest side) is the latest change.
			updated.setdefault(final, current_ts)
			# Keep overwriting as we go older; final value becomes the oldest seen.
			created[final] = current_ts
			if status == 'A':
				done.add(final)
				if len(done) == len(interest_paths):
					break
	finally:
		# Terminate early if we broke out, otherwise wait for completion.
		try:
			p.terminate()
		except Exception:
			pass
		p.wait(timeout=5)

	# Swallow stderr unless verbose (still return what we have).
	if verbose:
		err = p.stderr.read().strip()
		if err:
			print(f"[git] stderr: {err}")

	result: Dict[str, Tuple[int, int]] = {}
	for k in interest_paths:
		c = created.get(k)
		u = updated.get(k)
		if c is not None and u is not None:
			result[k] = (c, u)
	return result


def _build_front_matter(title: str, created_epoch_seconds: int, updated_epoch_seconds: int, categories, cover_url: str) -> str:
	title_json = json.dumps(title, ensure_ascii=False)
	cats = _yaml_list_inline_or_block(categories)
	created_str = json.dumps(_format_hexo_datetime(created_epoch_seconds), ensure_ascii=False)
	updated_str = json.dumps(_format_hexo_datetime(updated_epoch_seconds), ensure_ascii=False)
	cover_str = json.dumps(cover_url, ensure_ascii=False)
	return (
		"---\n"
		f"title: {title_json}\n"
		f"date: {created_str}\n"
		f"updated: {updated_str}\n"
		f"cover: {cover_str}\n"
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
	notes_dir: Path
	repo_root: Path
	image_root_url: str
	raw_wrap: str
	escape_curly: bool
	verbose: bool
	timestamp: Optional[int]
	date_kind: str
	git_batch: bool
	require_git_history: bool
	_time_cache: Dict[str, Tuple[int, int]]


def process_file(cfg: ProcessConfig, path: Path) -> bool:
	if not path.is_file() or not _is_markdown(path):
		return False

	raw = _read_text_best_effort(path)
	body = _strip_front_matter_if_any(raw)

	title = path.stem
	epoch_fallback = int(cfg.timestamp if cfg.timestamp is not None else int(time.time()))
	cat = _top_level_category(cfg.target_dir, path)
	categories = [cat] if cat else []

	# Derive created/updated from the original notes git history.
	created_epoch = epoch_fallback
	updated_epoch = epoch_fallback
	try:
		rel_to_target = path.relative_to(cfg.target_dir).as_posix()
	except ValueError:
		rel_to_target = path.name

	if rel_to_target in cfg._time_cache:
		created_epoch, updated_epoch = cfg._time_cache[rel_to_target]
	else:
		# Fallback: per-file query (slow). Kept for cases where batch index is disabled
		# or a particular file is missing from the batch results.
		times = _git_file_times_seconds(cfg.notes_dir, rel_to_target, cfg.date_kind)
		if times is None:
			msg = f"无法从 notes 的 git 历史获取时间：{rel_to_target}"
			if cfg.require_git_history:
				raise RuntimeError(msg)
			if cfg.verbose:
				print(f"[warn] {msg}，将使用 fallback 时间")
		else:
			cfg._time_cache[rel_to_target] = times
			created_epoch, updated_epoch = times

	# Rewrite relative image URLs to /note_image/... so both the post content and
	# cover extraction reference the new static directory.
	body = _rewrite_relative_image_urls(cfg, path, body)

	first_img = _extract_first_image_url(body)
	cover_url = first_img if (first_img and _local_image_exists(cfg.repo_root, path, first_img)) else _default_cover_url(cfg.repo_root, rel_to_target)

	front_matter = _build_front_matter(
		title=title,
		created_epoch_seconds=created_epoch,
		updated_epoch_seconds=updated_epoch,
		categories=categories,
		cover_url=cover_url,
	)
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

	files = [p for p in sorted(cfg.target_dir.rglob('*')) if p.is_file() and _is_markdown(p)]
	total = len(files)

	# Build git time index once (huge speed-up vs per-file git calls).
	if cfg.git_batch and files:
		interest = set()
		for p in files:
			try:
				interest.add(p.relative_to(cfg.target_dir).as_posix())
			except ValueError:
				interest.add(p.name)
			# Only fill missing to preserve any externally provided cache.
		missing = {x for x in interest if x not in cfg._time_cache}
		if missing:
			idx = _build_git_time_index(cfg.notes_dir, missing, cfg.date_kind, verbose=cfg.verbose)
			cfg._time_cache.update(idx)
			if cfg.verbose:
				print(f"[git] batch index: filled={len(idx)}/{len(missing)}")

	def render_bar(done: int, total_count: int, width: int = 24) -> str:
		if total_count <= 0:
			return "[" + ("-" * width) + "] 0/0"
		frac = max(0.0, min(1.0, done / float(total_count)))
		filled = int(round(frac * width))
		bar = "#" * filled + "-" * (width - filled)
		pct = int(frac * 100)
		return f"[{bar}] {done}/{total_count} {pct:3d}%"

	show_progress = (not cfg.verbose)
	is_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())
	last_reported_pct = -1

	count = 0
	for i, p in enumerate(files, start=1):
		if process_file(cfg, p):
			count += 1
			if cfg.verbose:
				print(f"[ok] {p.relative_to(cfg.target_dir).as_posix()}")

		if show_progress:
			if is_tty:
				msg = f"\r{render_bar(i, total)}"
				sys.stderr.write(msg)
				sys.stderr.flush()
			else:
				# Non-interactive output: print on percentage change (1% steps) and at the end.
				pct = int((i / max(1, total)) * 100)
				if pct != last_reported_pct and (pct % 5 == 0 or i == total):
					print(f"progress: {pct}% ({i}/{total})")
					last_reported_pct = pct

	if show_progress and is_tty:
		sys.stderr.write("\n")

	print(f"processed: {count} files, target={cfg.target_dir}")
	return 0


def main(argv=None) -> int:
	parser = argparse.ArgumentParser(
		description="统一处理 Hexo source/_posts 下的 Markdown：生成最小 front-matter，并可选 raw-wrap/花括号转义"
	)
	parser.add_argument('--target', default='source/_posts', help='目标目录（默认：source/_posts）')
	parser.add_argument('--notes', default=None, help='notes 仓库目录（默认：自动推断为 <repo_root>/notes）')
	parser.add_argument('--image-root', default='/note_image', help='图片 URL 根路径（默认：/note_image）')
	parser.add_argument('--raw-wrap', choices=['auto', 'always', 'never'], default='auto', help='遇到模板语法时用 Nunjucks raw 包裹正文（默认：auto）')
	parser.add_argument('--escape-curly', choices=['true', 'false'], default='true', help='是否转义 {{ }} 以避免 Nunjucks 解析（默认：true）')
	parser.add_argument('--git-date', choices=['author', 'committer'], default='author', help='使用 git 的 author 时间或 committer 时间（默认：author）')
	parser.add_argument('--git-batch', choices=['true', 'false'], default='false', help='是否用一次 git log 构建时间索引（默认：true）')
	parser.add_argument('--require-git-history', choices=['true', 'false'], default='true', help='无法读取 git 历史时是否直接失败（默认：true）')
	parser.add_argument('--timestamp', type=int, default=None, help='指定 date/updated 的时间戳（秒）。默认使用当前时间')
	parser.add_argument('-v', '--verbose', action='store_true', help='输出更多日志')
	args = parser.parse_args(argv)

	target_dir = Path(args.target).resolve()
	repo_root = _find_repo_root_from_target(target_dir)
	if repo_root is None:
		# Best-effort fallback to script location: <repo_root>/processor/process_posts.py
		repo_root = Path(__file__).resolve().parents[1]
	if args.notes:
		notes_dir = Path(args.notes).resolve()
	else:
		notes_dir = ((repo_root / 'notes') if repo_root else (target_dir.parents[1] / 'notes')).resolve()

	if not notes_dir.exists() or not (notes_dir / '.git').exists():
		raise RuntimeError(f"notes 仓库不存在或不是 git 仓库：{notes_dir}（请先运行 ./sync.sh 或指定 --notes）")

	cfg = ProcessConfig(
		target_dir=target_dir,
		notes_dir=notes_dir,
		repo_root=repo_root,
		image_root_url=str(args.image_root),
		raw_wrap=str(args.raw_wrap),
		escape_curly=str(args.escape_curly).lower() == 'true',
		verbose=bool(args.verbose),
		timestamp=args.timestamp,
		date_kind=str(args.git_date),
		git_batch=str(args.git_batch).lower() == 'true',
		require_git_history=str(args.require_git_history).lower() == 'true',
		_time_cache={},
	)
	return process_directory(cfg)


if __name__ == '__main__':
	raise SystemExit(main())
