#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import sys
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Set, Tuple


def _to_posix_relpath(path: Path) -> str:
	# NOTE: always return a relative, POSIX-style path for gitignore matching.
	# PathSpec expects '/' separators.
	return path.as_posix().lstrip('/')


def _load_ignore_spec(ignore_file: Path):
	"""Load .bgignore patterns using gitignore-style rules.

	Requires the third-party 'pathspec' library.
	"""
	try:
		from pathspec import PathSpec
	except Exception as exc:  # pragma: no cover
		raise RuntimeError(
			"缺少 Python 依赖 pathspec，无法按 .gitignore 规则解析 .bgignore。\n"
			"请在仓库根目录执行：pip install -r requirements.txt\n"
			"或：pip install pathspec"
		) from exc

	if not ignore_file.exists():
		return PathSpec.from_lines('gitwildmatch', [])

	lines = ignore_file.read_text(encoding='utf-8').splitlines()
	return PathSpec.from_lines('gitwildmatch', lines)


@dataclass(frozen=True)
class SyncConfig:
	repo_root: Path
	notes_dir: Path
	target_dir: Path
	image_target_dir: Path
	ignore_file: Path
	min_md_per_tree: int
	dry_run: bool
	verbose: bool
	delete_before_sync: bool
	post_process: bool


def _is_markdown(path: Path) -> bool:
	return path.suffix.lower() in {'.md', '.markdown'}


def _is_image(path: Path) -> bool:
	# Common image types used in markdown notes.
	return path.suffix.lower() in {
		'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.tiff', '.tif', '.ico', '.avif'
	}


def _extract_title_from_markdown(content: str, fallback: str) -> str:
	# Prefer the first ATX H1 title.
	for line in content.splitlines():
		s = line.strip()
		if s.startswith('# '):
			return s[2:].strip() or fallback
	return fallback


def _has_front_matter_prefix(content: str) -> bool:
	# Old style: starts with ---/;;; front-matter block.
	# If already present, keep as-is.
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
	# Find the closing separator line (same token).
	for i in range(1, len(lines)):
		if lines[i].strip() == sep:
			fm = ''.join(lines[:i + 1])
			body = ''.join(lines[i + 1:])
			return fm, body
	# No closing separator; treat as no front matter to avoid corrupting.
	return '', content


def _ensure_front_matter(content: str, title: str) -> str:
	# Hexo's hexo-front-matter supports a "new" format where a later `---` line
	# can cause the entire prefix to be parsed as YAML. To avoid accidental YAML
	# parsing of normal markdown, we always add a minimal old-style front-matter
	# unless one already exists.
	if _has_front_matter_prefix(content):
		return content
	# Quote title safely for YAML via JSON string.
	title_json = json.dumps(title, ensure_ascii=False)
	header = f"---\ntitle: {title_json}\n---\n\n"
	return header + content


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
	# Ensure raw tags are surrounded by newlines so markdown stays intact.
	return '{% raw %}\n' + body + ('\n' if not body.endswith('\n') else '') + '{% endraw %}\n'


def _escape_nunjucks_curly(content: str) -> str:
	# Hexo uses Nunjucks to process tag plugins inside posts. Any `{{ ... }}`
	# sequence in plain text can be parsed as a Nunjucks variable and break.
	# We escape them to HTML entities so rendered output still shows braces.
	return content.replace('{{', '&#123;&#123;').replace('}}', '&#125;&#125;')


def _read_text_best_effort(path: Path) -> str:
	# Most notes are UTF-8; accept BOM; fall back to replacement to avoid crashing.
	try:
		return path.read_text(encoding='utf-8-sig')
	except UnicodeDecodeError:
		return path.read_text(encoding='utf-8', errors='replace')


def _walk_notes(cfg: SyncConfig, ignore_spec) -> Tuple[List[str], List[str], Dict[str, int], Set[str]]:
	"""Return (md_files, image_files, local_md_count_by_dir, all_dirs).

	- md_files: list of markdown file paths relative to notes_dir (POSIX)
	- image_files: list of image file paths relative to notes_dir (POSIX)
	- local_md_count_by_dir: dir_rel_posix -> markdown count directly under that dir
	- all_dirs: set of all visited directories (dir_rel_posix), including '.'
	"""
	md_files: List[str] = []
	image_files: List[str] = []
	local_counts: Dict[str, int] = {}
	all_dirs: Set[str] = set()

	def is_ignored(rel_posix: str, is_dir: bool) -> bool:
		# PathSpec matches directories when the path ends with '/'
		candidate = rel_posix + ('/' if is_dir else '')
		return bool(ignore_spec.match_file(candidate))

	for root, dirnames, filenames in os.walk(cfg.notes_dir, topdown=True):
		root_path = Path(root)
		rel_dir = root_path.relative_to(cfg.notes_dir)
		rel_dir_posix = _to_posix_relpath(rel_dir) or '.'
		all_dirs.add(rel_dir_posix)

		# Prune ignored directories in-place
		pruned: List[str] = []
		for d in list(dirnames):
			rel_d = (rel_dir / d)
			rel_d_posix = _to_posix_relpath(rel_d)
			if is_ignored(rel_d_posix, is_dir=True):
				dirnames.remove(d)
				pruned.append(d)
			else:
				all_dirs.add(rel_d_posix)
		if cfg.verbose and pruned:
			print(f"[ignore] prune dirs under {rel_dir_posix}: {', '.join(pruned)}")

		count_here = 0
		for name in filenames:
			src = root_path / name
			rel_f = rel_dir / name
			rel_f_posix = _to_posix_relpath(rel_f)
			if is_ignored(rel_f_posix, is_dir=False):
				if cfg.verbose:
					print(f"[ignore] {rel_f_posix}")
				continue
			if _is_markdown(src):
				md_files.append(rel_f_posix)
				count_here += 1
			elif _is_image(src):
				image_files.append(rel_f_posix)
		local_counts[rel_dir_posix] = local_counts.get(rel_dir_posix, 0) + count_here

	md_files.sort()
	image_files.sort()
	return md_files, image_files, local_counts, all_dirs


def _compute_subtree_counts(local_counts: Dict[str, int], all_dirs: Set[str]) -> Dict[str, int]:
	subtree: Dict[str, int] = {d: local_counts.get(d, 0) for d in all_dirs}

	# Process deepest directories first
	def depth(d: str) -> int:
		if d == '.':
			return 0
		return len(PurePosixPath(d).parts)

	for d in sorted(all_dirs, key=depth, reverse=True):
		if d == '.':
			continue
		p = str(PurePosixPath(d).parent)
		if p == '':
			p = '.'
		subtree[p] = subtree.get(p, 0) + subtree.get(d, 0)

	return subtree


def _sync(cfg: SyncConfig) -> int:
	ignore_spec = _load_ignore_spec(cfg.ignore_file)
	md_files, image_files, local_counts, all_dirs = _walk_notes(cfg, ignore_spec)
	subtree_counts = _compute_subtree_counts(local_counts, all_dirs)

	if cfg.verbose:
		print(f"[scan] markdown files found (after ignore): {len(md_files)}")
		print(f"[scan] image files found (after ignore): {len(image_files)}")

	# Directories whose whole subtree has at least N markdown files
	eligible_dirs = {d for d, c in subtree_counts.items() if c >= cfg.min_md_per_tree}
	if cfg.verbose:
		skipped_dirs = sorted({d for d, c in subtree_counts.items() if c < cfg.min_md_per_tree})
		if skipped_dirs:
			print(f"[rule] skip subtree (<{cfg.min_md_per_tree} md): {len(skipped_dirs)} dirs")

	# Optionally delete existing markdown docs in target before sync.
	if cfg.delete_before_sync:
		if cfg.dry_run:
			print(f"[dry-run] delete markdown under {cfg.target_dir}")
			print(f"[dry-run] delete images under {cfg.image_target_dir}")
		else:
			if cfg.target_dir.exists():
				deleted_md = 0
				for p in cfg.target_dir.rglob('*'):
					if p.is_file() and _is_markdown(p):
						p.unlink()
						deleted_md += 1
				# attempt to remove empty dirs bottom-up
				for d in sorted((x for x in cfg.target_dir.rglob('*') if x.is_dir()), key=lambda x: len(x.as_posix()), reverse=True):
					try:
						d.rmdir()
					except OSError:
						pass
				if cfg.verbose:
					print(f"[delete] removed markdown files: {deleted_md}")
			else:
				cfg.target_dir.mkdir(parents=True, exist_ok=True)

			if cfg.image_target_dir.exists():
				deleted_img = 0
				for p in cfg.image_target_dir.rglob('*'):
					if p.is_file() and _is_image(p):
						p.unlink()
						deleted_img += 1
				# attempt to remove empty dirs bottom-up
				for d in sorted((x for x in cfg.image_target_dir.rglob('*') if x.is_dir()), key=lambda x: len(x.as_posix()), reverse=True):
					try:
						d.rmdir()
					except OSError:
						pass
				if cfg.verbose:
					print(f"[delete] removed image files: {deleted_img}")
			else:
				cfg.image_target_dir.mkdir(parents=True, exist_ok=True)

	copied = 0
	skipped = 0
	copied_images = 0

	for rel_posix in md_files:
		rel_path = Path(rel_posix)
		parent_dir = _to_posix_relpath(rel_path.parent) or '.'
		if parent_dir not in eligible_dirs:
			skipped += 1
			if cfg.verbose:
				print(f"[skip] {rel_posix} (dir subtree md < {cfg.min_md_per_tree})")
			continue

		src = cfg.notes_dir / rel_path
		dst = cfg.target_dir / rel_path
		if cfg.dry_run:
			print(f"[dry-run] copy {src} -> {dst}")
		else:
			dst.parent.mkdir(parents=True, exist_ok=True)
			# Copy content as UTF-8 text; post-processing will normalize front-matter.
			raw = _read_text_best_effort(src)
			dst.write_text(raw, encoding='utf-8')
		copied += 1

	# Copy ALL images (after ignore) while keeping the directory structure.
	# Images are not gated by the markdown subtree threshold to avoid breaking relative references.
	for rel_posix in image_files:
		rel_path = Path(rel_posix)
		src = cfg.notes_dir / rel_path
		dst = cfg.image_target_dir / rel_path
		if cfg.dry_run:
			print(f"[dry-run] copy {src} -> {dst}")
		else:
			dst.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(src, dst)
		copied_images += 1

	print(f"done: copied_md={copied}, skipped_md={skipped}, copied_img={copied_images}, target={cfg.target_dir}")

	# Post-process all markdown under target_dir.
	if cfg.post_process and not cfg.dry_run:
		processor_script = (cfg.repo_root / 'processor' / 'process_posts.py').resolve()
		if not processor_script.exists():
			raise RuntimeError(f"缺少处理脚本：{processor_script}")
		cmd = [sys.executable, str(processor_script), '--target', str(cfg.target_dir)]
		if cfg.verbose:
			cmd.append('--verbose')
		try:
			subprocess.run(cmd, check=True)
		except subprocess.CalledProcessError as e:
			raise RuntimeError(f"内容处理脚本执行失败（exit={e.returncode}）：{' '.join(cmd)}")

	return 0


def _resolve_notes_dir(repo_root: Path, user_value: str) -> Path:
	p = Path(user_value)
	if p.is_absolute():
		return p
	return (repo_root / p).resolve()


def main(argv: Optional[List[str]] = None) -> int:
	# repo root is the parent directory of 'processor'
	repo_root = Path(__file__).resolve().parents[1]
	parser = argparse.ArgumentParser(
		description="同步 notes 下的 Markdown + 图片 到 Hexo source/_posts（保留目录结构、支持 .bgignore、目录子树 Markdown 数量阈值）"
	)
	parser.add_argument('--notes', default='notes', help='notes 目录路径（默认：仓库根目录下的 notes）')
	parser.add_argument('--target', default='source/_posts', help='目标目录（默认：source/_posts）')
	parser.add_argument('--image-target', default='source/note_image', help='图片目标目录（默认：source/note_image）')
	parser.add_argument('--ignore-file', default='.bgignore', help='忽略规则文件（默认：.bgignore）')
	parser.add_argument('--min-md', type=int, default=2, help='目录子树内最少 Markdown 数（默认：2）')
	parser.add_argument('--delete', action='store_true', help='同步前清空目标目录下所有 Markdown 文档，然后重新生成')
	parser.add_argument('--no-post-process', action='store_true', help='不同步后处理（默认会扫描 target 下所有 Markdown 生成统一 front-matter）')
	parser.add_argument('--dry-run', action='store_true', help='只打印将要复制的文件，不实际写入')
	parser.add_argument('-v', '--verbose', action='store_true', help='输出更多日志')

	args = parser.parse_args(argv)

	notes_dir = _resolve_notes_dir(repo_root, args.notes)
	target_dir = (repo_root / args.target).resolve()
	image_target_dir = (repo_root / args.image_target).resolve()
	ignore_file = (repo_root / args.ignore_file).resolve()

	if not notes_dir.exists() or not notes_dir.is_dir():
		print(f"notes 目录不存在：{notes_dir}")
		print("你可以显式指定，例如：python3 sync.py --notes /home/estom/work/notes")
		return 2

	cfg = SyncConfig(
		repo_root=repo_root,
		notes_dir=notes_dir,
		target_dir=target_dir,
		image_target_dir=image_target_dir,
		ignore_file=ignore_file,
		min_md_per_tree=max(1, int(args.min_md)),
		dry_run=bool(args.dry_run),
		verbose=bool(args.verbose),
		delete_before_sync=bool(args.delete),
		post_process=not bool(args.no_post_process),
	)

	try:
		return _sync(cfg)
	except BrokenPipeError:
		# When piping output (e.g. to `head`), stdout may close early.
		return 0
	except RuntimeError as e:
		print(str(e))
		return 3


if __name__ == '__main__':
	raise SystemExit(main())
