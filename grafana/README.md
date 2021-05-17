Grafana Dashboard
=================

Beschreibung
------------

Dieser Container stellt ein lokales Grafana-Dashboard zur Verfügung, das als Webserver
auf dem IoT-Device läuft. Das Dashboard kann unter die Portnummer 3000 erreicht werden.
Die Anmeldedaten sind (aus dem Vorlage-Container von Grafana):

    Benutzer: admin
    Passwort: admin

![Screenshot](screenshot.png)

Umgebungsvariablen
------------------

Folgende Umgebungsvariablen sollten in der `docker-compose.yml` gesetzt werden, um den
Container zu konfigurieren:

 * `REDIS_HOST`: Hostname des lokalen Redis-Servers
 * `REDIS_PORT`: Portnummer des lokalen Redis-Servers
 * `REDIS_DB`: Datenbanknummer des lokalen Redis-Servers

Gemäß Docker-Konvention entspricht der Redis-Hostname dem Namen seines Dockercontainers.