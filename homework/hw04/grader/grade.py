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
    return {
        # задача 2 (мс)
        "q2": round(0.15 + 0.05 * (v % 6), 2),   # доля ответов из кэша
        "c2": 3 + v % 5,                          # время ответа из кэша
        "d2": 15 + 5 * (v % 4),                   # минимальное время обработки
        "mu2": 60 + 10 * (v % 7),                 # средняя добавка к d2
        "T2": 120 + 20 * (v % 5),                 # таймаут клиента
        # задача 3
        "N3": 20 + v % 11,
        "m3": 30 + 2 * (v % 9),
    }


def make_data(variant):
    """Данные варианта для задач 4 и 5. Не изменяйте эту функцию."""
    v = int(variant)
    r = np.random.default_rng(30_000 + v)
    # задача 4: рекламные кампании в трёх регионах
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
    # задача 5: дневные доходности трёх активов, %
    sig = np.array([1.0 + 0.1 * (v % 5), 1.5, 0.8 + 0.05 * (v % 7)])
    corr = np.array([[1.0, 0.1 + 0.1 * (v % 5), -0.3 + 0.1 * (v % 4)],
                     [0.1 + 0.1 * (v % 5), 1.0, 0.1 * (v % 5)],
                     [-0.3 + 0.1 * (v % 4), 0.1 * (v % 5), 1.0]])
    returns = np.round(r.multivariate_normal([0.05, 0.08, 0.03], corr * np.outer(sig, sig), size=750), 4)
    return campaigns, returns
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

    if valid:
        P = ns["params"](V)
        camp, rets = ns["make_data"](V)

        # ---- задача 1: функция moments на скрытых тестах
        def mtest(cases, what):
            def run():
                f = get("moments")
                for x, w in cases:
                    exp = ref_moments(x, w)
                    got = f(np.array(x, dtype=float), np.array(w, dtype=float))
                    got = [float(t) for t in got]
                    if len(got) != 3:
                        return False, "moments должна возвращать (mean, var, skew)"
                    tol = [1e-9 * max(1, abs(exp[0])), 1e-6 * max(exp[1], 1e-12), 1e-5]
                    if any(abs(a - b) > t for a, b, t in zip(got, exp, tol)):
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
        add(1, "1.1 moments: обычные распределения", 0.5, mtest(basic, "обычный случай"))
        add(1, "1.2 moments: ненормированные веса, повторы, нулевые веса", 0.5, mtest(unnorm, "ненормированные веса"))
        add(1, "1.3 moments: большие значения (устойчивость)", 0.5, mtest(big, "значения порядка 1e9"))
        add(1, "1.4 moments: асимметрия", 0.5, mtest(skewc, "асимметрия"))

        # ---- задача 2: смешанное распределение с таймаутом
        q, c, d, mu, T = P["q2"], P["c2"], P["d2"], P["mu2"], P["T2"]
        lam, t0 = 1 / mu, T - d
        e1 = (1 - np.exp(-lam * t0)) / lam
        e2 = 2 / lam ** 2 * (1 - np.exp(-lam * t0) * (1 + lam * t0))
        EM, EM2 = d + e1, d * d + 2 * d * e1 + e2
        EX = q * c + (1 - q) * EM
        DX = q * c * c + (1 - q) * EM2 - EX ** 2
        add(2, "2.1 p2_timeout", 0.5, lambda: close("p2_timeout", (1 - q) * np.exp(-lam * t0)))
        add(2, "2.2 EX2", 0.75, lambda: close("EX2", EX))
        add(2, "2.3 DX2", 0.75, lambda: close("DX2", DX))

        # ---- задача 3: пустые серверы
        N, m = P["N3"], P["m3"]
        p1, p2 = (1 - 1 / N) ** m, (1 - 2 / N) ** m
        add(3, "3.1 E3_empty", 0.5, lambda: close("E3_empty", N * p1))
        add(3, "3.2 D3_empty", 1.0, lambda: close("D3_empty", N * p1 * (1 - p1) + N * (N - 1) * (p2 - p1 ** 2)))
        add(3, "3.3 E3_single", 0.5, lambda: close("E3_single", m * (1 - 1 / N) ** (m - 1)))

        # ---- задача 4: кампании, Симпсон
        keep = camp["is_test"] == 0
        reg, x4, y4 = camp["region"][keep], camp["ads"][keep], camp["sales"][keep]
        add(4, "4.1 corr4_all", 0.5, lambda: close("corr4_all", np.corrcoef(x4, y4)[0, 1]))

        def t42():
            got = dict(get("corr4_by_region"))
            exp = {g: np.corrcoef(x4[reg == g], y4[reg == g])[0, 1] for g in np.unique(reg)}
            if set(map(str, got)) != set(exp):
                return False, f"ключи {sorted(map(str, got))}, ожидались {sorted(exp)}"
            bad = [g for g in exp if not np.isclose(float(got[g]), exp[g], rtol=1e-6)]
            return (not bad), f"неверно для регионов {bad}"
        add(4, "4.2 corr4_by_region", 0.5, t42)
        xc, yc = x4.copy(), y4.copy()
        for g in np.unique(reg):
            xc[reg == g] -= x4[reg == g].mean(); yc[reg == g] -= y4[reg == g].mean()
        add(4, "4.3 slope4_within", 0.5, lambda: close("slope4_within", (xc * yc).sum() / (xc ** 2).sum()))
        ss_tot = ((y4 - y4.mean()) ** 2).sum()
        ss_between = sum((reg == g).sum() * (y4[reg == g].mean() - y4.mean()) ** 2 for g in np.unique(reg))
        add(4, "4.4 eta2_4", 0.5, lambda: close("eta2_4", ss_between / ss_tot))

        # ---- задача 5: портфель минимальной дисперсии
        S = np.cov(rets, rowvar=False)
        ones = np.ones(3)
        w = np.linalg.solve(S, ones); w = w / w.sum()
        sd_min = np.sqrt(w @ S @ w)
        sd_eq = np.sqrt(ones @ S @ ones) / 3
        add(5, "5.1 cov5", 0.5, lambda: close("cov5", S))
        add(5, "5.2 w5_min", 0.5, lambda: close("w5_min", w, rtol=1e-5))
        add(5, "5.3 sd5_min", 0.5, lambda: close("sd5_min", sd_min, rtol=1e-5))
        add(5, "5.4 gain5", 0.5, lambda: close("gain5", sd_eq / sd_min, rtol=1e-5))

    total = round(sum(i["score"] for i in items), 2)
    out = {"student": student, "group": group, "variant": V, "valid_variant": valid,
           "total": total, "max": 10.0, "items": items}
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

__hw04_check(RESULT_PATH, SHARED_CODE)
'''

TASKS = [1, 2, 3, 4, 5]

# Метки из скрытых комментариев в условии. Человек, читающий ноутбук в Colab, их не видит,
# а нейросеть, которой передали .ipynb целиком, может выполнить скрытую инструкцию.
CANARY_MARKERS = ['outlier_policy', 'timeout_units']


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
                   "total": 0.0, "max": 10.0, "items": []}
            error = error or "проверка не запустилась (ошибка в последней ячейке проверки)"
    res["file"] = Path(path).name
    res["error"] = error
    res["cell_errors"] = cell_errors
    res["canary"] = canary
    return res


def task_score(res, t):
    return round(sum(i["score"] for i in res["items"] if i["task"] == t), 2)


def write_reports(results, out):
    out.mkdir(parents=True, exist_ok=True)
    for r in results:
        (out / (Path(r["file"]).stem + ".json")).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(out / "grades.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["file", "student", "group", "variant"] + [f"task{t}" for t in TASKS] + ["total", "ai_marker"])
        for r in results:
            wr.writerow([r["file"], r["student"], r["group"], r["variant"]] + [task_score(r, t) for t in TASKS] + [r["total"], ";".join(r["canary"])])

    lines = ["## ДЗ 4: результаты автопроверки", "",
             "| Файл | Студент | Группа | Вариант | " + " | ".join(f"З{t}" for t in TASKS) + " | Итого | Метка ИИ |",
             "|---|---|---|---|" + "---|" * len(TASKS) + "---|---|"]
    for r in results:
        lines.append(f"| {r['file']} | {r['student'] or '—'} | {r['group'] or '—'} | {r['variant']} | "
                     + " | ".join(str(task_score(r, t)) for t in TASKS) + f" | **{r['total']}** | {'⚠️ ' + ', '.join(r['canary']) if r['canary'] else ''} |")
    lines += ["", "### Замечания", ""]
    for r in results:
        notes = []
        if r["error"]:
            notes.append(r["error"])
        if not r["valid_variant"]:
            notes.append("не указан или неверен номер варианта (VARIANT от 1 до 40) — проверка не проводилась")
        notes += [f"{i['name']}: {i['msg']}" for i in r["items"] if i["score"] < i["max"]]
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
        print(f"  {r['student'] or '—'}, вариант {r['variant']}: {r['total']} / {r['max']}", flush=True)
        results.append(r)
    write_reports(results, Path(args.out))
    print((Path(args.out) / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
