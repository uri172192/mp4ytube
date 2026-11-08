# Streamlit Community Cloud

Aquesta carpeta s'ha de desar com `streamlit/` dins de `uri172192/mp4ytube`.
La publicació utilitza `streamlit/app.py` com a fitxer principal i Python 3.12.
Les dependències es llegeixen de `streamlit/requirements.txt` i `streamlit/packages.txt`.
FFmpeg s'instal·la amb el sistema; l'app prepara Deno 2.6.6 des del repositori oficial.

Abans de desplegar, a Advanced settings → Secrets, configura:

```toml
APP_PASSWORD = "una-contrasenya-unica-de-16-caracters-o-mes"
```

El valor de l'exemple és només una indicació: introdueix el teu secret al tauler,
mai al repositori ni al xat. L'app no permet descarregar sense aquest secret.
A Settings → Sharing, selecciona Only specific people can view this app.
El repositori actual és públic i Streamlit pot publicar amb accés públic per defecte;
la protecció amb contrasenya impedeix utilitzar el descarregador en aquest interval.

La prova curta de 8 segons està activada inicialment. Primer s'ha de verificar
amb un vídeo autoritzat que es pot descarregar des del servidor de Streamlit.
Canviar Render per Streamlit Cloud no garanteix resoldre el bloqueig de YouTube:
`Sign in to confirm you’re not a bot`. L'app mostra aquest error explícitament.
No s'exporten galetes de sessió de YouTube ni es contracten proxies.

En aquesta versió gratuïta el botó de Streamlit carrega el MP4 a la memòria.
Es limita l'enviament al navegador a 500 MB per no exhaurir-la. Per a vídeos
més grans, selecciona menys qualitat o utilitza la versió local de Windows.
L'app local original no té aquest límit de 500 MB.

Fonts:
https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
https://github.com/yt-dlp/yt-dlp/wiki/EJS
