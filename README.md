# TUM Mensa Bot

## Setup

* requires python 3.6 or above
* install dependencies: `pip install -r requirements.txt`
* copy `config.example.ini` to `config.ini` and enter bot details

## Running
**Start bot daemon:**

```bash
python3 main.py daemon
# or
./mensa_daemon.sh
```

**Send notifications:**

```bash
python3 main.py notifications
# or
./mensa_notifications.sh
```

