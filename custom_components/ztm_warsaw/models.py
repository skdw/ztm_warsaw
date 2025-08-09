from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo
import homeassistant.util.dt as dt_util

import logging

_LOGGER = logging.getLogger(__name__)

ZTMTimeZone = ZoneInfo("Europe/Warsaw")

@dataclass
class ZTMDepartureDataReading:
    kierunek: str = field(default="unknown")
    czas: str = field(default="00:00:00")
    symbol_1: Optional[str] = field(default=None)
    symbol_2: Optional[str] = field(default=None)
    trasa: Optional[str] = field(default=None)
    brygada: Optional[str] = field(default=None)

    @classmethod
    def from_dict(cls, data):
        return cls(
            kierunek=data.get("kierunek", "unknown"),
            czas=data.get("czas", "00:00:00"),
            symbol_1=data.get("symbol_1"),
            symbol_2=data.get("symbol_2"),
            trasa=data.get("trasa"),
            brygada=data.get("brygada"),
        )

    # Night buses in ZTM use hours >= 24; day services after midnight keep 00:xx
    @property
    def night_bus(self) -> bool:
        try:
            hour = int(self.czas.split(":")[0])
            return hour >= 24
        except Exception:
            return False

    @property
    def dt(self):
        try:
            # Validate time format HH:MM:SS
            if not isinstance(self.czas, str) or len(self.czas.split(":")) != 3:
                _LOGGER.warning("Invalid time format for 'czas': %r", self.czas)
                return None

            hour_str, minute_str, _ = self.czas.split(":")
            hour = int(hour_str)
            minute = int(minute_str)

            local_now = dt_util.now().astimezone(ZTMTimeZone)
            base_date = local_now.date()
            current_hour = local_now.hour
            current_minute = local_now.minute

            # Night courses: 24+ -> 0+
            if hour >= 24:
                dt_hour = hour - 24
            else:
                dt_hour = hour

            # Decide target date: today if time is still ahead, otherwise tomorrow
            if (dt_hour > current_hour) or (dt_hour == current_hour and minute > current_minute):
                target_date = base_date
            else:
                target_date = base_date + timedelta(days=1)

            # Build timezone-aware datetime in Europe/Warsaw and convert to UTC
            naive = datetime.combine(target_date, dt_util.parse_time(f"{dt_hour:02d}:{minute:02d}"))
            local_dt = naive.replace(tzinfo=ZTMTimeZone)
            utc_dt = local_dt.astimezone(timezone.utc)
            return utc_dt

        except Exception as e:
            _LOGGER.warning("Error while calculating dt: %s (czas=%r)", e, self.czas)
            return None

    @property
    def time_to_depart(self):
        now = dt_util.now().astimezone(timezone.utc)
        if self.dt:
            delta = self.dt - now
            return max(0, int(delta.total_seconds() / 60))
        return -1

@dataclass
class ZTMDepartureData:
    departures: list[ZTMDepartureDataReading]
    stop_info: Optional[dict] = field(default_factory=dict)