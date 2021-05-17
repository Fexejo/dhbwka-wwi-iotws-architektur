Deviceseitiger Softwarestack
============================

Dieses Verzeichnis enthält die Quellcodes und Softwarekomponenten für die IoT-Devices.
Jede Komponente besitzt ihren eigenen Docker-Container, so dass sie mit dem Balena CLI
bzw. der Balena Cloud auf die Devices verteilt werden kann.

 * `redis`: Zentraler Redis-Server
 * `sensor`: Python-Programm zum Auslesen der Sensordaten und Ablage in Redis
 * `startstopbutton`: Python-Programm zum Starten und Stoppen der Sensormessungen
 * `mqtthandler`: Python-Programm zum Versand der Sensordaten via MQTT
 * `grafana`: Lokales Grafana-Dashboard zur Überwachung der Devices