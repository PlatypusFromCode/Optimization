from gurobipy import Model, GRB
from structures import Teacher, Course, Room
import gurobipy as gp
import hard_constrains
#import structures_loaders

m = Model()

teachers: list[Teacher] = [] #probably use loaders here
courses: list[Course] = []
rooms: list[Room] = []

T = [t.teacher_id for t in teachers] #lists of ids
C = [c.course_id for c in courses]
R = [r.room_id for r in rooms]

slots = range(31) # mon, thue, thur, fri 7.30 9.15 11.00 13.30 15.15 17.00 18.30 wed 7.30 9.15 11.00
teacher_by_id = {t.teacher_id: t for t in teachers} #dict in form of obj_id:obj
course_by_id = {c.course_id: c for c in courses} #dict in form of obj_id:obj
room_by_id = {r.room_id: r for r in rooms}

semesters = set(c.semester for c in courses) # for example SC4DMsem1

x = m.addVars(slots, T, C, R, vtype=GRB.BINARY, name="x") #x[slot, teacher, course, room]

hard_constrains.add_single_room_single_course_constr(m,x,slots, teachers, courses, rooms)
hard_constrains.add_single_teacher_single_course_constr(m,x, slots, teachers, courses, rooms)
hard_constrains.add_no_semester_overlapping_constr(m,x,semesters, course_by_id,slots, teachers, courses, rooms)
hard_constrains.add_teacher_hard_time_constraints(m, x, teachers, teacher_by_id, courses, rooms)
hard_constrains.add_room_capacity_constr(m, x, courses, rooms, course_by_id, room_by_id, slots, teachers)
hard_constrains.add_room_type_constraints(m, x, slots, teachers, courses, rooms, course_by_id, room_by_id)


