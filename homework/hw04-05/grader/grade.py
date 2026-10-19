"""Автопроверка ДЗ 4–5 «Матожидание и дисперсия, ЗБЧ и ЦПТ».

Запускает каждый ноутбук с нуля, затем в том же ядре выполняет проверки
и собирает баллы в таблицу. Части A и B (задачи 1–6, 60 баллов) проверяются
автоматически. Задачу 7 (эксперимент, 40 баллов) оценивает преподаватель;
проверка только сообщает, сколько в ней наблюдений, и ищет одинаковые данные
в разных работах.

    python grade.py <ноутбук или папка> [...] --out grades

Результат в папке --out:
    summary.md      — таблица баллов и комментарии (её же workflow выводит в отчёт)
    grades.csv      — баллы по пунктам для ведомости
    <файл>.json     — подробный результат по каждому ноутбуку
"""
import argparse
import csv
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import nbformat
from nbclient import NotebookClient

# >>> SHARED (совпадает с ячейкой параметров в ноутбуке ДЗ, не редактировать отдельно)
SHARED = r'''
import numpy as np

N_VARIANTS = 40


def params(variant):
    """Параметры варианта. Не изменяйте эту функцию."""
    v = int(variant)
    r4 = 0.5 + 0.04 * (v % 6)
    values4 = np.r_[np.arange(1, 9), 20]
    w4 = np.r_[r4 ** np.arange(8), 0.0]
    w4 = w4 / w4.sum() * (1 - (0.02 + 0.005 * (v % 4)))
    w4[-1] = 0.02 + 0.005 * (v % 4)
    probs4 = np.round(w4, 6) / np.round(w4, 6).sum()
    n4 = 40 + 5 * (v % 5)
    mu4 = float(values4 @ probs4)
    sd4 = float(np.sqrt(((values4 - mu4) ** 2) @ probs4))
    return {
        # задача 2 (мс)
        "q2": round(0.15 + 0.05 * (v % 6), 2),   # доля ответов из кэша
        "c2": 3 + v % 5,                          # время ответа из кэша
        "d2": 15 + 5 * (v % 4),                   # минимальное время обработки
        "mu2": 60 + 10 * (v % 7),                 # средняя добавка к d2
        "T2": 120 + 20 * (v % 5),                 # таймаут клиента
        # задача 4: число товаров в заказе
        "values4": values4,
        "probs4": probs4,
        "n4": n4,                                 # заказов за смену
        "s4": int(round(n4 * mu4 + (2.0 + 0.1 * (v % 5)) * sd4 * np.sqrt(n4))),   # порог числа товаров
        "T4": 400 + 25 * (v % 4),                 # план отгрузки
    }


def make_data(variant):
    """Данные варианта для задач 3, 5 и 6. Не изменяйте эту функцию."""
    v = int(variant)
    r = np.random.default_rng(30_000 + v)
    # задача 3: рекламные кампании в трёх регионах
    n = 600
    region = r.choice(np.array(["Север", "Центр", "Юг"]), size=n, p=[0.3, 0.4, 0.3])
    g = np.searchsorted(np.array(["Север", "Центр", "Юг"]), region)
    ads = np.round(r.normal(np.array([20.0, 40.0, 60.0])[g] + v % 5, 5 + v % 3), 2)
    beta = 1.5 + 0.1 * (v % 10)
    sales = np.round(np.array([320.0, 210.0, 100.0])[g] + beta * ads + r.normal(0, 12 + v % 6, n), 2)
    is_test = (r.random(n) < 0.03).astype(int)
    ads = np.where(is_test == 1, np.round(r.uniform(150, 400, n), 2), ads)
    sales = np.where(is_test == 1, 0.0, sales)
    campaigns = {"region": region, "ads": ads, "sales": sales, "is_test": is_test}
    # задача 5: время ответа сервиса, мс (быстрые запросы и запросы через медленную базу)
    n5 = 300 + 20 * (v % 6)
    slow = r.random(n5) < 0.12 + 0.01 * (v % 5)
    latency = np.round(np.where(slow, r.lognormal(np.log(320 + 20 * (v % 4)), 0.5, n5),
                                r.lognormal(np.log(70 + 5 * (v % 6)), 0.45, n5)), 1)
    # задача 6: заболеваемость по районам
    m6 = 500
    pop = np.round(np.exp(r.uniform(np.log(200), np.log(100_000), m6))).astype(int)
    p6 = 0.008 + 0.001 * (v % 5)
    pr = np.full(m6, p6)
    hot = r.choice(np.where(pop > 20_000)[0], 4, replace=False)
    pr[hot] *= 1.5
    districts = {"district": np.arange(1, m6 + 1), "population": pop, "cases": r.binomial(pop, pr)}
    return campaigns, latency, districts
'''
# <<< SHARED

# Код проверки выполняется в ядре ноутбука после всех ячеек студента.
CHECK = r'''
def __hw0405_check(result_path, shared):
    import json
    import numpy as np
    from scipy import stats as _st

    G = globals()
    ns = {}
    exec(shared, ns)
    items = []

    def add(task, name, pts, fn):
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"{type(exc).__name__}: {exc}"
        items.append({"task": task, "name": name, "max": pts, "score": pts if ok else 0.0, "msg": "" if ok else msg})

    def get(name):
        if name not in G:
            raise NameError(f"переменная {name} не найдена")
        v = G[name]
        if v is Ellipsis:
            raise ValueError(f"{name} не заполнена (стоит ...)")
        return v

    def close(name, expected, rtol=1e-6, atol=1e-9):
        v = np.asarray(get(name), dtype=float)
        exp = np.asarray(expected, dtype=float)
        if v.shape != exp.shape:
            return False, f"{name}: форма {v.shape}, ожидалась {exp.shape}"
        if np.allclose(v, exp, rtol=rtol, atol=atol):
            return True, ""
        shown = np.round(v, 6).tolist() if v.size <= 6 else f"массив, первые значения {np.round(v.ravel()[:4], 4).tolist()}"
        return False, f"{name} = {shown} — неверно"

    def ref_moments(x, w):
        x = np.asarray(x, float); w = np.asarray(w, float); w = w / w.sum()
        c = x[np.argmax(w)]
        y = x - c
        m = (y * w).sum()
        z = y - m
        var = (z ** 2 * w).sum()
        skew = (z ** 3 * w).sum() / var ** 1.5 if var > 0 else 0.0
        return m + c, var, skew

    student = str(G.get("STUDENT", "")).strip()
    group = str(G.get("GROUP", "")).strip()
    try:
        V = int(G.get("VARIANT", 0))
    except Exception:
        V = 0
    valid = 1 <= V <= ns["N_VARIANTS"]

    # задача 7: только сведения для преподавателя
    exp = {"title": str(G.get("EXP_TITLE", "")).strip(), "n": 0, "hash": ""}
    try:
        data = np.asarray([float(t) for t in G.get("EXP_DATA", [])], dtype=float)
        exp["n"] = int(data.size)
        if data.size:
            exp["hash"] = __import__("hashlib").md5(np.round(data, 6).tobytes()).hexdigest()
            exp["mean"] = float(data.mean())
    except Exception as exc:
        exp["error"] = f"EXP_DATA не читается как список чисел: {exc}"

    if valid:
        P = ns["params"](V)
        camp, lat, dist = ns["make_data"](V)

        # ---- задача 1: функция moments на скрытых тестах
        def mtest(cases, what):
            def run():
                f = get("moments")
                for x, w in cases:
                    exp_ = ref_moments(x, w)
                    got = f(np.array(x, dtype=float), np.array(w, dtype=float))
                    got = [float(t) for t in got]
                    if len(got) != 3:
                        return False, "moments должна возвращать (mean, var, skew)"
                    tol = [1e-9 * max(1, abs(exp_[0])), 1e-6 * max(exp_[1], 1e-12), 1e-5]
                    if any(abs(a - b) > t for a, b, t in zip(got, exp_, tol)):
                        return False, f"{what}: неверно на values={np.round(x[:6], 3).tolist()}…"
                return True, ""
            return run
        rg = np.random.default_rng(1234 + V)
        basic = [(rg.normal(0, 10, size=k), rg.dirichlet(np.ones(k))) for k in (2, 5, 9)]
        unnorm = []
        for k in (4, 7):
            x = rg.choice(np.arange(-5, 6), size=k - 1, replace=False).astype(float)
            x = np.r_[x, x[0]]                               # повторяющееся значение
            unnorm.append((x, rg.integers(0, 20, size=k).astype(float) + np.r_[1, np.zeros(k - 1)]))
        big = [(1e9 + rg.integers(0, 5, size=6).astype(float), rg.integers(1, 9, size=6).astype(float)),
               (-3e8 + rg.normal(0, 0.5, size=8), rg.dirichlet(np.ones(8)))]
        skewc = [(np.array([0.0, 1.0, 10.0]), np.array([0.5, 0.45, 0.05])), (np.array([-4.0, 0.0, 1.0]), np.array([0.1, 0.3, 0.6]))]
        add(1, "1.1 moments: обычные распределения", 2.5, mtest(basic, "обычный случай"))
        add(1, "1.2 moments: ненормированные веса, повторы, нулевые веса", 2.5, mtest(unnorm, "ненормированные веса"))
        add(1, "1.3 moments: большие значения (устойчивость)", 2.5, mtest(big, "значения порядка 1e9"))
        add(1, "1.4 moments: асимметрия", 2.5, mtest(skewc, "асимметрия"))

        # ---- задача 2: смешанное распределение с таймаутом
        q, c, d, mu, T = P["q2"], P["c2"], P["d2"], P["mu2"], P["T2"]
        lam, t0 = 1 / mu, T - d
        e1 = (1 - np.exp(-lam * t0)) / lam
        e2 = 2 / lam ** 2 * (1 - np.exp(-lam * t0) * (1 + lam * t0))
        EM, EM2 = d + e1, d * d + 2 * d * e1 + e2
        EX = q * c + (1 - q) * EM
        DX = q * c * c + (1 - q) * EM2 - EX ** 2
        add(2, "2.1 p2_timeout", 2.5, lambda: close("p2_timeout", (1 - q) * np.exp(-lam * t0)))
        add(2, "2.2 EX2", 3.75, lambda: close("EX2", EX))
        add(2, "2.3 DX2", 3.75, lambda: close("DX2", DX))

        # ---- задача 3: кампании, Симпсон
        keep = camp["is_test"] == 0
        reg, x3, y3 = camp["region"][keep], camp["ads"][keep], camp["sales"][keep]
        add(3, "3.1 corr3_all", 2.5, lambda: close("corr3_all", np.corrcoef(x3, y3)[0, 1]))

        def t32():
            got = dict(get("corr3_by_region"))
            exp_ = {g: np.corrcoef(x3[reg == g], y3[reg == g])[0, 1] for g in np.unique(reg)}
            if set(map(str, got)) != set(exp_):
                return False, f"ключи {sorted(map(str, got))}, ожидались {sorted(exp_)}"
            bad = [g for g in exp_ if not np.isclose(float(got[g]), exp_[g], rtol=1e-6)]
            return (not bad), f"неверно для регионов {bad}"
        add(3, "3.2 corr3_by_region", 2.5, t32)
        xc, yc = x3.copy(), y3.copy()
        for g in np.unique(reg):
            xc[reg == g] -= x3[reg == g].mean(); yc[reg == g] -= y3[reg == g].mean()
        add(3, "3.3 slope3_within", 2.5, lambda: close("slope3_within", (xc * yc).sum() / (xc ** 2).sum()))
        ss_tot = ((y3 - y3.mean()) ** 2).sum()
        ss_between = sum((reg == g).sum() * (y3[reg == g].mean() - y3.mean()) ** 2 for g in np.unique(reg))
        add(3, "3.4 eta2_3", 2.5, lambda: close("eta2_3", ss_between / ss_tot))

        # ---- задача 4: точная сумма против ЦПТ
        vals, probs = P["values4"], P["probs4"]
        pmf1 = np.zeros(vals.max() + 1); pmf1[vals] = probs
        mu4 = vals @ probs; sd4 = np.sqrt(((vals - mu4) ** 2) @ probs)
        pm = np.array([1.0])
        for _ in range(P["n4"]):
            pm = np.convolve(pm, pmf1)
        add(4, "4.1 p4_exact", 3.75, lambda: close("p4_exact", pm[P["s4"]:].sum(), rtol=1e-6, atol=1e-12))
        add(4, "4.2 p4_clt", 2.5, lambda: close("p4_clt", _st.norm.sf((P["s4"] - 0.5 - P["n4"] * mu4) / (sd4 * np.sqrt(P["n4"]))), rtol=1e-6, atol=1e-12))
        pm, nmin = np.array([1.0]), 0
        while pm[P["T4"]:].sum() < 0.95:
            pm = np.convolve(pm, pmf1); nmin += 1

        def t43():
            got = float(get("n4_min"))
            if got != nmin:
                return False, f"n4_min = {got:g} — неверно" + (" (похоже на ответ по ЦПТ, а нужен точный)" if abs(got - nmin) <= 3 else "")
            return True, ""
        add(4, "4.3 n4_min", 3.75, t43)

        # ---- задача 5: бутстреп
        x5 = np.asarray(lat, float); n5 = x5.size
        z = _st.norm.ppf(0.975)
        m5, h5 = x5.mean(), z * x5.std(ddof=1) / np.sqrt(n5)
        rb = np.random.default_rng(777 + V)
        med_b, p95_b, max_b = [], [], []
        for _ in range(10):
            xb = x5[rb.integers(0, n5, size=(5_000, n5))]
            med_b.append(np.median(xb, axis=1)); p95_b.append(np.quantile(xb, 0.95, axis=1)); max_b.append(xb.max(axis=1))
        med_b, p95_b, max_b = map(np.concatenate, (med_b, p95_b, max_b))
        se_med = med_b.std()
        ci_p95 = np.quantile(p95_b, [0.025, 0.975])
        sh_max = np.mean(max_b == x5.max())
        def t51():
            for nm, val in [("mean5", m5), ("median5", np.median(x5)), ("p95_5", np.quantile(x5, 0.95))]:
                ok, msg = close(nm, val)
                if not ok:
                    return ok, msg
            return True, ""
        add(5, "5.1 mean5, median5, p95_5", 1.25, t51)

        def t52():
            ok, msg = close("ci5_mean", [m5 - h5, m5 + h5])
            if not ok:
                got = np.asarray(get("ci5_mean"), float).ravel()
                if got.size == 2 and np.allclose(got, [m5 - 2 * h5 / z, m5 + 2 * h5 / z], rtol=1e-6):
                    msg += " (похоже на коэффициент 2 вместо 1,96)"
            return ok, msg
        add(5, "5.2 ci5_mean", 2.5, t52)

        def t53a():
            got = float(get("se5_median"))
            if abs(got - se_med) <= 0.1 * se_med:
                return True, ""
            norm_f = 1.2533 * x5.std(ddof=1) / np.sqrt(n5)
            hint = " (это формула для нормальных данных, нужен бутстреп)" if abs(got - norm_f) < 0.02 * norm_f else ""
            return False, f"se5_median = {got:.4g}, ожидалось около {se_med:.4g}" + hint
        add(5, "5.3 se5_median (бутстреп)", 1.875, t53a)

        def t53b():
            got = np.asarray(get("ci5_p95"), float).ravel()
            # хвост бутстреп-распределения p95 дискретный, поэтому сравниваем ранги, а не значения
            def rank_ok(val, q):
                return np.mean(p95_b < val) - 1e-9 <= q + 0.015 and np.mean(p95_b <= val) + 1e-9 >= q - 0.015
            if got.size == 2 and rank_ok(min(got), 0.025) and rank_ok(max(got), 0.975):
                return True, ""
            return False, f"ci5_p95 = {np.round(got, 2).tolist()}, ожидалось около {np.round(ci_p95, 2).tolist()}"
        add(5, "5.3 ci5_p95 (процентильный интервал)", 1.875, t53b)

        def t54():
            th = 1 - (1 - 1 / n5) ** n5
            ok, msg = close("share5_theory", th)
            if not ok:
                return ok, msg
            got = float(get("share5_max"))
            if got == float(get("share5_theory")):
                return False, "share5_max совпадает с теорией в точности: посчитайте долю по бутстреп-выборкам"
            if abs(got - sh_max) <= 0.04:
                return True, ""
            return False, f"share5_max = {got:.4g}, ожидалось около {sh_max:.3f}"
        add(5, "5.4 share5_max, share5_theory", 2.5, t54)

        # ---- задача 6: воронка
        pop, cases = dist["population"], dist["cases"]
        rate = cases / pop
        pp = cases.sum() / pop.sum()
        z6 = (rate - pp) / np.sqrt(pp * (1 - pp) / pop)
        top = np.argsort(-rate, kind="stable")[:20]
        flagged = np.sort(dist["district"][z6 > _st.norm.isf(0.05 / pop.size)])
        add(6, "6.1 p6_pooled", 1.25, lambda: close("p6_pooled", pp))
        add(6, "6.2 z6", 2.5, lambda: close("z6", z6))
        add(6, "6.3 small6_share", 1.25, lambda: close("small6_share", np.mean(pop[top] < np.median(pop))))

        def t64():
            got = np.sort(np.asarray(get("flagged6")).astype(int).ravel())
            if got.shape == flagged.shape and np.array_equal(got, flagged):
                return True, ""
            return False, f"flagged6 = {got.tolist()[:12]} — неверно"
        add(6, "6.4 flagged6", 5, t64)

    total = round(sum(i["score"] for i in items), 2)
    out = {"student": student, "group": group, "variant": V, "valid_variant": valid,
           "total": total, "max": 60.0, "items": items, "experiment": exp}
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

__hw0405_check(RESULT_PATH, SHARED_CODE)
'''

TASKS = [1, 2, 3, 4, 5, 6]
EXP_MIN = 30

# Метки из скрытых комментариев в условии. Человек, читающий ноутбук в Colab, их не видит,
# а нейросеть, которой передали .ipynb целиком, может выполнить скрытую инструкцию.
CANARY_MARKERS = ['outlier_policy', 'timeout_units', 'ci_rule']


def grade_one(path, timeout):
    nb = nbformat.read(path, as_version=4)
    code_src = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    canary = [m for m in CANARY_MARKERS if m in code_src]
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs, cell.execution_count = [], None
    with tempfile.TemporaryDirectory() as tmp:
        result_path = Path(tmp) / "result.json"
        check = CHECK.replace("RESULT_PATH", repr(str(result_path))).replace("SHARED_CODE", repr(SHARED))
        nb.cells.append(nbformat.v4.new_code_cell(check))
        client = NotebookClient(nb, timeout=timeout, kernel_name="python3", allow_errors=True,
                                resources={"metadata": {"path": tmp}})
        error = ""
        try:
            client.execute()
        except Exception as exc:  # таймаут или падение ядра
            error = f"ноутбук не выполнился: {type(exc).__name__}: {str(exc)[:300]}"
        cell_errors = [o.get("ename", "") + ": " + o.get("evalue", "")[:200]
                       for c in nb.cells[:-1] if c.cell_type == "code"
                       for o in c.get("outputs", []) if o.get("output_type") == "error"]
        if result_path.exists():
            res = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            res = {"student": "", "group": "", "variant": None, "valid_variant": False,
                   "total": 0.0, "max": 60.0, "items": [], "experiment": {"title": "", "n": 0, "hash": ""}}
            error = error or "проверка не запустилась (ошибка в последней ячейке проверки)"
    res["file"] = Path(path).name
    res["error"] = error
    res["cell_errors"] = cell_errors
    res["canary"] = canary
    return res


def task_score(res, t):
    return round(sum(i["score"] for i in res["items"] if i["task"] == t), 2)


def mark_duplicates(results):
    by_hash = defaultdict(list)
    for r in results:
        h = r["experiment"].get("hash")
        if h and r["experiment"]["n"] >= 10:
            by_hash[h].append(r["file"])
    for r in results:
        h = r["experiment"].get("hash")
        r["experiment"]["same_as"] = [f for f in by_hash.get(h, []) if f != r["file"]] if h else []


def exp_cell(r):
    e = r["experiment"]
    s = f"n = {e['n']}"
    if e["n"] < EXP_MIN:
        s += " ❗"
    if e.get("same_as"):
        s += " ⚠️ дубль"
    return s


def write_reports(results, out):
    out.mkdir(parents=True, exist_ok=True)
    for r in results:
        (out / (Path(r["file"]).stem + ".json")).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(out / "grades.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["file", "student", "group", "variant"] + [f"task{t}" for t in TASKS]
                    + ["auto_total", "exp_title", "exp_n", "exp_duplicate_of", "task7_manual", "total", "ai_marker"])
        for r in results:
            e = r["experiment"]
            wr.writerow([r["file"], r["student"], r["group"], r["variant"]] + [task_score(r, t) for t in TASKS]
                        + [r["total"], e.get("title", ""), e["n"], ";".join(e.get("same_as", [])), "", "", ";".join(r["canary"])])

    lines = ["## ДЗ 4–5: результаты автопроверки", "",
             "Задачи 1–6 — автоматически (из 60). Задачу 7 (эксперимент, из 40) оценивает преподаватель: "
             "в `grades.csv` для неё есть пустые колонки `task7_manual` и `total`.", "",
             "| Файл | Студент | Группа | Вариант | " + " | ".join(f"З{t}" for t in TASKS) + " | Авто (из 60) | Эксперимент | Метка ИИ |",
             "|---|---|---|---|" + "---|" * len(TASKS) + "---|---|---|"]
    for r in results:
        lines.append(f"| {r['file']} | {r['student'] or '—'} | {r['group'] or '—'} | {r['variant']} | "
                     + " | ".join(str(task_score(r, t)) for t in TASKS) + f" | **{r['total']}** | {exp_cell(r)} | "
                     + f"{'⚠️ ' + ', '.join(r['canary']) if r['canary'] else ''} |")
    lines += ["", "### Замечания", ""]
    for r in results:
        notes = []
        if r["error"]:
            notes.append(r["error"])
        if not r["valid_variant"]:
            notes.append("не указан или неверен номер варианта (VARIANT от 1 до 40) — задачи 1–6 не проверялись")
        notes += [f"{i['name']}: {i['msg']}" for i in r["items"] if i["score"] < i["max"]]
        e = r["experiment"]
        if e.get("error"):
            notes.append("задача 7: " + e["error"])
        if not e.get("title"):
            notes.append("задача 7: не заполнена тема EXP_TITLE")
        if e["n"] < EXP_MIN:
            notes.append(f"задача 7: в EXP_DATA {e['n']} наблюдений, нужно не меньше {EXP_MIN}")
        if e.get("same_as"):
            notes.append("задача 7: данные EXP_DATA совпадают с работами " + ", ".join(e["same_as"]))
        if r["canary"]:
            notes.append("в коде есть метка из скрытой инструкции для нейросетей: " + ", ".join(r["canary"]) + " — стоит обсудить на защите")
        if r["cell_errors"]:
            notes.append("ошибки в ячейках: " + "; ".join(r["cell_errors"][:5]))
        if notes:
            lines.append(f"**{r['file']}** ({r['student'] or 'без имени'})")
            lines += [f"- {n}" for n in notes]
            lines.append("")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="ноутбуки или папки с ноутбуками")
    ap.add_argument("--out", default="grades", help="папка для результатов")
    ap.add_argument("--timeout", type=int, default=180, help="лимит на одну ячейку, секунд")
    args = ap.parse_args()

    files = []
    for p in map(Path, args.paths):
        files += sorted(p.rglob("*.ipynb")) if p.is_dir() else [p]
    files = [f for f in files if ".ipynb_checkpoints" not in f.parts]
    if not files:
        print("Ноутбуков для проверки нет")
        write_reports([], Path(args.out))
        return 0

    results = []
    for f in files:
        print(f"Проверяю {f} ...", flush=True)
        r = grade_one(f, args.timeout)
        print(f"  {r['student'] or '—'}, вариант {r['variant']}: {r['total']} / {r['max']}, эксперимент n = {r['experiment']['n']}", flush=True)
        results.append(r)
    mark_duplicates(results)
    write_reports(results, Path(args.out))
    print((Path(args.out) / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
