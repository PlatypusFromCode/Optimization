import json
import random
import decimal
from dataclasses import asdict
from enum import Enum
from typing import List
from dataclasses import dataclass
from structures import *


'''quantative constrains'''

MAX_COURSES_PER_TEACHER = 3
MAX_ROOM_CAPACITY = 150
MAX_HARD_CONSTRAINS_PER_TEACHER = 10
MAX_SOFT_CONSTRAINS_PER_TEACHER = 10

ROOM_TYPE_WEIGHTS = {
    RoomType.LECTURE: 0.5,
    RoomType.LAB: 0.05,
    RoomType.COMPUTER: 0.05,
    RoomType.SEMINAR: 0.4
}

FACULTY_WEIGHTS = {
    Faculty.BU: 0.4,
    Faculty.AU: 0.3,
    Faculty.KG: 0.2,
    Faculty.M: 0.1
}

CAPACITY_WEIGHTS = {
    20 : 0.3,
    30 : 0.2,
    40 : 0.2,
    50 : 0.15,
    100 : 0.15,
}

EXPECTED_NUM_STUDENTS = {
    20 : 0.3,
    30 : 0.2,
    40 : 0.2,
    50 : 0.15,
    100 : 0.1,
    150 : 0.05
}

BUILDING_WEIGHTS = {
    Building.GSS: 0.3,
    Building.M13: 0.2,
    Building.C11: 0.15,
    Building.C13: 0.15,
    Building.M7: 0.1,
    Building.B11: 0.05,
    Building.HK7: 0.05
}



''' pool of possible values'''

POOLS = {
    "teacher_name": ["Teacher 1", "Teacher 2", "Teacher 3", "Teacher 4",
                    "Teacher 5", "Teacher 6", "Teacher 7", "Teacher 8"],
    "faculty_name": ["BU", "AU", "KG", "M"],
    "course_name" : ["Course 1", "Course 2", "Course 3", "Course 4",
                     "Course 5", "Course 6", "Course 7", "Course 8",
                     "Course 9", "Course 10", "Course 11", "Course 12"],
    "hard_time_constr" : range(1,32),
    "soft_time_constr" : range(1,32),
    "expected_num_students" : range(MAX_ROOM_CAPACITY),
    "semester": [
        ("Study 1", 1),
        ("Study 2", 1),
        ("Study 3", 1),
        ("Study 1", 2),
        ("Study 2", 2),
        ("Study 3", 2),
        ("Study 1", 3),
        ("Study 2", 3),
        ("Study 3", 3),
    ],
    "facility_constr" : ["LECTURE", "LAB", "COMPUTER", "SEMINAR"],
    "times_per_week": [1,2],
    "address" : ["GSS", "M13", "C11", "C13", "M7", "B11", "HK7"],
    "capacity" : [20, 30, 40, 60 , 100]
}



def weighted_choice(weight_dict):
    return random.choices(
        list(weight_dict.keys()),
        weights=list(weight_dict.values()),
        k=1
    )[0]



def serialize(obj):
    if isinstance(obj, Enum):
        return obj.name
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def choose_room_type(expected_students: int) -> RoomType:
    allowed = []

    if expected_students <= 30:
        allowed += [RoomType.LAB, RoomType.COMPUTER]

    if expected_students <= 50:
        allowed += [RoomType.SEMINAR]

    allowed.append(RoomType.LECTURE)

    weights = {t: ROOM_TYPE_WEIGHTS[t] for t in allowed}

    return weighted_choice(weights)



def random_teacher(i: int) -> Teacher:
    return Teacher(
        teacher_id=i,
        teacher_name=random.choice(POOLS["teacher_name"]),
        faculty=random.choice(list(Faculty)),
        course_name=random.sample(
            POOLS["course_name"],
            k=random.randint(1, MAX_COURSES_PER_TEACHER)
        ),
        hard_time_constr=random.sample(
            POOLS["hard_time_constr"],
            k=MAX_HARD_CONSTRAINS_PER_TEACHER
        ),
        soft_time_constr=random.sample(
            POOLS["soft_time_constr"],
            k=MAX_SOFT_CONSTRAINS_PER_TEACHER
        ),
    )


def random_room(i: int) -> Room:
    return Room(
        room_id= i,
        address=random.choice(list(Building)),
        room_name=str(200 + i),
        type=weighted_choice(ROOM_TYPE_WEIGHTS),
        faculty=weighted_choice(FACULTY_WEIGHTS),
        capacity=weighted_choice(CAPACITY_WEIGHTS)
    )


def random_course(i: int) -> Course:
    expected_students = weighted_choice(EXPECTED_NUM_STUDENTS)

    return Course(
        course_id=i,
        faculty=random.choice(list(Faculty)),
        expected_num_students=expected_students,
        semester=[
            (study, sem_num, random.choice(list(CourseType)))
            for (study, sem_num) in random.sample(
                POOLS["semester"],
                k=random.randint(1, 2)
            )
        ],
        course_name=random.choice(POOLS["course_name"]),
        facility_constr=[choose_room_type(expected_students)],
        soft_time_constr=random.sample(
            POOLS["soft_time_constr"],
            k=random.randint(1, 5)
        ),
        hard_time_constr=random.sample(
            POOLS["hard_time_constr"],
            k=random.randint(1, 5)
        ),
        times_per_week=random.choice(POOLS["times_per_week"])
    )



def random_teachers(number_of_objects: int) -> List[Teacher]:
    return [random_teacher(i) for i in range(number_of_objects)]

def random_courses(number_of_objects: int) -> List[Course]:
    return [random_course(i) for i in range(number_of_objects)]

def random_rooms(number_of_objects: int) -> List[Room]:
    return [random_room(i) for i in range(number_of_objects)]