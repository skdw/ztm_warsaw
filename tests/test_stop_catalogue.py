"""The shared stops catalogue: what it keeps, for how long, and what it does when the City fails."""

from __future__ import annotations

import asyncio
import time

import pytest

from custom_components.ztm_warsaw.client import StopCatalogue, ZTMStopClient

UUID = "11111111-2222-4333-8444-555555555555"  # synthetic


def rec(zespol, slupek, **more):
    """A stop record in the shape the API returns (a `values` list of key/value pairs); the pole is left out when `slupek` is None."""
    values = [{"key": "zespol", "value": zespol}]
    if slupek is not None:
        values.append({"key": "slupek", "value": slupek})
    values += [{"key": k, "value": v} for k, v in more.items()]
    return {"values": values}


class Stub:
    """Stands in for a client: counts the downloads and answers with ``rows``."""

    uses_token = False
    retired = False

    def __init__(self, rows):
        """Keep the rows to answer with and start the download count at zero."""
        self.rows, self.downloads = rows, 0

    async def _stop_info_rows(self):
        """Count a download and return the rows, as the real client would after fetching them."""
        self.downloads += 1
        return self.rows


ROWS = [rec("7009", "01", nazwa_zespolu="Dom"), rec("7009", "02", nazwa_zespolu="Dom 2"), rec("1000", "05", nazwa_zespolu="X")]


async def test_one_download_serves_everyone_and_the_pole_rule_is_the_old_one():
    catalogue, client = StopCatalogue(), Stub(ROWS)
    assert await catalogue.find(client, "7009", "02") == (True, {"nazwa_zespolu": "Dom 2"})
    assert await catalogue.find(client, "7009", "99") == (True, {"nazwa_zespolu": "Dom"}), "the first pole of the stop"
    assert await catalogue.find(client, "0000", "01") == (True, None), "a stop that is not there"
    assert client.downloads == 1


async def test_the_first_record_of_a_pole_wins_and_a_pole_without_fields_is_itself():
    catalogue = StopCatalogue()
    rows = [rec("1", "01", nazwa_zespolu="first"), rec("1", "01", nazwa_zespolu="second"), rec("1", "02"), rec("2", None, nazwa_zespolu="no pole")]
    client = Stub(rows)
    assert (await catalogue.find(client, "1", "01"))[1] == {"nazwa_zespolu": "first"}
    assert (await catalogue.find(client, "1", "02"))[1] == {}, "an exact pole with nothing to say is not the first pole"
    assert (await catalogue.find(client, "2", "01"))[1] == {"nazwa_zespolu": "no pole"}


async def test_the_copy_it_returns_cannot_change_the_index():
    catalogue, client = StopCatalogue(), Stub(ROWS)
    info = (await catalogue.find(client, "7009", "01"))[1]
    info["stop_name"] = "changed"
    assert (await catalogue.find(client, "7009", "01"))[1] == {"nazwa_zespolu": "Dom"}


@pytest.mark.parametrize("rows", [None, [], [{"junk": 1}], ["x"]])
async def test_nothing_readable_is_not_kept_and_is_not_asked_again_for_a_minute(rows, monkeypatch):
    catalogue, client = StopCatalogue(), Stub(rows)
    assert await catalogue.find(client, "7009", "01") == (False, None)
    assert await catalogue.find(client, "7009", "01") == (None, None), "not asked: the failure is fresh"
    assert client.downloads == 1
    client.rows = ROWS
    now = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: now + 61)
    assert await catalogue.find(client, "7009", "01") == (True, {"nazwa_zespolu": "Dom"})


async def test_the_minute_counts_from_the_end_of_the_download(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])

    class Slow(Stub):
        """A client whose download takes 42 seconds of the fake clock and then fails."""
        async def _stop_info_rows(self):
            """Move the fake clock 42 seconds and fail (return None)."""
            clock[0] += 42  # a download that takes 42 s and fails
            return None

    catalogue, client = StopCatalogue(), Slow(None)
    await catalogue.find(client, "7009", "01")
    clock[0] += 30
    assert await catalogue.find(client, "7009", "01") == (None, None), "30 s after the failure, not 72 s after the start"


async def test_the_index_is_good_for_a_day_and_per_kind_of_host(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    catalogue, legacy, token = StopCatalogue(), Stub(ROWS), Stub(ROWS)
    token.uses_token = True
    await catalogue.find(legacy, "7009", "01")
    await catalogue.find(token, "7009", "01")
    assert (legacy.downloads, token.downloads) == (1, 1), "each host answers its own way"
    clock[0] += 86399
    await catalogue.find(legacy, "7009", "01")
    assert legacy.downloads == 1
    clock[0] += 2
    await catalogue.find(legacy, "7009", "01")
    assert legacy.downloads == 2


async def test_a_client_that_is_alone_keeps_nothing():
    client = Stub(ROWS)
    alone = StopCatalogue(ttl=0)
    await alone.find(client, "7009", "01")
    await alone.find(client, "7009", "01")
    assert client.downloads == 2


async def test_a_skipped_catalogue_is_not_a_failed_attempt_of_the_entry():
    class Skipped:
        """A catalogue that did not look (the answer a fresh failure gives), so there is no result either way."""
        async def find(self, *_):
            """Answer (None, None): the catalogue did not look, so nothing is known."""
            return None, None

    client = ZTMStopClient(None, UUID, "7009", "01", "151", catalogue=Skipped())
    assert await client.get_stop_name() is None
    assert client._stop_info_attempts == 0
    assert client._stop_info_next_retry is None


async def test_a_slow_host_does_not_hold_up_the_other_one():
    release = asyncio.Event()

    class Blocked(Stub):
        """A client whose download waits until the test sets `release`."""
        async def _stop_info_rows(self):
            """Wait for `release`, then return the rows (without counting the download)."""
            await release.wait()
            return self.rows

    catalogue, slow, fast = StopCatalogue(), Blocked(ROWS), Stub(ROWS)
    fast.uses_token = True
    first = asyncio.ensure_future(catalogue.find(slow, "7009", "01"))
    await asyncio.sleep(0)
    assert await asyncio.wait_for(catalogue.find(fast, "7009", "01"), 1) == (True, {"nazwa_zespolu": "Dom"})
    assert not first.done()
    release.set()
    assert (await first)[0] is True


async def test_two_entries_of_one_host_still_wait_for_one_download():
    release = asyncio.Event()

    class Blocked(Stub):
        """A client whose download counts itself and then waits until the test sets `release`."""
        async def _stop_info_rows(self):
            """Count the download, wait for `release`, then return the rows."""
            self.downloads += 1
            await release.wait()
            return self.rows

    catalogue, client = StopCatalogue(), Blocked(ROWS)
    a = asyncio.ensure_future(catalogue.find(client, "7009", "01"))
    b = asyncio.ensure_future(catalogue.find(client, "7009", "02"))
    await asyncio.sleep(0)
    release.set()
    assert [(await a)[0], (await b)[0]] == [True, True]
    assert client.downloads == 1
