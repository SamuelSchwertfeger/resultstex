"""resultstex: record numbers from code, emit LaTeX macros, audit papers."""

import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

from typing import Any

KEY_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')


def _git_commit(d: str) -> str | None:
    try:
        r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=d, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def _json_default(o: Any) -> Any:
    item = getattr(o, 'item', None)
    return item() if callable(item) else str(o)


def record(
    key: str,
    value: Any,
    fmt: str | None = None,
    unit: str | None = None,
    note: str | None = None,
    path: str = 'results.json',
) -> None:
    """Store `value` under `key` in the JSON file `path` (created if missing)."""
    if not isinstance(key, str) or not KEY_RE.match(key):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError(f'invalid key {key!r}: must match {KEY_RE.pattern}')
    text = format(value, fmt) if fmt else str(value)
    if unit:
        text += unit if unit == '%' else f' {unit}'
    script = pathlib.Path(sys._getframe(1).f_code.co_filename).absolute().as_posix()  # pyright: ignore[reportPrivateUsage]
    data: dict[str, Any] = {}
    if pathlib.Path(path).exists():
        with pathlib.Path(path).open(encoding='utf-8') as f:
            data = json.load(f)
    data[key] = {
        'value': value,
        'text': text,
        'note': note,
        'script': script,
        'git_commit': _git_commit(str(pathlib.Path(script).parent)),
        'timestamp': datetime.datetime.now().isoformat(timespec='seconds'),
    }
    d = str(pathlib.Path(path).absolute().parent)
    fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True, default=_json_default)
        pathlib.Path(tmp).replace(path)
    except BaseException:
        if pathlib.Path(tmp).exists():
            pathlib.Path(tmp).unlink()
        raise


_ESC = {
    '\\': r'\textbackslash{}',
    '%': r'\%',
    '#': r'\#',
    '&': r'\&',
    '_': r'\_',
    '$': r'\$',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\textasciicircum{}',
}


def _esc(s: str) -> str:
    return ''.join(_ESC.get(c, c) for c in s)


def build(results: str = 'results.json', out: str = 'results.tex') -> None:
    """Write the LaTeX macro file `out` from the JSON file `results`."""
    with pathlib.Path(results).open(encoding='utf-8') as f:
        data = json.load(f)
    lines = ['% GENERATED \u2014 do not edit. Source: ' + pathlib.Path(results).name]
    lines += [f'\\resultdef{{{k}}}{{{_esc(v["text"])}}}' for k, v in sorted(data.items())]
    with pathlib.Path(out).open('w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def _blank(m: re.Match[str]) -> str:
    return re.sub(r'[^\n]', ' ', m.group())


_COMMENT = r'(?<!\\)%.*'
# A line carrying this comment is skipped by the hard-coded number check.
_IGNORE_MARK = re.compile(r'(?<!\\)%\s*resultstex:\s*ignore\b')
_IGNORE = [
    r'\\(?:cite\w*|(?:auto|c|C|eq|page|v)?ref|label|eqref|includegraphics|input|include'
    r'|usepackage|bibliography\w*|url|href)\*?(?:\[[^\]]*\])*\{[^}]*\}',
    r'\\result\{[^}]*\}',
    r'[-+]?\d*\.?\d+\s*(?:pt|cm|mm|in|em|ex|\\textwidth|\\linewidth|\\columnwidth|\\textheight)(?![a-zA-Z])',  # lengths
]
_NUM = re.compile(r'(?<![\w.\\])(\d+(?:,\d{3})*\.\d+|\d+(?:\.\d+)?\\?%|\d{1,3}(?:,\d{3})+|\d{3,})(?![\w])')


_YEAR_COUNT = re.compile(r'\s+(?:samples|instances|examples|participants)\b', re.I)
_INCLUDE = re.compile(r'\\(?:input|include)\{([^}]*)\}')


def _audit_file(tex: str, seen: set[str]) -> tuple[list[str], list[tuple[int, str]]]:
    """-> (used_keys, hard) for one tex file plus files it inputs/includes (cycle-guarded)."""
    seen.add(str(pathlib.Path(tex).absolute()))
    with pathlib.Path(tex).open(encoding='utf-8') as f:
        src = f.read()
    if src.startswith('% GENERATED'):  # the file written by `build`: values come from code by definition
        return [], []
    ignored = {i for i, line in enumerate(src.split('\n'), 1) if _IGNORE_MARK.search(line)}
    src = re.sub(_COMMENT, _blank, src)
    used = re.findall(r'\\result\{([^}]*)\}', src)
    hard: list[tuple[int, str]] = []
    for name in _INCLUDE.findall(src):
        sub = str(pathlib.Path(tex).absolute().parent / name.strip())
        if not pathlib.Path(sub).suffix:
            sub += '.tex'
        if str(pathlib.Path(sub).absolute()) in seen or not pathlib.Path(sub).exists():
            continue
        u, h = _audit_file(sub, seen)
        used += u
        hard += [(ln, f'[{pathlib.Path(sub).name}] {snip}') for ln, snip in h]
    m = re.search(r'\\begin\{document\}', src)
    if m:  # blank the preamble
        src = re.sub(r'[^\n]', ' ', src[: m.end()]) + src[m.end() :]
    for p in _IGNORE:
        src = re.sub(p, _blank, src)
    own: list[tuple[int, str]] = []
    for i, line in enumerate(src.split('\n'), 1):
        if i in ignored:
            continue
        for n in _NUM.finditer(line):
            if re.fullmatch(r'(19|20)\d\d', n.group(1)) and not _YEAR_COUNT.match(line, n.end()):
                continue
            own.append((i, line.strip()))
            break
    return used, own + hard


def audit(tex: str, results: str = 'results.json') -> tuple[list[str], list[tuple[int, str]]]:
    """Return (missing_keys, [(line, snippet)])."""
    used, hard = _audit_file(tex, set())
    keys: dict[str, Any] = {}
    if pathlib.Path(results).exists():
        with pathlib.Path(results).open(encoding='utf-8') as f:
            keys = json.load(f)
    missing = sorted({k for k in used if k not in keys})
    return missing, hard


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog='resultstex')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('results', nargs='?', default='results.json')
    b.add_argument('-o', '--out', default='results.tex')
    a = sub.add_parser('audit')
    a.add_argument('tex')
    a.add_argument('--results', default='results.json')
    a.add_argument('--strict', action='store_true')
    args = ap.parse_args(argv)
    if args.cmd == 'build':
        build(args.results, args.out)
        return 0
    missing, hard = audit(args.tex, args.results)
    for k in missing:
        print(f'MISSING: \\result{{{k}}} not in {args.results}')
    for ln, snip in hard:
        print(f'WARNING {args.tex}:{ln}: hard-coded number: {snip}')
    return 1 if missing or (args.strict and hard) else 0


if __name__ == '__main__':
    sys.exit(main())
