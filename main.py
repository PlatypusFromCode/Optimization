from gurobipy import Model, GRB
from structures import Teacher, Course, Room
import gurobipy as gp
#import structures_loaders

m = Model()

teachers: list[Teacher] = [] #probably use loaders here
courses: list[Course] = []
rooms: list[Room] = []

T = [t.teacher_id for t in teachers] #lists of
C = [c.course_id for c in courses]
R = [r.room_id for r in rooms]

S = range(31)

teacher_by_id = {t.teacher_id: t for t in teachers} #dict in form of obj_id:obj
course_by_id = {c.course_id: c for c in courses} #dict in form of obj_id:obj
room_by_id = {r.room_id: r for r in rooms}

semesters = set(c.semester for c in courses) # for example SC4DMsem1

x = m.addVars(S, T, C, R, vtype=GRB.BINARY, name="x") #x[slot, teacher, course, room]

for r in R:
    for s in S:                                                  # for every room r in R and for every time slot s in S
        m.addConstr(gp.quicksum(x[s, t, c, r] for t in T for c in C) <= 1)  # there is more than 1 teacher t teaching course c


for t in T:
    for s in S:                                                   # for every teacher t and for every time slot s
        m.addConstr(gp.quicksum(x[s, t, c, r] for c in C for r in R) <= 1)# there is no more than 1 course taught in any room






for sem in semesters:
    courses_in_sem = [
        c_id for c_id in C
        if course_by_id[c_id].semester == sem
    ]

    for s in S:
        m.addConstr(
            gp.quicksum(
                x[s, t, c_id, r]
                for c_id in courses_in_sem
                for t in T
                for r in R
            ) <= 1
        )


for t_id in T:  # if there is a hard personal constraint for teacher there must be no courses for that time
    teacher = teacher_by_id[t_id]

    for s in teacher.hard_time_constr:
        m.addConstr(
            gp.quicksum(
                x[s, t_id, c_id, r_id]
                for c_id in C
                for r_id in R
            ) == 0
        )



for c_id in C: #constrain for rooms capacity
    course = course_by_id[c_id]
    for r_id in R:
        room = room_by_id[r_id]

        if course.expected_num_students > room.capacity:
            for s in S:
                for t_id in T:
                    m.addConstr(x[s, t_id, c_id, r_id] == 0)


for s in S: #constrain for room type
    for t_id in T:
        for c_id in C:
            course = course_by_id[c_id]
            allowed = set(course.facility_constr)

            for r_id in R:
                if room_by_id[r_id].type not in allowed:
                    m.addConstr(x[s, t_id, c_id, r_id] == 0)



