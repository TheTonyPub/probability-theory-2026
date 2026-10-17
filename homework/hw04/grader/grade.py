"""Автопроверка ДЗ 4 «Математическое ожидание и дисперсия».

Запускает каждый ноутбук с нуля, затем в том же ядре выполняет проверки
и собирает баллы в таблицу.

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
    r = np.random.default_rng(700 + v)
    corr = np.array([[1.0, 0.1 + 0.1 * (v % 5), -0.3 + 0.1 * (v % 4)],
                     [0.1 + 0.1 * (v % 5), 1.0, 0.1 * (v % 5)],
                     [-0.3 + 0.1 * (v % 4), 0.1 * (v % 5), 1.0]])
    w = r.integers(1, 6, size=3)
    return {
        # задача 1
        "values1": np.array([-2, 0, 1, 3, 5]) + v % 3,
        "weights1": r.integers(1, 10, size=5),
        # задача 2: f(x) = c * x**k на [0; b]
        "k2": 1 + v % 3,
        "b2": 1 + (v // 3) % 3,
        # задача 3
        "N3": 20 + v % 11,
        "m3": 30 + 2 * (v % 9),
        "a3": 2 + v % 3,
        "b3": -(1 + v % 4),
        "DX3": 4.0 + v % 5,
        "DY3": 9.0 - v % 4,
        "rho3": round(-0.6 + 0.1 * (v % 13), 2),
        # задача 5
        "sigma5": np.array([0.02 + 0.002 * (v % 5), 0.03, 0.015 + 0.001 * (v % 7)]),
        "corr5": corr,
        "w5": w / w.sum(),
    }


def make_data(variant):
    """Данные варианта для задачи 4. Не изменяйте эту функцию."""
    v = int(variant)
    r = np.random.default_rng(20_000 + v)
    load = np.round(r.normal(40 + v % 10, 8 + v % 5, size=500), 1)
    latency = np.round(60 + (2 + 0.25 * (v % 9)) * load + r.gamma(4, 10 + v % 7, size=500), 1)
    return load, latency
'''
# <<< SHARED

# Код проверки выполняется в ядре ноутбука после всех ячеек студента.
CHECK = r'''
def __hw04_check(result_path, shared):
    import json
    import numpy as np

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
        return False, f"{name} = {np.round(v, 6).tolist()} — неверно"

    def all_close(names, expected, **kw):
        for n, e in zip(names, expected):
            ok, msg = close(n, e, **kw)
            if not ok:
                return False, msg
        return True, ""

    student = str(G.get("STUDENT", "")).strip()
    group = str(G.get("GROUP", "")).strip()
    try:
        V = int(G.get("VARIANT", 0))
    except Exception:
        V = 0
    valid = 1 <= V <= ns["N_VARIANTS"]

    if valid:
        P = ns["params"](V)
        load, lat = ns["make_data"](V)

        # ---- задача 1
        x1 = P["values1"].astype(float)
        p1 = P["weights1"] / P["weights1"].sum()
        m1 = (x1 * p1).sum()
        d1 = ((x1 - m1) ** 2 * p1).sum()
        add(1, "1.1 probs1", 0.5, lambda: close("probs1", p1))
        add(1, "1.2 EX1, DX1, sd1", 0.5, lambda: all_close(["EX1", "DX1", "sd1"], [m1, d1, np.sqrt(d1)]))

        def t13():
            f = get("moments")
            r = np.random.default_rng(77)
            for _ in range(5):
                vals = r.normal(0, 10, size=r.integers(2, 9))
                pp = r.dirichlet(np.ones(len(vals)))
                mm = (vals * pp).sum()
                dd = ((vals - mm) ** 2 * pp).sum()
                got = f(vals, pp)
                if len(got) != 2 or not np.allclose([float(got[0]), float(got[1])], [mm, dd], rtol=1e-6, atol=1e-9):
                    return False, f"moments неверно на values={np.round(vals, 3).tolist()}"
            return True, ""
        add(1, "1.3 moments", 0.5, t13)
        add(1, "1.4 EX1_cubed", 0.5, lambda: close("EX1_cubed", (x1 ** 3 * p1).sum()))

        # ---- задача 2
        k, b = P["k2"], P["b2"]
        m2 = (k + 1) / (k + 2) * b
        d2 = (k + 1) / (k + 3) * b ** 2 - m2 ** 2
        s2 = np.sqrt(d2)
        F = lambda x: np.clip(x / b, 0, 1) ** (k + 1)
        add(2, "2.1 EX2", 0.5, lambda: close("EX2", m2))
        add(2, "2.2 DX2", 0.5, lambda: close("DX2", d2))
        add(2, "2.3 p2_tail", 1.0, lambda: close("p2_tail", F(m2 - 2 * s2) + 1 - F(m2 + 2 * s2)))

        # ---- задача 3
        N, m = P["N3"], P["m3"]
        a, bb, DX, DY, rho = P["a3"], P["b3"], P["DX3"], P["DY3"], P["rho3"]
        add(3, "3.1 E3_empty", 1.0, lambda: close("E3_empty", N * (1 - 1 / N) ** m))
        add(3, "3.2 D3_indep", 0.5, lambda: close("D3_indep", a ** 2 * DX + bb ** 2 * DY))
        add(3, "3.3 D3_dep", 0.5, lambda: close("D3_dep", a ** 2 * DX + bb ** 2 * DY + 2 * a * bb * rho * np.sqrt(DX * DY)))

        # ---- задача 4
        c = np.cov(load, lat)
        slope = c[0, 1] / c[0, 0]
        rr = np.corrcoef(load, lat)[0, 1]
        add(4, "4.1 mean4, var4", 0.5, lambda: all_close(["mean4", "var4"], [lat.mean(), lat.var(ddof=1)]))
        add(4, "4.2 cov4, corr4", 0.5, lambda: all_close(["cov4", "corr4"], [c[0, 1], rr]))
        add(4, "4.3 slope4, intercept4", 0.5, lambda: all_close(["slope4", "intercept4"], [slope, lat.mean() - slope * load.mean()]))
        add(4, "4.4 r2_4", 0.5, lambda: close("r2_4", rr ** 2))

        # ---- задача 5
        S = P["corr5"] * np.outer(P["sigma5"], P["sigma5"])
        w = P["w5"]
        sd = np.sqrt(w @ S @ w)
        s1, s2_, s12 = S[0, 0], S[1, 1], S[0, 1]
        a_best = (s2_ - s12) / (s1 + s2_ - 2 * s12)
        add(5, "5.1 cov5", 0.5, lambda: close("cov5", S))
        add(5, "5.2 sd5", 0.5, lambda: close("sd5", sd))
        add(5, "5.3 a5_best", 0.5, lambda: close("a5_best", a_best, rtol=1e-4))

        def t54():
            n = int(get("n5"))
            if n < 200_000:
                return False, f"n5 = {n} < 200000"
            v = float(get("sd5_mc"))
            return (abs(v - sd) <= 6 * sd / np.sqrt(2 * n) + 1e-5), f"sd5_mc = {v:.6f} слишком далеко от верного значения"
        add(5, "5.4 sd5_mc", 0.5, t54)

    total = round(sum(i["score"] for i in items), 2)
    out = {"student": student, "group": group, "variant": V, "valid_variant": valid,
           "total": total, "max": 10.0, "items": items}
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

__hw04_check(RESULT_PATH, SHARED_CODE)
'''

TASKS = [1, 2, 3, 4, 5]


def grade_one(path, timeout):
    nb = nbformat.read(path, as_version=4)
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
                   "total": 0.0, "max": 10.0, "items": []}
            error = error or "проверка не запустилась (ошибка в последней ячейке проверки)"
    res["file"] = Path(path).name
    res["error"] = error
    res["cell_errors"] = cell_errors
    return res


def task_score(res, t):
    return round(sum(i["score"] for i in res["items"] if i["task"] == t), 2)


def write_reports(results, out):
    out.mkdir(parents=True, exist_ok=True)
    for r in results:
        (out / (Path(r["file"]).stem + ".json")).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(out / "grades.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["file", "student", "group", "variant"] + [f"task{t}" for t in TASKS] + ["total"])
        for r in results:
            wr.writerow([r["file"], r["student"], r["group"], r["variant"]] + [task_score(r, t) for t in TASKS] + [r["total"]])

    lines = ["## ДЗ 4: результаты автопроверки", "",
             "| Файл | Студент | Группа | Вариант | " + " | ".join(f"З{t}" for t in TASKS) + " | Итого |",
             "|---|---|---|---|" + "---|" * len(TASKS) + "---|"]
    for r in results:
        lines.append(f"| {r['file']} | {r['student'] or '—'} | {r['group'] or '—'} | {r['variant']} | "
                     + " | ".join(str(task_score(r, t)) for t in TASKS) + f" | **{r['total']}** |")
    lines += ["", "### Замечания", ""]
    for r in results:
        notes = []
        if r["error"]:
            notes.append(r["error"])
        if not r["valid_variant"]:
            notes.append("не указан или неверен номер варианта (VARIANT от 1 до 40) — проверка не проводилась")
        notes += [f"{i['name']}: {i['msg']}" for i in r["items"] if i["score"] < i["max"]]
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
        print(f"  {r['student'] or '—'}, вариант {r['variant']}: {r['total']} / {r['max']}", flush=True)
        results.append(r)
    write_reports(results, Path(args.out))
    print((Path(args.out) / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
