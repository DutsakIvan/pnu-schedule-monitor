import time
import json
import requests
from datetime import datetime
from scraper import parse_schedule_html_to_json

# --- Налаштування ---
URL = "https://asu-srv.pnu.edu.ua/cgi-bin/timetable.cgi"
GROUPS = [
    "КН-41", "КН-42",
]
START_DATE = "01.01.2026"
END_DATE = "01.07.2026"
OUTPUT_JS_FILE = "schedule_data.js"
CHANGES_JSON_FILE = "schedule_changes.json"
SLEEP_BETWEEN_REQUESTS = 1

def load_existing_data(filename):
    """Завантажує існуючі дані з файлу, якщо він існує"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            json_str = content.replace('const schedulesData =', '').replace(';\n', '').strip()
            return json.loads(json_str)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    except Exception as e:
        print(f"Помилка при завантаженні існуючих даних: {e}")
        return {}

def load_changes_history(filename):
    """Завантажує історію змін з файлу"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"history": []}
    except Exception as e:
        print(f"Помилка при завантаженні історії змін: {e}")
        return {"history": []}

def format_lesson_short(lesson):
    """Форматує заняття у короткий рядок для email"""
    subject = lesson.get('subject', 'Невідомо')
    time_str = lesson.get('time', '')
    teacher = lesson.get('teacher', '')
    result = f"{subject}"
    if time_str:
        result = f"{time_str} — {result}"
    if teacher:
        result += f" ({teacher})"
    return result

def compare_schedules(old_data, new_data):
    """Порівнює старі та нові дані та повертає список текстових змін (для сумісності) 
    і детальний об'єкт змін для JSON"""
    text_changes = []
    detailed_changes = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "groups": {}
    }

    for group_name, new_group_data in new_data.items():
        if group_name not in old_data:
            text_changes.append(f"{group_name}: додано нову групу")
            continue

        old_group_data = old_data[group_name]
        group_day_changes = {}

        if old_group_data.get('date_range') != new_group_data.get('date_range'):
            text_changes.append(f"{group_name}: змінився діапазон дат")

        old_days = {day['date']: day for day in old_group_data.get('schedule', [])}
        new_days = {day['date']: day for day in new_group_data.get('schedule', [])}
        all_dates = sorted(list(set(old_days.keys()).union(set(new_days.keys()))),
                           key=lambda d: datetime.strptime(d, "%d.%m.%Y"))

        for date in all_dates:
            if date not in old_days:
                new_day = new_days[date]
                text_changes.append(f"{group_name}: додано новий день {date}")
                group_day_changes[date] = {
                    "day_name": new_day.get('day', ''),
                    "type": "added_day",
                    "old_lessons": [],
                    "new_lessons": new_day.get('lessons', []),
                    "removed": [],
                    "added": new_day.get('lessons', []),
                    "modified": [],
                    "summary": f"Додано новий день з {len(new_day.get('lessons', []))} парами"
                }
                continue

            if date not in new_days:
                old_day = old_days[date]
                text_changes.append(f"{group_name}: видалено день {date}")
                group_day_changes[date] = {
                    "day_name": old_day.get('day', ''),
                    "type": "removed_day",
                    "old_lessons": old_day.get('lessons', []),
                    "new_lessons": [],
                    "removed": old_day.get('lessons', []),
                    "added": [],
                    "modified": [],
                    "summary": f"Усі {len(old_day.get('lessons', []))} пари скасовані/перенесені"
                }
                continue

            old_day = old_days[date]
            new_day = new_days[date]
            old_lessons = old_day.get('lessons', [])
            new_lessons = new_day.get('lessons', [])

            if old_lessons == new_lessons:
                continue

            removed = []
            added = []
            modified = []

            old_by_time = {}
            for lesson in old_lessons:
                t = lesson.get('time', '')
                if t not in old_by_time:
                    old_by_time[t] = []
                old_by_time[t].append(lesson)

            new_by_time = {}
            for lesson in new_lessons:
                t = lesson.get('time', '')
                if t not in new_by_time:
                    new_by_time[t] = []
                new_by_time[t].append(lesson)

            all_times = sorted(set(list(old_by_time.keys()) + list(new_by_time.keys())))

            for t in all_times:
                old_at_time = old_by_time.get(t, [])
                new_at_time = new_by_time.get(t, [])

                if not new_at_time:
                    removed.extend(old_at_time)
                elif not old_at_time:
                    added.extend(new_at_time)
                else:
                    for old_l in old_at_time:
                        found_match = False
                        for new_l in new_at_time:
                            if old_l == new_l:
                                found_match = True
                                break
                        if not found_match:
                            best_match = None
                            for new_l in new_at_time:
                                if new_l.get('time') == old_l.get('time'):
                                    best_match = new_l
                                    break
                            if best_match:
                                modified.append({"old": old_l, "new": best_match})
                            else:
                                removed.append(old_l)

                    for new_l in new_at_time:
                        found_match = False
                        for old_l in old_at_time:
                            if old_l == new_l:
                                found_match = True
                                break
                        if not found_match:
                            already_modified = any(
                                m["new"].get('time') == new_l.get('time') and 
                                m["new"].get('subject') == new_l.get('subject')
                                for m in modified
                            )
                            if not already_modified:
                                added.append(new_l)

            if removed or added or modified:
                summary_parts = []
                if removed:
                    summary_parts.append(f"Видалено {len(removed)} пар")
                if added:
                    summary_parts.append(f"Додано {len(added)} пар")
                if modified:
                    summary_parts.append(f"Змінено {len(modified)} пар")
                summary = ", ".join(summary_parts)

                group_day_changes[date] = {
                    "day_name": new_day.get('day', old_day.get('day', '')),
                    "type": "modified",
                    "old_lessons": old_lessons,
                    "new_lessons": new_lessons,
                    "removed": removed,
                    "added": added,
                    "modified": modified,
                    "summary": summary
                }

                if len(old_lessons) != len(new_lessons):
                    text_changes.append(f"{group_name}: змінилася кількість занять {date} (було {len(old_lessons)}, стало {len(new_lessons)})")
                else:
                    for i, (old_lesson, new_lesson) in enumerate(zip(old_lessons, new_lessons)):
                        if old_lesson != new_lesson:
                            text_changes.append(f"{group_name}: змінилося заняття {date} пара {i + 1}")

        if group_day_changes:
            detailed_changes["groups"][group_name] = {"days": group_day_changes}

    return text_changes, detailed_changes

def generate_email_summary(detailed_changes):
    """Генерує детальний текстовий огляд змін для email"""
    lines = []
    for group_name, group_data in detailed_changes.get("groups", {}).items():
        for date, day_data in group_data.get("days", {}).items():
            day_name = day_data.get("day_name", "")
            header = f"📅 {group_name} — {date}"
            if day_name:
                header += f" ({day_name})"
            lines.append(header)

            removed = day_data.get("removed", [])
            added = day_data.get("added", [])
            modified = day_data.get("modified", [])

            if day_data.get("type") == "removed_day":
                lines.append("  ⛔ Усі пари з цього дня скасовані/перенесені:")
                for lesson in removed:
                    lines.append(f"    ❌ {format_lesson_short(lesson)}")
            elif day_data.get("type") == "added_day":
                lines.append("  ✨ Додано новий день:")
                for lesson in added:
                    lines.append(f"    ✅ {format_lesson_short(lesson)}")
            else:
                if removed:
                    lines.append("  Видалені пари:")
                    for lesson in removed:
                        lines.append(f"    ❌ {format_lesson_short(lesson)}")
                if added:
                    lines.append("  Додані пари:")
                    for lesson in added:
                        lines.append(f"    ✅ {format_lesson_short(lesson)}")
                if modified:
                    lines.append("  Змінені пари:")
                    for mod in modified:
                        lines.append(f"    🔄 Було: {format_lesson_short(mod['old'])}")
                        lines.append(f"       Стало: {format_lesson_short(mod['new'])}")

            lines.append("")

    return "\n".join(lines)


# Завантажуємо існуючі дані
existing_data = load_existing_data(OUTPUT_JS_FILE)
print(f"Завантажено існуючі дані для {len(existing_data)} груп")

all_groups_data = {}

# --- Основний цикл по групам ---
for group in GROUPS:
    print(f"\nОбробка групи: {group}")
    try:
        # Відправляємо POST-запит з параметрами (як робить форма на сайті)
        # Університетський сайт використовує кодування windows-1251
        data = {
            'group': group.encode('windows-1251'),
            'sdate': START_DATE,
            'edate': END_DATE
        }
        response = requests.post(URL, data=data)
        response.encoding = 'windows-1251' # Встановлюємо правильне кодування відповіді
        
        container_html = response.text
        
        parsed_data, parsed_group_name = parse_schedule_html_to_json(container_html)

        if parsed_group_name != "Невідома група" and parsed_group_name in parsed_data:
            all_groups_data.update(parsed_data)
            print(f"  Дані для групи {parsed_group_name} успішно додано.")
        else:
            print(f"  ПОМИЛКА: Не вдалося коректно розпарсити дані або назву для групи {group}.")

    except Exception as e:
        print(f"  ПОМИЛКА: Неочікувана помилка при обробці групи '{group}': {e}")
    finally:
        time.sleep(SLEEP_BETWEEN_REQUESTS)

if all_groups_data:
    text_changes, detailed_changes = compare_schedules(existing_data, all_groups_data)
    
    if text_changes:
        print("\nЗнайдено зміни в розкладах:")
        for change in text_changes[:10]: # Виводимо перші 10 змін
            print(f"  - {change}")
        if len(text_changes) > 10:
            print(f"  ... та ще {len(text_changes) - 10} змін.")

        # Генеруємо детальний email
        email_detail = generate_email_summary(detailed_changes)
        print("\n--- EMAIL_DETAIL_START ---")
        print(email_detail)
        print("--- EMAIL_DETAIL_END ---")

        # Зберігаємо детальні зміни
        changes_history = load_changes_history(CHANGES_JSON_FILE)
        
        # Додаємо нову запис в історію (зберігаємо останні 20)
        changes_history["history"].insert(0, detailed_changes)
        changes_history["history"] = changes_history["history"][:20]
        changes_history["latest"] = detailed_changes
        
        with open(CHANGES_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(changes_history, f, ensure_ascii=False, indent=2)
        print(f"\nДетальні зміни збережено у {CHANGES_JSON_FILE}")
    else:
        print("\nЗмін у розкладах не знайдено.")

    # Оновлюємо існуючі дані новими
    existing_data.update(all_groups_data)

    with open(OUTPUT_JS_FILE, 'w', encoding='utf-8') as f:
        # Конвертуємо в JSON з відступами для читабельності
        json_output = json.dumps(existing_data, ensure_ascii=False, indent=4)
        f.write(f"const schedulesData = {json_output};\n")
    print(f"\nДані успішно збережено у {OUTPUT_JS_FILE}")
else:
    print("\nНе вдалося зібрати дані для жодної групи.")
