Redis-Server
============

Beschreibung
------------

Dieser Container stellt einen lokalen Redis-Server auf dem IoT-Device zur Verfügung.
Es handelt sich dabei um das Herzstück des deviceseitigen Softwarestacks, da Redis
hier zum Persistieren der Messwerte sowie der Konfigurationswerte zur Steuerung des
Devices genutzt wird. Hierbei werden die Eigenschaften von Redis als strukturierter
Key-Value Store, der alle Daten aus dem Hauptspeicher bezieht, diese aber gleichzeitg
auch auf „Platte“ sichert, genutzt.

Die Architektur sieht vor, dass sich mehrere Clientanwendungen mit dem Redis-Server
verbinden, um dort entweder Sensordaten abzulegen (in einem Redis Stream) oder diese
zu lesen und zu verarbeiten. Der Server ist dabei so konfiguriert, dass im Falle eines
Stromausfalls maximal die Daten der letzten Sekunde verloren gehen können. Gleichzeitig
ist die Speichergröße der Datenbank begrenzt, um eine Art Ringpuffer zum Zwischenspeichern
der Messwerte vor ihrem Versand über das Internet zu realisieren. Die Größe ist dabei
mit 100 MB allerdings so großzügig dimensioniert, dass laut Redis-Dokumentation mindestens
eine halbe Million Messwerte gespeichert werden könnten.

Vgl. https://redis.io/topics/faq, What's the Redis memory footprint?

Umgebungsvariablen
------------------

Keine