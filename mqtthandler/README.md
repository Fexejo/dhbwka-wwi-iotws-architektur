MQTT-Handler
============

Beschreibung
------------

Dieses Programm liest regelmäßig die neusten Messwerte aus der Redis-Datenbank
und versendet diese via MQTT an den Rest der Welt. Das Programm merkt sich dabei
in der Datenbank, welcher Messwert als letztes verschickt wurde und stellt sicher,
dass bei jedem Durchlauf alle nachfolgenden Werte versendet werden. Selbst wenn
das Programm mal eine Weile nicht läuft, gehen keine Messwerte verlorsen. Der
Versand wird einfach beim nächsten Programmstart nachgeholt.

Zusätzlich implementiert das Programm ein einfaches Protokoll, um die Devices
via MQTT aus der Ferne steuern zu können. Details zu den hierbei ausgetauschten
MQTT-Nachrichten finden sich am Anfang der Datei `app.py`.

Umgebungsvariablen
------------------

Folgende Umgebungsvariablen sollten in der `docker-compose.yml` gesetzt werden:

 * `REDIS_HOST`: Hostname des lokalen Redis-Servers
 * `REDIS_PORT`: Portnummer des lokalen Redis-Servers
 * `REDIS_DB`: Datenbanknummer des lokalen Redis-Servers

Folgende Umgebungsvariablen können in der Balena Cloud überschrieben werden:

  * `MQTT_HOST`: Hostname des MQTT-Brokers
  * `MQTT_PORT`: Portnummer des MQTT-Brokers
  * `MQTT_KEEPALIVE_SECONDS`: Anzahl Sekunden für MQTT Keep Alive

Folgende Umgebungsvariablen können optional ebenfalls überschrieben werden:

  * `MQTT_USERNAME`: Benutzername zur Authentifizierung am MQTT-Broker
  * `MQTT_PASSWORD`: Passwort zur Authentifizierung am MQTT-Broker
  * `MQTT_TLS_INSECURE`: Unsichere TLS-Zertifikate des MQTT-Brokers zulassen
  * `MQTT_TLS_CA_CERTS`: Datei mit vertrauenswürdigen CA-Zertifikaten
  * `MQTT_TLS_CERTFILE`: Datei mit dem zu verwendenden Client-Zertifikat
  * `MQTT_TLS_KEYFILE`: Datei mit dem Private Key des Client-Zertifikats
  * `MQTT_TOPIC_BROADCAST`: MQTT-Topic, um Kommandos an alle Devices zu schicken
  * `MQTT_TOPIC_REQUEST`: MQTT-Topic, um Kommandos an dieses Device zu schicken
  * `MQTT_TOPIC_RESPONSE`: MQTT-Topic, an das Kommandoantworten geschickt werden
  * `MQTT_TOPIC_VALUES`: MQTT-Topic, an das die Messwerte gesendet werden

 Die MQTT-Topics können folgende Platzhalter beinhalten, die genau den Werten
 aus dem Konfigurationsbschnitt `[balena]`bzw. den dazugehörigen Umgebungsvariablen
 entsprechen:

  * `%(device_uuid)s`: Technische Geräte-UUID
  * `%(app_id)s`: Technische Anwendungs-ID 
  * `%(app_name)s`: Name der Anwendung
  * `%(device_type)s`: Hardwareplattform

Siehe hierzu auch die Kommentare in der Datei `app.conf`.

Laufzeitkonfiguration
---------------------

Folgende Keys in Redis beeinflussen das Laufzeitverhalten dieses Programms.
Sie können von anderen Programmen geschrieben werden, um Einfluss auf den
Versand der Messwerte zu nehmen:

 * `mqtt_sender:enabled`: 1 = Versand eingeschaltet, 0 = Versand ausgeschaltet
 * `mqtt_sender:interval`: Abstand zwischen zwei Sendungen in Sekunden
 * `mqtt_sender:last_id`: Letzte bereits verschickte Messwert-ID