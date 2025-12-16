from gurobipy import Model, GRB
from structures import Teacher, Course, Room
import gurobipy as gp
#import structures_loaders







def add_single_room_single_course_constr(m, x, slots, teachers, courses, rooms):
    for r in rooms:                                                          # for every room r in R and for every time slot s in S
        for s in slots:                                                      # there is more than 1 teacher t teaching course c
            m.addConstr(
                gp.quicksum(x[s, t, c, r] for t in teachers for c in courses) <= 1
            )


def add_single_teacher_single_course_constr(m, x, slots, teachers, courses, rooms):

    for t_id in teachers:
        for slot in slots:
            m.addConstr(
                gp.quicksum(
                    x[slot, t_id, c_id, r_id]
                    for c_id in courses
                    for r_id in rooms
                ) <= 1
            )







def add_no_semester_overlapping_constr(m, x, semesters, course_by_id,  slots, teachers, courses, rooms):

    for sem in semesters:

        courses_in_sem = [
            c_id for c_id in courses
            if sem in course_by_id[c_id].semester
        ]

        for slot in slots:
            m.addConstr(
                gp.quicksum(
                    x[slot, t_id, c_id, r_id]
                    for c_id in courses_in_sem
                    for t_id in teachers
                    for r_id in rooms
                ) <= 1,
            )



def add_teacher_hard_time_constraints(m, x, teachers, teacher_by_id, courses, rooms):

    for t_id in teachers:
        teacher = teacher_by_id[t_id]

        for slot in teacher.hard_time_constr:
            m.addConstr(
                gp.quicksum(
                    x[slot, t_id, c_id, r_id]
                    for c_id in courses
                    for r_id in rooms
                ) == 0
            )

def add_room_capacity_constr(
    m, x, courses, rooms, course_by_id, room_by_id, slots, teachers
):

    for c_id in courses:
        course = course_by_id[c_id]

        for r_id in rooms:
            room = room_by_id[r_id]

            if course.expected_num_students > room.capacity:
                for slot in slots:
                    for t_id in teachers:
                        m.addConstr(
                            x[slot, t_id, c_id, r_id] == 0
                        )

def add_room_type_constraints(
    m, x, slots, teachers, courses, rooms, course_by_id, room_by_id
):

    for slot in slots:
        for t_id in teachers:
            for c_id in courses:
                course = course_by_id[c_id]
                allowed_types = set(course.facility_constr)

                for r_id in rooms:
                    if room_by_id[r_id].type not in allowed_types:
                        m.addConstr(
                            x[slot, t_id, c_id, r_id] == 0
                        )


def add_all_courses_scheduled_constraint(
    m,
    x,
    courses_id_list,
    teachers_id_list,
    rooms_id_list,
    slots
):
    for c_id in courses_id_list:
        m.addConstr(
            gp.quicksum(
                x[s, t_id, c_id, r_id]
                for s in slots
                for t_id in teachers_id_list
                for r_id in rooms_id_list
            ) >= 1
        )

