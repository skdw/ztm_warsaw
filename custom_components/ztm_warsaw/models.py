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
            
            # Get current local time in Warsaw
            local_now = dt_util.now().astimezone(ZTMTimeZone)
            current_hour = local_now.hour
            current_minute = local_now.minute
            
            # Normalize hour (for night services using 24+ notation)
            normalized_hour = hour % 24
            
            # Determine the correct date for this departure
            base_date = local_now.date()
            
            # 1. Night buses (hour >= 24)
            if hour >= 24:
                # If it's early morning, treat as part of tonight's schedule
                if current_hour < 5:
                    target_date = base_date
                else:
                    # Otherwise, it's a night bus from the next day
                    target_date = base_date + timedelta(days=1)
            
            # 2. Regular services
            else:
                # If departure hour < 5 and it's between midnight and 5:00 AM
                if hour < 5 and 0 <= current_hour < 5:
                    # Check if this departure time has already passed
                    if hour < current_hour or (hour == current_hour and minute < current_minute):
                        target_date = base_date + timedelta(days=1)
                    else:
                        target_date = base_date
                
                # If hour < 5 but it's already later in the day
                elif hour < 5 and current_hour >= 5:
                    # This is tomorrow's early morning departure
                    target_date = base_date + timedelta(days=1)
                
                # If it's a late evening hour (20–23) but current time is early morning
                elif hour >= 20 and current_hour < 5:
                    # Treat as today's evening departure even if we're past midnight
                    target_date = base_date
                
                # In all other cases, check if the departure time has already passed
                else:
                    # If this hour has already passed, consider it as tomorrow's departure
                    if hour < current_hour or (hour == current_hour and minute < current_minute):
                        target_date = base_date + timedelta(days=1)
                    else:
                        target_date = base_date
            
            # Compose the full datetime object
            dt_combined = datetime.combine(
                target_date,
                dt_util.parse_time(f"{normalized_hour:02d}:{minute:02d}")
            ).astimezone(timezone.utc)
            
            # Debug info (day offset applied)
            day_diff = (target_date - base_date).days
            print(f"Time: {self.czas}, Current: {current_hour}:{current_minute}, Day offset: {day_diff}, Result: {dt_combined}")
            
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