from enum import Enum


class Mode(str, Enum):
    WALK = "walk"
    BIKE = "bike"
    BUS = "bus"
    METRO = "metro"
    AUTO = "auto"
    CAR = "car"
