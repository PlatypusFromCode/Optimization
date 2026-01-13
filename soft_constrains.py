import gurobipy as gp
from gurobipy import GRB


def add_teacher_soft_time_objective(
    m,
    x,
    teachers,
    teacher_by_id,
    courses,
    rooms,
    weight: float = 10.0,
    use_multiobj: bool = False,
    priority: int = 1,
):
    """
    Soft constraint: Termine in teacher.soft_time_constr (ungünstige Slots) werden bestraft.
    Da bei dir pro Teacher und Slot sowieso max. 1 Termin erlaubt ist, ist die Summe (c,r) <= 1,
    d.h. man zahlt pro "ungünstigen Slot" höchstens 1x penalty.

    weight: Strafgewicht pro Termin in ungünstigem Slot
    use_multiobj: wenn True, nutzt setObjectiveN (Multi-Objective)
    priority: Multiobj-Priorität (höher = wichtiger)
    """
    penalty_expr = gp.LinExpr()

    for t_id in teachers:
        t = teacher_by_id[t_id]
        for slot in t.soft_time_constr:
            penalty_expr += gp.quicksum(
                x[slot, t_id, c_id, r_id]
                for c_id in courses
                for r_id in rooms
            )

    penalty_expr *= weight
    return penalty_expr


def add_room_waste_objective(
    m,
    x,
    courses,
    rooms,
    course_by_id,
    room_by_id,
    slots,
    teachers,
    weight: float = 0.1,
    use_multiobj: bool = False,
    priority: int = 0,
):
    """
    Sitzplatz-Verschwendung minimieren.
    Kosten = (room.capacity - expected_students) wenn belegt.
    weight: Skaliert diese Kosten (typisch klein im Vergleich zu harten Präferenzen).
    """
    waste_expr = gp.LinExpr()

    for slot in slots:
        for t_id in teachers:
            for c_id in courses:
                exp = course_by_id[c_id].expected_num_students
                for r_id in rooms:
                    cap = room_by_id[r_id].capacity
                    if cap >= exp:
                        waste_expr += (cap - exp) * x[slot, t_id, c_id, r_id]

    waste_expr *= weight
    return waste_expr



def add_faculty_mismatch_objective(
    m,
    x,
    courses,
    rooms,
    course_by_id,
    room_by_id,
    slots,
    teachers,
    weight: float = 1.0,
    use_multiobj: bool = False,
    priority: int = 0,
):
    """
    Fakultätsfremde Räume bestrafen.
    Kosten = 1, wenn course.faculty != room.faculty (wenn belegt).
    """
    mismatch_expr = gp.LinExpr()

    for slot in slots:
        for t_id in teachers:
            for c_id in courses:
                cf = course_by_id[c_id].faculty
                for r_id in rooms:
                    rf = room_by_id[r_id].faculty
                    if rf != cf:
                        mismatch_expr += x[slot, t_id, c_id, r_id]

    mismatch_expr *= weight
    return mismatch_expr

def add_remote_building_lunch_objcetive(
    m,
    x,
    slots,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    room_by_id,
    remote_buildings,
    weight: float = 0.1
):
    expr = gp.LinExpr()

    lunch_pairs = [(2,3), (9,10), (19,20), (26,27)]

    for (s1, s2) in lunch_pairs:
        if s1 not in slots or s2 not in slots:
            continue

        for t_id in teachers_id_list:
            for c_id in courses_id_list:
                for r_id in rooms_id_list:
                    if room_by_id[r_id].address in remote_buildings:
                        z = m.addVar(vtype=GRB.BINARY)
                        m.addConstr(z <= x[s1, t_id, c_id, r_id])
                        m.addConstr(z <= x[s2, t_id, c_id, r_id])
                        m.addConstr(z >= x[s1, t_id, c_id, r_id] + x[s2, t_id, c_id, r_id] - 1)
                        expr += z

    return weight * expr



def add_semester_gap_objective(
    x,
    semesters,
    courses_id_list,
    course_by_id,
    teachers_id_list,
    rooms_id_list,
    days,
    max_gap: int = 5,
    weight: float = 1.0,
):

    gap_expr = gp.LinExpr()

    courses_by_sem = {
        sem: [
            c_id for c_id in courses_id_list
            if sem in course_by_id[c_id].semester
        ]
        for sem in semesters
    }

    for sem in semesters:
        sem_courses = courses_by_sem[sem]

        for day in days:
            slots = list(day) #list of slots per day

            for i, s1 in enumerate(slots):
                for k in range(1, max_gap + 1): # k - length of a window
                    j = i + k + 1 # last class on a day
                    if j >= len(slots):
                        break

                    s2 = slots[j] # time of the last class on a day


                    start = gp.quicksum(
                        x[s1, t, c, r]
                        for c in sem_courses
                        for t in teachers_id_list
                        for r in rooms_id_list
                    ) # if there is a class on the first time slot


                    end = gp.quicksum(
                        x[s2, t, c, r]
                        for c in sem_courses
                        for t in teachers_id_list
                        for r in rooms_id_list
                    ) #if there is a class at the last time slot


                    middle = gp.quicksum(
                        x[slots[m], t, c, r]
                        for m in range(i + 1, j)
                        for c in sem_courses
                        for t in teachers_id_list
                        for r in rooms_id_list
                    ) #check if there is classes between the first and last

                    # if start is 1(true) and end is 1(true) and middle is 0(false) then pay a fine depending on the size of the window
                    # if exactly the situation start + end - middle - 1 = 1
                    if (start + end - middle - 1) == 1:
                        gap_expr += weight * k

    return gap_expr


def add_different_buildings_objective(
    m,
    x,
    slots,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    room_by_id,
    weight: float = 0.1,
):

    expr = gp.LinExpr()

    for s in slots:
        s_next = s + 1
        if s_next not in slots:
            continue

        for t_id in teachers_id_list:
            for c_id in courses_id_list:
                for r1 in rooms_id_list:
                    for r2 in rooms_id_list:
                        if r1 == r2 :
                            continue

                        if room_by_id[r1].address != room_by_id[r2].address:
                            expr += (
                                x[s, t_id, c_id, r1]
                                + x[s_next, t_id, c_id, r2]
                            )

    return weight * expr



#zum laufen bringen und die kombination von den 2 programmen mit großen inputs (huge random example) vergleichen.

#wir gehen davon aus, dass wir 50 kurse haben und wir nehmen die anzahl von den stundenten, die wir vom anfang an in dem kurs hatten. wir wissen auch wie viele und was wir alles an räumen haben und das können wir ungefähr dann in unseren Constrains einfügen. Genaunso können wir ein paar fake teachers erstellen und sie auch für unsere zwecken nutzen. 

#wir sollten auch mit den anderen reden, wie das mit dem JSON funktionieren soll. und die andere sollen das alles dann analysieren. 

#linear programming von uns muss in zu dem nächsten meeting fertig sein(das wird wahrscheinlich in 2 wochen sei)