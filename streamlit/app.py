"""Streamlit edition for Community Cloud; local Windows edition stays separate."""
from pathlib import Path
from urllib.parse import urlparse
import hmac
import platform
import shutil
import tempfile
import time
import urllib.request
import zipfile

import streamlit as st
import yt_dlp
from yt_dlp.utils import download_range_func

BASE = Path(__file__).resolve().parent

def valid_url(url):
    try:
        p = urlparse(url)
        return p.scheme in ('http', 'https') and p.port in (None, 80, 443) and not p.username and (p.hostname or '').lower() in {
            'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}
    except ValueError:
        return False

def friendly_error(exc):
    text = str(exc)
    if 'confirm' in text.lower() and 'bot' in text.lower():
        return 'YouTube està bloquejant les descàrregues des d’aquest servidor i demana confirmar que no és un robot. Aquest mateix vídeo pot funcionar a l’app local de Windows.'
    if 'requested format' in text.lower():
        return 'El vídeo no ofereix un format MP4 compatible amb la qualitat seleccionada. Prova una altra qualitat.'
    if 'private video' in text.lower() or 'sign in' in text.lower():
        return 'YouTube exigeix iniciar sessió per accedir a aquest vídeo. Aquesta app no utilitza el teu compte de YouTube.'
    if 'http error 403' in text.lower():
        return 'YouTube ha denegat l’accés al fitxer des del servidor (403).'
    if 'no space' in text.lower() or 'espai' in text.lower():
        return 'No queda prou espai temporal per completar la descàrrega.'
    return 'No s’ha pogut completar la descàrrega. Comprova l’enllaç i torna-ho a provar.'

@st.cache_resource(show_spinner=False)
def runtime():
    executable = shutil.which('deno')
    if executable:
        return executable
    # The Linux runtime is public software from the official Deno release.
    # No account cookies, passwords or tokens are exported or uploaded.
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise RuntimeError('Instal·la Deno i afegeix-lo al PATH per executar aquesta versió fora de Streamlit Cloud.')
    folder = Path(tempfile.gettempdir()) / 'streamlit-video-tools'
    folder.mkdir(exist_ok=True)
    deno = folder / 'deno'
    if not deno.exists():
        archive = folder / 'deno.zip'
        with urllib.request.urlopen('https://github.com/denoland/deno/releases/download/v2.6.6/deno-x86_64-unknown-linux-gnu.zip', timeout=60) as response:
            with archive.open('wb') as output:
                shutil.copyfileobj(response, output)
        with zipfile.ZipFile(archive) as zipped:
            with zipped.open('deno') as source, deno.open('wb') as output:
                shutil.copyfileobj(source, output)
        deno.chmod(0o755)
        archive.unlink(missing_ok=True)
    return str(deno)

def options(height, folder, hook, deno, sample=False):
    opts = {
        'format': f'bv[height<={height}][ext=mp4][vcodec^=avc1]+ba[ext=m4a]/b[height<={height}][ext=mp4]/bv[height<={height}][ext=mp4]+ba[ext=m4a]',
        'merge_output_format': 'mp4', 'noplaylist': True,
        'outtmpl': str(folder / '%(title).120s [%(id)s].%(ext)s'),
        'windowsfilenames': True, 'cachedir': False,
        'js_runtimes': {'deno': {'path': deno}},
        'socket_timeout': 30, 'retries': 2, 'extractor_retries': 2,
        'progress_hooks': [hook], 'quiet': True, 'no_warnings': False,
        'external_downloader_args': {'ffmpeg': ['-loglevel', 'error']},
        'match_filter': lambda info, *, incomplete: 'No s’admeten emissions en directe.' if info.get('is_live') else None,
    }
    if sample:
        opts['download_ranges'] = download_range_func(None, [(0, 8)])
    return opts

def password_gate():
    try:
        password = st.secrets.get('APP_PASSWORD', '')
    except Exception:
        password = ''
    if not isinstance(password, str) or len(password) < 16:
        st.info('Falta configurar la contrasenya privada a la secció Secrets de Streamlit Cloud (APP_PASSWORD, almenys 16 caràcters).')
        st.stop()
    if st.session_state.get('authenticated'):
        return
    with st.form('login', clear_on_submit=True):
        entered = st.text_input('Contrasenya d’accés', type='password')
        submitted = st.form_submit_button('Entrar', type='primary')
    if submitted:
        if time.time() < st.session_state.get('retry_after', 0):
            st.warning('Espera uns segons abans de tornar-ho a provar.')
        elif hmac.compare_digest(entered.encode(), password.encode()):
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.session_state['retry_after'] = time.time() + 5
            st.error('Contrasenya incorrecta.')
    st.stop()

def main():
    st.set_page_config(page_title='Descarrega vídeos · Streamlit', page_icon='🎬')
    st.title('🎬 Descarrega vídeos')
    password_gate()
    if st.button('Tancar sessió'):
        st.session_state.clear()
        st.rerun()
    st.write('Enganxa un enllaç de YouTube i descarrega el vídeo en MP4.')
    st.caption('Només vídeos propis o amb autorització de descàrrega.')
    url = st.text_input('Enllaç del vídeo', placeholder='https://www.youtube.com/watch?v=…').strip()
    height = st.selectbox('Qualitat màxima', [720, 480, 1080], format_func=lambda n: f'{n}p' + (' HD · Recomanada' if n == 720 else ''))
    sample = st.checkbox('Prova curta: descarregar només els primers 8 segons', value=True)
    st.caption('Comença amb la prova curta per comprovar que YouTube accepta la connexió des de Streamlit Cloud. Desmarca-la per baixar el vídeo sencer.')
    if st.button('Preparar MP4', type='primary'):
        if not valid_url(url):
            st.warning('Introdueix un enllaç vàlid de YouTube.')
            return
        previous = st.session_state.pop('download_folder', None)
        st.session_state.pop('result', None)
        if previous:
            shutil.rmtree(previous, ignore_errors=True)
        folder = Path(tempfile.mkdtemp(prefix='streamlit-video-'))
        st.session_state['download_folder'] = str(folder)
        bar = st.progress(0)
        status = st.empty()
        last = [0.0]
        def hook(data):
            if shutil.disk_usage(folder).free < 256 * 1024**2:
                raise RuntimeError('No hi ha prou espai temporal.')
            if time.monotonic() - last[0] < .3:
                return
            last[0] = time.monotonic()
            if data['status'] == 'downloading':
                total = data.get('total_bytes') or data.get('total_bytes_estimate')
                if total:
                    bar.progress(min(data.get('downloaded_bytes', 0) / total, 1.0))
                status.info('Descarregant vídeo i àudio…')
            elif data['status'] == 'finished':
                status.info('Preparant el MP4…')
        try:
            with st.spinner('Preparant la descàrrega…'):
                deno = runtime()
                with yt_dlp.YoutubeDL(options(height, folder, hook, deno, sample)) as ydl:
                    info = ydl.extract_info(url, download=True)
                    result = Path(ydl.prepare_filename(info)).with_suffix('.mp4')
                if not result.is_file():
                    raise RuntimeError('No s’ha generat el MP4.')
            bar.progress(1.0)
            status.empty()
            st.session_state['result'] = str(result)
            st.success('MP4 preparat correctament.')
        except Exception as exc:
            bar.empty()
            status.empty()
            st.error(friendly_error(exc))
            shutil.rmtree(folder, ignore_errors=True)
    result = st.session_state.get('result')
    if result and Path(result).is_file():
        path = Path(result)
        mb = path.stat().st_size / 1024**2
        st.write(path.name)
        st.caption(f'Mida: {mb:.1f} MB')
        # Community Cloud has a small memory budget: Streamlit's supported download
        # button stores the file in memory. Refuse oversized files instead of OOM.
        if mb > 500:
            st.warning('El MP4 supera els 500 MB, el límit d’enviament d’aquesta versió gratuïta. Prova 480p o utilitza l’app local per a partits grans.')
        else:
            st.download_button('Guardar MP4 al dispositiu', data=lambda: path.read_bytes(), file_name=path.name, mime='video/mp4', on_click='ignore', type='primary')
    st.caption('Els fitxers són temporals. Per a partits llargs, l’app local continua sent l’opció sense límits de memòria del servidor.')

if __name__ == '__main__':
    main()
