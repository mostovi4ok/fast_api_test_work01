```
python3.11 -m venv .env 
source .env/bin/activate  
pip install -r requirements.txt 
export FAST_DB=postgresql+psycopg2://username:password@localhost:5432/db_name
uvicorn numismatics.app:app --reload
```
- создать первого пользователя (админа) с помощью команды 
	
```
python create_one_user.py --name=petr
```

- пример вызова метода программой httpie  https://httpie.io/
``` 
http --auth petr: get :8000/money/upload/ order_by=="-id,mint" -v
GET /money/upload/?order_by=-id%2Cmint HTTP/1.1
Authorization: Basic cGV0cjo=

HTTP/1.1 200 OK
content-disposition: filename=money.csv
content-type: text/csv; charset=utf-8
```
Документация http://localhost:8000/redoc
