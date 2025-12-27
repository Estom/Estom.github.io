#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from typing import Dict, List, Optional, Protocol, Set, Tuple


_TAG_STOPWORDS = {
	'note_image', 'images', 'image', 'img', 'http', 'https', 'www',
	'true', 'false', 'null', 'none',
}


class TagExtractor(Protocol):
	"""Pluggable tag extractor.

	Implementations should return {rel_path_posix -> [tag, ...]}.
	"""

	name: str

	def build_index(
		self,
		files: List[Path],
		target_root: Path,
		tag_count: int,
		max_unique_tags: int,
		verbose: bool,
	) -> Dict[str, List[str]]: ...


@dataclass
class ProgressPrinter:
	"""Print progress in both interactive (TTY) and non-interactive environments.

	- TTY: renders a single-line progress bar updated in-place.
	- Non-TTY (CI/server): prints on every 1% progress change.
	"""

	enabled: bool
	prefix: str
	width: int = 24
	tty_stream = sys.stderr
	_last_pct: int = -1
	_is_tty: bool = False

	def __post_init__(self) -> None:
		if not self.enabled:
			return
		self._is_tty = bool(getattr(self.tty_stream, "isatty", lambda: False)())
		print(f"[tags] enabled: {self.enabled},is_tty: {self._is_tty}")

	def _render_bar(self, done: int, total: int) -> str:
		if total <= 0:
			return "[" + ("-" * self.width) + "] 0/0"
		frac = max(0.0, min(1.0, done / float(total)))
		filled = int(round(frac * self.width))
		bar = "#" * filled + "-" * (self.width - filled)
		pct = int(frac * 100)
		return f"[{bar}] {done}/{total} {pct:3d}%"

	def update(self, done: int, total: int) -> None:
		if not self.enabled:
			return
		if total < 0:
			total = 0
		if done < 0:
			done = 0
		if total > 0 and done > total:
			done = total

		if self._is_tty:
			msg = f"\r{self.prefix} {self._render_bar(done, total)}"
			self.tty_stream.write(msg)
			self.tty_stream.flush()
			return

		pct = int((done / max(1, total)) * 100)
		# Non-interactive: print every 1% change.
		if pct != self._last_pct:
			print(f"{self.prefix}: {pct}% ({done}/{total})")
			self._last_pct = pct

	def close(self, total: int) -> None:
		if not self.enabled:
			return
		self.update(total, total)
		if self._is_tty:
			self.tty_stream.write("\n")
			self.tty_stream.flush()


def _clean_text_for_tags(text: str) -> str:
	# Remove common non-content segments to reduce noisy tokens.
	clean = text
	clean = re.sub(r"```[\s\S]*?```", "\n", clean)  # fenced code blocks
	clean = re.sub(r"`[^`]+`", " ", clean)  # inline code
	clean = re.sub(r"!\[[^\]]*\]\([^\)]*\)", " ", clean)  # markdown images
	clean = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r" \1 ", clean)  # markdown links -> keep text
	clean = re.sub(r"<[^>]+>", " ", clean)  # html tags
	clean = re.sub(r"https?://\S+", " ", clean)  # urls
	clean = re.sub(r"\bwww\.\S+", " ", clean)
	return clean


def _jieba_tokenize(text: str, *, dedupe: bool = True) -> List[str]:
	try:
		import jieba
	except Exception as exc:  # pragma: no cover
		raise RuntimeError(
			"缺少 Python 依赖 jieba，无法进行分词。\n"
			"请在仓库根目录执行：pip install -r requirements.txt\n"
			"或：pip install jieba"
		) from exc

	clean = _clean_text_for_tags(text)
	result: List[str] = []
	seen: Set[str] = set()
	for t in jieba.cut(clean, cut_all=False):
		w = (t or '').strip()
		if not w:
			continue
		lw = w.lower()
		if lw in _TAG_STOPWORDS:
			continue
		if dedupe and lw in seen:
			continue
		# skip very short tokens
		if len(w) < 2:
			continue
		# skip pure digits
		if w.isdigit():
			continue
		# skip path-like tokens
		if '/' in w or '\\' in w:
			continue
		if dedupe:
			seen.add(lw)
		result.append(w)
	return result


def _build_tfidf_tag_index(
	files: List[Path],
	target_root: Path,
	tag_count: int,
	max_unique_tags: int,
	verbose: bool,
) -> Dict[str, List[str]]:
	"""Compute global TF-IDF (IDF from full corpus) and select tags per file.

	Returns: {rel_path_posix -> [tag, ...]}
	"""
	if tag_count <= 0 or not files:
		return {}

	print(f"[tags] building index for {len(files)} files...")
 
	try:
		from sklearn.feature_extraction.text import TfidfVectorizer
	except Exception as exc:  # pragma: no cover
		raise RuntimeError(
			"缺少 Python 依赖 scikit-learn，无法使用 sklearn 的 TF-IDF。\n"
			"请在仓库根目录执行：pip install -r requirements.txt\n"
			"或：pip install scikit-learn"
		) from exc

	# Build corpus: jieba tokens joined by spaces.
	progress_corpus = ProgressPrinter(enabled=verbose, prefix='[tags tfidf] corpus')
	rel_paths: List[str] = []
	corpus: List[str] = []
	for i, p in enumerate(files, start=1):
		rel = p.relative_to(target_root).as_posix()
		rel_paths.append(rel)
		raw = _read_text_best_effort(p)
		body = _strip_front_matter_if_any(raw)
		tokens = _jieba_tokenize(body, dedupe=True)
		corpus.append(' '.join(tokens))
		progress_corpus.update(i, len(files))
	progress_corpus.close(len(files))

	vectorizer = TfidfVectorizer(
		# We already tokenized; keep tokens as-is.
		tokenizer=str.split,
		preprocessor=None,
		token_pattern=None,
		lowercase=False,
	)
	X = vectorizer.fit_transform(corpus)
	features = vectorizer.get_feature_names_out()

	used_global: Set[str] = set()
	tags_by_path: Dict[str, List[str]] = {}
	progress_pick = ProgressPrinter(enabled=verbose, prefix='[tags tfidf] pick')

	for i, rel in enumerate(rel_paths):
		row = X.getrow(i)
		if row.nnz == 0:
			tags_by_path[rel] = []
			progress_pick.update(i + 1, len(rel_paths))
			continue
		# Sort terms by TF-IDF score descending.
		pairs = sorted(zip(row.indices, row.data), key=lambda x: x[1], reverse=True)
		picked: List[str] = []
		for idx, _score in pairs[: max(30, tag_count * 10)]:
			t = str(features[int(idx)])
			if not t:
				continue
			lt = t.lower()
			if lt in _TAG_STOPWORDS:
				continue
			# Enforce global unique tag budget.
			if lt not in used_global and len(used_global) >= max_unique_tags:
				continue
			if lt not in used_global:
				used_global.add(lt)
			picked.append(t)
			if len(picked) >= tag_count:
				break
		tags_by_path[rel] = picked
		progress_pick.update(i + 1, len(rel_paths))
	progress_pick.close(len(rel_paths))

	if verbose:
		print(f"[tags] unique={len(used_global)}/{max_unique_tags}")
	return tags_by_path


def _build_textrank_tag_index(
	files: List[Path],
	target_root: Path,
	tag_count: int,
	max_unique_tags: int,
	verbose: bool,
) -> Dict[str, List[str]]:
	"""Compute tags per file using jieba + textrank4zh TextRank keywords."""
	if tag_count <= 0 or not files:
		return {}

	try:
		from textrank4zh import TextRank4Keyword
	except Exception as exc:  # pragma: no cover
		raise RuntimeError(
			"缺少 Python 依赖 textrank4zh，无法使用 TextRank 提取关键词。\n"
			"请在仓库根目录执行：pip install -r requirements.txt\n"
			"或：pip install textrank4zh"
		) from exc
	print(f"[tags] start building TextRank index for {len(files)} files...")
	progress = ProgressPrinter(enabled=verbose, prefix='[tags textrank]')

	used_global: Set[str] = set()
	tags_by_path: Dict[str, List[str]] = {}

	for i, p in enumerate(files, start=1):
		rel = p.relative_to(target_root).as_posix()
		raw = _read_text_best_effort(p)
		body = _strip_front_matter_if_any(raw)
		# KeyBERT 对中文混合文本若直接喂原文，容易抽出“短语/片段”。
		# 这里先用 jieba 分词，再用空格拼回去，让 KeyBERT 在“词粒度”上做 (1,1) 抽取。
		# 注意：不去重以保留词频，帮助相关性排序。
		clean = _clean_text_for_tags(body)
		tokens = _jieba_tokenize(clean, dedupe=False)
		if not tokens:
			tags_by_path[rel] = []
			continue
		doc = ' '.join(tokens)

		tr = TextRank4Keyword()
		# textrank4zh uses jieba internally
		try:
			tr.analyze(text=clean, lower=True, window=2)
		except AttributeError as exc:
			# textrank4zh 依赖旧版 networkx API（例如 from_numpy_matrix），
			# 在 networkx 3.x 中已移除。
			raise RuntimeError(
				"textrank4zh 与当前 networkx 版本不兼容。\n"
				"请安装 networkx<3（本项目已在 pyproject.toml 里 pin）。\n"
				"建议执行：uv sync（或 uv pip install 'networkx<3'）"
			) from exc
		candidates = tr.get_keywords(num=max(30, tag_count * 10), word_min_len=2)

		picked: List[str] = []
		for item in candidates:
			word = (getattr(item, 'word', None) or '').strip()
			if not word:
				continue
			lw = word.lower()
			if lw in _TAG_STOPWORDS:
				continue
			# Enforce global unique tag budget.
			if lw not in used_global and len(used_global) >= max_unique_tags:
				continue
			if lw not in used_global:
				used_global.add(lw)
			picked.append(word)
			if len(picked) >= tag_count:
				break
		tags_by_path[rel] = picked
		progress.update(i, len(files))
	progress.close(len(files))

	if verbose:
		print(f"[tags] end building TextRank index, unique={len(used_global)}/{max_unique_tags}")
	return tags_by_path


def _build_keybert_tag_index(
	files: List[Path],
	target_root: Path,
	tag_count: int,
	max_unique_tags: int,
	verbose: bool,
) -> Dict[str, List[str]]:
	"""Compute tags per file using KeyBERT + sentence-transformers.

	Notes:
	- This usually downloads a transformer model on first run.
	- We still enforce the global unique tag budget.
	"""
	if tag_count <= 0 or not files:
		return {}

	try:
		from keybert import KeyBERT
	except Exception as exc:  # pragma: no cover
		raise RuntimeError(
			"缺少 Python 依赖 keybert，无法使用 KeyBERT 提取关键词。\n"
			"请在仓库根目录执行：uv sync\n"
			"或：pip install keybert"
		) from exc

	try:
		from sentence_transformers import SentenceTransformer
	except Exception as exc:  # pragma: no cover
		raise RuntimeError(
			"缺少 Python 依赖 sentence-transformers，无法使用 KeyBERT（需要嵌入模型）。\n"
			"请在仓库根目录执行：uv sync\n"
			"或：pip install sentence-transformers"
		) from exc

	print(f"[tags] start building KeyBERT index for {len(files)} files...")
	progress = ProgressPrinter(enabled=verbose, prefix='[tags keybert]')

	# A multilingual model works for Chinese and English mixed content.
	# Keep it as an internal default to avoid expanding CLI surface.
	model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
	try:
		embed_model = SentenceTransformer(model_name)
		kw_model = KeyBERT(model=embed_model)
	except Exception as exc:  # pragma: no cover
		raise RuntimeError(
			"KeyBERT 初始化失败（可能是首次下载模型失败或网络受限）。\n"
			f"模型：{model_name}\n"
			"可重试或预先下载模型后再运行。"
		) from exc

	used_global: Set[str] = set()
	tags_by_path: Dict[str, List[str]] = {}

	for i, p in enumerate(files, start=1):
		rel = p.relative_to(target_root).as_posix()
		raw = _read_text_best_effort(p)
		body = _strip_front_matter_if_any(raw)
		clean = _clean_text_for_tags(body)
		tokens = _jieba_tokenize(clean, dedupe=False)
		if not tokens:
			tags_by_path[rel] = []
			continue
		doc = ' '.join(tokens)

		# KeyBERT returns list[(keyword, score)]. Use keyphrase_ngram_range=(1,1)
		# to align with the existing per-tag token behavior.
		try:
			candidates = kw_model.extract_keywords(
				doc,
				keyphrase_ngram_range=(1, 1),
				top_n=max(30, tag_count * 10),
				use_mmr=False,
				diversity=0.0,
			)
		except Exception as exc:
			raise RuntimeError(f"KeyBERT 提取关键词失败：{rel}") from exc

		picked: List[str] = []
		seen_local: Set[str] = set()
		for kw, _score in candidates:
			word = (kw or '').strip()
			if not word:
				continue
			# 理论上 (1,1) 会返回单 token，但仍做兜底：过滤带空白的片段。
			if any(ch.isspace() for ch in word):
				continue
			lw = word.lower()
			if lw in _TAG_STOPWORDS:
				continue
			if lw in seen_local:
				continue
			# Skip very short tokens
			if len(word) < 2:
				continue
			# Skip pure digits
			if word.isdigit():
				continue
			# Skip path-like tokens
			if '/' in word or '\\' in word:
				continue

			# Enforce global unique tag budget.
			if lw not in used_global and len(used_global) >= max_unique_tags:
				continue
			if lw not in used_global:
				used_global.add(lw)
			seen_local.add(lw)
			picked.append(word)
			if len(picked) >= tag_count:
				break

		tags_by_path[rel] = picked
		progress.update(i, len(files))
	progress.close(len(files))

	if verbose:
		print(f"[tags] unique={len(used_global)}/{max_unique_tags}")
	return tags_by_path


class TfidfTagExtractor:
	name = 'tfidf'

	def build_index(
		self,
		files: List[Path],
		target_root: Path,
		tag_count: int,
		max_unique_tags: int,
		verbose: bool,
	) -> Dict[str, List[str]]:
		return _build_tfidf_tag_index(
			files=files,
			target_root=target_root,
			tag_count=tag_count,
			max_unique_tags=max_unique_tags,
			verbose=verbose,
		)


class TextRankTagExtractor:
	name = 'textrank'

	def build_index(
		self,
		files: List[Path],
		target_root: Path,
		tag_count: int,
		max_unique_tags: int,
		verbose: bool,
	) -> Dict[str, List[str]]:
		return _build_textrank_tag_index(
			files=files,
			target_root=target_root,
			tag_count=tag_count,
			max_unique_tags=max_unique_tags,
			verbose=verbose,
		)


class KeyBertTagExtractor:
	name = 'keybert'

	def build_index(
		self,
		files: List[Path],
		target_root: Path,
		tag_count: int,
		max_unique_tags: int,
		verbose: bool,
	) -> Dict[str, List[str]]:
		return _build_keybert_tag_index(
			files=files,
			target_root=target_root,
			tag_count=tag_count,
			max_unique_tags=max_unique_tags,
			verbose=verbose,
		)


_TAG_EXTRACTORS: Dict[str, TagExtractor] = {
	'tfidf': TfidfTagExtractor(),
	'textrank': TextRankTagExtractor(),
	'keybert': KeyBertTagExtractor(),
}


def _get_tag_extractor(method: str) -> Optional[TagExtractor]:
	m = (method or 'tfidf').lower().strip()
	if m in {'none', 'off', 'false', '0'}:
		return None
	return _TAG_EXTRACTORS.get(m)


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

	if verbose:
		print(f"[git] Building datetime index for {len(interest_paths)} paths")
	date_kind_norm = (date_kind or 'author').lower()
	fmt = '%at' if date_kind_norm == 'author' else '%ct'
	marker = '__TS__'
	# Only scan Markdown notes (recursive). This avoids walking unrelated files.
	md_pathspec = ':(glob)**/*.md'
	cmd = [
		'git',
		'-C', str(repo_dir),
		'-c', 'core.quotepath=false',
		'--no-pager',
		'log',
		'--name-status',
		'--diff-filter=AMDR',
		f'--format={marker}%{fmt[1:]}',
		'--',
		md_pathspec,
	]

	if verbose:
		print(f"[git] Running git command: {' '.join(cmd)}")

	# Avoid streaming huge stdout over pipes (can block/timeout over SSH). Dump
	# stdout to a temp file first, then parse it line-by-line.
	out_path: Optional[str] = None
	cp: Optional[subprocess.CompletedProcess[str]] = None

	# Map historical (older) names -> final (current) name we attribute times to.
	back_trace: Dict[str, str] = {}
	updated: Dict[str, int] = {}
	created: Dict[str, int] = {}
	done: Set[str] = set()
	current_ts: Optional[int] = None
	progress = ProgressPrinter(enabled=verbose, prefix='[git] scan')
	total_lines = 0

	try:
		with tempfile.NamedTemporaryFile(prefix='git-log-', suffix='.txt', delete=False, mode='w', encoding='utf-8') as fp:
			out_path = fp.name
			try:
				cp = subprocess.run(
					cmd,
					check=False,
					stdout=fp,
					stderr=subprocess.PIPE,
					text=True,
				)
			except FileNotFoundError:
				raise RuntimeError("未找到 git 命令，请先安装 git")

		if cp is None:
			return {}
		if cp.returncode != 0:
			err = (cp.stderr or '').strip()
			if verbose and err:
				print(f"[git] stderr: {err}")
			return {}

		if out_path is None:
			return {}

		# Progress: use processed line count / total line count.
		# Only compute total_lines when verbose to avoid an extra full pass.
		with open(out_path, 'r', encoding='utf-8', errors='replace') as f_total:
			total_lines = sum(1 for _ in f_total)

		with open(out_path, 'r', encoding='utf-8', errors='replace') as f:
			for line_no, line in enumerate(f, start=1):
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
				if len(parts) < 2:
					continue
				status = parts[0]
				# Rename: Rxxx\told\tnew
				if status.startswith('R') and len(parts) >= 3:
					old_name = parts[1]
					new_name = parts[2]
					# new_name感兴趣或者回溯找到感兴趣的path则记录
					if new_name in interest_paths:
						final = new_name
					elif back_trace.get(new_name) and back_trace.get(new_name) in interest_paths:
						final = back_trace.get(new_name)
					else:
						continue

					back_trace[old_name] = final
					updated.setdefault(final,current_ts)
					created[final] = current_ts
					continue


				path = parts[1]
				if path in interest_paths:
					final = path
				elif back_trace.get(path) and back_trace.get(path) in interest_paths:
					final = back_trace.get(path)
				else:
					continue

				updated.setdefault(final, current_ts)
				created[final] = current_ts
				# Throttle progress updates to reduce TTY overhead.
				progress.update(line_no, total_lines)
	finally:
		if out_path:
			try:
				Path(out_path).unlink(missing_ok=True)
			except Exception:
				pass

	result: Dict[str, Tuple[int, int]] = {}
	for k in interest_paths:
		c = created.get(k)
		u = updated.get(k)
		if c is not None and u is not None:
			result[k] = (c, u)
	# Mark progress completed (even if we early-stopped).
	progress.close(total_lines)
	return result


def _build_front_matter(
	title: str,
	created_epoch_seconds: int,
	updated_epoch_seconds: int,
	categories,
	cover_url: str,
	tags,
) -> str:
	title_json = json.dumps(title, ensure_ascii=False)
	tags_yaml = _yaml_list_inline_or_block(tags)
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
		+ (f"tags: {tags_yaml}\n" if tags_yaml == '[]' else f"tags:{tags_yaml}\n")
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
	tag_count: int
	tag_budget: int
	tag_method: str
	raw_wrap: str
	escape_curly: bool
	verbose: bool
	timestamp: Optional[int]
	date_kind: str
	git_batch: bool
	require_git_history: bool
	_time_cache: Dict[str, Tuple[int, int]]
	_tags_by_path: Dict[str, List[str]]


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

	# Tags are precomputed from full corpus TF-IDF (global IDF) in process_directory.
	tags: List[str] = []
	if cfg._tags_by_path:
		tags = cfg._tags_by_path.get(rel_to_target, [])

	first_img = _extract_first_image_url(body)
	cover_url = first_img if (first_img and _local_image_exists(cfg.repo_root, path, first_img)) else _default_cover_url(cfg.repo_root, rel_to_target)

	front_matter = _build_front_matter(
		title=title,
		created_epoch_seconds=created_epoch,
		updated_epoch_seconds=updated_epoch,
		categories=categories,
		cover_url=cover_url,
		tags=tags,
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

	# Build tag index once.
	if cfg.tag_count > 0 and files:
		extractor = _get_tag_extractor(cfg.tag_method)
		if extractor is not None:
			cfg._tags_by_path.update(
				extractor.build_index(
					files=files,
					target_root=cfg.target_dir,
					tag_count=int(cfg.tag_count),
					max_unique_tags=int(cfg.tag_budget),
					verbose=cfg.verbose,
				)
			)

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

	progress = ProgressPrinter(enabled=cfg.verbose, prefix='[process]')

	count = 0
	for i, p in enumerate(files, start=1):
		if process_file(cfg, p):
			count += 1
			# if cfg.verbose:
			# 	print(f"[ok] {p.relative_to(cfg.target_dir).as_posix()}")
		progress.update(i, total)
	progress.close(total)

	print(f"processed: {count} files, target={cfg.target_dir}")
	return 0


def main(argv=None) -> int:
	parser = argparse.ArgumentParser(
		description="统一处理 Hexo source/_posts 下的 Markdown：生成最小 front-matter，并可选 raw-wrap/花括号转义"
	)
	parser.add_argument('--target', default='source/_posts', help='目标目录（默认：source/_posts）')
	parser.add_argument('--notes', default=None, help='notes 仓库目录（默认：自动推断为 <repo_root>/notes）')
	parser.add_argument('--image-root', default='/note_image', help='图片 URL 根路径（默认：/note_image）')
	parser.add_argument('--tag-count', type=int, default=3, help='每篇文章提取标签数量（默认：3）')
	parser.add_argument('--tag-budget', type=int, default=100, help='全局唯一标签总量上限（默认：100）')
	parser.add_argument(
		'--tag-method',
		choices=['tfidf', 'textrank', 'keybert', 'none'],
		default='tfidf',
		help='标签提取方法：tfidf(默认) / textrank(jieba+textrank4zh) / keybert(sentence-transformers) / none(禁用)',
	)
	parser.add_argument('--raw-wrap', choices=['auto', 'always', 'never'], default='auto', help='遇到模板语法时用 Nunjucks raw 包裹正文（默认：auto）')
	parser.add_argument('--escape-curly', choices=['true', 'false'], default='true', help='是否转义 {{ }} 以避免 Nunjucks 解析（默认：true）')
	parser.add_argument('--git-date', choices=['author', 'committer'], default='author', help='使用 git 的 author 时间或 committer 时间（默认：author）')
	parser.add_argument('--git-batch', choices=['true', 'false'], default='true', help='是否用一次 git log 构建时间索引（默认：true）')
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
		tag_count=int(args.tag_count),
		tag_budget=int(args.tag_budget),
		tag_method=str(args.tag_method),
		raw_wrap=str(args.raw_wrap),
		escape_curly=str(args.escape_curly).lower() == 'true',
		verbose=bool(args.verbose),
		timestamp=args.timestamp,
		date_kind=str(args.git_date),
		git_batch=str(args.git_batch).lower() == 'true',
		require_git_history=str(args.require_git_history).lower() == 'true',
		_time_cache={},
		_tags_by_path={},
	)
	return process_directory(cfg)


if __name__ == '__main__':
	raise SystemExit(main())
