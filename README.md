# PulseWave
### Таск-трекер https://front.pwave.pnpl.tech. 
### Проект еще находится в разработке...


## Переменные окружения (на прод)

#### Postgres DB
```
DB_NAME = название БД
DB_USER = имя пользователя
DB_PASSWORD = пароль пользователя
DB_HOST = хост
DB_PORT = порт
```

#### Email
```
EMAIL_HOST_USER = email адрес с когорого отправляется email
EMAIL_HOST_PASSWORD = пароль email приложения
```
#### Keys
```
SECRET_KEY
```
## Локальная работа
Для локальной работы необходимо в папке **pulsewave** создать файл с локальными настройками *local_settings.py*.\
*local_settings* нельзя пушить в репозиторий, он должен быть в *.gitignore.*\
Минимальное наполнение *local_settings*: SECRET_KEY, DEBUG, DATABASES и EMAIL_BACKEND.\
Например:

```
DEBUG = True
SECRET_KEY = 'django-insecure-l7h7&-z_@56g7^G&7g6%^g76^tdu#593v$cq_*1xb82+0v@_p7'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': './db.sqlite3',
    }
}
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

```


## Установка
1. Клонируйте репозиторий на свой компьютер
2. Установите и активируйте виртуальное виртуальное окружение в папке с проектом:
```
python3 -m venv venv
source venv/bin/activate
```
3. Установите зависимости:
```
pip install --upgrade pip && pip install -r requirements.txt
```

4. Создайте и примените миграции

    Cперва выполнить команду:

```
python3 manage.py makemigrations
```

    только после этого:
   
```
python3 manage.py migrate
```

  
5. Запуск сервера:
   
```
python3 manage.py runserver
```

## Запуск задач по расписанию
`celery -A pulsewave worker -l INFO -B`


## API Documentation.

    Swagger UI: `/api/schema/swagger-ui/` 
    Yaml: `/api/schema/` 
    Redoc: `/api/schema/redoc/` 


