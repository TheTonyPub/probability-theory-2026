# teaching-theory-of-probability-2026
Лекции по теории вероятности для Тимирязевки

Структура повторяет курс `probability-theory` в [dataprosvet-lectures](https://github.com/dataprosvet/dataprosvet-lectures) (ветка `courses/probability-theory`), чтобы материалы можно было перенести туда без переименований:

| Путь | Что лежит |
|---|---|
| `seminars/` | Markdown семинаров (`<sortOrder>_<slug>.md`), открывается в Obsidian |
| `attachments/` | Скачиваемые файлы к материалам: ноутбуки `.ipynb` для Google Colab |

Преподавательские версии с решениями (`lectures-teacher/`) в репозиторий не коммитятся.

## Семинары группы 17-25-2

- [Семинар 7. Схема Бернулли. Формулы Лапласа и Пуассона](seminars/207_bernoulli-laplace-poisson-17-25-2.md)
  - [ноутбук семинара](attachments/207-bernoulli-laplace-poisson-simulations-17-25-2.ipynb) · [открыть в Colab](https://colab.research.google.com/github/TheTonyPub/probability-theory-2026/blob/master/attachments/207-bernoulli-laplace-poisson-simulations-17-25-2.ipynb)
  - [шаблон бонусного задания](attachments/207-hw-simulation-template-17-25-2.ipynb) · [открыть в Colab](https://colab.research.google.com/github/TheTonyPub/probability-theory-2026/blob/master/attachments/207-hw-simulation-template-17-25-2.ipynb)

### Запись для `course.yaml` (раздел `materials.seminars`)

```yaml
    - slug: bernoulli-laplace-poisson-17-25-2
      title: "#7 [17-25-2] Схема Бернулли. Формулы Лапласа и Пуассона"
      summary: >-
        Формула Бернулли, локальная и интегральная формулы Лапласа, формула
        Пуассона: когда какую применять. Бросаем монеты, строим распределение
        руками и сверяем с симуляцией в Python. Восемь задач для самостоятельной
        работы и бонусное исследование на симуляции.
      sortOrder: 207
      lifecycleStatus: published
      availability: available
      markdown: seminars/207_bernoulli-laplace-poisson-17-25-2.md
      attachments:
        - { key: jupyter-notebook, title: "Симуляции к семинару", file: attachments/207-bernoulli-laplace-poisson-simulations-17-25-2.ipynb, sortOrder: 1 }
        - { key: hw-simulation-template, title: "Шаблон бонусного задания", file: attachments/207-hw-simulation-template-17-25-2.ipynb, sortOrder: 2 }
```
