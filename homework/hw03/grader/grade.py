"""Автопроверка ДЗ 3 «Случайные величины и распределения».

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

# >>> SHARED (генерируется build_hw.py, не редактировать)
SHARED = r'''
import numpy as np

N_VARIANTS = 40
DIST_NAMES = ["binom", "poisson", "geom", "uniform", "expon", "norm"]


def params(variant):
    """Параметры варианта. Не изменяйте эту функцию."""
    v = int(variant)
    r = np.random.default_rng(500 + v)
    return {
        # задача 1
        "values1": np.array([0, 1, 2, 3, 4]),
        "weights1": r.integers(1, 10, size=5),
        # задача 2: f(x) = c * x**k на [0; b]
        "k2": 1 + v % 3,
        "b2": 1 + (v // 3) % 3,
        # задача 4
        "lam4": 2.5 + 0.25 * (v % 13),
        "scale4": 10 + v,
        # задача 5
        "m5": 2 + v % 3,
        "mean5": 100 + 10 * (v % 7),
        "t5": 200,
    }


def make_data(variant, with_truth=False):
    """Данные варианта для задачи 4. Не изменяйте эту функцию."""
    p = params(variant)
    r = np.random.default_rng(10_000 + int(variant))
    requests_per_minute = r.poisson(p["lam4"], size=600)
    gaps_sec = np.round(r.exponential(p["scale4"], size=800), 2)
    names = [str(x) for x in r.permutation(DIST_NAMES)[:3]]
    mystery = {}
    for label, name in zip("ABC", names):
        if name == "binom":
            s = r.binomial(20, r.uniform(0.2, 0.5), size=2000)
        elif name == "poisson":
            s = r.poisson(r.uniform(3, 8), size=2000)
        elif name == "geom":
            s = r.geometric(r.uniform(0.2, 0.4), size=2000)
        elif name == "uniform":
            a = r.uniform(-5, 5)
            s = r.uniform(a, a + r.uniform(2, 10), size=2000)
        elif name == "expon":
            s = r.exponential(r.uniform(1, 5), size=2000)
        else:
            s = r.normal(r.uniform(10, 50), r.uniform(2, 8), size=2000)
        mystery[label] = s
    if with_truth:
        return dict(zip("ABC", names))
    return requests_per_minute, gaps_sec, mystery
'''
# <<< SHARED

# Код проверки выполняется в ядре ноутбука после всех ячеек студента.
CHECK = r'''
def __hw03_check(result_path, shared):
    import json
    import numpy as np
    from scipy import stats

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

    student = str(G.get("STUDENT", "")).strip()
    group = str(G.get("GROUP", "")).strip()
    try:
        V = int(G.get("VARIANT", 0))
    except Exception:
        V = 0
    valid = 1 <= V <= ns["N_VARIANTS"]

    if valid:
        P = ns["params"](V)
        counts, gaps, _ = ns["make_data"](V)
        truth = ns["make_data"](V, with_truth=True)
        w = P["weights1"]
        pr = w / w.sum()
        k, b = P["k2"], P["b2"]

        # ---- задача 1
        add(1, "1.1 probs1", 0.5, lambda: close("probs1", pr))

        def t12():
            f = get("cdf_discrete")
            r = np.random.default_rng(99)
            for _ in range(4):
                vals = np.sort(r.choice(np.arange(-20, 21), size=r.integers(2, 8), replace=False)).astype(float)
                pp = r.dirichlet(np.ones(len(vals)))
                xs = np.concatenate([vals, vals + 0.5, vals - 0.5, [vals.min() - 10, vals.max() + 10]])
                exp = np.array([pp[vals <= x].sum() for x in xs])
                got = np.asarray(f(vals, pp, xs), dtype=float)
                if got.shape != xs.shape or not np.allclose(got, exp, atol=1e-9):
                    return False, f"неверно на values={vals.tolist()}, x={xs.tolist()}"
                x0 = float(vals[len(vals) // 2])
                if not np.isclose(float(f(vals, pp, x0)), pp[vals <= x0].sum()):
                    return False, "неверно для числового (не массива) x"
            return True, ""
        add(1, "1.2 cdf_discrete", 1.0, t12)
        add(1, "1.3 p13a", 0.25, lambda: close("p13a", pr[2] + pr[3]))
        add(1, "1.3 p13b", 0.25, lambda: close("p13b", pr[1] + pr[2] + pr[3]))

        # ---- задача 2
        add(2, "2.1 c2", 0.5, lambda: close("c2", (k + 1) / b ** (k + 1)))

        def t22():
            f = get("F2")
            xs = np.array([-1.0, 0.0, b / 3, b / 2, 0.9 * b, b, b + 1.0])
            exp = np.clip(xs / b, 0, 1) ** (k + 1)
            got = np.asarray(f(xs), dtype=float)
            if got.shape != xs.shape or not np.allclose(got, exp, atol=1e-9):
                return False, f"F2({xs.tolist()}) = {np.round(got, 4).tolist()}"
            if not np.isclose(float(f(b / 2)), 0.5 ** (k + 1)):
                return False, "неверно для числового x"
            return True, ""
        add(2, "2.2 F2", 0.5, t22)
        add(2, "2.3 p23", 0.5, lambda: close("p23", 1 - 0.5 ** (k + 1)))
        add(2, "2.3 median2", 0.5, lambda: close("median2", b * 0.5 ** (1 / (k + 1))))

        # ---- задача 3
        def t31():
            s = np.asarray(get("sample_task2")(20_000, np.random.default_rng(12345)), dtype=float).ravel()
            if s.size != 20_000:
                return False, f"вернула {s.size} значений вместо 20000"
            if s.min() < 0 or s.max() > b:
                return False, "значения вне отрезка [0; b]"
            p = stats.kstest(s, lambda x: np.clip(x / b, 0, 1) ** (k + 1)).pvalue
            return (p > 0.001), f"выборка не согласуется с распределением задачи 2 (p-value {p:.2g})"
        add(3, "3.1 sample_task2", 1.0, t31)

        def t32():
            f = get("sample_discrete")
            for vals, pp, seed in [(np.array([10, 20, 30, 40]), np.array([0.1, 0.2, 0.3, 0.4]), 7),
                                   (P["values1"], pr, 8)]:
                s = np.asarray(f(vals, pp, 200_000, np.random.default_rng(seed))).ravel()
                if s.size != 200_000:
                    return False, f"вернула {s.size} значений вместо 200000"
                if not np.all(np.isin(s, vals)):
                    return False, "в выборке есть значения не из values"
                freq = np.array([np.mean(s == v) for v in vals])
                if np.max(np.abs(freq - pp)) > 0.006:
                    return False, f"частоты {np.round(freq, 3).tolist()} не совпадают с {np.round(pp, 3).tolist()}"
            return True, ""
        add(3, "3.2 sample_discrete", 1.0, t32)

        # ---- задача 4
        lam = counts.mean()
        C = int(np.ceil(lam + 2 * np.sqrt(lam)))
        add(4, "4.1 lam_hat", 0.5, lambda: close("lam_hat", lam))
        add(4, "4.2 p_overload", 0.5, lambda: close("p_overload", stats.poisson.sf(C, lam), rtol=1e-4))
        add(4, "4.3 wait_q95", 0.5, lambda: close("wait_q95", -gaps.mean() * np.log(0.05), rtol=1e-4))

        def t44():
            a = get("answer_types")
            got = {str(key): str(val).strip().lower() for key, val in dict(a).items()}
            return (got == truth), "распределения определены неверно"
        add(4, "4.4 answer_types", 0.5, t44)

        # ---- задача 5
        m, mean, t = P["m5"], P["mean5"], P["t5"]
        p_true = 1 - (1 - np.exp(-t / mean)) ** m
        add(5, "5.1 p5_exact", 1.0, lambda: close("p5_exact", p_true))

        def t52():
            n = int(get("n5"))
            if n < 100_000:
                return False, f"n5 = {n} < 100000"
            v = float(get("p5_mc"))
            tol = 4 * np.sqrt(p_true * (1 - p_true) / n) + 1e-3
            return (abs(v - p_true) <= tol), f"p5_mc = {v:.4f} слишком далеко от верного значения"
        add(5, "5.2 p5_mc", 1.0, t52)

    total = round(sum(i["score"] for i in items), 2)
    out = {"student": student, "group": group, "variant": V, "valid_variant": valid,
           "total": total, "max": 10.0, "items": items}
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

__hw03_check(RESULT_PATH, SHARED_CODE)
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

    lines = ["## ДЗ 3: результаты автопроверки", "",
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
