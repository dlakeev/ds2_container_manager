import re
from copy import deepcopy

RESOURCES = {
    "п": {"name": "Полимеры", "containers": [40, 80, 160, 320]},
    "м": {"name": "Металлы", "containers": [50, 100, 200, 400]},
    "к": {"name": "Керамика", "containers": [40, 80, 160, 320]},
    "х": {"name": "Химикаты", "containers": [30, 60, 120, 240]},
    "с": {"name": "Спецсплавы", "containers": [60, 120, 240, 480]},
}

ALIASES = {
    "p": "п",
    "polymer": "п",
    "полимер": "п",
    "полимеры": "п",
    "m": "м",
    "metal": "м",
    "металл": "м",
    "металлы": "м",
    "c": "к",
    "ceramic": "к",
    "керамика": "к",
    "x": "х",
    "chem": "х",
    "химия": "х",
    "химикаты": "х",
    "s": "с",
    "special": "с",
    "спецсплав": "с",
    "спецсплавы": "с",
    "сс": "с",
}

# Токен: число + [× или * для множителя] + код ресурса.
# Поддерживает форматы: '320п', '2×320п', '2*320п'.
# ВАЖНО: символы 'x'/'х' НЕ используются как множитель — они конфликтуют
# с кодами ресурсов (х — химикаты).
TOKEN_RE = re.compile(
    r"(?:(\d+)\s*[×*]\s*)?(\d+)\s*([a-zа-я]+)",
    re.IGNORECASE,
)


def parse_amounts(text: str) -> list[tuple[str, int]]:
    """
    Парсит строку в список (код, штука).
    '320п 80с 80с'      → [('п',320), ('с',80), ('с',80)]
    '2×320п 80с'        → [('п',320), ('п',320), ('с',80)]
    """
    text = text.strip().lower().replace(",", " ")
    items = []
    for mult_str, amount_str, code in TOKEN_RE.findall(text):
        code = ALIASES.get(code, code)
        if code not in RESOURCES:
            print(f"  ⚠ Неизвестный код ресурса: '{code}' — пропущен.")
            continue
        mult = int(mult_str) if mult_str else 1
        amount = int(amount_str)
        for _ in range(mult):
            items.append((code, amount))
    return items


def pick_containers(deficit: int, containers: list[int]) -> tuple[dict, int]:
    """
    Жадно: крупные контейнеры пока влезают целиком,
    остаток — минимальным контейнером, в который он помещается.
    """
    counts = {size: 0 for size in containers}
    remaining = deficit

    for size in sorted(containers, reverse=True):
        if remaining >= size:
            counts[size] = remaining // size
            remaining -= counts[size] * size

    if remaining > 0:
        sizes_asc = sorted(containers)
        cover = next((s for s in sizes_asc if s >= remaining), sizes_asc[-1])
        counts[cover] += 1

    total = sum(size * n for size, n in counts.items())
    return counts, total


def format_plan(items: list[tuple[str, int]], title: str = "Нужно взять") -> str:
    """Форматирует список требований с разбивкой по контейнерам."""
    if not items:
        return f"  {title}: ничего, всё закрыто ✓"

    name_w = max(len(RESOURCES[c]["name"]) for c, _ in items)
    need_w = max(len(str(n)) for _, n in items)

    lines = [f"┌── {title} " + "─" * max(2, 40 - len(title))]
    for code, deficit in items:
        info = RESOURCES[code]
        counts, total = pick_containers(deficit, info["containers"])
        excess = total - deficit

        parts = []
        for size in sorted(counts.keys(), reverse=True):
            n = counts[size]
            if n > 0:
                parts.append(f"{n}×{size}")
        breakdown = " + ".join(parts) if parts else "—"

        excess_str = f"  (+{excess})" if excess else ""
        lines.append(
            f"│  {info['name']:{name_w}s}  {deficit:>{need_w}d}  →  "
            f"{breakdown}  = {total}{excess_str}"
        )
    lines.append("└" + "─" * 50)
    return "\n".join(lines)


def apply_taken(
    items: list[tuple[str, int]], taken: list[tuple[str, int]]
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """
    Списывает взятые контейнеры с требований.
    Стратегия: для каждой взятой штуки находим требование того же ресурса,
    которому она лучше всего подходит:
      1) сначала пробуем требования, где остаток >= штуки (вычитаем штуку);
         выбираем требование с минимальным остатком (чтобы быстрее закрыть).
      2) если таких нет — берём требование с наибольшим остатком и закрываем
         его (излишек уходит «в перебор»).
    Возвращает (новый_список_требований, нераспределённые_излишки).
    """
    # Группируем требования по коду, сохраняя индексы для порядка.
    remaining = [[code, amount] for code, amount in items]
    overflow = []  # что взяли сверх нужного

    for code, amount in taken:
        # Индексы открытых требований этого ресурса.
        idxs = [i for i, (c, a) in enumerate(remaining) if c == code and a > 0]
        if not idxs:
            overflow.append((code, amount))
            continue

        # 1) Требования, в которые штука влезает целиком.
        fits = [i for i in idxs if remaining[i][1] >= amount]
        if fits:
            # Выбираем с минимальным остатком → быстрее закроется.
            best = min(fits, key=lambda i: remaining[i][1])
            remaining[best][1] -= amount
        else:
            # 2) Закрываем требование с наибольшим остатком, излишек запоминаем.
            best = max(idxs, key=lambda i: remaining[i][1])
            leftover = amount - remaining[best][1]
            remaining[best][1] = 0
            overflow.append((code, leftover))

    # Убираем закрытые требования (=0).
    new_items = [(c, a) for c, a in remaining if a > 0]
    return new_items, overflow


def print_help():
    print("Коды ресурсов и контейнеры в убежищах:")
    for code, info in RESOURCES.items():
        sizes = " / ".join(str(s) for s in info["containers"])
        print(f"  {code:3s} — {info['name']:12s}  {sizes}")
    print("\nВвод требований:  400п 360с 560п 360с")
    print("Ввод взятого:     320п 80с 80с   (или 2×320п 80с)")
    print("Команды трекера:  show, undo, reset, q\n")


def run_tracker(initial_items: list[tuple[str, int]]):
    """Цикл трекера: показываем остаток, ждём что взято, повторяем."""
    history = []  # для undo: список (items_before, taken)
    items = list(initial_items)

    print(format_plan(items, "Нужно взять"))

    while items:
        try:
            raw = input("\nВзял (или show/undo/reset/q)> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nПрервано.")
            return "quit"

        if not raw:
            continue

        cmd = raw.lower()
        if cmd in ("q", "quit", "exit", "выход"):
            return "quit"
        if cmd in ("reset", "сброс", "new", "новый"):
            return "reset"
        if cmd in ("show", "s", "?", "покажи"):
            print(format_plan(items, "Осталось взять"))
            continue
        if cmd in ("undo", "u", "назад", "отмена"):
            if not history:
                print("  Нечего отменять.")
                continue
            items, _ = history.pop()
            print("  ↶ Отменил последнее действие.")
            print(format_plan(items, "Осталось взять"))
            continue

        taken = parse_amounts(raw)
        if not taken:
            print("  Не распознал ввод. Пример: '320п 80с 80с'.")
            continue

        prev_items = deepcopy(items)
        items, overflow = apply_taken(items, taken)
        history.append((prev_items, taken))

        if overflow:
            extra = ", ".join(
                f"{a} {RESOURCES[c]['name'].lower()}" for c, a in overflow
            )
            print(f"  ⚠ Лишнего взято: {extra}")

        if not items:
            print("\n✓ Всё взято! Можно сдавать постройку.")
            return "done"

        print(format_plan(items, "Осталось взять"))

    return "done"


def main():
    print("═" * 56)
    print("  Death Stranding 2 — калькулятор ресурсов + трекер")
    print("═" * 56)
    print_help()

    while True:
        try:
            raw = input("Нужно> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nПока!")
            break

        if not raw:
            continue
        if raw.lower() in ("q", "quit", "exit", "выход"):
            print("Пока!")
            break
        if raw.lower() in ("help", "h", "?", "помощь"):
            print_help()
            continue

        items = parse_amounts(raw)
        if not items:
            print("  Не распознал ни одного ресурса. Введи 'help'.\n")
            continue

        result = run_tracker(items)
        if result == "quit":
            print("Пока!")
            break
        # При 'reset' или 'done' возвращаемся к вводу новых требований.
        print()


if __name__ == "__main__":
    main()
