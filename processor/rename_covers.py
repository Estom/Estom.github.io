#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


_IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.ico', '.avif', '.svg'}


def _is_image(p: Path) -> bool:
	return p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES


def _natural_key(name: str) -> Tuple:
	# Best-effort natural sort: split digits.
	parts = re.split(r'(\d+)', name)
	key = []
	for part in parts:
		if part.isdigit():
			key.append(int(part))
		else:
			key.append(part.lower())
	return tuple(key)


def _list_images(dir_path: Path) -> List[Path]:
	files = [p for p in dir_path.iterdir() if _is_image(p)]
	files.sort(key=lambda p: _natural_key(p.name))
	return files


def _ensure_dir(path: Path) -> None:
	if not path.exists() or not path.is_dir():
		raise RuntimeError(f"目录不存在或不是目录：{path}")


def _target_name(i: int, ext: str = '.jpg') -> str:
	return f"cover-{i}{ext}"


@dataclass(frozen=True)
class RenamePlan:
	sources: Sequence[Path]
	final_names: Sequence[str]


def _build_plan(images: Sequence[Path], start: int, ext: str) -> RenamePlan:
	final_names = [_target_name(start + idx, ext) for idx in range(len(images))]
	return RenamePlan(sources=images, final_names=final_names)


def _validate_plan(dir_path: Path, plan: RenamePlan, overwrite: bool) -> None:
	# Check for conflicts with non-involved files.
	existing = {p.name for p in dir_path.iterdir() if p.is_file()}
	source_names = {p.name for p in plan.sources}

	for name in plan.final_names:
		if name in existing and name not in source_names and not overwrite:
			raise RuntimeError(
				f"目标文件已存在且不允许覆盖：{dir_path / name}\n"
				"你可以先清空 cover 目录或使用 --overwrite"
			)


def _apply_rename(dir_path: Path, plan: RenamePlan, dry_run: bool, overwrite: bool, verbose: bool) -> None:
	# Two-phase rename to avoid collisions (e.g. cover-1.jpg already present among sources).
	token = uuid.uuid4().hex[:8]
	tmp_names = [f".__tmp_cover_{token}_{i}__{src.suffix.lower()}" for i, src in enumerate(plan.sources, start=1)]

	# Phase 1: sources -> temp
	for src, tmp in zip(plan.sources, tmp_names):
		tmp_path = dir_path / tmp
		if dry_run:
			print(f"[dry-run] mv {src.name} -> {tmp}")
			continue
		if tmp_path.exists() and not overwrite:
			raise RuntimeError(f"临时文件已存在：{tmp_path}")
		src.rename(tmp_path)
		if verbose:
			print(f"[tmp] {src.name} -> {tmp}")

	# Phase 2: temp -> final
	for tmp, final in zip(tmp_names, plan.final_names):
		tmp_path = dir_path / tmp
		final_path = dir_path / final
		if dry_run:
			print(f"[dry-run] mv {tmp} -> {final}")
			continue
		if final_path.exists():
			if overwrite:
				final_path.unlink()
			else:
				raise RuntimeError(f"目标文件已存在：{final_path}")
		tmp_path.rename(final_path)
		if verbose:
			print(f"[ok] {tmp} -> {final}")


def main(argv: List[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		description="将 source/images/cover 下的图片批量重命名为 cover-1.jpg, cover-2.jpg, ..."
	)
	parser.add_argument('--dir', default='source/images/cover', help='cover 目录（默认：source/images/cover）')
	parser.add_argument('--start', type=int, default=1, help='编号起始值（默认：1）')
	parser.add_argument('--ext', default='.jpg', help='目标扩展名（默认：.jpg）')
	parser.add_argument('--dry-run', action='store_true', help='只打印重命名计划，不实际修改文件')
	parser.add_argument('--overwrite', action='store_true', help='允许覆盖已存在的目标文件')
	parser.add_argument('-v', '--verbose', action='store_true', help='输出更多日志')
	args = parser.parse_args(argv)

	dir_path = Path(args.dir).resolve()
	_ensure_dir(dir_path)

	start = int(args.start)
	if start <= 0:
		raise SystemExit("--start 必须 >= 1")

	ext = str(args.ext).strip()
	if not ext.startswith('.'):
		ext = '.' + ext
	if ext.lower() != ext:
		ext = ext.lower()

	images = _list_images(dir_path)
	if not images:
		print(f"未找到图片：{dir_path}")
		return 0

	# Safety: if forcing .jpg but some files are non-jpg, warn.
	non_jpg = [p for p in images if p.suffix.lower() not in {'.jpg', '.jpeg'}]
	if ext == '.jpg' and non_jpg:
		print("[warn] cover 目录里存在非 jpg/jpeg 图片：")
		for p in non_jpg[:20]:
			print(f"  - {p.name}")
		if len(non_jpg) > 20:
			print(f"  ... ({len(non_jpg)} total)")
		print("[warn] 本脚本只做重命名，不会进行图片格式转换；非 jpg/jpeg 文件会被直接改名为 .jpg（可能导致查看器无法识别）。")

	plan = _build_plan(images, start=start, ext=ext)
	_validate_plan(dir_path, plan, overwrite=bool(args.overwrite))

	if args.dry_run:
		print(f"dir: {dir_path}")
		print(f"count: {len(plan.sources)}")
		for src, final in zip(plan.sources, plan.final_names):
			print(f"  {src.name} -> {final}")

	_apply_rename(dir_path, plan, dry_run=bool(args.dry_run), overwrite=bool(args.overwrite), verbose=bool(args.verbose))

	if not args.dry_run:
		print(f"done: renamed {len(plan.sources)} files in {dir_path}")
	return 0


if __name__ == '__main__':
	raise SystemExit(main())
