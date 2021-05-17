Sensordaten ermitteln
=====================

Beschreibung
------------

Dieses Programm kümmert sich um die Ansteuerung der Sensoren des IoT-Devices
zur periodischen Ermittlung der Messwerte. Gemäß der Aufgabenteilung der
verschiedenen deviceseitigen Programme, werden die Messwerte hier nicht
weiterverarbeitet, sondern einfach in einen Redis Stream geschrieben. Das
Auslesen und Verarbeiten der Streamdaten erfolgt durch die anderen Programme.

Umgebungsvariablen
------------------

Folgende Umgebungsvariablen sollten in der `docker-compose.yml` gesetzt werden:

 * `REDIS_HOST`: Hostname des lokalen Redis-Servers
 * `REDIS_PORT`: Portnummer des lokalen Redis-Servers
 * `REDIS_DB`: Datenbanknummer des lokalen Redis-Servers

Folgende Umgebungsvariablen können in der Balena Cloud überschrieben werden:

 * `INTERVAL_SECONDS`: Abstand in Sekunden zwischen zwei Messungen

Siehe hierzu auch die Kommentare in der Datei `app.conf`.

Laufzeitkonfiguration
---------------------

Folgende Keys in Redis beeinflussen das Laufzeitverhalten dieses Programms.
Sie können von anderen Programmen geschrieben werden, um Einfluss auf die
Messungen zu nehmen:

 * `measurement:enabled`: 1 = Messung eingeschaltet, 0 = Messung ausgeschaltet
 * `measurement:interval`: Abstand zwischen zwei Messungen in Sekunden