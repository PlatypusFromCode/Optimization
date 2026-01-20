import gurobipy as gp
from gurobipy import GRB

from structures import Building


#================HELPER=====================
def build_teacher_teach_any(m, x, slots, teachers, courses, rooms, name="teach_any"):
    """
    teach_any[t,s] = 1, falls Lehrer t im Slot s irgendeinen Kurs hält.
    Setzt Gleichheit zur Summe, was bei deinen harten Constraints typischerweise sauber ist.
    """
    teach_any = m.addVars(teachers, list(slots), vtype=GRB.BINARY, name=name)
    for t in teachers:
        for s in slots:
            m.addConstr(
                teach_any[t, s] == gp.quicksum(x[s, t, c, r] for c in courses for r in rooms),
                name=f"{name}_def[{t},{s}]"
            )
    return teach_any


def build_course_occ(m, x, slots, teachers, courses, rooms, name="course_occ"):
    """
    course_occ[c,s] = 1, falls Kurs c im Slot s stattfindet (egal welcher Lehrer/Raum).
    Bei 'Kurs genau einmal' ist das insgesamt genau ein Slot.
    """
    occ = m.addVars(courses, list(slots), vtype=GRB.BINARY, name=name)
    for c in courses:
        for s in slots:
            m.addConstr(
                occ[c, s] == gp.quicksum(x[s, t, c, r] for t in teachers for r in rooms),
                name=f"{name}_def[{c},{s}]"
            )
    return occ


def build_courses_by_semester(semesters, courses_id_list, course_by_id):
    out = {}

    for sem in semesters:
        study, sem_num = sem

        out[sem] = [
            c_id
            for c_id in courses_id_list
            if any(
                study == s and sem_num == n
                for (s, n, _) in course_by_id[c_id].semester
            )
        ]

    return out


#=========================================
#=================SOFTS===================
#=========================================

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
    remote_buildings:list[Building],
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

    courses_by_sem = build_courses_by_semester(semesters, courses_id_list, course_by_id)

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

                    # if start is 1(true) and end is 1(true) and middle is 0(false) then pay a fine depending on the size of the window
                    # if exactly the situation start + end - middle - 1 = 1

                    gap_expr += weight * k * (start + end)






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


#---------------------------------

def add_teacher_max_consecutive_objective(
    m: gp.Model,
    x,
    slots,
    days,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    max_consecutive: int = 2,
    weight: float = 1.0,
):
    """
    Soft: Dozent soll nicht mehr als max_consecutive Slots am Stück unterrichten.
    Wir penalizen jedes vollständige Fenster der Länge max_consecutive+1 (d.h. wenn alle 1 sind).
    """
    expr = gp.LinExpr()

    # y[t,s] = 1 wenn Lehrer t in Slot s überhaupt unterrichtet
    y = m.addVars(teachers_id_list, list(slots), vtype=GRB.BINARY, name="teach_any")

    for t in teachers_id_list:
        for s in slots:
            m.addConstr(
                y[t, s] == gp.quicksum(x[s, t, c, r] for c in courses_id_list for r in rooms_id_list),
                name=f"teach_any_def[{t},{s}]"
            )

    window_len = max_consecutive + 1
    for day in days:
        day_slots = list(day)
        for t in teachers_id_list:
            for i in range(0, len(day_slots) - window_len + 1):
                win = day_slots[i:i + window_len]
                # v=1 wenn in diesem Fenster alle Slots belegt sind -> Überschreitung (max_consecutive+1 am Stück)
                v = m.addVar(vtype=GRB.BINARY, name=f"teach_consec_violation[{t},{day_slots[i]}]")
                # sum(y) in Fenster ist integer 0..window_len
                m.addConstr(
                    v >= gp.quicksum(y[t, s] for s in win) - max_consecutive,
                    name=f"teach_consec_link[{t},{day_slots[i]}]"
                )
                expr += v

    return weight * expr


def add_teacher_min_teaching_days_objective(
    m: gp.Model,
    x,
    slots,
    days,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    weight: float = 1.0,
):
    """
    Soft: Dozenten sollen an möglichst wenigen Tagen unterrichten.
    """
    expr = gp.LinExpr()

    # y[t,s] = 1 wenn Lehrer t in Slot s unterrichtet
    y = m.addVars(teachers_id_list, list(slots), vtype=GRB.BINARY, name="teach_any2")
    for t in teachers_id_list:
        for s in slots:
            m.addConstr(
                y[t, s] == gp.quicksum(x[s, t, c, r] for c in courses_id_list for r in rooms_id_list),
                name=f"teach_any2_def[{t},{s}]"
            )

    teach_day = m.addVars(teachers_id_list, range(len(days)), vtype=GRB.BINARY, name="teach_day")
    for d_idx, day in enumerate(days):
        day_slots = list(day)
        for t in teachers_id_list:
            # teach_day[t,d] >= y[t,s] für alle s im Tag
            for s in day_slots:
                m.addConstr(
                    teach_day[t, d_idx] >= y[t, s],
                    name=f"teach_day_link[{t},{d_idx},{s}]"
                )
            expr += teach_day[t, d_idx]

    return weight * expr

def add_semester_max_classes_per_day_objective(
    m: gp.Model,
    x,
    semesters,
    course_by_id,
    slots,
    days,
    teachers_id_list,
    rooms_id_list,
    courses_id_list,
    max_classes_per_day: int = 3,
    weight: float = 1.0,
):
    """
    Soft: Pro Semester soll es nicht mehr als max_classes_per_day Veranstaltungen am Tag geben.
    Penalty = Überschreitung.
    """
    expr = gp.LinExpr()

    # Kurse je Semester sammeln (IDs)
    courses_by_sem = build_courses_by_semester(semesters, courses_id_list, course_by_id)

    for sem in semesters:
        sem_courses = courses_by_sem.get(sem, [])
        if not sem_courses:
            continue

        for d_idx, day in enumerate(days):
            day_slots = list(day)

            # classes_count ist Summe der aktiven Belegungen dieses Semesters über die Slots des Tages
            # da pro Slot im Semester <= 1, zählt das wirklich "Anzahl Veranstaltungen am Tag"
            classes_count = gp.quicksum(
                gp.quicksum(
                    x[s, t, c, r]
                    for t in teachers_id_list
                    for r in rooms_id_list
                )
                for s in day_slots
                for c in sem_courses
            )

            # Slack für Überschreitung
            slack = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name=f"sem_day_excess[{sem},{d_idx}]")
            m.addConstr(
                slack >= classes_count - max_classes_per_day,
                name=f"sem_day_excess_constr[{sem},{d_idx}]"
            )
            expr += slack

    return weight * expr

def add_semester_avoid_early_slots_objective(
    m: gp.Model,
    x,
    semesters,
    course_by_id,
    early_slots: set[int],
    teachers_id_list,
    rooms_id_list,
    courses_id_list,
    target_semesters: set = None,
    weight: float = 1.0,
):
    """
    Soft: Bestimmte Semester sollen frühe Slots vermeiden.
    early_slots: Menge von Slot-IDs, die als "früh" gelten (z.B. {1,8,15,18,25,...} oder auch +1)
    target_semesters: wenn gesetzt, nur diese Semester bestrafen; sonst alle.
    """
    expr = gp.LinExpr()

    if target_semesters is None:
        target_semesters = set(semesters)

    courses_by_sem = build_courses_by_semester(semesters, courses_id_list, course_by_id)

    for sem in target_semesters:
        sem_courses = courses_by_sem.get(sem, [])
        if not sem_courses:
            continue

        for s in early_slots:
            # Penalty, falls im Semester in einem early-slot etwas liegt
            expr += gp.quicksum(
                x[s, t, c, r]
                for c in sem_courses
                for t in teachers_id_list
                for r in rooms_id_list
            )

    return weight * expr

def add_course_room_and_building_stability_objective(
    m: gp.Model,
    x,
    courses_id_list,
    slots,
    teachers_id_list,
    rooms_id_list,
    room_by_id,
    weight_room: float = 0.2,
    weight_building: float = 0.2,
):
    """
    Soft: Kurs soll möglichst im selben Raum / Gebäude stattfinden (bei Mehrfachterminen).
    Penalty: (#Räume verwendet - 1) + (#Gebäude verwendet - 1)
    """
    expr = gp.LinExpr()

    buildings = sorted({room_by_id[r].address for r in rooms_id_list}, key=lambda v: str(v))
    rooms_by_building = {b: [r for r in rooms_id_list if room_by_id[r].address == b] for b in buildings}

    # room_used[c,r] = 1, wenn Kurs c mindestens einmal in Raum r liegt
    room_used = m.addVars(courses_id_list, rooms_id_list, vtype=GRB.BINARY, name="course_room_used")
    # building_used[c,b] = 1, wenn Kurs c mindestens einmal in Gebäude b liegt
    building_used = m.addVars(courses_id_list, buildings, vtype=GRB.BINARY, name="course_building_used")

    for c in courses_id_list:
        # Link room_used >= x
        for r in rooms_id_list:
            for s in slots:
                for t in teachers_id_list:
                    m.addConstr(
                        room_used[c, r] >= x[s, t, c, r],
                        name=f"course_room_used_link[{c},{r},{s},{t}]"
                    )

        # building_used >= sum der room_used in building (oder >= x direkt)
        for b in buildings:
            for r in rooms_by_building[b]:
                m.addConstr(
                    building_used[c, b] >= room_used[c, r],
                    name=f"course_building_used_link[{c},{b},{r}]"
                )

        # Penalty: Sum(room_used) - 1 und Sum(building_used) - 1
        rooms_count = gp.quicksum(room_used[c, r] for r in rooms_id_list)
        buildings_count = gp.quicksum(building_used[c, b] for b in buildings)

        expr += weight_room * (rooms_count - 1)
        expr += weight_building * (buildings_count - 1)

    return expr

def add_teacher_back_to_back_building_change_objective(
    m: gp.Model,
    x,
    slots,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    room_by_id,
    weight: float = 0.5,
):
    """
    Soft: Dozent soll nicht in zwei aufeinanderfolgenden Slots in unterschiedlichen Gebäuden sein.
    Penalty pro (t, s->s+1), wenn building(s) != building(s+1).
    """
    expr = gp.LinExpr()

    buildings = sorted({room_by_id[r].address for r in rooms_id_list}, key=lambda v: str(v))
    rooms_by_building = {b: [r for r in rooms_id_list if room_by_id[r].address == b] for b in buildings}

    # y[t,s,b] = 1 wenn Lehrer t in Slot s in Gebäude b lehrt
    y = m.addVars(teachers_id_list, list(slots), buildings, vtype=GRB.BINARY, name="teach_building")

    for t in teachers_id_list:
        for s in slots:
            # In jedem Slot kann Lehrer t in höchstens 1 Gebäude sein.
            # Definiere y[t,s,b] = Summe der x in Räumen dieses Gebäudes.
            for b in buildings:
                m.addConstr(
                    y[t, s, b] == gp.quicksum(
                        x[s, t, c, r]
                        for c in courses_id_list
                        for r in rooms_by_building[b]
                    ),
                    name=f"teach_building_def[{t},{s},{b}]"
                )

    # AND-Vars für Wechsel b1->b2 in aufeinanderfolgenden Slots
    for t in teachers_id_list:
        for s in slots:
            s_next = s + 1
            if s_next not in slots:
                continue

            for b1 in buildings:
                for b2 in buildings:
                    if b1 == b2:
                        continue
                    z = m.addVar(vtype=GRB.BINARY, name=f"bchange[{t},{s},{b1}->{b2}]")
                    m.addConstr(z <= y[t, s, b1], name=f"bchange_le1[{t},{s},{b1},{b2}]")
                    m.addConstr(z <= y[t, s_next, b2], name=f"bchange_le2[{t},{s},{b1},{b2}]")
                    m.addConstr(z >= y[t, s, b1] + y[t, s_next, b2] - 1, name=f"bchange_ge[{t},{s},{b1},{b2}]")
                    expr += z

    return weight * expr

def add_semester_single_class_day_objective(
    m,
    x,
    semesters,
    courses_id_list,
    course_by_id,
    teachers_id_list,
    rooms_id_list,
    days,
    weight: float = 1.0,
):
    """
    Soft: Ein Tag mit genau 1 Termin für ein Semester ist unpraktisch => Penalty.
    """
    expr = gp.LinExpr()
    sem_courses = build_courses_by_semester(semesters, courses_id_list, course_by_id)

    for sem in semesters:
        sc = sem_courses.get(sem, [])
        if not sc:
            continue

        for d_idx, day in enumerate(days):
            day_slots = list(day)

            # day_load = Summe aller Belegungen dieses Semesters am Tag
            # (bei no_semester_overlapping ist das pro Slot <= 1 und zählt "Anzahl Veranstaltungen")
            day_load = gp.quicksum(
                x[s, t, c, r]
                for s in day_slots
                for c in sc
                for t in teachers_id_list
                for r in rooms_id_list
            )

            has_any = m.addVar(vtype=GRB.BINARY, name=f"sem_has_any[{sem},{d_idx}]")
            has_two = m.addVar(vtype=GRB.BINARY, name=f"sem_has_two[{sem},{d_idx}]")
            single = m.addVar(vtype=GRB.BINARY, name=f"sem_single_day[{sem},{d_idx}]")

            M = len(day_slots)

            # has_any = 1 <=> day_load >= 1
            m.addConstr(day_load <= M * has_any, name=f"sem_has_any_ub[{sem},{d_idx}]")
            m.addConstr(day_load >= has_any,      name=f"sem_has_any_lb[{sem},{d_idx}]")

            # has_two = 1 <=> day_load >= 2
            m.addConstr(day_load <= 1 + M * has_two, name=f"sem_has_two_ub[{sem},{d_idx}]")
            m.addConstr(day_load >= 2 * has_two,     name=f"sem_has_two_lb[{sem},{d_idx}]")

            # single = has_any - has_two
            m.addConstr(single == has_any - has_two, name=f"sem_single_def[{sem},{d_idx}]")

            expr += single

    return weight * expr

def add_teacher_min_free_days_objective(
    m,
    x,
    slots,
    days,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    min_free_days: int = 1,
    weight: float = 1.0,
    teach_any=None,
):
    """
    Soft: Lehrer sollen mindestens min_free_days frei haben.
    Penalty falls sie zu vielen Tagen unterrichten.
    """
    if teach_any is None:
        teach_any = build_teacher_teach_any(m, x, slots, teachers_id_list, courses_id_list, rooms_id_list, name="teach_any_free")

    num_days = len(days)
    max_teaching_days = max(0, num_days - min_free_days)

    expr = gp.LinExpr()
    day_on = m.addVars(teachers_id_list, range(num_days), vtype=GRB.BINARY, name="t_day_on_free")

    for d_idx, day in enumerate(days):
        day_slots = list(day)
        for t in teachers_id_list:
            for s in day_slots:
                m.addConstr(day_on[t, d_idx] >= teach_any[t, s], name=f"t_day_on_free_ge[{t},{d_idx},{s}]")

    for t in teachers_id_list:
        teaching_days = gp.quicksum(day_on[t, d] for d in range(num_days))
        excess = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name=f"t_excess_teaching_days[{t}]")
        m.addConstr(excess >= teaching_days - max_teaching_days, name=f"t_excess_teaching_days_lb[{t}]")
        expr += excess

    return weight * expr

def add_room_load_balancing_objective(
    m,
    x,
    slots,
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    weight: float = 0.1,
):
    """
    Soft: Balanciere Raumauslastung, indem der maximale Load eines Raums minimiert wird.
    load[r] = Anzahl Assignments in Raum r.
    max_load >= load[r] für alle r. Objective: min max_load.
    """
    load = {}
    for r in rooms_id_list:
        load[r] = gp.quicksum(
            x[s, t, c, r]
            for s in slots
            for t in teachers_id_list
            for c in courses_id_list
        )

    max_load = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="max_room_load")
    for r in rooms_id_list:
        m.addConstr(max_load >= load[r], name=f"max_room_load_ge[{r}]")

    return weight * max_load

def add_priority_weighted_early_slot_objective(
    m,
    x,
    early_slots: set[int],
    teachers_id_list,
    courses_id_list,
    rooms_id_list,
    course_by_id,
    weight: float = 1.0,
    default_priority: float = 1.0,
):
    """
    Soft: Early slots sind schlimmer für wichtige Kurse.
    Penalty = priority[c] * x in early slots.
    """
    expr = gp.LinExpr()

    for s in early_slots:
        for t in teachers_id_list:
            for c in courses_id_list:
                pr = getattr(course_by_id[c], "priority", default_priority)
                for r in rooms_id_list:
                    expr += pr * x[s, t, c, r]

    return weight * expr

def add_lecture_before_tutorial_objective(
    m,
    x,
    slots,
    teachers_id_list,
    rooms_id_list,
    pairs,  # list[tuple[lecture_id, tutorial_id]]
    weight: float = 1.0,
    course_occ=None,
):
    """
    Soft: Übung soll nach Vorlesung stattfinden.
    Penalty für jede Kombination (tutorial_slot < lecture_slot).
    Achtung: O(|pairs| * |slots|^2). Nur für wenige Paare nutzen.
    """
    slots_list = list(slots)
    if course_occ is None:
        # Kurse aus pairs extrahieren
        course_ids = sorted({cid for p in pairs for cid in p})
        course_occ = build_course_occ(m, x, slots_list, teachers_id_list, course_ids, rooms_id_list, name="occ_pair")

    expr = gp.LinExpr()

    for lecture_id, tutorial_id in pairs:
        for s_tut in slots_list:
            for s_lect in slots_list:
                if s_lect <= s_tut:
                    continue  # wir bestrafen nur lecture nach tutorial -> lecture_slot > tutorial_slot
                z = m.addVar(vtype=GRB.BINARY, name=f"viol_lect_after_tut[{lecture_id},{tutorial_id},{s_tut},{s_lect}]")
                m.addConstr(z <= course_occ[tutorial_id, s_tut], name=f"viol1[{lecture_id},{tutorial_id},{s_tut},{s_lect}]")
                m.addConstr(z <= course_occ[lecture_id, s_lect],   name=f"viol2[{lecture_id},{tutorial_id},{s_tut},{s_lect}]")
                m.addConstr(z >= course_occ[tutorial_id, s_tut] + course_occ[lecture_id, s_lect] - 1,
                            name=f"viol3[{lecture_id},{tutorial_id},{s_tut},{s_lect}]")
                expr += z

    return weight * expr



def add_last_two_slots_objective(
    x,
    semesters,
    courses_id_list,
    course_by_id,
    teachers_id_list,
    rooms_id_list,
    days,
    weight: float = 1.0,
):

    obj = gp.LinExpr()

    courses_by_sem = build_courses_by_semester(semesters,courses_id_list,course_by_id)

    for sem in semesters:
        sem_courses = courses_by_sem[sem]

        for day in days:
            slots = list(day)

            if len(slots) < 2:
                continue

            pre_last = slots[-2]
            last = slots[-1]


            obj += weight * gp.quicksum(
                x[pre_last, t, c, r]
                for c in sem_courses
                for t in teachers_id_list
                for r in rooms_id_list
            )

            obj += 10 * weight * gp.quicksum(
                x[last, t, c, r]
                for c in sem_courses
                for t in teachers_id_list
                for r in rooms_id_list
            )

    return obj
