from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo
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

            local_now = dt_util.now().astimezone(ZTMTimeZone)
            base_date = local_now.date()
            current_hour = local_now.hour
            current_minute = local_now.minute

            # Night courses: 24+ -> 0+
            if hour >= 24:
                dt_hour = hour - 24
            else:
                dt_hour = hour

            # Has it already passed today?
            if (dt_hour > current_hour) or (dt_hour == current_hour and minute > current_minute):
                target_date = base_date
            else:
                target_date = base_date + timedelta(days=1)

            dt_combined = datetime.combine(
                target_date,
                dt_util.parse_time(f"{dt_hour:02d}:{minute:02d}")
            ).astimezone(timezone.utc)
            return dt_combined

        except Exception as e:
            print(f"Error while calculating dt: {e}")
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