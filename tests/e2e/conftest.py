"""Fixtures for the in-process end-to-end suite.

Layering (each fixture lists what it needs, so the order below is the setup order):

    clock        freezegun, started BEFORE hass so the event loop's monotonic clock is consistent
    hass         the real Home Assistant core from pytest-homeassistant-custom-component
    fake_city    two aiohttp servers on 127.0.0.1 (legacy GET + new POST contract)
    env          bundle with helpers: add entries (config flow or restored), move time, read states
"""

from __future__ import annotations


import asyncio
import os
import time as time_module
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import freezegun
import pytest
from freezegun import api as freezegun_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util.async_ import get_scheduled_timer_handles
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.patch_time import HAFakeDatetime

from custom_components.ztm_warsaw import client as client_module
from custom_components.ztm_warsaw.const import DOMAIN

from .fake_city import DEFAULT_KEY, SMALL_CATALOGUE, WARSAW, FakeCity, HarnessError, route_to_fake_city

_FIRE_MARGIN = 0.6  # seconds: HA spreads coordinator refreshes over 0.05-0.50 s after the interval
DEFAULT_START = "2026-10-16 12:00:00+02:00"  # a Friday noon, the day the fixtures were captured


def at(when: str | datetime) -> datetime:
    """Parse '2026-10-17 02:31' as WARSAW wall-clock time (or pass a datetime through)."""
    if isinstance(when, datetime):
        return when if when.tzinfo else when.replace(tzinfo=WARSAW)
    return datetime.fromisoformat(when).replace(tzinfo=WARSAW) if "+" not in when[10:] else datetime.fromisoformat(when)


# ----------------------------------------------------------------------------- time
@pytest.fixture
def process_tz() -> Iterator[Callable[[str], None]]:
    """Set the *process* time zone (what ``datetime.astimezone()`` with no argument uses).

    Default for the whole suite is Europe/Warsaw (how the maintainer runs HA); tests that show the
    process-timezone bug call ``process_tz("UTC")``.
    """
    previous = os.environ.get("TZ")

    def _set(name: str) -> None:
        """Switch the process time zone to ``name`` and make the C library notice."""
        os.environ["TZ"] = name
        time_module.tzset()

    _set("Europe/Warsaw")
    yield _set
    if previous is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = previous
    time_module.tzset()


@pytest.fixture
def clock(request, process_tz) -> Iterator[Any]:
    """freezegun, started first. ``@pytest.mark.start("2026-10-17 02:31")`` picks the start instant."""
    marker = request.node.get_closest_marker("start")
    start = at(marker.args[0] if marker else DEFAULT_START)
    # freezegun's FakeDatetime.astimezone(None) uses dateutil's DST-aware tzlocal(); the real
    # datetime.astimezone(None) yields a FIXED offset. Production sees the real one, so restore it
    # or the fixed-offset DST bug (fixed-offset labels) becomes invisible under a plain freezer.
    real_astimezone = freezegun_api.real_datetime.astimezone

    def production_astimezone(self, tz=None):
        """``astimezone`` as production sees it: the real fixed-offset behaviour, with the result wrapped back into freezegun's fake datetime."""
        return freezegun_api.datetime_to_fakedatetime(real_astimezone(self, tz))

    patched = []
    for cls in {HAFakeDatetime, HAFakeDatetime.__mro__[1]}:
        patched.append((cls, cls.__dict__.get("astimezone")))
        cls.astimezone = production_astimezone
    with freezegun.freeze_time(start) as frozen:
        yield frozen
    for cls, old in patched:
        if old is None:
            del cls.astimezone
        else:
            cls.astimezone = old


# ----------------------------------------------------------------------------- fake city
@pytest.fixture(autouse=True)
def _keep_1_1_x_entries(request) -> Iterator[None]:
    """The tests that add a 1.1.x entry (one stop) test that shape; the conversion into lines is not run for them unless
    the test is marked ``migrate``."""
    if request.node.get_closest_marker("migrate"):
        yield
        return
    with patch("custom_components.ztm_warsaw.async_migrate_to_lines", AsyncMock()):
        yield


@pytest.fixture
def city_options(request) -> dict[str, Any]:
    """The keyword arguments of ``@pytest.mark.city(...)`` on the test (empty without the mark), passed on to the fake city."""
    marker = request.node.get_closest_marker("city")
    return dict(marker.kwargs) if marker else {}


@pytest.fixture
async def fake_city(clock, socket_enabled, city_options) -> AsyncIterator[FakeCity]:
    """A started fake City of Warsaw with the integration's HTTP routed to it; fails the test if the code under test tried to reach anything else."""
    city = FakeCity(**{"catalogue_bytes": SMALL_CATALOGUE, **city_options})
    await city.start()
    try:
        with route_to_fake_city(city):
            yield city
        assert not city.blocked, f"code under test tried to leave the sandbox: {city.blocked}"
    finally:
        await city.stop()


@dataclass
class Sleeps:
    """Delays the integration asked for with asyncio.sleep (they are skipped, not waited)."""

    requested: list[float] = field(default_factory=list)


@pytest.fixture
def sleeps(monkeypatch) -> Sleeps:
    """Make the integration's retry back-off instant WITHOUT touching asyncio.sleep globally.

    ``client.py`` does ``import asyncio`` (the config flow goes through it); replacing that module attribute
    inside it with a proxy changes nothing for Home Assistant, aiohttp or the fake server.
    """
    rec = Sleeps()

    class _AsyncioProxy:
        """Stands in for the ``asyncio`` module inside the client: ``sleep`` is recorded and skipped, everything else is the real thing."""
        async def sleep(self, delay, *args, **kwargs):
            """Record the requested delay and return at once, so back-off sleeps cost no time."""
            rec.requested.append(delay)
            await asyncio.sleep(0)

        def __getattr__(self, name):
            return getattr(asyncio, name)

    proxy = _AsyncioProxy()
    monkeypatch.setattr(client_module, "asyncio", proxy)
    return rec


# ----------------------------------------------------------------------------- env
class Env:
    """What a test needs, in one object."""

    def __init__(self, hass: HomeAssistant, clock: Any, city: FakeCity, sleeps: Sleeps) -> None:
        """Bundle the pieces of one test: the Home Assistant instance, the frozen clock, the fake city and the recorded sleeps."""
        self.hass = hass
        self.clock = clock
        self.city = city
        self.sleeps = sleeps

    # -- time -------------------------------------------------------------------------
    async def settle(self) -> None:
        """Let everything that is already scheduled or running finish, background tasks included."""
        await self.hass.async_block_till_done(wait_background_tasks=True)

    def move_to(self, when: str | datetime) -> None:
        """Jump the clock WITHOUT firing anything (pure passage of time)."""
        self.clock.move_to(at(when))

    async def run_to(self, to: str | datetime, *, max_steps: int = 5000) -> int:
        """Let simulated time flow to ``to``: jump from scheduled timer to scheduled timer.

        Every timer that falls due on the way is fired at (just after) its own instant, exactly as
        in a real run, so the integration's hourly refresh and its per-departure wake-ups keep their
        real phase. Nothing is evaluated "in between" unless a timer asks for it. Returns the number
        of steps taken.
        """
        # UTC on purpose: aware datetimes that share one tzinfo (WARSAW) subtract and add as WALL-CLOCK time,
        # which skips or doubles the repeated hour on a DST day.
        target = at(to).astimezone(timezone.utc)
        loop = self.hass.loop
        steps = 0
        while True:
            remaining = (target - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                break
            due = [
                h.when() - loop.time()
                for h in get_scheduled_timer_handles(loop)
                if not h.cancelled() and h.when() - loop.time() > 0
            ]
            nxt = min(due) + _FIRE_MARGIN if due else None
            step = remaining if nxt is None or nxt > remaining else nxt
            self.clock.tick(timedelta(seconds=step))
            async_fire_time_changed(self.hass)
            await self.settle()
            steps += 1
            if steps > max_steps:
                raise HarnessError("time simulation did not converge (timer storm?)")
        return steps

    async def advance(self, **delta: float) -> int:
        """Like :meth:`run_to` but relative: ``await env.advance(hours=1)``."""
        return await self.run_to(datetime.now(timezone.utc) + timedelta(**delta))

    @property
    def now(self) -> datetime:
        """The current (frozen) time in Warsaw."""
        return datetime.now(WARSAW)

    async def drive_timeouts(self, task: asyncio.Future, *, tick: float = 21.0, max_requests: int = 6) -> Any:
        """Finish ``task`` while the fake city never answers: let the frozen clock run past the client timeout.

        Each round waits until one more request is stuck in the fake, then advances the clock beyond the
        client's 20 s limit (and over the back-off sleep, which ``sleeps`` already skips). Returns the task's
        result. Real wall time spent: milliseconds.
        """
        for hung in range(1, max_requests + 1):
            waiter = asyncio.ensure_future(self.city.wait_hung(hung))
            await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
            if task.done():
                waiter.cancel()
                break
            await waiter
            self.clock.tick(timedelta(seconds=tick))
            for _ in range(200):  # let cancellation, retry and the next request propagate
                await asyncio.sleep(0)
        if not task.done():
            raise HarnessError(f"still waiting after {max_requests} stuck requests")
        return await task

    async def hourly_tick(self, *, hanging: bool = False) -> None:
        """Move one hour (plus a second) forward, fire the coordinator's refresh, wait for it to finish.

        With ``hanging=True`` the city never answers: the client's timeouts are driven by the frozen clock.
        """
        self.clock.tick(timedelta(hours=1, seconds=1))
        async_fire_time_changed(self.hass)
        if hanging:
            await self.drive_timeouts(asyncio.ensure_future(self.settle()))
        else:
            await self.settle()

    # -- entries ----------------------------------------------------------------------
    async def submit_flow(
        self,
        *,
        line: str = "151",
        stop_id: int | str = 7009,
        stop_nr: str = "01",
        api_key: str = DEFAULT_KEY,
    ) -> dict:
        """Run the user step of the real config flow once and return the raw flow result."""
        flow = self.hass.config_entries.flow
        result = await flow.async_init(DOMAIN, context={"source": "user"})
        if result["type"] != "form":
            raise HarnessError(f"the config flow did not open a form: {result}")
        result = await flow.async_configure(  # "I know the numbers": the form of the numbers, as the setup dialog of 1.1.x was
            result["flow_id"], {"api_key": api_key, "manual": True}
        )
        if result["type"] == "form" and result["step_id"] == "manual":
            result = await flow.async_configure(
                result["flow_id"],
                {
                    "api_key": api_key,
                    "busstop_id": stop_id,
                    "busstop_nr": stop_nr,
                    "line": line,
                },
            )
        await self.settle()
        return result

    async def manual_form(self, *, api_key: str = DEFAULT_KEY) -> dict:
        """The form of the numbers of the setup dialog ("I know the numbers" ticked on the first screen)."""
        flow = self.hass.config_entries.flow
        result = await flow.async_init(DOMAIN, context={"source": "user"})
        return await flow.async_configure(result["flow_id"], {"api_key": api_key, "manual": True})

    async def add_stop_form(self, entry: ConfigEntry, *, manual: bool = True) -> dict:
        """The form of *Add stop* on a line (the form of the numbers when ``manual``, else the first screen)."""
        manager = self.hass.config_entries.subentries
        form = await manager.async_init((entry.entry_id, "stop"), context={"source": "user"})
        if manual and form["type"] == "form":
            form = await manager.async_configure(form["flow_id"], {"manual": True})
        return form

    async def submit_wizard(
        self, *, query: str, line: str, stop: str | None = None, pole: str | None = None, api_key: str = DEFAULT_KEY, **extra: Any
    ) -> dict:
        """Run the screens of the setup dialog (the key, what to search for, the stop when the name fits several, the pole when the stop has
        more than one with lines, the line) and return the raw result of the last one; ``extra`` goes to the line screen."""
        flow = self.hass.config_entries.flow
        result = await flow.async_init(DOMAIN, context={"source": "user"})
        result = await flow.async_configure(result["flow_id"], {"api_key": api_key})
        answers = {"stop": {"query": query}, "pick": {"stop": stop}, "pole": {"pole": pole}, "line": {"line": line, **extra}}
        while result["type"] == "form" and result["step_id"] in answers:
            answer = answers[result["step_id"]]
            if None in answer.values():
                return result
            result = await flow.async_configure(result["flow_id"], answer)
        await self.settle()
        return result

    async def add_entry_via_flow(self, **kwargs: Any) -> ConfigEntry:
        """Run the config flow to the end and return the entry it created; a flow that ends any other way is a harness error."""
        result = await self.submit_flow(**kwargs)
        if result["type"] != "create_entry":
            raise HarnessError(f"the config flow did not create an entry: {result.get('errors') or result}")
        return result["result"]

    async def add_entry(
        self,
        *,
        line: str = "151",
        stop_id: int | str = 7009,
        stop_nr: str = "01",
        departures: int = 1,
        api_key: str = DEFAULT_KEY,
        data: dict | None = None,
        options: dict | None = None,
        setup: bool = True,
    ) -> MockConfigEntry:
        """Add a config entry shaped exactly like the ones a 1.1.4 user already has."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=f"Line {line} from {stop_id}/{stop_nr}",
            data=data
            if data is not None
            else {
                "api_key": api_key,
                "busstop_id": int(stop_id) if str(stop_id).isdigit() else stop_id,
                "busstop_nr": stop_nr,
                "line": line,
                "departures": departures,
            },
            options=options or {},
        )
        entry.add_to_hass(self.hass)
        if setup:
            await self.hass.config_entries.async_setup(entry.entry_id)
            await self.settle()
        return entry

    # -- reading ----------------------------------------------------------------------
    @staticmethod
    def entity_id(line: str, stop_id: int | str = 7009, stop_nr: str = "01", *, diag: bool = False) -> str:
        """The entity ID the integration gives the sensor of this line at this pole (or its diagnostic sensor with ``diag=True``)."""
        return f"sensor.line_{line.lower()}_from_{stop_id}_{stop_nr}" + ("_last_update" if diag else "")

    def state(self, line: str = "151", stop_id: int | str = 7009, stop_nr: str = "01", *, diag: bool = False) -> State:
        """The state of that sensor; a harness error if Home Assistant has none, so a typo cannot read as 'no state'."""
        st = self.hass.states.get(self.entity_id(line, stop_id, stop_nr, diag=diag))
        if st is None:
            raise HarnessError(f"no state for {self.entity_id(line, stop_id, stop_nr, diag=diag)}")
        return st

    def departure_local(self, line: str = "151", stop_id: int | str = 7009, stop_nr: str = "01") -> str | None:
        """The sensor's state as 'YYYY-MM-DD HH:MM' Warsaw wall-clock, or None for unknown/unavailable."""
        st = self.state(line, stop_id, stop_nr)
        if st.state in ("unknown", "unavailable"):
            return None
        return datetime.fromisoformat(st.state).astimezone(WARSAW).strftime("%Y-%m-%d %H:%M")

    def coordinator(self, entry: ConfigEntry):
        """The coordinator the integration created for this entry (a version 1 entry only: a line keeps its coordinators by stop)."""
        return entry.runtime_data["coordinator"]

    @property
    def entity_registry(self) -> er.EntityRegistry:
        """Home Assistant's entity registry."""
        return er.async_get(self.hass)

    @property
    def device_registry(self) -> dr.DeviceRegistry:
        """Home Assistant's device registry."""
        return dr.async_get(self.hass)


@pytest.fixture
async def env(clock, hass, enable_custom_integrations, fake_city, sleeps) -> AsyncIterator[Env]:
    """The one fixture e2e tests use. Order matters: clock first, then hass, then the fake city.

    Home Assistant's device tracker component (set up for the vehicle tracker) wakes every five seconds to look for stale
    devices; ``run_to`` steps from timer to timer, so that timer is switched off here: it has nothing to do with the integration."""
    await hass.config.async_set_time_zone("Europe/Warsaw")
    # The City's old API is treated as gone in production (const.LEGACY_API_RETIRED); its code stays until 2.0, and these
    # tests keep it covered against the fake city. The tests of the retired mode switch it back on.
    with (
        patch("homeassistant.components.device_tracker.legacy.async_track_utc_time_change", return_value=lambda: None),
        patch("custom_components.ztm_warsaw.const.LEGACY_API_RETIRED", False),
    ):
        yield Env(hass, clock, fake_city, sleeps)
