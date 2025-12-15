from structures import Teacher, Course, Room, Faculty, RoomType, Building
import json
from gurobipy import GRB
from decimal import Decimal


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
            facility_constr=[type[rt] for rt in item["facility_constr"]],
            soft_time_constr=item["soft_time_constr"],
            times_per_week = Decimal(item["times_per_week"])

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


def save_schedule_to_json(
    m,
    x,
    slots,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    path: str = "schedule_solution.json"
):
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Model status is not OPTIMAL: {m.Status}")

    solution = []

    for slot in slots:
        for t_id in teachers_id_list:
            for c_id in courses_id_list:
                for r_id in rooms_id_list:
                    if x[slot, t_id, c_id, r_id].X == 1:
                        solution.append({
                            "slot": slot,
                            "teacher_id": t_id,
                            "course_id": c_id,
                            "room_id": r_id
                        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(solution, f, ensure_ascii=False, indent=2)

'''
json sample
[
  {
    "slot": 3,
    "teacher_id": 5,
    "course_id": 12,
    "room_id": 7
  },
  {
    "slot": 4,
    "teacher_id": 2,
    "course_id": 9,
    "room_id": 1
  }
]
'''


def print_schedule_for_semester(
    m,
    x,
    semester: str,
    slots,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    teacher_by_id,
    course_by_id,
    room_by_id
):
    if m.Status != GRB.OPTIMAL:
        print(f"Model status is not OPTIMAL: {m.Status}")
        return

    print(f"\nSemester: {semester}")
    print("-" * 40)

    found = False

    for slot in slots:
        for c_id in courses_id_list:
            if course_by_id[c_id].semester != semester:
                continue

            for t_id in teachers_id_list:
                for r_id in rooms_id_list:
                    if x[slot, t_id, c_id, r_id].X == 1:
                        found = True
                        print(
                            f"Slot {slot} | "
                            f"Course {course_by_id[c_id].name} | "
                            f"Teacher {teacher_by_id[t_id].teacher_name} | "
                            f"Room {room_by_id[r_id].name}"
                        )

    if not found:
        print("No courses scheduled for this semester.")
