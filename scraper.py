# scraper.py
from bs4 import BeautifulSoup
import json
import re
# import os # Не використовується

# Допоміжна функція: чи рядки містять лише метадані (дист. тощо), а не предмет
def is_only_metadata(lines):
    """Перевіряє, чи рядки містять лише метадані без назви предмета."""
    for line in lines:
        stripped = line.strip().lower()
        if stripped and stripped not in ('дист.', 'дистанційно', 'дист'):
            return False
    return True

def parse_lesson_lines(lesson_lines, group_name):
    """Обробляє список рядків одного заняття і повертає словник із даними."""
    subject_lines = []
    teacher = ""
    details_lines = []
    location = ""
    address = ""
    group = ""
    link = "" # Link обробляється зовнішньою функцією

    teacher_line_index = -1

    # Знаходимо викладача та розділяємо subject і details
    for i, line in enumerate(lesson_lines):
        if i > 0 and re.fullmatch(r'[А-ЯІЇЄҐ][а-яіїєґ\'`\'\u2019]+\s+[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.', line.strip()):
            teacher = line.strip()
            teacher_line_index = i
            break
        elif i > 0 and re.fullmatch(r'[А-ЯІЇЄҐ][А-Яа-яІіЇїЄєҐґ\.\s\-\'`\'\u2019]{3,}', line.strip()):
             is_likely_teacher = True
             if i + 1 < len(lesson_lines):
                 next_line = lesson_lines[i+1].strip()
                 if next_line.startswith('ауд.') or next_line.startswith('кор.') or next_line.lower().startswith('дист'):
                      pass
                 elif re.fullmatch(r'[А-ЯІЇЄҐ][а-яіїєґ\'`\'\u2019]+\s+[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.', next_line):
                      is_likely_teacher = False
                 elif re.fullmatch(r'[А-ЯІЇЄҐ][А-Яа-яІіЇїЄєҐґ\.\s\-\'`\'\u2019]{3,}', next_line):
                      is_likely_teacher = False

             if is_likely_teacher:
                teacher = line.strip()
                teacher_line_index = i
                break

    if not teacher:
        for i, line in enumerate(lesson_lines):
             if i > 0 and i < len(lesson_lines) -1 and re.fullmatch(r'[А-Яа-яІіЇїЄєҐґ\.\s\-\'`\'\u2019]+', line.strip()) \
                and not line.strip().startswith(('ауд.', 'кор.', 'дист.', 'http', '(')) and len(line.strip()) > 5:
                 next_line = lesson_lines[i+1].strip()
                 if next_line.startswith(('ауд.', 'кор.', 'дист.', 'http')):
                     teacher = line.strip()
                     teacher_line_index = i
                     break

    if not teacher and lesson_lines:
        last_line = lesson_lines[-1].strip()
        if re.fullmatch(r'[А-ЯІЇЄҐ][А-Яа-яІіЇїЄєҐґ\.\s\-\'`\'\u2019]{3,}', last_line) and not last_line.startswith(('ауд.', 'кор.', 'дист.', 'http')):
             if len(lesson_lines) > 1 and not re.fullmatch(r'[А-ЯІЇЄҐ][А-Яа-яІіЇїЄєҐґ\.\s\-\'`\'\u2019]{3,}', lesson_lines[-2].strip()):
                 teacher = last_line
                 teacher_line_index = len(lesson_lines) - 1

    if teacher_line_index != -1:
        subject_lines = lesson_lines[:teacher_line_index]
        details_lines = lesson_lines[teacher_line_index + 1:]
    else:
        subject_lines = lesson_lines
        details_lines = []

    subject = '\n'.join(subject_lines).strip() if subject_lines else ""
    details_combined = '\n'.join(details_lines).strip() if details_lines else ""

    is_distant = False
    if "дист." in subject.lower():
        is_distant = True
        subject = re.sub(r'\s*\(?дист\.\)?\s*', ' ', subject, flags=re.IGNORECASE).strip()
    if "дист." in details_combined.lower():
        is_distant = True
        details_combined = re.sub(r'\s*\(?дист\.\)?\s*', ' ', details_combined, flags=re.IGNORECASE).strip()

    location_pattern = r'(ауд\.\s*\S+\s+кор\.\s*[^\n,]+(?:,\s*[^\n,]+)?)'
    address_pattern = r'Шевченка\s+57'

    location_match_subj = re.search(location_pattern, subject)
    address_match_subj = re.search(address_pattern, subject)
    location_match_details = re.search(location_pattern, details_combined)
    address_match_details = re.search(address_pattern, details_combined)

    if location_match_subj:
        location = location_match_subj.group(1).strip()
        subject = subject.replace(location_match_subj.group(0), "").strip()
    elif location_match_details:
        location = location_match_details.group(1).strip()
        details_combined = details_combined.replace(location_match_details.group(0), "").strip()

    if address_match_subj:
        address = address_match_subj.group(0).strip()
        subject = subject.replace(address_match_subj.group(0), "").strip()
    elif address_match_details:
        address = address_match_details.group(0).strip()
        details_combined = details_combined.replace(address_match_details.group(0), "").strip()

    details_parts = []
    if is_distant:
        details_parts.append("дист.")
    if location:
        details_parts.append(location)
    if address and address not in location:
        details_parts.append(address)
    if details_combined:
        details_parts.append(details_combined.strip())

    details = ', '.join(filter(None, details_parts)).strip().replace(' ,', ',').replace(', ,', ',')
    details = re.sub(r'\s+,', ',', details)

    podgr_match = re.search(r'\(підгр\. \d+\)', subject)
    if podgr_match:
        podgroup_str = podgr_match.group(0).strip()
        group = f"{group_name} {podgroup_str}"
        subject = subject.replace(podgroup_str, "").strip()
    else:
        stream_match = re.match(r'^(Потік|Збірна група)\s+(.*)', subject, re.IGNORECASE)
        if stream_match:
            group_prefix = stream_match.group(1)
            group_names_str = stream_match.group(2).strip()
            group = f"{group_prefix} {group_names_str}"
            subject = subject.replace(stream_match.group(0), "").strip()

            if not subject.strip() and details_lines:
                 potential_subject = details_lines[0].strip()
                 if not potential_subject.startswith(('ауд.', 'кор.')) and not re.fullmatch(r'[А-ЯІЇЄҐ][А-Яа-яІіЇїЄєҐґ\.\s\-\']{3,}', potential_subject):
                     subject = potential_subject
                     details_lines = details_lines[1:]
                     details_combined = '\n'.join(details_lines).strip() if details_lines else ""
                     details_parts = []
                     if is_distant: details_parts.append("дист.")
                     if location: details_parts.append(location)
                     if address and address not in location: details_parts.append(address)
                     if details_combined: details_parts.append(details_combined.strip())
                     details = ', '.join(filter(None, details_parts)).strip().replace(' ,', ',').replace(', ,', ',')
                     details = re.sub(r'\s+,', ',', details)
        else:
             group = group_name

    subject = ' '.join(subject.split())
    if not group:
        group = group_name

    return {
        "subject": subject.replace('\xa0', ' ').strip(),
        "teacher": teacher.replace('\xa0', ' ').strip(),
        "group": group.replace('\xa0', ' ').strip(), # Повертаємо повну специфікацію
        "details": details.replace('\xa0', ' ').strip(),
        "link": ""
    }

# Функція is_new_lesson_start залишається БЕЗ ЗМІН
def is_new_lesson_start(line):
    """Визначає, чи є рядок початком нового заняття (Потік, Збірна група, підгр.)."""
    line_strip = line.strip()
    return (
        line_strip.startswith('Потік ') or
        line_strip.startswith('Збірна група ') or
        re.match(r'^\(\s*підгр\.\s*\d+\s*\)', line_strip)
    )

# --- ЗМІНИ В ЦІЙ ФУНКЦІЇ ---
def parse_schedule_html_to_json(html_content):
    soup = BeautifulSoup(html_content, 'lxml')

    group_name = "Невідома група"
    date_range = ""
    group_header = soup.find('h4', class_='hidden-xs')
    if group_header:
        group_link = group_header.find('a')
        if group_link:
            group_name = group_link.text.strip() # Базова назва групи сторінки (напр., "КН-31")
        header_text = group_header.text
        match = re.search(r'з\s+(\d{2}\.\d{2}\.\d{4})\s+по\s+(\d{2}\.\d{2}\.\d{4})', header_text)
        if match:
            date_range = f"{match.group(1)} - {match.group(2)}"

    faculty_map = { "КН": "ФМФІТ", "ІПЗ": "ФМФІТ", "ІСТ": "ФМФІТ", "ПР": "Факультет Права" }
    faculty = "Невідомий Факультет"
    for prefix, fac_name in faculty_map.items():
        if group_name.startswith(prefix):
            faculty = fac_name
            break

    schedule_data = { group_name: { "faculty": faculty, "date_range": date_range, "schedule": [] } }

    day_blocks = soup.find_all('div', class_=re.compile(r'col-(md|sm|xs|print)-6'))
    processed_days = set()
    unique_day_blocks = []
    for block in day_blocks:
        day_header = block.find('h4')
        if day_header:
             day_key = day_header.text.strip()
             if day_key not in processed_days:
                 processed_days.add(day_key)
                 unique_day_blocks.append(block)

    for day_block in unique_day_blocks:
        day_header = day_block.find('h4')
        if not day_header: continue

        day_full_text = day_header.get_text(separator=" ", strip=True)
        day_parts = day_full_text.split(' ')
        day_date = day_parts[0] if day_parts else ""
        day_name = day_parts[1] if len(day_parts) > 1 else ""

        day_schedule = { "date": day_date, "day": day_name, "lessons": [] }

        lesson_rows = day_block.find_all('tr')
        if lesson_rows:
            for row in lesson_rows:
                cells = row.find_all('td')
                if len(cells) == 3:
                    time_element = cells[1]; time_parts = [t.strip() for t in time_element.stripped_strings]
                    time_str = '-'.join(time_parts) if len(time_parts) > 1 else (time_parts[0] if time_parts else "")
                    lesson_info_cell = cells[2]
                    if not lesson_info_cell.get_text(strip=True): continue
                    link = ""; link_div = lesson_info_cell.find('div', class_='link')
                    if link_div:
                        a_tag = link_div.find('a');
                        if a_tag and 'href' in a_tag.attrs: link = a_tag['href']
                        link_div.decompose()
                    # Видаляємо <img> та <span class="remote_work"> перед витяганням тексту
                    for img_tag in lesson_info_cell.find_all('img'):
                        img_tag.decompose()
                    for remote_span in lesson_info_cell.find_all('span', class_='remote_work'):
                        # Зберігаємо текст ("дист."), але видаляємо тег
                        remote_span.replace_with(remote_span.get_text())
                    raw_lines = [line.strip() for line in lesson_info_cell.stripped_strings if line.strip()]
                    lessons_in_cell_lines = []; current_lesson_lines = []
                    for line in raw_lines:
                        # Не розділяємо, якщо попередні рядки — лише метадані ("дист.")
                        if is_new_lesson_start(line) and current_lesson_lines and not is_only_metadata(current_lesson_lines):
                            lessons_in_cell_lines.append(current_lesson_lines)
                            current_lesson_lines = [line]
                        else:
                            current_lesson_lines.append(line)
                    if current_lesson_lines: lessons_in_cell_lines.append(current_lesson_lines)

                    for i, lesson_lines in enumerate(lessons_in_cell_lines):
                        parsed_lesson_data = parse_lesson_lines(lesson_lines, group_name)
                        if parsed_lesson_data["subject"]:
                            initial_subject = parsed_lesson_data["subject"]
                            full_group_spec = parsed_lesson_data["group"] # Повна специфікація

                            # --- Формування final_subject ---
                            final_subject = initial_subject
                            subgroup_part_only = None
                            is_subgroup_of_current_group = False

                            # Перевіряємо, чи це підгрупа САМЕ ПОТОЧНОЇ ГРУПИ (group_name)
                            # Використовуємо екранування для group_name на випадок спецсимволів
                            subgroup_match = re.match(rf"^{re.escape(group_name)}\s*(\(підгр\.\s*\d+\))$", full_group_spec)
                            if subgroup_match:
                                subgroup_part_only = subgroup_match.group(1) # Отримуємо "(підгр. N)"
                                final_subject = f"{subgroup_part_only} {initial_subject}" # Додаємо тільки підгрупу
                                is_subgroup_of_current_group = True
                            else:
                                # Якщо це не підгрупа поточної групи (або потік, збірна, інша),
                                # додаємо повну специфікацію, якщо її ще немає
                                if full_group_spec and not initial_subject.startswith(full_group_spec):
                                    final_subject = f"{full_group_spec} {initial_subject}"

                            # --- Формування final_group ---
                            final_group = full_group_spec # Починаємо з повної

                            # Якщо це підгрупа поточної групи, то в group ставимо базову назву
                            if is_subgroup_of_current_group:
                                final_group = group_name
                            else:
                                # Інакше (потік, збірна), видаляємо префікси
                                prefixes_to_remove = ["Збірна група ", "Потік "]
                                for prefix in prefixes_to_remove:
                                    if final_group.startswith(prefix):
                                        final_group = final_group[len(prefix):].strip()
                                        break

                            if not final_group: final_group = group_name # Fallback

                            # --- Створення фінального запису ---
                            lesson_entry = {
                                "time": time_str,
                                "subject": final_subject,
                                "teacher": parsed_lesson_data["teacher"],
                                "group": final_group,
                                "details": parsed_lesson_data["details"],
                                "link": link if link and (i == len(lessons_in_cell_lines) - 1) else ""
                            }
                            day_schedule["lessons"].append(lesson_entry)

        if day_schedule["lessons"]: schedule_data[group_name]["schedule"].append(day_schedule)

    return schedule_data, group_name

# --- Блок для тестування (з оновленими очікуваннями) ---
if __name__ == '__main__':
    test_html = """
    <div class="container">
        <h4 class="hidden-xs">Розклад групи <a title="Постійне посилання на тижневий розклад" style="font-size: 28px;" href="./timetable.cgi?n=700&group=-4072">КН-31</a> з 01.09.2024 по 07.09.2024</h4>
        <div class="row">
            <div class="col-md-6 col-sm-6 col-xs-12 col-print-6">
                <h4>04.09.2024 <small>Середа</small></h4>
                <table class="table  table-bordered table-striped">
                    <tbody>
                        <tr><td>3</td><td>12:20<br>13:40</td><td style="max-width: 340px;overflow: hidden;">Збірна група КН(зб)2.27<br> Програмування iOS (Лаб)<br> Ровінський В.А.<br> ауд. 313 кор. Центральний корпус, Шевченка 57</td></tr>
                        <tr><td>4</td><td>13:50<br>15:10</td><td style="max-width: 340px;overflow: hidden;"> (підгр. 1) <br> Веб-технології (Лаб)<br> Годлевський М.Д.<br> ауд. 313 кор. Центральний корпус, Шевченка 57 </td></tr>
                        <tr><td>5</td><td>15:20<br>16:40</td><td style="max-width: 340px;overflow: hidden;">Потік КН-31, КН-32<br> Теорія ймовірностей (Л)<br> Слободян С.Я.<br> ауд. 318 кор. Центральний корпус, Шевченка 57 </td></tr>
                     </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    if test_html.strip():
        parsed_data, parsed_group_name = parse_schedule_html_to_json(test_html)
        print(f"--- Результат парсингу для групи: {parsed_group_name} ---")
        print(json.dumps(parsed_data, indent=4, ensure_ascii=False))
        # --- Очікуваний вивід ---
        # Заняття 1 (Збірна група):
        #   "subject": "Збірна група КН(зб)2.27 Програмування iOS (Лаб)"
        #   "group": "КН(зб)2.27"
        # Заняття 2 (Підгрупа поточної групи КН-31):
        #   "subject": "(підгр. 1) Веб-технології (Лаб)"  <-- ТУТ ЗМІНА
        #   "group": "КН-31"
        # Заняття 3 (Потік):
        #   "subject": "Потік КН-31, КН-32 Теорія ймовірностей (Л)"
        #   "group": "КН-31, КН-32"
        # --- ---
    else:
        print("Вставте приклад HTML в змінну test_html для тестування парсера.")