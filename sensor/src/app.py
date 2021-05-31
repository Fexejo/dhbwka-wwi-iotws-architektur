#! /bin/env python

import redis
from smbus2 import SMBus
import configparser, logging, pprint, os, random, sys, time, math

REDIS_KEY_MEASUREMENT_INTERVAL = "measurement:interval"
REDIS_KEY_MEASUREMENT_ENABLED = "measurement:enabled"
REDIS_KEY_MEASUREMENT_VALUES = "measurement:values"


class App:
    """
    Beispiel für ein einfaches Python-Skript zur Messung von Sensorwerten und Ablage
    dieser in einer Redis-Datenbank. Das Skript liest die Konfigurationsdatei `app.conf`
    ein, um herauszufinden, was es tun soll. Die Messwerte werden als Stream in der
    Datenbank abgelegt. Zusätzlich können durch entsprechende Einträge in der Datenbank
    die Messung aus der Ferne unterbrochen sowie das Messintervall überschrieben werden.
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

        self._pp = pprint.PrettyPrinter(indent=4)

        # Konfigurationsdatei einlesen
        self._logger.info("Lese Konfigurationsdatei app.conf")
        self._config = configparser.ConfigParser(interpolation=None)
        self._config.read(configfile)

        # Verbindung zur Redis-Datenbank herstellen
        redis_config = {
            "host": os.getenv("REDIS_HOST") or self._config["redis"]["host"],
            "port": os.getenv("REDIS_PORT") or self._config["redis"]["port"],
            "db": os.getenv("REDIS_DB") or self._config["redis"]["db"],
        }

        redis_config["port"] = int(redis_config["port"])
        redis_config["db"] = int(redis_config["db"])

        self._logger.info(
            "Stelle Verbindung zu Redis her: host=%(host)s, port=%(port)s, db=%(db)s"
            % redis_config
        )
        self._redis = redis.Redis(decode_responses=True, **redis_config)

        # Voreingestelltes Messintervall
        self._interval_seconds = float(
            os.getenv("INTERVAL_SECONDS")
            or self._config["measurement"]["interval_seconds"]
        )
        self._enabled = True

    def main(self):
        """
        Hauptverarbeitung des Skripts. Startet eine Endlosschleife zur Messung der
        Daten und Speicherung in der Redis-Datenbank.
        """
        try:
            while True:
                if self._is_measurement_enabled():
                    mesaurement = self._perform_mesaurement()
                    self._save_measurement(mesaurement)

                interval_seconds = self._read_measurement_interval()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            pass

    def _is_measurement_enabled(self):
        """
        Prüft den Eintrag REDIS_KEY_MEASUREMENT_ENABLED in Redis, um festzustellen,
        ob überhaupt Messungen vorgenommen werden sollen. Jeder Wert ungleich dem
        String "0" wird dabei als Ja interpretiert. Fehlt der Eintrag, wird der in
        self._enabled hinterlegte, zuletzt bekannte Werte verwendet.
        """
        enabled = self._redis.get(REDIS_KEY_MEASUREMENT_ENABLED)

        if enabled == None:
            return self._enabled

        enabled = enabled != "0"

        if not enabled == self._enabled:
            self._enabled = enabled
            self._logger.info(
                "Messung wird fortgeführt" if enabled else "Messung wird unterbrochen"
            )

        return enabled

    def _read_measurement_interval(self):
        """
        Liest den Eintrag REDIS_KEY_MEASUREMENT_INTERVAL in Redis mit der Anzahl Sekunden
        zwischen zwei Messungen. Fehlt der Eintrag, wird der in self._interval_seconds
        hinterlegte, zuletzt bekannte Werte verwendet.
        """
        interval_seconds = self._redis.get(REDIS_KEY_MEASUREMENT_INTERVAL)

        if interval_seconds == None:
            return self._interval_seconds

        interval_seconds = float(interval_seconds)

        if not interval_seconds == self._interval_seconds:
            self._interval_seconds = interval_seconds
            self._logger.info("Neues Messintervall: %s Sekunde(n)" % interval_seconds)

        return interval_seconds

    def _perform_mesaurement(self):
        self._logger.info("Starte neue Messung")

        # Beispiel: Wir messen Beschleunigung und Rotation des Sensors.
        # Register
        power_mgmt_1 = 0x6B
        power_mgmt_2 = 0x6C

        def read_byte(reg):
            return bus.read_byte_data(address, reg)

        def read_word(reg):
            h = bus.read_byte_data(address, reg)
            l = bus.read_byte_data(address, reg + 1)
            value = (h << 8) + l
            return value

        def read_word_2c(reg):
            val = read_word(reg)
            if val >= 0x8000:
                return -((65535 - val) + 1)
            else:
                return val

        def dist(a, b):
            return math.sqrt((a * a) + (b * b))

        def get_y_rotation(x, y, z):
            radians = math.atan2(x, dist(y, z))
            return -math.degrees(radians)

        def get_x_rotation(x, y, z):
            radians = math.atan2(y, dist(x, z))
            return math.degrees(radians)

        bus = SMBus(1)  # bus = smbus.SMBus(0) fuer Revision 1
        address = 0x68  # via i2cdetect

        # Aktivieren, um das Modul ansprechen zu koennen
        bus.write_byte_data(address, power_mgmt_1, 0)

        # Beschleunigungs- und Rotationsmessungen auslesen
        gyroskop_xout = read_word_2c(0x43)
        gyroskop_yout = read_word_2c(0x45)
        gyroskop_zout = read_word_2c(0x47)

        beschleunigung_xout = read_word_2c(0x3B)
        beschleunigung_yout = read_word_2c(0x3D)
        beschleunigung_zout = read_word_2c(0x3F)

        beschleunigung_xout_skaliert = beschleunigung_xout / 16384.0
        beschleunigung_yout_skaliert = beschleunigung_yout / 16384.0
        beschleunigung_zout_skaliert = beschleunigung_zout / 16384.0

        # Werte in Dictionary speichern
        reading = {
            "X_acceleration": beschleunigung_xout_skaliert,
            "Y_acceleration": beschleunigung_yout_skaliert,
            "Z_acceleration": beschleunigung_zout_skaliert,
            "X_rotation": gyroskop_xout,
            "Y_rotation": gyroskop_yout,
            "Z_rotation": gyroskop_zout,
        }

        return reading

    def _save_measurement(self, measurement):
        """
        Speichert das Ergebnis einer Messung in der Redis-Datenbank, indem dem
        Stream REDIS_KEY_MEASUREMENT_VALUES ein neuer Eintrag hinzugefügt wird.
        Die Messwerte müssen hierfür als Dictionary übergeben werden.
        """
        self._logger.info("Speichere Messwerte: %s" % self._pp.pformat(measurement))
        self._redis.xadd(REDIS_KEY_MEASUREMENT_VALUES, measurement)


if __name__ == "__main__":
    configfile = "app.conf"

    if len(sys.argv) > 1:
        configfile = sys.argv[1]

    app = App(configfile)
    app.main()
