import os
import json
import inspect
from collections import defaultdict

import gurobipy as gp
from gurobipy import Model, GRB

import structures
from structures import Faculty, Teacher, Course, Room

import hard_constrains
import soft_constrains


# ============================ Config ============================

JSON_DIR = "."
TEACHERS_JSON = os.path.join(JSON_DIR, "teachers.json")
COURSES_JSON  = os.path.join(JSON_DIR, "courses.json")
ROOMS_JSON    = os.path.join(JSON_DIR, "rooms.json")
TIMESLOTS_JSON = os.path.join(JSON_DIR, "timeslot.json")

PREFERRED_SEMESTER = "Computer Science for Digital Media"

# Allow dropping courses (otherwise model can become infeasible)
ALLOW_DROPPING_COURSES = True
DROP_PENALTY = 1e6  # very high => only drop if truly impossible


# ============================ JSON helpers ============================

ROOMTYPE_SYNONYMS = {
    "LAB": "COMPUTER",
    "PC": "COMPUTER",
    "PCPOOL": "COMPUTER",
    "POOL": "COMPUTER",
    "HÖRSAAL": "LECTURE",
}

GERMAN_WEEKDAY_ORDER = {
    "Montag": 0,
    "Dienstag": 1,
    "Mittwoch": 2,
    "Donnerstag": 3,
    "Freitag": 4,
    "Samstag": 5,
    "Sonntag": 6,
}


def read_json_list(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected JSON list, got {type(data)}")
    return data


def enum_try(enum_cls, value):
    if value is None:
        return None
    if hasattr(value, "name"):
        return value

    if isinstance(value, str):
        key = value.strip()

        if enum_cls is getattr(structures, "RoomType", None):
            key = ROOMTYPE_SYNONYMS.get(key.upper(), key)

        if hasattr(enum_cls, key):
            return getattr(enum_cls, key)
        if hasattr(enum_cls, key.upper()):
            return getattr(enum_cls, key.upper())

        try:
            return enum_cls[key]
        except Exception:
            pass
        try:
            return enum_cls[key.upper()]
        except Exception:
            pass

    return value


def construct_flex(cls, payload: dict):
    sig = inspect.signature(cls.__init__)
    accepted = {p.name for p in sig.parameters.values() if p.name != "self"}
    kwargs = {}

    if cls is Teacher:
        if "teacher_id" in accepted:
            kwargs["teacher_id"] = payload.get("teacher_id")

        if "teacher_name" in accepted:
            kwargs["teacher_name"] = payload.get("teacher_name")
        elif "name" in accepted:
            kwargs["name"] = payload.get("teacher_name")

        if "faculty" in accepted:
            kwargs["faculty"] = enum_try(Faculty, payload.get("faculty"))

        if "hard_time_constr" in accepted:
            kwargs["hard_time_constr"] = payload.get("hard_time_constr", [])
        if "soft_time_constr" in accepted:
            kwargs["soft_time_constr"] = payload.get("soft_time_constr", [])

        # IMPORTANT: your Teacher.__init__ requires course_name
        if "course_name" in accepted:
            cn = payload.get("course_name")
            if cn is None:
                cn = payload.get("course_names", [])
            if isinstance(cn, list):
                kwargs["course_name"] = ", ".join(cn)
            else:
                kwargs["course_name"] = str(cn) if cn is not None else ""

    elif cls is Room:
        if "room_id" in accepted:
            kwargs["room_id"] = payload.get("room_id")

        room_name_val = payload.get("room_name", payload.get("name"))
        if "room_name" in accepted:
            kwargs["room_name"] = room_name_val
        elif "name" in accepted:
            kwargs["name"] = room_name_val

        if "address" in accepted:
            kwargs["address"] = payload.get("address")

        rtype = payload.get("type")
        if hasattr(structures, "RoomType"):
            rtype = enum_try(structures.RoomType, rtype)

        if "type" in accepted:
            kwargs["type"] = rtype
        elif "room_type" in accepted:
            kwargs["room_type"] = rtype

        if "faculty" in accepted:
            kwargs["faculty"] = enum_try(Faculty, payload.get("faculty"))

        if "capacity" in accepted:
            kwargs["capacity"] = payload.get("capacity", 0)

    elif cls is Course:
        if "course_id" in accepted:
            kwargs["course_id"] = payload.get("course_id")
        if "course_name" in accepted:
            kwargs["course_name"] = payload.get("course_name")

        if "course_type" in accepted:
            ctype = payload.get("course_type")
            if hasattr(structures, "CourseType"):
                ctype = enum_try(structures.CourseType, ctype)
            kwargs["course_type"] = ctype

        if "faculty" in accepted:
            kwargs["faculty"] = enum_try(Faculty, payload.get("faculty"))

        if "semester" in accepted:
            kwargs["semester"] = payload.get("semester", [])
        if "duration_minutes" in accepted:
            kwargs["duration_minutes"] = payload.get("duration_minutes", 90)

        # IMPORTANT: facility_constr must be RoomType enums
        if "facility_constr" in accepted:
            raw = payload.get("facility_constr", [])
            if not isinstance(raw, list):
                raw = [] if raw is None else [raw]
            if hasattr(structures, "RoomType"):
                raw = [enum_try(structures.RoomType, v) for v in raw]
            kwargs["facility_constr"] = raw

        if "teacher_ids" in accepted:
            kwargs["teacher_ids"] = payload.get("teacher_ids", [])
        if "room_name" in accepted:
            kwargs["room_name"] = payload.get("room_name")
        if "expected_num_students" in accepted:
            kwargs["expected_num_students"] = payload.get("expected_num_students", 0)
        if "times_per_week" in accepted:
            kwargs["times_per_week"] = payload.get("times_per_week", 1.0)

        # required by your Course.__init__
        if "hard_time_constr" in accepted:
            kwargs["hard_time_constr"] = payload.get("hard_time_constr", [])
        if "soft_time_constr" in accepted:
            kwargs["soft_time_constr"] = payload.get("soft_time_constr", [])

    kwargs = {k: v for k, v in kwargs.items() if k in accepted}
    return cls(**kwargs)


def load_teachers(path: str) -> list[Teacher]:
    return [construct_flex(Teacher, it) for it in read_json_list(path)]


def load_rooms(path: str) -> list[Room]:
    return [construct_flex(Room, it) for it in read_json_list(path)]


def load_courses(path: str) -> list[Course]:
    return [construct_flex(Course, it) for it in read_json_list(path)]


def load_timeslots(timeslots_path: str):
    """
    Returns:
      slots: range/list of ids
      days: list[list[int]] grouped by weekday
      ts_by_id: {id: {"day":..., "start":..., "end":...}}
    """
    data = read_json_list(timeslots_path)

    slot_ids = []
    day_map = defaultdict(list)
    ts_by_id = {}

    for ts in data:
        slot_id = ts.get("timeslot_id", ts.get("slot_id", ts.get("id")))
        if slot_id is None:
            continue
        slot_id = int(slot_id)

        slot_ids.append(slot_id)
        ts_by_id[slot_id] = ts

        day = ts.get("day")
        if day is not None:
            day_map[str(day)].append(slot_id)

    slot_ids = sorted(set(slot_ids))
    if not slot_ids:
        raise ValueError("No timeslots found in timeslot.json")

    def day_sort_key(d: str):
        return (GERMAN_WEEKDAY_ORDER.get(d, 999), d)

    days = [sorted(day_map[d]) for d in sorted(day_map.keys(), key=day_sort_key)]
    slots = range(slot_ids[0], slot_ids[-1] + 1) if (slot_ids[-1] - slot_ids[0] + 1 == len(slot_ids)) else slot_ids
    return slots, days, ts_by_id


# ============================ Model helpers ============================

def add_course_teacher_compatibility_constraint(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, course_by_id):
    """
    Hard: course can only be assigned to teacher_ids.
    Robust:
      - if teacher_ids empty -> allow any teacher (warn)
      - if teacher_ids contain only missing IDs -> allow any teacher (warn)
    """
    teachers_set = set(teachers_id_list)
    warned_empty = False
    warned_invalid = False

    for c in courses_id_list:
        raw_allowed = set(getattr(course_by_id[c], "teacher_ids", []) or [])
        allowed = raw_allowed & teachers_set

        if not raw_allowed:
            warned_empty = True
            continue

        if raw_allowed and not allowed:
            warned_invalid = True
            continue

        for t in teachers_id_list:
            if t in allowed:
                continue
            m.addConstr(
                gp.quicksum(x[s, t, c, r] for s in slots for r in rooms_id_list) == 0,
                name=f"course_{c}_teacher_{t}_not_allowed"
            )

    if warned_empty:
        print("WARNING: At least one course has empty teacher_ids. Those courses are allowed with ANY teacher.")
    if warned_invalid:
        print("WARNING: At least one course has teacher_ids that do not exist in teachers.json. Those courses are allowed with ANY teacher.")


def add_all_courses_scheduled_soft(m, x, courses_id_list, teachers_id_list, rooms_id_list, slots, penalty: float):
    """
    Soft: schedule each course once OR pay a drop-penalty:
      sum_{s,t,r} x[s,t,c,r] + u[c] == 1
    """
    u = m.addVars(courses_id_list, vtype=GRB.BINARY, name="unscheduled")
    for c in courses_id_list:
        m.addConstr(
            gp.quicksum(x[s, t, c, r] for s in slots for t in teachers_id_list for r in rooms_id_list) + u[c] == 1,
            name=f"course_{c}_scheduled_or_dropped"
        )
    return u, penalty * gp.quicksum(u[c] for c in courses_id_list)


def print_objective_breakdown(soft_exprs: dict[str, gp.LinExpr], drop_expr, obj_val: float):
    print("\n================ OBJECTIVE BREAKDOWN ================")
    total = 0.0
    for k, expr in soft_exprs.items():
        v = float(expr.getValue())
        print(f"{k:28s}: {v:12.6f}")
        total += v
    if drop_expr is not None:
        dv = float(drop_expr.getValue())
        print(f"{'DROP_PENALTY':28s}: {dv:12.6f}")
        total += dv
    print(f"{'SUM(components)':28s}: {total:12.6f}")
    print(f"{'OBJ (m.ObjVal)':28s}: {obj_val:12.6f}")
    print("====================================================\n")


def print_schedule_for_semester(
    x,
    semester: str,
    slots,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    teacher_by_id,
    course_by_id,
    room_by_id,
    ts_by_id,
):
    rows = []
    for s in list(slots):
        for t in teachers_id_list:
            for c in courses_id_list:
                # only print the selected semester
                if semester not in getattr(course_by_id[c], "semester", []):
                    continue
                for r in rooms_id_list:
                    if x[s, t, c, r].X > 0.5:
                        course = course_by_id[c]
                        teacher = teacher_by_id[t]
                        room = room_by_id[r]

                        ts = ts_by_id.get(s, {})
                        day = ts.get("day", "")
                        start = ts.get("start", "")
                        end = ts.get("end", "")

                        teacher_name = getattr(teacher, "teacher_name", getattr(teacher, "name", str(t)))
                        course_name = getattr(course, "course_name", str(c))
                        room_name = getattr(room, "room_name", getattr(room, "name", str(r)))

                        rows.append((s, day, start, end, course_name, teacher_name, room_name))

    rows.sort(key=lambda x: x[0])

    print(f"\nSemester: {semester}")
    print("----------------------------------------")
    if not rows:
        print("No courses scheduled for this semester.")
        return

    for (s, day, start, end, course_name, teacher_name, room_name) in rows:
        time_str = f"{day} {start}-{end}".strip()
        print(f"Slot {s:>2} | {time_str:20s} | Course {course_name} | Teacher {teacher_name} | Room {room_name}")


# ============================ Main ============================

def main():
    m = Model()

    teachers_objects = load_teachers(TEACHERS_JSON)
    courses_objects  = load_courses(COURSES_JSON)
    rooms_objects    = load_rooms(ROOMS_JSON)
    slots, days, ts_by_id = load_timeslots(TIMESLOTS_JSON)

    teachers_id_list = [t.teacher_id for t in teachers_objects]
    courses_id_list  = [c.course_id for c in courses_objects]
    rooms_id_list    = [r.room_id for r in rooms_objects]

    teacher_by_id = {t.teacher_id: t for t in teachers_objects}
    course_by_id  = {c.course_id: c for c in courses_objects}
    room_by_id    = {r.room_id: r for r in rooms_objects}

    semesters = {sem for c in courses_objects for sem in c.semester}

    print("\n================ DATA SANITY ================")
    print("Teachers:", len(teachers_objects))
    print("Courses :", len(courses_objects))
    print("Rooms   :", len(rooms_objects))
    print("Slots   :", len(list(slots)))
    print("Days    :", [len(d) for d in days])
    print("Semesters in data:", sorted(list(semesters), key=lambda x: str(x)))
    print("============================================\n")

    weights_by_name = {
        "TEACHER_SOFT_TIME": 100,
        "ROOM_WASTE": 70,
        "FACULTY_MISMATCH": 50,
    }

    x = m.addVars(slots, teachers_id_list, courses_id_list, rooms_id_list, vtype=GRB.BINARY, name="x")

    # Hard constraints
    hard_constrains.add_single_room_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_single_teacher_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_no_semester_overlapping_constr(m, x, semesters, course_by_id, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_teacher_hard_time_constraints(m, x, teachers_id_list, teacher_by_id, courses_id_list, rooms_id_list)
    hard_constrains.add_room_capacity_constr(m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list)
    hard_constrains.add_room_type_constraints(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, course_by_id, room_by_id)

    add_course_teacher_compatibility_constraint(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, course_by_id)

    # Soft "all courses must be scheduled"
    unscheduled = None
    drop_expr = None
    if ALLOW_DROPPING_COURSES:
        unscheduled, drop_expr = add_all_courses_scheduled_soft(
            m, x, courses_id_list, teachers_id_list, rooms_id_list, slots, penalty=DROP_PENALTY
        )
    else:
        hard_constrains.add_all_courses_scheduled_constraint(m, x, courses_id_list, teachers_id_list, rooms_id_list, slots)

    # Soft objective components
    soft_exprs: dict[str, gp.LinExpr] = {
        "TEACHER_SOFT_TIME": soft_constrains.add_teacher_soft_time_objective(
            m, x, teachers_id_list, teacher_by_id, courses_id_list, rooms_id_list, weights_by_name["TEACHER_SOFT_TIME"]
        ),
        "ROOM_WASTE": soft_constrains.add_room_waste_objective(
            m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list, weights_by_name["ROOM_WASTE"]
        ),
        "FACULTY_MISMATCH": soft_constrains.add_faculty_mismatch_objective(
            m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list, weights_by_name["FACULTY_MISMATCH"]
        ),
    }

    obj = gp.quicksum(soft_exprs.values())
    if drop_expr is not None:
        obj = obj + drop_expr

    m.setObjective(obj, GRB.MINIMIZE)
    m.Params.OutputFlag = 1
    m.optimize()

    if m.Status in (GRB.OPTIMAL, GRB.SUBOPTIMAL) and m.SolCount > 0:
        print("\nSolution found")
        print(f"Obj = {m.ObjVal:.6f}")
        print_objective_breakdown(soft_exprs, drop_expr, m.ObjVal)

        if unscheduled is not None:
            dropped = [c for c in courses_id_list if unscheduled[c].X > 0.5]
            if dropped:
                print("Dropped courses (unschedulable under current hard constraints):", dropped)
                for c in dropped[:50]:
                    print("  ", course_by_id[c])
            else:
                print("No courses dropped.")

        sem = PREFERRED_SEMESTER if PREFERRED_SEMESTER in semesters else next(iter(semesters))
        print_schedule_for_semester(
            x=x,
            semester=sem,
            slots=slots,
            teachers_id_list=teachers_id_list,
            courses_id_list=courses_id_list,
            rooms_id_list=rooms_id_list,
            teacher_by_id=teacher_by_id,
            course_by_id=course_by_id,
            room_by_id=room_by_id,
            ts_by_id=ts_by_id,
        )
    else:
        print(f"\nNO SOLUTION. Status = {m.Status}")


if __name__ == "__main__":
    main()