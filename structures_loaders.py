from structures import Teacher, Course, Room, Faculty, RoomType, Building
import json

def load_teachers(path: str) -> list[Teacher]:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return [
        Teacher(
            teacher_id=item["teacher_id"],
            teacher_name=item["teacher_name"],
            faculty=Faculty[item["faculty"]],
            course_name=item["course_name"],
            hard_time_constr=item["hard_time_constr"],
            soft_time_constr=item["soft_time_constr"]
        )
        for item in data
    ]

'''
json sample
[
  {
    "teacher_id": 0,
    "teacher_name": "Mueller",
    "faculty": "BU",
    "course_name": ["Baukonstruktionen"],
    "hard_time_constr": [1, 2],
    "soft_time_constr": [5, 6]
  }
]

'''



def load_courses(path: str) -> list[Course]:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return [
        Course(
            course_id=item["course_id"],
            faculty=Faculty[item["faculty"]],
            expected_num_students=item["expected_num_students"],
            semester=item["semester"],
            name=item["name"],
            facility_constr=[type[rt] for rt in item["facility_constr"]]
        )
        for item in data
    ]
'''
json sample
[
  {
    "course_id": 0,
    "faculty": "BU",
    "expected_num_students": 90,
    "semester": ["BI1", "UI1"],
    "name": "Baukonstruktionen",
    "facility_constr": ["LECTURE"]
  }
]

'''

def load_rooms(path: str) -> list[Room]:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return [
        Room(
            room_id=item["room_id"],
            address=Building[item["address"]],
            name=item["name"],
            type=RoomType[item["type"]],
            faculty=Faculty[item["faculty"]],
            capacity=item["capacity"]
        )
        for item in data
    ]

'''
json sample
[
  {
    "room_id": 0,
    "address": "M13",
    "name": "201",
    "type": "LECTURE",
    "faculty": "BU",
    "capacity": 120
  }
]
'''