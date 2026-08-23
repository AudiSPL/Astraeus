"""Request schema. The response is returned as the packet dict (its schema is
documented in README); keeping it untyped avoids over-constraining the contract
while the packet grows through the phases.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class BirthIn(BaseModel):
    date: str = Field(..., examples=["1984-07-24"])
    time: str = Field(..., examples=["05:10:00"])
    time_accuracy: Literal["exact", "approx", "unknown"] = "unknown"
    time_uncertainty_minutes: Optional[float] = Field(
        None, ge=0, le=180,
        description="Symmetric +/- uncertainty around the recorded birth time. "
                    "Use with time_accuracy='approx'; exact defaults to 0 and unknown remains explicitly unresolved."
    )
    birth_time_provenance: Literal[
        "user_supplied", "official_record", "hospital_record",
        "family_memory", "rectified", "unknown"
    ] = "user_supplied"
    place_label: Optional[str] = Field(None, examples=["Belgrade, Serbia"])
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None

    @model_validator(mode="after")
    def validate_birth_time_precision(self):
        u = self.time_uncertainty_minutes
        if self.time_accuracy == "exact":
            if u not in (None, 0, 0.0):
                raise ValueError("time_accuracy='exact' requires time_uncertainty_minutes to be 0 or omitted")
        elif self.time_accuracy == "approx":
            if u is None or u <= 0:
                raise ValueError("time_accuracy='approx' requires time_uncertainty_minutes > 0")
        elif self.time_accuracy == "unknown":
            if u is not None:
                raise ValueError("time_accuracy='unknown' requires time_uncertainty_minutes to be omitted")
        return self


class SettingsIn(BaseModel):
    zodiac: Literal["tropical", "sidereal"] = "tropical"
    ayanamsha: Literal["lahiri", "fagan_bradley", "krishnamurti", "raman"] = "lahiri"
    house_system: Literal["placidus", "whole_sign", "koch", "equal"] = "placidus"
    node_type: Literal["true", "mean"] = "true"
    include_points: list[str] = ["chiron", "lilith"]


class TransitIn(BaseModel):
    date: str
    time: str = "12:00:00"
    timezone: str = "UTC"


class ForecastIn(BaseModel):
    enabled: bool = False
    start_date: Optional[str] = Field(
        None, examples=["2026-06-20"],
        description="YYYY-MM-DD; defaults to today (UTC) if omitted")
    end_date: Optional[str] = Field(
        None, examples=["2027-06-20"],
        description="YYYY-MM-DD; if omitted, computed as start_date + months")
    months: int = 12
    include_inner: bool = Field(
        False,
        description="Also scan Sun and Mars exact hits (Moon/Mercury/Venus still excluded).")
    movers: Optional[list[str]] = Field(
        None,
        description="Override mover list entirely; e.g. ['Mars','Jupiter']. Ignored if empty.")


class ProgressionsIn(BaseModel):
    date: str = Field(..., examples=["2026-07-15"])
    angle_method: Literal["fast", "real_gmt"] = Field(
        "fast",
        description="fast: progressed JD through natal coordinates; "
                    "real_gmt: houses/angles at birth local time on progressed calendar date.")


class SolarReturnIn(BaseModel):
    year: int = Field(..., examples=[2026])
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    house_system: Optional[Literal["placidus", "whole_sign", "koch", "equal"]] = None


class SynastryIn(BaseModel):
    enabled: bool = False
    partner: BirthIn
    include_composite: bool = True
    house_overlay: bool = True


class BaziIn(BaseModel):
    enabled: bool = False
    hour_pillar_time_basis: Literal[
        "civil_clock", "standard_time_no_dst", "local_mean_solar_time", "true_solar_time"
    ] = "local_mean_solar_time"
    late_zi_advances_day: bool = False
    gender: Literal["male", "female", "unspecified"] = "unspecified"


class ChineseStem(BaseModel):
    index: int
    name: str
    character: str
    element: str
    yin_yang: str


class ChineseBranch(BaseModel):
    index: int
    name: str
    character: str
    animal: str
    element: str
    yin_yang: str


class ChineseYearPillarCombined(BaseModel):
    name: str
    characters: str


class ChineseYearPillar(BaseModel):
    stem: ChineseStem
    branch: ChineseBranch
    combined: ChineseYearPillarCombined


class ChineseAstrologyBlock(BaseModel):
    system: str
    calendar_method: str
    year_pillar: ChineseYearPillar
    five_elements_presence: dict[str, int]
    yin_yang_presence: dict[str, int]
    warnings: list[str]


class ChartRequest(BaseModel):
    birth: BirthIn
    settings: SettingsIn = SettingsIn()
    include_chinese_astrology: bool = False
    bazi: Optional[BaziIn] = None
    transit: Optional[TransitIn] = None
    forecast: Optional[ForecastIn] = None
    progressions: Optional[ProgressionsIn] = None
    solar_return: Optional[SolarReturnIn] = None
    synastry: Optional[SynastryIn] = None
