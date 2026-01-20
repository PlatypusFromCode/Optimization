import random
from collections import defaultdict

import gurobipy as gp
from gurobipy import Model, GRB

import structures
from structures import Room, Building, Faculty

import hard_constrains
import soft_constrains
import json_loaders_savers
import json_generator


# ============================ IIS Helpers (wie bei dir) ============================

def analyze_iis(m):
    reasons = defaultdict(list)
    for constr in m.getConstrs():
        if constr.IISConstr:
            name = constr.ConstrName
            if name.startswith("course_"):
                reasons["courses"].append(name)
            elif name.startswith("teacher_"):
                reasons["teachers"].append(name)
            elif name.startswith("room_"):
                reasons["rooms"].append(name)
            elif name.startswith("slot_"):
                reasons["slots"].append(name)
            else:
                reasons["other"].append(name)
    return reasons


def get_unschedulable_objects_from_iis(m) -> tuple[list[int], dict[int, int], list[str]]:
    unschedulable_courses = []
    unschedulable_teachers_hard_time_dict = {}
    allowed_types = []
    counter = [0,0,0,0,0,0,0,0]

    m.computeIIS()

    for constr in m.getConstrs():
        if not constr.IISConstr:
            continue

        name = constr.ConstrName

        if name.startswith("teacher_") and "_must_be_fulfilled" in name:
            parts = name.split("_")
            t_id = int(parts[1])
            slot = int(parts[4])
            unschedulable_teachers_hard_time_dict[t_id] = slot
            if counter[0] == 0:
                print(f"{name}_cannot be fullfilled")
                counter[0] = 1

        elif name.startswith("there_is_at_least_1_slot_1_room_1_teacher_assigned_to_course_"):
            c_id = int(name.rsplit("_", 1)[1])
            unschedulable_courses.append(c_id)
            if counter[1] == 0:
                print(f"{name}_cannot be fullfilled")
                counter[1] = 1

        elif name.startswith("course_") and "_needs_" in name and "_allowed_" in name:
            allowed_part = name.split("_allowed_", 1)[1]
            allowed_types = allowed_part.split("_")
            if counter[2] == 0:
                print(f"{name}_cannot be fullfilled")
                counter[2] = 1

        elif name.startswith("course_"):
            # fallback: versucht Kurs-ID zu lesen
            if counter[3] == 0:
                print(f"{name}_cannot be fullfilled")
                counter[3] = 1
            parts = name.split("_")
            try:
                c_id = int(parts[1])
                unschedulable_courses.append(c_id)
            except Exception:
                pass

    return list(set(unschedulable_courses)), unschedulable_teachers_hard_time_dict, allowed_types


# ============================ Utility / Debug ============================

def build_courses_by_semester(courses_objects):
    courses_by_sem = defaultdict(list)
    for c in courses_objects:
        for sem in c.semester:
            courses_by_sem[sem].append(c.course_id)
    return dict(courses_by_sem)

def pick_existing_semester(
    courses_by_sem: dict[tuple[str, int], list],
    preferred: tuple[str, int] | None,
):
    #if preferred sem exists and not empty
    if preferred and preferred in courses_by_sem and courses_by_sem[preferred]:
        return preferred
    #first sem with courses
    for sem, ids in courses_by_sem.items():
        if ids:
            return sem
    #fallback
    return next(iter(courses_by_sem.keys()), preferred)




def print_objective_breakdown(soft_exprs: dict[str, gp.LinExpr], obj_val: float):
    print("\n================ OBJECTIVE BREAKDOWN ================")
    total = 0.0
    for k, expr in soft_exprs.items():
        try:
            v = float(expr.getValue())
        except Exception:
            v = float("nan")
        print(f"{k:28s}: {v:12.6f}")
        if v == v:  # not NaN
            total += v
    print(f"{'SUM(components)':28s}: {total:12.6f}")
    print(f"{'OBJ (m.ObjVal)':28s}: {obj_val:12.6f}")
    print("====================================================\n")


def count_assignments(x, slots, teachers_id_list, courses_id_list, rooms_id_list):
    return sum(
        1
        for s in slots
        for t in teachers_id_list
        for c in courses_id_list
        for r in rooms_id_list
        if x[s, t, c, r].X > 0.5
    )


# ============================ Main ============================

def main():
    m = Model()
    random.seed(41)

    # ------------------ Data generation ------------------
    teachers_objects = json_generator.random_teachers(10)
    courses_objects = json_generator.random_courses(30)
    rooms_objects = json_generator.random_rooms(8)
    rooms_objects.append(Room(len(rooms_objects), Building.GSS, "Audimax", structures.RoomType.LECTURE, Faculty.BU, 150))
    rooms_objects.append(Room(len(rooms_objects) + 1 , Building.B11, "Labclass", structures.RoomType.LAB, Faculty.M, 30))
    rooms_objects.append(Room(len(rooms_objects) + 2, Building.B11, "Compclass", structures.RoomType.COMPUTER, Faculty.M, 30))



    teachers_id_list = [t.teacher_id for t in teachers_objects]
    courses_id_list = [c.course_id for c in courses_objects]
    rooms_id_list = [r.room_id for r in rooms_objects]

    slots = range(1, 32)

    teacher_by_id = {t.teacher_id: t for t in teachers_objects}
    course_by_id = {c.course_id: c for c in courses_objects}
    room_by_id = {r.room_id: r for r in rooms_objects}

    semesters = {
        (study, sem_num)
        for c in courses_objects
        for (study, sem_num, _) in c.semester
    }

    days = [
        range(1, 8),
        range(8, 15),
        range(15, 18),
        range(18, 25),
        range(25, 32),
    ]

    remote_buildings=[Building.C11,Building.C13]

    courses_by_sem = build_courses_by_semester(courses_objects)

    print("\n================ DATA SANITY ================")
    print("Teachers:", len(teachers_objects))
    print("Courses :", len(courses_objects))
    print("Rooms   :", len(rooms_objects))
    print("Semesters in data:", sorted(list(semesters), key=lambda x: str(x))[:30])
    for sem, ids in sorted(courses_by_sem.items(), key=lambda kv: str(kv[0])):
        print(f"  {sem}: {len(ids)} courses")
    print("============================================\n")

    # ------------------ Weights + toggles ------------------
    # Basis-Softs
    weights_by_name: dict[str, float] = {
        "TEACHER_SOFT_TIME": 50,
        "ROOM_WASTE": 10,
        "FACULTY_MISMATCH": 500,
        "REMOTE_LUNCH": 50,
        "GAP_AVOID" : 50,

        # Neue Softs (Beispielgewichte – müssen kalibriert werden)
        "T_MAX_CONSEC": 20,
        "T_MIN_TEACH_DAYS": 5,
        "SEM_MAX_PER_DAY": 5,
        "SEM_AVOID_EARLY": 3,
        "SEM_SINGLE_DAY": 2,
        "T_MIN_FREE_DAYS": 5,
        # Gebäudestabilität pro Kurs ist nur sinnvoll bei Mehrfach-Terminen pro Kurs:
        "COURSE_STABILITY": 0.2,
        "T_B2B_BUILDING_CHANGE": 1.0,
        # optional (falls du Paare definierst):
        "LECT_BEFORE_TUT": 5,
        "TWO_LAST_SLOTS" : 50
    }

    ENABLE_SOFTS = {
        "TEACHER_SOFT_TIME": True,
        "ROOM_WASTE": True,
        "FACULTY_MISMATCH": True,
        "REMOTE_LUNCH": True,
        "GAP_AVOID": False,

        "T_MAX_CONSEC": True,
        "T_MIN_TEACH_DAYS": True,
        "SEM_MAX_PER_DAY": True,
        "SEM_AVOID_EARLY": True,
        "SEM_SINGLE_DAY": True,
        "T_MIN_FREE_DAYS": True,

        "COURSE_STABILITY": False,           # meist 0, wenn Kurse nur 1x stattfinden
        "T_B2B_BUILDING_CHANGE": True,

        "LECT_BEFORE_TUT": False,            # braucht Paare
        "TWO_LAST_SLOTS" : True
    }

    # Definiere, was "early" ist: hier z.B. erster Slot pro Tag
    early_slots = {1, 8, 15, 18, 25}

    # Wenn du bestimmte Semester besonders schützen willst (z.B. Erstsemester):
    target_semesters_early = None  # oder z.B. {"Study 1 Sem 1"}

    # Lecture/Tutorial Paare
    lecture_tutorial_pairs = []  # [(lecture_course_id, tutorial_course_id), ...]

    # ------------------ Variables ------------------
    x = m.addVars(slots, teachers_id_list, courses_id_list, rooms_id_list, vtype=GRB.BINARY, name="x")

    # ------------------ Hard constraints ------------------
    hard_constrains.add_single_room_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_single_teacher_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_no_semester_overlapping_constr(m, x, semesters, course_by_id, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_teacher_hard_time_constraints(m, x, teachers_id_list, teacher_by_id, courses_id_list, rooms_id_list)
    hard_constrains.add_room_capacity_constr(m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list)
    hard_constrains.add_room_type_constraints(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, course_by_id, room_by_id)
    hard_constrains.add_all_courses_scheduled_constraint(m, x, courses_id_list, teachers_id_list, rooms_id_list, slots)

    # ------------------ Soft constraints (objective components) ------------------
    soft_exprs: dict[str, gp.LinExpr] = {}

    if ENABLE_SOFTS["TEACHER_SOFT_TIME"]:
        soft_exprs["TEACHER_SOFT_TIME"] = soft_constrains.add_teacher_soft_time_objective(
            m, x, teachers_id_list, teacher_by_id, courses_id_list, rooms_id_list, weights_by_name["TEACHER_SOFT_TIME"]
        )

    if ENABLE_SOFTS["ROOM_WASTE"]:
        soft_exprs["ROOM_WASTE"] = soft_constrains.add_room_waste_objective(
            m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list, weights_by_name["ROOM_WASTE"]
        )

    if ENABLE_SOFTS["FACULTY_MISMATCH"]:
        soft_exprs["FACULTY_MISMATCH"] = soft_constrains.add_faculty_mismatch_objective(
            m, x, courses_id_list, rooms_id_list, course_by_id, room_by_id, slots, teachers_id_list, weights_by_name["FACULTY_MISMATCH"]
        )

    if ENABLE_SOFTS["REMOTE_LUNCH"]:
        soft_exprs["REMOTE_LUNCH"] = soft_constrains.add_remote_building_lunch_objcetive(
            m,x,slots,teachers_id_list, courses_id_list, rooms_id_list, room_by_id, remote_buildings, weight= weights_by_name["REMOTE_LUNCH"]
        )

    if ENABLE_SOFTS["GAP_AVOID"]:
        soft_exprs["GAP_AVOID"] = soft_constrains.add_semester_gap_objective(
            x, semesters, courses_id_list, course_by_id, teachers_id_list, rooms_id_list, days, weight=weights_by_name["GAP_AVOID"]
        )

    # Neue Softs
    if ENABLE_SOFTS["T_MAX_CONSEC"]:
        soft_exprs["T_MAX_CONSEC"] = soft_constrains.add_teacher_max_consecutive_objective(
            m, x, slots, days, teachers_id_list, courses_id_list, rooms_id_list,
            max_consecutive=2, weight=weights_by_name["T_MAX_CONSEC"]
        )

    if ENABLE_SOFTS["T_MIN_TEACH_DAYS"]:
        soft_exprs["T_MIN_TEACH_DAYS"] = soft_constrains.add_teacher_min_teaching_days_objective(
            m, x, slots, days, teachers_id_list, courses_id_list, rooms_id_list,
            weight=weights_by_name["T_MIN_TEACH_DAYS"]
        )

    if ENABLE_SOFTS["SEM_MAX_PER_DAY"]:
        soft_exprs["SEM_MAX_PER_DAY"] = soft_constrains.add_semester_max_classes_per_day_objective(
            m, x, semesters, course_by_id, slots, days, teachers_id_list, rooms_id_list, courses_id_list,
            max_classes_per_day=3, weight=weights_by_name["SEM_MAX_PER_DAY"]
        )

    if ENABLE_SOFTS["SEM_AVOID_EARLY"]:
        soft_exprs["SEM_AVOID_EARLY"] = soft_constrains.add_semester_avoid_early_slots_objective(
            m, x, semesters, course_by_id, early_slots, teachers_id_list, rooms_id_list, courses_id_list,
            target_semesters=target_semesters_early, weight=weights_by_name["SEM_AVOID_EARLY"]
        )

    if ENABLE_SOFTS["SEM_SINGLE_DAY"]:
        soft_exprs["SEM_SINGLE_DAY"] = soft_constrains.add_semester_single_class_day_objective(
            m, x, semesters, courses_id_list, course_by_id, teachers_id_list, rooms_id_list, days,
            weight=weights_by_name["SEM_SINGLE_DAY"]
        )

    if ENABLE_SOFTS["T_MIN_FREE_DAYS"]:
        teach_any = soft_constrains.build_teacher_teach_any(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, name="teach_any_free")
        soft_exprs["T_MIN_FREE_DAYS"] = soft_constrains.add_teacher_min_free_days_objective(
            m, x, slots, days, teachers_id_list, courses_id_list, rooms_id_list,
            min_free_days=1, weight=weights_by_name["T_MIN_FREE_DAYS"], teach_any=teach_any
        )

    if ENABLE_SOFTS["COURSE_STABILITY"]:
        soft_exprs["COURSE_STABILITY"] = soft_constrains.add_course_room_and_building_stability_objective(
            m, x, courses_id_list, slots, teachers_id_list, rooms_id_list, room_by_id,
            weight_room=weights_by_name["COURSE_STABILITY"], weight_building=weights_by_name["COURSE_STABILITY"]
        )

    if ENABLE_SOFTS["T_B2B_BUILDING_CHANGE"]:
        soft_exprs["T_B2B_BUILDING_CHANGE"] = soft_constrains.add_teacher_back_to_back_building_change_objective(
            m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, room_by_id,
            weight=weights_by_name["T_B2B_BUILDING_CHANGE"]
        )

    if ENABLE_SOFTS["LECT_BEFORE_TUT"] and lecture_tutorial_pairs:
        soft_exprs["LECT_BEFORE_TUT"] = soft_constrains.add_lecture_before_tutorial_objective(
            m, x, slots, teachers_id_list, rooms_id_list, lecture_tutorial_pairs,
            weight=weights_by_name["LECT_BEFORE_TUT"]
        )

    if ENABLE_SOFTS["TWO_LAST_SLOTS"]:
        soft_exprs["TWO_LAST_SLOTS"] = soft_constrains.add_last_two_slots_objective(x,semesters, courses_id_list, course_by_id, teachers_id_list, rooms_id_list, days)

    # ------------------ Objective ------------------
    if len(soft_exprs) == 0:
        m.setObjective(0.0, GRB.MINIMIZE)
    else:
        m.setObjective(gp.quicksum(soft_exprs.values()), GRB.MINIMIZE)

    m.Params.OutputFlag = 1
    m.optimize()

    # ------------------ Results / IIS ------------------
    if m.Status == GRB.INFEASIBLE:
        print("Model infeasible, computing IIS...")
        m.computeIIS()
        m.write("model.ilp")
        unscheduled_courses, unscheduled_teachers_slots, not_found_room_types = get_unschedulable_objects_from_iis(m)
        print("Unscheduled courses:", unscheduled_courses)
        print("Unscheduled teachers slots:", unscheduled_teachers_slots)
        print("Not found room types:", not_found_room_types)
        print("uns. course:", course_by_id[unscheduled_courses[0]])
        return

    if m.Status in (GRB.OPTIMAL, GRB.SUBOPTIMAL) and m.SolCount > 0:
        print("\nSolution found")
        print(f"Obj = {m.ObjVal:.6f}")

        print("Total scheduled assignments:", count_assignments(x, slots, teachers_id_list, courses_id_list, rooms_id_list))
        print_objective_breakdown(soft_exprs, m.ObjVal)

        preferred_sem = ("Study 3", 1)

        semester_to_print = pick_existing_semester(courses_by_sem, preferred_sem)

        if semester_to_print != preferred_sem:
            print(
                f"NOTE: preferred semester {preferred_sem} "
                f"not found/empty. Printing {semester_to_print} instead."
            )

        courses_in_preferred = courses_by_sem.get(semester_to_print, [])

        json_loaders_savers.print_schedule_for_semester(
            m,
            x,
            semester=semester_to_print,
            slots=slots,
            teachers_id_list=teachers_id_list,
            courses_id_list=courses_id_list,
            rooms_id_list=rooms_id_list,
            teacher_by_id=teacher_by_id,
            course_by_id=course_by_id,
            room_by_id=room_by_id
        )
    else:
        print(f"\nNO SOLUTION. Status = {m.Status}")


if __name__ == "__main__":
    main()