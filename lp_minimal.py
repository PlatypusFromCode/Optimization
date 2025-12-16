from gurobipy import Model, GRB

import soft_constrains
from structures import Teacher, Course, Room
import gurobipy as gp
import hard_constrains
import json_loaders_savers

def main():
    m = Model()

    teachers_objects: list[Teacher] = json_loaders_savers.load_teachers("teachers.json")  # probably use loaders here
    courses_objects: list[Course] = json_loaders_savers.load_courses("courses.json")
    rooms_objects: list[Room] = json_loaders_savers.load_rooms("rooms.json")

    teachers_id_list = [t.teacher_id for t in teachers_objects]  # lists of ids
    courses_id_list = [c.course_id for c in courses_objects]
    rooms_id_list = [r.room_id for r in rooms_objects]

    slots = range(5)  # mon, thue, thur, fri 7.30 9.15 11.00 13.30 15.15 17.00 18.30 wed 7.30 9.15 11.00
    teacher_dict_id_obj = {t.teacher_id: t for t in teachers_objects}  # dict in form of obj_id:obj
    course_dict_id_obj = {c.course_id: c for c in courses_objects}  # dict in form of obj_id:obj
    room_dict_id_obj = {r.room_id: r for r in rooms_objects}

    semesters = {
        sem
        for c in courses_objects
        for sem in c.semester
    }
    # for example SC4DMsem1

    x = m.addVars(slots, teachers_id_list, courses_id_list, rooms_id_list, vtype=GRB.BINARY, name="x")  # x[slot, teacher, course, room]

    hard_constrains.add_single_room_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_single_teacher_single_course_constr(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_no_semester_overlapping_constr(m, x, semesters, course_dict_id_obj, slots, teachers_id_list, courses_id_list, rooms_id_list)
    hard_constrains.add_teacher_hard_time_constraints(m, x, teachers_id_list, teacher_dict_id_obj, courses_id_list, rooms_id_list)
    hard_constrains.add_room_capacity_constr(m, x, courses_id_list, rooms_id_list, course_dict_id_obj, room_dict_id_obj, slots, teachers_id_list)
    hard_constrains.add_room_type_constraints(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, course_dict_id_obj, room_dict_id_obj)
    hard_constrains.add_all_courses_scheduled_constraint(m, x, courses_id_list,teachers_id_list, rooms_id_list, slots)

    #dict of weights by constraints names so the weights are easily changable
    weights_by_name: dict[str, float] = { "TEACHER_SOFT_TIME" : 0.1,
                                          "ROOM_WASTE" : 0.1,
                                          "FACULTY_MISMATCH" : 0.1 }

    #dict of linear expressions for setObjective, we use it for agile weight setting
    soft_constrs_dict_name_grexpr: dict[str, gp.LinExpr] = {
        "TEACHER_SOFT_TIME" : soft_constrains.add_teacher_soft_time_objective(m,x, teachers_id_list, teacher_dict_id_obj, courses_id_list, rooms_id_list, weights_by_name["TEACHER_SOFT_TIME"]),
        "ROOM_WASTE" : soft_constrains.add_room_waste_objective(m, x, courses_id_list, rooms_id_list, course_dict_id_obj, room_dict_id_obj, slots, teachers_id_list, weights_by_name["ROOM_WASTE"]),
        "FACULTY_MISMATCH" : soft_constrains.add_faculty_mismatch_objective(m,x,courses_id_list,rooms_id_list,course_dict_id_obj,room_dict_id_obj, slots, teachers_id_list, weights_by_name["FACULTY_MISMATCH"]),
    }


    # The exact objects function supposed to be minimized
    m.setObjective(soft_constrs_dict_name_grexpr["TEACHER_SOFT_TIME"] +
                   soft_constrs_dict_name_grexpr["ROOM_WASTE"] +
                   soft_constrs_dict_name_grexpr["FACULTY_MISMATCH"], GRB.MINIMIZE)


    # Optional: Ausgabe steuern
    m.Params.OutputFlag = 1  # 0 = still, 1 = normal

    # Optimieren
    m.optimize()

    if m.Status == GRB.INFEASIBLE:
        print("Model infeasible, computing IIS...")
        m.computeIIS()
        m.write("model.ilp")

    #print for tests
    if m.Status == GRB.OPTIMAL:
        print("\nOptimal solution found")
        print(f"Obj = {m.ObjVal:.6f}")

        json_loaders_savers.print_schedule_for_semester(
            m,
            x,
            semester="CS4DMsem1",
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