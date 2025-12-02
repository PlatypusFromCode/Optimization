from dataclasses import dataclass
from typing import List
from enum import Enum

class Faculty(Enum):
    BU = 1
    AU = 2
    KG = 3
    M  = 4

class RoomType(Enum):
    LECTURE = 1
    LAB = 2
    COMPUTER = 3
    SEMINAR = 4


class Building(Enum):
    GSS = 1
    M7 = 2
    C11 = 3

@dataclass
class Teacher:
    faculty: Faculty
    course_name: List[str]     # список названий курсов
    hard_time_constr: List[int]
    soft_time_constr: List[int]


@dataclass
class Course:
    faculty: Faculty
    assumed_capacity: int
    semester: List[str]
    name: str
    facility_constr: List[RoomType]


class Room:
    address: Building
    name: str
    type: RoomType
    faculty: Faculty
    capacity: int