#! /bin/env python

import redis, RPi.GPIO as GPIO
import configparser, logging, os, time, sys

REDIS_KEY_MEASUREMENT_ENABLED = "measurement:enabled"

class App:
    """
    Hilfsprogramm, das einen am Raspberry Pi angeschlossenen Button überwacht, mit
    dem die periodischen Messungen ausgesetzt werden können. Hierfür wird einfach
    bei jedem Druck auf den Button ein Wert in der Redis-Datenbank getoggelt.
    """

    def __init__(self, configfile):
        """
        Konstruktor. Liest die Konfigurationsdatei ein und stellt eine Verbindung
        zur Redis-Datenbank her.
        """
        # Logger konfigurieren
        self._logger = logging.getLogger()
        self._logger.setLevel(logging.INFO)
    
        formatter = logging.Formatter("[%(asctime)s] %(message)s")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

        # Konfigurationsdatei einlesen
        self._logger.info("Lese Konfigurationsdatei app.conf")
        self._config = configparser.ConfigParser(interpolation=None)
        self._config.read(configfile)

        # Verbindung zur Redis-Datenbank herstellen
        redis_config = {
            "host": os.getenv("REDIS_HOST") or self._config["redis"]["host"],
            "port": os.getenv("REDIS_PORT") or self._config["redis"]["port"],
            "db":   os.getenv("REDIS_DB")   or self._config["redis"]["db"],
        }

        redis_config["port"] = int(redis_config["port"])
        redis_config["db"]   = int(redis_config["db"])

        self._logger.info("Stelle Verbindung zu Redis her: host=%(host)s, port=%(port)s, db=%(db)s" % redis_config)
        self._redis = redis.Redis(decode_responses=True, **redis_config)

    def main(self):
        """
        Hauptverarbeitung des Skripts. Initialisiert den GPIO und startet eine
        Endlosschleife, um das Programm am Laufen zu halten.
        """
        pin           = os.getenv("BUTTON_PIN")           or self._config["button"]["pin"]
        pull_up_down  = os.getenv("BUTTON_PULL_UP_DOWN")  or self._config["button"]["pull_up_down"]
        event         = os.getenv("BUTTON_EVENT")         or self._config["button"]["event"]
        bounce_millis = os.getenv("BUTTON_BOUNCE_MILLIS") or self._config["button"]["bounce_millis"]

        pin = int(pin)
        bounce_millis = int(bounce_millis)

        if pull_up_down.upper() == "UP":
            pull_up_down = GPIO.PUD_UP
        else:
            pull_up_down = GPIO.PUD_DOWN
        
        if event.upper() == "RISING":
            event = GPIO.RISING
        else:
            event = GPIO.FALLING

        self._logger.info("Initialisiere GPIO: pin = %s, pull_up_down=%s, event=%s" % (pin, pull_up_down, event))

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN, pull_up_down=pull_up_down)
        GPIO.add_event_detect(pin, event, bouncetime=bounce_millis)
        GPIO.add_event_callback(pin, self._on_button_pressed)

        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            pass
        finally:
            self._logger.info("Räume GPIO auf")
            GPIO.cleanup(pin)
    
    def _on_button_pressed(self, channel):
        """
        Wert in der Datenbank ändern, wenn der Button gedrückt wurde.

        THREADING: Diese Metheode läuft in einem separaten GPIO-Thread
        """
        enabled = self._redis.get(REDIS_KEY_MEASUREMENT_ENABLED) != "0"

        if enabled:
            self._logger.info("Button wurde gedrückt: Stoppe Messung")
            self._redis.set(REDIS_KEY_MEASUREMENT_ENABLED, "0")
        else:
            self._logger.info("Button wurde gedrückt: Reaktiviere Messung")
            self._redis.set(REDIS_KEY_MEASUREMENT_ENABLED, "1")

if __name__ == "__main__":
    configfile = "app.conf"

    if len(sys.argv) > 1:
        configfile = sys.argv[1]

    app = App(configfile)
    app.main()
