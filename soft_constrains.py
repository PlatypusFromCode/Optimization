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
    d.h. du zahlst pro "ungünstigen Slot" höchstens 1x penalty.

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

    if use_multiobj:
        # Soft objective als separates Ziel (Multi-Objective)
        m.setObjectiveN(penalty_expr, index=priority, priority=priority, name="soft_teacher_time")
    else:
        # Single objective: addiere zum bestehenden Ziel (falls vorhanden), sonst setze es.
        # Hinweis: Falls du schon eine Maximierungs-Zielfunktion hast, musst du das Konzept anpassen.
        if m.NumObj == 0:
            m.setObjective(penalty_expr, GRB.MINIMIZE)
        else:
            m.setObjective(m.getObjective() + penalty_expr, GRB.MINIMIZE)


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
    Optionales Soft objective: Sitzplatz-Verschwendung minimieren.
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

    if use_multiobj:
        m.setObjectiveN(waste_expr, index=priority, priority=priority, name="soft_room_waste")
    else:
        if m.NumObj == 0:
            m.setObjective(waste_expr, GRB.MINIMIZE)
        else:
            m.setObjective(m.getObjective() + waste_expr, GRB.MINIMIZE)


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
    Optionales Soft objective: Fakultätsfremde Räume bestrafen.
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

    if use_multiobj:
        m.setObjectiveN(mismatch_expr, index=priority, priority=priority, name="soft_faculty_mismatch")
    else:
        if m.NumObj == 0:
            m.setObjective(mismatch_expr, GRB.MINIMIZE)
        else:
            m.setObjective(m.getObjective() + mismatch_expr, GRB.MINIMIZE)