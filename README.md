# Descarrega vídeos · accés privat

Versió web separada de l'app local de Windows. L'accés a les operacions i als MP4
requereix una contrasenya personal. La pàgina d'entrada és visible a Internet;
no és una xarxa privada. No comparteixis la contrasenya ni els seus secrets.

## Publicar a Render

1. Puja el contingut d'aquesta carpeta a un repositori GitHub privat.
2. Connecta el repositori a Render i crea un Blueprint amb `render.yaml`.
3. Mantén el pla `Free`. No afegeixis recursos de pagament sense revisar-ne el cost.
4. Render demanarà `APP_PASSWORD`: escull una contrasenya única d'almenys 16 caràcters.
   No la desis al repositori ni l'enganxis al xat. `SESSION_SECRET` es genera al servidor.
5. En acabar el desplegament, obre l'URL HTTPS assignada i inicia sessió.
6. Prova primer un fragment o vídeo curt propi/autoritzat. YouTube pot bloquejar
   adreces IP de centres de dades encara que el mateix vídeo funcioni al teu PC.

La publicació no està verificada fins que el desplegament i la prova real des
del servidor hagin passat. No hi ha cap URL publicada dins d'aquest paquet.

## Ús

Enganxa un enllaç HTTPS de YouTube, escull 480p, 720p (per defecte) o 1080p i prem
Preparar MP4. Quan acabi, prem Guardar MP4 al dispositiu. El navegador segueix la
seva configuració de descàrregues. El servidor no pot obrir carpetes del teu PC.

Un sol vídeo en procés alhora; màxim quatre hores i 3 GB. Els MP4 es transmeten
des de disc al navegador, sense carregar-los sencers a la memòria del servidor.
Cal espai temporal per a vídeo, àudio i la combinació final. Es mantenen com a
màxim tres treballs acabats; els fitxers caduquen al cap d'una hora (neteja cada
minut, o quan es consulta la sessió o es prepara un altre vídeo). Els fitxers que
s'estan enviant al navegador no s'esborren fins que acaba l'enviament.

Sessions de 12 hores, cookies HttpOnly/Secure/SameSite, protecció d'origen i CSRF,
limitació d'intents de contrasenya i rutes de fitxers protegides. Tancar sessió
revoca la sessió al servidor. Canviar els secrets requereix reiniciar el servei.
Una sola rèplica i un sol procés: no augmentis `--workers` amb aquest disseny.

Render Free pot suspendre's quan està inactiu i els fitxers temporals desapareixen
amb els reinicis. El trànsit i els minuts de construcció tenen quotes. Si afegeixes
un mètode de pagament, revisa els límits de despesa abans de descarregar partits llargs.
Referència: https://render.com/docs/free

## Execució en altres servidors

Construeix el Dockerfile i inicia el contenidor amb `APP_PASSWORD` (16+ caràcters)
i `SESSION_SECRET` (32+ caràcters aleatoris), passant-los com a secrets del servidor.
Cal un proxy HTTPS davant del contenidor. No exposis directament el port HTTP a
Internet: les cookies són Secure i es requereix un origen HTTPS coherent.

No s'inclouen contrasenyes, vídeos, dades personals ni l'entorn de Windows.
