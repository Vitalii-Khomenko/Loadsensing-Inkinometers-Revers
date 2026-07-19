# Projektbericht: Lokale Verwaltung der TIL90-Sensoren

**Stand:** 15. Juli 2026  
**Zielgruppe:** Kolleginnen und Kollegen aus Technik, Projektleitung und Baustellenbetrieb

## Worum geht es?

Wir haben untersucht, wie unsere TIL90-Neigungssensoren direkt mit einem Linux-Computer verbunden und verwaltet werden können. Bisher wurden viele Arbeiten hauptsächlich mit der offiziellen Smartphone-App durchgeführt. Unser Ziel war eine zusätzliche, unabhängige Lösung für Prüfung, Datenauslesung, Konfiguration und Wiederherstellung.

Die neue Lösung arbeitet lokal über ein USB-Kabel. Für die grundlegende Bedienung sind weder ein Smartphone noch eine Cloud-Verbindung notwendig.

## Was wurde erreicht?

Wir können den Sensor zuverlässig erkennen und wichtige Informationen verständlich anzeigen, zum Beispiel:

- Sensor- und Seriennummer;
- Firmware-Version;
- Batteriestand und Temperatur;
- aktuelle Neigungswerte für X, Y und Z;
- Messintervall und gespeicherte Messwerte;
- Funkstatus, Funkleistung und Netzwerkinformationen;
- aktivierte Messachsen und Kalibrierungsdaten.

Zusätzlich wurde eine lokale Weboberfläche entwickelt. Sie läuft im Browser und zeigt die Informationen übersichtlich an, ohne dass technische Rohdaten gelesen werden müssen.

## Konfiguration und Datensicherung

Über die Weboberfläche können bereits mehrere Einstellungen geändert werden:

- Messintervall;
- aktivierte X-, Y- und Z-Achsen;
- Zeitplanung für die Funkübertragung;
- Gateway-Netzwerknummer und Passwort.

Vor wichtigen Änderungen kann eine vollständige Sicherung der Sensoreinstellungen erstellt werden. Die Sicherung wird geprüft, damit beschädigte oder falsche Dateien nicht versehentlich verwendet werden.

## Wiederherstellung und Firmware

Die besonders wichtigen Wiederherstellungsfunktionen wurden an einem echten Sensor erfolgreich getestet:

- Neustart des Sensors;
- Zurücksetzen auf Werkseinstellungen;
- Wiederherstellung der vorherigen Konfiguration;
- erneute Installation der passenden Firmware-Version 2.81;
- Kontrolle aller Einstellungen nach dem Neustart.

Nach dem Test entsprach die Konfiguration wieder vollständig der Sicherung vor dem Zurücksetzen. Der Sensor blieb funktionsfähig und konnte weiterhin normal ausgelesen werden.

Für gefährliche Aktionen gibt es zusätzliche Sicherheitsabfragen. Ein Zurücksetzen über die Weboberfläche wird direkt mit Wiederherstellung und Kontrolle verbunden. Dadurch wird das Risiko reduziert, einen Sensor versehentlich mit falschen Grundeinstellungen zurückzulassen.

## Speicherung und Überwachung

Messungen können lokal auf dem Computer gespeichert werden. Die Anwendung unterstützt außerdem:

- regelmäßige automatische Messungen;
- lokale Warnungen bei Grenzwertüberschreitungen;
- Warnungen bei niedrigem Batteriestand oder fehlenden Daten;
- Import älterer Messwerte aus dem Sensor;
- Fortsetzung eines unterbrochenen Datenimports;
- Export der Messwerte als CSV-Datei.

Damit kann der Industrie-PC auf einer Baustelle nicht nur zur Konfiguration, sondern auch als lokale Mess- und Überwachungsstation verwendet werden.

## Welchen Nutzen kann das in Zukunft bringen?

Die Lösung kann uns langfristig mehrere Vorteile bieten:

1. **Weniger Abhängigkeit vom Smartphone**  
   Sensoren können direkt am Linux-Computer geprüft und eingerichtet werden.

2. **Schnellere Fehlersuche**  
   Bei Verbindungsproblemen können USB, Sensorantwort, Konfiguration und Firmware getrennt geprüft werden.

3. **Sichere Wiederherstellung**  
   Nach Reparaturen oder fehlerhaften Einstellungen kann eine bekannte Konfiguration wiederhergestellt werden.

4. **Zentrale Verwaltung mehrerer Sensoren**  
   Später könnten mehrere Sensoren an einem Industrie-PC oder an kleinen Linux-Controllern betrieben und gemeinsam überwacht werden.

5. **Lokale Daten ohne Cloud-Abhängigkeit**  
   Messwerte könnten auf der Baustelle gespeichert, ausgewertet und anschließend an unseren eigenen Server übertragen werden.

6. **Eigene Berichte und Alarme**  
   Grenzwerte, Baustellenberichte und Benachrichtigungen könnten an unsere internen Abläufe angepasst werden.

7. **Anbindung eines Gateways**  
   Mit einem Test-Gateway können wir später prüfen, ob die empfangenen Funkdaten direkt über unseren Industrie-PC verarbeitet und ohne fremde Cloud an unseren Server gesendet werden können.

## Was ist noch offen?

Einige Punkte benötigen weitere Geräte oder längere Tests:

- vollständiger Funk-Test mit einem echten Gateway;
- Langzeittest über mehrere Tage;
- gleichzeitiger Betrieb mehrerer Sensoren;
- Prüfung der Messgenauigkeit mit bekannten Referenzwinkeln;
- automatische Berichte für Baustellen und Projekte;
- Installation als dauerhaft laufender Dienst auf einem Industrie-PC;
- Tests für unterschiedliche Sensor- und Firmware-Versionen.

Eine neuere Firmware als Version 2.81 war in der untersuchten offiziellen Anwendung nicht vorhanden. Aktuell ist deshalb eine sichere Wiederherstellung dieser Version möglich, aber noch kein Upgrade auf eine neuere Version.

## Zusammenfassung

Wir haben eine funktionierende lokale Alternative für viele Aufgaben der offiziellen Android-App geschaffen. Der Sensor kann direkt unter Linux ausgelesen, konfiguriert, gesichert und wiederhergestellt werden. Auch das Zurücksetzen und die Firmware-Wiederherstellung wurden erfolgreich an echter Hardware geprüft.

Der nächste große Schritt ist der Test mit einem Gateway. Danach können wir beurteilen, wie weit sich eine vollständige lokale Lösung für Baustellenbetrieb, zentrale Überwachung und Übertragung an unsere eigenen Server umsetzen lässt.
