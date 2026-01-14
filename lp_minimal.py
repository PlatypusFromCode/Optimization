import random

from gurobipy import Model, GRB

import soft_constrains
import structures
from structures import Teacher, Course, Room, Building, Faculty
import gurobipy as gp
import hard_constrains
import json_loaders_savers
import json_generator
from collections import defaultdict

'''============================================ helping functions ===================================================='''

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
    breaks_counters = [0, 0, 0, 0, 0, 0, 0, 0]
    allowed_types = []

    m.computeIIS()

    for constr in m.getConstrs():
        if constr.IISConstr:
            name = constr.ConstrName

            if name.startswith("room_"):
                if breaks_counters[0] == 0:
                    print("unpredicted constraint break, must be no 2 courses per 1 room")
                    breaks_counters[0] += 1


            elif name.startswith("teacher_") and "_has_1_course_in_1_room_at_time_slot_" in name:
                if breaks_counters[1] == 0:
                    print("unpredicted constraint break, teacher cannot simultaneously teach 2 courses")
                    breaks_counters[1] += 1


            elif name.startswith("no_more_than_1_course_at_time_"):
                if breaks_counters[2] == 0:
                    print("unpredicted constraint break, no more than 1 course per slot at the same room")
                    breaks_counters[2] += 1


            elif name.startswith("teacher_") and "_must_be_fulfilled" in name:
                parts = name.split("_")
                t_id = int(parts[1])
                slot = int(parts[4])
                unschedulable_teachers_hard_time_dict[t_id] = slot

            elif name.startswith("course_"):
                parts = name.split("_")
                c_id = int(parts[1])
                unschedulable_courses.append(c_id)


            elif name.startswith("course_") and "_needs_" in name:
                allowed_part = name.split("_allowed_", 1)[1]
                allowed_types = allowed_part.split("_")

                if breaks_counters[3] == 0:
                    print("unpredicted constraint break, room must assign iff facility matches")
                    breaks_counters[3] += 1


            elif name.startswith("there_is_at_least_1_slot_1_room_1_teacher_assigned_to_course_"):
                # name = f"there_is_at_least_1_slot_1_room_1_teacher_assigned_to_course_{c_id}" - we take id after last _
                c_id = int(name.rsplit("_", 1)[1])
                unschedulable_courses.append(c_id)

    return list(set(unschedulable_courses)), unschedulable_teachers_hard_time_dict, allowed_types  # убираем дубликаты


def main():
    m = Model()
    random.seed(42)
    ''' ========================= main lists ====================================== '''
    #teachers_objects: list[Teacher] = json_loaders_savers.load_teachers("teachers.json")  # probably use loaders here
    #courses_objects: list[Course] = json_loaders_savers.load_courses("courses.json")
    #rooms_objects: list[Room] = json_loaders_savers.load_rooms("rooms.json")


    teachers_objects = json_generator.random_teachers(20)
    courses_objects = json_generator.random_courses(50)
    rooms_objects = json_generator.random_rooms(200)

    rooms_objects.append(Room(len(rooms_objects), Building.GSS, "Audimax", structures.RoomType.LECTURE,Faculty.BU, 150))



    print(len(teachers_objects), len(courses_objects), len(rooms_objects))


    teachers_id_list = [t.teacher_id for t in teachers_objects]  # lists of ids
    courses_id_list = [c.course_id for c in courses_objects]
    rooms_id_list = [r.room_id for r in rooms_objects]

    #slots from 1 to 31 inc.
    slots = range(1,32)
    #slots = range(5)  # mon, thue, thur, fri 7.30 9.15 11.00 13.30 15.15 17.00 18.30 wed 7.30 9.15 11.00
    teacher_dict_id_obj = {t.teacher_id: t for t in teachers_objects}  # dict in form of obj_id:obj
    course_dict_id_obj = {c.course_id: c for c in courses_objects}  # dict in form of obj_id:obj
    room_dict_id_obj = {r.room_id: r for r in rooms_objects}

    ''' =========================== helping lists ===================================='''

    semesters = {
        sem
        for c in courses_objects
        for sem in c.semester
    }
    # for example SC4DMsem1
    remote_buildings = {structures.Building.C11}

    days = [
        range(1, 8),
        range(8, 15),
        range(15, 18),
        range(18, 25),
        range(25, 32),
    ]

    # dict of weights by constraints names so the weights are easily changable
    weights_by_name: dict[str, float] = {"TEACHER_SOFT_TIME": 100,
                                         "ROOM_WASTE": 70,
                                         "FACULTY_MISMATCH": 50}

    '''================================== applying constrains ================================'''

    x = m.addVars(slots, teachers_id_list, courses_id_list, rooms_id_list, vtype=GRB.BINARY, name="x")  # x[slot, teacher, course, room]

    hard_constrains.add_single_room_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_single_teacher_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_no_semester_overlapping_constr(m, x, semesters, course_dict_id_obj, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_teacher_hard_time_constraints(m, x, teachers_id_list, teacher_dict_id_obj, courses_id_list, rooms_id_list)
    hard_constrains.add_room_capacity_constr(m, x, courses_id_list, rooms_id_list, course_dict_id_obj, room_dict_id_obj, slots, teachers_id_list)
    hard_constrains.add_room_type_constraints(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, course_dict_id_obj, room_dict_id_obj)
    hard_constrains.add_all_courses_scheduled_constraint(m, x, courses_id_list,teachers_id_list, rooms_id_list, slots)



    #dict of linear expressions for setObjective, we use it for agile weight setting
    soft_constrs_dict_name_grexpr: dict[str, gp.LinExpr] = {
        "TEACHER_SOFT_TIME" : soft_constrains.add_teacher_soft_time_objective(
            m,x, teachers_id_list, teacher_dict_id_obj, courses_id_list, rooms_id_list, weights_by_name["TEACHER_SOFT_TIME"]
        ),
        "ROOM_WASTE" : soft_constrains.add_room_waste_objective(
            m, x, courses_id_list, rooms_id_list, course_dict_id_obj, room_dict_id_obj, slots, teachers_id_list, weights_by_name["ROOM_WASTE"]
        ),
        "FACULTY_MISMATCH" : soft_constrains.add_faculty_mismatch_objective(
            m,x,courses_id_list,rooms_id_list,course_dict_id_obj,room_dict_id_obj, slots, teachers_id_list, weights_by_name["FACULTY_MISMATCH"]
        )
    }


    '''======================================== Optimizing ==========================================='''
    # The exact objects function supposed to be minimized
    m.setObjective(soft_constrs_dict_name_grexpr["TEACHER_SOFT_TIME"] +
                   soft_constrs_dict_name_grexpr["ROOM_WASTE"] +
                   soft_constrs_dict_name_grexpr["FACULTY_MISMATCH"], GRB.MINIMIZE)


    # Optional: Ausgabe steuern
    m.Params.OutputFlag = 1  # 0 = still, 1 = normal

    # Optimieren
    m.optimize()


    '''========================================= Results =============================================='''


    if m.Status == GRB.INFEASIBLE:
        print("Model infeasible, computing IIS...")
        m.computeIIS()
        m.write("model.ilp")
        unscheduled_courses, unscheduled_teachers_slots, not_found_room_types = get_unschedulable_objects_from_iis(m)
        print("Unscheduled courses: ", unscheduled_courses)
        print("Unscheduled teachers slots: ", unscheduled_teachers_slots)
        for course in unscheduled_courses:
            print("Unscheduled course: ", course_dict_id_obj[course])
        print("Not found room types: ", not_found_room_types)
        for teacher_id in unscheduled_teachers_slots.keys():
            print("Unfitted teacher", teacher_dict_id_obj[teacher_id])

    #print for tests
    if m.Status == GRB.OPTIMAL:
        print("\nOptimal solution found")
        print(f"Obj = {m.ObjVal:.6f}")

        json_loaders_savers.print_schedule_for_semester(
            m,
            x,
            semester="Study 3 Sem 1",
            slots=slots,
            teachers_id_list=teachers_id_list,
            courses_id_list=courses_id_list,
            rooms_id_list=rooms_id_list,
            teacher_by_id=teacher_dict_id_obj,
            course_by_id=course_dict_id_obj,
            room_by_id=room_dict_id_obj
        )
    else:
        print(f"\nNO OPTIMAL SOLUTION. Status = {m.Status}")
    #for saving in file
    '''
    if m.Status == GRB.OPTIMAL:
        print("\nOptimal solution found")
        print(f"Obj = {m.ObjVal:.6f}")

        json_loaders_savers.save_schedule_to_json(
            m,
            x,
            slots,
            teachers_id_list,
            courses_id_list,
            rooms_id_list
        )
    else:
        print(f"\nNO OPTIMAL SOLUTION. Status = {m.Status}")
    '''

if __name__ == "__main__":
    main()