from gurobipy import Model, GRB
from structures import Teacher, Course, Room

m = Model()

T: list[Teacher] = []
C: list[Course] = []
R: list[Room] = []

S = range(31)

x = m.addVars(S, T, C, R, vtype=GRB.BINARY, name="x") #x[slot, teacher, course, room]


for r in R:
    for s in S:                                                  # for every room r in R and for every time slot s in S
        m.addConstr(sum(x[s,t,c,r] for t in T for c in C) <= 1)  # there is more than 1 teacher t teaching course c


for t in T:
    for s in S:                                                   # for every teacher t and for every time slot s
        m.addConstr(sum(x[s, t, c, r] for c in C for r in R) <= 1)# there is no more than 1 course taught in any room

semesters = set(c.semester for c in C)

for sem in semesters:
    courses_in_sem = [c for c in C if c.semester == sem]

    for s in S:
        m.addConstr(
            sum(x[s, t, c, r]
                for c in courses_in_sem
                for t in T
                for r in R) <= 1
        )

for t in T: # if there is a hard personal constraint for teacher there must be no courses for that time
    for s in t.hard_time_constr:
        m.addConstr(sum(x[s, t, c, r] for c in C for r in R) == 0)
