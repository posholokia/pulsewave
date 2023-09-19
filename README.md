# PulseWave

## Переменные окружения

### Postgres DB
```
DB_NAME = название БД
DB_USER = имя пользователя
DB_PASSWORD = пароль пользователя
DB_HOST = хост
DB_PORT = порт
```

### Server
`SERVER_HOST = адрес сервера`

## Установка:
1. Клонируйте репозиторий на свой компьютер
2. Установите и активируйте виртуальное виртуальное окружение в папке с проектом:
```
python3 -m venv venv
source venv/bin/activate
```
3. Установите зависимости:
```
pip install -r requirements.txt
```

4. Создайте и примените миграции

    Cперва выполнить команду:

    ```
   cd pulsewave
   python3 manage.py makemigrations
   ```

    только после этого:
   
    `python3 manage.py migrate`

  
5. Запуск сервера:
   
   `python3 manage.py runserver`



## API Documentation.

    Swagger UI: `/api/schema/swagger-ui/` 
    Yaml: `/api/schema/` 
    Redoc: `/api/schema/redoc/` 


