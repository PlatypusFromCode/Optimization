import decimal
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

class CourseType(Enum):
    PFLICHT = 1
    WAHLPHLICHT = 2
    WAHL = 3
    UNABSICHTIGT = 4

class Building(Enum):
    GSS = 1
    M13 = 2
    C11 = 3
    C13 = 4
    M7 = 5
    B11 = 6
    HK7 = 7

@dataclass
class Teacher:
    teacher_id: int
    teacher_name: str
    faculty: Faculty
    course_name: List[str]     # course name list
    hard_time_constr: List[int]
    soft_time_constr: List[int]


@dataclass
class Course:
    course_id: int
    faculty: Faculty
    expected_num_students: int
    semester: list[tuple[str, int, CourseType]] #[[str study program, int sem name 0 - 8, bool is_mand],[],[]....]
    course_name: str
    facility_constr: List[RoomType] #it is a course type as well lecture room for lectures
    soft_time_constr: List[int]
    hard_time_constr: List[int]
    times_per_week: decimal.Decimal # 1/2 if every 2 weeks


@dataclass
class Room:
    room_id: int
    address: Building
    room_name: str
    type: RoomType
    faculty: Faculty
    capacity: int