# PNU Schedule Monitor

Автономна система моніторингу розкладу занять ПНУ.

## Як працює

1. **Кожні 3 години** GitHub Actions автоматично запускає скрипт `main-scraper.py`
2. Скрипт парсить розклад для груп **КН-41** та **КН-42** з сайту `asu-srv.pnu.edu.ua`
3. Якщо знайдено зміни — оновлений `schedule_data.js` пушиться в:
   - Цей репозиторій (`pnu-schedule-monitor`)
   - Основний сайт (`student-pnu-web.github.io`)
4. На пошту надсилається сповіщення про зміни

## Технології

- **Python 3.10** + `requests` + `BeautifulSoup4` + `lxml`
- **GitHub Actions** для автоматизації
- Без Selenium — працює швидко через HTTP-запити

## Секрети (GitHub Secrets)

| Секрет | Опис |
|--------|------|
| `REPO_B_PAT` | Personal Access Token для пушу в `student-pnu-web.github.io` |
| `MAIL_USERNAME` | Gmail адреса для сповіщень |
| `MAIL_PASSWORD` | App Password для Gmail |
