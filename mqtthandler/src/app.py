#! /bin/env python

import redis, paho.mqtt.client as mqtt
import configparser, json, logging, os, subprocess, time, sys

REDIS_KEY_MEASUREMENT_VALUES   = "measurement:values"
REDIS_KEY_MQTT_SENDER_INTERVAL = "mqtt_sender:interval"
REDIS_KEY_MQTT_SENDER_ENABLED  = "mqtt_sender:enabled"
REDIS_KEY_MQTT_SENDER_LAST_ID  = "mqtt_sender:last_id"

class App:
    """
    Verbindungsprogramm zwischen Redis und dem MQTT-Broker. Überwacht den
    Sensorstream in Redis und sendet die Werte via MQTT an den Rest der Welt.
    Zusätzlich werden via MQTT empfangene Kommandos in Redis gespeichert,
    um das Device zu steuern. Hierfür werden folgende in der Konfiguration
    hinterlegte MQTT-Topics verwendet:

      * topic_values: An dieses Topic werden die Messwerte gesendet. QOS = 1.

      * topic_broadcast: Aus diesem Topic werden Befehle, die an alle
            momentan aktiven Devices gehen sollen, ausgelesen

      * topic_request: Aus diesem Topic werden Befehle für ein einzelnes
            Device ausgelesen. Das Topic muss daher die Device UUID im
            Namen enthalten.
    
      * topic_response: An dieses Topic wird die Antwort auf einen empfangen
            Befehl gesendet, falls dieser eine Antwort erfordert. QOS = 0.
    
    Die Sensordaten werden als UTF-8 kodierte JSON-Liste im folgenden
    Format versendet:

        [
            {
                "_id": "1621122796939-0",
                "_device_uuid": "6076a30f1cfaca6636db7f89c83507fc",
                "_device_type": "raspberrypi",
                "_app_id": "1829540",
                "_app_name": "IoT-Projekt",
                "temperature_celsius": "20.3",
                "humidity_percent": "74",
            }, {
                "_id": "1621122797943-0",
                "_device_uuid": "6076a30f1cfaca6636db7f89c83507fc",
                "_device_type": "raspberrypi",
                "_app_id": "1829540",
                "_app_name": "IoT-Projekt",
                "temperature_celsius": "20.8",
                "humidity_percent": "72",
            }, {
                …
            }
        ]
    
    Jeder Eintrag entspricht dabei einem JSON-Objekt mit genau einer Messung.
    `_id` ist die ID des Messwertes aus der Redis-Datenbank und entspricht
    daher dem Unix Timestamp mit einer angehängten Laufnummer. Alle anderen
    Werte mit Unterstrich am Anfang sind Verwaltungsdaten zur Identifikation
    des IoT-Devices. Werte ohne Unterstrich sind Sensordaten aus Redis.

    Über die anderen beiden Topics können folgende Befehle ebenfalls als UTF-8
    kodierte JSON-Objekte emfpangen werden:

      * {"command": "reboot"}

        Gerät neustarten. Liefert folgende Antwort:
        {"command": "reboot"}

        Da der Neustart direkt ausgeführt wird, kann es aber vorkommen, dass die
        Antwort nicht mehr rechtzeitig verschickt werden kann. Außerdem wird die
        Verbindung zum MQTT-Server und zur Datenbank ggf. nicht sauber geschlossen.

      * {"command": "get_config", "key": "xxx"}

        Konfigurationswert aus Redis auslesen. Liefert folgende Antwort:
        {"command: "get_config", "key": "xxx", "value": "yyy"}

      * {"command": "set_config", "key": "xxx", "value": "yyy"}

        Konfigurationswert in Redis ändern. Liefert folgende Antwort:
        {"command: "set_config", "key": "xxx", "value": "yyy"}
    
      * {"command": "send_measurements": "min_id": "-", "max_id": "+", "count": 999}

        Direkte Abfrage von Messwerten innerhalb des gegebenen Ranges.
        Die Parameter `min_id`, `max_id` und `count` sind optional und
        entsprechen den Parametern des Redis-Befehls XRANGE. Hat keine
        Auswirkung auf den ohnehin stattfindenden, automatischen Versand.

        Die Antwort wird an das `topic_values` im selben Format gesendet,
        wie beim automatischen Versand der Messwerte.
    
    Die zulässigen Konfigurationswerte werden hier nicht geprüft, um bei
    Einführung weiterer Werte das Programm nicht ständig erweitern zu
    müssen. Sie werden stattdessen unter dem angegebenen Key direkt in der
    Redis-Datenbank abgelegt. Die anderen Programme lesen sie dann ggf.
    regelmäßig aus der Datenbank aus, um ihr Verhalten anzupassen. Die
    MQTT-Kommunikation sollte daher entsprechend abgesichert werden.
    
    Dieses Programm reagiert auf folgende Konfigurationswerte:

      * mqtt_sender:interval  ->  Sendeintervall in Sekunden
      * mqtt_sender:enabled   ->  1 = Versand aktiv, 0 = Versand gestoppt
      * mqtt_sender:last_id   ->  Versand ab folgender ID wiederholen
    
    Bei `mqtt_sender:last_id` sollte die übermittelte ID mit einer runden
    Klammer beginnen, um alle Messungen **nach** dieser ID zu liefern.
    """

    def __init__(self, configfile):
        """
        Konstruktor. Liest die Konfigurationsdatei ein und stellt eine Verbindung
        zur Redis-Datenbank und dem MQTT-Broker her.
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

        # Balena Device ID und App ID
        self._balena = {
            "device_uuid": os.getenv("BALENA_DEVICE_UUID") or self._config["balena"]["device_uuid"],
            "device_type": os.getenv("BALENA_DEVICE_TYPE") or self._config["balena"]["device_type"],
            "app_id":      os.getenv("BALENA_APP_ID")      or self._config["balena"]["app_id"],
            "app_name":    os.getenv("BALENA_APP_NAME")    or self._config["balena"]["app_name"],
        }

        # Voreingestelltes Sendeintervall
        self._interval_seconds = float(os.getenv("INTERVAL_SECONDS") or self._config["main"]["interval_seconds"])
        self._enabled = True
        self._last_id = "-"

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

        # Verbindung zum MQTT-Broker herstellen
        self._mqtt_connected = False

        self._mqtt_config = {
            "host":            os.getenv("MQTT_HOST")              or self._config["mqtt"]["host"],
            "port":            os.getenv("MQTT_PORT")              or self._config["mqtt"]["port"],
            "keepalive":       os.getenv("MQTT_KEEPALIVE_SECONDS") or self._config["mqtt"]["keepalive_seconds"],
            "username":        os.getenv("MQTT_USERNAME")          or self._config["mqtt"]["username"],
            "password":        os.getenv("MQTT_PASSWORD")          or self._config["mqtt"]["password"],
            "tls_insecure":    os.getenv("MQTT_TLS_INSECURE")      or self._config["mqtt"]["tls_insecure"],
            "tls_ca_certs":    os.getenv("MQTT_TLS_CA_CERTS")      or self._config["mqtt"]["tls_ca_certs"],
            "tls_certfile":    os.getenv("MQTT_TLS_CERTFILE")      or self._config["mqtt"]["tls_certfile"],
            "tls_keyfile":     os.getenv("MQTT_TLS_KEYFILE")       or self._config["mqtt"]["tls_keyfile"],
            "topic_broadcast": os.getenv("MQTT_TOPIC_BROADCAST")   or self._config["mqtt"]["topic_broadcast"],
            "topic_request":   os.getenv("MQTT_TOPIC_REQUEST")     or self._config["mqtt"]["topic_request"],
            "topic_response":  os.getenv("MQTT_TOPIC_RESPONSE")    or self._config["mqtt"]["topic_response"],
            "topic_values":    os.getenv("MQTT_TOPIC_VALUES")      or self._config["mqtt"]["topic_values"],
        }

        self._mqtt_config["port"]            = int(self._mqtt_config["port"])
        self._mqtt_config["keepalive"]       = int(self._mqtt_config["keepalive"])
        self._mqtt_config["tls_insecure"]    = self._mqtt_config["tls_insecure"].upper() == "TRUE"
        self._mqtt_config["topic_broadcast"] = self._mqtt_config["topic_broadcast"] % self._balena
        self._mqtt_config["topic_request"]   = self._mqtt_config["topic_request"]   % self._balena
        self._mqtt_config["topic_response"]  = self._mqtt_config["topic_response"]  % self._balena
        self._mqtt_config["topic_values"]    = self._mqtt_config["topic_values"]    % self._balena

        self._logger.info("Stelle Verbindung zum MQTT-Broker her: host=%(host)s, port=%(port)s, keepalive_seconds=%(keepalive)s" % self._mqtt_config)

        self._mqtt = mqtt.Client()
        self._mqtt.on_connect = self._on_mqtt_connect
        self._mqtt.on_disconnect = self._on_mqtt_disconnect

        self._mqtt.connect(host=self._mqtt_config["host"], port=self._mqtt_config["port"], keepalive=self._mqtt_config["keepalive"])
        
        if self._mqtt_config["tls_ca_certs"] or self._mqtt_config["tls_certfile"] or self._mqtt_config["tls_keyfile"]:
            self._logger.info(
                "Setze TLS-Parameter für die MQTT-Verbindung: "
                "tls_ca_certs=%(tls_ca_certs)s, tls_certfile=%(tls_certfile)s, tls_keyfile=%(tls_keyfile)s" % self._mqtt_config
            )

            self._mqtt.tls_set(ca_certs=self._mqtt_config["tls_ca_certs"], certfile=self._mqtt_config["tls_certfile"], keyfile=self._mqtt_config["tls_keyfile"])

        if self._mqtt_config["tls_insecure"]:
            self._logger.info("Erlaube unsichere TLS-Zertifikate für die Verbindung zum MQTT-Broker")
            self._mqtt.tls_insecure_set(True)

        if self._mqtt_config["username"] or self._mqtt_config["password"]:
            self._logger.info("Setze Benutzername und Passwort für den MQTT-Broker")
            self._mqtt.username_pw_set(username=self._mqtt_config["username"], password=self._mqtt_config["password"])

    def main(self):
        """
        Hauptverarbeitung des Skripts. Startet eine Endlosschleife zum Auslesen der
        aktuellsten Messwerte aus Redis und ihrem Versand via MQTT.
        """
        try:
            self._mqtt.loop_start()

            while True:
                if self._is_sender_enabled() and self._mqtt_connected:
                    last_id = self._read_sender_last_id()
                    measurements, last_id = self._read_measurements(last_id)

                    if measurements:
                        self._send_measurements(measurements)
                        self._save_sender_last_id(last_id)

                interval_seconds = self._read_sender_interval()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            self._logger.info("Trenne Verbindung zum MQTT-Broker")
            self._mqtt.loop_stop()
            self._mqtt.disconnect()

    def _is_sender_enabled(self):
        """
        Prüft den Eintrag REDIS_KEY_MQTT_SENDER_ENABLED in Redis, um festzustellen,
        ob die aufgelaufenen Messwerte überhaupt versendet werden sollen. Jeder Wert
        ungleich dem String "0" wird dabei als Ja interpretiert. Fehlt der Eintrag,
        wird der in self._enabled hinterlegte, zuletzt bekannte Werte verwendet.
        """
        enabled = self._redis.get(REDIS_KEY_MQTT_SENDER_ENABLED)

        if enabled == None:
            return self._enabled
        
        enabled = enabled != "0"

        if not enabled == self._enabled:
            self._enabled = enabled
            self._logger.info("Versand wird fortgeführt" if enabled else "Versand wird unterbrochen")

        return enabled

    def _read_sender_interval(self):
        """
        Liest den Eintrag REDIS_KEY_MQTT_SENDER_INTERVAL in Redis mit der Anzahl Sekunden
        zwischen dem Versand der gesammelten Messwerte. Fehlt der Eintrag, wird der in
        self._interval_seconds hinterlegte, zuletzt bekannte Werte verwendet.
        """
        interval_seconds = self._redis.get(REDIS_KEY_MQTT_SENDER_INTERVAL)

        if interval_seconds == None:
            return self._interval_seconds
        
        interval_seconds = float(interval_seconds)

        if not interval_seconds == self._interval_seconds:
            self._interval_seconds = interval_seconds
            self._logger.info("Neues Sendeintervall: %s Sekunde(n)" % interval_seconds)
        
        return interval_seconds

    def _read_sender_last_id(self):
        """
        Liest den Eintrag REDIS_KEY_MQTT_SENDER_LAST_ID in Redis mit der ID der zuletzt
        versendeten Sensordaten. Fehlt der Eintrag, wird der in self._last_id hinterlegte,
        zuletzt bekannte Wert verwendet.
        """
        last_id = self._redis.get(REDIS_KEY_MQTT_SENDER_LAST_ID)

        if last_id == None:
            return self._last_id
        
        if not last_id == self._last_id:
            self._last_id = last_id
            self._logger.info("Vormerkung für Versand der Messwerte ab ID %s" % last_id)
        
        return last_id

    def _save_sender_last_id(self, last_id):
        """
        Legt die übergebene ID mit dem Key REDIS_KEY_MQTT_SENDER_LAST_ID in Redis ab, so dass
        beim nächsten Sendeversuch alle Events nach dieser ID verschickt werden.
        """
        self._last_id = last_id
        self._redis.set(REDIS_KEY_MQTT_SENDER_LAST_ID, last_id)
    
    def _read_measurements(self, min_id="-", max_id="+", count=None):
        """
        Liest den Redis-Stream REDIS_KEY_MEASUREMENT_VALUES mit den aktuellsten Messwerten
        innerhalb der übergebenen IDs. Entsprechend den Konventionen von Redis handelt es
        sich bei den IDs um Unix Timestamps mit angehängter Sequenznummer. Normalerweise
        wird als `min_id` die ID des zuletzt versendeten Messwerts (mit einer runden Klammer
        am Anfang) mitgegeben, um alle nachfolgenden Messungen zu ermitteln. Es können aber
        auch Unix Timestamps mitgegeben werden, um die gepufferten Messwerte eines bestimmten
        Zeitraums zu erhalten.
        
        Die Methode gibt immer genau zwei Werte zurück:

            1) Die Messwerte so, wie sie der XRANGE-Befehl von Redis liefert: Als Liste mit
               einem Tupel je Messwert. Das Tupel beinhaltet als erstes Element die ID der
               Messung und als zweiten Wert ein Dictionary mit den eigentlichen Werten. Jeder
               Eintrag im Dictionary entspricht dabei einem Sensor. Zum Beispiel:

                [
                    ("1621122796939-0", {"temperature_celsius": "20.3", "humidity_percent": "74"}),
                    ("1621122797943-0", {"temperature_celsius": "20.8", "humidity_percent": "72"}),
                    ("1621122798948-0", {"temperature_celsius": "20.1", "humidity_percent": "76"}),
                ]
            
            2) Die ID des letzten Messwertes mit vorangestellter runder Klammer, da dieser
               Wert dann direkt beim nächsten Aufruf der Methode verwendet werden kann, um
               alle Messungen **nach** dieser ID zu ermitteln.
        
        Wurden keine Messwerte gefunden, liefert die Methode eine leere Liste sowie die
        letzte ID des vorherigen Aufrufs zurück.
        """
        measurements = self._redis.xrange(REDIS_KEY_MEASUREMENT_VALUES, min=min_id, max=max_id, count=count)
        last_id = self._last_id

        if measurements:
            last_id = "(" + measurements[-1][0]

        return measurements, last_id

    def _send_measurements(self, measurements):
        """
        Nimmt die mit _read_measurements() ermittelten Messwerte entgegen und sendet sie
        an das als `topic_values` konfigurierte MQTT-Topic. Die Werte werden hierfür in
        einen UTF-8 kodierten JSON-String gemäß der Beschreibung am Anfang der Klasse
        unmgewandelt.
        """
        # Messwerte in eine etwas einfachere Form bringen, bei der jeder Messwert aus
        # genau einem Objekt mit einer `_id` sowie einem Key je Sensor besteht
        simplified_measurements = []

        for measurement in measurements:
            simplified_measurement = {
                "_id":          measurement[0],
                "_device_uuid": self._balena["device_uuid"],
                "_device_type": self._balena["device_type"],
                "_app_id":      self._balena["app_id"],
                "_app_name":    self._balena["app_name"],
            }

            for key in measurement[1]:
                simplified_measurement[key] = measurement[1][key]
            
            simplified_measurements.append(simplified_measurement)
        
        # JSON-String erzeugen und versenden
        self._logger.info("Sende Messwerte %(min_id)s bis %(max_id)s, Anzahl %(count)s" % {
            "min_id": simplified_measurements[0]["_id"],
            "max_id": simplified_measurements[-1]["_id"],
            "count": len(simplified_measurements),
        })

        json_payload = json.dumps(simplified_measurements)
        self._mqtt.publish(self._mqtt_config["topic_values"], payload=json_payload, qos=1)

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """
        Callback-Methode, die nach dem versuchten Verbindungsaufbau mit dem MQTT-Broker
        aufgerufen wird. Hier werden die überwachten Topics aboniert. Erfolgt hier und
        nicht im Konstruktur, damit die Abos bei einem erneuten Verbindungsaufbau nicht
        verloren gehen.

        THREADING: Diese Methode läuft im MQTT-Thread
        """
        rc_messages = {
            0: "Verbindung hergestellt",
            1: "Fehlercode 1 – Falsche Protokollversion",
            2: "Fehlercode 2 – Ungültige Client-ID",
            3: "Fehlercode 3 – Server nicht erreichbar",
            4: "Fehlercode 4 – Benutzername/Passwort falsch",
            5: "Fehlercode 5 – Keine Berechtigung"
        }

        rc_message = rc_messages.get(rc, "Fehlercode %s – Unbekannter Fehler" % rc)
        self._logger.info("Ergebnis des Verbindungsaufbaus mit dem MQTT-Broker: %s" % rc_message)

        if rc == 0:
            self._mqtt_connected = True

            self._mqtt.subscribe([
                (self._mqtt_config["topic_broadcast"], 0),
                (self._mqtt_config["topic_request"], 0)
            ])

            self._mqtt.message_callback_add(self._mqtt_config["topic_broadcast"], self._on_mqtt_command_received)
            self._mqtt.message_callback_add(self._mqtt_config["topic_request"], self._on_mqtt_command_received)
        else:
            self._mqtt_connected = False
        
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """
        Verhindert den weiteren Versand von Messwerten, solange keine Verbindung
        mit dem MQTT-Broker besteht.

        THREADING: Diese Methode läuft im MQTT-Thread
        """
        self._mqtt_connected = False

    def _on_mqtt_command_received(self, client, userdata, message):
        """
        Wertet ein über MQTT empfangenes Kommando zur Fernsteuerung des Devices aus
        und führt die jeweilige Aktion direkt aus.

        THREADING: Diese Methode läuft im MQTT-Thread
        """
        if message.topic == self._mqtt_config["topic_broadcast"]:
            self._logger.info("Empfange Broadcast an alle Devices: %s" % message.payload)
        else:
            self._logger.info("Empfange Kommando für dieses Device: %s" % message.payload)
        
        payload = json.loads(message.payload)
        command = payload.get("command", "").upper()

        # Device neustarten
        if command == "REBOOT":
            self._logger.info("Starte Device neu")

            self._mqtt.publish(
                qos     = 0,
                topic   = self._mqtt_config["topic_response"],
                payload = json.dumps({
                    "command": "reboot",
                })
            )

            subprocess.run([os.path.join(os.path.dirname(__file__), "reboot.sh")])

        # Konfigurationswert auslesen
        elif command == "GET_CONFIG":
            config_key = payload.get("key", "")

            if config_key:
                config_value = self._redis.get(config_key)
                self._logger.info("Lese Konfigurationswert %s=%s" % (config_key, config_value))

                self._mqtt.publish(
                    qos     = 0,
                    topic   = self._mqtt_config["topic_response"],
                    payload = json.dumps({
                        "command": "get_config",
                        "key": config_key,
                        "value": config_value,
                    }),
                )
        
        # Konfigurationswert ändern
        elif command == "SET_CONFIG":
            config_key = payload.get("key", "")
            config_value = payload.get("value", "")

            if config_key:
                self._logger.info("Setze Konfigurationswert %s=%s" % (config_key, config_value))
                self._redis.set(config_key, config_value)

                self._mqtt.publish(
                    qos     = 0,
                    topic   = self._mqtt_config["topic_response"],
                    payload = json.dumps({
                        "command": "set_config",
                        "key": config_key,
                        "value": config_value,
                    })
                )
    
        # Messwerte abfragen
        elif command == "SEND_MEASUREMENTS":
            kwargs = {
                "min_id": payload.get("min_id", "-"),
                "max_id": payload.get("max_id", "+"),
                "count":  payload.get("count", None),
            }

            if kwargs["count"]:
                kwargs["count"] = int(kwargs["count"])

            self._logger.info("Ermittle Messwerte: min_id=%(min_id)s, max_id=%(max_id)s, count=%(count)s" % kwargs)
            measurements = self._read_measurements(**kwargs)[0]
            
            if measurements:
                self._send_measurements(measurements)
        
        # Sonstiger, unbekannter Befehl
        else:
            self._logger.info("Unbekanntes Kommando: %s" % command)

if __name__ == "__main__":
    configfile = "app.conf"

    if len(sys.argv) > 1:
        configfile = sys.argv[1]

    app = App(configfile)
    app.main()
