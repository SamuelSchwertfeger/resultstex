import json

from pathlib import Path

import pytest

import resultstex as r


def test_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / 'results.json'
    r.record('auc_xgb', 0.91312, fmt='.3f', path=str(p))
    r.record('acc', 0.913, fmt='.1%', note='n', path=str(p))
    r.record('lat', 12, unit='ms', path=str(p))
    d = json.loads(p.read_text())
    assert d['auc_xgb']['text'] == '0.913'
    assert d['auc_xgb']['value'] == 0.91312
    assert d['acc']['text'] == '91.3%'
    assert d['lat']['text'] == '12 ms'
    assert d['auc_xgb']['script'].endswith('test_resultstex.py')
    out = tmp_path / 'results.tex'
    r.build(str(p), str(out))
    t = out.read_text(encoding='utf-8')
    assert 'GENERATED' in t
    assert r'\resultdef{auc_xgb}{0.913}' in t
    assert r'\resultdef{acc}{91.3\%}' in t
    tex = tmp_path / 'p.tex'
    tex.write_text('\\begin{document}\nAUC \\result{auc_xgb}.\n\\end{document}\n')
    assert r.audit(str(tex), str(p)) == ([], [])


def test_missing_key(tmp_path: Path) -> None:
    p = tmp_path / 'results.json'
    r.record('a', 1, path=str(p))
    tex = tmp_path / 'p.tex'
    tex.write_text('\\begin{document}\\result{a} \\result{nope}\\end{document}')
    assert r.audit(str(tex), str(p))[0] == ['nope']
    assert r.main(['audit', str(tex), '--results', str(p)]) == 1


def test_hardcoded(tmp_path: Path) -> None:
    tex = tmp_path / 'p.tex'
    tex.write_text(
        '\\documentclass{article}\n\\newcommand{\\x}{0.777}\n\\begin{document}\n'
        '% 0.888 in comment\n'
        'Ours gets 0.913 AUC.\n'  # 5 flagged
        'Acc is 91\\% here.\n'  # 6 flagged
        'We have 12,345 rows.\n'  # 7 flagged
        'Vaswani~\\cite{v2017,x1234} in 2017, Section 3, Fig.~\\ref{f:1.5}.\n'
        '\\includegraphics[width=0.5\\textwidth]{fig10.5.png}\n'
        '\\vspace{-2.5em}\n'
        '\\end{document}\n'
    )
    missing, hard = r.audit(str(tex), str(tmp_path / 'none.json'))
    assert [ln for ln, _ in hard] == [5, 6, 7]
    assert r.main(['audit', str(tex)]) == 0
    assert r.main(['audit', str(tex), '--strict']) == 1


@pytest.mark.parametrize('k', ['1a', 'a-b', '', 'a b', '_x'])
def test_bad_key(tmp_path: Path, k: str) -> None:
    with pytest.raises(ValueError):
        r.record(k, 1, path=str(tmp_path / 'r.json'))


BS = chr(92)


def test_audit_units_years_includes(tmp_path: Path) -> None:
    (tmp_path / 'sec.tex').write_text(f'Got 0.91{BS}footnote{{x}}.\n')
    (tmp_path / 'loop.tex').write_text(f'{BS}input{{main}}\n')
    tex = tmp_path / 'main.tex'
    tex.write_text(
        f'{BS}begin{{document}}\n'
        f'AUC 0.93{BS}pm 0.01.\n'  # 2 flagged
        f'Width 0.5{BS}textwidth and 3pt.\n'  # skipped
        'Year 2017 ok.\n'  # skipped
        'We used 2000 samples.\n'  # 5 flagged
        f'{BS}input{{sec}}\n{BS}input{{loop}}\n{BS}end{{document}}\n'
    )
    _, hard = r.audit(str(tex), str(tmp_path / 'none.json'))
    assert [ln for ln, _ in hard][:2] == [2, 5]
    assert any('[sec.tex]' in s for _, s in hard)


def test_record_numpy_like_and_cleanup(tmp_path: Path) -> None:
    class V:
        def item(self) -> int:
            return 5

    p = tmp_path / 'results.json'
    r.record('a', V(), path=str(p))
    assert json.loads(p.read_text())['a']['value'] == 5
    assert not list(tmp_path.glob('*.tmp'))


def test_ignore_comment(tmp_path: Path) -> None:
    tex = tmp_path / 'p.tex'
    lines = [
        f'{BS}begin{{document}}',
        'Fixed 0.913 here. % resultstex: ignore',
        'Flagged 0.914 here.',
        f'Escaped 0.915 {BS}% resultstex: ignore',
        f'{BS}end{{document}}',
    ]
    tex.write_text('\n'.join(lines) + '\n')
    _, hard = r.audit(str(tex), str(tmp_path / 'none.json'))
    assert [ln for ln, _ in hard] == [3, 4]


def test_cli_build(tmp_path: Path) -> None:
    p = tmp_path / 'results.json'
    r.record('a', 1.5, fmt='.2f', path=str(p))
    out = tmp_path / 'out.tex'
    assert r.main(['build', str(p), '-o', str(out)]) == 0
    assert r'\resultdef{a}{1.50}' in out.read_text(encoding='utf-8')


def test_generated_file_not_flagged(tmp_path: Path) -> None:
    p = tmp_path / 'results.json'
    r.record('a', 0.913, fmt='.3f', path=str(p))
    r.build(str(p), str(tmp_path / 'results.tex'))
    tex = tmp_path / 'p.tex'
    tex.write_text(f'{BS}begin{{document}}\n{BS}input{{results}}\n{BS}result{{a}}\n{BS}end{{document}}\n')
    assert r.audit(str(tex), str(p)) == ([], [])
