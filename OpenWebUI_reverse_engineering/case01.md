## Case01

1. GET http://host.docker.internal:11434/api/tags HTTP/1.1
2. GET http://host.docker.internal:11434/api/ps HTTP/1.1
3. GET http://host.docker.internal:11434/api/tags HTTP/1.1
4. GET http://host.docker.internal:11434/api/ps HTTP/1.1
5. POST http://host.docker.internal:11434/api/chat HTTP/1.1.
    * Request: Запрос на генерацию названия чата
    * Response "title": "📁 Extract Transaction Data" 
6. POST http://host.docker.internal:11434/api/chat HTTP/1.1
    * Request: Запрос на генерацию дополнительных поисковых запросов (search queries). Это RAG запросы вероятно
    * Response:
    ```json
            {"queries": [
                "extract metadata and transaction table from Excel files including leader, export date, transaction date, article number, and cost", 
                "parse spreadsheet data to retrieve leader, export date, and transaction details such as date, article, and amount ignoring summary rows"]} 
    ```
7.  http://host.docker.internal:11434/api/chat HTTP/1.1
    * Request: Пользовательский запрос на парсинг файла наконец-то пошел. Request содержит messages и tools (33 функции). Message output содержит <context> (cодеримое файлов), <attached_files> (ссылки на файлы) и заканчивается дублированием исходного пользовательского сообщения
    * Response: стрим json-ов, внутри которого json