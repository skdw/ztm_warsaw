from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo
import re
import homeassistant.util.dt as dt_util

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
            hour, minute, _ = self.czas.split(":")
            hour = int(hour)
            minute = int(minute)

            if hour >= 24:
                hour -= 24
                day_offset = 1
            else:
                day_offset = 0

            local_now = dt_util.now().astimezone(ZTMTimeZone)
            local_date = local_now.date()

            # If it is after midnight, but before 5 am - we treat the day as “yesterday”
            if local_now.hour < 5:
                local_date -= timedelta(days=1)

            dt_combined = datetime.combine(
                local_date + timedelta(days=day_offset),
                dt_util.parse_time(f"{hour:02d}:{minute:02d}")
            ).astimezone(timezone.utc)

            return dt_combined
        except Exception:
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