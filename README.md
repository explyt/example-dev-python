# NetBox

Django-based network infrastructure management system.

## Требования

- Python 3.8 или выше
- pip
- Git

## Быстрый старт

### Linux / macOS

```bash
# 1. Клонировать репозиторий
git clone <repository>

# 2. Запустить setup (создаст venv и установит зависимости)
./setup.sh

# 3. Запустить сервер
./start_server.sh
```

### Windows

```powershell
# 1. Клонировать репозиторий
git clone <repository>

# 2. Запустить setup (создаст venv и установит зависимости)
.\setup.ps1

# 3. Запустить сервер
.\start_server.ps1
```

### Окуржение
Не забудьте указать вашему редактору созданное виртуальное окружение:
1. В PyCharm:
    - Shift-Shift, `Interpreter` 
    - Нажмите `Add Interpreter`, затем `Add Local Interpreter`
    - В открытом окне поставьте чекбокс `Select existing`
    - Выберите тип `Python`
    - В `Python path` укажите путь до созданного окружения `.../example-dev-python/.venv/bin/python`
2. В VS Code + Python-расширение:
    - Command-Shift-P (для macOS) или Ctrl+P (на Windows и Linux), `>Python: Select Interpreter`
    - Выберите созданное окружение `./.venv/bin/python`

## После запуска

Сервер будет доступен по адресу: **http://127.0.0.1:8000**

**Учетные данные:**
- Username: `admin`
- Password: `admin`

**API Token** будет выведен в консоли при запуске.

## Тестирование

Проект покрыт тестами, для их запуска необходимо выполнить в виртуальном окружении
```bash
python manage.py test
```