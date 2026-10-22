"""The stops of every line that ships with the integration, and the script that builds it."""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError

import pytest

from custom_components.ztm_warsaw import line_index

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_line_index.py"


@pytest.fixture
def builder():
    """The generator script as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location("build_line_index", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_shipped_index_is_a_list_of_numeric_stop_ids_per_line():
    data = json.loads((ROOT / "custom_components" / "ztm_warsaw" / "line_stops.json").read_text(encoding="utf-8"))
    date.fromisoformat(data["generated"])
    lines = data["lines"]
    assert len(lines) > 250, "the network has about 330 lines"
    assert all(ids and all(i.isdigit() for i in ids) for ids in lines.values())
    assert all(ids == sorted(ids, key=int) and len(set(ids)) == len(ids) for ids in lines.values()), "sorted, each stop once"


def test_lines_are_read_numbers_first_then_letters():
    assert sorted(["N31", "151", "S4", "9", "100"], key=line_index.line_order) == ["9", "100", "151", "N31", "S4"]


async def test_the_index_is_read_once_and_kept(hass, tmp_path, monkeypatch):
    path = tmp_path / "line_stops.json"
    path.write_text(json.dumps({"generated": "2026-10-22", "lines": {"151": ["7009", 3044]}}))
    monkeypatch.setattr(line_index, "INDEX_FILE", path)
    assert await line_index.async_line_stops(hass) == {"151": ["7009", "3044"]}
    path.unlink()
    assert await line_index.async_line_stops(hass) == {"151": ["7009", "3044"]}, "kept, not read again"


@pytest.mark.parametrize("content", [None, "not json", '{"lines": 5}', '{"lines": {"151": "7009"}}', "[]"])
async def test_an_index_that_cannot_be_read_is_none_and_the_setup_falls_back_to_the_numbers(hass, tmp_path, monkeypatch, content):
    path = tmp_path / "line_stops.json"
    if content is not None:
        path.write_text(content)
    monkeypatch.setattr(line_index, "INDEX_FILE", path)
    assert await line_index.async_line_stops(hass) is None


def test_the_script_turns_the_lines_at_each_pole_into_the_stops_of_each_line(builder):
    lines = builder.invert({("7009", "01"): ["151", "N25"], ("7009", "02"): ["151"], ("30", "01"): ["151"]})
    assert lines == {"151": ["30", "7009"], "N25": ["7009"]}, "a stop once however many poles, sorted by number"
    assert builder.render(lines, date(2026, 10, 22)) == '{"generated":"2026-10-22","lines":{"151":["30","7009"],"N25":["7009"]}}\n'


def test_the_script_reads_a_record_and_the_lines_of_a_pole(builder, monkeypatch):
    assert builder.values_of({"values": [{"key": "linia", "value": "151"}, {"key": "x", "value": "y"}]}) == {"linia": "151", "x": "y"}
    monkeypatch.setattr(builder, "call", lambda token, action, body=None: [{"values": [{"key": "linia", "value": "151"}]}, {"values": []}])
    assert builder.lines_at("t", ("7009", "01")) == ["151"]
    monkeypatch.setattr(builder, "call", lambda token, action, body=None: None)
    assert builder.lines_at("t", ("7009", "01")) == []


def test_the_script_lists_the_poles_of_the_catalogue_or_stops(builder, monkeypatch):
    rows = [{"values": [{"key": "zespol", "value": "7009"}, {"key": "slupek", "value": "02"}]}, {"values": [{"key": "zespol", "value": "7009"}, {"key": "slupek", "value": "01"}]}, {"values": []}]
    monkeypatch.setattr(builder, "call", lambda token, action, body=None: rows)
    assert builder.poles_of("t") == [("7009", "01"), ("7009", "02")]
    monkeypatch.setattr(builder, "call", lambda token, action, body=None: None)
    with pytest.raises(SystemExit):
        builder.poles_of("t")


def test_the_script_builds_from_the_answers_of_every_pole(builder, monkeypatch):
    answers = {("1", "01"): ["10"], ("2", "01"): ["10", "20"]}
    monkeypatch.setattr(builder, "lines_at", lambda token, pole: answers[pole])
    assert builder.build("t", answers) == {"10": ["1", "2"], "20": ["2"]}


def test_the_script_refuses_to_write_a_file_when_the_city_did_not_answer(builder, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(builder, "TARGET", tmp_path / "out.json")
    monkeypatch.delenv("ZTM_LIVE_API_KEY", raising=False)
    assert builder.main() == 2
    monkeypatch.setenv("ZTM_LIVE_API_KEY", "synthetic-token")
    monkeypatch.setattr(builder, "poles_of", lambda token: [("1", "01")])
    monkeypatch.setattr(builder, "build", lambda token, poles: {"10": ["1"]})
    assert builder.main() == 1
    assert not (tmp_path / "out.json").exists()
    assert "synthetic-token" not in capsys.readouterr().out


def test_the_script_writes_the_file_when_enough_lines_came_back(builder, monkeypatch, tmp_path):
    target = tmp_path / "a" / "b" / "c" / "out.json"
    target.parent.mkdir(parents=True)
    monkeypatch.setattr(builder, "TARGET", target)
    monkeypatch.setenv("ZTM_LIVE_API_KEY", "synthetic-token")
    monkeypatch.setattr(builder, "poles_of", lambda token: [("1", "01")])
    monkeypatch.setattr(builder, "build", lambda token, poles: {str(n): ["1"] for n in range(120)})
    assert builder.main() == 0
    assert len(json.loads(target.read_text())["lines"]) == 120


def test_a_request_that_fails_is_retried_and_never_reports_the_token(builder, monkeypatch):
    calls = []

    def refuse(request, timeout):
        """A City that answers 502."""
        calls.append(request.get_header("Authorization"))
        raise HTTPError("https://example.invalid", 502, "bad gateway", {}, None)

    monkeypatch.setattr(builder, "urlopen", refuse)
    monkeypatch.setattr(builder.time, "sleep", lambda seconds: None)
    assert builder.call("synthetic-token", "x") is None
    assert len(calls) == builder.ATTEMPTS
    monkeypatch.setattr(builder, "urlopen", lambda request, timeout: (_ for _ in ()).throw(HTTPError("u", 500, "no lines", {}, None)))
    assert builder.call("synthetic-token", "x") is None
