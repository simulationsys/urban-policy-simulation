from enum import Enum


class Mode(str, Enum):
    WALK = "walk"
    BIKE = "bike"
    BUS = "bus"
    METRO = "metro"
    AUTO = "auto"
    CAR = "car"


class Occupation(str, Enum):
    OFFICE_EXECUTIVE = "office_executive"
    STUDENT = "student"
    BLUE_COLLAR_WORKER = "blue_collar_worker"
    GIG_WORKER = "gig_worker"
    RETIRED_CITIZEN = "retired_citizen"
    STALL_OWNER = "stall_owner"
    STORE_MANAGER = "store_manager"
    STORE_STAFF = "store_staff"
