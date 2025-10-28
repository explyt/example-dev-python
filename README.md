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
cd netbox

# 2. Запустить setup (создаст venv и установит зависимости)
./setup.sh

# 3. Запустить сервер
./start_server.sh
```

### Windows

```powershell
# 1. Клонировать репозиторий
git clone <repository>
cd netbox

# 2. Запустить setup (создаст venv и установит зависимости)
.\setup.ps1

# 3. Запустить сервер
.\start_server.ps1
```

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

**Важно** что один из тестов `test_single_create_process_eventrule` намеренно сломан
