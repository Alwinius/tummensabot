FROM python:3
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . /app
EXPOSE 4215
CMD [ "python", "main.py", "daemon" ]