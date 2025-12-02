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
    M13 = 2
    C11 = 3

@dataclass
class Teacher:
    teacher_id: int
    teacher_name: str
    faculty: Faculty
    course_name: List[str]     # список названий курсов
    hard_time_constr: List[int]
    soft_time_constr: List[int]


@dataclass
class Course:
    course_id: int
    faculty: Faculty
    expected_num_students: int
    semester: List[str]
    name: str
    facility_constr: List[RoomType]

@dataclass
class Room:
    room_id: int
    address: Building
    name: str
    type: RoomType
    faculty: Faculty
    capacity: int