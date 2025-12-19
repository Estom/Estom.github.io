#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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


def _build_front_matter(title: str, created_epoch_seconds: int, updated_epoch_seconds: int, categories) -> str:
	title_json = json.dumps(title, ensure_ascii=False)
	cats = _yaml_list_inline_or_block(categories)
	created_str = json.dumps(_format_hexo_datetime(created_epoch_seconds), ensure_ascii=False)
	updated_str = json.dumps(_format_hexo_datetime(updated_epoch_seconds), ensure_ascii=False)
	return (
		"---\n"
		f"title: {title_json}\n"
		f"date: {created_str}\n"
		f"updated: {updated_str}\n"
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

	front_matter = _build_front_matter(
		title=title,
		created_epoch_seconds=created_epoch,
		updated_epoch_seconds=updated_epoch,
		categories=categories,
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
	if args.notes:
		notes_dir = Path(args.notes).resolve()
	else:
		notes_dir = ((repo_root / 'notes') if repo_root else (target_dir.parents[1] / 'notes')).resolve()

	if not notes_dir.exists() or not (notes_dir / '.git').exists():
		raise RuntimeError(f"notes 仓库不存在或不是 git 仓库：{notes_dir}（请先运行 ./sync.sh 或指定 --notes）")

	cfg = ProcessConfig(
		target_dir=target_dir,
		notes_dir=notes_dir,
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
