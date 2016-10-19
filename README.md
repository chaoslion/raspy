# RasPy 3.3

## Python Package Requirements

* [simplejson](https://pypi.python.org/pypi/simplejson)
* [requests](https://github.com/kennethreitz/requests)
* [wiringpi2](https://github.com/Gadgetoid/Wiringpi2-Python)
* [pushbullet.py](https://github.com/randomchars/pushbullet.py)
* [tweepy](https://github.com/tweepy/tweepy)
* [googlemaps](https://github.com/googlemaps/google-maps-services-python)

## Basic Configuration

### Permissions

* RasPy must run with root permissions
* php folder must belong to webserver group [www-data]

### Example configuration

```json
{
    "apikey": "???",
    "timeout": 5,
    "rcsocket": {
        "automatctrl": {
            "items": [
                "automat1",
                "automat2"
            ]
        }
    },
    "notifier": {
        "pushbullet": {
            "apikey": "???",
            "excluded": ["alex", "bob"]
        },
        "mail": {
            "server": "mail.gmx.net",
            "port": 587,
            "user": "???",
            "password": "???",
            "sender": "webmaster@foo.de",
            "recipients": ["bob@foo.de"]
        },
        "twitter": {
            "consumer": [
                "???",
                "???"
            ],
            "access": [
                "???",
                "???"
            ]
        }
    },
    "traffic": {
        "apikey": "???"
    },
    "weather": {
        "forecast": {
            "apikey": "???",
            "location": [50.37, 13.37]
        },
        "cam": {
            "device": 0
        }
    },
    "system": {
        "disk": {
            "rootpartition": "sda2"
        }
    },
    "fritz": {
        "ip": "192.168.178.1",
        "password": "???",
        "user": "???"
    }
}
```

## Run RasPy

Start RasPy with -d to enter debug mode

```bash
python raspy.py [-d]
```
