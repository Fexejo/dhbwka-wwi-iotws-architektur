Start/Stop-Button
=================

Beschreibung
------------

Dieses Programm zeigt beispielhaft, wie mehrere Programme gleichzeitig auf die Daten
in der Redis-Datenbank zugreifen können, um miteinander zu kommunizieren. Hier wird
als Beispiel einfach ein am Raspberry Pi angeschlossener Hardware-Button überwacht
und bei jedem Druck der Wert `measurement:enabled` in der Datenbank umgeschaltet, um
die Sensormessungen zu unterbrechen bzw. fortzusetzen.

Umgebungsvariablen
------------------

Folgende Umgebungsvariablen sollten in der `docker-compose.yml` gesetzt werden:

 * `REDIS_HOST`: Hostname des lokalen Redis-Servers
 * `REDIS_PORT`: Portnummer des lokalen Redis-Servers
 * `REDIS_DB`: Datenbanknummer des lokalen Redis-Servers

Folgende Umgebungsvariablen können in der Balena Cloud überschrieben werden:

 * `BUTTON_PIN`: GPIO-Pin des Buttons
 * `BUTTON_PULL_UP_DOWN`: Internen Pull Up oder Pull Down aktivieren ("UP" oder "DOWN")
 * `BUTTON_EVENT`: Auslösendes Ereignis für Buttondruck ("RAISING" oder "FALLING")
 * `BUTTON_BOUNCE_MILLIS`: Anzahl Millisekunden zum Debouncen des Buttons

Siehe hierzu auch die Kommentare in der Datei `app.conf`.