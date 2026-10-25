# Console OS — Mac edition 0.1.1

Eerste USB-prototype voor een Intel MacBookPro9,2: een eigen gamemenu en GitHub-updatecode bovenop de bestaande Batocera Linux 43.1 x86_64-distributie. De Linux-kernel, drivers, EmulationStation en emulators zijn van hun oorspronkelijke makers. Dit project bouwt die onderdelen niet vanaf nul.

## Eerste start

1. Sluit de USB-stick en bij voorkeur de PS4-controller met een USB-datakabel aan.
2. Zet de MacBook aan en houd **Option/Alt** ingedrukt. Kies de USB-optie **EFI Boot**.
3. Laat de eerste start en het vergroten van de gebruikerspartitie afronden. Dat kan enkele minuten duren.
4. Configureer eventueel de controller door een knop ingedrukt te houden. Het menu werkt ook met het toetsenbord.
5. Stel wifi in via het hoofdmenu. Gebruik ethernet als de wifi-chip nog niet werkt.
6. Gebruik de meegeleverde homebrew-games om beeld, geluid en bediening te testen. Voeg eigen games toe via de gebruikelijke Batocera-mappen.
7. Sluit af vanuit het menu. De interne Windows-schijf wordt niet automatisch beschreven of geformatteerd.

De USB is bedoeld voor Intel x86_64-computers. Hij start niet als besturingssysteem op de Apple Silicon-Mac waarop de image is gemaakt.

## Wat deze versie doet

- Een eenvoudig eigen thema op 1280×800, met directe navigatie en duidelijke selectie.
- Gebruikt Batocera's bestaande PS4-controllerondersteuning; een kabel is de eerste test.
- Installeert onze laag op de USB-gebruikerspartitie, los van games en saves.
- Controleert bij opstarten de nieuwste stabiele GitHub-release. Alleen een hoger versienummer wordt geïnstalleerd.
- Controleert de SHA-256 en pakketstructuur voordat de actieve versiemap atomair wordt gewisseld. De vorige versie blijft beschikbaar.
- Geen internet, ontbrekende release of downloadfout: het bestaande menu start door.
- Slaat na ongeveer 25 seconden een Linux-hardwarerapport op in `CONSOLE-RAPPORT` op de leesbare bootpartitie. Configuratiebestanden met wifiwachtwoorden worden niet meegenomen. Technische systeemlogs kunnen lokale apparaat- en netwerkgegevens bevatten; rapporten blijven lokaal en worden niet naar GitHub gestuurd.

## D2-opslagtest en 0.1.1

De fysieke MacBook-test bevestigt Intel HD Graphics 4000 met werkende i915/Crocus-versnelling en een werkende PS4-controller via USB. Wifi wordt als `wlan0` met de b43-driver herkend; een geslaagde internetverbinding is nog niet vastgesteld.

Bij de test werd `/userdata` op een tijdelijke tmpfs van 256 MiB geplaatst. De oorspronkelijke ext4-partitie was schoon maar nog nooit aangekoppeld. Op de teststick is de partitie offline uitgebreid tot ongeveer 20 GB. De aangepaste partitietabel en het vergrote ext4-bestandssysteem zijn gecontroleerd. `recover-userdata.sh` probeert vóór de populatiefase expliciet ext4 op de gegevenspartitie naast de actieve bootpartitie wanneer de standaardmethode op RAM terugvalt. Dit script formatteert geen schijven. De mount en het starten van games moeten nog opnieuw op de doellaptop worden bevestigd.

De D2-opstartbestanden bewaren service-uitvoer, systeemmeldingen en gamestartfouten. Shutdown overschrijft de opstartmetingen niet meer. Een minimumklok op de builddatum voorkomt dat een RTC die op 2022 staat meteen moderne HTTPS-certificaten afwijst; normale netwerktijdsynchronisatie blijft actief. Versie 0.1.1 herkent tijdelijke RAM-opslag, bewaart de concrete netwerkfout en accepteert een nieuwe seedversie.

## Grenzen van het prototype

- Eerste fysieke test op de MacBookPro9,2: joystick-opstartscherm gevolgd door zwart beeld. De USB-gegevenspartitie bleef leeg en onveranderd op 512 MiB; de eigen menulaag heeft die partitie dus niet bereikt. De D1-diagnose voegt `boot/boot-custom.sh` en `boot/trace-stage.sh` toe om fasen vóór `/userdata` op FAT te loggen. Dit is diagnose, nog geen bewezen oplossing voor de oorzaak. Op de teststick zijn ook zichtbare opstartmeldingen en 1280×800 ingesteld. Laat deze test drie minuten draaien en sluit de laptop af voordat de USB wordt verwijderd.

- Beeld, geluid, wifi en Bluetooth moeten nog op de echte MacBook worden getest. De diagnose in Windows bewijst Linux-compatibiliteit niet.
- De Broadcom BCM4331 wordt eerst met de beschikbare ingebouwde Linux-driver getest. Een Windows-driverfout is geen bewijs van een defecte chip.
- De Wii U GamePad met scherm is nog niet gekoppeld. Die vereist aanvullend werk met geschikte wifi-hardware en gespecialiseerde software; gewone Bluetooth-pairing is niet voldoende.
- GitHub-updates beheren onze eigen laag. Ze vervangen de Batocera-kernel of emulators niet. De basisdistributie heeft haar eigen updatefunctie.
- Er wordt niet automatisch teruggeschakeld als een nieuw thema visueel verkeerd blijkt. Wel blijft de vorige versie bewaard en is `python3 /boot/console-os/runtime.py rollback` beschikbaar.
- Deze eerste updater gebruikt publieke releases zonder token. Privérepositories werken nog niet met deze updater. Er wordt nooit een ontwikkelaarstoken van deze Mac naar de USB gekopieerd.

## Uitgevoerde controles voor 0.1.0

18 geautomatiseerde tests slagen voor de updater en de USB-doelcontroles. De image is via UEFI in QEMU opgestart; de eigen laag is onder Linux geïnstalleerd en de GitHub-controle is uitgevoerd. De virtuele videokaart heeft in deze configuratie geen bruikbare GLX-renderer. Het grafische thema en de fysieke controllers zijn daarom **nog niet visueel/functioneel geverifieerd op de doellaptop**. De image bevat wel de i915-kernelmodule en de Crocus-driver voor oudere Intel-graphics. De echte MacBook is de volgende hardwaretest.

## Een release maken

Pas `payload/manifest.json` en het versienummer in het thema aan. Voer vervolgens uit:

```sh
python3 -m unittest discover -s tests -v
python3 build-release.py
```

Maak na het uitvoeren van de tests een stabiele GitHub-release met tag `vMAJOR.MINOR.PATCH`. Voeg `dist/console-os-update.tar.gz` en de bijbehorende `.sha256` toe.

De bootpartitie bevat `postshare.sh`, `console-os/runtime.py`, `console-os/config.json`, `console-os/seed.tar.gz` en `console-os/linux-report.sh`. `postshare.sh` wordt door Batocera uitgevoerd na het beschikbaar maken van `/userdata` en voor EmulationStation start. Netwerkfouten hebben korte time-outs. Persoonlijke instellingen worden alleen bij de eerste installatie aangevuld.

## Bronnen en licenties

- [Batocera broncode en distributie](https://github.com/batocera-linux/batocera.linux)
- [Batocera opstartscripts](https://wiki.batocera.org/launch_a_script)
- [EmulationStation-themaformaat](https://github.com/batocera-linux/batocera-emulationstation/blob/master/THEMES.md)
- [Controllerondersteuning](https://wiki.batocera.org/supported_controllers)
- [Wii U GamePad-onderzoek: libdrc](https://libdrc.org/docs/index.html)

De MIT-licentie in dit project geldt alleen voor onze eigen toegevoegde bestanden. De basisdistributie en meegeleverde games/emulators houden hun eigen licenties. Hardwareverslagen, wachtwoorden, tokens en gebruikersbestanden horen niet in deze repository.
