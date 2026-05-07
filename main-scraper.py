import time
import json
import requests
from scraper import parse_schedule_html_to_json

# --- Налаштування ---
URL = "https://asu-srv.pnu.edu.ua/cgi-bin/timetable.cgi"
GROUPS = [
    "КН-41", "КН-42",
]
START_DATE = "01.01.2026"
END_DATE = "01.07.2026"
OUTPUT_JS_FILE = "schedule_data.js"
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

def compare_schedules(old_data, new_data):
    """Порівнює старі та нові дані та повертає список змін"""
    changes = []
    for group_name, new_group_data in new_data.items():
        if group_name not in old_data:
            changes.append(f"{group_name}: додано нову групу")
            continue

        old_group_data = old_data[group_name]
        if old_group_data.get('date_range') != new_group_data.get('date_range'):
            changes.append(f"{group_name}: змінився діапазон дат")

        old_days = {day['date']: day for day in old_group_data.get('schedule', [])}
        new_days = {day['date']: day for day in new_group_data.get('schedule', [])}
        from datetime import datetime
        all_dates = sorted(list(set(old_days.keys()).union(set(new_days.keys()))), 
                           key=lambda d: datetime.strptime(d, "%d.%m.%Y"))

        for date in all_dates:
            if date not in old_days:
                changes.append(f"{group_name}: додано новий день {date}")
                continue
            if date not in new_days:
                changes.append(f"{group_name}: видалено день {date}")
                continue

            old_lessons = old_days[date]['lessons']
            new_lessons = new_days[date]['lessons']

            if len(old_lessons) != len(new_lessons):
                changes.append(f"{group_name}: змінилася кількість занять {date} (було {len(old_lessons)}, стало {len(new_lessons)})")
            else:
                for i, (old_lesson, new_lesson) in enumerate(zip(old_lessons, new_lessons)):
                    if old_lesson != new_lesson:
                        changes.append(f"{group_name}: змінилося заняття {date} пара {i + 1}")
    return changes

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
    changes = compare_schedules(existing_data, all_groups_data)
    
    if changes:
        print("\nЗнайдено зміни в розкладах:")
        for change in changes[:10]: # Виводимо перші 10 змін
            print(f"  - {change}")
        if len(changes) > 10:
            print(f"  ... та ще {len(changes) - 10} змін.")
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
